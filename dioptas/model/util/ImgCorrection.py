# SPDX-License-Identifier: MIT

from __future__ import annotations

from collections.abc import Callable

import numpy as np
import fabio
from PIL import Image


class ImgCorrectionManager:
    def __init__(self, img_shape: tuple[int, ...] | None = None) -> None:
        self._corrections: dict[str | int, ImgCorrectionInterface] = {}
        self._ind: int = 0
        self.shape: tuple[int, ...] | None = img_shape

    def add(self, img_correction: ImgCorrectionInterface, name: str | None = None) -> bool:
        if self.shape is None:
            self.shape = img_correction.shape()

        if self.shape == img_correction.shape():
            if name is None:
                name = self._ind
                self._ind += 1
            self._corrections[name] = img_correction
            return True
        return False

    def has_items(self) -> bool:
        return len(self._corrections) != 0

    def delete(self, name: str | int | None = None) -> None:
        if name is None:
            if self._ind == 0:
                return
            self._ind -= 1
            name = self._ind
        del self._corrections[name]
        if len(self._corrections) == 0:
            self.clear()

    def clear(self) -> None:
        self._corrections = {}
        self.shape = None
        self._ind = 0

    def get_data(self) -> np.ndarray | None:
        if len(self._corrections) == 0:
            return None

        res = np.ones(self.shape)
        for key, correction in self._corrections.items():
            res *= correction.get_data()
        return res

    def get_correction(self, name: str | int) -> ImgCorrectionInterface | None:
        try:
            return self._corrections[name]
        except KeyError:
            return None

    @property
    def corrections(self) -> dict[str | int, ImgCorrectionInterface]:
        return self._corrections


class ImgCorrectionInterface:
    def get_data(self) -> np.ndarray:
        raise NotImplementedError

    def shape(self) -> tuple[int, ...]:
        raise NotImplementedError


class CbnCorrection(ImgCorrectionInterface):
    def __init__(
        self,
        tth_array: np.ndarray = [],
        azi_array: np.ndarray = [],
        diamond_thickness: float = 2.0,
        seat_thickness: float = 5.0,
        small_cbn_seat_radius: float = 0.5,
        large_cbn_seat_radius: float = 2.0,
        tilt: float = 0,
        tilt_rotation: float = 0,
        diamond_abs_length: float = 13.7,
        cbn_abs_length: float = 14.05,
        center_offset: float = 0,
        center_offset_angle: float = 0,
    ) -> None:
        self._tth_array: np.ndarray = tth_array
        self._azi_array: np.ndarray = azi_array
        self._diamond_thickness: float = diamond_thickness
        self._seat_thickness: float = seat_thickness
        self._small_cbn_seat_radius: float = small_cbn_seat_radius
        self._large_cbn_seat_radius: float = large_cbn_seat_radius
        self._tilt: float = tilt
        self._tilt_rotation: float = tilt_rotation
        self._diamond_abs_length: float = diamond_abs_length
        self._seat_abs_length: float = cbn_abs_length
        self._center_offset: float = center_offset
        self._center_offset_angle: float = center_offset_angle

        self._data: np.ndarray | None = None

    def get_data(self) -> np.ndarray | None:
        return self._data

    def shape(self) -> tuple[int, ...]:
        return self._data.shape

    def get_params(self) -> dict[str, float]:
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

    def set_params(self, params: dict[str, float]) -> None:
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

    def update(self) -> None:

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

    def __eq__(self, other: object) -> bool:
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
    def __init__(
        self,
        tth_array: np.ndarray,
        azi_array: np.ndarray,
        detector_thickness: float = 40,
        absorption_length: float = 150,
        tilt: float = 0,
        rotation: float = 0,
    ) -> None:
        self.tth_array: np.ndarray = tth_array
        self.azi_array: np.ndarray = azi_array
        self.detector_thickness: float = detector_thickness
        self.absorption_length: float = absorption_length
        self.tilt: float = tilt
        self.rotation: float = rotation

        self._data: np.ndarray | None = None
        self.update()

    def get_params(self) -> dict[str, float]:
        return {'detector_thickness': self.detector_thickness,
                'absorption_length': self.absorption_length,
                'tilt': self.tilt,
                'rotation': self.rotation
                }

    def set_params(self, params: dict[str, float]) -> None:
        self.detector_thickness = params['detector_thickness']
        self.absorption_length = params['absorption_length']
        self.tilt = params['tilt']
        self.rotation = params['rotation']

    def get_data(self) -> np.ndarray | None:
        return self._data

    def shape(self) -> tuple[int, ...]:
        return self._data.shape

    def update(self) -> None:
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
    def __init__(
        self,
        original_filename: str | None = None,
        response_filename: str | None = None,
        img_transformations: list[Callable[[np.ndarray], np.ndarray]] | None = None,
    ) -> None:
        self.original_filename: str | None = None
        self.response_filename: str | None = None
        self.original_data: np.ndarray | None = None
        self.response_data: np.ndarray | None = None
        self.transfer_data: np.ndarray | None = None

        self.img_transformations: list[Callable[[np.ndarray], np.ndarray]] | None = img_transformations

        if original_filename:
            self.load_original_image(original_filename)
        if response_filename:
            self.load_response_image(response_filename)

    def load_original_image(self, img_filename: str) -> None:
        self.original_filename = img_filename
        self.original_data = load_image(img_filename)
        if self.response_filename:
            self.calculate_transfer_data()

    def load_response_image(self, img_filename: str) -> None:
        self.response_filename = img_filename
        self.response_data = load_image(img_filename)
        if self.original_filename:
            self.calculate_transfer_data()

    def set_img_transformations(self, img_transformations: list[Callable[[np.ndarray], np.ndarray]]) -> None:
        """Sets the image transformations."""
        self.img_transformations = img_transformations
        if self.response_filename and self.original_filename:
            self.calculate_transfer_data()

    def calculate_transfer_data(self) -> None:
        transfer_data = self.response_data / self.original_data
        if self.img_transformations:
            for transformation in self.img_transformations:
                transfer_data = transformation(transfer_data)
        self.transfer_data = transfer_data

    def get_data(self) -> np.ndarray | None:
        return self.transfer_data

    def shape(self) -> tuple[int, ...]:
        return self.transfer_data.shape

    def get_params(self) -> dict[str, str | np.ndarray | None]:
        return {
            'original_filename': self.original_filename,
            'response_filename': self.response_filename,
            'original_data': self.original_data,
            'response_data': self.response_data,
        }

    def set_params(self, params: dict[str, str | np.ndarray | None]) -> None:
        self.original_filename = params['original_filename']
        self.response_filename = params['response_filename']
        self.original_data = params['original_data']
        self.response_data = params['response_data']
        self.calculate_transfer_data()

    def reset(self) -> None:
        self.original_filename = None
        self.response_filename = None
        self.original_data = None
        self.response_data = None
        self.transfer_data = None
        self.img_transformations = None


class FlatFieldCorrection(ImgCorrectionInterface):
    """Flat field correction for non-uniform detector pixel response.

    Divides the image by a normalized flat field image to compensate for
    pixel-to-pixel sensitivity variations. The flat field image is normalized
    by its mean so the correction preserves the overall intensity scale.
    """

    def __init__(
        self,
        filename: str | None = None,
        img_transformations: list[Callable[[np.ndarray], np.ndarray]] | None = None,
    ) -> None:
        self.filename: str | None = None
        self.raw_data: np.ndarray | None = None
        self.data: np.ndarray | None = None
        self.img_transformations: list[Callable[[np.ndarray], np.ndarray]] | None = (
            img_transformations
        )

        if filename:
            self.load(filename)

    def load(self, filename: str) -> None:
        self.filename = filename
        self.raw_data = load_image(filename).astype(np.float64)
        self._calculate()

    def set_img_transformations(
        self, img_transformations: list[Callable[[np.ndarray], np.ndarray]]
    ) -> None:
        self.img_transformations = img_transformations
        if self.raw_data is not None:
            self._calculate()

    def _calculate(self) -> None:
        data = self.raw_data.copy()
        if self.img_transformations:
            for transformation in self.img_transformations:
                data = transformation(data)
        mean_val = np.mean(data)
        if mean_val != 0:
            data = data / mean_val
        # Avoid division by zero in the correction
        data[data == 0] = 1.0
        self.data = data

    def get_data(self) -> np.ndarray | None:
        return self.data

    def shape(self) -> tuple[int, ...]:
        return self.data.shape

    def get_params(self) -> dict[str, str | np.ndarray | None]:
        return {
            "filename": self.filename,
            "raw_data": self.raw_data,
        }

    def set_params(self, params: dict[str, str | np.ndarray | None]) -> None:
        self.filename = params["filename"]
        self.raw_data = params["raw_data"]
        self._calculate()

    def reset(self) -> None:
        self.filename = None
        self.raw_data = None
        self.data = None
        self.img_transformations = None


class SlabAbsorptionCorrection(ImgCorrectionInterface):
    """Absorption correction for a flat slab sample in transmission geometry.

    Calculates the transmission factor for X-rays passing through a flat
    sample of given thickness and composition, integrating over all possible
    scattering depths within the slab.

    For a slab of thickness t with linear absorption coefficient \u03bc, the
    effective linear absorption coefficients along the incident and diffracted
    beam paths are:

        \u03bc_i = \u03bc / cos(\u03b1_i)     (incident beam)
        \u03bc_d = \u03bc / cos(\u03b1_d)     (diffracted beam)

    where \u03b1_i and \u03b1_d are the angles between the respective beams and the
    slab normal.

    The transmission factor is obtained by integrating over the scattering
    depth z:

        A*(2\u03b8,\u03c6) = \u222b\u2080\u1d57 exp(-\u03bc_i\u00b7z) \u00b7 exp(-\u03bc_d\u00b7(t-z)) dz

    which evaluates to:

        A* = [exp(-\u03bc_i\u00b7t) - exp(-\u03bc_d\u00b7t)] / (\u03bc_d - \u03bc_i)    when \u03bc_i \u2260 \u03bc_d
        A* = t \u00b7 exp(-\u03bc_i\u00b7t)                                when \u03bc_i = \u03bc_d

    Reference: Busing, W. R. & Levy, H. A. (1957). Acta Cryst. 10, 180-182.
    See also: International Tables for Crystallography, Vol. C, Section 6.3.

    The tth_array and azi_array should be in degrees (consistent with
    CbnCorrection and ObliqueAngleDetectorAbsorptionCorrection).
    """

    def __init__(
        self,
        tth_array: np.ndarray | None = None,
        azi_array: np.ndarray | None = None,
        thickness: float = 0.1,
        absorption_coefficient: float = 1.0,
        slab_tilt: float = 0,
        slab_rotation: float = 0,
    ) -> None:
        """
        :param tth_array: 2D array of 2\u03b8 values in degrees
        :param azi_array: 2D array of azimuthal angles in degrees
        :param thickness: slab thickness in mm
        :param absorption_coefficient: linear absorption coefficient in 1/mm
        :param slab_tilt: tilt of the slab normal from the beam direction in degrees
        :param slab_rotation: rotation of the tilt direction in degrees,
            following pyFAI's azimuthal (chi) convention: 0\u00b0 = horizontal,
            90\u00b0 = vertical (up), when looking along the beam direction
        """
        self._tth_array: np.ndarray = tth_array if tth_array is not None else np.array([])
        self._azi_array: np.ndarray = azi_array if azi_array is not None else np.array([])
        self._thickness: float = thickness
        self._absorption_coefficient: float = absorption_coefficient
        self._slab_tilt: float = slab_tilt
        self._slab_rotation: float = slab_rotation
        self._data: np.ndarray | None = None

    def get_data(self) -> np.ndarray | None:
        return self._data

    def shape(self) -> tuple[int, ...]:
        return self._data.shape

    def get_params(self) -> dict[str, float]:
        return {
            "thickness": self._thickness,
            "absorption_coefficient": self._absorption_coefficient,
            "slab_tilt": self._slab_tilt,
            "slab_rotation": self._slab_rotation,
        }

    def set_params(self, params: dict[str, float]) -> None:
        self._thickness = params["thickness"]
        self._absorption_coefficient = params["absorption_coefficient"]
        self._slab_tilt = params["slab_tilt"]
        self._slab_rotation = params["slab_rotation"]

    def update(self) -> None:
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

        # Effective linear absorption coefficients along each beam path
        mu_i = mu / cos_incident      # incident beam
        mu_d = mu / cos_diffracted    # diffracted beam

        # Transmission factor by integrating over scattering depth z:
        #   A* = \u222b\u2080\u1d57 exp(-\u03bc_i\u00b7z) \u00b7 exp(-\u03bc_d\u00b7(t-z)) dz
        #
        # Solution (Busing & Levy, 1957):
        #   A* = [exp(-\u03bc_i\u00b7t) - exp(-\u03bc_d\u00b7t)] / (\u03bc_d - \u03bc_i)   when \u03bc_i \u2260 \u03bc_d
        #   A* = t \u00b7 exp(-\u03bc_i\u00b7t)                               when \u03bc_i = \u03bc_d
        if mu == 0 or t == 0:
            self._data = np.ones_like(two_theta)
            return

        exp_i = np.exp(-mu_i * t)
        exp_d = np.exp(-mu_d * t)
        delta_mu = mu_d - mu_i

        # Use the general formula where |delta_mu| is large enough,
        # and the limit form where mu_i \u2248 mu_d to avoid numerical issues
        nearly_equal = np.abs(delta_mu) < 1e-10 * mu
        self._data = np.where(
            nearly_equal,
            t * exp_i,
            (exp_i - exp_d) / delta_mu,
        )

class CylinderAbsorptionCorrection(ImgCorrectionInterface):
    """Absorption correction for a cylindrical sample in transmission geometry.

    Calculates the transmission factor by integrating the absorption over
    the beam footprint within the cylinder cross-section:

        A*(2\u03b8,\u03c6) = average of exp(-\u03bc\u00b7(l_in + l_out))

    The beam width controls how much of the cross-section is illuminated:
    - beam_width=0 (default): pencil beam through center (synchrotron case)
    - beam_width >= 2*radius: full illumination (lab source case)
    - intermediate values: partial illumination

    The cylinder axis orientation is defined by two angles:
    - axis_tilt: angle of the cylinder axis from the z-axis (vertical)
      in degrees. 0\u00b0 = vertical (perpendicular to beam), 90\u00b0 = along beam.
    - axis_rotation: rotation of the tilt direction around the beam axis
      in degrees, following pyFAI's azimuthal (chi) convention.

    Reference: Paalman, H. H. & Pings, C. J. (1962). J. Appl. Phys. 33,
    2635-2639.

    The tth_array and azi_array should be in degrees (consistent with
    other corrections in Dioptas).
    """

    def __init__(
        self,
        tth_array: np.ndarray | None = None,
        azi_array: np.ndarray | None = None,
        radius: float = 0.15,
        absorption_coefficient: float = 1.0,
        axis_tilt: float = 0,
        axis_rotation: float = 0,
        beam_width: float = 0,
        container_absorption_coefficient: float = 0,
        wall_thickness: float = 0,
        n_points: int = 200,
        n_tth: int = 200,
        n_azi: int = 180,
    ) -> None:
        """
        :param tth_array: 2D array of 2\u03b8 values in degrees
        :param azi_array: 2D array of azimuthal angles in degrees
        :param radius: sample cylinder radius (inner radius) in mm
        :param absorption_coefficient: sample linear absorption coefficient in 1/mm
        :param axis_tilt: tilt of the cylinder axis from vertical (degrees).
            0 = vertical (perpendicular to beam), 90 = along beam.
        :param axis_rotation: rotation of the tilt direction in degrees,
            following pyFAI's azimuthal (chi) convention: 0\u00b0 = horizontal,
            90\u00b0 = vertical (up), when looking along the beam direction
        :param beam_width: beam width/diameter in mm. 0 = pencil beam
            (default), >= 2*radius = full illumination.
        :param container_absorption_coefficient: container (e.g. glass
            capillary) linear absorption coefficient in 1/mm. 0 = no
            container correction (default).
        :param wall_thickness: container wall thickness in mm.
        :param n_points: grid resolution for integration
        :param n_tth: number of 2\u03b8 points in the interpolation grid
        :param n_azi: number of azimuth points in the interpolation grid
        """
        self._tth_array: np.ndarray = tth_array if tth_array is not None else np.array([])
        self._azi_array: np.ndarray = azi_array if azi_array is not None else np.array([])
        self._radius: float = radius
        self._absorption_coefficient: float = absorption_coefficient
        self._axis_tilt: float = axis_tilt
        self._axis_rotation: float = axis_rotation
        self._beam_width: float = beam_width
        self._container_absorption_coefficient: float = container_absorption_coefficient
        self._wall_thickness: float = wall_thickness
        self._n_points: int = n_points
        self._n_tth: int = n_tth
        self._n_azi: int = n_azi
        self._data: np.ndarray | None = None

    def get_data(self) -> np.ndarray | None:
        return self._data

    def shape(self) -> tuple[int, ...]:
        return self._data.shape

    def get_params(self) -> dict[str, float]:
        return {
            "radius": self._radius,
            "absorption_coefficient": self._absorption_coefficient,
            "axis_tilt": self._axis_tilt,
            "axis_rotation": self._axis_rotation,
            "beam_width": self._beam_width,
            "container_absorption_coefficient": self._container_absorption_coefficient,
            "wall_thickness": self._wall_thickness,
        }

    def set_params(self, params: dict[str, float]) -> None:
        self._radius = params["radius"]
        self._absorption_coefficient = params["absorption_coefficient"]
        self._axis_tilt = params["axis_tilt"]
        self._axis_rotation = params["axis_rotation"]
        self._beam_width = params.get("beam_width", 0)
        self._container_absorption_coefficient = params.get(
            "container_absorption_coefficient", 0
        )
        self._wall_thickness = params.get("wall_thickness", 0)

    @staticmethod
    def _build_cylinder_basis(
        axis_tilt_rad: float, axis_rotation_rad: float
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Build orthonormal basis for the cylinder cross-section plane.

        Returns (cyl_axis, cyl_u, cyl_v) where cyl_axis is the cylinder
        axis unit vector, and cyl_u, cyl_v span the cross-section plane.
        """
        tilt = axis_tilt_rad
        rot = axis_rotation_rad

        cyl_axis = np.array([
            np.sin(tilt) * np.cos(rot),
            np.sin(tilt) * np.sin(rot),
            np.cos(tilt),
        ])

        ref = np.array([0.0, 0.0, 1.0])
        if abs(np.dot(cyl_axis, ref)) > 0.99:
            ref = np.array([0.0, 1.0, 0.0])
        cyl_u = np.cross(cyl_axis, ref)
        cyl_u /= np.linalg.norm(cyl_u)
        cyl_v = np.cross(cyl_axis, cyl_u)
        cyl_v /= np.linalg.norm(cyl_v)

        return cyl_axis, cyl_u, cyl_v

    @staticmethod
    def _project_to_cross_section(
        direction_3d: np.ndarray, cyl_u: np.ndarray, cyl_v: np.ndarray
    ) -> tuple[np.ndarray, np.ndarray]:
        """Project 3D direction(s) onto the cylinder cross-section plane."""
        du = np.tensordot(cyl_u, direction_3d, axes=([0], [0]))
        dv = np.tensordot(cyl_v, direction_3d, axes=([0], [0]))
        return du, dv

    def update(self) -> None:
        from scipy.interpolate import RegularGridInterpolator

        dtor = np.pi / 180.0
        R = self._radius
        mu = self._absorption_coefficient
        tth_full = self._tth_array * dtor
        azi_full = self._azi_array * dtor

        if mu == 0 or R == 0:
            self._data = np.ones_like(tth_full)
            return

        # Build cylinder coordinate system
        tilt = self._axis_tilt * dtor
        rot = self._axis_rotation * dtor
        cyl_axis, cyl_u, cyl_v = self._build_cylinder_basis(tilt, rot)

        # Project incident beam onto cross-section plane
        beam_dir = np.array([1.0, 0.0, 0.0])
        beam_u = np.dot(cyl_u, beam_dir)
        beam_v = np.dot(cyl_v, beam_dir)
        beam_proj_len = np.sqrt(beam_u**2 + beam_v**2)

        if beam_proj_len < 1e-10:
            # Beam is along the cylinder axis
            self._data = np.ones_like(tth_full)
            return

        beam_u_n = beam_u / beam_proj_len
        beam_v_n = beam_v / beam_proj_len

        # Compute on a coarse (2\u03b8, azi) grid
        tth_min = max(tth_full.min(), 0.001)
        tth_max = tth_full.max() + 0.001
        tth_grid = np.linspace(tth_min, tth_max, self._n_tth)
        azi_grid = np.linspace(0, 2 * np.pi, self._n_azi)
        tth_2d, azi_2d = np.meshgrid(tth_grid, azi_grid, indexing="ij")

        # Diffracted beam 3D directions, projected onto cross-section
        diff_3d = np.array([
            np.cos(tth_2d),
            np.cos(azi_2d) * np.sin(tth_2d),
            np.sin(azi_2d) * np.sin(tth_2d),
        ])
        diff_u, diff_v = self._project_to_cross_section(diff_3d, cyl_u, cyl_v)
        diff_proj_len = np.maximum(np.sqrt(diff_u**2 + diff_v**2), 1e-30)

        R_outer = R + self._wall_thickness if self._wall_thickness > 0 else 0
        mu_container = self._container_absorption_coefficient

        correction_table = self._compute_correction(
            R, mu, beam_u_n, beam_v_n, beam_proj_len,
            diff_u, diff_v, diff_proj_len,
            R_outer, mu_container,
        )

        # Interpolate to the full detector grid
        interp = RegularGridInterpolator(
            (tth_grid, azi_grid),
            correction_table,
            method="linear",
            bounds_error=False,
            fill_value=None,
        )
        azi_wrapped = azi_full % (2 * np.pi)
        points = np.stack([tth_full.ravel(), azi_wrapped.ravel()], axis=-1)
        self._data = interp(points).reshape(tth_full.shape)

    @staticmethod
    def _chord_length_through_shell(
        u0: np.ndarray,
        v0: np.ndarray,
        du: np.ndarray,
        dv: np.ndarray,
        R_inner: float,
        R_outer: float,
    ) -> np.ndarray:
        """Compute the path length through a cylindrical shell.

        For a ray starting at (u0, v0) in direction (du, dv), compute
        the total path length through the shell between R_inner and R_outer.
        The ray may cross the shell on entry and/or exit side.

        Returns the total path in projected coordinates (divide by
        proj_len for 3D path).
        """
        a = du**2 + dv**2

        # Intersections with outer cylinder (R_outer)
        b_out = u0 * du + v0 * dv
        c_out = u0**2 + v0**2 - R_outer**2
        disc_out = np.maximum(b_out**2 - a * c_out, 0)
        sqrt_disc_out = np.sqrt(disc_out)
        t_out_entry = (-b_out - sqrt_disc_out) / np.maximum(a, 1e-30)
        t_out_exit = (-b_out + sqrt_disc_out) / np.maximum(a, 1e-30)

        # Intersections with inner cylinder (R_inner)
        b_in = b_out  # same
        c_in = u0**2 + v0**2 - R_inner**2
        disc_in = b_in**2 - a * c_in
        has_inner = disc_in > 0
        sqrt_disc_in = np.sqrt(np.maximum(disc_in, 0))
        t_in_entry = (-b_in - sqrt_disc_in) / np.maximum(a, 1e-30)
        t_in_exit = (-b_in + sqrt_disc_in) / np.maximum(a, 1e-30)

        # Path through shell = path through outer - path through inner (if it crosses inner)
        path_outer = t_out_exit - t_out_entry
        path_inner = np.where(has_inner, t_in_exit - t_in_entry, 0)
        return path_outer - path_inner

    def _compute_correction(
        self,
        R: float,
        mu: float,
        beam_u_n: float,
        beam_v_n: float,
        beam_proj_len: float,
        diff_u: np.ndarray,
        diff_v: np.ndarray,
        diff_proj_len: np.ndarray,
        R_outer: float,
        mu_container: float,
    ) -> np.ndarray:
        """Compute correction by integrating over beam footprint in cross-section.

        For beam_width=0 (pencil beam): integrates along a line through center.
        For beam_width>=2R (full illumination): integrates over full cross-section.
        For intermediate values: integrates over the beam footprint within the cylinder.

        When R_outer > 0 and mu_container > 0, the absorption through the
        container wall is included for both incident and diffracted beams.
        """
        # Perpendicular direction to beam in cross-section plane
        perp_u = -beam_v_n
        perp_v = beam_u_n

        n = self._n_points
        beam_half = self._beam_width / 2.0
        has_container = R_outer > R and mu_container > 0

        if self._beam_width <= 0:
            # Pencil beam: 1D grid along beam through center
            s = np.linspace(-R * 0.9999, R * 0.9999, n)
            gu = s * beam_u_n
            gv = s * beam_v_n
        else:
            # 2D grid: along beam x across beam (within beam_width)
            s_beam = np.linspace(-R * 0.999, R * 0.999, n)
            half = min(beam_half, R * 0.999)
            n_perp = max(int(n * half / R), 5)
            s_perp = np.linspace(-half, half, n_perp)
            sb, sp = np.meshgrid(s_beam, s_perp)
            gu = sb.ravel() * beam_u_n + sp.ravel() * perp_u
            gv = sb.ravel() * beam_v_n + sp.ravel() * perp_v

        # Filter to points inside the sample cylinder
        inside = gu**2 + gv**2 < R**2
        gu = gu[inside]
        gv = gv[inside]

        if len(gu) == 0:
            return np.ones_like(diff_u)

        # Incident path lengths through sample
        b_dot_g = gu * beam_u_n + gv * beam_v_n
        g_r2 = gu**2 + gv**2 - R**2
        disc_in = np.maximum(b_dot_g**2 - g_r2, 0)
        s_entry = b_dot_g + np.sqrt(disc_in)
        l_in_sample = s_entry / beam_proj_len

        # Incident container path: depends on where the beam enters.
        # For each scattering point, the perpendicular offset from the
        # beam center determines the chord through the shell.
        if has_container:
            # Perpendicular distance of each grid point from beam axis
            perp_dist = gu * perp_u + gv * perp_v
            # Point on the beam axis at this perpendicular offset
            entry_u = perp_dist * perp_u
            entry_v = perp_dist * perp_v
            l_in_container = self._chord_length_through_shell(
                entry_u, entry_v,
                np.full_like(entry_u, beam_u_n),
                np.full_like(entry_v, beam_v_n),
                R, R_outer,
            ) / beam_proj_len
        else:
            l_in_container = np.zeros(len(gu))

        # Accumulate over grid points
        accumulator = np.zeros_like(diff_u)
        for i in range(len(gu)):
            u0, v0 = gu[i], gv[i]

            # Diffracted beam exit from sample
            a = diff_u**2 + diff_v**2
            b = u0 * diff_u + v0 * diff_v
            c = u0**2 + v0**2 - R**2
            discriminant = np.maximum(b**2 - a * c, 0)
            t_exit_proj = (-b + np.sqrt(discriminant)) / np.maximum(a, 1e-30)
            l_out_sample = t_exit_proj / diff_proj_len

            # Container path for diffracted beam
            if has_container:
                l_out_container = self._chord_length_through_shell(
                    u0, v0, diff_u, diff_v, R, R_outer,
                ) / diff_proj_len
            else:
                l_out_container = 0

            total_absorption = (
                mu * (l_in_sample[i] + l_out_sample)
                + mu_container * (l_in_container[i] + l_out_container)
            )
            accumulator += np.exp(-total_absorption)

        return accumulator / len(gu)


class SphereAbsorptionCorrection(ImgCorrectionInterface):
    """Absorption correction for a spherical sample in transmission geometry.

    Calculates the transmission factor by integrating the absorption over
    the beam footprint within the sphere:

    - beam_width=0 (default): pencil beam through sphere center. Typical
      for synchrotron experiments (2-10 \u03bcm beam, ~1 mm sample).
    - beam_width >= 2*radius: full illumination of the sphere.
    - intermediate values: partial illumination.

    For a pencil beam, the 1D integral along the beam path is:

        A*(2\u03b8) = (1/2R) \u222b_{-R}^{R} exp(-\u03bc\u00b7(l_in(x) + l_out(x, 2\u03b8))) dx

    where:
        l_in(x) = x + R
        l_out(x, 2\u03b8) = -x\u00b7cos(2\u03b8) + \u221a(R\u00b2 - x\u00b2\u00b7sin\u00b2(2\u03b8))

    Due to spherical symmetry, the correction depends only on 2\u03b8 (not
    azimuth). No orientation parameters are needed.

    The tth_array and azi_array should be in degrees (consistent with
    other corrections in Dioptas).
    """

    def __init__(
        self,
        tth_array: np.ndarray | None = None,
        azi_array: np.ndarray | None = None,
        radius: float = 0.1,
        absorption_coefficient: float = 1.0,
        beam_width: float = 0,
        n_points: int = 500,
    ) -> None:
        """
        :param tth_array: 2D array of 2\u03b8 values in degrees
        :param azi_array: 2D array of azimuthal angles in degrees
        :param radius: sphere radius in mm
        :param absorption_coefficient: linear absorption coefficient in 1/mm
        :param beam_width: beam width/diameter in mm. 0 = pencil beam
            (default), >= 2*radius = full illumination.
        :param n_points: number of integration points
        """
        self._tth_array: np.ndarray = tth_array if tth_array is not None else np.array([])
        self._azi_array: np.ndarray = azi_array if azi_array is not None else np.array([])
        self._radius: float = radius
        self._absorption_coefficient: float = absorption_coefficient
        self._beam_width: float = beam_width
        self._n_points: int = n_points
        self._data: np.ndarray | None = None

    def get_data(self) -> np.ndarray | None:
        return self._data

    def shape(self) -> tuple[int, ...]:
        return self._data.shape

    def get_params(self) -> dict[str, float]:
        return {
            "radius": self._radius,
            "absorption_coefficient": self._absorption_coefficient,
            "beam_width": self._beam_width,
        }

    def set_params(self, params: dict[str, float]) -> None:
        self._radius = params["radius"]
        self._absorption_coefficient = params["absorption_coefficient"]
        self._beam_width = params.get("beam_width", 0)

    def update(self) -> None:
        dtor = np.pi / 180.0
        R = self._radius
        mu = self._absorption_coefficient
        tth_full = self._tth_array * dtor

        if mu == 0 or R == 0:
            self._data = np.ones_like(tth_full)
            return

        # Compute A*(2\u03b8) on a 1D grid
        tth_min = max(tth_full.min(), 0.001)
        tth_max = tth_full.max() + 0.001
        n_tth = 500
        tth_grid = np.linspace(tth_min, tth_max, n_tth)

        # Build 2D grid of (x, rho) points within the beam footprint.
        # x is along beam, rho is radial distance from beam axis.
        # For a pencil beam (beam_width=0): only rho=0 (1D along x).
        # For finite beam: grid of (x, rho) with rho up to beam_width/2.
        # For full illumination (beam_width >= 2R): rho up to R.
        beam_half = self._beam_width / 2.0

        if self._beam_width <= 0:
            # Pencil beam: 1D along x
            x = np.linspace(-R * 0.9999, R * 0.9999, self._n_points)
            rho = np.zeros_like(x)
            weights = np.ones_like(x)
        else:
            # 2D grid in (x, rho) with rho weighted
            rho_max = min(beam_half, R * 0.999)
            n_rho = max(int(self._n_points * rho_max / R), 5)
            g_x = np.linspace(-R * 0.999, R * 0.999, self._n_points)
            g_rho = np.linspace(0, rho_max, n_rho)
            gx, grho = np.meshgrid(g_x, g_rho)
            gx = gx.ravel()
            grho = grho.ravel()
            # Filter to inside sphere
            inside = gx**2 + grho**2 < R**2
            x = gx[inside]
            rho = grho[inside]
            # Weight by rho for cylindrical symmetry (rho=0 has weight ~0)
            weights = np.maximum(rho, rho[rho > 0].min() * 0.1)

        if len(x) == 0:
            self._data = np.ones_like(tth_full)
            return

        # Incident path: beam along x, enters at x = -sqrt(R\u00b2 - \u03c1\u00b2)
        l_in = x + np.sqrt(R**2 - rho**2)

        cos_tth = np.cos(tth_grid)
        sin_tth = np.sin(tth_grid)

        # For each point, diffracted beam exits the sphere.
        # Point P = (x, rho, 0), beam direction d = (cos2\u03b8, sin2\u03b8, 0)
        # |P + t\u00b7d|\u00b2 = R\u00b2 \u2192 t\u00b2 + 2t(x\u00b7cos2\u03b8 + \u03c1\u00b7sin2\u03b8) + (x\u00b2 + \u03c1\u00b2 - R\u00b2) = 0
        correction_1d = np.zeros_like(tth_grid)
        weight_sum = np.sum(weights)

        for i in range(len(x)):
            x0, rho0 = x[i], rho[i]
            b = x0 * cos_tth + rho0 * sin_tth
            c = x0**2 + rho0**2 - R**2
            discriminant = np.maximum(b**2 - c, 0)
            t_exit = -b + np.sqrt(discriminant)
            correction_1d += weights[i] * np.exp(-mu * (l_in[i] + t_exit))

        correction_1d /= weight_sum

        # Interpolate to the full detector
        self._data = np.interp(tth_full.ravel(), tth_grid, correction_1d).reshape(
            tth_full.shape
        )


class PlateAbsorptionCorrection(ImgCorrectionInterface):
    """Absorption correction for a flat absorber plate after the sample.

    Models a flat plate (e.g. diamond anvil window) between the sample and
    detector. Each diffracted beam passes through the plate at an angle
    determined by its 2\u03b8/azimuth and the plate orientation.

    The transmission factor is simply:

        T(2\u03b8,\u03c6) = exp(-\u03bc \u00b7 t / cos(\u03b8_plate))

    where \u03b8_plate is the angle between the diffracted beam and the plate
    normal, t is the plate thickness, and \u03bc is the linear absorption
    coefficient.

    The tth_array and azi_array should be in degrees.
    """

    def __init__(
        self,
        tth_array: np.ndarray | None = None,
        azi_array: np.ndarray | None = None,
        thickness: float = 2.0,
        absorption_coefficient: float = 1.0,
        plate_tilt: float = 0,
        plate_rotation: float = 0,
    ) -> None:
        """
        :param tth_array: 2D array of 2\u03b8 values in degrees
        :param azi_array: 2D array of azimuthal angles in degrees
        :param thickness: plate thickness in mm
        :param absorption_coefficient: linear absorption coefficient in 1/mm
        :param plate_tilt: tilt of the plate normal from the beam direction in degrees
        :param plate_rotation: rotation of the tilt direction in degrees
        """
        self._tth_array: np.ndarray = tth_array if tth_array is not None else np.array([])
        self._azi_array: np.ndarray = azi_array if azi_array is not None else np.array([])
        self._thickness: float = thickness
        self._absorption_coefficient: float = absorption_coefficient
        self._plate_tilt: float = plate_tilt
        self._plate_rotation: float = plate_rotation
        self._data: np.ndarray | None = None

    def get_data(self) -> np.ndarray | None:
        return self._data

    def shape(self) -> tuple[int, ...]:
        return self._data.shape

    def get_params(self) -> dict[str, float]:
        return {
            "thickness": self._thickness,
            "absorption_coefficient": self._absorption_coefficient,
            "plate_tilt": self._plate_tilt,
            "plate_rotation": self._plate_rotation,
        }

    def set_params(self, params: dict[str, float]) -> None:
        self._thickness = params["thickness"]
        self._absorption_coefficient = params["absorption_coefficient"]
        self._plate_tilt = params["plate_tilt"]
        self._plate_rotation = params["plate_rotation"]

    def update(self) -> None:
        dtor = np.pi / 180.0

        t = self._thickness
        mu = self._absorption_coefficient

        two_theta = self._tth_array * dtor
        azi = self._azi_array * dtor
        tilt = self._plate_tilt * dtor
        tilt_rotation = self._plate_rotation * dtor

        if mu == 0 or t == 0:
            self._data = np.ones_like(two_theta)
            return

        # Plate normal vector (points along beam when tilt=0)
        plate_normal = np.array(
            [
                np.cos(tilt),
                np.sin(tilt) * np.cos(tilt_rotation),
                np.sin(tilt) * np.sin(tilt_rotation),
            ]
        )

        # Diffracted beam direction for each pixel
        diff_x = np.cos(two_theta)
        diff_y = np.cos(azi) * np.sin(two_theta)
        diff_z = np.sin(azi) * np.sin(two_theta)

        # Cosine of angle between diffracted beam and plate normal
        cos_angle = np.abs(
            plate_normal[0] * diff_x
            + plate_normal[1] * diff_y
            + plate_normal[2] * diff_z
        )
        cos_angle = np.maximum(cos_angle, 1e-10)

        # Path length through plate and transmission
        path_length = t / cos_angle
        self._data = np.exp(-mu * path_length)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, PlateAbsorptionCorrection):
            return False
        if self._thickness != other._thickness:
            return False
        if self._absorption_coefficient != other._absorption_coefficient:
            return False
        if self._plate_tilt != other._plate_tilt:
            return False
        if self._plate_rotation != other._plate_rotation:
            return False
        if not np.array_equal(self._tth_array, other._tth_array):
            return False
        if not np.array_equal(self._azi_array, other._azi_array):
            return False
        return True


class DummyCorrection(ImgCorrectionInterface):
    """Used in particular for unit tests."""

    def __init__(self, shape: tuple[int, ...], number: float = 1) -> None:
        self._data: np.ndarray = np.ones(shape) * number
        self._shape: tuple[int, ...] = shape

    def get_data(self) -> np.ndarray:
        return self._data

    def shape(self) -> tuple[int, ...]:
        return self._shape


def load_image(filename: str) -> np.ndarray:
    try:
        im = Image.open(filename)
        img_data = np.array(im)[::-1]
        im.close()
    except IOError:
        _img_data_fabio = fabio.open(filename)
        img_data = _img_data_fabio.data[::-1]
    return img_data


def vector_len(vec: np.ndarray) -> np.ndarray:
    return np.sqrt(vec[0] ** 2 + vec[1] ** 2 + vec[2] ** 2)


def dot_product(vec1: np.ndarray, vec2: np.ndarray) -> np.ndarray:
    return vec1[0] * vec2[0] + vec1[1] * vec2[1] + vec1[2] * vec2[2]
