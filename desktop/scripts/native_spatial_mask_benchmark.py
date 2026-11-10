"""Full-source Spot/Cosmic timings with persistent before/after float64 oracles."""
import argparse
import hashlib
import json
import os
import platform
import tempfile
import time
from pathlib import Path

os.environ["HDF5_PLUGIN_PRELOAD"] = "::"
import h5py
import numpy as np
import native_reference_client as client
from native_processed_series_benchmark import configure
from native_series_pipeline_benchmark import stored


def compare(reference, view, case, arrays):
    comparison = {}
    with np.load(reference / (view+"-"+case+".npz")) as expected:
        assert set(arrays) == set(expected.files), (view, case, arrays.keys(), expected.files)
        for key, values in arrays.items():
            np.testing.assert_allclose(values, expected[key], rtol=3e-12, atol=1e-8,
                                       equal_nan=True, err_msg=f"{view}/{case}/{key}")
            diff = np.nan_to_num(values-expected[key])
            comparison[key] = dict(maxAbs=float(np.max(np.abs(diff))),
                relativeL2=float(np.linalg.norm(diff.ravel())/max(np.linalg.norm(np.nan_to_num(expected[key]).ravel()),1e-300)))
    return comparison


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--processor", type=Path, required=True)
    parser.add_argument("--label", required=True)
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--reference", type=Path)
    parser.add_argument("--threads", type=int, default=8)
    parser.add_argument("--views", nargs="+", default=["batch", "map"], choices=["batch", "map"])
    parser.add_argument("--cases", nargs="+", default=["spot", "cosmic"], choices=["spot", "cosmic", "both"])
    parser.add_argument("--corrections", action="store_true", help="Subtract background with counting noise and apply a nonuniform flat field before masking")
    parser.add_argument("--check-map-from-batch", action="store_true", help="After timing Batch, import its full profiles through this processor's Map code and compare with --reference Map results; no additional frame integration")
    args = parser.parse_args()
    if args.check_map_from_batch and (not args.reference or args.views != ["batch"]):
        parser.error("--check-map-from-batch requires --reference and --views batch")
    args.directory.mkdir(parents=True, exist_ok=True)
    initial = args.source.stat()
    with h5py.File(args.source) as f:
        shape = list(f["entry_0000/instrument/eiger/data"].shape)
    report = dict(source=str(args.source), sourceBytes=initial.st_size, shape=shape,
                  label=args.label, processor=str(args.processor),
                  executableSha256=hashlib.sha256(args.processor.read_bytes()).hexdigest(),
                  requestedWorkers=args.threads, bins=2000, poisson=True,
                  corrections=(dict(backgroundCounts=7., backgroundScale=0.7, backgroundOffset=1.2,
                                    backgroundPoisson=True, flatField="mean-normalized, linear 0.8–1.2 across columns")
                               if args.corrections else None),
                  reference=str(args.reference) if args.reference else None,
                  machine=platform.platform(), records=[],
                  scope="All original frames; warm-plan complete native stdio commands, including mask generation, worker startup, integration, final selection and Map preview/reduction. Excludes initial setup, export/parity checks, process startup and Tauri rendering. OS file pages warm; CPU not isolated.")
    output = args.directory / (args.label + ".json")
    client.EXECUTABLE = args.processor
    with tempfile.TemporaryDirectory(prefix="dioptas-spatial-export-") as temporary:
        temporary = Path(temporary)
        if args.corrections:
            np.save(temporary / "background.npy", np.full(shape[1:], 7.))
            np.save(temporary / "flat.npy", np.broadcast_to(np.linspace(0.8, 1.2, shape[2]), shape[1:]))
        for view in args.views:
            for case in args.cases:
                with client.Native({"DIOPTAS_INTEGRATION_THREADS":str(args.threads)}) as native:
                    configure(native, args.source, "corrected" if args.corrections else "raw", temporary)
                    for name, enabled in [("Spot Mask", case in ("spot", "both")),
                                          ("Cosmic Ray Mask", case in ("cosmic", "both"))]:
                        if enabled:
                            native.call("mask_plugin", name=name, enabled=True)
                    native.call("batch_load", paths=[str(args.source)], start=1, stop=2)
                    native.buffers.clear()
                    before = native.call("integration_diagnostics")["integrationDiagnostics"]
                    active = dict(pid=native.child.pid, view=view, case=case, label=args.label)
                    (args.directory / "active.json").write_text(json.dumps(active))
                    print(json.dumps(dict(phase="timing", **active)), flush=True)
                    started = time.perf_counter()
                    reply = native.call(view+"_load", paths=[str(args.source)])
                    elapsed = time.perf_counter()-started
                    after = native.call("integration_diagnostics")["integrationDiagnostics"]
                    delta = {key:after[key]-before.get(key,0) for key in after}
                    assert delta["processedFrameIntegrations"] == shape[0], delta
                    assert delta["dynamicSeriesPlanBuilds"] == 0, delta
                    arrays = stored(native, view, temporary)
                    assert arrays["data"].shape == (shape[0], 2000)
                    if view == "map": arrays["map_values"] = np.asarray(reply["map"]["values"], dtype=float)
                    comparison = {}
                    if args.reference:
                        comparison = compare(args.reference, view, case, arrays)
                    else:
                        np.savez(args.directory / (view+"-"+case+".npz"), **arrays)
                    record = dict(view=view, case=case, frames=shape[0], seconds=elapsed,
                                  fps=shape[0]/elapsed, diagnosticsDelta=delta, comparison=comparison)
                    if args.check_map_from_batch:
                        # Series export precedes this import. Reuse the frozen
                        # processor's integrated frames as the independent Map
                        # reduction oracle without integrating them twice.
                        imported = native.call("map_batch", path=str(temporary / "series.h5"))
                        map_arrays = stored(native, "map", temporary)
                        map_arrays["map_values"] = np.asarray(imported["map"]["values"], dtype=float)
                        record["mapFromBatchComparison"] = compare(args.reference, "map", case, map_arrays)
                    report["records"].append(record)
                    output.write_text(json.dumps(report,indent=2)+"\n")
                    print(json.dumps(record),flush=True)
    final = args.source.stat()
    assert (initial.st_size,initial.st_mtime_ns)==(final.st_size,final.st_mtime_ns)
    report["sourceUnchanged"] = True
    output.write_text(json.dumps(report,indent=2)+"\n")


if __name__ == "__main__":
    main()
