# -*- coding: utf-8 -*-
"""
About
=====

cosmics.py is a small and simple python module to detect and clean cosmic ray hits on images (numpy arrays or FITS), using scipy, and based on Pieter van Dokkum's L.A.Cosmic algorithm.

L.A.Cosmic = Laplacian cosmic ray detection

U{http://www.astro.yale.edu/dokkum/lacosmic/}

(article : U{http://arxiv.org/abs/astro-ph/0108003})


Additional features
===================

I pimped this a bit to suit my needs :

    - Automatic recognition of saturated stars, including their full saturation trails.
    This avoids that such stars are treated as big cosmics.
    Indeed saturated stars tend to get even uglier when you try to clean them. Plus they
    keep L.A.Cosmic iterations going on forever.
    This feature is mainly for pretty-image production. It is optional, requires one more parameter (a CCD saturation level in ADU), and uses some 
    nicely robust morphology operations and object extraction.
    
    - Scipy image analysis allows to "label" the actual cosmic ray hits (i.e. group the pixels into local islands).
    A bit special, but I use this in the scope of visualizing a PSF construction.

But otherwise the core is really a 1-to-1 implementation of L.A.Cosmic, and uses the same parameters.
Only the conventions on how filters are applied at the image edges might be different.

No surprise, this python module is much faster then the IRAF implementation, as it does not read/write every step to disk.

Usage
=====

Everything is in the file cosmics.py, all you need to do is to import it. You need pyfits, numpy and scipy.
See the demo scripts for example usages (the second demo uses f2n.py to make pngs, and thus also needs PIL).

Your image should have clean borders, cut away prescan/overscan etc.



Todo
====
Ideas for future improvements :

    - Add something reliable to detect negative glitches (dust on CCD or small traps)
    - Top level functions to simply run all this on either numpy arrays or directly on FITS files
    - Reduce memory usage ... easy
    - Switch from signal to ndimage, homogenize mirror boundaries


Malte Tewes, January 2010
"""


__version__ = '0.4'

import os
import numpy as np
import math
import scipy.signal as signal
import scipy.ndimage as ndimage


# We define the laplacian kernel to be used
laplkernel = np.array([[0.0, -1.0, 0.0], [-1.0, 4.0, -1.0], [0.0, -1.0, 0.0]])
# Other kernels :
growkernel = np.ones((3, 3))
# dilation structure for some morphological operations
dilstruct = np.ones((5, 5))
dilstruct[0, 0] = 0
dilstruct[0, 4] = 0
dilstruct[4, 0] = 0
dilstruct[4, 4] = 0
# So this dilstruct looks like :
# 01110
#   11111
#   11111
#   11111
#   01110
# and is used to dilate saturated stars and connect cosmic rays.


class cosmicsimage:
    def __init__(self, rawarray, pssl=0.0, gain=2.2, readnoise=10.0, sigclip=5.0, sigfrac=0.3, objlim=5.0,
                 satlevel=50000.0, verbose=True):
        """

        sigclip : increase this if you detect cosmics where there are none. Default is 5.0, a good value for earth-bound images.
        objlim : increase this if normal stars are detected as cosmics. Default is 5.0, a good value for earth-bound images.

        Constructor of the cosmic class, takes a 2D numpy array of your image as main argument.
        sigclip : laplacian-to-noise limit for cosmic ray detection
        objlim : minimum contrast between laplacian image and fine structure image. Use 5.0 if your image is undersampled, HST, ...

        satlevel : if we find agglomerations of pixels above this level, we consider it to be a saturated star and
        do not try to correct and pixels around it. A negative satlevel skips this feature.

        pssl is the previously subtracted sky level !

        real   gain    = 1.8          # gain (electrons/ADU)    (0=unknown)
        real   readn   = 6.5              # read noise (electrons) (0=unknown)
        ##gain0  string statsec = "*,*"       # section to use for automatic computation of gain
        real   skyval  = 0.           # sky level that has been subtracted (ADU)
        real   sigclip = 3.0          # detection limit for cosmic rays (sigma)
        real   sigfrac = 0.5          # fractional detection limit for neighbouring pixels
        real   objlim  = 3.0           # contrast limit between CR and underlying object
        int    niter   = 1            # maximum number of iterations

        """
        # internally, we will always work "with sky".
        self.rawarray = rawarray + pssl
        # In lacosmiciteration() we work on this guy
        self.cleanarray = self.rawarray.copy()
        # All False, no cosmics yet
        self.mask = np.cast['bool'](np.zeros(self.rawarray.shape))

        self.gain = gain
        self.readnoise = readnoise
        self.sigclip = sigclip
        self.objlim = objlim
        self.sigcliplow = sigclip * sigfrac
        self.satlevel = satlevel

        self.verbose = verbose

        self.pssl = pssl

        self.backgroundlevel = None  # only calculated and used if required.
        # a mask of the saturated stars, only calculated if required
        self.satstars = None

    def __str__(self):
        """
        Gives a summary of the current state, including the number of cosmic pixels in the mask etc.
        """
        stringlist = [
            "Input array : (%i, %i), %s" % (
                self.rawarray.shape[
                    0], self.rawarray.shape[1], self.rawarray.dtype.name),
            "Current cosmic ray mask : %i pixels" % np.sum(self.mask)
        ]

        if self.pssl != 0.0:
            stringlist.append(
                "Using a previously subtracted sky level of %f" % self.pssl)

        if self.satstars is not None:
            stringlist.append(
                "Saturated star mask : %i pixels" % np.sum(self.satstars))

        return "\n".join(stringlist)

    def labelmask(self, verbose=None):
        """
        Finds and labels the cosmic "islands" and returns a list of dicts containing their positions.
        This is made on purpose for visualizations a la f2n.drawstarslist, but could be useful anyway.
        """
        if verbose is None:
            verbose = self.verbose
        if verbose:
            print()
            "Labeling mask pixels ..."
        # We morphologicaly dilate the mask to generously connect "sparse" cosmics :
        #dilstruct = np.ones((5,5))
        dilmask = ndimage.morphology.binary_dilation(
            self.mask, structure=dilstruct, iterations=1, mask=None, output=None, border_value=0, origin=0,
            brute_force=False)
        # origin = 0 means center
        (labels, n) = ndimage.measurements.label(dilmask)
        # print "Number of cosmic ray hits : %i" % n
        #tofits(labels, "labels.fits", verbose = False)
        slicecouplelist = ndimage.measurements.find_objects(labels)
        # Now we have a huge list of couples of numpy slice objects giving a frame around each object
        # For plotting purposes, we want to transform this into the center of
        # each object.
        if len(slicecouplelist) != n:
            # This never happened, but you never know ...
            raise RuntimeError("Mega error in labelmask !")
        centers = [[(tup[0].start + tup[0].stop) / 2.0, (tup[1].start + tup[1].stop) / 2.0]
                   for tup in slicecouplelist]
        # We also want to know how many pixels where affected by each cosmic ray.
        # Why ? Dunno... it's fun and available in scipy :-)
        sizes = ndimage.measurements.sum(
            self.mask.ravel(), labels.ravel(), np.arange(1, n + 1, 1))
        retdictlist = [{"name": "%i" % size, "x": center[0], "y": center[1]}
                       for (size, center) in zip(sizes, centers)]

        if verbose:
            print()
            "Labeling done"

        return retdictlist

    def getdilatedmask(self, size=3):
        """
        Returns a morphologically dilated copy of the current mask.
        size = 3 or 5 decides how to dilate.
        """
        if size == 3:
            dilmask = ndimage.morphology.binary_dilation(
                self.mask, structure=growkernel, iterations=1, mask=None, output=None, border_value=0, origin=0,
                brute_force=False)
        elif size == 5:
            dilmask = ndimage.morphology.binary_dilation(
                self.mask, structure=dilstruct, iterations=1, mask=None, output=None, border_value=0, origin=0,
                brute_force=False)
        else:
            dismask = self.mask.copy()

        return dilmask

    def clean(self, mask=None, verbose=None):
        """
        Given the mask, we replace the actual problematic pixels with the masked 5x5 median value.
        This mimics what is done in L.A.Cosmic, but it's a bit harder to do in python, as there is no
        readymade masked median. So for now we do a loop...
        Saturated stars, if calculated, are also masked : they are not "cleaned", but their pixels are not
        used for the interpolation.

        We will directly change self.cleanimage. Instead of using the self.mask, you can supply your
        own mask as argument. This might be useful to apply this cleaning function iteratively.
        But for the true L.A.Cosmic, we don't use this, i.e. we use the full mask at each iteration.

        """
        if verbose is None:
            verbose = self.verbose
        if mask is None:
            mask = self.mask

        if verbose:
            print()
            "Cleaning cosmic affected pixels ..."

        # So... mask is a 2D array containing False and True, where True means "here is a cosmic"
        # We want to loop through these cosmics one by one.
        cosmicindices = np.argwhere(mask)
        # This is a list of the indices of cosmic affected pixels.
        # print cosmicindices

        # We put cosmic ray pixels to np.Inf to flag them :
        self.cleanarray[mask] = np.Inf

        # Now we want to have a 2 pixel frame of Inf padding around our image.
        w = self.cleanarray.shape[0]
        h = self.cleanarray.shape[1]
        padarray = np.zeros((w + 4, h + 4)) + np.Inf
        # that copy is important, we need 2 independent arrays
        padarray[2:w + 2, 2:h + 2] = self.cleanarray.copy()

        # The medians will be evaluated in this padarray, skipping the np.Inf.
        # Now in this copy called padarray, we also put the saturated stars to
        # np.Inf, if available :
        if self.satstars is not None:
            padarray[2:w + 2, 2:h + 2][self.satstars] = np.Inf
            # Viva python, I tested this one, it works...

        # A loop through every cosmic pixel :
        for cosmicpos in cosmicindices:
            x = cosmicpos[0]
            y = cosmicpos[1]
            # remember the shift due to the padding !
            cutout = padarray[x:x + 5, y:y + 5].ravel()
            # print cutout
            # Now we have our 25 pixels, some of them are np.Inf, and we want
            # to take the median
            goodcutout = cutout[cutout != np.Inf]
            # print np.alen(goodcutout)

            if np.alen(goodcutout) >= 25:
                # This never happened, but you never know ...
                raise RuntimeError("Mega error in clean !")
            elif np.alen(goodcutout) > 0:
                replacementvalue = np.median(goodcutout)
            else:
                # i.e. no good pixels : Shit, a huge cosmic, we will have to
                # improvise ...
                print("OH NO, I HAVE A HUUUUUUUGE COSMIC !!!!!")
                replacementvalue = self.guessbackgroundlevel()

            # We update the cleanarray,
            # but measure the medians in the padarray, so to not mix things
            # up...
            self.cleanarray[x, y] = replacementvalue

        # That's it.
        if verbose:
            print(
            "Cleaning done")

        # FYI, that's how the LACosmic cleaning looks in iraf :
        """
        imarith(outmask,"+",finalsel,outmask)
        imreplace(outmask,1,lower=1,upper=INDEF) # ok so outmask = 1 are the cosmics
        imcalc(outmask,inputmask,"(1.-10000.*im1)",verb-)
        imarith(oldoutput,"*",inputmask,inputmask)
        median(inputmask,med5,5,5,zloreject=-9999,zhi=INDEF,verb-)
        imarith(outmask,"*",med5,med5)
        if (i>1) imdel(output)
        imcalc(oldoutput//","//outmask//","//med5,output,"(1.-im2)*im1+im3",verb-)

        # =

        merging to full mask
        inputmask = 1.0 - 10000.0 * finalsel # So this is 1.0, but cosmics are very negative
        inputmask = oldoutput * inputmask # orig image, with very negative cosmics
        med5 = median of inputmask, but rejecting these negative cosmics
        # i dunno how to do this in python -> had to do the loop
        med5 = finalsel * med5 # we keep only the cosmics of this median
        # actual replacement :
        output = (1.0 - outmask)*oldoutput + med5 # ok
        """

    def findsatstars(self, verbose=None):
        """
        Uses the satlevel to find saturated stars (not cosmics !), and puts the result as a mask in self.satstars.
        This can then be used to avoid these regions in cosmic detection and cleaning procedures.
        Slow ...
        """
        if verbose is None:
            verbose = self.verbose
        if verbose:
            print()
            "Detecting saturated stars ..."
        # DETECTION

        satpixels = self.rawarray > self.satlevel  # the candidate pixels

        # We build a smoothed version of the image to look for large stars and
        # their support :
        m5 = ndimage.filters.median_filter(
            self.rawarray, size=5, mode='mirror')
        # We look where this is above half the satlevel
        largestruct = m5 > (self.satlevel / 2.0)
        # The rough locations of saturated stars are now :
        satstarscenters = np.logical_and(largestruct, satpixels)

        if verbose:
            print()
            "Building mask of saturated stars ..."

        # BUILDING THE MASK
        # The subtility is that we want to include all saturated pixels connected to these saturated stars...
        # I haven't found a better solution then the double loop

        # We dilate the satpixels alone, to ensure connectivity in glitchy regions and to add a safety margin around them.
        #dilstruct = np.array([[0,1,0], [1,1,1], [0,1,0]])

        dilsatpixels = ndimage.morphology.binary_dilation(
            satpixels, structure=dilstruct, iterations=2, mask=None, output=None, border_value=0, origin=0,
            brute_force=False)
        # It turns out it's better to think large and do 2 iterations...

        # We label these :
        (dilsatlabels, nsat) = ndimage.measurements.label(dilsatpixels)
        #tofits(dilsatlabels, "test.fits")

        if verbose:
            print()
            "We have %i saturated stars." % nsat

        # The ouput, False for now :
        outmask = np.zeros(self.rawarray.shape)

        # we go through the islands of saturated pixels
        for i in range(1, nsat + 1):
            thisisland = dilsatlabels == i  # gives us a boolean array
            # Does this intersect with satstarscenters ?
            overlap = np.logical_and(thisisland, satstarscenters)
            if np.sum(overlap) > 0:
                # we add thisisland to the mask
                outmask = np.logical_or(outmask, thisisland)

        self.satstars = np.cast['bool'](outmask)

        if verbose:
            print()
            "Mask of saturated stars done"

    def getsatstars(self, verbose=None):
        """
        Returns the mask of saturated stars after finding them if not yet done.
        Intended mainly for external use.
        """
        if verbose is None:
            verbose = self.verbose
        if not self.satlevel > 0:
            raise RuntimeError("Cannot determine satstars : you gave satlevel <= 0 !")
        if self.satstars is None:
            self.findsatstars(verbose=verbose)
        return self.satstars

    def getmask(self):
        return self.mask

    def getrawarray(self):
        """
        For external use only, as it returns the rawarray minus pssl !
        """
        return self.rawarray - self.pssl

    def getcleanarray(self):
        """
        For external use only, as it returns the cleanarray minus pssl !
        """
        return self.cleanarray - self.pssl

    def guessbackgroundlevel(self):
        """
        Estimates the background level. This could be used to fill pixels in large cosmics.
        """
        if self.backgroundlevel == None:
            self.backgroundlevel = np.median(self.rawarray.ravel())
        return self.backgroundlevel

    def lacosmiciteration(self, verbose=None):
        """
        Performs one iteration of the L.A.Cosmic algorithm.
        It operates on self.cleanarray, and afterwards updates self.mask by adding the newly detected
        cosmics to the existing self.mask. Cleaning is not made automatically ! You have to call
        clean() after each iteration.
        This way you can run it several times in a row to to L.A.Cosmic "iterations".
        See function lacosmic, that mimics the full iterative L.A.Cosmic algorithm.

        Returns a dict containing
                - niter : the number of cosmic pixels detected in this iteration
                - nnew : among these, how many were not yet in the mask
                - itermask : the mask of pixels detected in this iteration
                - newmask : the pixels detected that were not yet in the mask

        If findsatstars() was called, we exclude these regions from the search.

        """

        if verbose is None:
            verbose = self.verbose

        if verbose:
            print()
            "Convolving image with Laplacian kernel ..."

        # We subsample, convolve, clip negative values, and rebin to original
        # size
        subsam = subsample(self.cleanarray)
        conved = signal.convolve2d(
            subsam, laplkernel, mode="same", boundary="symm")
        cliped = conved.clip(min=0.0)
        # cliped = np.abs(conved) # unfortunately this does not work to find
        # holes as well ...
        lplus = rebin2x2(cliped)

        if verbose:
            print()
            "Creating noise model ..."

        # We build a custom noise map, so to compare the laplacian to
        m5 = ndimage.filters.median_filter(
            self.cleanarray, size=5, mode='mirror')
        # We keep this m5, as I will use it later for the interpolation.
        m5clipped = m5.clip(min=0.00001)  # As we will take the sqrt
        noise = (1.0 / self.gain) * np.sqrt(
            self.gain * m5clipped + self.readnoise * self.readnoise)

        if verbose:
            print()
            "Calculating Laplacian signal to noise ratio ..."

        # Laplacian signal to noise ratio :
        s = lplus / (2.0 * noise)  # the 2.0 is from the 2x2 subsampling
        # This s is called sigmap in the original lacosmic.cl

        # We remove the large structures (s prime) :
        sp = s - ndimage.filters.median_filter(s, size=5, mode='mirror')

        if verbose:
            print()
            "Selecting candidate cosmic rays ..."

        # Candidate cosmic rays (this will include stars + HII regions)
        candidates = sp > self.sigclip
        nbcandidates = np.sum(candidates)

        if verbose:
            print()
            "  %5i candidate pixels" % nbcandidates

        # At this stage we use the saturated stars to mask the candidates, if
        # available :
        if self.satstars is not None:
            if verbose:
                print()
                "Masking saturated stars ..."
            candidates = np.logical_and(
                np.logical_not(self.satstars), candidates)
            nbcandidates = np.sum(candidates)

            if verbose:
                print()
                "  %5i candidate pixels not part of saturated stars" % nbcandidates

        if verbose:
            print()
            "Building fine structure image ..."

        # We build the fine structure image :
        m3 = ndimage.filters.median_filter(
            self.cleanarray, size=3, mode='mirror')
        m37 = ndimage.filters.median_filter(m3, size=7, mode='mirror')
        f = m3 - m37
        # In the article that's it, but in lacosmic.cl f is divided by the noise...
        # Ok I understand why, it depends on if you use sp/f or L+/f as criterion.
        # There are some differences between the article and the iraf implementation.
        # So I will stick to the iraf implementation.
        f = f / noise
        # as we will divide by f. like in the iraf version.
        f = f.clip(min=0.01)

        if verbose:
            print()
            "Removing suspected compact bright objects ..."

        # Now we have our better selection of cosmics :
        cosmics = np.logical_and(candidates, sp / f > self.objlim)
        # Note the sp/f and not lplus/f ... due to the f = f/noise above.

        nbcosmics = np.sum(cosmics)

        if verbose:
            print()
            "  %5i remaining candidate pixels" % nbcosmics

        # What follows is a special treatment for neighbors, with more relaxed
        # constains.

        if verbose:
            print()
            "Finding neighboring pixels affected by cosmic rays ..."

        # We grow these cosmics a first time to determine the immediate
        # neighborhod  :
        growcosmics = np.cast['bool'](
            signal.convolve2d(np.cast['float32'](cosmics), growkernel, mode="same", boundary="symm"))

        # From this grown set, we keep those that have sp > sigmalim
        # so obviously not requiring sp/f > objlim, otherwise it would be
        # pointless
        growcosmics = np.logical_and(sp > self.sigclip, growcosmics)

        # Now we repeat this procedure, but lower the detection limit to
        # sigmalimlow :

        finalsel = np.cast['bool'](
            signal.convolve2d(np.cast['float32'](growcosmics), growkernel, mode="same", boundary="symm"))
        finalsel = np.logical_and(sp > self.sigcliplow, finalsel)

        # Again, we have to kick out pixels on saturated stars :
        if self.satstars is not None:
            if verbose:
                print()
                "Masking saturated stars ..."
            finalsel = np.logical_and(np.logical_not(self.satstars), finalsel)

        nbfinal = np.sum(finalsel)

        if verbose:
            print()
            "  %5i pixels detected as cosmics" % nbfinal

        # Now the replacement of the cosmics...
        # we outsource this to the function clean(), as for some purposes the cleaning might not even be needed.
        # Easy way without masking would be :
        #self.cleanarray[finalsel] = m5[finalsel]

        # We find how many cosmics are not yet known :
        newmask = np.logical_and(np.logical_not(self.mask), finalsel)
        nbnew = np.sum(newmask)

        # We update the mask with the cosmics we have found :
        self.mask = np.logical_or(self.mask, finalsel)

        # We return
        # (used by function lacosmic)

        return {"niter": nbfinal, "nnew": nbnew, "itermask": finalsel, "newmask": newmask}

    def findholes(self, verbose=True):
        """
        Detects "negative cosmics" in the cleanarray and adds them to the mask.
        This is not working yet.
        """
        pass

        """
        if verbose == None:
            verbose = self.verbose
        
        if verbose :
            print "Finding holes ..."

        m3 = ndimage.filters.median_filter(self.cleanarray, size=3, mode='mirror')
        h = (m3 - self.cleanarray).clip(min=0.0)
        
        tofits("h.fits", h)
        sys.exit()
        
        # The holes are the peaks in this image that are not stars
    
        #holes = h > 300
        """
        """
        subsam = subsample(self.cleanarray)
        conved = -signal.convolve2d(subsam, laplkernel, mode="same", boundary="symm")
        cliped = conved.clip(min=0.0)
        lplus = rebin2x2(conved)
        
        tofits("lplus.fits", lplus)
        
        m5 = ndimage.filters.median_filter(self.cleanarray, size=5, mode='mirror')
        m5clipped = m5.clip(min=0.00001)
        noise = (1.0/self.gain) * np.sqrt(self.gain*m5clipped + self.readnoise*self.readnoise)
 
        s = lplus / (2.0 * noise) # the 2.0 is from the 2x2 subsampling
        # This s is called sigmap in the original lacosmic.cl
        
        # We remove the large structures (s prime) :
        sp = s - ndimage.filters.median_filter(s, size=5, mode='mirror')
        
        holes = sp > self.sigclip   
        """
        """
        # We have to kick out pixels on saturated stars :
        if self.satstars != None:
            if verbose:
                print "Masking saturated stars ..."
            holes = np.logical_and(np.logical_not(self.satstars), holes)
        
        if verbose:
            print "%i hole pixels found" % np.sum(holes)
        
        # We update the mask with the holes we have found :
        self.mask = np.logical_or(self.mask, holes)
        """

    def run(self, maxiter=4, verbose=False):
        """
        Full artillery :-)
                - Find saturated stars
                - Run maxiter L.A.Cosmic iterations (stops if no more cosmics are found)

        Stops if no cosmics are found or if maxiter is reached.
        """

        if self.satlevel > 0 and self.satstars is None:
            self.findsatstars(verbose=True)

        print()
        "Starting %i L.A.Cosmic iterations ..." % maxiter
        for i in range(1, maxiter + 1):
            print()
            "Iteration %i" % i

            iterres = self.lacosmiciteration(verbose=verbose)
            print()
            "%i cosmic pixels (%i new)" % (iterres["niter"], iterres["nnew"])

            # self.clean(mask = iterres["mask"]) # No, we want clean to operate on really clean pixels only !
            # Thus we always apply it on the full mask, as lacosmic does :
            self.clean(verbose=verbose)
            # But note that for huge cosmics, one might want to revise this.
            # Thats why I added a feature to skip saturated stars !

            if iterres["niter"] == 0:
                break


# Top-level functions


# def fullarray(verbose = False):
#   """
#   Applies the full artillery using and returning only numpy arrays
#   """
#   pass
#
# def fullfits(infile, outcleanfile = None, outmaskfile = None):
#   """
#   Applies the full artillery of the function fullarray() directly on FITS files.
#   """
#   pass


# Array manipulation

def subsample(a):  # this is more a generic function then a method ...
    """
    Returns a 2x2-subsampled version of array a (no interpolation, just cutting pixels in 4).
    The version below is directly from the scipy cookbook on rebinning :
    U{http://www.scipy.org/Cookbook/Rebinning}
    There is ndimage.zoom(cutout.array, 2, order=0, prefilter=False), but it makes funny borders.

    """
    """
    # Ouuwww this is slow ...
    outarray = np.zeros((a.shape[0]*2, a.shape[1]*2), dtype=np.float64)
    for i in range(a.shape[0]):
        for j in range(a.shape[1]): 
            outarray[2*i,2*j] = a[i,j]
            outarray[2*i+1,2*j] = a[i,j]
            outarray[2*i,2*j+1] = a[i,j]
            outarray[2*i+1,2*j+1] = a[i,j]
    return outarray
    """
    # much better :
    newshape = (2 * a.shape[0], 2 * a.shape[1])
    slices = [slice(0, old, float(old) / new)
              for old, new in zip(a.shape, newshape)]
    coordinates = np.mgrid[slices]
    #choose the biggest smaller integer index
    indices = coordinates.astype('i')
    return a[tuple(indices)]


def rebin(a, newshape):
    """
    Auxiliary function to rebin an ndarray a.
    U{http://www.scipy.org/Cookbook/Rebinning}

            >>> a=rand(6,4); b=rebin(a,(3,2))
    """

    shape = a.shape
    lenShape = len(shape)
    factor = np.asarray(shape) / np.asarray(newshape)
    # print factor
    evList = ['a.reshape('] + \
             ['int(newshape[%d]),int(factor[%d]),' % (i, i) for i in range(lenShape)] + \
             [')'] + ['.sum(%d)' % (i + 1) for i in range(lenShape)] + \
             ['/factor[%d]' % i for i in range(lenShape)]

    return eval(''.join(evList))


def rebin2x2(a):
    """
    Wrapper around rebin that actually rebins 2 by 2
    """
    inshape = np.array(a.shape)
    # Modulo check to see if size is even
    if not (inshape % 2 == np.zeros(2)).all():
        raise RuntimeError("I want even image shapes !")

    return rebin(a, inshape / 2)
