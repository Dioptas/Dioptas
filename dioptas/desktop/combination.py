# SPDX-License-Identifier: MIT
"""Detector combination controls over the existing Dioptas scientific models."""

from copy import deepcopy
from pathlib import Path

import numpy as np
from xypattern import Pattern

from .integration import boolean, finite, values
from .combination_engine import (
    native_unavailable,
    native_combination_key,
    make_native_multi,
)


class CombinationWorkflow:
    # Scientific state belongs to Configuration. These are only the desktop's
    # companion workflow values, which must follow the selected configuration.
    _configuration_fields = (
        "_has_image",
        "_calibration_image_shape",
        "_setup_confirmed",
        "_geometry_source",
        "_fit_dirty",
        "_fit_rms",
        "_calibrant_name",
        "_workflow",
    )

    def _init_combination(self):
        self._configuration_workflows = {}
        self._combine_patterns = False
        self._combine_cakes = False
        self._combined_pattern = None
        self._combined_cake_data = None
        self._combination_backend = {}
        self._native_combination = None
        self._native_combination_key = None

    def _combination_commands(self):
        return {
            "configuration_select": self._configuration_select,
            "combination_settings": self._combination_settings,
            "save_combined_pattern": self._save_combined_pattern,
        }

    def _combination_reason(self):
        if len(self._model.configurations) < 2:
            return "Load a project with at least two detector configurations."
        missing = [
            str(i + 1)
            for i, c in enumerate(self._model.configurations)
            if c.img_model.raw_img_data is None or not c.calibration_model.is_calibrated
        ]
        return (
            (
                "Load an image and calibration for configuration "
                + ", ".join(missing)
                + "."
            )
            if missing
            else None
        )

    def _combination_state(self):
        reason = self._combination_reason()
        return {
            "patterns": self._combine_patterns,
            "cakes": self._combine_cakes,
            "ready": reason is None,
            "reason": reason,
            "factor": float(self.configuration.img_model.factor),
            "configurations": [
                {
                    "index": i,
                    "imageName": Path(c.img_model.filename).name,
                    "calibrated": c.calibration_model.is_calibrated,
                    "factor": float(c.img_model.factor),
                }
                for i, c in enumerate(self._model.configurations)
            ],
            "backends": self._combination_backend.copy(),
        }

    def _remember_configuration_workflow(self):
        self._configuration_workflows[str(self._model.configuration_ind)] = {
            name: deepcopy(getattr(self, name)) for name in self._configuration_fields
        }
        self._configuration_workflows[str(self._model.configuration_ind)][
            "custom_calibrant"
        ] = (
            {key: self._custom_calibrant[key] for key in ("name", "content")}
            if self._custom_calibrant
            else None
        )

    def _configuration_select(self, index):
        index = finite(
            index, "Configuration", 0, len(self._model.configurations) - 1, True
        )
        if index == self._model.configuration_ind:
            return self._snapshot(include_image=True)
        self._remember_configuration_workflow()
        self._integration_reset_autoprocess()
        self._integration_auto_save = False
        self._model.select_configuration(index)
        c = self.configuration.calibration_model
        saved = self._configuration_workflows.get(str(index), {})
        defaults = {
            "_has_image": self.configuration.img_model.img_data is not None,
            "_calibration_image_shape": None,
            "_setup_confirmed": c.is_calibrated,
            "_geometry_source": "loaded" if c.is_calibrated else "none",
            "_fit_dirty": False,
            "_fit_rms": None,
            "_calibrant_name": "LaB6",
            "_workflow": self._workflow.copy(),
        }
        for name, value in defaults.items():
            setattr(self, name, deepcopy(saved.get(name, value)))
        # The actual loaded pixels, not metadata, determine availability.
        self._has_image = self.configuration.img_model.img_data is not None
        custom = saved.get("custom_calibrant")
        if custom:
            self._install_custom_calibrant(custom["name"], custom["content"])
        else:
            self._custom_calibrant = None
            self._calibrant_directory = None
        self._set_calibrant()
        c.use_dioptrin = self._engine.id == "dioptrin"
        if c.is_calibrated:
            c.calibrant.setWavelength_change2th(c.pattern_geometry.wavelength)
            c.create_cake_geometry()
        self._inspection = None
        self._ring_cache = None
        self._calculate()
        return {**self._snapshot(include_image=True), "clearImage": not self._has_image}

    def _combination_settings(self, patterns=None, cakes=None, factor=None):
        enabling = patterns is True or cakes is True
        patterns = (
            self._combine_patterns
            if patterns is None
            else boolean(patterns, "Combine patterns")
        )
        cakes = (
            self._combine_cakes if cakes is None else boolean(cakes, "Combine cakes")
        )
        factor = (
            self.configuration.img_model.factor
            if factor is None
            else finite(factor, "Detector factor")
        )
        reason = self._combination_reason()
        if enabling and reason:
            raise ValueError(reason)
        self._combine_patterns, self._combine_cakes = patterns, cakes
        # This is Qt ConfigurationController's factor, applied to this detector
        # by ImgModel before either ordinary or combined integration.
        self.configuration.img_model.factor = float(factor)
        self._calculate()
        return self._snapshot(include_image=True)

    def _calculate_combination(self):
        self._combined_pattern = None
        self._combined_cake_data = None
        self._combination_backend = {}
        if self._combination_reason():
            return
        if not (self._combine_patterns or self._combine_cakes):
            return
        fallback = None
        if self._engine.id == "dioptrin":
            fallback = native_unavailable(
                self._model.configurations, self.configuration
            )
            if fallback is None:
                self._calculate_native_combination()
                return
        if self._combine_patterns:
            self._combined_pattern = self._model._integrate_combined_1d()
            self._combination_backend["pattern"] = "pyFAI"
        if self._combine_cakes:
            # Qt's existing entry point activates individual cakes. Hold its
            # notifications and restore the desktop's explicit processing policy.
            try:
                with self._model._combined_cake.hold(flush=False):
                    self._model.calculate_combined_cake()
            finally:
                self._disable_automatic_processing(self._model)
            unit = (
                "2th_deg"
                if self.configuration.integration_unit == "d_A"
                else self.configuration.integration_unit
            )
            self._combined_cake_data = (
                self._model._cake_data,
                self._model._cake_tth,
                self._model._cake_azi,
                unit,
            )
            self._combination_backend["cake"] = "pyFAI"

        if fallback:
            self._combination_backend = {
                key: f"pyFAI ({fallback})" for key in self._combination_backend
            }

    def _calculate_native_combination(self):
        c = self.configuration
        unit = "2th_deg" if c.integration_unit == "d_A" else c.integration_unit
        key, masks, radial_range, azimuth_range = native_combination_key(
            self._model.configurations,
            unit,
            c.calibration_model.polarization_factor,
        )
        if key != self._native_combination_key or self._native_combination is None:
            self._native_combination = {}
            self._native_combination_key = key

        def integrator_for(target):
            # Dioptrin caches one prepared 2D grid per Integrator. Keep the
            # one-row pattern grid separate from the multi-row cake grid so
            # displaying both does not rebuild both tables on every image.
            if target not in self._native_combination:
                self._native_combination[target] = make_native_multi(
                    self._model.configurations,
                    unit,
                    c.calibration_model.polarization_factor,
                    masks,
                    radial_range,
                )
            return self._native_combination[target]

        images = [
            np.ascontiguousarray(config.img_model.img_data, dtype=np.float64)
            for config in self._model.configurations
        ]
        bins = c.integration_rad_points
        if bins is None:
            bins = c.calibration_model.calculate_number_of_pattern_points(
                c.img_model.img_data.shape, 2
            )
        if self._combine_patterns:
            result = integrator_for("pattern").integrate2d(
                images,
                bins,
                1,
                azimuthal_range=azimuth_range,
                normalization="absolute",
            )
            x = np.asarray(result.radial)
            if c.integration_unit == "d_A":
                x = (
                    c.calibration_model.pattern_geometry.wavelength
                    * 1e10
                    / (2 * np.sin(np.deg2rad(x) / 2))
                )
            self._combined_pattern = Pattern(
                x, np.asarray(result.intensity).reshape(-1)
            )
            self._combination_backend["pattern"] = "Dioptrin"
        if self._combine_cakes:
            result = integrator_for("cake").integrate2d(
                images,
                bins,
                c.cake_azimuth_points,
                azimuthal_range=azimuth_range,
                normalization="absolute",
            )
            self._combined_cake_data = (
                np.asarray(result.intensity).reshape(c.cake_azimuth_points, bins),
                np.asarray(result.radial),
                np.rad2deg(result.azimuthal),
                unit,
            )
            self._combination_backend["cake"] = "Dioptrin"

    def _combined_pattern_display(self):
        pattern = self._combined_pattern
        if pattern is None:
            return None
        x, y = pattern.data
        return {
            "x": np.asarray(x).tolist(),
            "y": values(y),
            "unit": self.configuration.integration_unit,
            **self._pattern_reference_data(self.configuration.integration_unit),
        }

    def _cake_arrays(self):
        if self._combine_cakes:
            return self._combined_cake_data
        c = self.configuration.calibration_model
        return c.cake_img, c.cake_tth, c.cake_azi, "2th_deg"

    def _save_combined_pattern(self, path=None, suggested_name=None):
        if (
            not self._combine_patterns
            or self._combined_pattern is None
            or self._integration_dirty
        ):
            raise ValueError(
                "Enable Combine patterns and integrate the detectors before saving."
            )
        path = self._path(path, "pattern", save=True)
        if path is None:
            return {"cancelled": True}
        if not Path(path).suffix:
            path += ".xy"
        if Path(path).suffix.lower() not in {".xy", ".chi", ".dat", ".fxye"}:
            raise ValueError("Use XY, CHI, DAT or FXYE format for a combined pattern.")
        # Same xypattern writer as DioptasModel.save_combined_pattern; save the
        # result actually displayed, without recalculating a different backend.
        self._combined_pattern.save(path, unit=self.configuration.integration_unit)
        self.configuration.working_directories["pattern"] = str(Path(path).parent)
        return {"savedPath": path}
