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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--processor", type=Path, required=True)
    parser.add_argument("--label", required=True)
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--reference", type=Path)
    parser.add_argument("--threads", type=int, default=8)
    parser.add_argument("--views", nargs="+", default=["batch", "map"], choices=["batch", "map"])
    parser.add_argument("--cases", nargs="+", default=["spot", "cosmic"], choices=["spot", "cosmic"])
    args = parser.parse_args()
    args.directory.mkdir(parents=True, exist_ok=True)
    initial = args.source.stat()
    with h5py.File(args.source) as f:
        shape = list(f["entry_0000/instrument/eiger/data"].shape)
    report = dict(source=str(args.source), sourceBytes=initial.st_size, shape=shape,
                  label=args.label, processor=str(args.processor),
                  executableSha256=hashlib.sha256(args.processor.read_bytes()).hexdigest(),
                  requestedWorkers=args.threads, bins=2000, poisson=True,
                  machine=platform.platform(), records=[],
                  scope="All original frames; warm-plan complete native stdio commands, including mask generation, worker startup, integration, final selection and Map preview/reduction. Excludes initial setup, export/parity checks, process startup and Tauri rendering. OS file pages warm; CPU not isolated.")
    output = args.directory / (args.label + ".json")
    client.EXECUTABLE = args.processor
    with tempfile.TemporaryDirectory(prefix="dioptas-spatial-export-") as temporary:
        for view in args.views:
            for case in args.cases:
                with client.Native({"DIOPTAS_INTEGRATION_THREADS":str(args.threads)}) as native:
                    configure(native, args.source, case, Path(temporary))
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
                    arrays = stored(native, view, Path(temporary))
                    assert arrays["data"].shape == (shape[0], 2000)
                    if view == "map": arrays["map_values"] = np.asarray(reply["map"]["values"], dtype=float)
                    comparison = {}
                    if args.reference:
                        with np.load(args.reference / (view+"-"+case+".npz")) as expected:
                            for key, values in arrays.items():
                                np.testing.assert_allclose(values, expected[key], rtol=3e-12, atol=1e-8, equal_nan=True, err_msg=f"{view}/{case}/{key}")
                                diff = np.nan_to_num(values-expected[key])
                                comparison[key] = dict(maxAbs=float(np.max(np.abs(diff))),
                                    relativeL2=float(np.linalg.norm(diff.ravel())/max(np.linalg.norm(np.nan_to_num(expected[key]).ravel()),1e-300)))
                    else:
                        np.savez(args.directory / (view+"-"+case+".npz"), **arrays)
                    record = dict(view=view, case=case, frames=shape[0], seconds=elapsed,
                                  fps=shape[0]/elapsed, diagnosticsDelta=delta, comparison=comparison)
                    report["records"].append(record)
                    output.write_text(json.dumps(report,indent=2)+"\n")
                    print(json.dumps(record),flush=True)
    final = args.source.stat()
    assert (initial.st_size,initial.st_mtime_ns)==(final.st_size,final.st_mtime_ns)
    report["sourceUnchanged"] = True
    output.write_text(json.dumps(report,indent=2)+"\n")


if __name__ == "__main__":
    main()
