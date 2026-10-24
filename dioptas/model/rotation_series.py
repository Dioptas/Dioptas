# SPDX-License-Identifier: MIT
"""File/angle translation for experimental position-first rotation peak hunting."""

from __future__ import annotations

import csv
import hashlib
import json
import re
from dataclasses import asdict, dataclass
from importlib.metadata import version
from pathlib import Path

import numpy as np

from .single_crystal import quality_labels


@dataclass(frozen=True)
class RotationSeries:
    files: tuple[str, ...]
    frame_numbers: tuple[int, ...]
    omega_bounds: np.ndarray
    angle_source: str
    source_records: tuple[dict, ...]

    def __post_init__(self):
        from phasesmith.experimental.rotation import angle_segments

        bounds, _ = angle_segments(self.omega_bounds)
        if len(self.files) != len(bounds) or len(self.frame_numbers) != len(bounds):
            raise ValueError(
                "Each frame needs a file, a frame number and omega bounds."
            )
        bounds.flags.writeable = False
        object.__setattr__(self, "omega_bounds", bounds)


@dataclass(frozen=True)
class SeriesTask:
    series: RotationSeries
    mask: np.ndarray
    spot_options: dict
    link_radius: float = 5.0
    exclude_zero_padding: bool = False
    gain: float = 1.0
    read_noise: float = 0.0
    saturation: float | None = None
    transformations: tuple[str, ...] = ()


@dataclass(frozen=True)
class SeriesPositions:
    table: object
    metadata: dict


@dataclass(frozen=True)
class SeriesFramePreview:
    """One owned read-only source image and immutable, unlinked frame detections."""

    index: int
    image: np.ndarray
    table: object


def series_files(seed: str | Path) -> tuple[tuple[str, ...], tuple[int, ...]]:
    """Same filename prefix/extension, sorted by numeric suffix; never mix runs."""
    seed = Path(seed)
    match = re.fullmatch(r"(.+?)(\d+)(\.[^.]+)", seed.name)
    if match is None:
        raise ValueError("Choose a numbered frame, e.g. sample_001.tif.")
    prefix, _, suffix = match.groups()
    pattern = re.compile(
        re.escape(prefix) + r"(\d+)" + re.escape(suffix), re.IGNORECASE
    )
    found = []
    for path in seed.parent.iterdir():
        item = pattern.fullmatch(path.name)
        if item and path.is_file():
            found.append((int(item[1]), str(path)))
    found.sort()
    if len(found) < 2:
        raise ValueError("A rotation series needs at least two matching frames.")
    if len({n for n, _ in found}) != len(found):
        raise ValueError("Duplicate numeric frame IDs in this series.")
    return tuple(p for _, p in found), tuple(n for n, _ in found)


def sidecar_record(filename: str) -> dict:
    """Preserve raw motor readings; chi/detector are never relabelled as omega."""
    path = Path(filename)
    choices = [
        path.with_name(path.name + ".txt"),
        path.with_name(path.parent.name + path.name + ".txt"),
    ]
    sidecar = next((p for p in choices if p.exists()), None)
    if sidecar is None:
        return {}
    text = sidecar.read_text(encoding="utf-8")
    values = {}
    for line in text.splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            try:
                values[key.strip()] = float(value)
            except ValueError:
                continue
    return dict(
        path=str(sidecar),
        sha256=hashlib.sha256(sidecar.read_bytes()).hexdigest(),
        values=values,
    )


def import_series(
    seed: str | Path, *, manual_angles: tuple[float, float, float] | None = None
):
    """Use explicit omega0/omegaR or an explicit (first start,step,width) override.

    Manual start applies to the lowest filename number. Missing numbers retain
    their angular gaps. Manual overrides retain every original sidecar record.
    No angle is inferred from exposure time, chi or detector motor values.
    """
    files, numbers = series_files(seed)
    records = tuple(sidecar_record(path) for path in files)
    if manual_angles is None:
        if any(not {"omega0", "omegaR"} <= set(r.get("values", {})) for r in records):
            raise ValueError(
                "Omega metadata are missing. Enter the first start angle, step and width."
            )
        starts = np.array([r["values"]["omega0"] for r in records])
        widths = np.array([r["values"]["omegaR"] for r in records])
        source = "sidecar omega0=start, omegaR=exposure width; interpretation confirmed at import"
    else:
        start, step, width = manual_angles
        if not np.isfinite([start, step, width]).all() or step == 0 or width <= 0:
            raise ValueError("Angles must be finite, step nonzero and width positive.")
        starts = start + (np.asarray(numbers) - numbers[0]) * step
        widths = np.full(len(files), np.copysign(width, step))
        source = (
            f"user override: first start={start}, step={step}, width={width} degrees"
        )
    return RotationSeries(
        files, numbers, np.column_stack([starts, starts + widths]), source, records
    )


def read_frame(filename: str, transformations=()) -> np.ndarray:
    """Match Dioptas detector orientation; worker-local readers have no Qt state."""
    from PIL import Image
    from .ImgModel import TRANSFORMATION_FUNCTIONS

    try:
        with Image.open(filename) as image:
            data = np.asarray(image)[::-1].copy()
    except (OSError, ValueError):
        import fabio

        with fabio.open(filename) as image:
            data = np.asarray(image.data)[::-1].copy()
    if data.ndim != 2 or data.dtype.kind not in "fiu":
        raise ValueError(
            "Rotation frames must contain two-dimensional detector counts."
        )
    for name in transformations:
        data = TRANSFORMATION_FUNCTIONS[name](data)
    return np.ascontiguousarray(data)


def locate_positions(task: SeriesTask, progress=None, preview=None) -> SeriesPositions:
    """Read one frame at a time; source and masks are fingerprinted by PhaseSmith."""
    from phasesmith import _core
    from phasesmith.experimental import rotation
    from phasesmith.experimental.spots import SpotOptions

    shape = task.mask.shape
    cached = {}
    current_image = None

    def load(i):
        nonlocal current_image
        data = read_frame(task.series.files[i], task.transformations)
        if data.shape != shape:
            raise ValueError(
                "Series frame dimensions do not match the current detector mask."
            )
        mask = task.mask.copy()
        mask |= ~np.isfinite(data)
        if task.exclude_zero_padding:
            mask |= data == 0
        cached[i] = mask
        data.flags.writeable = False
        current_image = data
        return data

    def mask(i):
        return cached.pop(i)

    def completed(index, table):
        if preview is not None:
            preview(SeriesFramePreview(index, current_image, table))

    options = SpotOptions(**task.spot_options)
    rotation_options = rotation.RotationOptions(link_radius=task.link_radius)
    table = rotation.locate_series(
        load,
        task.series.omega_bounds,
        mask_loader=mask,
        spot_options=options,
        rotation_options=rotation_options,
        gain=task.gain,
        read_noise=task.read_noise,
        saturation=task.saturation,
        progress=progress,
        frame_finished=completed if preview is not None else None,
    )
    metadata = dict(
        schema="dioptas.experimental.rotation-positions.v1",
        algorithm="adjacent-frame-position-hunt-v1",
        phasesmith_version=version("phasesmith"),
        native_engine_sha256=hashlib.sha256(
            Path(_core.__file__).read_bytes()
        ).hexdigest(),
        adapter_sha256=hashlib.sha256(Path(rotation.__file__).read_bytes()).hexdigest(),
        dioptas_adapter_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        application_mask_policy="fixed current combined mask applied to every frame",
        source_files=task.series.files,
        frame_numbers=task.series.frame_numbers,
        frame_image_mask_hashes=table.frame_hashes,
        omega_bounds=table.omega_bounds.tolist(),
        angle_source=task.series.angle_source,
        source_records=task.series.source_records,
        transformations=task.transformations,
        exclude_zero_padding=task.exclude_zero_padding,
        spot_options=asdict(options),
        rotation_options=asdict(rotation_options),
        gain=task.gain,
        read_noise=task.read_noise,
        saturation=task.saturation,
        positions=len(table),
        observations=len(table.observations),
        coordinates="x=column,y=row,zero-based pixel centers; omega in degrees; exposure midpoints",
        interpretation="unindexed position candidates; positive detected-count weights for means; "
        "not integrated rocking intensities or reciprocal vectors; no symmetry assignment",
    )
    return SeriesPositions(table, metadata)


def export_positions(result: SeriesPositions, filename: str):
    """Track CSV, all frame observations, and JSON provenance; original data untouched."""
    path = Path(filename).with_suffix(".csv")
    observations = path.with_name(path.stem + "_observations.csv")
    metadata = path.with_suffix(".json")
    t = result.table
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "track_id",
                *t.columns,
                "first_frame",
                "end_frame_exclusive",
                "flags",
                "quality",
            ]
        )
        for i, (values, span, flag) in enumerate(
            zip(t.values, t.frame_ranges, t.flags)
        ):
            writer.writerow(
                [i + 1, *values, *span, int(flag), quality_labels(int(flag))]
            )
    with observations.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "track_id",
                "frame_index",
                "frame_number",
                "source_file",
                "x",
                "y",
                "omega",
            ]
        )
        for track, frame, x, y, omega in t.observations:
            frame = int(frame)
            writer.writerow(
                [
                    int(track) + 1,
                    frame,
                    result.metadata["frame_numbers"][frame],
                    result.metadata["source_files"][frame],
                    x,
                    y,
                    omega,
                ]
            )
    metadata.write_text(
        json.dumps(result.metadata, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    return path, observations, metadata
