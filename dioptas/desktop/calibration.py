# SPDX-License-Identifier: MIT
"""Calibration workflow commands shared by the React controls and tests."""

from __future__ import annotations

import copy
import math
import threading
import tempfile
from pathlib import Path

import numpy as np
from skimage.measure import find_contours

from dioptas.model.util.calc import convert_units
from dioptas.model.CalibrationGuide import compute_guide_state, Step


def finite(value, label, low=-1e6, high=1e6):
    result = float(value)
    if not math.isfinite(result) or not low <= result <= high:
        raise ValueError(f"{label} must be between {low:g} and {high:g}.")
    return result


class CalibrationWorkflow:
    def _init_workflow(self):
        self._inspection = None
        self._workflow = {
            "autoIncrement": True,
            "searchSize": 10,
            "automaticRefinement": True,
            "algorithm": "Massif",
            "deltaTth": 0.1,
            "meanFactor": 3.0,
            "intensityLimit": 55000.0,
            "numberOfRings": 15,
        }
        self._cancel_refinement = threading.Event()
        self._progress = {"running": False, "current": 0, "total": 0}
        self._custom_calibrant = None
        self._geometry_source = "none"
        self._setup_confirmed = False
        self._calibrant_directory = None

    def _calibration_details(self):
        c = self.configuration.calibration_model
        pyfai, fit2d = c.get_calibration_parameter()
        guide = compute_guide_state(self._model)
        values = {
            "dist": c.start_values["dist"] * 1000,
            "wavelength": c.start_values["wavelength"] * 1e10,
            **{
                key: float(getattr(c.pattern_geometry, key))
                * (1000 if key.startswith("poni") else 1)
                for key in ("poni1", "poni2", "rot1", "rot2", "rot3")
            },
        }
        for key, value in c.fixed_values.items():
            values[key] = value * (1000 if key in ("dist", "poni1", "poni2") else 1)
        parameters = {
            key: {
                "value": value,
                "refine": c.fit_wavelength
                if key == "wavelength"
                else key not in c.fixed_values,
            }
            for key, value in values.items()
        }
        return {
            "referenceLines": [
                {
                    "ring": i + 1,
                    "x": float(
                        convert_units(
                            float(angle) * 180 / np.pi,
                            c.pattern_geometry.wavelength,
                            "2th_deg",
                            self.configuration.integration_unit,
                        )
                    ),
                }
                for i, angle in enumerate(c.calibrant.get_2th())
                if angle is not None and np.isfinite(angle)
            ],
            "setupConfirmed": self._setup_confirmed,
            "detectorIsCustom": c.params.detector_mode == 1,
            "workflow": self._workflow.copy(),
            "parameters": parameters,
            "freeParameterCount": sum(p["refine"] for p in parameters.values()),
            "polarization": c.polarization_factor,
            "fitWavelength": c.fit_wavelength,
            "detectorFile": c.params.detector_filename
            if c.params.detector_mode == 2
            else None,
            "distortionFile": c.distortion_spline_filename,
            "transformations": list(
                self.configuration.img_model.params.transformations
            ),
            "pyfai": {
                key: float(value)
                for key, value in pyfai.items()
                if isinstance(value, (int, float, np.number))
            },
            "fit2d": {
                key: float(value)
                for key, value in (fit2d or {}).items()
                if isinstance(value, (int, float, np.number))
            },
            "steps": [
                guide.step_status[step].name.lower()
                for step in (Step.IMAGE, Step.PEAKS, Step.CALIBRATE, Step.VALIDATE)
            ],
            "geometrySource": self._geometry_source,
            "canUndo": self._model.history.can_undo,
            "canRedo": self._model.history.can_redo,
        }

    def _calibrant_names(self):
        from dioptas import calibrants_path

        names = sorted(p.stem for p in Path(calibrants_path).glob("*.D"))
        if self._custom_calibrant:
            names.append(self._custom_calibrant["name"])
        return names

    def _install_custom_calibrant(self, name, content):
        from pyFAI.calibrant import Calibrant

        if len(content.encode("utf-8")) > 1024 * 1024:
            raise ValueError("Calibrant files must be smaller than 1 MiB.")
        directory = tempfile.TemporaryDirectory(prefix="dioptas-calibrant-")
        path = Path(directory.name) / "reference.D"
        path.write_text(content, encoding="utf-8")
        candidate = Calibrant()
        candidate.load_file(str(path))
        spacings = np.asarray(candidate.dSpacing, dtype=float)
        if (
            not len(spacings)
            or not np.all(np.isfinite(spacings))
            or np.any(spacings <= 0)
        ):
            directory.cleanup()
            raise ValueError("The reference needs finite positive d spacings in Å.")
        self._calibrant_directory = directory
        self._custom_calibrant = {"name": name, "content": content, "path": str(path)}

    def _validation_calibrant(self, calibrant):
        if calibrant not in self._calibrant_names():
            raise ValueError("Choose an available calibrant.")
        c = self.configuration.calibration_model
        self._calibrant_name = calibrant
        self._set_calibrant()
        if c.is_calibrated:
            c.calibrant.setWavelength_change2th(c.pattern_geometry.wavelength)
            self._rings = []
            if self._has_image:
                self._update_rings()
        # This changes the displayed reference, not the geometry. The previous
        # residual no longer describes the currently selected reference.
        self._fit_rms = None
        return self._snapshot()

    def _open_calibrant(self, path=None, validation=False):
        path = self._path(path, "calibrant")
        if path is None:
            return {"cancelled": True}
        content = Path(path).read_text(encoding="utf-8")
        name = Path(path).stem + " (custom)"
        self._install_custom_calibrant(name, content)
        if validation:
            return self._validation_calibrant(name)
        self._calibrant_name = name
        self._set_calibrant()
        self._fit_dirty = self.configuration.calibration_model.is_calibrated
        self._fit_rms = None
        return self._state()

    def _workflow_settings(self, **settings):
        updated = self._workflow.copy()
        for name, value in settings.items():
            if name in ("autoIncrement", "automaticRefinement"):
                if not isinstance(value, bool):
                    raise ValueError(f"{name} must be a boolean.")
            elif name == "algorithm":
                if value not in ("Massif", "Blob"):
                    raise ValueError("Choose Massif or Blob peak search.")
            elif name in ("searchSize", "numberOfRings"):
                value = finite(value, name, 1, 1000 if name == "searchSize" else 100)
                if value != int(value):
                    raise ValueError(f"{name} must be an integer.")
                value = int(value)
            elif name in ("deltaTth", "meanFactor", "intensityLimit"):
                value = finite(value, name, 0.00001, 1e15)
            else:
                raise ValueError(f"Unknown calibration setting: {name}")
            updated[name] = value
        self._workflow = updated
        return self._state()

    def _fit_parameters(self, parameters, polarization=None):
        c = self.configuration.calibration_model
        valid = {"dist", "wavelength", "poni1", "poni2", "rot1", "rot2", "rot3"}
        if set(parameters) - valid:
            raise ValueError("Unknown fit parameter.")
        values = c.start_values.copy()
        fixed = c.fixed_values.copy()
        fit_wavelength = c.fit_wavelength
        for key, entry in parameters.items():
            if not isinstance(entry.get("refine"), bool):
                raise ValueError("Each parameter needs a refine checkbox value.")
            low, high = (
                (0.01, 10)
                if key == "wavelength"
                else (1, 10000)
                if key == "dist"
                else (-1e5, 1e5)
                if key.startswith("poni")
                else (-2 * math.pi, 2 * math.pi)
            )
            value = finite(entry["value"], key, low, high)
            value *= (
                1e-10
                if key == "wavelength"
                else 0.001
                if key in ("dist", "poni1", "poni2")
                else 1
            )
            if key in ("dist", "wavelength"):
                values[key] = value
            if key == "wavelength":
                fit_wavelength = entry["refine"]
            elif entry["refine"]:
                fixed.pop(key, None)
            else:
                fixed[key] = value
        if polarization is not None:
            values["polarization_factor"] = finite(polarization, "Polarization", -1, 1)
        c.set_start_values(values)
        c.set_fixed_values(fixed)
        c.fit_wavelength = fit_wavelength
        # Confirm complete start values here; the Image step only applies pixels.
        if set(parameters) == valid:
            self._setup_confirmed = True
        c.calibrant.setWavelength_change2th(values["wavelength"])
        self._fit_dirty = c.is_calibrated
        self._fit_rms = None
        return self._state()

    def _reassign_pick(self, index, ring):
        c = self.configuration.calibration_model
        index = int(finite(index, "Selection index", 0, len(c.points) - 1))
        ring = int(finite(ring, "Ring number", 1, len(c.calibrant.get_2th())))
        c.set_peak_selection_ring(index, ring - 1)
        self._fit_dirty = True
        self._fit_rms = None
        return self._state()

    def _remove_picks(self, indices):
        c = self.configuration.calibration_model
        validated = [
            int(finite(i, "Selection index", 0, len(c.points) - 1)) for i in indices
        ]
        for index in sorted(set(validated), reverse=True):
            c.remove_peak_selection(index)
        self._fit_dirty = True
        self._fit_rms = None
        return self._state()

    def _history_step(self, redo=False):
        history = self._model.history
        overlay_only = (history.redo_label if redo else history.undo_label) == "integration_overlay"
        if redo:
            self._model.history.redo()
        else:
            self._model.history.undo()
        self._disable_automatic_processing(self._model)
        if overlay_only:
            self._refresh_integration_pattern()
            self._revision += 1
            return {**self._state(), "pattern": self._pattern, "patternOnly": True}
        c = self.configuration.calibration_model
        c.use_dioptrin = self._engine.id == "dioptrin"
        if c.is_calibrated:
            c.create_cake_geometry()
        self._fit_rms = None
        self._fit_dirty = bool(c.points)
        self._calculate()
        # Standalone pattern/overlay files remain displayable without detector geometry.
        if not self._has_image or self.configuration.pattern_model.pattern_source == "file":
            self._refresh_integration_pattern()
        result = self._snapshot(include_image=True)
        if self._workflow["autoIncrement"]:
            result["nextRing"] = max(c.points_index, default=-1) + 2
        return result

    def _image_transform(self, operation):
        if not self._has_image:
            raise ValueError("Open an image first.")
        c, image = self.configuration.calibration_model, self.configuration.img_model
        operations = {
            "rotate_left": (c.rotate_detector_m90, image.rotate_img_m90),
            "rotate_right": (c.rotate_detector_p90, image.rotate_img_p90),
            "flip_horizontal": (
                c.flip_detector_horizontally,
                image.flip_img_horizontally,
            ),
            "flip_vertical": (c.flip_detector_vertically, image.flip_img_vertically),
            "reset": (c.reset_transformations, image.reset_transformations),
        }
        if operation not in operations:
            raise ValueError("Unknown image transformation.")
        # Keep the user mask attached to the same source pixels across transforms.
        from dioptas.model.ImgModel import TRANSFORMATION_FUNCTIONS
        mask = self.configuration.mask_model.get_img().copy()
        if operation == "reset":
            inverse = {"rotate_matrix_p90": "rotate_matrix_m90", "rotate_matrix_m90": "rotate_matrix_p90"}
            for name in reversed(image.params.transformations):
                mask = TRANSFORMATION_FUNCTIONS[inverse.get(name, name)](mask)
        else:
            name = {"rotate_left": "rotate_matrix_m90", "rotate_right": "rotate_matrix_p90",
                    "flip_horizontal": "fliplr", "flip_vertical": "flipud"}[operation]
            mask = TRANSFORMATION_FUNCTIONS[name](mask)
        for transform in operations[operation]:
            transform()
        self.configuration.mask_model.set_mask_data(mask.copy())
        self.configuration._update_plugin_masks()
        c.clear_peaks()
        self._fit_rms = None
        self._fit_dirty = c.is_calibrated
        self._calculate()
        return self._snapshot(include_image=True)

    def _next_image(self, direction=1, step=1):
        if not self._has_image:
            raise ValueError("Open an image first.")
        if direction not in (-1, 1):
            raise ValueError("Image direction must be -1 or 1.")
        step = int(finite(step, "File step", 1, 100000))
        image = self.configuration.img_model
        (image.load_next_file if direction == 1 else image.load_previous_file)(
            step=step
        )
        self.configuration.calibration_model.clear_peaks()
        self._fit_rms = None
        self._calculate()
        return self._snapshot(include_image=True)

    def _detector_file(self, path=None, reset=False):
        c = self.configuration.calibration_model
        if reset:
            c.reset_detector()
        else:
            path = self._path(path, "detector")
            if path is None:
                return {"cancelled": True}
            c.load_detector_from_file(path)
        self._fit_dirty = c.is_calibrated
        self._fit_rms = None
        return self._state()

    def _distortion_file(self, path=None, reset=False):
        c = self.configuration.calibration_model
        if reset:
            c.reset_distortion_correction()
        else:
            path = self._path(path, "distortion")
            if path is None:
                return {"cancelled": True}
            c.load_distortion(path)
        c._sync_calibration_params()
        self._fit_dirty = c.is_calibrated
        self._fit_rms = None
        return self._state()

    def _manual_geometry(self, convention, values):
        c = self.configuration.calibration_model
        if convention == "pyfai":
            required = {
                "dist",
                "poni1",
                "poni2",
                "rot1",
                "rot2",
                "rot3",
                "pixel1",
                "pixel2",
                "wavelength",
                "polarization_factor",
            }
        elif convention == "fit2d":
            required = {
                "directDist",
                "centerX",
                "centerY",
                "tilt",
                "tiltPlanRotation",
                "pixelX",
                "pixelY",
                "wavelength",
                "polarization_factor",
            }
        else:
            raise ValueError("Choose pyFAI or Fit2D parameters.")
        if set(values) != required:
            raise ValueError("Complete every geometry field before applying.")
        parsed = {key: finite(value, key, -1e8, 1e8) for key, value in values.items()}
        for key in required & {
            "dist",
            "directDist",
            "pixel1",
            "pixel2",
            "pixelX",
            "pixelY",
            "wavelength",
        }:
            if parsed[key] <= 0:
                raise ValueError(f"{key} must be positive.")
        finite(parsed["polarization_factor"], "Polarization", -1, 1)
        (c.set_pyFAI if convention == "pyfai" else c.set_fit2d)(parsed)
        if convention == "fit2d":
            # The legacy wrapper transposes orig_pixel1/2 before applying its
            # supersampling. Restore Fit2D x=column / y=row pitches explicitly.
            c.set_pixel_size((parsed["pixelY"] * 1e-6, parsed["pixelX"] * 1e-6))
            c.create_cake_geometry()
        c.orig_pixel1, c.orig_pixel2 = c.detector.pixel1, c.detector.pixel2
        c.set_start_values(
            {
                "dist": c.pattern_geometry.dist,
                "wavelength": c.pattern_geometry.wavelength,
                "polarization_factor": c.polarization_factor,
            }
        )
        c.calibrant.setWavelength_change2th(c.pattern_geometry.wavelength)
        c.filename = ""
        c._sync_calibration_params()
        self._fit_dirty = False
        self._fit_rms = None
        self._geometry_source = "manual"
        self._setup_confirmed = True
        self._calculate()
        return self._snapshot()

    def _publish_calibration_progress(self, current, total, label, active_ring=None):
        """Publish detached display data on the scientific worker only.

        Progress requests bypass that worker. Replace the complete dictionary;
        never expose models or lists that subsequent searches mutate.
        """
        c = self.configuration.calibration_model
        self._progress = {
            "running": True,
            "current": current,
            "total": total,
            "label": label,
            "calibration": {
                "activeRing": active_ring,
                "picks": [
                    {
                        "ring": ring + 1,
                        "points": [[float(y), float(x)] for y, x in positions],
                    }
                    for ring, positions in c.params.peak_selections
                ],
                "rings": self._rings,
                "rmsDegrees": self._fit_rms,
            },
        }

    def _automatic_refinement(self):
        """Qt's staged ring search/refinement, with transactional cancellation."""
        c = self.configuration.calibration_model
        options = self._workflow
        previous = copy.deepcopy(c.params.peak_selections)
        previous_geometry = c.get_pyFAI_config()
        previous_rms = self._fit_rms
        try:
            c.clear_peaks()
            total = min(options["numberOfRings"], len(c.calibrant.get_2th()))
            self._publish_calibration_progress(0, total, "Preparing peak search", 1)
            c.setup_peak_search_algorithm(options["algorithm"])
            mask = (
                self.configuration.mask_model.get_mask()
                if self.configuration.use_mask
                else None
            )
            for ring in range(total):
                if self._cancel_refinement.is_set():
                    raise InterruptedError(
                        "Automatic refinement cancelled; picked peaks and initial fit restored."
                    )
                self._publish_calibration_progress(
                    ring + 1, total, "Finding peaks on ring", ring + 1
                )
                c.search_peaks_on_ring(
                    ring,
                    options["deltaTth"],
                    options["meanFactor"],
                    options["intensityLimit"],
                    mask,
                )
                self._publish_calibration_progress(
                    ring + 1, total, "Refining ring", ring + 1
                )
                if ring >= 1 and len(c.get_point_array()) >= self._free_count():
                    self._fit_rms = self._engine.fit(
                        c, c.get_point_array(), self._calibrant_path()
                    )
                    self._update_rings()
                self._publish_calibration_progress(
                    ring + 1, total, "Refining ring", ring + 1
                )
            if not c.points:
                raise ValueError(
                    "Automatic ring search found no peaks; picked peaks and initial fit restored."
                )
        except Exception:
            c.params.peak_selections = previous
            c.set_pyFAI_config(previous_geometry)
            c._sync_calibration_params()
            self._fit_rms = previous_rms
            raise

    def _free_count(self):
        c = self.configuration.calibration_model
        return sum(
            key not in c.fixed_values
            for key in ("dist", "poni1", "poni2", "rot1", "rot2", "rot3")
        ) + int(c.fit_wavelength)

    def _inspection_context(self):
        c = self.configuration
        return (
            id(c),
            str(c.img_model.filename),
            c.img_model.series_pos,
            c.img_model.img_data.shape,
            tuple(c.img_model.params.transformations),
            repr(c.calibration_model.get_pyFAI_config()),
        )

    def _linked_snapshot(self):
        if self._inspection is None:
            return None
        context, linked = self._inspection
        if not self._has_image or context != self._inspection_context():
            self._inspection = None
            return None
        return {
            **linked,
            "radial": float(
                convert_units(
                    linked["twoTheta"],
                    self.configuration.calibration_model.pattern_geometry.wavelength,
                    "2th_deg",
                    self.configuration.integration_unit,
                )
            ),
        }

    def _validation_position(self, source, x, y=None, azimuth=None):
        c = self.configuration.calibration_model
        if not c.is_calibrated or not self._has_image:
            raise ValueError("Calibrate an image before inspecting a linked position.")
        x = finite(x, "Position")
        previous = self._linked_snapshot()
        azi = previous.get("azimuth") if previous else None
        image_point = None
        if source == "image":
            h, w = self.configuration.img_model.img_data.shape
            row = finite(y, "y", 0, h - 1e-9)
            col = finite(x, "x", 0, w - 1e-9)
            factor = c.supersampling_factor
            # Display coordinates start at pixel edges; pyFAI's integer
            # coordinates refer to centers. Preserve the subpixel click.
            tth = float(
                np.rad2deg(
                    c.pattern_geometry.tth(
                        np.array([row * factor - 0.5]),
                        np.array([col * factor - 0.5]),
                    )[0]
                )
            )
            azi = float(
                np.rad2deg(c.pattern_geometry.chi(
                    np.array([row * factor - 0.5]),
                    np.array([col * factor - 0.5]),
                )[0])
            )
            image_point = {"x": col, "y": row}
        elif source == "cake":
            tth = x
            if azimuth is not None:
                azi = ((finite(azimuth, "Azimuth") + 180) % 360) - 180
        elif source == "pattern":
            tth = float(
                convert_units(
                    x,
                    c.pattern_geometry.wavelength,
                    self.configuration.integration_unit,
                    "2th_deg",
                )
            )
        else:
            raise ValueError("Unknown validation view.")
        finite(tth, "2θ position", 0, 180)
        radial = float(
            convert_units(
                tth,
                c.pattern_geometry.wavelength,
                "2th_deg",
                self.configuration.integration_unit,
            )
        )
        angles = c.get_pixel_two_theta_array()
        # Contour indices also refer to pixel centers. Use the full-resolution
        # path for inspection so zooming does not expose preview simplification.
        paths = find_contours(angles, np.deg2rad(tth))
        contours = [
            {
                "ring": 0,
                "points": [[float(x + 0.5), float(y + 0.5)] for y, x in contour],
            }
            for contour in paths
        ]
        # Keep the last azimuth for pattern clicks, as in Qt. Choose the closest
        # point on the full-resolution contour using a circular angular distance.
        if azi is not None and image_point is None:
            if paths:
                points = np.vstack(paths)
                factor = c.supersampling_factor
                chis = c.pattern_geometry.chi(
                    (points[:, 0] + 0.5) * factor - 0.5,
                    (points[:, 1] + 0.5) * factor - 0.5,
                )
                delta = np.angle(np.exp(1j * (chis - np.deg2rad(azi))))
                index = int(np.argmin(np.abs(delta)))
                # A limited detector need not intersect the selected azimuth.
                if abs(delta[index]) < np.deg2rad(1):
                    row, col = points[index]
                    image_point = {"x": float(col + 0.5), "y": float(row + 0.5)}
        linked = {
            "twoTheta": tth,
            "radial": radial,
            "contours": contours,
            "azimuth": azi,
            "imagePoint": image_point,
        }
        self._inspection = (self._inspection_context(), linked)
        return {"linked": linked}
