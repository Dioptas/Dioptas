# SPDX-License-Identifier: MIT

import logging
import os
import sys
import time
from collections.abc import Callable, Iterator
from enum import Enum
from copy import deepcopy
from typing import Any

import numpy as np
from pyFAI.integrator.azimuthal import AzimuthalIntegrator
from pyFAI.blob_detection import BlobDetection
from pyFAI.calibrant import Calibrant
from pyFAI.detectors import Detector, ALL_DETECTORS, NexusDetector
from pyFAI.detectors.orientation import Orientation
from pyFAI.geometryRefinement import GeometryRefinement
from pyFAI.io.ponifile import PoniFile
from pyFAI.massif import Massif
from skimage.measure import find_contours

from .. import calibrants_path
from .ImgModel import ImgModel
from .util import Signal
from .state import CalibrationParams
from .util.HelperModule import (
    get_base_name,
    rotate_matrix_p90,
    rotate_matrix_m90,
    get_partial_index,
)
from .util.calc import supersample_image, trim_trailing_zeros
from .util.file_type import file_loading_error

logger = logging.getLogger(__name__)


class CalibrationModel:

    def __init__(self, img_model: ImgModel | None = None) -> None:
        super().__init__()
        self.img_model: ImgModel | None = img_model
        # picked peaks live in params.peak_selections; these caches hold
        # the derived numpy views the algorithms consume
        self._points_cache: list[np.ndarray] | None = None
        self._points_index_cache: list[int] | None = None

        self.detector: Detector = Detector(pixel1=79e-6, pixel2=79e-6)
        # self.detector.shape = (2048, 2048)
        self._original_detector: Detector | None = (
            None  # used for saving original state before rotating or flipping
        )
        self.pattern_geometry: GeometryRefinement = GeometryRefinement(
            detector=self.detector, wavelength=0.3344e-10, poni1=0, poni2=0
        )  # default params are necessary, otherwise fails...
        self.pattern_geometry_img_shape: tuple[int, int] | None = None
        self.cake_geometry: AzimuthalIntegrator | None = None
        self.cake_geometry_img_shape: tuple[int, int] | None = None
        self.calibrant: Calibrant = Calibrant()

        self.orig_pixel1: float = (
            self.detector.pixel1
        )  # needs to be extra stored for applying supersampling
        self.orig_pixel2: float = self.detector.pixel2

        # All user-settable parameters live in the evented params dataclass;
        # the properties below delegate to it. The machine-specific dioptrin
        # fields get their effective defaults here at construction.
        import dioptas

        self.params: CalibrationParams = CalibrationParams(
            use_dioptrin=dioptas._dioptrin_available,
            dioptrin_num_workers=max((os.cpu_count() or 4) - 1, 1),
        )

        self._calibrants_working_dir: str = calibrants_path

        self.tth: np.ndarray = np.linspace(0, 25)
        self.int: np.ndarray = np.sin(self.tth)
        self.sigma: np.ndarray | None = None
        self.num_points: int = len(self.int)

        self.cake_img: np.ndarray = np.zeros((2048, 2048))
        self.cake_tth: np.ndarray | None = None
        self.cake_azi: np.ndarray | None = None

        self.peak_search_algorithm: Massif | BlobDetection | None = None

        self.img_model.img_changed.connect(self._check_detector_and_image_shape)

        self.detector_reset: Signal = Signal()
        self.parameters_changed: Signal = Signal()
        #: re-emitted whenever params.peak_selections changes; views that
        #: plot the picked peaks subscribe here
        self.points_changed: Signal = Signal()

        self._dioptrin_integrator: Any = None

        # side effects of settings changes live here (not in the property
        # setters), so a direct params write behaves exactly like the
        # property write
        self.params.events.connect(self._on_params_changed)
        # populate params.geometry from the default geometry right away, so
        # later syncs only emit on real change instead of on first touch
        self._sync_calibration_params()

    def _on_params_changed(self, info) -> None:
        if info.signal.name in (
            "detector_mode",
            "detector_name",
            "detector_filename",
            "geometry",
            "distortion_spline_filename",
        ):
            self._reconcile_calibration_params()
        elif info.signal.name == "peak_selections":
            value = info.args[0]
            canonical = _canonical_peak_selections(value)
            if canonical != value:
                # JSON round trips turn tuples into lists; normalize so
                # snapshots and fresh writes always compare equal
                self.params.peak_selections = canonical
                return
            self._points_cache = None
            self._points_index_cache = None
            self.points_changed.emit()

    @property
    def points(self) -> list[np.ndarray]:
        """Picked peaks as numpy arrays, one entry per pick (read-only view
        of ``params.peak_selections`` — mutate through the pick/clear/remove
        methods, which write the params)."""
        if self._points_cache is None:
            self._points_cache = [
                np.array(positions) for _, positions in self.params.peak_selections
            ]
        return self._points_cache

    @property
    def points_index(self) -> list[int]:
        if self._points_index_cache is None:
            self._points_index_cache = [
                ring for ring, _ in self.params.peak_selections
            ]
        return self._points_index_cache

    @property
    def is_calibrated(self) -> bool:
        return self.params.is_calibrated

    @is_calibrated.setter
    def is_calibrated(self, value: bool) -> None:
        self.params.is_calibrated = bool(value)

    @property
    def filename(self) -> str:
        return self.params.poni_filename

    @filename.setter
    def filename(self, value: str) -> None:
        self.params.poni_filename = str(value)

    @property
    def calibration_name(self) -> str:
        return self.params.calibration_name

    @calibration_name.setter
    def calibration_name(self, value: str) -> None:
        self.params.calibration_name = str(value)

    @property
    def detector_mode(self) -> "DetectorModes":
        return DetectorModes(self.params.detector_mode)

    @detector_mode.setter
    def detector_mode(self, value: "DetectorModes") -> None:
        self.params.detector_mode = int(value.value)

    def _sync_calibration_params(self) -> None:
        """Writes the live geometry and detector descriptor into the params.

        The geometry objects are the working machinery; the params are the
        canonical state. Every operation that changes the geometry or the
        detector calls this at the end, so the reconcile reaction sees
        params == live and stays quiet.
        """
        self.params.geometry = _plain_geometry_config(
            self.pattern_geometry.get_config()
        )
        if self.detector_mode == DetectorModes.PREDEFINED:
            self.params.detector_name = str(self.detector.name)
            self.params.detector_filename = ""
        elif self.detector_mode == DetectorModes.NEXUS:
            self.params.detector_name = ""
            self.params.detector_filename = str(
                getattr(self.detector, "filename", "") or ""
            )
        else:
            self.params.detector_name = ""
            self.params.detector_filename = ""

    def _reconcile_calibration_params(self) -> None:
        """Makes the live geometry follow the params (undo/restore path).

        Idempotent full-state compare: interactive operations sync at their
        end, which this recognizes as already reconciled. The detector is
        applied before the geometry, mirroring project loading. A geometry
        pyFAI rejects, or a detector file that has moved, is logged and the
        params are synced back rather than leaving state half-applied.
        """
        params = self.params
        try:
            detector_mode = DetectorModes(params.detector_mode)
            if detector_mode == DetectorModes.PREDEFINED and params.detector_name:
                if (
                    self.detector_mode != DetectorModes.PREDEFINED
                    or str(self.detector.name) != params.detector_name
                ):
                    self.load_detector(params.detector_name)
            elif detector_mode == DetectorModes.NEXUS and params.detector_filename:
                if (
                    self.detector_mode != DetectorModes.NEXUS
                    or str(getattr(self.detector, "filename", ""))
                    != params.detector_filename
                ):
                    self.load_detector_from_file(params.detector_filename)
            elif detector_mode == DetectorModes.CUSTOM:
                # the mode property reads the params, so it cannot serve as
                # the "live" side of this comparison — the detector object
                # can: predefined and nexus detectors are subclasses
                if type(self.detector) is not Detector:
                    # back to a plain detector; pixel sizes and shape then
                    # come from the geometry config applied below
                    self.reset_detector()

            if params.geometry is not None and params.geometry != (
                _plain_geometry_config(self.pattern_geometry.get_config())
            ):
                # rebuilding the integrator is expensive; only on real change.
                # set_pyFAI_config is the one method that applies a config
                # completely — including the model's own detector reference,
                # which a bare pattern_geometry.set_config would leave stale.
                # It marks the model calibrated; when this reconcile is part
                # of a params apply, the is_calibrated field is declared
                # after geometry and corrects that right afterwards.
                self.set_pyFAI_config(deepcopy(params.geometry))
                self.parameters_changed.emit()

            spline = params.distortion_spline_filename
            if spline and self.pattern_geometry.splinefile != spline:
                self.load_distortion(spline)
        except Exception:
            logger.exception("Failed to apply the calibration state")
            self._sync_calibration_params()

    def _append_peak_selection(self, points: np.ndarray, ring: int) -> None:
        entry = (int(ring), tuple(map(tuple, np.atleast_2d(points).tolist())))
        self.params.peak_selections = self.params.peak_selections + (entry,)

    @property
    def start_values(self) -> dict[str, float]:
        return self.params.start_values

    @start_values.setter
    def start_values(self, new_values: dict[str, float]) -> None:
        self.params.start_values = new_values

    @property
    def fit_wavelength(self) -> bool:
        return self.params.fit_wavelength

    @fit_wavelength.setter
    def fit_wavelength(self, new_value: bool) -> None:
        self.params.fit_wavelength = new_value

    @property
    def fixed_values(self) -> dict[str, float]:
        return self.params.fixed_values

    @fixed_values.setter
    def fixed_values(self, new_values: dict[str, float]) -> None:
        self.params.fixed_values = new_values

    @property
    def use_mask(self) -> bool:
        return self.params.use_mask

    @use_mask.setter
    def use_mask(self, new_value: bool) -> None:
        self.params.use_mask = new_value

    @property
    def polarization_factor(self) -> float:
        return self.params.polarization_factor

    @polarization_factor.setter
    def polarization_factor(self, new_value: float) -> None:
        self.params.polarization_factor = new_value

    @property
    def supersampling_factor(self) -> int:
        return self.params.supersampling_factor

    @supersampling_factor.setter
    def supersampling_factor(self, new_value: int) -> None:
        self.params.supersampling_factor = new_value

    @property
    def correct_solid_angle(self) -> bool:
        return self.params.correct_solid_angle

    @correct_solid_angle.setter
    def correct_solid_angle(self, new_value: bool) -> None:
        self.params.correct_solid_angle = new_value

    @property
    def distortion_spline_filename(self) -> str | None:
        return self.params.distortion_spline_filename

    @distortion_spline_filename.setter
    def distortion_spline_filename(self, new_value: str | None) -> None:
        self.params.distortion_spline_filename = new_value

    @property
    def use_dioptrin(self) -> bool:
        return self.params.use_dioptrin

    @use_dioptrin.setter
    def use_dioptrin(self, new_value: bool) -> None:
        self.params.use_dioptrin = new_value

    @property
    def dioptrin_num_workers(self) -> int:
        return self.params.dioptrin_num_workers

    @dioptrin_num_workers.setter
    def dioptrin_num_workers(self, new_value: int) -> None:
        self.params.dioptrin_num_workers = new_value

    def _get_poni_dict(self) -> dict[str, float]:
        return {
            "pixel1": self.orig_pixel1,
            "pixel2": self.orig_pixel2,
            "distance": self.pattern_geometry.dist,
            "poni1": self.pattern_geometry.poni1,
            "poni2": self.pattern_geometry.poni2,
            "rot1": self.pattern_geometry.rot1,
            "rot2": self.pattern_geometry.rot2,
            "rot3": self.pattern_geometry.rot3,
            "wavelength": self.pattern_geometry.wavelength,
        }

    def _create_dioptrin_integrator(self) -> None:
        try:
            import dioptrin

            self._dioptrin_integrator = dioptrin.Integrator.from_poni_dict(
                self._get_poni_dict(),
                method="pixel_split",
                polarization_factor=self.polarization_factor,
                unit="2th_deg",
            )
        except Exception:
            self._dioptrin_integrator = None
            logger.info("Dioptrin integrator not available, using pyFAI")
            self.use_dioptrin = False

    def can_use_dioptrin_batch(self, unit: str, azi_range: tuple[float, float] | None = None) -> bool:
        """Check whether dioptrin batch integration can be used for the given parameters."""
        if not self.use_dioptrin:
            return False
        if self._dioptrin_integrator is None:
            return False
        if azi_range is not None:
            return False
        if not self.correct_solid_angle:
            return False
        if unit not in ("2th_deg", "q_A^-1", "q_nm^-1", "d_A"):
            return False
        return True

    def sync_dioptrin_for_batch(
        self,
        mask: np.ndarray | None,
        unit: str,
        num_points: int | None,
        img_shape: tuple[int, int],
    ) -> int:
        """Configure the dioptrin integrator once before a batch run.

        Sets method, unit, mask, and polarization. Resolves num_points
        if None. Returns the resolved num_points.
        """
        if self.supersampling_factor > 1:
            self._dioptrin_integrator.set_method(
                "supersampled", n_ss=self.supersampling_factor
            )
        else:
            self._dioptrin_integrator.set_method("pixel_split")

        dioptrin_unit = "2th_deg" if unit == "d_A" else unit
        self._dioptrin_integrator.set_unit(dioptrin_unit)

        mask = self._prepare_integration_mask(mask)
        if mask is not None and mask.shape != img_shape:
            mask = None
        self._dioptrin_integrator.set_mask(
            mask.astype(np.uint8) if mask is not None else None
        )
        self._dioptrin_integrator.set_polarization_factor(self.polarization_factor)

        if num_points is None:
            num_points = self.calculate_number_of_pattern_points(img_shape, 2)
        return num_points

    def dioptrin_batch1d(self, images: list[str | np.ndarray], num_points: int) -> Any:
        """Run dioptrin batch 1D integration on a list of file paths or numpy arrays."""
        return self._dioptrin_integrator.batch1d(
            images, num_points, num_workers=self.dioptrin_num_workers
        )

    def dioptrin_batch1d_iter(self, images: Any, num_points: int) -> Iterator[Any]:
        """Run streaming dioptrin batch 1D integration (supports generators)."""
        return self._dioptrin_integrator.batch1d_iter(
            images, num_points, num_workers=self.dioptrin_num_workers
        )

    def find_peaks_automatic(self, x: float, y: float, peak_ind: int) -> np.ndarray:
        """Searches peaks by using the Massif algorithm.

        :param x: x-coordinate in pixel - should be from original image (not supersampled x-coordinate)
        :param y: y-coordinate in pixel - should be from original image (not supersampled y-coordinate)
        :param peak_ind: peak/ring index to which the found points will be added
        """
        logger.info("Auto-finding peaks at (%.1f, %.1f) for ring %d", x, y, peak_ind)
        massif = Massif(self.img_model.img_data, median_prefilter=False)
        cur_peak_points = massif.find_peaks(
            (int(np.round(x)), int(np.round(y))), stdout=DummyStdOut()
        )
        if len(cur_peak_points):
            self._append_peak_selection(np.array(cur_peak_points), peak_ind)
        return np.array(cur_peak_points)

    def find_peak(self, x: float, y: float, search_size: int, peak_ind: int) -> np.ndarray:
        """Searches a peak around the x,y position. It just searches for the maximum value in a specific search size.

        :param x: x-coordinate in pixel - should be from original image (not supersampled x-coordinate)
        :param y: y-coordinate in pixel - should be form original image (not supersampled y-coordinate)
        :param search_size: the length of the search rectangle in pixels in all direction in which the algorithm
            searches for the maximum peak
        :param peak_ind: peak/ring index to which the found points will be added
        """
        logger.debug("Finding peak at (%.1f, %.1f), search_size=%d, ring %d", x, y, search_size, peak_ind)
        left_ind = int(np.round(x - search_size * 0.5))
        if left_ind < 0:
            left_ind = 0
        top_ind = int(np.round(y - search_size * 0.5))
        if top_ind < 0:
            top_ind = 0
        search_array = self.img_model.img_data[
            left_ind : (left_ind + search_size), top_ind : (top_ind + search_size)
        ]
        x_ind, y_ind = np.where(search_array == search_array.max())
        x_ind = x_ind[0] + left_ind
        y_ind = y_ind[0] + top_ind
        self._append_peak_selection(np.array([x_ind, y_ind]), peak_ind)
        return np.array([np.array((x_ind, y_ind))])

    def clear_peaks(self) -> None:
        logger.info("Clearing all calibration peaks")
        self.params.peak_selections = ()

    def remove_peaks_by_ring(self, ring_ind: int) -> None:
        """Removes all peaks belonging to the specified ring index."""
        self.params.peak_selections = tuple(
            entry for entry in self.params.peak_selections if entry[0] != ring_ind
        )

    def remove_last_peak(self) -> int | None:
        if self.params.peak_selections:
            _, positions = self.params.peak_selections[-1]
            self.params.peak_selections = self.params.peak_selections[:-1]
            return len(positions)

    def remove_peak_selection(self, index: int) -> None:
        """Removes the picked-peak group at *index* (in pick order)."""
        selections = self.params.peak_selections
        if not 0 <= index < len(selections):
            return
        self.params.peak_selections = (
            selections[:index] + selections[index + 1:]
        )

    def set_peak_selection_ring(self, index: int, ring_ind: int) -> None:
        """Assigns the picked-peak group at *index* to another ring."""
        selections = self.params.peak_selections
        if not 0 <= index < len(selections):
            return
        ring, positions = selections[index]
        if ring == int(ring_ind):
            return
        self.params.peak_selections = (
            selections[:index]
            + ((int(ring_ind), positions),)
            + selections[index + 1:]
        )

    def create_cake_geometry(self) -> None:
        self.cake_geometry = AzimuthalIntegrator(
            splinefile=self.distortion_spline_filename
        )
        self.cake_geometry.set_config(self.pattern_geometry.get_config())
        self.cake_geometry.detector = self.detector
        if self.use_dioptrin:
            self._create_dioptrin_integrator()

    def setup_peak_search_algorithm(self, algorithm: str, mask: np.ndarray | None = None) -> None:
        """Initializes the peak search algorithm on the current image.

        :param algorithm: peak search algorithm used. Possible algorithms are 'Massif' and 'Blob'
        :param mask: if a mask is used during the process this is provided here as a 2d array for the image.
        """

        if algorithm == "Massif":
            self.peak_search_algorithm = Massif(
                self.img_model.img_data, median_prefilter=False
            )
        elif algorithm == "Blob":
            if mask is not None:
                self.peak_search_algorithm = BlobDetection(
                    self.img_model.img_data * mask
                )
            else:
                self.peak_search_algorithm = BlobDetection(self.img_model.img_data)
            self.peak_search_algorithm.process()
        else:
            return

    def search_peaks_on_ring(
        self,
        ring_index: int,
        delta_tth: float = 0.1,
        min_mean_factor: float = 1,
        upper_limit: float = 55000,
        mask: np.ndarray | None = None,
    ) -> None:
        """This function is searching for peaks on an expected ring. It needs an initial calibration
        before. Then it will search for the ring within some delta_tth and other parameters to get
        peaks from the calibrant.

        :param ring_index: the index of the ring for the search
        :param delta_tth: search space around the expected position in two theta
        :param min_mean_factor: a factor determining the minimum peak intensity to be picked up. it is based
                                on the mean value of the search area defined by delta_tth. Pick a large value
                                for larger minimum value and lower for lower minimum value. Therefore, a smaller
                                number is more prone to picking up noise. typical values like between 1 and 3.
        :param upper_limit: maximum intensity for the peaks to be picked
        :param mask: in case the image has to be masked from certain areas, it need to be given here. Default is None.
                     The mask should be given as an 2d array with the same dimensions as the image, where 1 denotes a
                     masked pixel and all others should be 0.
        """
        self.reset_supersampling()
        if not self.is_calibrated:
            return

        # transform delta from degree into radians
        delta_tth = delta_tth / 180.0 * np.pi

        # get appropriate two theta value for the ring number
        tth_calibrant_list = self.calibrant.get_2th()
        if ring_index >= len(tth_calibrant_list):
            raise NotEnoughSpacingsInCalibrant()
        tth_calibrant = float(tth_calibrant_list[ring_index])

        # get the calculated two theta values for the whole image
        tth_array = self.pattern_geometry.twoThetaArray(self.img_model.img_data.shape)

        # create mask based on two_theta position
        ring_mask = abs(tth_array - tth_calibrant) <= delta_tth

        if mask is not None:
            mask = np.logical_and(ring_mask, np.logical_not(mask))
        else:
            mask = ring_mask

        # calculate the mean and standard deviation of this area
        sub_data = np.array(
            self.img_model.img_data.ravel()[np.where(mask.ravel())], dtype=np.float64
        )
        sub_data[np.where(sub_data > upper_limit)] = np.nan
        mean = np.nanmean(sub_data)
        std = np.nanstd(sub_data)

        # set the threshold into the mask (don't detect very low intensity peaks)
        threshold = min_mean_factor * mean + std
        mask2 = np.logical_and(self.img_model.img_data > threshold, mask)
        mask2[np.where(self.img_model.img_data > upper_limit)] = False
        size2 = mask2.sum(dtype=int)

        keep = int(np.ceil(np.sqrt(size2)))
        try:
            old_stdout = sys.stdout
            sys.stdout = DummyStdOut
            res = self.peak_search_algorithm.peaks_from_area(
                mask2, Imin=mean - std, keep=keep
            )
            sys.stdout = old_stdout
        except IndexError:
            res = []

        # Store the result
        if len(res):
            self._append_peak_selection(np.array(res), ring_index)

        self.set_supersampling()
        self.pattern_geometry.reset()

    def set_calibrant(self, filename: str) -> None:
        logger.info("Setting calibrant: %s", filename)
        self.calibrant = Calibrant()
        self.calibrant.load_file(filename)
        self.pattern_geometry.calibrant = self.calibrant

    def set_start_values(self, start_values: dict[str, float]) -> None:
        self.start_values = start_values
        self.polarization_factor = start_values["polarization_factor"]

    def set_pixel_size(self, pixel_size: tuple[float, float]) -> None:
        self.orig_pixel1 = pixel_size[0]
        self.orig_pixel2 = pixel_size[1]

        self.detector.pixel1 = self.orig_pixel1
        self.detector.pixel2 = self.orig_pixel2
        self.set_supersampling()

    def update_detector_shape(self) -> None:
        self.detector.shape = self.img_model.img_data.shape
        self.detector.max_shape = self.img_model.img_data.shape

    def set_fixed_values(self, fixed_values: dict[str, float]) -> None:
        """Sets the fixed and not fitted values for the geometry refinement.

        :param fixed_values: a dictionary with the fixed parameters as key and their corresponding fixed value, possible
                             keys: 'dist', 'rot1', 'rot2', 'rot3', 'poni1', 'poni2'
        """
        self.fixed_values = fixed_values

    def calibrate(self) -> None:
        logger.info("Starting calibration")
        if len(self.points) == 0:
            raise NoPointsError("No starting points for calibration found.")

        self.reset_supersampling()
        self.pattern_geometry = GeometryRefinement(
            self.create_point_array(self.points, self.points_index),
            dist=self.start_values["dist"],
            wavelength=self.start_values["wavelength"],
            detector=self.detector,
            calibrant=self.calibrant,
            splinefile=self.distortion_spline_filename,
        )

        self.refine()
        self.create_cake_geometry()
        self.is_calibrated = True

        self.calibration_name = "current"
        self.set_supersampling()
        # reset the integrator (not the geometric parameters)
        self.pattern_geometry.reset()
        self._sync_calibration_params()
        self.parameters_changed.emit()

    def refine(self) -> None:
        logger.info("Refining calibration")
        if len(self.points) == 0:
            raise NoPointsError("No points for refinement found.")

        self.reset_supersampling()
        self.pattern_geometry.data = self.create_point_array(
            self.points, self.points_index
        )

        fix = ["wavelength"]
        if self.fit_wavelength:
            fix = []

        for key, value in self.fixed_values.items():
            fix.append(key)
            setattr(self.pattern_geometry, key, value)

        self.pattern_geometry.refine2(fix=fix)
        if self.fit_wavelength:
            self.pattern_geometry.refine2_wavelength(fix=fix)

        self.create_cake_geometry()
        self.set_supersampling()
        # reset the integrator (not the geometric parameters)
        self.pattern_geometry.reset()
        # a standalone refine (controller refinement loop) changes the
        # geometry too — the params must follow it like any other result
        self._sync_calibration_params()

    def _check_detector_and_image_shape(self) -> None:
        if self.detector.shape is not None:
            if self.detector.shape != self.img_model.img_data.shape:
                self.reset_detector()
                self.detector_reset.emit()
                if self.use_dioptrin and self._dioptrin_integrator is not None:
                    self._create_dioptrin_integrator()
        else:
            self.reset_detector()

    def _prepare_integration_mask(self, mask: np.ndarray | None) -> np.ndarray | None:
        if mask is None:
            return self.detector.mask
        else:
            if self.detector.mask is None:
                return mask
            else:
                if mask.shape == self.detector.mask.shape:
                    return np.logical_or(self.detector.mask, mask)

    def _prepare_integration_super_sampling(
        self, mask: np.ndarray | None
    ) -> tuple[np.ndarray, np.ndarray | None]:
        if self.supersampling_factor > 1:
            img_data = supersample_image(
                self.img_model.img_data, self.supersampling_factor
            )
            if mask is not None:
                mask = supersample_image(mask, self.supersampling_factor)
        else:
            img_data = self.img_model.img_data
        return img_data, mask

    def integrate_1d(
        self,
        num_points: int | None = None,
        mask: np.ndarray | None = None,
        polarization_factor: float | None = None,
        filename: str | None = None,
        unit: str = "2th_deg",
        method: str = "csr",
        azi_range: tuple[float, float] | None = None,
        trim_zeros: bool = True,
        calculate_errors: bool = False,
    ) -> tuple[np.ndarray, np.ndarray]:
        self.sigma = None
        if mask is not None and np.all(mask):
            # do not perform integration if the image is completely masked...
            return self.tth, self.int

        if self.pattern_geometry_img_shape != self.img_model.img_data.shape:
            # if cake geometry was used on differently shaped image before the azimuthal integrator needs to be reset
            self.pattern_geometry.reset()
            self.pattern_geometry_img_shape = self.img_model.img_data.shape

        if polarization_factor is None:
            polarization_factor = self.polarization_factor

        self._check_detector_and_image_shape()
        mask = self._prepare_integration_mask(mask)
        if mask is not None and mask.shape != self.img_model.img_data.shape:
            mask = None

        if self.use_dioptrin and self._dioptrin_integrator is not None:
            dioptrin_supported = unit in ("2th_deg", "q_A^-1", "q_nm^-1", "d_A")
            needs_pyFAI = (
                (azi_range is not None)
                or (not self.correct_solid_angle)
                or (not dioptrin_supported)
            )
            if not needs_pyFAI:
                img_data = np.ascontiguousarray(
                    self.img_model.img_data, dtype=np.float64
                )

                if num_points is None:
                    num_points = self.calculate_number_of_pattern_points(
                        img_data.shape, 2
                    )
                self.num_points = num_points

                if self.supersampling_factor > 1:
                    self._dioptrin_integrator.set_method(
                        "supersampled", n_ss=self.supersampling_factor
                    )
                else:
                    self._dioptrin_integrator.set_method("pixel_split")

                dioptrin_unit = "2th_deg" if unit == "d_A" else unit
                self._dioptrin_integrator.set_unit(dioptrin_unit)
                self._dioptrin_integrator.set_mask(
                    mask.astype(np.uint8) if mask is not None else None
                )
                self._dioptrin_integrator.set_polarization_factor(polarization_factor)

                t1 = time.time()
                if calculate_errors:
                    try:
                        result = self._dioptrin_integrator.integrate1d(
                            img_data, num_points, errors=True
                        )
                    except TypeError:
                        logger.info(
                            "Installed Dioptrin does not support error calculation; "
                            "using pyFAI"
                        )
                        result = None
                else:
                    result = self._dioptrin_integrator.integrate1d(
                        img_data, num_points
                    )

                if result is not None and (
                    not calculate_errors or getattr(result, "errors", None) is not None
                ):
                    self.tth = np.array(result.radial)
                    self.int = np.array(result.intensity)
                    if calculate_errors:
                        self.sigma = np.array(result.errors)

                    if unit == "d_A":
                        self.tth = (
                            self.pattern_geometry.wavelength
                            / (2 * np.sin(self.tth / 360 * np.pi))
                            * 1e10
                        )

                    logger.info(
                        "1d integration (dioptrin) of {0}: {1}s.".format(
                            os.path.basename(self.img_model.filename),
                            time.time() - t1,
                        )
                    )

                    if np.sum(self.int) != 0 and trim_zeros:
                        self.tth, self.int = trim_trailing_zeros(
                            self.tth, self.int
                        )
                        if self.sigma is not None:
                            self.sigma = self.sigma[: len(self.int)]

                    return self.tth, self.int

        # pyFAI path
        img_data, mask = self._prepare_integration_super_sampling(mask)

        if num_points is None:
            num_points = self.calculate_number_of_pattern_points(img_data.shape, 2)

        self.num_points = num_points

        t1 = time.time()

        integration_kwargs = dict(
            method=method,
            unit="2th_deg" if unit == "d_A" else unit,
            azimuth_range=azi_range,
            mask=mask,
            polarization_factor=polarization_factor,
            correctSolidAngle=self.correct_solid_angle,
            filename=filename,
        )
        if calculate_errors:
            integration_kwargs["error_model"] = "poisson"

        try:
            result = self.pattern_geometry.integrate1d(
                img_data, num_points, **integration_kwargs
            )
        except NameError:
            integration_kwargs["method"] = "csr"
            result = self.pattern_geometry.integrate1d(
                img_data, num_points, **integration_kwargs
            )

        self.tth = np.array(result.radial)
        self.int = np.array(result.intensity)
        if calculate_errors and result.sigma is not None:
            self.sigma = np.array(result.sigma)

        if unit == "d_A":
            self.tth = (
                self.pattern_geometry.wavelength
                / (2 * np.sin(self.tth / 360 * np.pi))
                * 1e10
            )
        logger.info(
            "1d integration of {0}: {1}s.".format(
                os.path.basename(self.img_model.filename), time.time() - t1
            )
        )

        if (
            np.sum(self.int) != 0 and trim_zeros
        ):  # only trim zeros if not everything is 0 (e.g. bkg-subtraction of the same image)
            self.tth, self.int = trim_trailing_zeros(self.tth, self.int)
            if self.sigma is not None:
                self.sigma = self.sigma[: len(self.int)]

        return self.tth, self.int

    def integrate_2d(
        self,
        mask: np.ndarray | None = None,
        polarization_factor: float | None = None,
        unit: str = "2th_deg",
        method: str = "csr",
        rad_points: int | None = None,
        azimuth_points: int = 360,
        azimuth_range: tuple[float, float] | None = None,
    ) -> np.ndarray:
        if polarization_factor is None:
            polarization_factor = self.polarization_factor

        if self.cake_geometry_img_shape != self.img_model.img_data.shape:
            # if cake geometry was used on differently shaped image before the azimuthal integrator needs to be reset
            self.cake_geometry.reset()
            self.cake_geometry_img_shape = self.img_model.img_data.shape

        self._check_detector_and_image_shape()
        mask = self._prepare_integration_mask(mask)
        if mask is not None and mask.shape != self.img_model.img_data.shape:
            mask = None

        if self.use_dioptrin and self._dioptrin_integrator is not None:
            dioptrin_supported = unit in ("2th_deg", "q_A^-1", "q_nm^-1")
            wrapping_azi = azimuth_range is not None and azimuth_range[0] > azimuth_range[1]
            needs_pyFAI = (not self.correct_solid_angle) or (not dioptrin_supported) or wrapping_azi
            if not needs_pyFAI:
                img_data = np.ascontiguousarray(
                    self.img_model.img_data, dtype=np.float64
                )

                if rad_points is None:
                    rad_points = self.calculate_number_of_pattern_points(
                        img_data.shape, 2
                    )
                self.num_points = rad_points

                if self.supersampling_factor > 1:
                    self._dioptrin_integrator.set_method(
                        "supersampled", n_ss=self.supersampling_factor
                    )
                else:
                    self._dioptrin_integrator.set_method("pixel_split")

                self._dioptrin_integrator.set_unit(unit)
                self._dioptrin_integrator.set_mask(
                    mask.astype(np.uint8) if mask is not None else None
                )
                self._dioptrin_integrator.set_polarization_factor(polarization_factor)

                azi_range_rad = None
                if azimuth_range is not None:
                    azi_range_rad = (
                        np.radians(azimuth_range[0]),
                        np.radians(azimuth_range[1]),
                    )

                t1 = time.time()
                result = self._dioptrin_integrator.integrate2d(
                    img_data, rad_points, azimuth_points,
                    azimuthal_range=azi_range_rad,
                )

                self.cake_img = np.array(result.intensity).reshape(
                    azimuth_points, rad_points
                )
                if result.radial is not None:
                    self.cake_tth = np.array(result.radial)
                else:
                    tth_arr = self.cake_geometry.center_array(
                        img_data.shape, unit=unit
                    )
                    tth_min, tth_max = tth_arr.min(), tth_arr.max()
                    half_step = (tth_max - tth_min) / rad_points / 2
                    self.cake_tth = np.linspace(
                        tth_min + half_step, tth_max - half_step, rad_points
                    )
                if result.azimuthal is not None:
                    self.cake_azi = np.array(result.azimuthal)
                else:
                    azi_min = azimuth_range[0] if azimuth_range else -180.0
                    azi_max = azimuth_range[1] if azimuth_range else 180.0
                    half_step = (azi_max - azi_min) / azimuth_points / 2
                    self.cake_azi = np.linspace(
                        azi_min + half_step, azi_max - half_step, azimuth_points
                    )

                logger.info(
                    "2d integration (dioptrin) of {0}: {1}s.".format(
                        os.path.basename(self.img_model.filename), time.time() - t1
                    )
                )
                return self.cake_img

        # pyFAI path
        img_data, mask = self._prepare_integration_super_sampling(mask)

        if rad_points is None:
            rad_points = self.calculate_number_of_pattern_points(img_data.shape, 2)
        self.num_points = rad_points

        t1 = time.time()

        res = self.cake_geometry.integrate2d(
            img_data,
            rad_points,
            azimuth_points,
            azimuth_range=azimuth_range,
            method=method,
            mask=mask,
            unit=unit,
            polarization_factor=polarization_factor,
            correctSolidAngle=self.correct_solid_angle,
        )
        logger.info(
            "2d integration of {0}: {1}s.".format(
                os.path.basename(self.img_model.filename), time.time() - t1
            )
        )
        self.cake_img = res[0]
        self.cake_tth = res[1]
        self.cake_azi = res[2]
        return self.cake_img

    def cake_integral(self, tth: float, bins: int = 1) -> tuple[np.ndarray, np.ndarray]:
        """Calculates a histogram of the cake in tth direction, thus the result will be pixel vs intensity.

        :param tth: tth value in A^-1
        :param bins: number of bins for summing
        """
        tth_partial_index = get_partial_index(self.cake_tth, tth)
        if tth_partial_index is None:
            return [], []

        tth_center = tth_partial_index + 0.5
        left = tth_center - 0.5 * bins
        right = tth_center + 0.5 * bins

        y1 = abs(np.ceil(left) - left) * self.cake_img[:, int(np.floor(left))]
        y2 = np.sum(self.cake_img[:, int(np.ceil(left)) : int(np.floor(right))], axis=1)
        y3 = (right - np.floor(right)) * self.cake_img[:, int(np.floor(right))]

        x = np.array(range(len(self.cake_azi))) + 0.5
        y = (y1 + y2 + y3) / bins
        return x, y

    def create_point_array(self, points: list[np.ndarray], points_ind: list[int]) -> np.ndarray:
        res = []
        for i, point_list in enumerate(points):
            if point_list.shape == (2,):
                res.append([point_list[0], point_list[1], points_ind[i]])
            else:
                for point in point_list:
                    res.append([point[0], point[1], points_ind[i]])
        return np.array(res)

    def get_point_array(self) -> np.ndarray:
        return self.create_point_array(self.points, self.points_index)

    def get_calibration_parameter(self) -> tuple[dict[str, Any], dict[str, Any] | None]:
        pyFAI_parameter = self.pattern_geometry.get_config()
        pyFAI_parameter["polarization_factor"] = self.polarization_factor
        try:
            fit2d_obj = self.pattern_geometry.getFit2D()
            fit2d_parameter = dict(fit2d_obj)
            fit2d_parameter["polarization_factor"] = self.polarization_factor
        except TypeError:
            fit2d_parameter = None

        pyFAI_parameter["wavelength"] = self.pattern_geometry.wavelength
        if fit2d_parameter:
            fit2d_parameter["wavelength"] = self.pattern_geometry.wavelength

        legacy_keys = [
            "detector",
            "pixel1",
            "pixel2",
            "dist",
            "poni1",
            "poni2",
            "rot1",
            "rot2",
            "rot3",
            "wavelength",
            "polarization_factor",
        ]
        normalized = {}
        for key in legacy_keys:
            value = pyFAI_parameter.get(key)
            if key == "detector" and isinstance(value, dict):
                value = value.get("name") or value.get("type") or value.get("class")
            if key in ("pixel1", "pixel2") and value is None:
                value = getattr(self.pattern_geometry, key, None)
            if key in ("pixel1", "pixel2") and value is None:
                value = getattr(self.detector, key, None)
            if value is not None:
                normalized[key] = value

        return normalized, fit2d_parameter

    def calculate_number_of_pattern_points(
        self, img_shape: tuple[int, int], max_dist_factor: float = 1.5
    ) -> int:
        # calculates the number of points for an integrated pattern, based on the distance of the beam center to the the
        # image corners. Maximum value is determined by the shape of the image.
        fit2d_parameter = self.pattern_geometry.getFit2D()
        center_x = fit2d_parameter["centerX"]
        center_y = fit2d_parameter["centerY"]
        width, height = img_shape

        if width > center_x > 0:
            side1 = np.max([abs(width - center_x), center_x])
        else:
            side1 = width

        if center_y < height and center_y > 0:
            side2 = np.max([abs(height - center_y), center_y])
        else:
            side2 = height
        max_dist = np.sqrt(side1**2 + side2**2)
        return int(max_dist * max_dist_factor)

    def load(self, poni_filename: str) -> None:
        """Loads a calibration file and sets all the calibration parameter."""
        logger.info("Loading calibration from %s", poni_filename)
        try:
            poni_dict = PoniFile(poni_filename).as_dict()
        except Exception as e:
            raise file_loading_error(poni_filename, "calibration") from e

        # PoniFile parses any text file without complaint and just leaves the
        # geometry values at None — treat that as an unreadable file
        if any(
            poni_dict.get(key) is None
            for key in ("dist", "poni1", "poni2", "rot1", "rot2", "rot3")
        ):
            raise file_loading_error(poni_filename, "calibration")

        if (
            poni_dict.get("poni_version", 1) >= 2
            and "orientation" in poni_dict["detector_config"]
        ):
            # Check orientation and patch it since pyFAI and Dioptas use different conventions:
            # - Dioptas convention: origin at the top right when looking from the sample
            # - Default pyFAI convention: origin at the bottom right when looking from the sample
            poni_dict = poni_flipud(poni_dict)

        self.pattern_geometry = GeometryRefinement(
            wavelength=0.3344e-10, detector=self.detector, poni1=0, poni2=0
        )  # default params are necessary, otherwise fails...
        self.pattern_geometry.set_config(poni_dict)
        self.orig_pixel1 = self.pattern_geometry.pixel1
        self.orig_pixel2 = self.pattern_geometry.pixel2

        if (
            self.pattern_geometry.pixel1 == self.detector.pixel1
            and self.pattern_geometry.pixel2 == self.detector.pixel2
        ):
            self.pattern_geometry.detector = (
                self.detector
            )  # necessary since loading a poni file will reset the detector
        else:
            self.reset_detector()

        self.calibration_name = get_base_name(poni_filename)
        self.filename = poni_filename
        self.is_calibrated = True
        self.create_cake_geometry()
        self.set_supersampling()
        if self.use_dioptrin:
            self._create_dioptrin_integrator()
        self._sync_calibration_params()
        self.parameters_changed.emit()

    def save(self, filename: str) -> None:
        """Save the current calibration parameters to a text file.

        The conventional filename suffix is ``.poni``.
        """
        logger.info("Saving calibration to %s", filename)
        poni_config = self.cake_geometry.get_config()
        poni_config = poni_flipud(poni_config)

        with open(filename, "w") as f:
            PoniFile(poni_config).write(f)

        self.calibration_name = get_base_name(filename)
        self.filename = filename

    def load_detector(self, name: str) -> None:
        logger.info("Loading detector: %s", name)
        self.detector_mode = DetectorModes.PREDEFINED
        names, classes = get_available_detectors()
        detector_ind = names.index(name)

        self._load_detector(classes[detector_ind]())

    def load_detector_from_file(self, filename: str) -> None:
        logger.info("Loading detector from file: %s", filename)
        self.detector_mode = DetectorModes.NEXUS
        self._load_detector(NexusDetector(filename))

    def _load_detector(self, detector: Detector) -> None:
        """Loads a pyFAI detector."""
        self.detector = detector
        self.detector.calc_mask()
        self.orig_pixel1 = self.detector.pixel1
        self.orig_pixel2 = self.detector.pixel2

        self.pattern_geometry.detector = self.detector

        if self.cake_geometry:
            self.cake_geometry.detector = self.detector

        self.set_supersampling()
        self._original_detector = None
        self._sync_calibration_params()
        self.parameters_changed.emit()

    def reset_detector(self) -> None:
        self.detector_mode = DetectorModes.CUSTOM
        self.detector = Detector(
            pixel1=self.detector.pixel1, pixel2=self.detector.pixel2
        )
        self.update_detector_shape()
        self.pattern_geometry.detector = self.detector
        if self.cake_geometry:
            self.cake_geometry.detector = self.detector
        self.set_supersampling()
        self._sync_calibration_params()

    def create_file_header(self) -> str:
        try:
            # pyFAI version 0.12.0
            return self.pattern_geometry.makeHeaders(
                polarization_factor=self.polarization_factor
            )
        except AttributeError:
            # pyFAI after version 0.12.0
            from pyFAI.io import DefaultAiWriter

            return DefaultAiWriter(None, self.pattern_geometry).make_headers()

    def set_fit2d(self, fit2d_parameter: dict[str, float]) -> None:
        """Reads in a dictionary with fit2d parameters where the fields of the dictionary are:
        'directDist', 'centerX', 'centerY', 'tilt', 'tiltPlanRotation', 'pixelX', pixelY',
        'polarization_factor', 'wavelength'
        """
        self.pattern_geometry.setFit2D(
            directDist=fit2d_parameter["directDist"],
            centerX=fit2d_parameter["centerX"],
            centerY=fit2d_parameter["centerY"],
            tilt=fit2d_parameter["tilt"],
            tiltPlanRotation=fit2d_parameter["tiltPlanRotation"],
            pixelX=fit2d_parameter["pixelX"],
            pixelY=fit2d_parameter["pixelY"],
        )
        # the detector pixel1 and pixel2 values are updated by setPyFAI
        self.orig_pixel1 = self.detector.pixel1
        self.orig_pixel2 = self.detector.pixel2

        self.pattern_geometry.wavelength = fit2d_parameter["wavelength"]
        self.create_cake_geometry()
        self.polarization_factor = fit2d_parameter["polarization_factor"]
        self.orig_pixel1 = fit2d_parameter["pixelX"] * 1e-6
        self.orig_pixel2 = fit2d_parameter["pixelY"] * 1e-6
        self.is_calibrated = True
        self.set_supersampling()
        self._sync_calibration_params()
        self.parameters_changed.emit()

    def set_pyFAI(self, pyFAI_parameter: dict[str, float]) -> None:
        """Reads in a dictionary with pyFAI parameters where the fields of dictionary are:
        'dist', 'poni1', 'poni2', 'rot1', 'rot2', 'rot3', 'pixel1', 'pixel2', 'wavelength',
        'polarization_factor'
        """
        config = self.pattern_geometry.get_config()
        for key in ("dist", "poni1", "poni2", "rot1", "rot2", "rot3"):
            config[key] = pyFAI_parameter[key]
        detector_config = dict(config.get("detector_config") or {})
        detector_config.update(
            pixel1=pyFAI_parameter["pixel1"],
            pixel2=pyFAI_parameter["pixel2"],
        )
        config["detector_config"] = detector_config
        self.pattern_geometry.set_config(config)

        # set_config reconstructs the detector from its serializable config.
        # Keep the live Dioptas detector instead: it may carry an image mask,
        # distortion spline, or detector-specific runtime state.
        self.detector.pixel1 = pyFAI_parameter["pixel1"]
        self.detector.pixel2 = pyFAI_parameter["pixel2"]
        self.pattern_geometry.detector = self.detector
        self.orig_pixel1 = self.detector.pixel1
        self.orig_pixel2 = self.detector.pixel2
        self.pattern_geometry.wavelength = pyFAI_parameter["wavelength"]
        self.create_cake_geometry()
        self.polarization_factor = pyFAI_parameter["polarization_factor"]
        self.is_calibrated = True
        self.set_supersampling()
        if self.use_dioptrin:
            self._create_dioptrin_integrator()
        self._sync_calibration_params()
        self.parameters_changed.emit()

    def get_pyFAI_config(self) -> dict:
        """Returns the pyFAI configuration of the geometry refinement object."""
        return self.pattern_geometry.get_config()

    def set_pyFAI_config(self, pyFAI_config: dict) -> None:
        """Updates the pyFAI configuration of the geometry refinement object. The pyFAI_config is the dictionary
        extracted from an azimuthal integrator object using the get_config() method.
        """
        self.pattern_geometry.set_config(pyFAI_config)
        def _get_detector_pixel(config: dict, key: str) -> float | None:
            detector_config = config.get("detector_config")
            if isinstance(detector_config, dict) and key in detector_config:
                return detector_config[key]
            detector = config.get("detector")
            if isinstance(detector, dict) and key in detector:
                return detector[key]
            if isinstance(detector, dict):
                detector_config = detector.get("config")
                if isinstance(detector_config, dict) and key in detector_config:
                    return detector_config[key]
            return None

        pixel1 = _get_detector_pixel(pyFAI_config, "pixel1")
        pixel2 = _get_detector_pixel(pyFAI_config, "pixel2")
        if pixel1 is None:
            pixel1 = getattr(self.pattern_geometry, "pixel1", None)
        if pixel2 is None:
            pixel2 = getattr(self.pattern_geometry, "pixel2", None)
        if pixel1 is None or pixel2 is None:
            raise ValueError("pyFAI config is missing detector pixel size information")

        self.detector.pixel1 = pixel1
        self.detector.pixel2 = pixel2
        self.orig_pixel1 = self.detector.pixel1
        self.orig_pixel2 = self.detector.pixel2
        self.create_cake_geometry()
        self.is_calibrated = True
        self.set_supersampling()
        if self.use_dioptrin:
            self._create_dioptrin_integrator()

    def load_distortion(self, spline_filename: str) -> None:
        logger.info("Loading distortion spline: %s", spline_filename)
        self.distortion_spline_filename = spline_filename
        self.pattern_geometry.splinefile = spline_filename
        if self.cake_geometry:
            self.cake_geometry.splinefile = spline_filename

    def reset_distortion_correction(self) -> None:
        self.distortion_spline_filename = None
        self.detector.splinefile = None
        self.pattern_geometry.splinefile = None
        if self.cake_geometry:
            self.cake_geometry.splinefile = None

    def set_supersampling(self, factor: int | None = None) -> None:
        """Sets the supersampling to a specific factor. Whereby the factor determines in how many artificial pixel the
        original pixel is split. (factor^2)

        factor  n_pixel
        1       1
        2       4
        3       9
        4       16
        """
        logger.info("Setting supersampling factor to %s", factor)
        if factor is None:
            factor = self.supersampling_factor

        self.detector.pixel1 = self.orig_pixel1 / float(factor)
        self.detector.pixel2 = self.orig_pixel2 / float(factor)
        self.pattern_geometry.pixel1 = self.orig_pixel1 / float(factor)
        self.pattern_geometry.pixel2 = self.orig_pixel2 / float(factor)

        if factor != self.supersampling_factor:
            self.pattern_geometry.reset()
            self.supersampling_factor = factor

    def reset_supersampling(self) -> None:
        self.pattern_geometry.pixel1 = self.orig_pixel1
        self.pattern_geometry.pixel2 = self.orig_pixel2
        self.detector.pixel1 = self.orig_pixel1
        self.detector.pixel2 = self.orig_pixel2

    def get_two_theta_img(self, x: np.ndarray | float, y: np.ndarray | float) -> float:
        """Gives the two_theta value for the x,y coordinates on the image. Be aware that this function will be
        incorrect for pixel indices, since it does not correct for center of the pixel.

        :param x: x-coordinate in pixel on the image
        :param y: y-coordinate in pixel on the image
        :return: two theta in radians
        """
        if not isinstance(x, np.ndarray):
            x = np.array([x])
        if not isinstance(y, np.ndarray):
            y = np.array([y])
        x *= self.supersampling_factor
        y *= self.supersampling_factor

        return self.pattern_geometry.tth(x - 0.5, y - 0.5)[
            0
        ]  # deletes 0.5 because tth function uses pixel indices

    def get_azi_img(self, x: np.ndarray | float, y: np.ndarray | float) -> float:
        """Gives chi for position on image.

        :param x: x-coordinate in pixel on the image
        :param y: y-coordinate in pixel on the image
        :return: azimuth in radians
        """
        # if float convert to np.array:
        if not isinstance(x, np.ndarray):
            x = np.array([x])
        if not isinstance(y, np.ndarray):
            y = np.array([y])
        x *= self.supersampling_factor
        y *= self.supersampling_factor
        return self.pattern_geometry.chi(x - 0.5, y - 0.5)[0]

    @property
    def tth_array(self) -> np.ndarray:
        """Two theta array for the current image shape in radians."""
        shape = self.img_model.img_data.shape
        return self.pattern_geometry.center_array(shape, unit="2th_rad")

    @property
    def azi_array(self) -> np.ndarray:
        """Azimuthal (chi) array for the current image shape in radians."""
        shape = self.img_model.img_data.shape
        return self.pattern_geometry.center_array(shape, unit="chi_rad")

    def get_two_theta_array(self) -> np.ndarray:
        return self.tth_array[
            :: self.supersampling_factor, :: self.supersampling_factor
        ]

    def get_pixel_ind(self, tth: float, azi: float) -> tuple[float, float] | list:
        """Calculates pixel index for a specific two theta and azimuthal value.

        :param tth: two theta in radians
        :param azi: azimuth in radians
        """
        tth_ind = find_contours(self.tth_array, tth)
        if len(tth_ind) == 0:
            return []
        tth_ind = np.vstack(tth_ind)
        azi_values = self.pattern_geometry.chi(tth_ind[:, 0], tth_ind[:, 1])
        min_index = np.argmin(np.abs(azi_values - azi))
        return tth_ind[min_index, 0], tth_ind[min_index, 1]

    @property
    def wavelength(self) -> float:
        return self.pattern_geometry.wavelength

    ##########################
    ## Detector rotation stuff
    def swap_detector_shape(self) -> None:
        self._swap_detector_shape()
        self._swap_pixel_size()
        self._swap_detector_module_size()

    def rotate_detector_m90(self) -> None:
        """Rotates the detector stuff by m90 degree. This includes swapping of shape, pixel size and module sizes,
        as well as dx and dy.
        """
        self._save_original_detector_definition()

        self.swap_detector_shape()
        self._reset_detector_mask()
        self._transform_pixel_corners(rotate_matrix_m90)

    def rotate_detector_p90(self) -> None:
        self._save_original_detector_definition()

        self.swap_detector_shape()
        self._reset_detector_mask()
        self._transform_pixel_corners(rotate_matrix_p90)

    def flip_detector_horizontally(self) -> None:
        self._save_original_detector_definition()
        self._transform_pixel_corners(np.fliplr)

    def flip_detector_vertically(self) -> None:
        self._save_original_detector_definition()
        self._transform_pixel_corners(np.flipud)

    def reset_transformations(self) -> None:
        """Restores the detector to its original state."""
        if self._original_detector is None:  # no transformations done so far
            return

        self.detector = deepcopy(self._original_detector)
        self.orig_pixel1, self.orig_pixel2 = self.detector.pixel1, self.detector.pixel2
        self.pattern_geometry.detector = self.detector
        if self.cake_geometry is not None:
            self.cake_geometry.detector = self.detector
        self.set_supersampling()
        self._original_detector = None

    def load_transformations_string_list(self, transformations: list[str]) -> None:
        """Transforms the detector parameters (shape, pixel size and distortion correction) based on a
        list of transformation actions.

        :param transformations: list of transformations specified as strings, values are "flipud", "fliplr",
                                "rotate_matrix_m90", "rotate_matrix_p90"
        """
        for transformation in transformations:
            if transformation == "flipud":
                self.flip_detector_vertically()
            elif transformation == "fliplr":
                self.flip_detector_horizontally()
            elif transformation == "rotate_matrix_m90":
                self.rotate_detector_m90()
            elif transformation == "rotate_matrix_p90":
                self.rotate_detector_p90()

    def _save_original_detector_definition(self) -> None:
        """Saves the state of the detector to _original_detector if not done yet. Used for restoration upon
        resetting the transformations.
        """
        if self._original_detector is None:
            self._original_detector = deepcopy(self.detector)
            self._original_detector.pixel1 = self.orig_pixel1
            self._original_detector.pixel2 = self.orig_pixel2
            self._mask = False

    def _transform_pixel_corners(self, transform_function: Callable[[np.ndarray], np.ndarray]) -> None:
        if self.detector._pixel_corners is not None:
            self.detector._pixel_corners = np.ascontiguousarray(
                transform_function(self.detector.get_pixel_corners())
            )

    def _swap_pixel_size(self) -> None:
        """Swaps the pixel sizes."""
        self.orig_pixel1, self.orig_pixel2 = self.orig_pixel2, self.orig_pixel1
        self.set_supersampling()

    def _swap_detector_shape(self) -> None:
        """Swaps the detector shape and max_shape values."""
        if self.detector.shape is not None:
            self.detector.shape = (self.detector.shape[1], self.detector.shape[0])
        if self.detector.max_shape is not None:
            self.detector.max_shape = (
                self.detector.max_shape[1],
                self.detector.max_shape[0],
            )

    def _swap_detector_module_size(self) -> None:
        """Swaps the module size and gap sizes for e.g. Pilatus Detectors."""
        if hasattr(self.detector, "module_size"):
            self.detector.module_size = (
                self.detector.module_size[1],
                self.detector.module_size[0],
            )
        if hasattr(self.detector, "MODULE_GAP"):
            self.detector.MODULE_GAP = (
                self.detector.MODULE_GAP[1],
                self.detector.MODULE_GAP[0],
            )

    def _reset_detector_mask(self) -> None:
        """Resets and recalculates the mask. Transformations to shape and module size have to be performed before."""
        self.detector._mask = False


def poni_flipud(poni_dict: dict) -> dict:
    """Flips the detector up-down orientation in a poni configuration dictionary. Changes the dictionary object
    in place.
    """
    orientation = poni_dict["detector_config"]["orientation"]
    if orientation in (Orientation.Unspecified, Orientation.BottomRight):
        poni_dict["detector_config"]["orientation"] = Orientation.TopRight
    elif orientation == Orientation.TopRight:
        poni_dict["detector_config"]["orientation"] = Orientation.BottomRight
    elif orientation == Orientation.BottomLeft:
        poni_dict["detector_config"]["orientation"] = Orientation.TopLeft
    elif orientation == Orientation.TopLeft:
        poni_dict["detector_config"]["orientation"] = Orientation.BottomLeft
    else:
        logger.error(
            "Detector orientation is not supported: Saved .poni file is not compatible with pyFAI"
        )
    return poni_dict


def _plain_geometry_config(config: dict) -> dict:
    """The pyFAI config with numpy scalars coerced to plain floats, so it
    compares and JSON-serializes like any other params value."""
    plain = {}
    for key, value in config.items():
        if isinstance(value, np.generic):
            plain[key] = value.item()
        elif isinstance(value, dict):
            plain[key] = _plain_geometry_config(value)
        else:
            plain[key] = value
    return plain


def _canonical_peak_selections(value: Any) -> tuple:
    """Nested tuples of (ring, ((x, y), ...)) — the one true shape.

    JSON (project files) has no tuples, so a loaded document arrives as
    nested lists; comparing that against a freshly picked tuple would claim
    a change where there is none."""
    return tuple(
        (int(ring), tuple(tuple(float(c) for c in point) for point in positions))
        for ring, positions in value
    )


class DetectorModes(Enum):
    CUSTOM = 1
    NEXUS = 2
    PREDEFINED = 3


class NotEnoughSpacingsInCalibrant(Exception):
    pass


class DetectorShapeError(Exception):
    pass


class NoPointsError(Exception):
    pass


class DummyStdOut:
    @classmethod
    def write(cls, *args: Any, **kwargs: Any) -> None:
        pass


def get_available_detectors() -> tuple[list[str], list[type[Detector]]]:
    detector_classes = set()
    detector_names = []

    for key, item in ALL_DETECTORS.items():
        detector_classes.add(item)

    for detector in detector_classes:
        if len(detector.aliases) > 0:
            detector_names.append(detector.aliases[0])
        else:
            detector_names.append(detector().__class__.__name__)

    sorted_indices = sorted(range(len(detector_names)), key=detector_names.__getitem__)

    detector_names_sorted = [detector_names[i] for i in sorted_indices]
    detector_classes_sorted = [list(detector_classes)[i] for i in sorted_indices]

    base_class_index = detector_names_sorted.index("Detector")
    del detector_names_sorted[base_class_index]
    del detector_classes_sorted[base_class_index]

    return detector_names_sorted, detector_classes_sorted
