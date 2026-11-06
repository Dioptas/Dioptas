"""Fresh-process setup benchmark: one shared plan vs one plan per frame worker."""
import argparse
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import resource
from statistics import median
import subprocess
import sys
import tempfile
import threading
import time

import dioptrin
import numpy as np
import psutil


def child(a):
    payload=json.loads(a.payload.read_text())
    image=np.load(a.payload.parent/'frame.npy')
    mask=np.load(a.payload.parent/'mask.npy')
    process=psutil.Process()
    before_rss=process.memory_info().rss
    peak=[before_rss];stop=threading.Event()
    def monitor():
        while not stop.wait(.01):peak[0]=max(peak[0],process.memory_info().rss)
    monitor_thread=threading.Thread(target=monitor);monitor_thread.start()
    def prepare():
        # Unsendable source stays on its creating thread; returned handles are sendable.
        source=dioptrin.Integrator.from_poni_dict(payload['poni'],method='pixel_split',
            unit='2th_deg',polarization_factor=.965,mask_mode='dynamic')
        return source.prepare_dynamic1d(tuple(payload['shape']),2000)
    def independent():
        plan=prepare()
        return plan.worker(num_threads=1)
    own=process.cpu_times();host=psutil.cpu_times()
    start=time.perf_counter()
    with concurrent.futures.ThreadPoolExecutor(a.workers) as pool:
        if a.mode=='shared':
            plan=prepare()
            futures=[pool.submit(plan.worker,num_threads=1) for _ in range(a.workers)]
        else:
            futures=[pool.submit(independent) for _ in range(a.workers)]
        workers=[f.result() for f in futures]
        elapsed=time.perf_counter()-start
        after=process.cpu_times();host_after=psutil.cpu_times()
        ready_rss=process.memory_info().rss
        highwater=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        if sys.platform!='darwin':highwater*=1024
        stop.set();monitor_thread.join()
        ids={w.shared_plan_id for w in workers}
        assert len(ids)==(1 if a.mode=='shared' else a.workers)
        assert all(w.num_threads==1 for w in workers)
        # Validate AFTER the setup timer and peak capture. No hidden geometry or
        # LUT warmup is performed before timing; prepare_dynamic1d eagerly builds CSC.
        source=dioptrin.Integrator.from_poni_dict(payload['poni'],method='pixel_split',
            unit='2th_deg',polarization_factor=.965,mask_mode='fixed')
        source.set_mask(mask)
        reference=np.asarray(source.integrate1d(image,2000).intensity)
        validation=[]
        for worker in workers:
            t=time.perf_counter();out=np.asarray(worker.integrate1d(image,mask).intensity)
            first=time.perf_counter()-t
            np.testing.assert_allclose(out,reference,rtol=5e-12,atol=1e-9)
            validation.append({'first_integration_seconds':first,
                'relative_l2':float(np.linalg.norm(out-reference)/np.linalg.norm(reference))})
    cpu=after.user+after.system-own.user-own.system
    busy=host_after.user+host_after.system-host.user-host.system
    result={'workers':a.workers,'mode':a.mode,'setup_seconds':elapsed,'setup_cpu_seconds':cpu,
        'other_busy_cores':max(0,(busy-cpu)/elapsed),'baseline_rss_GiB':before_rss/2**30,
        'ready_rss_GiB':ready_rss/2**30,'peak_setup_rss_GiB':max(highwater,peak[0],ready_rss)/2**30,
        'worker_plan_ids':sorted(ids),'validation':validation}
    a.output.write_text(json.dumps(result,indent=2)+'\n')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--child',action='store_true')
    p.add_argument('--payload',type=Path)
    p.add_argument('--workers',type=int,choices=(4,8))
    p.add_argument('--mode',choices=('shared','separate'))
    for name in ('hdf5','poni','mask','output'):p.add_argument('--'+name,type=Path)
    p.add_argument('--repeats',type=int,default=5)
    a=p.parse_args()
    if a.child:return child(a)
    os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
    from qtpy.QtWidgets import QApplication
    from scripts.benchmark_qt_eiger_masking import configure,close_model
    app=QApplication.instance() or QApplication([])
    c=configure(a,a.hdf5,'threshold_230',('Threshold Mask',{'above_value':230}))
    image=np.ascontiguousarray(c.img_model.img_data,dtype=np.float64)
    c._update_plugin_masks(image)
    mask=c.calibration_model._prepare_integration_mask(c.mask_model.get_mask()).astype(np.uint8)
    payload={'shape':image.shape,'poni':c.calibration_model._get_poni_dict()}
    close_model(c);del c
    records=[]
    with tempfile.TemporaryDirectory(prefix='dioptrin-setup-') as directory:
        folder=Path(directory);param=folder/'inputs.json'
        param.write_text(json.dumps(payload))
        np.save(folder/'frame.npy',image);np.save(folder/'mask.npy',mask)
        del image,mask
        for repeat in range(a.repeats):
            # Reverse both worker-count order and shared/separate order.
            for workers in ((4,8) if repeat%2==0 else (8,4)):
                for mode in (('shared','separate') if (repeat+workers//4)%2==0 else ('separate','shared')):
                    out=folder/'trial.json';env=os.environ.copy()
                    env.update(RAYON_NUM_THREADS=str(workers),OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1')
                    subprocess.run([sys.executable,'-m','scripts.benchmark_lut_setup','--child',
                        '--payload',str(param),'--workers',str(workers),'--mode',mode,'--output',str(out)],
                        env=env,check=True)
                    record=json.loads(out.read_text());record['repeat']=repeat
                    records.append(record)
                    print(f'{repeat+1}: {workers} {mode}: {record["setup_seconds"]:.3f}s, '
                          f'CPU {record["setup_cpu_seconds"]:.2f}s, peak {record["peak_setup_rss_GiB"]:.2f} GiB, '
                          f'other {record["other_busy_cores"]:.2f} cores',flush=True)
    binaries=list(Path(dioptrin.__file__).parent.glob('*.so'))
    paths=[Path(__file__),a.poni,a.mask]+binaries
    result={'date':'2026-11-06','source':str(a.hdf5),'source_bytes':a.hdf5.stat().st_size,
        'shape':payload['shape'],'poni':payload['poni'],'samples':records,
        'settings':{'bins':2000,'unit':'2th_deg','method':'pixel_split','precision':'float64',
                    'polarization':.965,'solid_angle':True,'threshold_above':230,
                    'native_threads_per_frame_worker':1,'geometry_build_rayon_threads':'matches requested workers'},
        'hashes':{str(f):hashlib.sha256(f.read_bytes()).hexdigest() for f in paths},
        'method':'Twenty fresh child processes: five alternating paired trials per worker count. '
                 'Timer starts before unprepared integrator creation and plan preparation, ends when all worker handles '
                 'are ready. Includes app pool startup, geometry/corrections/CSR/CSC preparation and native single-thread '
                 'worker pool creation. Excludes process/Python/library import startup, file reading, mask generation, '
                 'image integration, validation and pool teardown. One shared plan or exactly N independent plans; '
                 'separate plans are built concurrently, using the same N-thread global Rayon geometry-build budget. '
                 'Each trial has isolated allocator/cache and RSS accounting. Peak RSS measured before validation. '
                 'Same first Eiger frame and effective static+threshold mask validate all handles after timing.'}
    a.output.write_text(json.dumps(result,indent=2)+'\n')
    app.processEvents()

if __name__=='__main__':main()
