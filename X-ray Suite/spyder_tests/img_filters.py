# -*- coding: utf-8 -*-
"""
Created on Sat Nov 30 00:09:20 2013

@author: Clemens
"""
from scipy import ndimage, interpolate
import numpy as np

import matplotlib.pyplot as plt
import matplotlib.image as mpimg
from skimage import measure
from skimage import data, filter, color
from skimage.transform import hough_circle

img = mpimg.imread('LaB6_p49_40keV.tif')

img1 = ndimage.gaussian_filter(img,10)
#plt.imshow(img1, vmax=2500)

[x,y]=np.meshgrid(np.linspace(0,2048,2048),np.linspace(0,2048,2048))
test = interpolate.RectBivariateSpline(np.linspace(0,2048,2048),
                                       np.linspace(0,2048,2048),
                                       img1)

print test(1020,200)

#plt.imshow(img)


#detect contours

candy = filter.canny(img, sigma=2, low_threshold=90, high_threshold=120)
plt.imshow(candy, cmap='hot')
