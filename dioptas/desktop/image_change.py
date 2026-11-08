# SPDX-License-Identifier: MIT
"""Check detector changes before publishing an image into the live session."""

from copy import deepcopy
from pathlib import Path

import numpy as np
from pyFAI.detectors import Detector
from pyFAI.geometryRefinement import GeometryRefinement
from pyFAI.io.ponifile import PoniFile

from dioptas.model.ImgModel import ImgModel
from dioptas.model.CalibrationModel import DetectorModes


class ImageChangeWorkflow:
    def _source_image_shape(self):
        """Undo rotations on dimensions alone; never copy or move live pixels."""
        image = self.configuration.img_model
        shape = tuple(image.raw_img_data.shape)
        for name in image.params.transformations:
            if name in {"rotate_matrix_m90", "rotate_matrix_p90"}:
                shape = shape[::-1]
        return shape

    def _expected_image_shape(self):
        if self._has_image:
            return self._source_image_shape()
        expected = getattr(self, "_calibration_image_shape", None)
        calibration = self.configuration.calibration_model
        if expected is None and calibration.detector_mode != DetectorModes.CUSTOM:
            expected = calibration.detector.max_shape
        return tuple(expected) if expected else None

    @staticmethod
    def _poni_shape(path):
        """Legacy/custom PONIs may carry pitches but no detector dimensions."""
        detector = PoniFile(path).detector
        shape = detector.shape or detector.max_shape
        return tuple(shape) if shape else None

    def _open_checked_image(self, path, *, frame=1, reset_calibration=False):
        if not isinstance(reset_calibration, bool):
            raise ValueError("Reset calibration must be a boolean.")
        if isinstance(frame, bool) or int(frame) != frame or frame < 1:
            raise ValueError("Frame must be a positive integer.")
        frame = int(frame)
        # Some readers retain a loader/selected source. Probe on an independent
        # model so cancellation preserves these as well as the visible pixels.
        reader = ImgModel()
        decoded = reader.get_image_data(path, frame - 1)
        shape = tuple(decoded["img_data"].shape)
        image = self.configuration.img_model
        previous = self._expected_image_shape()
        if previous and shape != previous and not reset_calibration:
            return {
                "cancelled": True,
                "imageChange": {
                    "path": path, "frame": frame,
                    "previousShape": list(previous), "newShape": list(shape),
                },
            }
        if reset_calibration:
            self._reset_detector_state()
        # Adopt the reader handles only after the user accepts the change.
        for name in ("loader", "selected_source"):
            if hasattr(reader, name):
                setattr(image, name, getattr(reader, name))
        image.load_data(path, decoded, frame - 1)
        self.configuration.calibration_model.clear_peaks()
        self._fit_rms = None
        self._has_image = True
        if self.configuration.calibration_model.is_calibrated:
            self._calibration_image_shape = shape
        self._calculate()
        return {
            **self._snapshot(include_image=True),
            **({"calibrationReset": True} if reset_calibration else {}),
        }

    def _reset_detector_state(self):
        """Discard detector-dependent state while keeping the image/references."""
        configuration = self.configuration
        calibration, image = configuration.calibration_model, configuration.img_model
        calibration._dioptrin_integrator = None
        calibration._dioptrin_integrator_key = None
        calibration.is_calibrated = False
        calibration.clear_peaks()
        calibration.filename = ""
        calibration.calibration_name = ""
        calibration._original_detector = None
        calibration.detector = Detector(pixel1=79e-6, pixel2=79e-6)
        calibration.orig_pixel1 = calibration.orig_pixel2 = 79e-6
        calibration.pattern_geometry = GeometryRefinement(
            detector=calibration.detector,
            dist=calibration.start_values["dist"],
            wavelength=calibration.start_values["wavelength"], poni1=0, poni2=0,
        )
        calibration.cake_geometry = None
        calibration.pattern_geometry_img_shape = calibration.cake_geometry_img_shape = None
        # Publish detector and geometry together: individual params reactions
        # would otherwise reapply part of the previous calibrated detector.
        with calibration.params.events.blocked():
            calibration.detector_mode = DetectorModes.CUSTOM
            calibration.reset_distortion_correction()
            calibration.set_fixed_values({})
            calibration.set_supersampling()
            calibration._sync_calibration_params()
        calibration.parameters_changed.emit()

        for name in list(image.img_corrections.corrections):
            image.delete_img_correction(name)
        image.transfer_correction.reset()
        image.flat_field_correction.reset()
        image.reset_background()
        image.background_scaling = 1.0
        image.background_offset = 0.0
        image.factor = 1.0
        image.reset_transformations(img_changed=False)
        image._sync_correction_params()
        calibration.update_detector_shape()
        calibration._sync_calibration_params()
        mask = configuration.mask_model
        mask.roi = None
        mask.filename = ""
        mask.set_mask_data(np.zeros(image.img_data.shape, dtype=bool))
        for name in configuration.mask_plugin_manager.plugins:
            configuration.mask_plugin_manager.set_enabled(name, False)
        configuration.use_mask = False
        if configuration.pattern_model.pattern_source != "file":
            configuration.pattern_model.set_pattern(
                np.empty(0), np.empty(0), unit=configuration.integration_unit,
            )
        self._integration_auto_save = False
        self._integration_reset_autoprocess()
        self._calibration_image_shape = None
        self._setup_confirmed = False
        self._geometry_source = "none"
        self._fit_dirty = False
        self._fit_rms = None
        self._inspection = None
        self._ring_cache = None

    def _reset_calibration(self):
        self._reset_detector_state()
        self._calculate()
        return {**self._snapshot(include_image=True), "calibrationReset": True}

    def _checked_next_image(self, direction, step):
        image = self.configuration.img_model
        # Time-order iteration mutates its cursor; do that on a copy until
        # compatibility is accepted, including when the dialog is cancelled.
        iterator = deepcopy(image.file_name_iterator)
        method = iterator.get_next_filename if direction == 1 else iterator.get_previous_filename
        path = method(mode=image.file_iteration_mode, step=step)
        if path is None:
            return {"cancelled": True}
        return self._open_checked_image(str(Path(path).resolve()))
