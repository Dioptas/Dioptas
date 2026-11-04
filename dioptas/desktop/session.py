# SPDX-License-Identifier: MIT
"""Small, serialized command boundary around the existing scientific models.

Full-resolution display arrays use a binary native bridge. Integrations and
mask edits always use the original image resolution. Rows use Dioptas's bottom-left origin.
"""

from __future__ import annotations

import base64
import hashlib
from copy import deepcopy
import logging
import math
import json
import os
import tempfile
from contextlib import nullcontext
import threading
import time
from pathlib import Path
from typing import Any

import numpy as np
import h5py

from dioptas.model.DioptasModel import DioptasModel
from dioptas.model.CalibrationModel import get_available_detectors
from dioptas import calibrants_path
from .engines import available_engines, make_engine
from .calibration import CalibrationWorkflow
from .peak_files import load_peaks, save_peaks
from .display import image_levels
from .binary import RasterCache
from .integration import IntegrationWorkflow
from .mask import MaskWorkflow
from .map import MapWorkflow

logger = logging.getLogger(__name__)
UNITS = {"2th_deg", "q_A^-1", "d_A"}


def raster(
    array: np.ndarray,
    max_side: int | None = 1000,
    *,
    mask: bool = False,
    histogram: bool = False,
    binary: bool = False,
) -> dict:
    height, width = array.shape
    step = 1 if max_side is None else max(1, math.ceil(max(height, width) / max_side))
    if mask:
        # Preserve even a single masked pixel in a downsampled display block.
        padded = np.pad(array.astype(bool), ((0, -height % step), (0, -width % step)))
        preview = padded.reshape(padded.shape[0] // step, step, -1, step).any(
            axis=(1, 3)
        )
        values = np.ascontiguousarray(preview, dtype=np.uint8)
        limits = [0, 1]
    else:
        values = np.ascontiguousarray(array[::step, ::step], dtype="<f4")
        limits = [0, 1]
        if not histogram:
            finite = values[np.isfinite(values)]
            finite = finite[finite >= 0]
            limits = np.percentile(finite, [1, 99.5]).tolist() if finite.size else [0, 1]
            if limits[1] <= limits[0]:
                limits[1] = limits[0] + 1
    result = {
        "width": int(values.shape[1]),
        "height": int(values.shape[0]),
        "fullWidth": width,
        "fullHeight": height,
        "step": step,
        "dtype": "u8" if mask else "f32le",
        "limits": limits,
        "data": (
            values.tobytes()
            if binary
            else base64.b64encode(values.tobytes()).decode("ascii")
        ),
    }
    if histogram:
        # Use every finite source pixel, not the reduced display preview.
        # asinh is logarithmic at large intensities and supports zero/negative
        # detector values without discarding them from the distribution.
        finite = np.asarray(array, dtype=np.float64)
        finite = finite[np.isfinite(finite)]
        transformed = np.arcsinh(finite)
        histogram_range = (0, 1)
        if finite.size:
            low, high = float(transformed.min()), float(transformed.max())
            # Normalization can leave a map constant to floating-point precision.
            # 256 distinct edges cannot fit in a span of only a few ULPs.
            padding = max(abs(low), abs(high), 1.0) * 1e-6
            histogram_range = (low - padding, high + padding) if high - low < padding else (low, high)
        counts, edges = np.histogram(transformed, bins=256, range=histogram_range)
        result["limits"] = image_levels(array) or [0, 1]
        result["histogram"] = {
            "edges": np.sinh(edges).tolist(),
            "counts": counts.tolist(),
            "finitePixels": int(finite.size),
        }
    return result


def _finite_number(value: Any, name: str, low: float, high: float) -> float:
    number = float(value)
    if not math.isfinite(number) or not low <= number <= high:
        raise ValueError(f"{name} must be between {low:g} and {high:g}.")
    return number


class DesktopSession(MaskWorkflow, CalibrationWorkflow, IntegrationWorkflow, MapWorkflow):
    """One scientific session. A native window can supply its file picker."""

    def __init__(self, choose_file=None, *, binary_images=False):
        self._binary_images = binary_images
        self._raster_cache = RasterCache()
        self._ring_cache = None
        self._lock = threading.RLock()
        self._choose_file = choose_file
        self._engine = make_engine("pyfai")
        self._model = self._new_model()
        self._has_image = False
        self._project: str | None = None
        self._pattern: dict | None = None
        self._cake: dict | None = None
        self._elapsed: float | None = None
        self._defer_integration = False
        self._integration_dirty = False
        self._revision = 0
        self._calibrant_name = "LaB6"
        self._fit_dirty = False
        self._fit_rms = None
        self._rings = []
        self._init_workflow()
        self._set_calibrant()

    def _calibrant_path(self):
        if (
            self._custom_calibrant
            and self._custom_calibrant["name"] == self._calibrant_name
        ):
            return Path(self._custom_calibrant["path"])
        return Path(calibrants_path) / f"{self._calibrant_name}.D"

    def _set_calibrant(self):
        calibration = self.configuration.calibration_model
        calibration.set_calibrant(str(self._calibrant_path()))
        calibration.calibrant.setWavelength_change2th(
            calibration.start_values["wavelength"]
        )

    @staticmethod
    def _new_model():
        model = DioptasModel()
        # xypattern supplies a demonstration curve by default; the desktop starts empty.
        model.pattern.data = (np.empty(0), np.empty(0))
        DesktopSession._disable_automatic_processing(model)
        return model

    @staticmethod
    def _disable_automatic_processing(model):
        for configuration in model.configurations:
            configuration.auto_integrate_pattern = False
            configuration.auto_integrate_cake = False
            configuration.auto_save_integrated_pattern = False
            configuration.img_model.autoprocess = False

    @property
    def configuration(self):
        return self._model.current_configuration

    @staticmethod
    def example_paths():
        data = Path(__file__).resolve().parents[1] / "tests" / "data"
        image = data / "CeO2_Pilatus1M.tif"
        calibration = data / "CeO2_Pilatus1M.poni"
        return (
            (image, calibration) if image.is_file() and calibration.is_file() else None
        )

    def invoke(self, action: str, arguments: dict | None = None) -> dict:
        """The only method exposed to JavaScript; no arbitrary model access."""
        if action == "cancel_refinement":
            self._cancel_refinement.set()
            return {"ok": True}
        if action == "progress":
            return {"ok": True, "progress": self._progress.copy()}
        handlers = {
            "state": lambda: self._snapshot(include_image=True),
            "example": self._example,
            "open_image": self._open_image,
            "open_calibration": self._open_calibration,
            "open_project": self._open_project,
            "save_project": self._save_project,
            "export_pattern": self._export_pattern,
            "settings": self._settings,
            "integrate": self._integrate,
            "mask_stroke": self._mask_stroke,
            "clear_mask": lambda: self._mask_edit("clear"),
            "mask_edit": self._mask_edit,
            "mask_plugin": self._mask_plugin,
            "redo_mask": lambda: self._mask_history_step(redo=True),
            "undo_mask": self._mask_history_step,
            "pixel": self._pixel,
            "image_levels": self._image_levels,
            "calibration_setup": self._calibration_setup,
            "calibration_engine": self._select_engine,
            "pick_peak": self._pick_peak,
            "remove_pick": self._remove_pick,
            "clear_peaks": self._clear_peaks,
            "load_peaks": self._load_peaks,
            "save_peaks": self._save_peaks,
            "calibrate": self._calibrate,
            "save_calibration": self._save_calibration,
            "workflow_settings": self._workflow_settings,
            "open_calibrant": self._open_calibrant,
            "validation_calibrant": self._validation_calibrant,
            "fit_parameters": self._fit_parameters,
            "reassign_pick": self._reassign_pick,
            "remove_picks": self._remove_picks,
            "undo_calibration": self._history_step,
            "redo_calibration": lambda: self._history_step(redo=True),
            "image_transform": self._image_transform,
            "next_image": self._next_image,
            "detector_file": self._detector_file,
            "distortion_file": self._distortion_file,
            "mask_file": self._mask_file,
            "manual_geometry": self._manual_geometry,
            "validation_position": self._validation_position,
        }
        handlers.update(self._integration_handlers())
        handlers.update(self._map_commands())
        with self._lock:
            try:
                if action not in handlers:
                    raise ValueError(f"Unknown desktop command: {action}")
                if arguments is not None and not isinstance(arguments, dict):
                    raise ValueError("Command arguments must be an object.")
                arguments = dict(arguments or {})
                defer_integration = arguments.pop("defer_integration", False)
                if not isinstance(defer_integration, bool):
                    raise ValueError("Defer integration must be a boolean.")
                self._defer_integration = defer_integration
                readonly = {
                    "integration_phase_state",
                    "integration_phase_guides",
                    "integration_phase_editor",
                    "state",
                    "pixel",
                    "image_levels",
                    "validation_position",
                    "undo_calibration",
                    "redo_calibration",
                    "undo_mask",
                    "redo_mask",
                    "example",
                    "open_project",
                    "save_project",
                    "export_pattern",
                    "save_calibration",
                    "save_peaks",
                    "integration_save_image",
                    "integration_autoprocess_poll",
                }
                overlay_key = None
                if action == "integration_overlay" and arguments.get("operation") == "update":
                    fields = set(arguments) - {"operation", "index"}
                    index = arguments.get("index")
                    overlays = self._model.overlay_model.overlays
                    if fields in ({"scale"}, {"offset"}) and isinstance(index, int) and 0 <= index < len(overlays):
                        overlay_key = ("overlay", overlays[index].params.uid, next(iter(fields)))
                context = (
                    nullcontext()
                    if action in readonly or action.startswith("map_")
                    else self._model.history.transaction(action, key=overlay_key, merge_consecutive=overlay_key is not None)
                )
                with context:
                    result = handlers[action](**(arguments or {}))
                    if action in {"open_image", "next_image", "example"} and not result.get(
                        "cancelled"
                    ):
                        self._integration_image_loaded()
                if "state" in result:
                    result["state"] = self._state()["state"]
                return {"ok": True, **result}
            except Exception as exc:
                logger.exception("Desktop command %s failed", action)
                return {"ok": False, "error": str(exc) or type(exc).__name__}
            finally:
                self._defer_integration = False

    def _path(self, path, kind, save=False):
        if path is None:
            if self._choose_file is None:
                raise ValueError("Choose a file in the desktop application.")
            path = self._choose_file(kind, save)
        if not path:
            return None
        resolved = Path(path).expanduser().resolve()
        if not save and not resolved.is_file():
            raise FileNotFoundError(f"File not found: {resolved}")
        return str(resolved)

    def _state(self):
        c = self.configuration
        image = c.img_model.img_data if self._has_image else None
        calibration = c.calibration_model
        mask = c.mask_model.get_display_mask() if self._has_image else None
        return {
            "state": {
                "revision": self._revision,
                "hasImage": self._has_image,
                "imageName": Path(c.img_model.filename).name
                if self._has_image
                else None,
                "imagePath": str(c.img_model.filename) if self._has_image else None,
                "shape": list(image.shape) if image is not None else None,
                "calibrationName": calibration.calibration_name
                if calibration.is_calibrated
                else None,
                "calibrated": calibration.is_calibrated,
                "projectName": Path(self._project).name if self._project else None,
                "unit": c.integration_unit,
                "bins": c.integration_rad_points,
                "useMask": c.use_mask,
                "transparentMask": c.transparent_mask,
                "maskedPixels": int(np.count_nonzero(mask)) if mask is not None else 0,
                "canUndoMask": self._model.history.can_undo,
                "canRedoMask": self._model.history.can_redo,
                "undoLabel": self._model.history.undo_label,
                "redoLabel": self._model.history.redo_label,
                "maskDetails": self._mask_details(),
                "exampleAvailable": self.example_paths() is not None,
                "elapsedMs": self._elapsed,
                "integrationDirty": self._integration_dirty,
                "configurationCount": len(self._model.configurations),
                "configurationIndex": self._model.configuration_ind,
                "geometry": {
                    key: float(getattr(calibration.pattern_geometry, key))
                    for key in (
                        "dist",
                        "poni1",
                        "poni2",
                        "wavelength",
                        "rot1",
                        "rot2",
                        "rot3",
                    )
                },
                "integration": self._integration_state(),
                "calibration": {
                    **self._calibration_details(),
                    "engine": self._engine.id,
                    "engineLabel": self._engine.label,
                    "engines": available_engines(),
                    "calibrant": self._calibrant_name,
                    "calibrants": self._calibrant_names(),
                    "detectors": ["Custom", *get_available_detectors()[0]],
                    "detector": calibration.params.detector_name or "Custom",
                    "pixelX": calibration.orig_pixel2 * 1e6,
                    "pixelY": calibration.orig_pixel1 * 1e6,
                    "distance": calibration.start_values["dist"] * 1000,
                    "wavelength": calibration.start_values["wavelength"] * 1e10,
                    "fitTilts": "rot1" not in calibration.fixed_values,
                    "fitDirty": self._fit_dirty,
                    "rmsDegrees": self._fit_rms,
                    "saved": bool(calibration.filename),
                    "picks": [
                        {"ring": ring + 1, "points": [list(p) for p in positions]}
                        for ring, positions in calibration.params.peak_selections
                    ],
                    "rings": [
                        {"ring": i + 1, "twoTheta": float(angle * 180 / np.pi)}
                        for i, angle in enumerate(calibration.calibrant.get_2th())
                        if angle is not None and np.isfinite(angle)
                    ],
                },
            }
        }

    def _raster(self, array, **options):
        if self._binary_images:
            return self._raster_cache.raster(array, raster, binary=True, **options)
        return raster(array, **options)

    def _snapshot(self, include_image=False):
        result = self._state()
        result.update(self._map_snapshot())
        result.update(pattern=self._pattern, cake=self._cake)
        result["rings"] = self._rings
        result["linked"] = self._linked_snapshot()
        if self._has_image:
            result["mask"] = self._raster(
                self.configuration.mask_model.get_display_mask(),
                mask=True,
                max_side=None,
            )
            if include_image:
                result["image"] = self._raster(
                    self.configuration.img_model.img_data, max_side=None, histogram=True
                )
                result["rawImage"] = self._raster(
                    self.configuration.img_model.raw_img_data, max_side=None, histogram=True
                )
        return result

    def _example(self):
        paths = self.example_paths()
        if paths is None:
            raise FileNotFoundError(
                "The example is available in a source checkout. Open your own image and .poni calibration instead."
            )
        self._model = self._new_model()
        self.configuration.calibration_model.use_dioptrin = (
            self._engine.id == "dioptrin"
        )
        self._project = None
        self._integration_auto_save = False
        self._integration_reset_autoprocess()
        self._geometry_source = "none"
        image, calibration = paths
        # This example starts with a raw calibrant image, not a solved PONI.
        self._calibrant_name = "CeO2"
        self._set_calibrant()
        self._calibration_setup(
            calibrant="CeO2",
            wavelength=0.406626,
            distance=200,
            pixel_x=172,
            pixel_y=172,
        )
        self._fit_dirty = False
        self._fit_rms = None
        self.configuration.params.cake_azimuth_points = 360
        self.configuration.img_model.load(str(image))
        self._has_image = True
        self._calculate()
        return self._snapshot(include_image=True)

    def _open_image(self, path=None, directory=None):
        if path and directory and not Path(path).expanduser().is_absolute():
            path = str(Path(directory).expanduser() / path)
        path = self._path(path, "image")
        if path is None:
            return {"cancelled": True}
        self.configuration.img_model.load(path)
        self.configuration.calibration_model.clear_peaks()
        self._fit_rms = None
        self._has_image = True
        self._calculate()
        return self._snapshot(include_image=True)

    def _open_calibration(self, path=None):
        path = self._path(path, "calibration")
        if path is None:
            return {"cancelled": True}
        self.configuration.calibration_model.load(path)
        self._geometry_source = "loaded"
        self._setup_confirmed = True
        c = self.configuration.calibration_model
        c.set_start_values(
            {
                "dist": c.pattern_geometry.dist,
                "wavelength": c.pattern_geometry.wavelength,
                "polarization_factor": c.polarization_factor,
            }
        )
        self._fit_dirty = False
        self._fit_rms = None
        self.configuration.calibration_model.calibrant.setWavelength_change2th(
            self.configuration.calibration_model.pattern_geometry.wavelength
        )
        self._calculate()
        return self._snapshot()

    def _open_project(self, path=None):
        path = self._path(path, "project")
        if path is None:
            return {"cancelled": True}
        # Build separately so unsupported files cannot replace the live session.
        with h5py.File(path, "r") as project:
            metadata = json.loads(project.attrs.get("react_desktop", "{}"))
        candidate = self._new_model()
        candidate.load(path)
        self._disable_automatic_processing(candidate)
        candidate.calibration_model.use_dioptrin = self._engine.id == "dioptrin"
        if candidate.calibration_model.is_calibrated:
            candidate.calibration_model.create_cake_geometry()
        self._model = candidate
        self._integration_auto_save = False
        self._integration_reset_autoprocess()
        name = metadata.get("calibrant")
        if metadata.get("custom_calibrant"):
            custom = metadata["custom_calibrant"]
            self._install_custom_calibrant(custom["name"], custom["content"])
        if name in self._calibrant_names():
            self._calibrant_name = name
        self._set_calibrant()
        if candidate.calibration_model.is_calibrated:
            candidate.calibration_model.calibrant.setWavelength_change2th(
                candidate.calibration_model.pattern_geometry.wavelength
            )
        self._setup_confirmed = bool(
            metadata.get("setup_confirmed", candidate.calibration_model.is_calibrated)
        )
        self._workflow.update(metadata.get("workflow", {}))
        self._geometry_source = metadata.get("geometry_source", "loaded")
        self._fit_dirty = bool(metadata.get("fit_dirty", False))
        self._fit_rms = metadata.get("rms_degrees")
        self._has_image = candidate.img_model.img_data is not None
        self._project = path
        self._restore_map_normalization(path)
        self._calculate()
        return self._snapshot(include_image=True)

    def _save_project(self, path=None):
        path = self._path(path, "project", save=True)
        if path is None:
            return {"cancelled": True}
        if not path.lower().endswith(".dio"):
            path += ".dio"
        # Keep the ordinary .dio state intact and add a small optional UI
        # document. Older Qt readers ignore this attribute. Publish atomically.
        descriptor, temporary = tempfile.mkstemp(
            prefix=".dioptas-desktop-", suffix=".dio", dir=Path(path).parent
        )
        os.close(descriptor)
        try:
            self._model.save(temporary)
            with h5py.File(temporary, "r+") as project:
                self._save_map_normalization(project)
                project.attrs["react_desktop"] = json.dumps(
                    {
                        "version": 1,
                        "calibrant": self._calibrant_name,
                        "fit_dirty": self._fit_dirty,
                        "rms_degrees": self._fit_rms,
                        "custom_calibrant": {
                            k: v
                            for k, v in self._custom_calibrant.items()
                            if k != "path"
                        }
                        if self._custom_calibrant
                        else None,
                        "setup_confirmed": self._setup_confirmed,
                        "workflow": self._workflow,
                        "geometry_source": self._geometry_source,
                    }
                )
            os.replace(temporary, path)
        finally:
            Path(temporary).unlink(missing_ok=True)
        self._project = path
        return {**self._state(), "savedPath": path}

    def _export_pattern(self, path=None):
        if self._pattern is None:
            raise ValueError("Integrate an image before exporting a pattern.")
        path = self._path(path, "pattern", save=True)
        if path is None:
            return {"cancelled": True}
        if not Path(path).suffix:
            path += ".xy"
        # Delegate format handling and metadata to Dioptas's existing writer.
        self.configuration.save_pattern(path)
        return {"savedPath": path}

    def _settings(self, unit=None, bins=None, use_mask=None, transparent_mask=None):
        if unit is not None and unit not in UNITS:
            raise ValueError("Unsupported integration unit.")
        if bins is not None:
            number = _finite_number(bins, "Radial bins", 100, 10000)
            if number != int(number):
                raise ValueError("Radial bins must be an integer.")
        if use_mask is not None and not isinstance(use_mask, bool):
            raise ValueError("Use mask must be a boolean.")
        if transparent_mask is not None and not isinstance(transparent_mask, bool):
            raise ValueError("Mask transparency must be a boolean.")
        c = self.configuration
        if transparent_mask is not None:
            c.transparent_mask = transparent_mask
            if unit is None and bins is None and use_mask is None:
                # Opacity changes only the display; preserve integration caches
                # and do not resend unchanged detector or mask pixels.
                self._revision += 1
                return self._state()
        if unit is not None:
            c.integration_unit = unit
        if bins is not None:
            c.integration_rad_points = int(number)
        if use_mask is not None:
            c.use_mask = use_mask
        self._calculate()
        return self._snapshot()

    def _calculate(self):
        self._revision += 1
        self._pattern = self._cake = None
        self._rings = []
        self._elapsed = None
        c = self.configuration
        if not self._has_image or not c.calibration_model.is_calibrated:
            self._integration_dirty = False
            return
        # Mask mode needs the edited overlay immediately, but neither of its
        # hidden integration views. Clear stale results and calculate once
        # when a view that uses them becomes active again.
        self._integration_dirty = True
        if self._defer_integration:
            return
        start = time.perf_counter()
        self._integration_prepare_corrections()
        result = self._integration_calculate_pattern()
        if result is None:
            raise RuntimeError("Integration did not return a pattern.")
        x, y = result
        self._refresh_integration_pattern()
        self._integration_calculate_cake()
        calibration = c.calibration_model
        self._cake = {
            **self._raster(calibration.cake_img, max_side=None, histogram=True),
            "radialRange": [
                float(calibration.cake_tth[0]),
                float(calibration.cake_tth[-1]),
            ],
            "azimuthRange": [
                float(calibration.cake_azi[0]),
                float(calibration.cake_azi[-1]),
            ],
            # Configuration.integrate_image_2d deliberately uses 2theta.
            "unit": "2th_deg",
        }
        self._update_rings()
        self._elapsed = round((time.perf_counter() - start) * 1000)
        self._integration_dirty = False

    def _update_rings(self):
        from skimage.measure import find_contours

        c = self.configuration
        angles = c.calibration_model.get_pixel_two_theta_array()
        key = (
            angles.shape,
            angles.dtype.str,
            hashlib.sha256(np.ascontiguousarray(angles)).digest(),
            tuple(c.calibration_model.calibrant.get_2th()),
        )
        if self._ring_cache is not None and self._ring_cache[0] == key:
            self._rings = self._ring_cache[1]
            return
        step = max(1, math.ceil(max(angles.shape) / 450))
        preview = angles[::step, ::step]
        low, high = float(angles.min()), float(angles.max())
        rings = []
        for index, angle in enumerate(c.calibration_model.calibrant.get_2th()):
            if angle is None or not low < angle < high:
                continue
            for contour in find_contours(preview, float(angle)):
                rings.append(
                    {
                        "ring": index + 1,
                        "points": [
                            [float(x * step), float(y * step)] for y, x in contour[::2]
                        ],
                    }
                )

        self._rings = rings
        self._ring_cache = (key, rings)

    def _select_engine(self, engine):
        # Construct and validate first, so a missing dependency/license cannot
        # replace a functioning pyFAI session or silently change the engine.
        selected = make_engine(engine)
        self._engine = selected
        self.configuration.calibration_model.use_dioptrin = selected.id == "dioptrin"
        if self.configuration.calibration_model.is_calibrated:
            self.configuration.calibration_model.create_cake_geometry()
        self._calculate()
        return self._snapshot()

    def _calibration_setup(
        self,
        calibrant=None,
        wavelength=None,
        distance=None,
        pixel_x=None,
        pixel_y=None,
        detector=None,
        fit_tilts=None,
    ):
        c = self.configuration.calibration_model
        if calibrant is not None:
            if calibrant not in self._calibrant_names():
                raise ValueError("Choose an available calibrant.")
        values = c.start_values.copy()
        if wavelength is not None:
            values["wavelength"] = (
                _finite_number(wavelength, "Wavelength (Å)", 0.01, 10) * 1e-10
            )
        if distance is not None:
            values["dist"] = _finite_number(distance, "Distance (mm)", 1, 10000) * 1e-3
        px = (
            c.orig_pixel2
            if pixel_x is None
            else _finite_number(pixel_x, "Pixel width (µm)", 0.1, 5000) * 1e-6
        )
        py = (
            c.orig_pixel1
            if pixel_y is None
            else _finite_number(pixel_y, "Pixel height (µm)", 0.1, 5000) * 1e-6
        )
        if detector is not None and detector not in [
            "Custom",
            *get_available_detectors()[0],
        ]:
            raise ValueError("Choose an available detector.")
        if detector is not None:
            if detector == "Custom":
                c.reset_detector()
            else:
                c.load_detector(detector)
                px, py = c.detector.pixel2, c.detector.pixel1
        c.set_start_values(values)
        c.set_pixel_size((py, px))
        if all(v is not None for v in (wavelength, distance, pixel_x, pixel_y)):
            self._setup_confirmed = True
        if calibrant is not None:
            self._calibrant_name = calibrant
            self._set_calibrant()
        c.calibrant.setWavelength_change2th(values["wavelength"])
        if fit_tilts is not None:
            c.set_fixed_values(
                {"rot3": 0} if fit_tilts else {"rot1": 0, "rot2": 0, "rot3": 0}
            )
        if c.is_calibrated:
            self._fit_dirty = True
        self._fit_rms = None
        return self._state()

    def _pick_peak(self, x, y, ring, automatic=True, search_size=None):
        if not self._has_image:
            raise ValueError("Open a calibrant image first.")
        height, width = self.configuration.img_model.img_data.shape
        x = _finite_number(x, "x", 0, width - 1)
        y = _finite_number(y, "y", 0, height - 1)
        calibration = self.configuration.calibration_model
        ring = int(
            _finite_number(
                ring, "Ring number", 1, max(1, len(calibration.calibrant.get_2th()))
            )
        )
        if ring > len(calibration.calibrant.get_2th()):
            raise ValueError(
                "That ring is unavailable for this calibrant and wavelength."
            )
        if automatic:
            points = self._engine.find_peaks(
                calibration, self.configuration.img_model.img_data, x, y, ring - 1
            )
        else:
            size = int(
                _finite_number(
                    search_size
                    if search_size is not None
                    else self._workflow["searchSize"],
                    "Search size",
                    1,
                    1000,
                )
            )
            points = calibration.find_peak(y, x, size, ring - 1)
        if not len(points):
            raise ValueError(
                "No peak found here. Click on a bright ring, or try single-peak mode."
            )
        self._fit_dirty = True
        self._fit_rms = None
        next_ring = (
            min(ring + 1, len(calibration.calibrant.get_2th()))
            if self._workflow["autoIncrement"]
            else ring
        )
        return {**self._state(), "pickedCount": len(points), "nextRing": next_ring}

    def _remove_pick(self, index):
        self.configuration.calibration_model.remove_peak_selection(int(index))
        self._fit_dirty = True
        self._fit_rms = None
        return self._state()

    def _clear_peaks(self):
        self.configuration.calibration_model.clear_peaks()
        self._fit_dirty = True
        self._fit_rms = None
        return self._state()

    def _save_peaks(self, path=None):
        calibration = self.configuration.calibration_model
        if not self._has_image or not calibration.params.peak_selections:
            raise ValueError("Pick calibration peaks before saving them.")
        path = self._path(path, "peaks", save=True)
        if path is None:
            return {"cancelled": True}
        if not Path(path).suffix:
            path += ".json"
        save_peaks(path, calibration, self.configuration.img_model, self._calibrant_name)
        return {**self._state(), "savedPath": path}

    def _load_peaks(self, path=None):
        if not self._has_image:
            raise ValueError("Open a calibrant image before loading peaks.")
        path = self._path(path, "peaks")
        if path is None:
            return {"cancelled": True}
        calibration = self.configuration.calibration_model
        selections = load_peaks(path, calibration, self.configuration.img_model)
        calibration.params.peak_selections = selections
        self._fit_dirty = True
        self._fit_rms = None
        return self._state()

    def _calibrate(self, automatic=None, parameters=None, polarization=None, restart=False):
        if parameters is not None:
            self._fit_parameters(parameters, polarization=polarization)
        if not self._setup_confirmed:
            raise ValueError(
                "Check detector pixel sizes and the fit start values before fitting."
            )
        c = self.configuration.calibration_model
        points = c.get_point_array()
        if not len(points) or len(points) < self._free_count():
            raise ValueError(
                f"Select at least {max(1, self._free_count())} peaks for the current free parameters. Spread selections across several rings when possible."
            )
        previous = (
            deepcopy(c.get_pyFAI_config()),
            c.params.peak_selections,
            c.is_calibrated,
            c.calibration_name,
            c.filename,
            self._fit_rms,
            self._fit_dirty,
            self._geometry_source,
        )
        self._cancel_refinement.clear()
        self._publish_calibration_progress(0, 1, "Fitting calibration")
        try:
            if restart:
                # Both engines initialize a fresh geometry from the current
                # picks/start values when no calibrated solution is active.
                # Keep this inside the transaction so failure restores it.
                c.is_calibrated = False
            c.calibrant.setWavelength_change2th(c.start_values["wavelength"])
            self._fit_rms = self._engine.fit(c, points, self._calibrant_path())
            self._geometry_source = "fitted"
            self._update_rings()
            self._publish_calibration_progress(1, 1, "Initial fit complete")
            if (
                automatic
                if automatic is not None
                else self._workflow["automaticRefinement"]
            ):
                self._automatic_refinement()
            c.calibrant.setWavelength_change2th(c.pattern_geometry.wavelength)
            if self._cancel_refinement.is_set():
                raise InterruptedError(
                    "Calibration cancelled; previous geometry and picked peaks restored."
                )
            self._publish_calibration_progress(
                1, 1, "Integrating calibrated image",
                self._progress.get("calibration", {}).get("activeRing"),
            )
            self._fit_dirty = False
            self._calculate()
            return self._snapshot()
        except Exception:
            geometry, picks, calibrated, name, filename, rms, dirty, source = previous
            c.set_pyFAI_config(geometry)
            c.params.peak_selections = picks
            c.is_calibrated = calibrated
            c.calibration_name, c.filename = name, filename
            c._sync_calibration_params()
            c.calibrant.setWavelength_change2th(c.pattern_geometry.wavelength)
            self._fit_rms, self._fit_dirty, self._geometry_source = rms, dirty, source
            self._calculate()
            raise
        finally:
            self._progress = {
                **{key: value for key, value in self._progress.items() if key != "calibration"},
                "running": False,
            }

    def _save_calibration(self, path=None):
        if not self.configuration.calibration_model.is_calibrated or self._fit_dirty:
            raise ValueError(
                "Fit the current ring selections before saving the calibration."
            )
        path = self._path(path, "calibration", save=True)
        if path is None:
            return {"cancelled": True}
        if not path.lower().endswith(".poni"):
            path += ".poni"
        calibration = self.configuration.calibration_model
        # Integration supersampling is computational sampling, not a change
        # to the physical detector pixels written to a PONI calibration.
        factor = calibration.supersampling_factor
        try:
            calibration.reset_supersampling()
            calibration.save(path)
        finally:
            calibration.set_supersampling(factor)
            calibration.cake_geometry.reset()
        return {**self._state(), "savedPath": path}

    def _integrate(self):
        if (
            not self._has_image
            or not self.configuration.calibration_model.is_calibrated
        ):
            raise ValueError("Open an image and a .poni calibration first.")
        self._calculate()
        return self._snapshot()

    def _image_levels(
        self, mode="percentile", percentile=2.5, filter_gaps=True, source="detector"
    ):
        if source not in {"detector", "cake", "raw_detector"}:
            raise ValueError("Choose the detector or cake display.")
        if not self._has_image or (source == "cake" and self._cake is None):
            return {"levels": None, "display": source}
        data = (
            self.configuration.calibration_model.cake_img
            if source == "cake"
            else self.configuration.img_model.raw_img_data if source == "raw_detector"
            else self.configuration.img_model.img_data
        )
        return {
            "levels": image_levels(data, mode, percentile, filter_gaps),
            "display": "detector" if source == "raw_detector" else source,
        }

    def _pixel(self, x, y, raw=False):
        if not self._has_image:
            return {"pixel": None}
        image = self.configuration.img_model.raw_img_data if raw else self.configuration.img_model.img_data
        height, width = image.shape
        x = int(_finite_number(x, "x", 0, width - 1))
        y = int(_finite_number(y, "y", 0, height - 1))
        value = float(image[y, x])
        pixel = {"x": x, "y": y, "value": value if math.isfinite(value) else None}
        calibration = self.configuration.calibration_model
        if calibration.is_calibrated:
            factor = calibration.supersampling_factor
            rows = np.array([y, y, y + 1 if y + 1 < height else max(0, y - 1)], dtype=float)
            columns = np.array([x, x + 1 if x + 1 < width else max(0, x - 1), x], dtype=float)
            angles = np.rad2deg(calibration.pattern_geometry.tth(
                (rows + 0.5) * factor - 0.5,
                (columns + 0.5) * factor - 0.5,
            ))
            if np.isfinite(angles[0]):
                pixel["twoTheta"] = float(angles[0])
                differences = np.abs(angles[1:] - angles[0])
                finite_differences = differences[np.isfinite(differences)]
                if finite_differences.size:
                    pixel["twoThetaResolution"] = float(np.max(finite_differences))
        return {"pixel": pixel}
