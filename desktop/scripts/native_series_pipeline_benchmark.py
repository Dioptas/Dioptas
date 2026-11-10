"""Full-file native Batch/Map timing and float64/Poisson parity; no GUI."""
import argparse
import hashlib
import json
import os
import platform
import statistics
import tempfile
import time
from pathlib import Path

os.environ["HDF5_PLUGIN_PRELOAD"] = "::"
import h5py
import numpy as np
import native_reference_client as client


def stored(native, view, temporary):
    path = temporary / ("series.h5" if view == "batch" else "map.dio")
    native.call("integration_save_batch" if view == "batch" else "save_project", path=str(path))
    with h5py.File(path) as file:
        if view == "batch":
            group = file["processed/result"]
        else:
            candidates = []
            file.visit(lambda name: candidates.append(name) if name.endswith("map/native_series/result/data") else None)
            assert len(candidates) == 1, candidates
            group = file[candidates[0]].parent
        return {key: group[key][:] for key in ("data", "binning", "counting_std") if key in group}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--before", type=Path, required=True)
    parser.add_argument("--after", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repeats", type=int, default=2)
    parser.add_argument("--threads", type=int, default=8)
    args = parser.parse_args()
    initial = args.source.stat()
    with h5py.File(args.source) as file:
        dataset = file["entry_0000/instrument/eiger/data"]
        shape = list(dataset.shape)
    variants = {
        "before": (args.before, "0"),
        "codec_only": (args.after, "0"),
        "parallel": (args.after, "1"),
    }
    report = dict(
        source=str(args.source), sourceBytes=initial.st_size, sourceMtimeNs=initial.st_mtime_ns,
        shape=shape, threads=args.threads, bins=2000, cakeBins=90,
        method="polygon", residentLayout="csr", polarization=0.965,
        mask="automatic named-detector acquisition mask; no external user mask",
        scope="Complete warm-plan native stdio command through final selection/image/pattern/cake/series response; all frames. Includes worker startup and Map previews/reduction. Excludes initial input/geometry/plan setup, export/parity checks, Tauri/rendering and process startup. OS file pages warm after the first pass; CPU not isolated. Optimized development scientific packages; codec is unoptimized only in the before executable.",
        machine=platform.platform(), executables={
            name: dict(path=str(path), sha256=hashlib.sha256(path.read_bytes()).hexdigest())
            for name, path in [("before", args.before), ("after", args.after)]
        }, records=[], comparisons=[], summaries=[],
    )
    references = {}
    with tempfile.TemporaryDirectory(prefix="dioptas-series-benchmark-") as directory:
        temporary = Path(directory)
        for repeat in range(args.repeats):
            order = list(variants) if repeat % 2 == 0 else list(reversed(variants))
            for view in ["batch", "map"]:
                for poisson in [False, True]:
                    for variant in order:
                        executable, parallel = variants[variant]
                        client.EXECUTABLE = executable
                        with client.Native({"DIOPTAS_SERIES_PARALLEL": parallel,
                                            "DIOPTAS_INTEGRATION_THREADS": str(args.threads)}) as native:
                            native.call("integration_settings", bins=2000, cake_bins=90,
                                        trim_zeros=False, method="polygon", sparse_layout="csr",
                                        poisson_errors=poisson, polarization=0.965)
                            native.call("open_calibration", path=str(args.source.with_suffix(".poni")))
                            native.call("open_image", path=str(args.source))
                            # Warm the exact series plan before timing a full run.
                            native.call("batch_load", paths=[str(args.source)], start=1, stop=2)
                            native.buffers.clear()
                            before = native.call("integration_diagnostics")["integrationDiagnostics"]
                            started = time.perf_counter()
                            result = native.call(view + "_load", paths=[str(args.source)])
                            elapsed = time.perf_counter() - started
                            after = native.call("integration_diagnostics")["integrationDiagnostics"]
                            delta = {key: after[key] - before.get(key, 0) for key in after}
                            assert delta["patternPlanBuilds"] == 0, delta
                            if variant == "parallel":
                                assert delta["frameParallelIntegrations"] == shape[0], delta
                                assert delta["seriesPipelineRuns"] == 1, delta
                                assert delta["seriesWorkerStarts"] == args.threads, delta
                                assert after["seriesPendingPeak"] <= args.threads, after
                            arrays = stored(native, view, temporary)
                            assert arrays["data"].shape == (shape[0], 2000)
                            assert ("counting_std" in arrays) == poisson
                            if view == "batch":
                                assert [entry["frame"] for entry in result["batch"]["entries"]] == list(range(1, shape[0] + 1))
                            else:
                                arrays["map_values"] = np.asarray(result["map"]["values"], dtype=float)
                            key = (view, poisson)
                            comparison = dict(view=view, poisson=poisson, variant=variant, repeat=repeat)
                            if key not in references:
                                assert variant == "before"
                                references[key] = arrays
                            for name, values in arrays.items():
                                expected = references[key][name]
                                np.testing.assert_allclose(values, expected, rtol=2e-12, atol=1e-8, equal_nan=True,
                                                           err_msg=f"{comparison}: {name}")
                                difference = np.nan_to_num(values - expected)
                                comparison[name] = dict(maxAbs=float(np.max(np.abs(difference))),
                                    relativeL2=float(np.linalg.norm(difference.ravel()) / max(np.linalg.norm(np.nan_to_num(expected).ravel()), 1e-300)))
                            report["comparisons"].append(comparison)
                            row = dict(view=view, poisson=poisson, variant=variant, repeat=repeat,
                                       seconds=elapsed, fps=shape[0] / elapsed, diagnosticsDelta=delta)
                            report["records"].append(row)
                            print(json.dumps(row), flush=True)
                            native.buffers.clear()
        for view in ["batch", "map"]:
            for poisson in [False, True]:
                times = {variant: statistics.median(row["seconds"] for row in report["records"]
                         if row["view"] == view and row["poisson"] == poisson and row["variant"] == variant)
                         for variant in variants}
                report["summaries"].append(dict(view=view, poisson=poisson, medianSeconds=times,
                    fps={variant: shape[0] / elapsed for variant, elapsed in times.items()},
                    totalSpeedup=times["before"] / times["parallel"],
                    pipelineSpeedup=times["codec_only"] / times["parallel"]))
    final = args.source.stat()
    assert (initial.st_size, initial.st_mtime_ns) == (final.st_size, final.st_mtime_ns)
    report["sourceUnchanged"] = True
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report["summaries"], indent=2))


if __name__ == "__main__":
    main()
