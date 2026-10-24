# SPDX-License-Identifier: MIT
"""Bounded-memory rotation-series background subtraction and atomic export.

The baseline is fitted along omega, independently at each detector pixel.
Input and TIFF output use the source detector's native orientation. Arrays
never pass through the GUI's image corrections or integer image exporter.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import time
from typing import TYPE_CHECKING

import fabio
import numpy as np
from PIL import Image, TiffImagePlugin

from .util.omega_background import (
    ArPLSParameters,
    arpls_rows,
    backend_name,
    default_workers,
)

if TYPE_CHECKING:
    from .rotation_series import RotationSeries

CREDIT = (
    "Omega-sequence background estimation inspired by Konstantin Glazyrin's "
    "background-sc (https://gitlab.desy.de/konstantin.glazyrin/background-sc). "
    "Independent Dioptas implementation of arPLS: Baek et al., Analyst 140 "
    "(2015), 250–257, doi:10.1039/C4AN01061B. No background-sc code reused."
)


class BackgroundCancelled(Exception):
    """Cancelled between reads, compute tiles or exported frames."""


@dataclass(frozen=True)
class OmegaBackgroundTask:
    series: RotationSeries
    parameters: ArPLSParameters = ArPLSParameters()
    workers: int = 0
    tile_pixels: int = 4096
    export_frames: bool = True
    mask: np.ndarray | None = None  # True = exclude; native detector orientation
    exclude_zero_padding: bool = False
    backend: str = "auto"


@dataclass(frozen=True)
class OmegaBackgroundResult:
    directory: Path
    metadata: dict


def native_detector_mask(mask, transformations=()):
    """Undo user transforms, then Dioptas's file-loading vertical flip."""
    from .ImgModel import TRANSFORMATION_FUNCTIONS

    inverse = {
        "flipud": "flipud",
        "fliplr": "fliplr",
        "rotate_matrix_m90": "rotate_matrix_p90",
        "rotate_matrix_p90": "rotate_matrix_m90",
    }
    data = np.asarray(mask, dtype=bool)
    for name in reversed(transformations):
        data = TRANSFORMATION_FUNCTIONS[inverse[name]](data)
    return np.ascontiguousarray(data[::-1])


def display_detector_mask(mask, transformations=()):
    """Map an exported native detector mask into Dioptas display coordinates."""
    from .ImgModel import TRANSFORMATION_FUNCTIONS

    data = np.asarray(mask, dtype=bool)[::-1]
    for name in transformations:
        data = TRANSFORMATION_FUNCTIONS[name](data)
    return np.ascontiguousarray(data)


def _check_progress(callback, stage, done, total):
    if callback is not None and callback(stage, done, total) is False:
        raise BackgroundCancelled("Omega background subtraction cancelled.")


def _read(filename):
    # Use one-frame files from RotationSeries. Refuse silently taking only
    # the first image of a container; its frame/angle mapping is ambiguous.
    with fabio.open(str(filename)) as reader:
        if reader.nframes != 1:
            raise ValueError(
                "Select one image file per omega frame; multi-frame containers need an explicit angle mapping."
            )
        data = np.array(reader.data, copy=True)
        header = {str(k): str(v) for k, v in reader.header.items()}
    if data.ndim != 2 or data.dtype.kind not in "fiu":
        raise ValueError("Omega frames must be two-dimensional real detector images.")
    return data, header


def _write_tiff(path, data, description):
    info = TiffImagePlugin.ImageFileDirectory_v2()
    info[270] = json.dumps(description, allow_nan=False)
    array = np.ascontiguousarray(data, dtype=np.float32)
    Image.fromarray(array).save(path, tiffinfo=info)


def _validate_task(task):
    n = len(task.series.files)
    bounds = np.asarray(task.series.omega_bounds, dtype=float)
    if n < 3 or bounds.shape != (n, 2) or not np.isfinite(bounds).all():
        raise ValueError("At least three frames with finite omega bounds are required.")
    midpoints = bounds.mean(axis=1)
    steps = np.diff(midpoints)
    if steps[0] == 0 or not np.allclose(steps, steps[0], rtol=1e-6, atol=1e-8):
        raise ValueError(
            "arPLS requires uniformly spaced omega frames. Split the scan at missing frames or step changes."
        )
    if not isinstance(task.tile_pixels, int) or not 1 <= task.tile_pixels <= 65536:
        raise ValueError("Tile size must be an integer from 1 to 65536 pixels.")
    if not isinstance(task.workers, int) or not 0 <= task.workers <= 128:
        raise ValueError("CPU workers must be an integer from 0 (automatic) to 128.")
    if task.backend not in ("auto", "native", "scipy"):
        raise ValueError("Unknown background backend.")
    if len(set(task.series.files)) != n or len(set(task.series.frame_numbers)) != n:
        raise ValueError("Each frame needs a unique source file and frame number.")


def subtract_omega_background(task, output_directory, *, progress=None):
    """Process into a NEW directory; cancellation/failure removes staging data.

    Temporary disk storage holds two (pixels, frames) memory maps, requiring
    approximately 12 bytes per pixel/frame, plus optional TIFF output. The
    numerical workspace is bounded by tile_pixels, independently of image size.
    Masked pixels are retained unchanged, and exported in mask.tif (1=exclude).
    A pixel invalid/zero-padding in any frame is excluded for the whole scan.
    """
    _validate_task(task)
    target = Path(output_directory).expanduser().absolute()
    if target.exists():
        raise FileExistsError(
            "Choose a new output directory; existing results are never overwritten."
        )
    if not target.parent.is_dir():
        raise ValueError("The output parent directory does not exist.")
    started = time.perf_counter()
    staging = Path(tempfile.mkdtemp(prefix=".omega-background-", dir=target.parent))
    try:
        result = _process(task, staging, progress, started)
        # Windows cannot remove memory-mapped files while handles are open;
        # _process closes its maps before returning on every path.
        if target.exists():
            raise FileExistsError(
                "The output directory was created by another operation."
            )
        staging.rename(target)
        return OmegaBackgroundResult(target, result)
    finally:
        if staging.exists():
            shutil.rmtree(staging)


def _process(task, folder, progress, started):
    files = task.series.files
    nframes = len(files)
    _check_progress(progress, "Reading frames", 0, nframes)
    first, _ = _read(files[0])
    shape = first.shape
    pixels = first.size
    mask = (
        np.zeros(shape, bool)
        if task.mask is None
        else np.array(task.mask, dtype=bool, copy=True)
    )
    if mask.shape != shape:
        raise ValueError("The detector mask does not match the series frames.")
    required_bytes = (
        pixels * nframes * (16 if task.export_frames else 12)
        + pixels * 21
        + nframes * 65536
    )
    if shutil.disk_usage(folder).free < required_bytes + 64 * 1024**2:
        raise OSError(
            "Insufficient free disk space for the temporary stack and exported frames."
        )
    source_records = []
    raw_path, signal_path = folder / "raw.work", folder / "signal.work"
    raw = np.memmap(raw_path, dtype=np.float64, mode="w+", shape=(pixels, nframes))
    corrected = None
    try:
        for i, filename in enumerate(files):
            _check_progress(progress, "Reading frames", i, nframes)
            image, header = _read(filename)
            if image.shape != shape:
                raise ValueError(f"Frame dimensions differ: {filename}")
            invalid = ~np.isfinite(image)
            mask |= invalid
            if task.exclude_zero_padding:
                mask |= image == 0
            raw[:, i] = image.ravel()
            source_records.append(
                dict(
                    source_file=str(Path(filename).absolute()),
                    frame_number=task.series.frame_numbers[i],
                    omega_bounds=task.series.omega_bounds[i].tolist(),
                    source_header=header,
                    original_dtype=str(image.dtype),
                    image_sha256=hashlib.sha256(
                        np.ascontiguousarray(image).tobytes()
                    ).hexdigest(),
                    source_record=task.series.source_records[i],
                )
            )
        raw.flush()
        read_seconds = time.perf_counter() - started
        del first, image
        processing_start = time.perf_counter()
        corrected = np.memmap(
            signal_path, dtype=np.float32, mode="w+", shape=(pixels, nframes)
        )
        raw_sum = np.empty(pixels, dtype=np.float64)
        background_sum = np.zeros(pixels, dtype=np.float64)
        signal_sum = np.empty(pixels, dtype=np.float64)
        # Diagnostic maps record capped fits instead of concealing convergence failures.
        iteration_map = np.zeros(pixels, dtype=np.uint16)
        convergence_map = np.ones(pixels, dtype=bool)
        worker_count = task.workers or default_workers()
        valid = ~mask.ravel()
        for start in range(0, pixels, task.tile_pixels):
            end = min(start + task.tile_pixels, pixels)
            _check_progress(progress, "Estimating background", start, pixels)
            block = np.array(raw[start:end], copy=True)
            selected = valid[start:end]
            signal = block.copy()
            baseline_sum = np.zeros(end - start)
            if np.any(selected):
                baseline, counts, converged = arpls_rows(
                    block[selected],
                    task.parameters,
                    workers=worker_count,
                    backend=task.backend,
                )
                signal[selected] -= baseline
                baseline_sum[selected] = baseline.sum(axis=1, dtype=np.float64)
                iteration_map[start:end][selected] = counts
                convergence_map[start:end][selected] = converged
            # Preserve signed residuals. No smoothing or clipping is applied to signal.
            corrected[start:end] = signal
            raw_sum[start:end] = block.sum(axis=1, dtype=np.float64)
            background_sum[start:end] = baseline_sum
            signal_sum[start:end] = signal.sum(axis=1, dtype=np.float64)
        corrected.flush()
        processing_seconds = time.perf_counter() - processing_start
        write_start = time.perf_counter()
        excluded = int(mask.sum())
        unconverged = int(np.count_nonzero(~convergence_map & valid))
        metadata = dict(
            schema="dioptas.omega-background.v1",
            algorithm="independent-arpls-natural-boundaries-v1",
            credit=CREDIT,
            created_utc=datetime.now(timezone.utc).isoformat(),
            parameters=asdict(task.parameters),
            weight_floor=1e-8,
            backend="SciPy CPU" if task.backend == "scipy" else backend_name(),
            requested_workers=worker_count,
            frames=nframes,
            image_shape=list(shape),
            omega_bounds=task.series.omega_bounds.tolist(),
            angle_source=task.series.angle_source,
            source_records=source_records,
            source_files=list(files),
            frame_numbers=list(task.series.frame_numbers),
            orientation="native detector-file orientation; original dimensions; no display transforms",
            output_dtype="float32",
            negative_residuals="retained",
            masked_pixels=excluded,
            mask_policy="preserve original values at excluded pixels; mask.tif is 1=exclude",
            exclude_zero_padding=task.exclude_zero_padding,
            unconverged_pixels=unconverged,
            mean_iterations=float(iteration_map[valid].mean())
            if np.any(valid)
            else 0.0,
            uncertainty="No new uncertainty estimates. Original counting noise remains; baseline estimation introduces correlations.",
            export_frames=task.export_frames,
        )
        outputs = {
            "raw_sum.tif": raw_sum,
            "background_sum.tif": background_sum,
            "signal_sum.tif": signal_sum,
            "iterations.tif": iteration_map,
            "unconverged.tif": ~convergence_map,
        }
        for name, data in outputs.items():
            _check_progress(progress, "Writing summary images", 0, len(outputs))
            _write_tiff(
                folder / name, data.reshape(shape), {"kind": name, "credit": CREDIT}
            )
        Image.fromarray(mask.astype(np.uint8)).save(folder / "mask.tif")
        if task.export_frames:
            frames_folder = folder / "frames"
            frames_folder.mkdir()
            for i, record in enumerate(source_records):
                _check_progress(progress, "Exporting corrected frames", i, nframes)
                name = f"frame_{task.series.frame_numbers[i]:06d}.tif"
                record["corrected_file"] = "frames/" + name
                _write_tiff(
                    frames_folder / name, corrected[:, i].reshape(shape), record
                )
                a, b = task.series.omega_bounds[i]
                (frames_folder / (name + ".txt")).write_text(
                    f"omega0 = {a:.17g}\nomegaR = {b - a:.17g}\n",
                    encoding="utf-8",
                )
        timings = dict(
            read=read_seconds,
            processing=processing_seconds,
            write=time.perf_counter() - write_start,
            total=time.perf_counter() - started,
        )
        metadata["seconds"] = timings
        (folder / "manifest.json").write_text(
            json.dumps(metadata, indent=2, allow_nan=False) + "\n", encoding="utf-8"
        )
        _check_progress(progress, "Complete", nframes, nframes)
        return metadata
    finally:
        # Explicit close is needed on Windows, including exceptional paths.
        if corrected is not None:
            corrected._mmap.close()
        raw._mmap.close()
        raw_path.unlink(missing_ok=True)
        signal_path.unlink(missing_ok=True)
