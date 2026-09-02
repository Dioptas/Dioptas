# SPDX-License-Identifier: MIT

"""Worker-isolated batch integration."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from xypattern import Pattern
from xypattern.auto_background import SmoothBrucknerBackground

from .worker_configuration import (
    WorkerConfigurationState,
    build_worker_configuration,
)


@dataclass(frozen=True)
class BatchIntegrationTask:
    configuration: WorkerConfigurationState
    files: tuple[str, ...]
    pos_map: np.ndarray
    pos_map_all: np.ndarray
    start: int
    stop: int
    step: int
    use_all: bool


@dataclass(frozen=True)
class BatchIntegrationResult:
    data: np.ndarray
    binning: np.ndarray
    pos_map: np.ndarray
    used_mask: str | None
    used_mask_shape: tuple[int, ...] | None
    used_calibration: str | None


@dataclass(frozen=True)
class BatchBackgroundTask:
    binning: np.ndarray
    data: np.ndarray
    parameters: tuple


def compute_batch_integration(
    task: BatchIntegrationTask,
    callback=None,
) -> BatchIntegrationResult:
    configuration = build_worker_configuration(task.configuration)
    batch_model = configuration.batch_model
    batch_model.files = np.asarray(task.files)
    batch_model.pos_map = np.array(task.pos_map, copy=True)
    batch_model.pos_map_all = np.array(task.pos_map_all, copy=True)
    batch_model.raw_available = True
    batch_model.n_img_all = len(task.pos_map_all)
    batch_model.integrate_raw_data(
        task.start,
        task.stop,
        task.step,
        task.use_all,
        callback_fn=callback,
    )
    return BatchIntegrationResult(
        data=np.asarray(batch_model.data),
        binning=np.asarray(batch_model.binning),
        pos_map=np.asarray(batch_model.pos_map),
        used_mask=batch_model.used_mask,
        used_mask_shape=batch_model.used_mask_shape,
        used_calibration=batch_model.used_calibration,
    )


def apply_batch_integration(batch_model, result: BatchIntegrationResult) -> None:
    batch_model.data = result.data
    batch_model.binning = result.binning
    batch_model.pos_map = result.pos_map
    batch_model.bkg = None
    batch_model.n_img = len(result.data)
    batch_model.used_mask = result.used_mask
    batch_model.used_mask_shape = result.used_mask_shape
    batch_model.used_calibration = result.used_calibration


def compute_batch_background(
    task: BatchBackgroundTask,
    callback=None,
) -> np.ndarray:
    """Extract per-pattern backgrounds without touching the live model."""
    background = np.zeros(task.data.shape)
    extractor = SmoothBrucknerBackground(*task.parameters)
    for index, intensity in enumerate(task.data):
        if callback is not None and not callback(index + 1):
            break
        background[index] = extractor.extract_background(
            Pattern(task.binning, intensity)
        )
    return background
