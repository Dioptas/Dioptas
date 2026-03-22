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
    sample of given thickness and composition, integrating over all possible
    scattering depths within the slab.

    For a slab of thickness t with linear absorption coefficient μ, the
    effective linear absorption coefficients along the incident and diffracted
    beam paths are:

        μ_i = μ / cos(α_i)     (incident beam)
        μ_d = μ / cos(α_d)     (diffracted beam)

    where α_i and α_d are the angles between the respective beams and the
    slab normal.

    The transmission factor is obtained by integrating over the scattering
    depth z:

        A*(2θ,φ) = ∫₀ᵗ exp(-μ_i·z) · exp(-μ_d·(t-z)) dz

    which evaluates to:

        A* = [exp(-μ_i·t) - exp(-μ_d·t)] / (μ_d - μ_i)    when μ_i ≠ μ_d
        A* = t · exp(-μ_i·t)                                when μ_i = μ_d

    Reference: Busing, W. R. & Levy, H. A. (1957). Acta Cryst. 10, 180-182.
    See also: International Tables for Crystallography, Vol. C, Section 6.3.

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
        :param slab_rotation: rotation of the tilt direction in degrees,
            following pyFAI's azimuthal (chi) convention: 0° = horizontal,
            90° = vertical (up), when looking along the beam direction
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

        # Effective linear absorption coefficients along each beam path
        mu_i = mu / cos_incident      # incident beam
        mu_d = mu / cos_diffracted    # diffracted beam

        # Transmission factor by integrating over scattering depth z:
        #   A* = ∫₀ᵗ exp(-μ_i·z) · exp(-μ_d·(t-z)) dz
        #
        # Solution (Busing & Levy, 1957):
        #   A* = [exp(-μ_i·t) - exp(-μ_d·t)] / (μ_d - μ_i)   when μ_i ≠ μ_d
        #   A* = t · exp(-μ_i·t)                               when μ_i = μ_d
        if mu == 0 or t == 0:
            self._data = np.ones_like(two_theta)
            return

        exp_i = np.exp(-mu_i * t)
        exp_d = np.exp(-mu_d * t)
        delta_mu = mu_d - mu_i

        # Use the general formula where |delta_mu| is large enough,
        # and the limit form where mu_i ≈ mu_d to avoid numerical issues
        nearly_equal = np.abs(delta_mu) < 1e-10 * mu
        self._data = np.where(
            nearly_equal,
            t * exp_i,
            (exp_i - exp_d) / delta_mu,
        )

class CylinderAbsorptionCorrection(ImgCorrectionInterface):
    """Absorption correction for a cylindrical sample in transmission geometry.

    Supports two illumination modes controlled by the ``full_illumination``
    parameter:

    **Pencil beam mode** (``full_illumination=False``, default):
    Assumes the beam is much smaller than the cylinder (typical for
    synchrotron experiments). Integrates along the beam path through the
    cylinder center in the cross-section plane.

    **Full illumination mode** (``full_illumination=True``):
    Assumes the beam illuminates the full cylinder cross-section.
    Integrates over all scattering points in the cross-section.

    In both modes, the transmission factor is:

        A*(2θ,φ) = average of exp(-μ·(l_in + l_out))

    The cylinder axis orientation is defined by two angles:
    - axis_tilt: angle of the cylinder axis from the z-axis (vertical)
      in degrees. 0° = vertical (perpendicular to beam), 90° = along beam.
    - axis_rotation: rotation of the tilt direction around the beam axis
      in degrees, following pyFAI's azimuthal (chi) convention.

    Reference: Paalman, H. H. & Pings, C. J. (1962). J. Appl. Phys. 33,
    2635-2639.

    The tth_array and azi_array should be in degrees (consistent with
    other corrections in Dioptas).
    """

    def __init__(
        self,
        tth_array=None,
        azi_array=None,
        radius=0.15,
        absorption_coefficient=1.0,
        axis_tilt=0,
        axis_rotation=0,
        full_illumination=False,
        n_points=200,
        n_tth=200,
        n_azi=180,
    ):
        """
        :param tth_array: 2D array of 2θ values in degrees
        :param azi_array: 2D array of azimuthal angles in degrees
        :param radius: cylinder radius in mm
        :param absorption_coefficient: linear absorption coefficient in 1/mm
        :param axis_tilt: tilt of the cylinder axis from vertical (degrees).
            0 = vertical (perpendicular to beam), 90 = along beam.
        :param axis_rotation: rotation of the tilt direction in degrees,
            following pyFAI's azimuthal (chi) convention: 0° = horizontal,
            90° = vertical (up), when looking along the beam direction
        :param full_illumination: if True, beam illuminates the full
            cross-section; if False (default), pencil beam through center
        :param n_points: number of integration points (along beam for pencil
            mode, grid resolution for full illumination mode)
        :param n_tth: number of 2θ points in the interpolation grid
        :param n_azi: number of azimuth points in the interpolation grid
        """
        self._tth_array = tth_array if tth_array is not None else np.array([])
        self._azi_array = azi_array if azi_array is not None else np.array([])
        self._radius = radius
        self._absorption_coefficient = absorption_coefficient
        self._axis_tilt = axis_tilt
        self._axis_rotation = axis_rotation
        self._full_illumination = full_illumination
        self._n_points = n_points
        self._n_tth = n_tth
        self._n_azi = n_azi
        self._data = None

    def get_data(self):
        return self._data

    def shape(self):
        return self._data.shape

    def get_params(self):
        return {
            "radius": self._radius,
            "absorption_coefficient": self._absorption_coefficient,
            "axis_tilt": self._axis_tilt,
            "axis_rotation": self._axis_rotation,
            "full_illumination": self._full_illumination,
        }

    def set_params(self, params):
        self._radius = params["radius"]
        self._absorption_coefficient = params["absorption_coefficient"]
        self._axis_tilt = params["axis_tilt"]
        self._axis_rotation = params["axis_rotation"]
        self._full_illumination = params.get("full_illumination", False)

    @staticmethod
    def _build_cylinder_basis(axis_tilt_rad, axis_rotation_rad):
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
    def _project_to_cross_section(direction_3d, cyl_u, cyl_v):
        """Project 3D direction(s) onto the cylinder cross-section plane."""
        du = np.tensordot(cyl_u, direction_3d, axes=([0], [0]))
        dv = np.tensordot(cyl_v, direction_3d, axes=([0], [0]))
        return du, dv

    def update(self):
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

        # Compute on a coarse (2θ, azi) grid
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

        if self._full_illumination:
            correction_table = self._compute_full_illumination(
                R, mu, beam_u_n, beam_v_n, beam_proj_len,
                diff_u, diff_v, diff_proj_len,
            )
        else:
            correction_table = self._compute_pencil_beam(
                R, mu, beam_u_n, beam_v_n, beam_proj_len,
                diff_u, diff_v, diff_proj_len,
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

    def _compute_pencil_beam(self, R, mu, beam_u_n, beam_v_n, beam_proj_len,
                             diff_u, diff_v, diff_proj_len):
        """Pencil beam through cylinder center (beam << cylinder).

        Integrates along the beam path through the center of the
        cross-section. Points are parameterized as (s·beam_u_n, s·beam_v_n)
        for s in [-R, R] (projected coords), with 3D path length s/beam_proj_len.
        """
        n = self._n_points
        s = np.linspace(-R * 0.9999, R * 0.9999, n)
        # Filter to points inside the cylinder cross-section
        gu = s * beam_u_n
        gv = s * beam_v_n
        inside = gu**2 + gv**2 < R**2
        gu = gu[inside]
        gv = gv[inside]
        s = s[inside]

        if len(gu) == 0:
            return np.ones_like(diff_u)

        # Incident path: distance from entry to scattering point
        # Entry is at s = -sqrt(R² - (perpendicular component)²) in projected coords
        # Since beam goes through center: entry at s_entry, l_in = (s - s_entry) / beam_proj_len
        b_dot_g = gu * beam_u_n + gv * beam_v_n
        g_r2 = gu**2 + gv**2 - R**2
        disc_in = np.maximum(b_dot_g**2 - g_r2, 0)
        s_entry = b_dot_g + np.sqrt(disc_in)
        l_in = s_entry / beam_proj_len

        accumulator = np.zeros_like(diff_u)
        for i in range(len(gu)):
            u0, v0 = gu[i], gv[i]
            a = diff_u**2 + diff_v**2
            b = u0 * diff_u + v0 * diff_v
            c = u0**2 + v0**2 - R**2
            discriminant = np.maximum(b**2 - a * c, 0)
            t_exit_proj = (-b + np.sqrt(discriminant)) / np.maximum(a, 1e-30)
            l_out = t_exit_proj / diff_proj_len
            accumulator += np.exp(-mu * (l_in[i] + l_out))

        return accumulator / len(gu)

    def _compute_full_illumination(self, R, mu, beam_u_n, beam_v_n, beam_proj_len,
                                   diff_u, diff_v, diff_proj_len):
        """Full illumination (beam >> cylinder), integrates over cross-section."""
        g = np.linspace(-R, R, max(self._n_points, 30))
        gu, gv = np.meshgrid(g, g)
        inside = gu**2 + gv**2 < R**2
        gu = gu[inside]
        gv = gv[inside]

        if len(gu) == 0:
            return np.ones_like(diff_u)

        # Incident path lengths
        b_dot_g = gu * beam_u_n + gv * beam_v_n
        g_r2 = gu**2 + gv**2 - R**2
        disc_in = np.maximum(b_dot_g**2 - g_r2, 0)
        s_entry = b_dot_g + np.sqrt(disc_in)
        l_in = s_entry / beam_proj_len

        accumulator = np.zeros_like(diff_u)
        for i in range(len(gu)):
            u0, v0 = gu[i], gv[i]
            a = diff_u**2 + diff_v**2
            b = u0 * diff_u + v0 * diff_v
            c = u0**2 + v0**2 - R**2
            discriminant = np.maximum(b**2 - a * c, 0)
            t_exit_proj = (-b + np.sqrt(discriminant)) / np.maximum(a, 1e-30)
            l_out = t_exit_proj / diff_proj_len
            accumulator += np.exp(-mu * (l_in[i] + l_out))

        return accumulator / len(gu)


class SphereAbsorptionCorrection(ImgCorrectionInterface):
    """Absorption correction for a spherical sample in transmission geometry.

    Supports two illumination modes controlled by the ``full_illumination``
    parameter:

    **Pencil beam mode** (``full_illumination=False``, default):
    Assumes the beam is much smaller than the sphere (typical for
    synchrotron experiments with 2–10 μm beams on ~1 mm ball samples).
    Integrates along the beam path through the sphere center:

        A*(2θ) = (1/2R) ∫_{-R}^{R} exp(-μ·(l_in(x) + l_out(x, 2θ))) dx

    where:
        l_in(x) = x + R
        l_out(x, 2θ) = -x·cos(2θ) + √(R² - x²·sin²(2θ))

    **Full illumination mode** (``full_illumination=True``):
    Assumes the beam is larger than the sphere, illuminating the
    entire cross-section. Integrates over the sphere volume using
    cylindrical coordinates (x, ρ) weighted by ρ:

        A*(2θ) = ∫∫ exp(-μ·(l_in + l_out)) · ρ dρ dx / ∫∫ ρ dρ dx

    In both modes, the correction depends only on 2θ (not azimuth)
    due to spherical symmetry. No orientation parameters are needed.

    The tth_array and azi_array should be in degrees (consistent with
    other corrections in Dioptas).
    """

    def __init__(
        self,
        tth_array=None,
        azi_array=None,
        radius=0.1,
        absorption_coefficient=1.0,
        full_illumination=False,
        n_points=500,
    ):
        """
        :param tth_array: 2D array of 2θ values in degrees
        :param azi_array: 2D array of azimuthal angles in degrees
        :param radius: sphere radius in mm
        :param absorption_coefficient: linear absorption coefficient in 1/mm
        :param full_illumination: if True, beam illuminates the full sphere;
            if False (default), pencil beam through the center
        :param n_points: number of integration points (along beam for pencil
            mode, grid resolution for full illumination mode)
        """
        self._tth_array = tth_array if tth_array is not None else np.array([])
        self._azi_array = azi_array if azi_array is not None else np.array([])
        self._radius = radius
        self._absorption_coefficient = absorption_coefficient
        self._full_illumination = full_illumination
        self._n_points = n_points
        self._data = None

    def get_data(self):
        return self._data

    def shape(self):
        return self._data.shape

    def get_params(self):
        return {
            "radius": self._radius,
            "absorption_coefficient": self._absorption_coefficient,
            "full_illumination": self._full_illumination,
        }

    def set_params(self, params):
        self._radius = params["radius"]
        self._absorption_coefficient = params["absorption_coefficient"]
        self._full_illumination = params.get("full_illumination", False)

    def update(self):
        dtor = np.pi / 180.0
        R = self._radius
        mu = self._absorption_coefficient
        tth_full = self._tth_array * dtor

        if mu == 0 or R == 0:
            self._data = np.ones_like(tth_full)
            return

        # Compute A*(2θ) on a 1D grid
        tth_min = max(tth_full.min(), 0.001)
        tth_max = tth_full.max() + 0.001
        n_tth = 500
        tth_grid = np.linspace(tth_min, tth_max, n_tth)

        if self._full_illumination:
            correction_1d = self._compute_full_illumination(R, mu, tth_grid)
        else:
            correction_1d = self._compute_pencil_beam(R, mu, tth_grid)

        # Interpolate to the full detector
        self._data = np.interp(tth_full.ravel(), tth_grid, correction_1d).reshape(
            tth_full.shape
        )

    def _compute_pencil_beam(self, R, mu, tth_grid):
        """Pencil beam through sphere center (beam << sphere)."""
        x = np.linspace(-R * 0.9999, R * 0.9999, self._n_points)
        l_in = x + R

        cos_tth = np.cos(tth_grid)
        sin2_tth = np.sin(tth_grid) ** 2

        x_col = x[:, np.newaxis]
        discriminant = np.maximum(R**2 - x_col**2 * sin2_tth, 0)
        l_out = -x_col * cos_tth + np.sqrt(discriminant)

        integrand = np.exp(-mu * (l_in[:, np.newaxis] + l_out))
        return np.mean(integrand, axis=0)

    def _compute_full_illumination(self, R, mu, tth_grid):
        """Full illumination (beam >> sphere), integrates over cross-section."""
        n = self._n_points
        # Use a 2D grid in (x, rho) with cylindrical symmetry
        g = np.linspace(-R * 0.999, R * 0.999, max(n, 50))
        gx, grho = np.meshgrid(g, g)
        inside = (gx**2 + grho**2 < R**2) & (grho > 0)
        gx = gx[inside]
        grho = grho[inside]

        if len(gx) == 0:
            return np.ones_like(tth_grid)

        l_in = gx + np.sqrt(R**2 - grho**2)

        cos_tth = np.cos(tth_grid)
        sin_tth = np.sin(tth_grid)

        correction_1d = np.zeros_like(tth_grid)
        weight_sum = np.sum(grho)

        for i in range(len(gx)):
            x0, rho0 = gx[i], grho[i]
            b = x0 * cos_tth + rho0 * sin_tth
            c = x0**2 + rho0**2 - R**2
            discriminant = np.maximum(b**2 - c, 0)
            t_exit = -b + np.sqrt(discriminant)
            correction_1d += grho[i] * np.exp(-mu * (l_in[i] + t_exit))

        return correction_1d / weight_sum


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
