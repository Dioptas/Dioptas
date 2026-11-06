"""Controlled Qt Eiger comparison: identical frame kernels, shared vs separate plans."""
import argparse
from contextlib import contextmanager
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
import dioptrin
import numpy as np
import psutil
from qtpy.QtWidgets import QApplication
from scripts.benchmark_qt_eiger_masking import configure, close_model
from dioptas.model.util import dynamic_integration as dynamic


def independent_worker(snapshot):
    task = snapshot[0]
    native = dioptrin.Integrator.from_poni_dict(task.dioptrin_geometry_config,
        method='pixel_split', unit='2th_deg' if task.unit=='d_A' else task.unit,
        polarization_factor=task.polarization_factor, mask_mode='dynamic')
    if task.supersampling_factor > 1:
        native.set_method('supersampled', n_ss=task.supersampling_factor)
    plan = native.prepare_dynamic1d(task.image.shape, task.pattern_num_points)
    return dynamic._FrameWorker((*snapshot[:-1], plan))


@contextmanager
def plan_variant(config, separate, cache):
    # Keep both pools warm and switch only pool selection. All sources, image
    # processing, masks, frame dispatch, native arithmetic and result collection
    # use the production implementations unchanged.
    original = dynamic.FramePool
    def factory(snapshot, workers):
        if separate:
            return original(snapshot, workers, factory=independent_worker)
        return original(snapshot, workers)
    saved = cache.get(separate)
    if saved:
        config._frame_pool, config._frame_pool_key, config._frame_pool_finalizer = saved
    else:
        config._frame_pool = config._frame_pool_key = config._frame_pool_finalizer = None
    try:
        with patch.object(dynamic, 'FramePool', factory):
            yield
    finally:
        cache[separate] = (config._frame_pool, config._frame_pool_key,
                           config._frame_pool_finalizer)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('hdf5','poni','mask','output'):
        p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--workers',type=int,choices=(4,8),required=True)
    p.add_argument('--repeats',type=int,default=5)
    a=p.parse_args()
    app=QApplication.instance() or QApplication([])
    c=configure(a,a.hdf5,'threshold_230',('Threshold Mask',{'above_value':230}))
    cache={}; process=psutil.Process(); reference=None
    samples=[]; warmups=[]
    source_stat=a.hdf5.stat()
    original_compute=dynamic._FrameWorker.compute
    def run(separate,warm=False):
        nonlocal reference
        ids=set(); owners=set(); frames=[]
        def tracked(worker, read, index):
            ids.add(worker.adapter.worker.shared_plan_id)
            owners.add(threading.get_ident())
            frames.append(index)
            assert worker.adapter.worker.num_threads==1
            return original_compute(worker,read,index)
        gc.collect()
        peak=[process.memory_info().rss]; stop=threading.Event()
        def monitor():
            while not stop.wait(.05):
                peak[0]=max(peak[0],process.memory_info().rss)
        thread=threading.Thread(target=monitor);thread.start()
        before=process.cpu_times(); host=psutil.cpu_times(); start=time.perf_counter()
        try:
            with plan_variant(c,separate,cache), patch.object(dynamic._FrameWorker,'compute',tracked):
                c.map_model.load([str(a.hdf5)])
        finally:
            elapsed=time.perf_counter()-start;stop.set();thread.join()
        after=process.cpu_times(); host_after=psutil.cpu_times()
        own=after.user+after.system-before.user-before.system
        busy=host_after.user+host_after.system-host.user-host.system
        actual=np.asarray(c.map_model.pattern_intensities)
        if reference is None:reference=actual.copy()
        np.testing.assert_allclose(actual,reference,rtol=5e-12,atol=1e-9)
        assert actual.shape==(625,2000)
        assert len(ids)==(a.workers if separate else 1),ids
        assert len(owners)==a.workers
        assert sorted(frames)==list(range(625))
        item={'separate':separate,'seconds':elapsed,'fps':625/elapsed,
              'other_busy_cores':max(0,(busy-own)/elapsed),'process_busy_cores':own/elapsed,
              'peak_rss_GiB':peak[0]/2**30,'plan_ids':sorted(ids),
              'worker_threads':len(owners),
              'relative_l2':float(np.linalg.norm(actual-reference)/np.linalg.norm(reference))}
        (warmups if warm else samples).append(item)
        print('first' if warm else 'warm','separate' if separate else 'shared',
              f'{item["fps"]:.2f} fps, other {item["other_busy_cores"]:.2f} cores, RSS {item["peak_rss_GiB"]:.2f} GiB',flush=True)
    try:
        # Warm-up order reversed across worker counts; warm trials alternate AB/BA.
        for separate in ([False,True] if a.workers==4 else [True,False]):run(separate,True)
        for repeat in range(a.repeats):
            for separate in ([False,True] if (repeat+a.workers//4)%2 else [True,False]):
                run(separate)
        assert (a.hdf5.stat().st_size,a.hdf5.stat().st_mtime_ns)==(source_stat.st_size,source_stat.st_mtime_ns)
        paths=[Path(__file__),Path('dioptas/model/util/dynamic_integration.py')]
        binaries=list(Path(dioptrin.__file__).parent.glob('*.so'))
        result={'date':'2026-11-06','workers':a.workers,'source':str(a.hdf5),
            'source_bytes':source_stat.st_size,'source_mtime_ns':source_stat.st_mtime_ns,
            'settings':{'frames':625,'bins':2000,'unit':'2th_deg','method':'pixel_split',
                        'polarization':.965,'solid_angle':True,'precision':'float64',
                        'threshold_above':230,'poisson_errors':False,'azimuthal_std':False,
                        'native_threads_per_frame':1,'mask':str(a.mask),'poni':str(a.poni)},
            'warmups':warmups,'samples':samples,
            'median_fps':{str(separate):median(s['fps'] for s in samples if s['separate']==separate) for separate in (False,True)},
            'source_hashes':{str(f):hashlib.sha256(f.read_bytes()).hexdigest() for f in paths+[a.mask,a.poni]+binaries},
            'limits':'Same locally built native library, same borrowed-array API and numerical kernels; only sharing differs. '
                     'Separate creates one immutable prepared plan per frame worker. Production Qt MapModel and reader, '
                     'full original Eiger file, warm OS cache, five alternating paired passes. Timed: opening, snapshotting, '
                     'reading/decompression, image processing, changing threshold masks, normalization, integration and map assembly. '
                     'GUI rendering excluded. Both pools remain resident to permit alternating warm trials, so warm RSS is '
                     'combined process memory, not per-variant memory. First-run timings include setup, not cold disk IO. '
                     'One PhaseSmith solver was observed active; measured other busy cores are recorded per trial.'}
        a.output.write_text(json.dumps(result,indent=2)+'\n')
        print('Medians',result['median_fps'],flush=True)
    finally:
        for pool,key,finalizer in cache.values():
            if finalizer is not None:finalizer()
        close_model(c)
    app.processEvents()

if __name__=='__main__':main()
