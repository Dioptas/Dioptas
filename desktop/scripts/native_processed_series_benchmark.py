"""Corrected/dynamic-mask Eiger Batch/Map timings with complete float64 parity."""
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
from native_series_pipeline_benchmark import stored


def configure(native, source, case, refs):
    native.call("integration_settings", bins=2000, cake_bins=90, trim_zeros=False,
                poisson_errors=True, method="polygon", sparse_layout="csr", polarization=0.965)
    native.call("open_calibration", path=str(source.with_suffix(".poni")))
    native.call("open_image", path=str(source))
    if case in ("corrected", "combined"):
        native.call("integration_image_background", path=str(refs / "background.npy"), scale=0.7, offset=1.2, poisson=True)
        native.call("integration_flat_field", path=str(refs / "flat.npy"))
    if case == "spot":
        native.call("mask_plugin", name="Spot Mask", enabled=True)
    if case == "cosmic":
        native.call("mask_plugin", name="Cosmic Ray Mask", enabled=True)
    if case in ("dynamic", "combined"):
        native.call("mask_plugin", name="Threshold Mask", enabled=True,
                    settings=dict(above_enabled=True, above_value=1000.))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source", type=Path, required=True)
    p.add_argument("--before", type=Path, required=True)
    p.add_argument("--after", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--repeats", type=int, default=2)
    p.add_argument("--frames", type=int, default=625, help="Batch only; Map always processes the whole source")
    p.add_argument("--views", nargs="+", default=["batch", "map"], choices=["batch", "map"])
    p.add_argument("--cases", nargs="+", default=["corrected", "dynamic", "combined"], choices=["corrected", "dynamic", "combined", "spot", "cosmic"])
    p.add_argument("--sequential-reference", action="store_true", help="Disable frame parallelism for the before variant")
    args = p.parse_args()
    initial = args.source.stat()
    with h5py.File(args.source) as file:
        shape = list(file["entry_0000/instrument/eiger/data"].shape)
    report = dict(source=str(args.source), sourceBytes=initial.st_size, shape=shape, bins=2000,
                  requestedWorkers=8, poisson=True, sequentialReference=args.sequential_reference,
                  baseline="Same optimized binary with frame parallelism disabled; plugin setting hoisting included in both variants" if args.sequential_reference else "Preserved before executable", machine=platform.platform(), records=[], comparisons=[], summaries=[],
                  corrections="background=7 counts, scale=0.7, offset=1.2, background noise on; mean-normalized flat varies 0.8–1.2 across detector columns",
                  dynamicMask="Threshold above 1000 for dynamic/combined; Spot/Cosmic use native defaults when selected. Masks are evaluated on corrected values when corrections are enabled",
                  scope="Warm-plan complete native stdio commands, including per-command correction-map preparation, worker starts, ordered collection, final selection and Map previews/reduction. Excludes initial setup, exports, process startup and Tauri rendering. OS file pages warm; CPU not isolated. Both binaries have optimized codecs.",
                  executables={label: dict(path=str(path), sha256=hashlib.sha256(path.read_bytes()).hexdigest())
                               for label, path in [("before", args.before), ("after", args.after)]})
    references = {}
    with tempfile.TemporaryDirectory(prefix="dioptas-processed-benchmark-") as directory:
        refs = Path(directory)
        np.save(refs / "background.npy", np.full(shape[1:], 7.))
        np.save(refs / "flat.npy", np.broadcast_to(np.linspace(0.8, 1.2, shape[2]), shape[1:]))
        for repeat in range(args.repeats):
            order = ["before", "after"] if repeat % 2 == 0 else ["after", "before"]
            for view in args.views:
                for case in args.cases:
                    for variant in order:
                        client.EXECUTABLE = args.before if variant == "before" else args.after
                        with client.Native({"DIOPTAS_INTEGRATION_THREADS":"8", "DIOPTAS_SERIES_PARALLEL": "0" if variant == "before" and args.sequential_reference else "1"}) as native:
                            configure(native, args.source, case, refs)
                            native.call("batch_load", paths=[str(args.source)], start=1, stop=2)
                            native.buffers.clear()
                            before = native.call("integration_diagnostics")["integrationDiagnostics"]
                            started = time.perf_counter()
                            payload = dict(paths=[str(args.source)])
                            if view == "batch":
                                payload.update(start=1, stop=args.frames)
                            result = native.call(view + "_load", **payload)
                            elapsed = time.perf_counter() - started
                            after = native.call("integration_diagnostics")["integrationDiagnostics"]
                            count = args.frames if view == "batch" else shape[0]
                            delta = {key: after[key] - before.get(key, 0) for key in after}
                            if variant == "after":
                                assert delta["processedFrameIntegrations"] == count, delta
                                assert 1 < delta["seriesWorkerStarts"] <= 8, delta
                                assert delta["dynamicSeriesPlanBuilds"] == 0, delta
                            arrays = stored(native, view, refs)
                            assert arrays["data"].shape == (count, 2000)
                            assert "counting_std" in arrays
                            if view == "map":
                                arrays["map_values"] = np.asarray(result["map"]["values"], dtype=float)
                            key = view, case
                            if key not in references:
                                assert variant == "before"
                                references[key] = arrays
                            comparison = dict(view=view, case=case, variant=variant, repeat=repeat)
                            for name, values in arrays.items():
                                expected = references[key][name]
                                np.testing.assert_allclose(values, expected, rtol=3e-12, atol=1e-8, equal_nan=True,
                                                           err_msg=f"{comparison}: {name}")
                                difference = np.nan_to_num(values - expected)
                                comparison[name] = dict(maxAbs=float(np.max(np.abs(difference))),
                                    relativeL2=float(np.linalg.norm(difference.ravel()) / max(np.linalg.norm(np.nan_to_num(expected).ravel()), 1e-300)))
                            report["comparisons"].append(comparison)
                            row = dict(view=view, case=case, variant=variant, repeat=repeat, frames=count,
                                       seconds=elapsed, fps=count / elapsed, diagnosticsDelta=delta)
                            report["records"].append(row)
                            print(json.dumps(row), flush=True)
                            native.buffers.clear()
        for view in args.views:
            for case in args.cases:
                times = {variant: statistics.median(r["seconds"] for r in report["records"]
                         if (r["view"], r["case"], r["variant"]) == (view, case, variant)) for variant in ["before", "after"]}
                count = args.frames if view == "batch" else shape[0]
                report["summaries"].append(dict(view=view, case=case, medianSeconds=times,
                    fps={variant: count / seconds for variant, seconds in times.items()}, speedup=times["before"] / times["after"]))
    final = args.source.stat()
    assert (initial.st_size, initial.st_mtime_ns) == (final.st_size, final.st_mtime_ns)
    report["sourceUnchanged"] = True
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report["summaries"], indent=2))


if __name__ == "__main__":
    main()
