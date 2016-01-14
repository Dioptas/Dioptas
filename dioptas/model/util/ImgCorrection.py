# -*- coding: utf8 -*-


import numpy as np


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
        self._seat_abs_length = cbn_abs_length
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
        tilt_rotation = self._tilt_rotation * dtor + np.pi / 2
        center_offset_angle = self._center_offset_angle * dtor

        two_theta = self._tth_array * dtor
        azi = self._azi_array * dtor

        # calculate radius of the cone for each pixel specific to a center_offset and rotation angle
        if self._center_offset != 0:
            beta = azi - np.arcsin(
                    self._center_offset * np.sin((np.pi - (azi + center_offset_angle))) / r1) + center_offset_angle
            r1 = np.sqrt(r1 ** 2 + self._center_offset ** 2 - 2 * r1 * self._center_offset * np.cos(beta))
            r2 = np.sqrt(r2 ** 2 + self._center_offset ** 2 - 2 * r2 * self._center_offset * np.cos(beta))

        # defining rotation matrices for the diamond anvil cell
        Rx = np.matrix([[1, 0, 0],
                        [0, np.cos(tilt_rotation), -np.sin(tilt_rotation)],
                        [0, np.sin(tilt_rotation), np.cos(tilt_rotation)]])

        Ry = np.matrix([[np.cos(tilt), 0, np.sin(tilt)],
                        [0, 1, 0],
                        [-np.sin(tilt), 0, np.cos(tilt)]])

        dac_vector = np.array(Rx * Ry * np.matrix([1, 0, 0]).T)

        # calculating a diffraction vector for each pixel
        diffraction_vec = np.array([np.cos(two_theta),
                                    np.cos(azi) * np.sin(two_theta),
                                    np.sin(azi) * np.sin(two_theta)])

        # angle between diffraction vector and diamond anvil cell vector based on dot product:
        tt = np.arccos(dot_product(dac_vector, diffraction_vec) / \
                       (vector_len(dac_vector) * vector_len(diffraction_vec)))

        # calculate path through diamond its absorption
        path_diamond = diam / np.cos(tt)
        abs_diamond = np.exp(-path_diamond / self._diamond_abs_length)

        # define the different regions for the absorption in the seat
        # region 2 is partial absorption (in the cone) and region 3 is complete absorbtion
        ts1 = np.arctan(r1 / diam)
        ts2 = np.arctan(r2 / (diam + ds))
        tseat = np.arctan((r2 - r1) / ds)

        region2 = np.logical_and(tt > ts1, tt < ts2)
        region3 = tt >= ts2

        # calculate the paths through each region
        path_seat = np.zeros(tt.shape)
        if self._center_offset != 0:
            deltar = diam * np.tan(tt[region2]) - r1[region2]
            alpha = np.pi / 2. - tseat[region2]
            gamma = np.pi - (alpha + tt[region2] + np.pi / 2)
        else:
            deltar = diam * np.tan(tt[region2]) - r1
            alpha = np.pi / 2. - tseat
            gamma = np.pi - (alpha + tt[region2] + np.pi / 2)

        path_seat[region2] = deltar * np.sin(alpha) / np.sin(gamma)
        path_seat[region3] = ds / np.cos(tt[region3])

        abs_seat = np.exp(-path_seat / self._seat_abs_length)

        # combine both, diamond and seat absorption correction
        self._data = abs_diamond * abs_seat

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
        if self._seat_abs_length != other._seat_abs_length:
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


def vector_len(vec):
    return np.sqrt(vec[0] ** 2 + vec[1] ** 2 + vec[2] ** 2)


def dot_product(vec1, vec2):
    return vec1[0] * vec2[0] + vec1[1] * vec2[1] + vec1[2] * vec2[2]
