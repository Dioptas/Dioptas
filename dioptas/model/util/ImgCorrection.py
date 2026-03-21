# SPDX-License-Identifier: MIT

import numpy as np
import fabio
from PIL import Image


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

    def get_data(self):
        if len(self._corrections) == 0:
            return None

        res = np.ones(self.shape)
        for key, correction in self._corrections.items():
            res *= correction.get_data()
        return res

    def get_correction(self, name):
        try:
            return self._corrections[name]
        except KeyError:
            return None

    @property
    def corrections(self):
        return self._corrections


class ImgCorrectionInterface(object):
    def get_data(self):
        raise NotImplementedError

    def shape(self):
        raise NotImplementedError


class CbnCorrection(ImgCorrectionInterface):
    def __init__(self, tth_array=[], azi_array=[],
                 diamond_thickness=2.0, seat_thickness=5.0,
                 small_cbn_seat_radius=0.5, large_cbn_seat_radius=2.0,
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

    def get_params(self):
        return {'diamond_thickness': self._diamond_thickness,
                'seat_thickness': self._seat_thickness,
                'small_cbn_seat_radius': self._small_cbn_seat_radius,
                'large_cbn_seat_radius': self._large_cbn_seat_radius,
                'tilt': self._tilt,
                'tilt_rotation': self._tilt_rotation,
                'diamond_abs_length': self._diamond_abs_length,
                'seat_abs_length': self._seat_abs_length,
                'center_offset': self._center_offset,
                'center_offset_angle': self._center_offset_angle}

    def set_params(self, params):
        self._diamond_thickness = params['diamond_thickness']
        self._seat_thickness = params['seat_thickness']
        self._small_cbn_seat_radius = params['small_cbn_seat_radius']
        self._large_cbn_seat_radius = params['large_cbn_seat_radius']
        self._tilt = params['tilt']
        self._tilt_rotation = params['tilt_rotation']
        self._diamond_abs_length = params['diamond_abs_length']
        self._seat_abs_length = params['seat_abs_length']
        self._center_offset = params['center_offset']
        self._center_offset_angle = params['center_offset_angle']

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
        Rx = np.array(
            [
                [1, 0, 0],
                [0, np.cos(tilt_rotation), -np.sin(tilt_rotation)],
                [0, np.sin(tilt_rotation), np.cos(tilt_rotation)],
            ],
            dtype=float,
        )

        Ry = np.array(
            [
                [np.cos(tilt), 0, np.sin(tilt)],
                [0, 1, 0],
                [-np.sin(tilt), 0, np.cos(tilt)],
            ],
            dtype=float,
        )

        dac_vector = Rx @ Ry @ np.array([1.0, 0.0, 0.0], dtype=float)

        # calculating a diffraction vector for each pixel
        diffraction_vec = np.array([np.cos(two_theta),
                                    np.cos(azi) * np.sin(two_theta),
                                    np.sin(azi) * np.sin(two_theta)])

        # angle between diffraction vector and diamond anvil cell vector based on dot product:
        tt = np.arccos(dot_product(dac_vector, diffraction_vec) /
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
    def __init__(self, tth_array, azi_array, detector_thickness=40, absorption_length=150, tilt=0, rotation=0):
        self.tth_array = tth_array
        self.azi_array = azi_array
        self.detector_thickness = detector_thickness
        self.absorption_length = absorption_length
        self.tilt = tilt
        self.rotation = rotation

        self._data = None
        self.update()

    def get_params(self):
        return {'detector_thickness': self.detector_thickness,
                'absorption_length': self.absorption_length,
                'tilt': self.tilt,
                'rotation': self.rotation
                }

    def set_params(self, params):
        self.detector_thickness = params['detector_thickness']
        self.absorption_length = params['absorption_length']
        self.tilt = params['tilt']
        self.rotation = params['rotation']

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
        with np.errstate(over="ignore", divide="ignore", invalid="ignore"):
            absorption_correction = (1 - np.exp(-attenuation_constant * path_length)) / (
                1 - np.exp(-attenuation_constant * self.detector_thickness)
            )

        self._data = absorption_correction


class TransferFunctionCorrection(ImgCorrectionInterface):
    def __init__(self, original_filename=None, response_filename=None, img_transformations=None):
        self.original_filename = None
        self.response_filename = None
        self.original_data = None
        self.response_data = None
        self.transfer_data = None

        self.img_transformations = img_transformations

        if original_filename:
            self.load_original_image(original_filename)
        if response_filename:
            self.load_response_image(response_filename)

    def load_original_image(self, img_filename):
        self.original_filename = img_filename
        self.original_data = load_image(img_filename)
        if self.response_filename:
            self.calculate_transfer_data()

    def load_response_image(self, img_filename):
        self.response_filename = img_filename
        self.response_data = load_image(img_filename)
        if self.original_filename:
            self.calculate_transfer_data()

    def set_img_transformations(self, img_transformations):
        """
        sets the image transformations
        :param img_transformations:
        """
        self.img_transformations = img_transformations
        if self.response_filename and self.original_filename:
            self.calculate_transfer_data()

    def calculate_transfer_data(self):
        transfer_data = self.response_data / self.original_data
        if self.img_transformations:
            for transformation in self.img_transformations:
                transfer_data = transformation(transfer_data)
        self.transfer_data = transfer_data

    def get_data(self):
        return self.transfer_data

    def shape(self):
        return self.transfer_data.shape

    def get_params(self):
        return {
            'original_filename': self.original_filename,
            'response_filename': self.response_filename,
            'original_data': self.original_data,
            'response_data': self.response_data,
        }

    def set_params(self, params):
        self.original_filename = params['original_filename']
        self.response_filename = params['response_filename']
        self.original_data = params['original_data']
        self.response_data = params['response_data']
        self.calculate_transfer_data()

    def reset(self):
        self.original_filename = None
        self.response_filename = None
        self.original_data = None
        self.response_data = None
        self.transfer_data = None
        self.img_transformations = None


class SlabAbsorptionCorrection(ImgCorrectionInterface):
    """Absorption correction for a flat slab sample in transmission geometry.

    Calculates the transmission factor for X-rays passing through a flat
    sample of given thickness and composition. The path length through the
    sample depends on 2θ, azimuth, and the slab orientation.

    The incident beam travels through the slab and is diffracted. Both the
    incident and diffracted beam paths through the sample contribute to
    absorption. For a slab with normal along the beam direction:
        - Incident path: t / cos(α_in)
        - Diffracted path depends on 2θ and the slab normal

    The correction factor (transmission) is calculated as:
        A = exp(-μ · L_total)
    where L_total is the total path length through the slab.

    The tth_array and azi_array should be in degrees (consistent with
    CbnCorrection and ObliqueAngleDetectorAbsorptionCorrection).
    """

    def __init__(
        self,
        tth_array=None,
        azi_array=None,
        thickness=0.1,
        absorption_coefficient=1.0,
        slab_tilt=0,
        slab_rotation=0,
    ):
        """
        :param tth_array: 2D array of 2θ values in degrees
        :param azi_array: 2D array of azimuthal angles in degrees
        :param thickness: slab thickness in mm
        :param absorption_coefficient: linear absorption coefficient in 1/mm
        :param slab_tilt: tilt of the slab normal from the beam direction in degrees
        :param slab_rotation: rotation of the tilt direction in degrees
        """
        self._tth_array = tth_array if tth_array is not None else np.array([])
        self._azi_array = azi_array if azi_array is not None else np.array([])
        self._thickness = thickness
        self._absorption_coefficient = absorption_coefficient
        self._slab_tilt = slab_tilt
        self._slab_rotation = slab_rotation
        self._data = None

    def get_data(self):
        return self._data

    def shape(self):
        return self._data.shape

    def get_params(self):
        return {
            "thickness": self._thickness,
            "absorption_coefficient": self._absorption_coefficient,
            "slab_tilt": self._slab_tilt,
            "slab_rotation": self._slab_rotation,
        }

    def set_params(self, params):
        self._thickness = params["thickness"]
        self._absorption_coefficient = params["absorption_coefficient"]
        self._slab_tilt = params["slab_tilt"]
        self._slab_rotation = params["slab_rotation"]

    def update(self):
        dtor = np.pi / 180.0

        t = self._thickness
        mu = self._absorption_coefficient

        two_theta = self._tth_array * dtor
        azi = self._azi_array * dtor
        tilt = self._slab_tilt * dtor
        tilt_rotation = self._slab_rotation * dtor

        # Slab normal vector (points along beam when tilt=0)
        # Tilt rotates the normal away from the beam direction
        slab_normal = np.array(
            [
                np.cos(tilt),
                np.sin(tilt) * np.cos(tilt_rotation),
                np.sin(tilt) * np.sin(tilt_rotation),
            ]
        )

        # Incident beam direction (along x-axis)
        beam_dir = np.array([1.0, 0.0, 0.0])

        # Cosine of angle between incident beam and slab normal
        cos_incident = abs(np.dot(beam_dir, slab_normal))
        # Avoid division by zero for extreme tilts
        cos_incident = max(cos_incident, 1e-10)

        # Diffracted beam direction for each pixel
        diff_x = np.cos(two_theta)
        diff_y = np.cos(azi) * np.sin(two_theta)
        diff_z = np.sin(azi) * np.sin(two_theta)

        # Cosine of angle between diffracted beam and slab normal
        cos_diffracted = np.abs(
            slab_normal[0] * diff_x
            + slab_normal[1] * diff_y
            + slab_normal[2] * diff_z
        )
        # Avoid division by zero
        cos_diffracted = np.maximum(cos_diffracted, 1e-10)

        # Path lengths through the slab
        path_incident = t / cos_incident
        path_diffracted = t / cos_diffracted

        # Total transmission factor
        # For the general case with different incident and diffracted paths:
        # A = [exp(-mu*L_in) - exp(-mu*L_diff)] / [mu * (L_diff - L_in)]
        # when L_in ≈ L_diff (nearly perpendicular slab):
        # A = exp(-mu*L) * L * mu / (exp terms)
        # Simplified: just multiply incident and diffracted transmissions
        # since the sample is thin and we're in transmission geometry
        self._data = np.exp(-mu * (path_incident + path_diffracted))

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


def load_image(filename):
    try:
        im = Image.open(filename)
        img_data = np.array(im)[::-1]
        im.close()
    except IOError:
        _img_data_fabio = fabio.open(filename)
        img_data = _img_data_fabio.data[::-1]
    return img_data


def vector_len(vec):
    return np.sqrt(vec[0] ** 2 + vec[1] ** 2 + vec[2] ** 2)


def dot_product(vec1, vec2):
    return vec1[0] * vec2[0] + vec1[1] * vec2[1] + vec1[2] * vec2[2]
