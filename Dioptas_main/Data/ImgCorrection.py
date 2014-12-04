# -*- coding: utf8 -*-
__author__ = 'Clemens Prescher'

import numpy as np
import time


class ImgCorrectionManager(object):
    def __init__(self, img_shape=None):
        self._corrections = {}
        self._ind = 0
        self.shape = img_shape

    def add(self, ImgCorrection, name=None):
        if self.shape is None:
            self.shape = ImgCorrection.shape()

        if self.shape == ImgCorrection.shape():
            if name is None:
                name = self._ind
                self._ind += 1
            self._corrections[name] = ImgCorrection
            return True
        return False

    def has_items(self):
        return len(self._corrections)!=0

    def delete(self, name=None):
        if name is None:
            if self._ind == 0:
                return
            self._ind -= 1
            name = self._ind
        del self._corrections[name]
        if len(self._corrections) == 0:
            self.clear()

    def clear(self):
        self._corrections={}
        self.shape=None
        self._ind=0

    def set_shape(self, shape):
        if self.shape != shape:
            self.clear()
        self.shape = shape

    def get_data(self):
        if len(self._corrections) == 0:
            return None

        res = np.ones(self.shape)
        for key, correction in self._corrections.iteritems():
            res *= correction.get_data()
        return res

    def get_correction(self, name):
        return self._corrections[name]


class ImgCorrectionInterface(object):
    def get_data(self):
        raise NotImplementedError

    def shape(self):
        raise NotImplementedError


class CbnCorrection(ImgCorrectionInterface):
    def __init__(self, tth_array, azi_array, diamond_thickness, seat_thickness, small_cbn_seat_radius,
                 large_cbn_seat_radius, tilt=0, tilt_rotation=0):
        self.tth_array = tth_array
        self.azi_array = azi_array
        self.diamond_thickness = diamond_thickness
        self.seat_thickness = seat_thickness
        self.small_cbn_seat_radius = small_cbn_seat_radius
        self.large_cbn_seat_radius = large_cbn_seat_radius
        self.tilt = tilt
        self.tilt_rotation = tilt_rotation

        self._data = None
        self.update()


    def get_data(self):
        return self._data

    def shape(self):
        return self._data.shape

    def update(self):
        # diam - diamond thickness
        # ds - seat thickness
        # r1 - small radius
        #r2 - large radius
        #tilt - tilting angle of DAC

        diam = self.diamond_thickness
        ds = self.seat_thickness
        r1 = self.small_cbn_seat_radius
        r2 = self.large_cbn_seat_radius
        tilt = -self.tilt
        tilt_rotation = self.tilt_rotation

        t = self.tth_array
        a = self.azi_array

        dtor = np.pi / 180.0

        # ;calculate 2-theta limit for seat
        ts1 = 180 / np.pi * np.arctan(r1 / diam)
        ts2 = 180 / np.pi * np.arctan(r2 / (diam + ds))
        tseat = 180 / np.pi * np.arctan((r2 - r1) / ds)
        tcell = 180 / np.pi * np.arctan(((19. - 7) / 2) / 15.)
        tc1 = 180 / np.pi * np.arctan((7. / 2) / (diam + ds))
        tc2 = 180 / np.pi * np.arctan((19. / 2) / (diam + ds + 10.))
        print 'ts1=', ts1, '  ts2=', ts2, '  tseat=', tseat, '   tcell=', tc1, tc2, tcell

        tt = np.sqrt(t ** 2 + tilt ** 2 - 2 * t * tilt * np.cos(dtor * (a + tilt_rotation)))

        # ;absorption by diamond
        c = diam / np.cos(dtor * tt)
        ac = np.exp(-0.215680897 * 3.516 * c / 10)


        # ;absorption by conic part of seat
        if (ts2 >= ts1):
            deltar = (c * np.sin(dtor * tt) - r1).clip(min=0)
            cc = deltar * np.sin(dtor * (90 - tseat)) / np.sin(dtor * (tseat - tt.clip(max=ts2)))
            acc = np.exp(-(0.183873713 + 0.237310767) / 2 * 3.435 * cc / 10)
            accc = (acc - 1.) * (np.logical_and(tt >= ts1, tt <= ts2)) + 1
            # ;absorption by seat
            ccs = ds / np.cos(dtor * tt)
            accs = np.exp(-(0.183873713 + 0.237310767) / 2 * 3.435 * ccs / 10)
            accsc = (accs - 1.) * (tt >= ts2) + 1

        else:
            print 'in the else path'
            delta = ((diam + ds) * np.tan(dtor * tt) - r2).clip(min=0)

            cc = delta * np.sin(dtor * (90 + tseat)) / np.sin(dtor * (tt.clip(max < ts1) - tseat))

            acc = np.exp(-(0.183873713 + 0.237310767) / 2 * 3.435 * cc / 10)

            accc = (acc - 1.) * (np.logical_and(tt >= ts2, tt <= ts1)) + 1
            # ;absorption by seat
            ccs = ds / np.cos(dtor * tt)
            accs = np.exp(-(0.183873713 + 0.237310767) / 2 * 3.435 * ccs / 10)
            accsc = (accs - 1.) * (tt >= ts1) + 1

        self._data= ac * accc * accsc


class ObliqueAngleDetectorAbsorptionCorrection(ImgCorrectionInterface):
    def __init__(self, tth_array, azi_array, detector_thickness, absorption_length, tilt, rotation):
        self.tth_array = tth_array
        self.azi_array = azi_array
        self.detector_thickness = detector_thickness
        self.absorption_length = absorption_length
        self.tilt = tilt
        self.rotation = rotation

        self._data = None
        self.update()

    def get_data(self):
        return self._data

    def shape(self):
        return self._data.shape

    def update(self):
        tilt_rad = self.tilt / 180.0 * np.pi
        rotation_rad = self.rotation / 180.0 * np.pi

        path_length = self.detector_thickness / np.cos(
            np.sqrt(self.tth_array ** 2 + tilt_rad ** 2 - 2 * tilt_rad * self.tth_array * \
                    np.cos(np.pi - self.azi_array + rotation_rad)))

        attenuation_constant = 1.0 / self.absorption_length
        absorption_correction = (1 - np.exp(-attenuation_constant * path_length)) / \
                                (1 - np.exp(-attenuation_constant * self.detector_thickness))

        self._data = absorption_correction


class DummyCorrection(ImgCorrectionInterface):
    """
    Used in particular for unit tests
    """
    def __init__(self, shape, number=1):
        self._data = np.ones(shape)*number
        self._shape = shape

    def get_data(self):
        return self._data

    def shape(self):
        return self._shape