"""Full-file pyFAI-compatible Batch/Map timing with preserved-executable parity."""
import argparse
import hashlib
import json
import os
import platform
import statistics
import subprocess
import tempfile
import time
from pathlib import Path

os.environ["HDF5_PLUGIN_PRELOAD"] = "::"
import h5py
import numpy as np
import native_reference_client as client
from native_series_pipeline_benchmark import stored
from native_spatial_mask_benchmark import compare


def cpu_context(processor_pid):
    output = subprocess.check_output(["ps","-axo","pid,pcpu,comm"],text=True)
    active = []
    for line in output.splitlines()[1:]:
        pid,cpu,command = line.strip().split(None,2)
        if int(pid) not in (os.getpid(),processor_pid) and float(cpu)>=25:
            active.append(dict(pid=int(pid),cpu=float(cpu),name=Path(command).name))
    return active


def busy(context):
    return sum(p["cpu"] for p in context)>=50


def wait_idle(pid):
    started=time.perf_counter()
    while True:
        context=cpu_context(pid)
        if not busy(context):
            time.sleep(1)
            context=cpu_context(pid)
            if not busy(context): return context
        if time.perf_counter()-started>180:
            raise RuntimeError(f"Unrelated CPU work did not settle: {context}")
        time.sleep(2)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source", type=Path, required=True)
    p.add_argument("--before", type=Path, required=True)
    p.add_argument("--after", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--repeats", type=int, default=2)
    p.add_argument("--threads", type=int, default=8)
    p.add_argument("--bins", type=int, default=2000)
    p.add_argument("--parallel-before", action="store_true", help="The preserved reference already uses parallel frames")
    p.add_argument("--views", nargs="+", choices=["batch","map"], default=["batch","map"])
    p.add_argument("--errors", nargs="+", choices=["off","on"], default=["off","on"])
    p.add_argument("--method", choices=["pyfai_full","polygon"], default="pyfai_full")
    p.add_argument("--variants", nargs="+", choices=["before","after"], default=["before","after"])
    p.add_argument("--bitwise", action="store_true", help="Require identical float64 bits for every exported result")
    p.add_argument("--wait-idle", action="store_true", help="Wait for unrelated heavy CPU work, and retry visibly contended measurements")
    args = p.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    oracles = args.output.parent / "oracles"
    oracles.mkdir(exist_ok=True)
    initial = args.source.stat()
    with h5py.File(args.source) as f:
        shape = list(f["entry_0000/instrument/eiger/data"].shape)
    report = dict(source=str(args.source), sourceBytes=initial.st_size,
                  sourceMtimeNs=initial.st_mtime_ns, shape=shape,
                  method=args.method, bins=args.bins, residentLayout="csr", baselineParallel=args.parallel_before,
                  variants=args.variants,
                  bitwiseRequired=args.bitwise,
                  waitForIdle=args.wait_idle, contendedAttempts=[],
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
            for view in args.views:
                for poisson in [v=="on" for v in args.errors]:
                    case = "poisson" if poisson else "no-errors"
                    for variant in (args.variants if repeat%2==0 else list(reversed(args.variants))):
                        client.EXECUTABLE = args.before if variant=="before" else args.after
                        with client.Native({"DIOPTAS_INTEGRATION_THREADS":str(args.threads)}) as native:
                            def call(action, **payload):
                                return native.call(action, requested_products=dict(cake=False,rings=False), **payload)
                            call("integration_settings", bins=args.bins, cake_bins=90, trim_zeros=False,
                                 method=args.method, sparse_layout="csr", poisson_errors=poisson, polarization=0.965)
                            call("open_calibration", path=str(args.source.with_suffix(".poni")))
                            call("open_image", path=str(args.source))
                            call("batch_load", paths=[str(args.source)], start=1, stop=2)
                            native.buffers.clear()
                            for attempt in range(4):
                                cpu_before=wait_idle(native.child.pid) if args.wait_idle else cpu_context(native.child.pid)
                                before = call("integration_diagnostics")["integrationDiagnostics"]
                                print(json.dumps(dict(phase="timing",repeat=repeat,view=view,poisson=poisson,variant=variant,attempt=attempt)),flush=True)
                                started = time.perf_counter()
                                result = call("batch_load_data" if view=="batch" else "map_load", paths=[str(args.source)])
                                elapsed = time.perf_counter()-started
                                after = call("integration_diagnostics")["integrationDiagnostics"]
                                cpu_after=cpu_context(native.child.pid)
                                if not args.wait_idle or not busy(cpu_after): break
                                report["contendedAttempts"].append(dict(repeat=repeat,view=view,poisson=poisson,variant=variant,
                                    attempt=attempt,seconds=elapsed,cpuBefore=cpu_before,cpuAfter=cpu_after))
                                print(json.dumps(dict(phase="contention-retry",**report["contendedAttempts"][-1])),flush=True)
                            else:
                                raise RuntimeError("Timed command repeatedly overlapped unrelated CPU work")
                            delta = {k:after[k]-before.get(k,0) for k in after}
                            assert delta["patternPlanBuilds"]==0 and delta["dynamicSeriesPlanBuilds"]==0, delta
                            if variant=="after" or args.parallel_before:
                                assert delta["frameParallelIntegrations"]==shape[0],delta
                                assert delta["processedFrameIntegrations" if args.method=="pyfai_full" else "patternOnlyDecodes"]==shape[0],delta
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
                            if repeat==0 and variant==args.variants[0]:
                                np.savez(oracles/(view+"-"+case+".npz"),**arrays)
                            comparison = compare(oracles,view,case,arrays)
                            with np.load(oracles/(view+"-"+case+".npz")) as expected:
                                bitwise = all(np.array_equal(values.view("u8"),expected[key].view("u8"))
                                              for key,values in arrays.items())
                            if args.bitwise:
                                assert bitwise,(repeat,view,poisson,variant)
                            record=dict(repeat=repeat,view=view,poisson=poisson,variant=variant,
                                        frames=shape[0],seconds=elapsed,fps=shape[0]/elapsed,
                                        diagnosticsDelta=delta,comparison=comparison,bitwiseEqual=bitwise,
                                        cpuBefore=cpu_before,cpuAfter=cpu_after)
                            report["records"].append(record)
                            args.output.write_text(json.dumps(report,indent=2)+"\n")
                            print(json.dumps(record),flush=True)
    for view in args.views:
        for poisson in [v=="on" for v in args.errors]:
            times={variant:statistics.median(r["seconds"] for r in report["records"]
                   if r["variant"]==variant and r["view"]==view and r["poisson"]==poisson)
                   for variant in args.variants}
            report["summaries"].append(dict(view=view,poisson=poisson,medianSeconds=times,
                fps={v:shape[0]/s for v,s in times.items()},
                speedup=times["before"]/times["after"] if set(times)=={"before","after"} else None))
    final=args.source.stat()
    assert (initial.st_size,initial.st_mtime_ns)==(final.st_size,final.st_mtime_ns)
    report["sourceUnchanged"]=True
    args.output.write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps(report["summaries"],indent=2))


if __name__=="__main__":
    main()
