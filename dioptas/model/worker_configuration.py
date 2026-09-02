# SPDX-License-Identifier: MIT

"""Capture and rebuild a Configuration for isolated background workers."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass

import numpy as np

from .Configuration import Configuration
from .state.hdf5 import params_from_dict, params_to_dict
from .state.params import apply_params


@dataclass(frozen=True)
class WorkerConfigurationState:
    configuration: dict
    image: dict
    calibration: dict
    mask: dict
    mask_data: np.ndarray
    plugins: dict


def capture_worker_configuration(configuration: Configuration) -> WorkerConfigurationState:
    """Copy serializable processing state without retaining live models."""
    return WorkerConfigurationState(
        configuration=params_to_dict(configuration.params),
        image=params_to_dict(configuration.img_model.params),
        calibration=params_to_dict(configuration.calibration_model.params),
        mask=params_to_dict(configuration.mask_model.params),
        mask_data=np.array(configuration.mask_model.get_img(), dtype=bool, copy=True),
        plugins={
            name: {
                "enabled": bool(entry.enabled),
                "settings": (
                    deepcopy(entry.plugin.get_settings())
                    if entry.plugin.has_settings
                    else {}
                ),
            }
            for name, entry in configuration.mask_plugin_manager.plugins.items()
        },
    )


def build_worker_configuration(state: WorkerConfigurationState) -> Configuration:
    """Construct an unconnected model graph owned entirely by a worker."""
    configuration = Configuration()
    configuration.auto_integrate_pattern = False
    configuration.auto_integrate_cake = False
    configuration.auto_save_integrated_pattern = False

    # Some parameter changes explicitly request recomputation even while auto
    # integration is disabled. Discard those requests while the disconnected
    # worker graph is being populated; its task will integrate only once.
    with (
        configuration.pattern_integration.hold(flush=False),
        configuration.cake_integration.hold(flush=False),
    ):
        _apply_dict(configuration.calibration_model.params, state.calibration)
        _apply_dict(
            configuration.params,
            state.configuration,
            exclude={
                "auto_integrate_pattern",
                "auto_integrate_cake",
                "auto_save_integrated_pattern",
            },
        )
        _apply_dict(configuration.mask_model.params, state.mask)
        configuration.mask_model.set_mask_data(np.array(state.mask_data, copy=True))

        for name, plugin_state in state.plugins.items():
            manager = configuration.mask_plugin_manager
            if name not in manager.plugins:
                continue
            settings = plugin_state.get("settings") or {}
            if settings:
                manager.update_plugin_settings(name, settings)
            manager.set_enabled(name, bool(plugin_state.get("enabled", False)))

        _apply_dict(configuration.img_model.params, state.image)
        configuration.img_model.set_transformations(
            list(state.image.get("transformations", []))
        )
    return configuration


def _apply_dict(target, values: dict, exclude: set[str] | None = None) -> None:
    apply_params(
        target,
        params_from_dict(type(target), values),
        exclude=exclude,
    )
