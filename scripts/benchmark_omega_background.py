# SPDX-License-Identifier: MIT
"""Reproducible CPU scaling and optional full TIFF-stack pipeline benchmark.

Run from the checkout: python -m scripts.benchmark_omega_background --pipeline
For an existing numbered scan with confirmed omega0/omegaR sidecars:
  ... --real-seed /path/sample_003.tif --output /path/report.json
Actual results use a temporary directory and are removed after measurement.
"""

import argparse
from dataclasses import asdict
import json
import os
from pathlib import Path
import platform
import statistics
import tempfile
import time
from types import SimpleNamespace

import numpy as np
from PIL import Image

from dioptas.model.omega_background import (
    OmegaBackgroundTask,
    subtract_omega_background,
)
from dioptas.model.util.omega_background import (
    ArPLSParameters,
    arpls_rows,
    backend_name,
)


def make_data(pixels, frames):
    """All pixels noisy; sparse narrow peaks and gently curved background."""
    rng = np.random.default_rng(20261024)
    x = np.arange(frames)
    rows = rng.normal(0, 3, (pixels, frames))
    rows += 100 + 0.1 * x + 5 * np.sin(x / frames * np.pi)
    for start in range(0, pixels, 4096):
        end = min(start + 4096, pixels)
        centers = rng.uniform(frames * 0.15, frames * 0.85, end - start)
        amplitudes = rng.choice([0.0, 500.0], end - start, p=[0.9, 0.1])
        rows[start:end] += amplitudes[:, None] * np.exp(
            -0.5 * ((x - centers[:, None]) / 1.1) ** 2
        )
    return rows


def timed_compute(rows, p, workers):
    start_time = time.perf_counter()
    capped = steps = 0
    checksum = 0.0
    for start in range(0, len(rows), 4096):
        baseline, counts, converged = arpls_rows(
            rows[start : start + 4096], p, workers=workers
        )
        checksum += float(baseline.sum())
        capped += int(np.count_nonzero(~converged))
        steps += int(counts.sum())
    return dict(
        seconds=time.perf_counter() - start_time,
        checksum=checksum,
        unconverged_pixels=capped,
        mean_iterations=steps / len(rows),
    )


def pipeline(series, p, workers, folder, export_frames, exclude_zero_padding=False):
    result = subtract_omega_background(
        OmegaBackgroundTask(
            series,
            parameters=p,
            workers=workers,
            export_frames=export_frames,
            exclude_zero_padding=exclude_zero_padding,
        ),
        folder,
    )
    metadata = result.metadata
    return dict(
        seconds=metadata["seconds"],
        frames=metadata["frames"],
        image_shape=metadata["image_shape"],
        backend=metadata["backend"],
        workers=workers,
        export_frames=export_frames,
        unconverged_pixels=metadata["unconverged_pixels"],
        mean_iterations=metadata["mean_iterations"],
        masked_pixels=metadata["masked_pixels"],
        exclude_zero_padding=exclude_zero_padding,
        output_bytes=sum(p.stat().st_size for p in folder.rglob("*") if p.is_file()),
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frames", type=int, default=180)
    parser.add_argument("--height", type=int, default=512)
    parser.add_argument("--width", type=int, default=512)
    parser.add_argument("--workers", default="1,4,8")
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--smoothness", type=float, default=1e4)
    parser.add_argument("--iterations", type=int, default=30)
    parser.add_argument("--pipeline", action="store_true")
    parser.add_argument("--real-seed")
    parser.add_argument(
        "--exclude-zero-padding",
        action="store_true",
        help="For measured scans only: exclude pixels zero in any frame",
    )
    parser.add_argument("--output")
    args = parser.parse_args()
    workers = [int(value) for value in args.workers.split(",")]
    if min(args.frames, args.height, args.width, args.repeats) < 1:
        parser.error("Sizes and repeats must be positive.")
    p = ArPLSParameters(smoothness=args.smoothness, max_iterations=args.iterations)
    report = dict(
        platform=platform.platform(),
        machine=platform.machine(),
        logical_cpus=os.cpu_count(),
        backend=backend_name(),
        parameters=asdict(p),
        seed=20261024,
        workload="synthetic; all pixels noisy, 10% have a narrow reflection",
        array_shape_pixels_frames=[args.height * args.width, args.frames],
        compute=[],
    )
    rows = make_data(args.height * args.width, args.frames)
    arpls_rows(
        rows[:256], p, workers=max(workers)
    )  # initialize OpenMP outside timed regions
    for count in workers:
        runs = [timed_compute(rows, p, count) for _ in range(args.repeats)]
        result = dict(
            workers=count,
            runs=runs,
            median_seconds=statistics.median(r["seconds"] for r in runs),
        )
        report["compute"].append(result)
        print(json.dumps(result), flush=True)
    reference_rows = rows[:256]
    start = time.perf_counter()
    scipy = arpls_rows(reference_rows, p, backend="scipy")
    scipy_seconds = time.perf_counter() - start
    start = time.perf_counter()
    native = arpls_rows(reference_rows, p, workers=1)
    native_seconds = time.perf_counter() - start
    report["reference_check"] = dict(
        pixels=len(reference_rows),
        scipy_seconds=scipy_seconds,
        native_serial_seconds=native_seconds,
        max_absolute_baseline_difference=float(np.max(np.abs(scipy[0] - native[0]))),
    )
    with tempfile.TemporaryDirectory(prefix="dioptas-omega-benchmark-") as temp:
        folder = Path(temp)
        if args.pipeline:
            sources = folder / "sources"
            sources.mkdir()
            stack = rows.T.reshape(args.frames, args.height, args.width)
            files = []
            for i, image in enumerate(stack):
                path = sources / f"synthetic_{i:04d}.tif"
                Image.fromarray(image.astype(np.float32)).save(path)
                files.append(str(path))
            series = SimpleNamespace(
                files=tuple(files),
                frame_numbers=tuple(range(args.frames)),
                omega_bounds=np.column_stack(
                    [np.arange(args.frames) * 0.5, np.arange(args.frames) * 0.5 + 0.5]
                ),
                source_records=tuple({} for _ in files),
                angle_source="synthetic, 0.5 degree steps",
            )
            report["synthetic_pipeline"] = pipeline(
                series, p, max(workers), folder / "synthetic_result", True
            )
            print(json.dumps(report["synthetic_pipeline"]), flush=True)
        if args.real_seed:
            from dioptas.model.rotation_series import import_series

            series = import_series(args.real_seed)
            report["measured_scan_pipeline"] = pipeline(
                series,
                p,
                max(workers),
                folder / "measured_result",
                True,
                args.exclude_zero_padding,
            )
            report["measured_scan_pipeline"]["scan"] = Path(args.real_seed).stem.rsplit(
                "_", 1
            )[0]
            print(json.dumps(report["measured_scan_pipeline"]), flush=True)
    print(json.dumps(report, indent=2), flush=True)
    if args.output:
        Path(args.output).write_text(
            json.dumps(report, indent=2) + "\n", encoding="utf-8"
        )


if __name__ == "__main__":
    main()
