# SPDX-License-Identifier: MIT
"""Opt-in PhaseSmith spot processing boundary, independent of Qt and application state."""

from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import asdict, dataclass
from importlib.metadata import version
from pathlib import Path
from typing import Any

import numpy as np


@dataclass(frozen=True)
class SpotTask:
    """Owned raw-count snapshot. No calibration or crystal model is an inverse input."""

    image: np.ndarray
    mask: np.ndarray
    filename: str
    options: dict[str, Any]
    gain: float = 1.0
    read_noise: float = 0.0
    saturation: float | None = None
    transformations: tuple[str, ...] = ()
    mask_policy: dict[str, Any] | None = None


@dataclass(frozen=True)
class SpotResult:
    table: Any
    metadata: dict[str, Any]


def backend_available() -> bool:
    try:
        from phasesmith.experimental.spots import available
    except ImportError:
        return False
    return available()


def quality_labels(flags: int) -> str:
    """Stable labels match the experimental PhaseSmith flag contract."""
    labels = [
        (1, "Edge"),
        (2, "Masked signal"),
        (4, "Saturated"),
        (8, "Overlap"),
        (16, "Insufficient background"),
        (32, "Large component"),
        (64, "No centroid"),
    ]
    return "; ".join(label for bit, label in labels if flags & bit) or "Unflagged"


def measure_spots(task: SpotTask) -> SpotResult:
    """One native single-threaded pass, called on a background worker."""
    from phasesmith import _core
    from phasesmith.experimental import spots as spots_module
    from phasesmith.experimental.spots import SpotOptions, detect_spots

    options = SpotOptions(**task.options)
    table = detect_spots(
        task.image,
        mask=task.mask,
        options=options,
        gain=task.gain,
        read_noise=task.read_noise,
        saturation=task.saturation,
    )
    metadata = dict(
        schema="dioptas.experimental.spots.v1",
        algorithm="annular-mean-2pass-aperture-v1",
        phasesmith_version=version("phasesmith"),
        native_engine_sha256=hashlib.sha256(
            Path(_core.__file__).read_bytes()
        ).hexdigest(),
        python_adapter_sha256=hashlib.sha256(
            Path(spots_module.__file__).read_bytes()
        ).hexdigest(),
        source_file=task.filename,
        image_shape=list(task.image.shape),
        image_dtype=str(task.image.dtype),
        image_sha256=hashlib.sha256(task.image.tobytes(order="C")).hexdigest(),
        mask_sha256=hashlib.sha256(task.mask.tobytes(order="C")).hexdigest(),
        input="raw detector counts after image orientation transforms; no intensity corrections",
        coordinates="x=column, y=row; zero-based pixel centers; boxes half-open",
        intensity="signed finite-aperture counts; not corrected I(hkl)",
        options=asdict(options),
        image_transformations=list(task.transformations),
        masked_pixels=int(np.count_nonzero(task.mask)),
        gain=task.gain,
        read_noise=task.read_noise,
        mask_policy=task.mask_policy,
        saturation=task.saturation,
        noise_model=table.noise_model,
        rejected_small_components=table.rejected_small_components,
        records=len(table),
        flagged=int(np.count_nonzero(table.flags)),
        native_workers=1,
        uncertainty="conditional independent-pixel propagation; no selection-bias, "
        "background-gradient, missing-signal or cross-spot covariance correction",
    )
    return SpotResult(table, metadata)


def export_spots(result: SpotResult, filename: str | Path) -> tuple[Path, Path]:
    """Export every record and a sidecar with noise, threshold and source provenance."""
    path = Path(filename)
    if path.suffix.lower() != ".csv":
        path = path.with_suffix(".csv")
    sidecar = path.with_suffix(".json")
    table = result.table
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(
            ["spot_id", "x0", "y0", "x1", "y1", *table.columns, "flags", "quality"]
        )
        for i, (bounds, values, flags) in enumerate(
            zip(table.boxes, table.values, table.flags)
        ):
            writer.writerow(
                [i + 1, *bounds, *values, int(flags), quality_labels(int(flags))]
            )
    sidecar.write_text(
        json.dumps(result.metadata, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    return path, sidecar
