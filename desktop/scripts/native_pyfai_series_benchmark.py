"""Full-file pyFAI-compatible Batch/Map timing with preserved-executable parity."""
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
from native_spatial_mask_benchmark import compare


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source", type=Path, required=True)
    p.add_argument("--before", type=Path, required=True)
    p.add_argument("--after", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--repeats", type=int, default=2)
    p.add_argument("--threads", type=int, default=8)
    p.add_argument("--bins", type=int, default=2000)
    args = p.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    oracles = args.output.parent / "oracles"
    oracles.mkdir(exist_ok=True)
    initial = args.source.stat()
    with h5py.File(args.source) as f:
        shape = list(f["entry_0000/instrument/eiger/data"].shape)
    report = dict(source=str(args.source), sourceBytes=initial.st_size,
                  sourceMtimeNs=initial.st_mtime_ns, shape=shape,
                  method="pyfai_full", bins=args.bins, residentLayout="csr",
                  polarization=0.965, requestedWorkers=args.threads,
                  masks="automatic named-detector acquisition mask; no dynamic or external user mask",
                  corrections="none", machine=platform.platform(),
                  scope="Complete warm-plan native commands, including worker creation, ordered collection, final selection and Map previews/reduction. Detector/pattern requested, cake/rings hidden as in the normal Integration image view. Excludes initial geometry/plan warmup, process startup, export/parity checks and GUI rendering. OS pages warm; CPU not isolated.",
                  executables={name:dict(path=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest())
                               for name,path in [("before",args.before),("after",args.after)]},
                  records=[], summaries=[])
    with tempfile.TemporaryDirectory(prefix="dioptas-pyfai-series-") as temp:
        temp = Path(temp)
        for repeat in range(args.repeats):
            for view in ["batch", "map"]:
                for poisson in [False, True]:
                    case = "poisson" if poisson else "no-errors"
                    for variant in (["before","after"] if repeat%2==0 else ["after","before"]):
                        client.EXECUTABLE = args.before if variant=="before" else args.after
                        with client.Native({"DIOPTAS_INTEGRATION_THREADS":str(args.threads)}) as native:
                            def call(action, **payload):
                                return native.call(action, requested_products=dict(cake=False,rings=False), **payload)
                            call("integration_settings", bins=args.bins, cake_bins=90, trim_zeros=False,
                                 method="pyfai_full", sparse_layout="csr", poisson_errors=poisson, polarization=0.965)
                            call("open_calibration", path=str(args.source.with_suffix(".poni")))
                            call("open_image", path=str(args.source))
                            call("batch_load", paths=[str(args.source)], start=1, stop=2)
                            native.buffers.clear()
                            before = call("integration_diagnostics")["integrationDiagnostics"]
                            print(json.dumps(dict(phase="timing",repeat=repeat,view=view,poisson=poisson,variant=variant)),flush=True)
                            started = time.perf_counter()
                            result = call("batch_load_data" if view=="batch" else "map_load", paths=[str(args.source)])
                            elapsed = time.perf_counter()-started
                            after = call("integration_diagnostics")["integrationDiagnostics"]
                            delta = {k:after[k]-before.get(k,0) for k in after}
                            assert delta["patternPlanBuilds"]==0 and delta["dynamicSeriesPlanBuilds"]==0, delta
                            if variant=="after":
                                assert delta["frameParallelIntegrations"]==shape[0],delta
                                assert delta["processedFrameIntegrations"]==shape[0],delta
                                assert delta["seriesWorkerStarts"]==args.threads,delta
                                assert delta["seriesPipelineRuns"]==1,delta
                            else:
                                assert delta["frameParallelIntegrations"]==0 and delta["seriesPipelineRuns"]==0,delta
                            arrays = stored(native, view, temp)
                            assert arrays["data"].shape==(shape[0],args.bins)
                            assert ("counting_std" in arrays)==poisson
                            if view=="batch":
                                assert [e["frame"] for e in result["batch"]["entries"]]==list(range(1,shape[0]+1))
                            else:
                                assert result["map"]["points"]==shape[0]
                                arrays["map_values"]=np.asarray(result["map"]["values"],dtype=float)
                            if repeat==0 and variant=="before":
                                np.savez(oracles/(view+"-"+case+".npz"),**arrays)
                            comparison = compare(oracles,view,case,arrays)
                            record=dict(repeat=repeat,view=view,poisson=poisson,variant=variant,
                                        frames=shape[0],seconds=elapsed,fps=shape[0]/elapsed,
                                        diagnosticsDelta=delta,comparison=comparison)
                            report["records"].append(record)
                            args.output.write_text(json.dumps(report,indent=2)+"\n")
                            print(json.dumps(record),flush=True)
    for view in ["batch","map"]:
        for poisson in [False,True]:
            times={variant:statistics.median(r["seconds"] for r in report["records"]
                   if r["variant"]==variant and r["view"]==view and r["poisson"]==poisson)
                   for variant in ["before","after"]}
            report["summaries"].append(dict(view=view,poisson=poisson,medianSeconds=times,
                fps={v:shape[0]/s for v,s in times.items()},speedup=times["before"]/times["after"]))
    final=args.source.stat()
    assert (initial.st_size,initial.st_mtime_ns)==(final.st_size,final.st_mtime_ns)
    report["sourceUnchanged"]=True
    args.output.write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps(report["summaries"],indent=2))


if __name__=="__main__":
    main()
