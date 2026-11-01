# SPDX-License-Identifier: MIT
"""Qt mask workflows on the session's existing configuration and MaskModel."""

from contextlib import contextmanager
from copy import deepcopy
import math

import numpy as np

from dioptas.model.MaskModel import MaskModel
from dioptas.model.util.calc import convert_units
from dioptas.model.util.point import Point
from dioptas.model.util.cosmics import cosmicsimage
from .calibration import finite
from dioptas.model.state import params_to_dict


class MaskWorkflow:
    def _mask_history_step(self, redo=False):
        # Qt history is application-wide. Mask-only undo should keep the image
        # viewport/contrast and an unchanged fit's diagnostic state.
        before_image = (
            self.configuration.img_model.img_data.copy() if self._has_image else None
        )
        before_calibration = params_to_dict(self.configuration.calibration_model.params)
        dirty, rms = self._fit_dirty, self._fit_rms
        result = self._history_step(redo=redo)
        if before_calibration == params_to_dict(
            self.configuration.calibration_model.params
        ):
            self._fit_dirty, self._fit_rms = dirty, rms
        if before_image is not None and np.array_equal(
            before_image, self.configuration.img_model.img_data, equal_nan=True
        ):
            result.pop("image", None)
        result["state"] = self._state()["state"]
        return result

    def _mask_details(self):
        manager = self.configuration.mask_plugin_manager
        return {
            "mode": self.configuration.mask_model.mode,
            "filename": self.configuration.mask_model.filename or None,
            "plugins": [
                {
                    "name": name,
                    "description": entry.plugin.description,
                    "enabled": entry.enabled,
                    "settings": entry.plugin.get_settings(),
                    "schema": entry.plugin.get_settings_schema() or {},
                    "maskedPixels": int(np.count_nonzero(entry.cached_mask))
                    if entry.cached_mask is not None
                    else 0,
                }
                for name, entry in manager.plugins.items()
            ],
        }

    @contextmanager
    def _mask_job(self, label):
        self._cancel_refinement.clear()
        self._progress = {"running": True, "current": 0, "total": 1, "label": label}
        try:
            yield
        finally:
            self._progress = {**self._progress, "running": False}

    def _check_mask_cancelled(self):
        if self._cancel_refinement.is_set():
            raise ValueError("Mask operation cancelled; previous mask restored.")

    def _mask_edit(
        self,
        operation,
        points=None,
        erase=False,
        threshold=None,
        unit="2th_deg",
        lower=None,
        upper=None,
        outside=False,
    ):
        if not self._has_image:
            raise ValueError("Open an image before editing its mask.")
        if not isinstance(erase, bool):
            raise ValueError("Unmask must be a boolean.")
        image = self.configuration.img_model.img_data
        h, w = image.shape
        # Work on a detached model: validation, cancellation and failures cannot
        # leave a partially applied scientific mask or an undo step.
        candidate = MaskModel(image.shape)
        candidate.set_mask_data(self.configuration.mask_model.get_img().copy())
        candidate.mode = not erase
        vertices = []
        if operation in {"rectangle", "circle", "polygon", "arc"}:
            count = {"rectangle": 2, "circle": 2, "arc": 4}.get(operation)
            if not isinstance(points, list) or not 2 <= len(points) <= 10000:
                raise ValueError("Select the shape's points on the detector.")
            if (count and len(points) != count) or (
                operation == "polygon" and len(points) < 3
            ):
                raise ValueError("Incorrect number of points for this selection.")
            for point in points:
                if len(point) != 2:
                    raise ValueError("Each point needs x and y coordinates.")
                vertices.append(
                    (
                        finite(point[0], "x", 0, w - 1e-6),
                        finite(point[1], "y", 0, h - 1e-6),
                    )
                )
        with self._mask_job("Applying mask"):
            if operation == "rectangle":
                (x1, y1), (x2, y2) = vertices
                # MaskModel.mask_rect takes array row first, unlike polygon.
                candidate.mask_rect(y1, x1, y2 - y1, x2 - x1)
            elif operation == "circle":
                (x1, y1), (x2, y2) = vertices
                candidate.mask_ellipse(
                    int((x1 + x2) / 2),
                    int((y1 + y2) / 2),
                    max(1, int(abs(x2 - x1) / 2)),
                    max(1, int(abs(y2 - y1) / 2)),
                )
            elif operation == "polygon":
                candidate.mask_polygon(*np.asarray(vertices).T)
            elif operation == "arc":
                a, b, c, edge = [Point(*p) for p in vertices]
                center = candidate.find_center_of_circle_from_three_points(a, b, c)
                if center is None:
                    raise ValueError("Arc points must be distinct and not collinear.")
                radius = candidate.find_radius_of_circle_from_center_and_point(
                    center, a
                )
                angles = candidate.find_n_angles_on_arc_from_three_points_around_p0(
                    center, a, b, c, 50
                )
                if angles is None:
                    raise ValueError("Choose three distinct points along the arc.")
                width = abs(
                    radius - math.hypot(edge.x() - center.x(), edge.y() - center.y())
                )
                outer = candidate.calc_arc_points_from_angles(
                    center, radius, -width, angles
                )
                inner = candidate.calc_arc_points_from_angles(
                    center, radius, width, angles
                )
                polygon = outer + list(reversed(inner))
                candidate.mask_polygon(
                    np.array([p.x() for p in polygon]),
                    np.array([p.y() for p in polygon]),
                )
            elif operation in {"above", "below"}:
                value = finite(threshold, "Threshold", -1e30, 1e30)
                getattr(candidate, f"mask_{operation}_threshold")(image, value)
            elif operation == "range":
                calibration = self.configuration.calibration_model
                if not calibration.is_calibrated:
                    raise ValueError(
                        "Calibrate the detector before masking a radial range."
                    )
                if unit not in {"2th_deg", "q_A^-1", "d_A"}:
                    raise ValueError("Choose a supported radial unit.")
                tth = np.rad2deg(calibration.get_pixel_two_theta_array())
                with np.errstate(divide="ignore", invalid="ignore"):
                    radial = convert_units(tth, calibration.wavelength, "2th_deg", unit)
                candidate.mask_radial_range(radial, lower, upper, outside)
            elif operation in {"grow", "shrink", "invert", "clear"}:
                getattr(
                    candidate,
                    {"invert": "invert_mask", "clear": "clear_mask"}.get(
                        operation, operation
                    ),
                )()
            elif operation == "cosmic":
                # Same two LA Cosmic passes as MaskModel.remove_cosmic, with
                # cancellation between passes and no partially committed mask.
                self._progress = {
                    "running": True,
                    "current": 0,
                    "total": 2,
                    "label": "Cosmic removal",
                }
                cosmic = cosmicsimage(image, sigclip=3.0, objlim=3.0)
                for index in range(2):
                    self._check_mask_cancelled()
                    cosmic.lacosmiciteration(True)
                    cosmic.clean()
                    candidate.set_mask_data(
                        np.logical_or(candidate.get_img(), cosmic.mask)
                    )
                    self._progress = {**self._progress, "current": index + 1}
            else:
                raise ValueError("Unknown mask operation.")
            self._check_mask_cancelled()
            self.configuration.mask_model.mode = not erase
            self.configuration.mask_model.set_mask_data(candidate.get_img())
            self.configuration.use_mask = True
            # Refresh even when the count stayed constant (e.g. moving a mask).
            self.configuration._update_plugin_masks()
            self._calculate()
        return self._snapshot()

    def _mask_file(self, path=None, save=False, add=False, flipud=False):
        if not self._has_image:
            raise ValueError("Open an image first.")
        path = self._path(path, "mask", save=save)
        if path is None:
            return {"cancelled": True}
        model = self.configuration.mask_model
        if save:
            model.save_mask(path, flipud=flipud)
            return {**self._state(), "savedPath": path}
        data = model.read_mask_file(path, flipud=flipud)
        if data.shape != self.configuration.img_model.img_data.shape:
            raise ValueError("Mask dimensions do not match the current image.")
        if (
            not (np.issubdtype(data.dtype, np.number) or data.dtype == bool)
            or not np.isfinite(data).all()
        ):
            raise ValueError("Mask data must contain finite numeric values.")
        data = data.astype(bool)
        model.set_mask_data(np.logical_or(model.get_img(), data) if add else data)
        if not add:
            model.filename = path
        self.configuration.use_mask = True
        self.configuration._update_plugin_masks()
        self._calculate()
        return self._snapshot()

    def _mask_plugin(self, name, enabled=None, settings=None, imprint=False):
        if not self._has_image:
            raise ValueError("Open an image first.")
        manager = self.configuration.mask_plugin_manager
        plugin = manager.get_plugin(name)
        if plugin is None:
            raise ValueError("This optional mask plugin is not installed.")
        if enabled is not None and not isinstance(enabled, bool):
            raise ValueError("Plugin enabled must be a boolean.")
        if settings is not None:
            schema = plugin.get_settings_schema() or {}
            if not isinstance(settings, dict) or set(settings) - set(schema):
                raise ValueError("Unknown plugin setting.")
            parsed = {}
            for key, value in settings.items():
                spec = schema[key]
                kind = spec.get("type", "str")
                if kind in {"float", "int"}:
                    value = finite(
                        value, key, spec.get("min", -1e12), spec.get("max", 1e12)
                    )
                    if kind == "int":
                        if not value.is_integer():
                            raise ValueError(f"{key} must be an integer.")
                        value = int(value)
                elif kind == "bool" and not isinstance(value, bool):
                    raise ValueError(f"{key} must be a boolean.")
                elif kind == "choice" and value not in spec.get("choices", []):
                    raise ValueError(f"Invalid choice for {key}.")
                parsed[key] = value
            settings = parsed
        old = [
            (
                entry,
                entry.enabled,
                deepcopy(entry.plugin.get_settings()),
                entry.cached_mask,
            )
            for entry in manager.plugins.values()
        ]
        user_mask = self.configuration.mask_model.get_img().copy()
        with self._mask_job(f"Computing {name}"):
            try:
                # Suppress intermediate history: cancellation must not record a
                # plugin setting or an imprint that never completed.
                with self._model.history.suspended():
                    if settings is not None:
                        manager.update_plugin_settings(name, settings)
                    if enabled is not None:
                        manager.set_enabled(name, enabled)
                    if (
                        enabled is True
                        or (
                            enabled is None and old[manager.plugin_names.index(name)][1]
                        )
                    ) and not manager.is_enabled(name):
                        raise ValueError(
                            f"{name} failed; check its settings and calibration requirements."
                        )
                    self._check_mask_cancelled()
                    if imprint:
                        if (
                            not manager.is_enabled(name)
                            or manager.plugins[name].cached_mask is None
                        ):
                            raise ValueError(
                                "Enable the plugin before imprinting its mask."
                            )
                        self.configuration.mask_model.imprint_plugin_mask(name)
            except Exception:
                with self._model.history.suspended():
                    for entry, was_enabled, values, cached in old:
                        entry.plugin.update_settings(values)
                        entry.enabled, entry.cached_mask = was_enabled, cached
                    self.configuration.mask_model.set_mask_data(user_mask)
                raise
            self.configuration.mask_model.mask_changed.emit()
            self.configuration.use_mask = True
            self._calculate()
        return self._snapshot()

    def _mask_stroke(self, points, radius, erase=False):
        if not self._has_image:
            raise ValueError("Open an image before editing its mask.")
        radius = finite(radius, "Brush radius", 1, 300)
        if not isinstance(points, list) or not 1 <= len(points) <= 10000:
            raise ValueError("A brush stroke needs between 1 and 10000 points.")
        height, width = self.configuration.img_model.img_data.shape
        validated = []
        for point in points:
            if len(point) != 2:
                raise ValueError("A brush point needs x and y coordinates.")
            validated.append(
                (
                    finite(point[0], "x", 0, width - 1e-6),
                    finite(point[1], "y", 0, height - 1e-6),
                )
            )
        mask = self.configuration.mask_model.get_img().copy()
        for x, y in validated:
            left, right = max(0, int(x - radius)), min(width, math.ceil(x + radius + 1))
            bottom, top = (
                max(0, int(y - radius)),
                min(height, math.ceil(y + radius + 1)),
            )
            yy, xx = np.ogrid[bottom:top, left:right]
            region = (xx - x) ** 2 + (yy - y) ** 2 <= radius**2
            mask[bottom:top, left:right][region] = not erase
        self.configuration.mask_model.mode = not erase
        self.configuration.mask_model.set_mask_data(mask)
        self.configuration.use_mask = True
        self.configuration._update_plugin_masks()
        self._calculate()
        return self._snapshot()
