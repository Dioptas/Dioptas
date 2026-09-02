# SPDX-License-Identifier: MIT

"""Worker-isolated map integration."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .MapModel import MapPointInfo
from .worker_configuration import (
    WorkerConfigurationState,
    build_worker_configuration,
)


@dataclass(frozen=True)
class MapIntegrationResult:
    pattern_x: np.ndarray
    pattern_intensities: np.ndarray
    point_infos: tuple[tuple[str, int], ...]
    filepaths: tuple[str, ...]
    pattern_unit: str


def compute_map_integration(
    state: WorkerConfigurationState,
    filepaths: list[str],
    callback=None,
) -> MapIntegrationResult:
    configuration = build_worker_configuration(state)
    map_model = configuration.map_model
    map_model.load(filepaths, callback_fn=callback)
    return MapIntegrationResult(
        pattern_x=np.asarray(map_model.pattern_x),
        pattern_intensities=np.asarray(map_model.pattern_intensities),
        point_infos=tuple(
            (info.filepath, info.frame_index) for info in map_model.point_infos
        ),
        filepaths=tuple(filepaths),
        pattern_unit=str(map_model.pattern_unit),
    )


def apply_map_integration(map_model, result: MapIntegrationResult) -> None:
    point_infos = [
        MapPointInfo(filepath, frame_index)
        for filepath, frame_index in result.point_infos
    ]
    map_model.set_integration_results(
        result.pattern_x,
        result.pattern_intensities,
        point_infos,
        list(result.filepaths),
        pattern_unit=result.pattern_unit,
    )
