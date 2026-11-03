# SPDX-License-Identifier: MIT
"""Integration commands over the existing Qt-independent scientific models.

No automatic model signal launches work: the desktop worker owns all science,
including BatchModel. Image-load autocreate is explicitly handled by the host.
"""

from __future__ import annotations

from pathlib import Path
from copy import deepcopy
from collections import deque
import math
import numpy as np

from dioptas.model.util.NewFileWatcher import NewFileInDirectoryWatcher
from dioptas.model.util.calc import convert_units
from dioptas.model.util.ImgCorrection import (
    FlatFieldCorrection,
    CbnCorrection,
    ObliqueAngleDetectorAbsorptionCorrection,
)

CORRECTIONS = {
    "cbn": (
        CbnCorrection,
        {
            "diamond_thickness": ("Diamond thickness (mm)", 2.0, 0.001, 100.0),
            "seat_thickness": ("Seat thickness (mm)", 5.0, 0.001, 100.0),
            "small_cbn_seat_radius": ("Small seat radius (mm)", 0.5, 0.001, 100.0),
            "large_cbn_seat_radius": ("Large seat radius (mm)", 2.0, 0.001, 100.0),
            "tilt": ("Tilt (°)", 0.0, -89.0, 89.0),
            "tilt_rotation": ("Tilt rotation (°)", 0.0, -360.0, 360.0),
            "diamond_abs_length": ("Diamond absorption length (mm)", 13.7, 0.001, 1e6),
            "cbn_abs_length": ("cBN absorption length (mm)", 14.05, 0.001, 1e6),
            "center_offset": ("Center offset (mm)", 0.0, -100.0, 100.0),
            "center_offset_angle": ("Offset angle (°)", 0.0, -360.0, 360.0),
        },
    ),
    "oiadac": (
        ObliqueAngleDetectorAbsorptionCorrection,
        {
            "detector_thickness": ("Detector thickness (µm)", 40.0, 0.001, 1e6),
            "absorption_length": ("Absorption length (µm)", 150.0, 0.001, 1e6),
            "tilt": ("Detector tilt (°)", 0.0, -89.0, 89.0),
            "rotation": ("Detector rotation (°)", 0.0, -360.0, 360.0),
        },
    ),
}


def finite(value, name, low=-1e12, high=1e12, integer=False):
    result = float(value)
    if (
        not math.isfinite(result)
        or not low <= result <= high
        or (integer and result != int(result))
    ):
        raise ValueError(
            f"{name} must be {'an integer ' if integer else ''}between {low:g} and {high:g}."
        )
    return int(result) if integer else result


def boolean(value, name):
    if not isinstance(value, bool):
        raise ValueError(f"{name} must be a boolean.")
    return value


def optional_range(value):
    if value is None:
        return None
    if not isinstance(value, list) or len(value) != 2:
        raise ValueError("Azimuth range needs two angles or full range.")
    low, high = [finite(x, "Azimuth (°)", -180, 180) for x in value]
    # Qt/pyFAI supports wrapped sectors, e.g. [150, -150].
    if low == high:
        raise ValueError("Azimuth endpoints must differ.")
    return [low, high]


def values(array):
    return [float(x) if np.isfinite(x) else None for x in array]


class IntegrationWorkflow:
    @staticmethod
    def _integration_wrapped(angles):
        return angles is not None and angles[0] > angles[1]

    def _integration_calculate_pattern(self):
        c = self.configuration
        geometry = c.calibration_model.pattern_geometry
        wrapped = self._integration_wrapped(c.oned_azimuth_range)
        if wrapped:
            # pyFAI's discontinuity setter clears centers/corners, but not
            # every cached angular-width array from an earlier integration.
            geometry.reset()
            geometry.setChiDiscAtZero()
        try:
            return c.integrate_image_1d()
        finally:
            if wrapped:
                geometry.setChiDiscAtPi()
                geometry.reset()

    def _integration_calculate_cake(self):
        c = self.configuration
        geometry = c.calibration_model.cake_geometry
        wrapped = self._integration_wrapped(c.cake_azimuth_range)
        if wrapped:
            # pyFAI's discontinuity setter clears centers/corners, but not
            # every cached angular-width array from an earlier integration.
            geometry.reset()
            geometry.setChiDiscAtZero()
        try:
            c.integrate_image_2d()
        finally:
            if wrapped:
                geometry.setChiDiscAtPi()
                geometry.reset()

    def _integration_handlers(self):
        return {
            "integration_settings": self._integration_settings,
            "integration_roi": self._integration_roi,
            "integration_phase_guides": self._integration_phase_guides,
            "integration_navigation": self._integration_navigation,
            "integration_image_directory": self._integration_image_directory,
            "integration_autoprocess": self._integration_autoprocess,
            "integration_autoprocess_poll": self._integration_autoprocess_poll,
            "integration_clear_background": self._integration_clear_background,
            "integration_background": self._integration_background,
            "integration_image_background": self._integration_image_background,
            "integration_correction": self._integration_correction,
            "integration_flat_field": self._integration_flat_field,
            "integration_overlay": self._integration_overlay,
            "integration_phase": self._integration_phase,
            "integration_open_pattern": self._integration_open_pattern,
            "integration_pattern_navigation": self._integration_pattern_navigation,
            "integration_autocreate": self._integration_autocreate,
            "integration_save_image": self._integration_save_image,
            "integration_save_pattern": self._integration_save_pattern,
            "integration_save_background": self._integration_save_background,
            "integration_output_directory": self._integration_output_directory,
            "integration_batch": self._integration_batch,
            "integration_save_batch": self._integration_save_batch,
        }

    def _integration_state(self):
        c = self.configuration
        p = c.pattern_model.params
        image = c.img_model
        return {
            "roi": list(c.roi) if c.roi is not None else None,
            "automaticBinning": c.integration_rad_points is None,
            "actualBins": int(c.calibration_model.num_points or 0),
            "supersampling": c.calibration_model.supersampling_factor,
            "azimuthRange": c.oned_azimuth_range,
            "cakeAzimuthRange": c.cake_azimuth_range,
            "cakeBins": c.cake_azimuth_points,
            "solidAngle": c.correct_solid_angle,
            "polarization": c.calibration_model.polarization_factor,
            "poissonErrors": c.calculate_poisson_errors,
            "trimZeros": c.trim_trailing_zeros,
            "autoSave": getattr(self, "_integration_auto_save", False),
            "formats": c.integrated_patterns_file_formats,
            "outputDirectory": c.working_directories["pattern"],
            "imageBackground": {
                "filename": image.background_filename
                if image.has_background()
                else None,
                "scale": image.background_scaling,
                "offset": image.background_offset,
            },
            "patternBackground": {
                "enabled": p.auto_bkg_enabled,
                "smoothing": p.auto_bkg_smoothing,
                "iterations": p.auto_bkg_iterations,
                "order": p.auto_bkg_poly_order,
                "range": p.auto_bkg_roi,
                "overlay": c.pattern_model.background_pattern is not None,
            },
            "flatField": {
                "filename": image.flat_field_correction.filename,
                "enabled": image.get_img_correction("flat_field") is not None,
            },
            "corrections": {
                key: {
                    "enabled": image.get_img_correction(key) is not None,
                    "parameters": self._integration_correction_parameters(
                        key, image.get_img_correction(key)
                    )
                    if image.get_img_correction(key)
                    else {k: v[1] for k, v in fields.items()},
                    "fields": {
                        k: {"label": v[0], "min": v[2], "max": v[3]}
                        for k, v in fields.items()
                    },
                }
                for key, (_, fields) in CORRECTIONS.items()
            },
            "overlayDirectory": self._model.working_directories["overlay"],
            "waterfallSeparation": self._model.view.waterfall_separation,
            "overlays": [
                {
                    "uid": o.params.uid,
                    "background": c.pattern_model.background_pattern is o,
                    "name": o.name,
                    "visible": o.visible,
                    "color": o.color,
                    "scale": o.scaling,
                    "offset": o.offset,
                }
                for o in self._model.overlay_model.overlays
            ],
            "sameConditions": self._model.phase_model.same_conditions,
            "phases": [
                {
                    "name": phase.name,
                    "pressure": phase.params["pressure"],
                    "temperature": phase.params["temperature"],
                    "visible": self._model.phase_model.phase_visible[i],
                    "color": "#%02x%02x%02x"
                    % tuple(int(v) for v in self._model.phase_model.phase_colors[i]),
                    "references": self._model.phase_model.get_eos_reference_labels(i),
                    "reference": phase.params["eos_current_index"],
                }
                for i, phase in enumerate(self._model.phase_model.phases)
            ],
            "batchFrames": int(c.batch_model.n_img or 0),
            "patternName": c.pattern_model.pattern.name,
            "originalPatternColor": c.pattern_model.params.color,
            "originalPatternVisible": c.pattern_model.params.visible,
            "patternPath": c.pattern_model.pattern_filename if c.pattern_model.pattern_source == "file" else "",
            "patternFileIteration": c.pattern_model.file_iteration_mode,
            "fileInfo": str(image.file_info),
            "fileIteration": image.file_iteration_mode,
            "imageDirectory": c.working_directories["image"],
            "autoProcess": getattr(self, "_integration_auto_process", False),
            "autoProcessError": getattr(self, "_integration_auto_process_error", ""),
            "frame": image.series_pos,
            "frames": image.series_max,
        }

    @staticmethod
    def _integration_correction_parameters(kind, correction):
        parameters = dict(correction.get_params())
        if kind == "cbn":
            parameters["cbn_abs_length"] = parameters.pop("seat_abs_length")
        return parameters

    def _refresh_integration_pattern(self):
        """Use PatternModel's displayed (background-subtracted) data, like Qt."""
        c = self.configuration
        x, y = c.pattern_model.pattern.data
        if not len(x) and not self._model.overlay_model.overlays:
            self._pattern = None
            return
        curves = []
        for overlay in self._model.overlay_model.overlays:
            if overlay.visible:
                ox, oy = overlay.data
                curves.append(
                    {
                        "name": overlay.name,
                        "color": overlay.color,
                        "x": np.asarray(ox).tolist(),
                        "y": values(oy),
                    }
                )
        phase_lines = []
        model = self._model.phase_model
        for i, phase in enumerate(model.phases):
            if not model.phase_visible[i]:
                continue
            positions = model.get_phase_line_positions(
                i, c.pattern_model.unit, c.calibration_model.wavelength * 1e10
            )
            color = "#%02x%02x%02x" % tuple(int(v) for v in model.phase_colors[i])
            for position, reflection in zip(positions, model.reflections[i]):
                if np.isfinite(position):
                    phase_lines.append(
                        {
                            "phaseIndex": i,
                            "x": float(position),
                            "intensity": float(reflection[1]),
                            "name": phase.name,
                            "color": color,
                            "hkl": [int(v) for v in reflection[2:5]],
                        }
                    )
        inspection = []
        background = c.pattern_model.pattern.auto_background_pattern
        if background is not None and c.pattern_model.params.auto_bkg_enabled:
            ox, oy = c.pattern_model.pattern.original_data
            bx, by = background.data
            inspection = [
                {"name": "Original pattern", "color": "#8196a6", "x": np.asarray(ox).tolist(), "y": values(oy)},
                {"name": "Fitted background", "color": "#73bba6", "x": np.asarray(bx).tolist(), "y": values(by)},
            ]
        self._pattern = {
            "x": np.asarray(x).tolist(),
            "y": values(y),
            "unit": c.pattern_model.unit,
            "curves": curves,
            "phaseLines": phase_lines,
            "backgroundCurves": inspection,
        }

    def _integration_save_image(self, **settings):
        from .image_export import save_image

        return save_image(self, **settings)

    def _integration_roi(self, limits=None):
        if not self._has_image:
            raise ValueError("Open an image first.")
        if limits is not None:
            if not isinstance(limits, list) or len(limits) != 4:
                raise ValueError("ROI needs row minimum/maximum and column minimum/maximum.")
            height, width = self.configuration.img_model.img_data.shape
            limits = [finite(v, "ROI limit", 0, height if i < 2 else width, True) for i, v in enumerate(limits)]
            if limits[0] >= limits[1] or limits[2] >= limits[3]:
                raise ValueError("ROI minimum must be below maximum.")
        self.configuration.roi = tuple(limits) if limits is not None else None
        self._calculate()
        return self._snapshot()

    def _integration_phase_guides(self):
        """Phase guides use the calibrated angular array, as the Qt image view does."""
        from skimage.measure import find_contours
        c = self.configuration
        if not self._has_image or not c.calibration_model.is_calibrated:
            return {"phaseGuides": []}
        angles = np.degrees(c.calibration_model.get_pixel_two_theta_array())
        step = max(1, math.ceil(max(angles.shape) / 512))
        sampled = angles[::step, ::step]
        guides = []
        phases = self._model.phase_model
        for i, phase in enumerate(phases.phases):
            if not phases.phase_visible[i]:
                continue
            color = "#%02x%02x%02x" % tuple(int(v) for v in phases.phase_colors[i])
            positions = phases.get_phase_line_positions(i, "2th_deg", c.calibration_model.wavelength * 1e10)
            intensities = np.asarray([reflection[1] for reflection in phases.reflections[i]], dtype=float)
            intensities = np.where(np.isfinite(intensities), np.maximum(intensities, 0), 0)
            maximum = float(np.max(intensities)) if intensities.size else 0
            for reflection_index, (position, intensity) in enumerate(zip(positions, intensities)):
                if not np.isfinite(position):
                    continue
                # Match CakePhasePlot.update_pen: stronger reflections are
                # thicker and more opaque, normalized independently per phase.
                scaling = float(intensity / maximum) if maximum > 0 else 0
                style = {"lineWidth": 1 + 3 * scaling, "opacity": 0.3 + 0.4 * scaling}
                contours = [[[float(x * step), float(y * step)] for y, x in line[::2]]
                            for line in find_contours(sampled, float(position))]
                for points in contours:
                    guides.append({"ring": 0, "twoTheta": float(position), "color": color, "points": points,
                                   "phaseIndex": i, "reflectionIndex": reflection_index, **style})
        return {"phaseGuides": guides}

    def _integration_settings(self, **changes):
        c = self.configuration
        validated = {}
        for key, value in changes.items():
            if key == "unit":
                if value not in {"2th_deg", "q_A^-1", "d_A"}:
                    raise ValueError("Unsupported integration unit.")
            elif key == "bins":
                value = (
                    None
                    if value is None
                    else finite(value, "Radial bins", 1, 100000, True)
                )
            elif key == "supersampling":
                value = finite(value, "Supersampling", 1, 20, True)
            elif key == "cake_bins":
                value = finite(value, "Cake azimuth bins", 1, 10000, True)
            elif key in {"azimuth_range", "cake_azimuth_range"}:
                value = optional_range(value)
            elif key == "polarization":
                value = finite(value, "Polarization", -1, 1)
            elif key in {"solid_angle", "poisson_errors", "trim_zeros", "auto_save"}:
                value = boolean(value, key)
            elif key == "formats":
                if (
                    not isinstance(value, list)
                    or not value
                    or any(
                        v not in {".xy", ".xye", ".chi", ".dat", ".fxye"} for v in value
                    )
                ):
                    raise ValueError("Choose at least one supported pattern format.")
            else:
                raise ValueError(f"Unknown integration option: {key}")
            validated[key] = value
        errors = validated.get("poisson_errors", c.calculate_poisson_errors)
        formats = validated.get("formats", c.integrated_patterns_file_formats)
        if any(f in {".xye", ".fxye"} for f in formats) and not errors:
            raise ValueError("Enable Calculate Poisson errors for XYE/FXYE output.")
        previous_unit = c.integration_unit
        background_range = c.pattern_model.params.auto_bkg_roi
        if "unit" in validated and background_range is not None:
            converted = convert_units(
                np.asarray(background_range), c.calibration_model.wavelength,
                previous_unit, validated["unit"],
            )
            if not np.all(np.isfinite(converted)):
                raise ValueError("Background range cannot be converted to this radial coordinate.")
            background_range = sorted(converted.tolist())
        background_params = c.pattern_model.params
        restore_background = (
            validated.get("unit", previous_unit) != previous_unit
            and background_params.auto_bkg_enabled
        )
        if restore_background:
            # xypattern transforms to descending d before the fresh integration.
            # Suspend extraction across that intermediate state; restore the same
            # parameters after the new, ascending radial samples are available.
            c.pattern_model.unset_auto_background_subtraction()
        try:
            for key, value in validated.items():
                if key == "auto_save":
                    self._integration_auto_save = value
                elif key == "supersampling":
                    c.calibration_model.set_supersampling(value)
                    if c.is_calibrated:
                        c.calibration_model.create_cake_geometry()
                elif key == "polarization":
                    c.calibration_model.polarization_factor = value
                else:
                    name = {
                        "unit": "integration_unit",
                        "bins": "integration_rad_points",
                        "cake_bins": "cake_azimuth_points",
                        "azimuth_range": "oned_azimuth_range",
                        "solid_angle": "correct_solid_angle",
                        "poisson_errors": "calculate_poisson_errors",
                        "trim_zeros": "trim_trailing_zeros",
                        "formats": "integrated_patterns_file_formats",
                    }.get(key, key)
                    setattr(c, name, value)
            if "unit" in validated and background_range is not None:
                c.pattern_model.params.auto_bkg_roi = background_range
            if (
                set(validated) - {"auto_save", "formats"}
                and self._has_image
                and c.is_calibrated
            ):
                self._calculate()
            else:
                self._revision += 1
                self._refresh_integration_pattern()
        finally:
            if restore_background:
                x, y = c.pattern_model.pattern.original_data
                if len(x) > 1 and np.any(np.diff(x) < 0):
                    order = np.argsort(x)
                    scale, offset = c.pattern_model.pattern.scaling, c.pattern_model.pattern.offset
                    c.pattern_model.pattern.data = (x[order], y[order])
                    c.pattern_model.pattern.scaling = scale
                    c.pattern_model.pattern.offset = offset
                c.pattern_model.set_auto_background_subtraction(
                    [background_params.auto_bkg_smoothing, background_params.auto_bkg_iterations, background_params.auto_bkg_poly_order],
                    c.pattern_model.params.auto_bkg_roi,
                )
                self._refresh_integration_pattern()
        return self._snapshot()

    def _integration_image_background(
        self, path=None, reset=False, scale=None, offset=None
    ):
        if not self._has_image:
            raise ValueError("Open an image first.")
        image = self.configuration.img_model
        if reset:
            image.reset_background()
        elif scale is None and offset is None:
            path = self._path(path, "image")
            if path is None:
                return {"cancelled": True}
            # Validate using a separate model so a bad shape cannot discard the
            # user's existing background (the Qt loader resets it on mismatch).
            from dioptas.model.ImgModel import ImgModel

            candidate = ImgModel()
            candidate.load(path)
            if candidate.raw_img_data.shape != image.untransformed_raw_img_data.shape:
                raise ValueError("Background image must have the same detector shape.")
            image.load_background(path)
        new_scale = (
            image.background_scaling
            if scale is None
            else finite(scale, "Background scale")
        )
        new_offset = (
            image.background_offset
            if offset is None
            else finite(offset, "Background offset")
        )
        image.background_scaling = new_scale
        image.background_offset = new_offset
        self._calculate()
        return self._snapshot(include_image=True)

    def _integration_reset_autoprocess(self):
        # This watcher is polled by desktop commands on the processing worker;
        # it never starts its own thread or invokes science from a callback.
        self._integration_auto_process = False
        self._integration_auto_process_error = ""
        self._integration_file_watcher = None
        self._integration_incoming = deque()

    def _integration_watch_directory(self, directory):
        watcher = NewFileInDirectoryWatcher(
            directory,
            file_types=list(self.configuration.img_model._directory_watcher.file_types),
        )
        self._integration_incoming = deque()
        watcher.file_added.connect(self._integration_incoming.append)
        watcher._take_baseline()
        self._integration_file_watcher = watcher

    def _integration_image_directory(self, path=None):
        if path is None:
            if self._choose_file is None:
                raise ValueError("Choose an image directory in the desktop application.")
            path = self._choose_file("directory", False)
        if not path:
            return {"cancelled": True}
        directory = Path(path).expanduser().resolve()
        if not directory.is_dir():
            raise ValueError(f"Image directory does not exist: {directory}")
        previous = self.configuration.working_directories["image"]
        if str(directory) != previous:
            self.configuration.working_directories["image"] = str(directory)
            self._integration_auto_process_error = ""
            if getattr(self, "_integration_auto_process", False):
                self._integration_watch_directory(str(directory))
        return self._state()

    def _integration_autoprocess(self, enabled, directory=None):
        enabled = boolean(enabled, "Autoprocess")
        if enabled:
            if directory is not None:
                self._integration_image_directory(path=directory)
            directory = self.configuration.working_directories["image"]
            if not Path(directory).is_dir():
                raise ValueError("Choose an existing image directory first.")
            if not getattr(self, "_integration_auto_process", False):
                self._integration_watch_directory(directory)
            self._integration_auto_process = True
            self._integration_auto_process_error = ""
        else:
            self._integration_reset_autoprocess()
        return self._state()

    def _integration_autoprocess_poll(self):
        if not getattr(self, "_integration_auto_process", False):
            return {}
        self._integration_file_watcher.poll_once()
        if not self._integration_incoming:
            return {}
        path = self._integration_incoming.popleft()
        try:
            result = self._open_image(path=path)
            self._integration_image_loaded()
        except Exception as exc:
            # A bad image must not block the remaining acquisition queue.
            self._integration_auto_process_error = f"{Path(path).name}: {exc}"
            return self._snapshot(include_image=True)
        self._integration_auto_process_error = ""
        return result

    def _integration_navigation(self, mode=None, frame=None):
        image = self.configuration.img_model
        if mode is not None:
            if mode not in {"number", "time"}:
                raise ValueError("Choose filename number or creation time navigation.")
            image.set_file_iteration_mode(mode)
        if frame is not None:
            if not self._has_image:
                raise ValueError("Open an image first.")
            frame = finite(frame, "Frame", 1, image.series_max, True)
            image.load_series_img(frame)
            self.configuration.calibration_model.clear_peaks()
            self._fit_rms = None
            self._calculate()
            self._integration_image_loaded()
            return self._snapshot(include_image=True)
        return self._state()

    def _integration_clear_background(self):
        from .overlay import set_background

        set_background(self, None)
        self._refresh_integration_pattern()
        self._revision += 1
        return self._snapshot()

    def _integration_background(
        self, enabled, smoothing=None, iterations=None, order=None, range=...
    ):
        model = self.configuration.pattern_model
        boolean(enabled, "Background enabled")
        if smoothing is None:
            smoothing = 0.1 if enabled else model.params.auto_bkg_smoothing
        if iterations is None:
            iterations = 150 if enabled else model.params.auto_bkg_iterations
        if order is None:
            order = 50 if enabled else model.params.auto_bkg_poly_order
        if range is ...:
            range = None if enabled else model.params.auto_bkg_roi
        smoothing = finite(smoothing, "Smooth width", 0.000001, 1e7)
        iterations = finite(iterations, "Iterations", 1, 99999, True)
        order = finite(order, "Order", 1, 1000, True)
        if range is not None:
            if not isinstance(range, list) or len(range) != 2:
                raise ValueError("Background range needs two values.")
            range = [finite(v, "Background range") for v in range]
            if range[0] >= range[1]:
                raise ValueError("Background minimum must be below maximum.")
        if enabled:
            if self._pattern is None:
                raise ValueError("Load or integrate a pattern first.")
            model.set_auto_background_subtraction([smoothing, iterations, order], range)
        else:
            model.unset_auto_background_subtraction()
            # Retain automatic control edits while subtraction is switched off.
            # The disabled model emits updates without extracting a background.
            model.params.auto_bkg_smoothing = smoothing
            model.params.auto_bkg_iterations = iterations
            model.params.auto_bkg_poly_order = order
            model.params.auto_bkg_roi = model._clamped_roi(range)
        self._refresh_integration_pattern()
        self._revision += 1
        return self._snapshot()

    def _integration_flat_field(self, path=None, enabled=True, reset=False):
        image = self.configuration.img_model
        if not self._has_image:
            raise ValueError("Open an image first.")
        boolean(enabled, "Flat field enabled")
        if reset or not enabled:
            image.disable_flat_field()
            if reset:
                image.flat_field_correction.reset()
        else:
            if path is not None or image.flat_field_correction.data is None:
                path = self._path(path, "image")
                if path is None:
                    return {"cancelled": True}
                correction = FlatFieldCorrection(path, image.img_transformations)
                if correction.shape() != image.img_data.shape:
                    raise ValueError("Flat field must have the same detector shape.")
                if not np.all(np.isfinite(correction.data)) or np.any(
                    correction.data <= 0
                ):
                    raise ValueError(
                        "Flat field must contain finite, positive response factors."
                    )
                image.disable_flat_field()
                image.flat_field_correction = correction
            image.enable_flat_field()
        self._calculate()
        return self._snapshot(include_image=True)

    def _integration_correction(self, kind, enabled, parameters=None):
        if kind not in CORRECTIONS:
            raise ValueError("Unsupported correction.")
        boolean(enabled, "Correction enabled")
        c = self.configuration
        if enabled:
            if not self._has_image or not c.is_calibrated:
                raise ValueError("Load an image and calibration first.")
            factory, fields = CORRECTIONS[kind]
            parameters = parameters or {}
            if any(key not in fields for key in parameters):
                raise ValueError("Unknown correction parameter.")
            params = {
                key: finite(parameters.get(key, data[1]), data[0], data[2], data[3])
                for key, data in fields.items()
            }
            if (
                kind == "cbn"
                and params["small_cbn_seat_radius"] > params["large_cbn_seat_radius"]
            ):
                raise ValueError("Small seat radius must not exceed large seat radius.")
            correction = self._integration_build_correction(kind, params)
            shape = c.img_model.img_data.shape
            data = correction.get_data()
            if (
                data.shape != shape
                or not np.all(np.isfinite(data))
                or np.any(data <= 0)
            ):
                raise ValueError(
                    "Correction is not finite and positive across this detector."
                )
            c.img_model.add_img_correction(correction, kind)
        elif c.img_model.get_img_correction(kind) is not None:
            c.img_model.delete_img_correction(kind)
        self._calculate()
        return self._snapshot(include_image=True)

    def _integration_build_correction(self, kind, parameters):
        calibration = self.configuration.calibration_model
        shape = self.configuration.img_model.img_data.shape
        geometry = calibration.pattern_geometry
        rows, columns = np.indices(shape, dtype=float)
        factor = calibration.supersampling_factor
        tth = calibration.get_pixel_two_theta_array()
        azi = geometry.chi((rows + 0.5) * factor - 0.5, (columns + 0.5) * factor - 0.5)
        # The existing Qt controller passes degrees to cBN and radians to
        # OIADAC. Its project reconstructor currently uses degrees for both;
        # normalize here so desktop saves reopen with the applied correction.
        if kind == "cbn":
            tth, azi = np.rad2deg(tth), np.rad2deg(azi)
        correction = CORRECTIONS[kind][0](tth_array=tth, azi_array=azi, **parameters)
        correction.update()
        correction._desktop_geometry_key = self._integration_geometry_key()
        return correction

    def _integration_geometry_key(self):
        calibration = self.configuration.calibration_model
        geometry = calibration.pattern_geometry
        return (
            self.configuration.img_model.img_data.shape,
            calibration.supersampling_factor,
            *(
                getattr(geometry, key)
                for key in ("dist", "poni1", "poni2", "rot1", "rot2", "rot3")
            ),
            calibration.orig_pixel1,
            calibration.orig_pixel2,
            calibration.distortion_spline_filename,
        )

    def _integration_prepare_corrections(self):
        image = self.configuration.img_model
        key = self._integration_geometry_key()
        for kind in CORRECTIONS:
            existing = image.get_img_correction(kind)
            if (
                existing is not None
                and getattr(existing, "_desktop_geometry_key", None) != key
            ):
                parameters = self._integration_correction_parameters(kind, existing)
                correction = self._integration_build_correction(kind, parameters)
                image.add_img_correction(correction, kind)

    def _integration_overlay(self, operation, index=None, path=None, paths=None, **changes):
        from .overlay import update_overlay

        return update_overlay(self, operation, index, path, paths, **changes)

    @staticmethod
    def _integration_color(value):
        import re

        if (
            not isinstance(value, str)
            or re.fullmatch(r"#[0-9a-fA-F]{6}", value) is None
        ):
            raise ValueError("Choose a hexadecimal RGB color.")
        return value

    def _integration_phase(self, operation, index=None, path=None, **changes):
        model = self._model.phase_model
        if operation == "load":
            path = self._path(path, "phase")
            if path is None:
                return {"cancelled": True}
            if Path(path).suffix.lower() == ".cif":
                model.add_cif(
                    path,
                    wavelength_angstrom=self.configuration.calibration_model.wavelength
                    * 1e10,
                )
            elif Path(path).suffix.lower() in {".eosmat", ".json"}:
                from dioptas.model.eos import load_material_file, build_jcpds

                model.add_jcpds_object(
                    build_jcpds(
                        load_material_file(path),
                        wavelength_angstrom=self.configuration.calibration_model.wavelength
                        * 1e10,
                        origin="file",
                    ),
                    filename=path,
                )
            else:
                model.add_jcpds(path)
        elif operation == "same_conditions":
            model.same_conditions = boolean(changes["enabled"], "Same conditions")
        elif operation == "clear":
            model.reset()
        else:
            index = finite(index, "Phase index", 0, len(model.phases) - 1, True)
            if operation == "remove":
                model.del_phase(index)
            elif operation == "update":
                for key, value in changes.items():
                    if key in {"pressure", "temperature"}:
                        value = finite(
                            value, key, -100 if key == "pressure" else 0, 10000
                        )
                        if not getattr(model, "set_" + key)(index, value):
                            raise ValueError(f"Phase model rejected {key} {value:g}.")
                    elif key == "reference":
                        value = finite(
                            value,
                            key,
                            0,
                            len(model.get_eos_reference_labels(index)) - 1,
                            True,
                        )
                        if not model.set_eos_reference(index, value):
                            raise ValueError("Phase model rejected this reference.")
                    elif key == "visible":
                        model.set_phase_visible(index, boolean(value, key))
                    elif key == "color":
                        color = self._integration_color(value)
                        model.set_color(
                            index, tuple(int(color[i : i + 2], 16) for i in (1, 3, 5))
                        )
                    else:
                        raise ValueError("Unknown phase option.")
            else:
                raise ValueError("Unknown phase operation.")
        self._refresh_integration_pattern()
        self._revision += 1
        return self._snapshot()

    def _integration_autocreate(self, enabled, directory=None):
        enabled = boolean(enabled, "Autocreate")
        if enabled and directory:
            self._integration_output_directory(path=directory)
        return self._integration_settings(auto_save=enabled)

    def _integration_pattern_navigation(self, mode):
        if mode not in {"number", "time"}:
            raise ValueError("Choose filename number or creation time navigation.")
        self.configuration.pattern_model.set_file_iteration_mode(mode)
        return self._state()

    def _integration_open_pattern(self, path=None, direction=None, step=1, directory=None):
        model = self.configuration.pattern_model
        if direction is not None:
            if direction not in {-1, 1}:
                raise ValueError("Pattern direction must be -1 or 1.")
            step = finite(step, "Pattern file step", 1, 100000, True)
            if model.pattern_source != "file":
                raise ValueError("Load a pattern file before browsing files.")
            (model.load_next_file if direction == 1 else model.load_previous_file)(step=step)
        else:
            if path and directory and not Path(path).expanduser().is_absolute():
                path = str(Path(directory).expanduser() / path)
            path = self._path(path, "pattern")
            if path is None:
                return {"cancelled": True}
            model.load_pattern(path)
        self.configuration.working_directories["pattern"] = str(Path(model.pattern_filename).resolve().parent)
        model.unit = self.configuration.integration_unit
        self._refresh_integration_pattern()
        self._revision += 1
        return self._snapshot()

    def _integration_save_pattern(self, path=None, subtract_background=False):
        if self._pattern is None:
            raise ValueError("Load or integrate a pattern first.")
        path = self._path(path, "pattern", save=True)
        if path is None:
            return {"cancelled": True}
        if not Path(path).suffix:
            path += ".xy"
        suffix = Path(path).suffix.lower()
        if suffix not in {".xy", ".xye", ".chi", ".dat", ".fxye"}:
            raise ValueError("Use XY, XYE, CHI, DAT or FXYE format.")
        if (
            suffix in {".xye", ".fxye"}
            and self.configuration.pattern_model.errors is None
        ):
            raise ValueError(
                "Enable Calculate Poisson errors and integrate before saving errors."
            )
        self.configuration.save_pattern(
            path,
            subtract_background=boolean(subtract_background, "Subtract background"),
        )
        return {"savedPath": path}

    def _integration_save_background(self, path=None):
        if not self.configuration.pattern_model.params.auto_bkg_enabled:
            raise ValueError("Enable pattern background first.")
        path = self._path(path, "pattern", save=True)
        if path is None:
            return {"cancelled": True}
        if not Path(path).suffix:
            path += ".xy"
        if Path(path).suffix.lower() not in {".xy", ".chi", ".dat"}:
            raise ValueError(
                "Save background as XY, CHI or DAT; it has no propagated Poisson errors."
            )
        self.configuration.pattern_model.save_auto_background_as_pattern(
            path, header="Dioptas automatic background"
        )
        return {"savedPath": path}

    def _integration_output_directory(self, path=None):
        if path is None:
            if self._choose_file is None:
                raise ValueError("Choose an output folder in the desktop application.")
            path = self._choose_file("directory", False)
        if not path:
            return {"cancelled": True}
        path = Path(path).expanduser().resolve()
        if not path.is_dir():
            raise ValueError("Choose an existing output folder.")
        self.configuration.working_directories["pattern"] = str(path)
        return self._state()

    def _integration_batch(self, path=None):
        c = self.configuration
        if not self._has_image or not c.is_calibrated:
            raise ValueError("Load an image and calibration first.")
        if path is None:
            if self._choose_file is None:
                raise ValueError("Choose an input folder in the desktop application.")
            path = self._choose_file("directory", False)
        if not path:
            return {"cancelled": True}
        folder = Path(path).expanduser().resolve()
        if not folder.is_dir():
            raise ValueError("Choose an input folder.")
        suffix = Path(c.img_model.filename).suffix.lower()
        files = sorted(
            str(p)
            for p in folder.iterdir()
            if p.is_file() and p.suffix.lower() == suffix
        )
        if not files:
            raise ValueError(f"No {suffix} images in this folder.")
        original, frame = c.img_model.filename, c.img_model.series_pos
        self._cancel_refinement.clear()
        self._progress = {"running": True, "current": 0, "total": len(files)}
        previous = {
            key: deepcopy(value)
            for key, value in c.batch_model.__dict__.items()
            if key != "configuration"
        }
        try:
            expected_shape = c.img_model.untransformed_raw_img_data.shape
            for index, filename in enumerate(files):
                if self._cancel_refinement.is_set():
                    return {**self._snapshot(), "cancelled": True}
                frame_data = c.img_model.get_image_data(filename)
                if frame_data is None or frame_data["img_data"].shape != expected_shape:
                    raise ValueError(
                        f"Batch image must have the current detector shape: {Path(filename).name}"
                    )
                self._progress = {
                    "running": True,
                    "current": index + 1,
                    "total": len(files),
                }
            c.batch_model.set_image_files(files)
            total = c.batch_model.n_img_all
            self._progress["total"] = total

            def progress(current):
                self._progress = {"running": True, "current": current, "total": total}
                return not self._cancel_refinement.is_set()

            wrapped = self._integration_wrapped(c.oned_azimuth_range)
            if wrapped:
                c.calibration_model.pattern_geometry.reset()
                c.calibration_model.pattern_geometry.setChiDiscAtZero()
            try:
                c.batch_model.integrate_raw_data(
                    0, total, 1, use_all=True, callback_fn=progress
                )
            finally:
                if wrapped:
                    c.calibration_model.pattern_geometry.setChiDiscAtPi()
                    c.calibration_model.pattern_geometry.reset()
            cancelled = self._cancel_refinement.is_set()
            if cancelled:
                # Preserve the previous complete batch; partial output has not
                # been published or silently saved to disk.
                c.batch_model.__dict__.update(previous)
        except Exception:
            c.batch_model.__dict__.update(previous)
            raise
        finally:
            c.img_model.blockSignals(False)
            c.img_model.load(original)
            if frame > 0:
                c.img_model.load_series_img(frame)
            self._progress["running"] = False
            self._calculate()
        return {**self._snapshot(include_image=True), "cancelled": cancelled}

    def _integration_save_batch(self, path=None):
        batch = self.configuration.batch_model
        if batch.data is None:
            raise ValueError("Integrate a folder first.")
        path = self._path(path, "batch", save=True)
        if path is None:
            return {"cancelled": True}
        if Path(path).suffix.lower() == ".csv":
            batch.save_as_csv(path)
        else:
            if not Path(path).suffix:
                path += ".h5"
            batch.save_proc_data(path)
        return {"savedPath": path}

    def _integration_image_loaded(self):
        """Keep the image working directory and Qt autocreate in sync."""
        directory = str(Path(self.configuration.img_model.filename).resolve().parent)
        if directory != self.configuration.working_directories["image"]:
            self._integration_image_directory(path=directory)
        if getattr(self, "_integration_auto_save", False) and self._pattern is not None:
            self.configuration._auto_save_patterns()
