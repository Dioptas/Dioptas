# -*- coding: utf8 -*-
__author__ = 'Clemens Prescher'

import numpy as np
import time


class ImgCorrectionManager(object):
    def __init__(self, img_shape=None):
        self._corrections = {}
        self._ind = 0
        self.shape = img_shape

    def add(self, img_correction, name=None):
        if self.shape is None:
            self.shape = img_correction.shape()

        if self.shape == img_correction.shape():
            if name is None:
                name = self._ind
                self._ind += 1
            self._corrections[name] = img_correction
            return True
        return False

    def has_items(self):
        return len(self._corrections) != 0

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
        self._corrections = {}
        self.shape = None
        self._ind = 0

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
        try:
            return self._corrections[name]
        except KeyError:
            return None


class ImgCorrectionInterface(object):
    def get_data(self):
        raise NotImplementedError

    def shape(self):
        raise NotImplementedError


class CbnCorrection(ImgCorrectionInterface):
    def __init__(self, tth_array, azi_array,
                 diamond_thickness, seat_thickness,
                 small_cbn_seat_radius, large_cbn_seat_radius,
                 tilt=0, tilt_rotation=0,
                 diamond_abs_length=13.7, cbn_abs_length=14.05,
                 center_offset=0, center_offset_angle=0):
        self._tth_array = tth_array
        self._azi_array = azi_array
        self._diamond_thickness = diamond_thickness
        self._seat_thickness = seat_thickness
        self._small_cbn_seat_radius = small_cbn_seat_radius
        self._large_cbn_seat_radius = large_cbn_seat_radius
        self._tilt = tilt
        self._tilt_rotation = tilt_rotation
        self._diamond_abs_length = diamond_abs_length
        self._cbn_abs_length = cbn_abs_length
        self._center_offset = center_offset
        self._center_offset_angle = center_offset_angle

        self._data = None

    def get_data(self):
        return self._data

    def shape(self):
        return self._data.shape

    def update(self):

        # diam - diamond thickness
        # ds - seat thickness
        # r1 - small radius
        # r2 - large radius
        # tilt - tilting angle of DAC
        dtor = np.pi / 180.0

        diam = self._diamond_thickness
        ds = self._seat_thickness
        r1 = self._small_cbn_seat_radius
        r2 = self._large_cbn_seat_radius
        tilt = -self._tilt * dtor
        tilt_rotation = self._tilt_rotation * dtor
        center_offset_angle = self._center_offset_angle * dtor

        t = self._tth_array * dtor
        a = self._azi_array * dtor

        if self._center_offset != 0:
            beta = a - np.arcsin(
                self._center_offset * np.sin((np.pi - (a + center_offset_angle))) / r1) + center_offset_angle
            r1 = np.sqrt(r1 ** 2 + self._center_offset ** 2 - 2 * r1 * self._center_offset * np.cos(beta))
            r2 = np.sqrt(r2 ** 2 + self._center_offset ** 2 - 2 * r2 * self._center_offset * np.cos(beta))


        # ;calculate 2-theta limit for seat
        ts1 = np.arctan(r1 / diam)
        ts2 = np.arctan(r2 / (diam + ds))
        tseat = np.arctan((r2 - r1) / ds)

        tt = np.sqrt(t ** 2 + tilt ** 2 - 2 * t * tilt * np.cos(a + tilt_rotation))

        # ;absorption by diamond
        c = diam / np.cos(tt)
        # old version from Vitali
        ac = np.exp(-c / self._diamond_abs_length)

        # # ;absorption by conic part of seat
        deltar = (c * np.sin(tt) - r1).clip(min=0)

        cc = deltar * np.sin(np.pi - tseat) / (np.sin(tseat - tt.clip(max=ts2)) * np.tan(tseat))

        acc = np.exp(-cc / self._cbn_abs_length)
        accc = (acc - 1.) * (np.logical_and(tt >= ts1, tt <= ts2)) + 1

        ccs = ds / np.cos(tt)
        accs = np.exp(-ccs / self._cbn_abs_length)
        accsc = (accs - 1.) * (tt >= ts2) + 1

        self._data = ac * accc * accsc

    def __eq__(self, other):
        if not isinstance(other, CbnCorrection):
            return False
        if self._diamond_thickness != other._diamond_thickness:
            return False
        if self._seat_thickness != other._seat_thickness:
            return False
        if self._small_cbn_seat_radius != other._small_cbn_seat_radius:
            return False
        if self._large_cbn_seat_radius != other._large_cbn_seat_radius:
            return False
        if self._tilt != other._tilt:
            return False
        if self._tilt_rotation != other._tilt_rotation:
            return False
        if self._diamond_abs_length != other._diamond_abs_length:
            return False
        if self._cbn_abs_length != other._cbn_abs_length:
            return False
        if self._center_offset != other._center_offset:
            return False
        if self._center_offset_angle != other._center_offset_angle:
            return False
        if not np.array_equal(self._tth_array, other._tth_array):
            return False
        if not np.array_equal(self._azi_array, other._azi_array):
            return False
        return True


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
        self._data = np.ones(shape) * number
        self._shape = shape

    def get_data(self):
        return self._data

    def shape(self):
        return self._shape