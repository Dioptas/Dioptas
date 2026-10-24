# SPDX-License-Identifier: MIT
"""Compare the unchanged external CPU arPLS function with Dioptas, serially.

Supply a reviewed local background-sc script explicitly. It is imported only
for this benchmark, never by Dioptas production code. Its own optional imports
(including memory_profiler) must be available in the benchmark environment.
"""

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import platform
import statistics
import time

import fabio
import numpy as np

from dioptas.model.rotation_series import import_series
from dioptas.model.util.omega_background import ArPLSParameters, arpls_rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--upstream-script", required=True)
    parser.add_argument("--seed-frame", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--pixels", type=int, default=8192)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument(
        "--crop",
        type=int,
        nargs=4,
        default=[512, 1024, 768, 1280],
        metavar=("Y0", "Y1", "X0", "X1"),
    )
    args = parser.parse_args()
    if args.pixels < 1 or args.repeats < 1:
        parser.error("Pixels and repeats must be positive.")
    source = Path(args.upstream_script).resolve()
    spec = importlib.util.spec_from_file_location("external_background_sc", source)
    upstream = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(upstream)
    series = import_series(args.seed_frame)
    y0, y1, x0, x1 = args.crop
    stack = []
    for filename in series.files:
        with fabio.open(filename) as image:
            stack.append(np.array(image.data[y0:y1, x0:x1], copy=True))
    stack = np.array(stack)
    rows = stack.reshape(len(stack), -1).T
    rows = rows[np.all(np.isfinite(rows) & (rows != 0), axis=1)]
    if len(rows) < args.pixels:
        parser.error("Not enough valid nonzero pixel traces in the crop.")
    rng = np.random.default_rng(20261024)
    rows = rows[rng.choice(len(rows), args.pixels, replace=False)]
    # Exactly the edge padding and float32 input used by the CPU application's
    # process_data() wrapper. Dioptas's production boundary remains unpadded.
    padded = np.pad(rows.astype(np.float32), ((0, 0), (5, 5)), mode="edge")
    parameters = ArPLSParameters(300.0, 1e-6, 6)
    upstream.baseline_arPLS(padded[0], lam=300, ratio=1e-6, niter=5)
    arpls_rows(padded[:64], parameters, workers=1, backend="native")
    report = dict(
        schema="dioptas.external-arpls-cpu-comparison.v1",
        platform=platform.platform(),
        shape=list(padded.shape),
        source_frames=len(stack),
        source_crop_yx=args.crop,
        random_seed=20261024,
        workers=1,
        upstream_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        upstream_version=getattr(upstream, "__version__", None),
        parameters=dict(
            smoothness=300.0, tolerance=1e-6, max_solves=6, upstream_niter=5
        ),
        runs=[],
    )
    for _ in range(args.repeats):
        original, counts = [], []
        started = time.perf_counter()
        for row in padded:
            baseline, _, info = upstream.baseline_arPLS(
                row, lam=300, ratio=1e-6, niter=5, full_output=True
            )
            original.append(baseline)
            counts.append(info["num_iter"])
        old_seconds = time.perf_counter() - started
        original = np.array(original)
        started = time.perf_counter()
        new, iterations, converged = arpls_rows(
            padded, parameters, workers=1, backend="native"
        )
        new_seconds = time.perf_counter() - started
        run = dict(
            upstream_seconds=old_seconds,
            dioptas_seconds=new_seconds,
            speedup=old_seconds / new_seconds,
            upstream_mean_solves=float(np.mean(counts)),
            dioptas_mean_solves=float(iterations.mean()),
            dioptas_capped=int((~converged).sum()),
            upstream_nonfinite_values=int((~np.isfinite(original)).sum()),
            dioptas_nonfinite_values=int((~np.isfinite(new)).sum()),
            baseline_max_absolute_difference=float(np.nanmax(np.abs(original - new))),
            baseline_rms_difference=float(np.sqrt(np.nanmean((original - new) ** 2))),
        )
        report["runs"].append(run)
        print(json.dumps(run), flush=True)
    report["median_upstream_seconds"] = statistics.median(
        r["upstream_seconds"] for r in report["runs"]
    )
    report["median_dioptas_seconds"] = statistics.median(
        r["dioptas_seconds"] for r in report["runs"]
    )
    Path(args.output).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
