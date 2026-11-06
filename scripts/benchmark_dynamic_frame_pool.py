"""Paired full-file Qt Map benchmark: serial masks versus whole-frame jobs."""
import argparse
from contextlib import nullcontext
import gc
import hashlib
import json
import os
from pathlib import Path
from statistics import median
import threading
import time
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import numpy as np
import psutil
from qtpy.QtWidgets import QApplication
from scripts.benchmark_qt_eiger_masking import configure, close_model
from dioptas.model.util import dynamic_integration as dynamic


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('hdf5', 'poni', 'mask', 'output'):
        p.add_argument('--'+name, type=Path, required=True)
    p.add_argument('--workers', type=int, required=True)
    p.add_argument('--repeats', type=int, default=3)
    a = p.parse_args()
    app = QApplication.instance() or QApplication([])
    c = configure(a, a.hdf5, 'threshold_230', ('Threshold Mask', {'above_value': 230}))
    model = c.map_model
    process = psutil.Process()
    samples, warmups = [], []
    reference = None
    def run(parallel, warm=False):
        plan_ids = set()
        original_job = dynamic._FrameWorker.compute
        def tracked(worker, *args):
            plan_ids.add(worker.adapter.worker.shared_plan_id)
            return original_job(worker, *args)
        nonlocal reference
        peak = [process.memory_info().rss]
        stop = threading.Event()
        def monitor():
            while not stop.wait(.05):
                peak[0] = max(peak[0], process.memory_info().rss)
        monitor_thread = threading.Thread(target=monitor)
        monitor_thread.start()
        cpu = process.cpu_times()
        host = psutil.cpu_times()
        start = time.perf_counter()
        try:
            context = nullcontext() if parallel else patch.object(dynamic, '_eligible', return_value=False)
            with context, patch.object(dynamic._FrameWorker, 'compute', tracked):
                model.load([str(a.hdf5)])
        finally:
            elapsed = time.perf_counter()-start
            stop.set()
            monitor_thread.join()
        cpu_after = process.cpu_times()
        host_after = psutil.cpu_times()
        process_seconds = cpu_after.user+cpu_after.system-cpu.user-cpu.system
        busy = host_after.user+host_after.system-host.user-host.system
        output = np.asarray(model.pattern_intensities)
        if reference is None:
            reference = output.copy()
        np.testing.assert_allclose(output, reference, rtol=5e-12, atol=1e-9)
        assert len(plan_ids) == (1 if parallel else 0)
        item = {'shared_plan_ids':sorted(plan_ids), 'parallel': parallel, 'seconds': elapsed, 'frames':len(output),
                'fps': len(output)/elapsed, 'process_cpu_seconds':process_seconds,
                'other_busy_cores':max(0,(busy-process_seconds)/elapsed),
                'peak_rss_GiB':peak[0]/2**30,
                'relative_l2':float(np.linalg.norm(output-reference)/np.linalg.norm(reference))}
        (warmups if warm else samples).append(item)
        print(('cold' if warm else 'warm'), 'whole-frame' if parallel else 'serial',
              f'{item["fps"]:.2f} fps, RSS {item["peak_rss_GiB"]:.2f} GiB', flush=True)
    try:
        run(False, True)
        gc.collect()
        run(True, True)
        for repeat in range(a.repeats):
            for parallel in ([False, True] if repeat % 2 == 0 else [True, False]):
                gc.collect()
                run(parallel)
        paths = [Path(__file__), Path('dioptas/model/util/dynamic_integration.py'),
                 Path('dioptas/model/MapModel.py'),Path('dioptas/model/loader/fastHdf5.py')]
        result = {'date':'2026-11-06','source':str(a.hdf5.resolve()),
            'source_bytes':a.hdf5.stat().st_size,'dataset':'entry_0000/instrument/eiger/data',
            'backend':'Local unreleased Dioptrin shared-plan build; version metadata remains 0.8.0, not published wheel.',
            'workers':a.workers,'warmups':warmups,'samples':samples,
            'median_fps':{'serial':median(s['fps'] for s in samples if not s['parallel']),
                          'whole_frame':median(s['fps'] for s in samples if s['parallel'])},
            'settings':{'bins':2000,'unit':'2th_deg','method':'pixel_split','precision':'float64',
                        'polarization':.965,'solid_angle':True,'threshold_above':230,
                        'static_mask':str(a.mask),'whole_frame_native_threads':1,
                        'serial_reader_workers':a.workers,
                        'environment':{k:os.environ.get(k) for k in
                                       ('OMP_NUM_THREADS','RAYON_NUM_THREADS','OPENBLAS_NUM_THREADS')}},
            'source_hashes':{str(path):hashlib.sha256(path.read_bytes()).hexdigest() for path in paths},
            'limits':'Full original 625-frame Eiger file, warm OS cache, concurrent user work. '
                     'Alternating paired runs share the same configuration. Serial baseline retains '
                     'parallel decoder prefetch and intra-frame Rayon threads from the environment. '
                     'Whole-frame jobs each decode, prepare, mask, normalize and integrate with a '
                     'private single-thread native pool. Timed: file opening, snapshotting, all reads, '
                     'mask updates, normalization, integration, ordering and map reduction. Initial '
                     'Configuration construction and GUI rendering excluded. Cold execution retained separately.'}
        a.output.write_text(json.dumps(result,indent=2)+'\n')
        print(result['median_fps'], flush=True)
    finally:
        close_model(c)
    app.processEvents()

if __name__ == '__main__':
    main()
