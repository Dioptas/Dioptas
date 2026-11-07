"""Matched Qt snapshot/worker timings; requires the source-built native bridge.

Run from the checkout with RAYON_NUM_THREADS=8 OMP_NUM_THREADS=1
OPENBLAS_NUM_THREADS=1 QT_QPA_PLATFORM=offscreen and the bridge on PYTHONPATH.
No GUI rendering or debounce delay is included. The ordinary display loader
still decodes a full image before either integration task is dispatched.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import time

import numpy as np
from qtpy.QtWidgets import QApplication
import dioptrin
import dioptrin_io_fused
from dioptas.model.Configuration import Configuration
from dioptas.model.loader.fusedHdf5 import describe_fused_source
from dioptas.model.integration_task import PersistentIntegrationEngine


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hdf5", type=Path, required=True)
    parser.add_argument("--poni", type=Path, required=True)
    parser.add_argument("--mask-u8", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--frames", type=int, default=12)
    parser.add_argument("--repeats", type=int, default=3)
    args = parser.parse_args()
    app = QApplication.instance() or QApplication([])
    config = Configuration()
    config.auto_integrate_pattern = False
    config.auto_integrate_cake = False
    config.integration_rad_points = 2000
    config.trim_trailing_zeros = False
    config.use_mask = True
    config.integration_unit = "2th_deg"
    config.img_model.load(str(args.hdf5))
    cal = config.calibration_model
    cal.load(str(args.poni))
    cal.use_dioptrin = True
    cal.dioptrin_num_workers = 8
    cal.polarization_factor = .965
    mask = np.fromfile(args.mask_u8, np.uint8).reshape(config.img_model.raw_img_data.shape).astype(bool)
    config.mask_model.set_mask_data(mask)
    base = config.create_integration_task()
    base = replace(base, fused_hdf5_source=describe_fused_source(config.img_model))
    assert base.calculate_pattern and base.fused_hdf5_source
    indices = np.linspace(0, config.img_model.series_max-1, args.frames, dtype=int).tolist()
    report = {"file":str(args.hdf5),"poni":str(args.poni),"frames":indices,"passes":args.repeats,
        "shape":base.image.shape,"bins":2000,"polarization":.965,"unit":"2th_deg",
        "mask_sha256":hashlib.sha256(base.mask.tobytes()).hexdigest(),"precision":"float64 weights and sums",
        "legacy_rayon_threads":dioptrin.rayon_num_threads(),"block_workers":8,
        "cache":"warm OS cache; display loader reads each selected frame first; no decoded scan cache",
        "includes":"worker task time includes bridge count equality check, source checks, thread launch, decode, integration, merge, normalization, output conversion",
        "excludes":"rendering, Qt debounce, plot application and file-index/lookup preparation (reported as cold compute separately)",
        "timings":[], "cold_compute":{}, "bridge":dioptrin_io_fused.__file__}
    pool = ThreadPoolExecutor(max_workers=1)
    engines = {}
    def compute(mode, task):
        if mode not in engines: engines[mode] = PersistentIntegrationEngine()
        start = time.perf_counter()
        result = engines[mode].compute(task)
        elapsed = time.perf_counter()-start
        if mode == "fused":
            assert any(b.fused not in (None, False) for b in engines[mode]._dioptrin_backends.values())
        return result, elapsed
    def close():
        for engine in engines.values(): engine.close()
    try:
        for mode in ["legacy", "fused"]:
            task = replace(base, fused_hdf5_source=None) if mode == "legacy" else base
            _, elapsed = pool.submit(compute,mode,task).result()
            report["cold_compute"][mode] = elapsed
            print("Cold",mode,round(elapsed,3),flush=True)
        for errors in [False, True]:
            config.calculate_poisson_errors = errors
            for repeat in range(args.repeats):
                for sample,index in enumerate(indices):
                    start = time.perf_counter()
                    # Explicit load_series_img keeps the same already-open selected reader.
                    config.img_model.load_series_img(index+1)
                    load_seconds = time.perf_counter()-start
                    start = time.perf_counter()
                    task = config.create_integration_task()
                    task = replace(task, fused_hdf5_source=describe_fused_source(config.img_model))
                    snapshot_seconds = time.perf_counter()-start
                    assert task.calculate_pattern and task.fused_hdf5_source
                    results = {}
                    row={"frame":index,"pass":repeat,"poisson":errors,"display_load_seconds":load_seconds,
                         "snapshot_seconds":snapshot_seconds}
                    for mode in (["legacy","fused"] if (sample+repeat)%2==0 else ["fused","legacy"]):
                        selected = replace(task,fused_hdf5_source=None) if mode=="legacy" else task
                        result,elapsed=pool.submit(compute,mode,selected).result()
                        results[mode]=result.pattern
                        row[mode+"_compute_seconds"]=elapsed
                    a,b=results["fused"],results["legacy"]
                    np.testing.assert_allclose(a.radial,b.radial)
                    np.testing.assert_allclose(a.intensity,b.intensity,rtol=2e-12,atol=1e-10)
                    if errors: np.testing.assert_allclose(a.sigma,b.sigma,rtol=2e-12,atol=1e-10)
                    row["max_scaled_error"]=float(np.max(np.abs(a.intensity-b.intensity)/np.maximum(1,np.abs(b.intensity))))
                    report["timings"].append(row)
                args.output.parent.mkdir(parents=True,exist_ok=True)
                args.output.write_text(json.dumps(report,indent=2)+"\n")
                print("Completed",repeat,"Poisson",errors,flush=True)
    finally:
        pool.submit(close).result()
        pool.shutdown()
    app.processEvents()


if __name__=="__main__": main()
