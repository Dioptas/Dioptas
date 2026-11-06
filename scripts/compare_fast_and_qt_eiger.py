"""Matched old reusable-buffer and Qt file pipelines on all Eiger frames.

The old decoder is loaded by explicit package path without modifying the Qt
Python environment. All integration uses the same installed Dioptrin wheel,
float64 geometry/settings and static mask. No GUI rendering is timed.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
import gc
import hashlib
import importlib.util
from importlib.metadata import version
import json
import logging
import mmap
import os
from pathlib import Path
import re
import statistics
import sys
import threading
import time
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import dioptrin
import h5py
import hdf5plugin  # noqa: F401
import numpy as np
import psutil
from qtpy.QtWidgets import QApplication

from scripts.benchmark_qt_eiger_masking import configure, close_model
import dioptas.model.loader.hdf5Loader as hdf

DATASET='entry_0000/instrument/eiger/data'


def load_old(path):
    try:
        import bslz4_to_sparse as installed
    except ImportError:
        installed = None
    if installed is not None and Path(installed.__file__).parent.resolve() == path.resolve():
        return installed
    spec=importlib.util.spec_from_file_location('_dioptas_benchmark_bslz4',path/'__init__.py',submodule_search_locations=[str(path)])
    module=importlib.util.module_from_spec(spec)
    sys.modules[spec.name]=module
    spec.loader.exec_module(module)
    return module


def unpack(results):
    values=list(results)
    assert all(x.is_ok() for x in values)
    values.sort(key=lambda x:int(re.findall(r'\d+',x.filename)[-1]))
    return np.array([x.result.intensity for x in values])


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--hdf5',type=Path,required=True)
    p.add_argument('--poni',type=Path,required=True)
    p.add_argument('--mask',type=Path,required=True)
    p.add_argument('--old-package',type=Path,required=True)
    p.add_argument('--workers',type=int,default=8)
    p.add_argument('--repeats',type=int,default=3)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--only',nargs='+')
    args=p.parse_args()
    # Array batches use the global Rayon pool; streaming batches use private
    # workers. Set both explicitly before any integrator initializes Rayon.
    dioptrin.set_rayon_threads(args.workers)
    app=QApplication.instance() or QApplication([])
    logging.getLogger().setLevel(logging.WARNING)
    b=load_old(args.old_package)
    with h5py.File(args.hdf5) as f:
        ds=f[DATASET]
        count,height,width=ds.shape
        assert ds.chunks==(1,height,width) and ds.dtype==np.uint32
        locations=[ds.id.get_chunk_info_by_coord((i,0,0)) for i in range(count)]
        assert all(x.filter_mask==0 for x in locations)
        offsets=np.array([x.byte_offset for x in locations],np.int64)
        lengths=np.array([x.size for x in locations],np.int64)
        first=np.ascontiguousarray(ds[0][::-1],dtype=np.float64)
    config=configure(args,args.hdf5,'static_mask',None)
    cal=config.calibration_model
    mask=cal._prepare_integration_mask(config.mask_model.get_mask())
    native=dioptrin.Integrator.from_poni_dict(cal._get_poni_dict(),method='pixel_split',unit='2th_deg',polarization_factor=.965,mask_mode='fixed')
    native.set_mask(mask.astype(np.uint8))
    native.integrate1d(first,2000)
    cal.sync_dioptrin_for_batch(mask,'2th_deg',2000,(height,width))
    cal._dioptrin_integrator.integrate1d(first,2000)
    model=config.map_model
    # Public batch arguments explicitly match the archived 8x1 integration.
    def qt_batch(images,n_points,azimuthal_std=False):
        return cal._dioptrin_integrator.batch1d_iter(images,n_points,num_workers=args.workers,num_threads=1,
             **({'azimuthal_std':True} if azimuthal_std else {}))
    cal.dioptrin_batch1d_iter=qt_batch
    raw_getter=type(config.img_model).img_data.fget
    tls=threading.local()
    float_buffers=np.empty((args.workers,height,width),np.float64)
    pool=ThreadPoolExecutor(max_workers=args.workers)
    fh=open(args.hdf5,'rb')
    mapped=mmap.mmap(fh.fileno(),0,access=mmap.ACCESS_READ)
    stages={}
    worker_times=[]

    @contextmanager
    def stage(name):
        start=time.perf_counter()
        try:yield
        finally:stages[name]=stages.get(name,0.)+time.perf_counter()-start

    def old_decode(item,reuse):
        slot,index=item
        start=time.perf_counter()
        if not hasattr(tls,'typed'):
            tls.typed=np.empty((height,width),np.uint32)
        b.decompress_from_buffer(mapped,offsets[index:index+1],lengths[index:index+1],np.uint32,out=tls.typed)
        target=float_buffers[slot] if reuse else np.empty((height,width),np.float64)
        np.copyto(target,tls.typed[::-1])
        worker_times.append(time.perf_counter()-start)
        return target

    def grouped_old(reuse):
        rows=[]
        for start in range(0,count,args.workers):
            ids=list(enumerate(range(start,min(start+args.workers,count))))
            with stage('read_decode_flip_convert_wall'):
                frames=list(pool.map(lambda item:old_decode(item,reuse),ids))
            with stage('integration_and_results_wall'):
                rows.append(unpack(native.batch1d(frames,2000,num_workers=args.workers,num_threads=1)))
        return np.concatenate(rows)

    original_decode=hdf._decompress_bitshuffle_lz4
    def qt_decode(*a,**kw):
        start=time.perf_counter()
        result=original_decode(*a,**kw)
        worker_times.append(time.perf_counter()-start)
        return result

    def grouped_qt(use_mmap=False):
        rows=[]
        with h5py.File(args.hdf5) as f:
            ds=f[DATASET]
            for start in range(0,count,args.workers):
                with stage('read_decode_flip_convert_wall'):
                    raw=([mapped[offsets[i]:offsets[i]+lengths[i]] for i in range(start,min(start+args.workers,count))] if use_mmap else [bytes(ds.id.read_direct_chunk((i,0,0))[1]) for i in range(start,min(start+args.workers,count))])
                    frames=list(pool.map(lambda raw:qt_decode(raw,(height,width),np.dtype('uint32')),raw))
                with stage('integration_and_results_wall'):
                    rows.append(unpack(native.batch1d(frames,2000,num_workers=args.workers,num_threads=1)))
        return np.concatenate(rows)

    def old_bytes_decode(item):
        slot,raw=item
        start=time.perf_counter()
        if not hasattr(tls,'typed'):
            tls.typed=np.empty((height,width),np.uint32)
        b.decompress_from_buffer(raw,np.array([0],np.int64),np.array([len(raw)],np.int64),np.uint32,out=tls.typed)
        np.copyto(float_buffers[slot],tls.typed[::-1])
        worker_times.append(time.perf_counter()-start)
        return float_buffers[slot]

    def grouped_old_hdf():
        rows=[]
        with h5py.File(args.hdf5) as f:
            ds=f[DATASET]
            for start in range(0,count,args.workers):
                with stage('read_decode_flip_convert_wall'):
                    raw=[bytes(ds.id.read_direct_chunk((i,0,0))[1]) for i in range(start,min(start+args.workers,count))]
                    frames=list(pool.map(old_bytes_decode,enumerate(raw)))
                with stage('integration_and_results_wall'):
                    rows.append(unpack(native.batch1d(frames,2000,num_workers=args.workers,num_threads=1)))
        return np.concatenate(rows)

    original_gen=hdf.Hdf5Image.gen_frames
    def bounded_gen(self,n_frames=None,decomp_workers=None,**options):
        return original_gen(self,n_frames=n_frames,decomp_workers=args.workers,**options)

    def reader_stream():
        reader=hdf.Hdf5Image(str(args.hdf5))
        try:return unpack(native.batch1d_iter(reader.gen_frames(decomp_workers=args.workers),2000,num_workers=args.workers,num_threads=1))
        finally:reader.f.close()

    def map_actual():
        model.load([str(args.hdf5)])
        return np.asarray(model.pattern_intensities)

    def mmap_stream_frames():
        # Allocated frames remain independently owned while native workers
        # borrow them. Reusable buffers must not be yielded to this queue.
        pending=[]
        for start in range(0,count,args.workers):
            ids=list(enumerate(range(start,min(start+args.workers,count))))
            pending=list(pool.map(lambda item:old_decode(item,False),ids))
            yield from pending

    def mmap_stream():
        return unpack(native.batch1d_iter(mmap_stream_frames(),2000,num_workers=args.workers,num_threads=1))

    def map_with_old_decoder():
        import dioptas.model.util.integration as util
        def open_frames(filepath,img_model,fast_path,*,load=False):
            assert fast_path and str(filepath)==str(args.hdf5)
            if load:img_model.load(filepath)
            return mmap_stream_frames()
        with patch.object(util,'_open_file_frames',open_frames):
            return map_actual()

    getter_calls=0
    getter_bytes=0
    def getter(model):
        nonlocal getter_calls,getter_bytes
        result=raw_getter(model)
        getter_calls+=1
        if result is not None and not np.shares_memory(result,model.raw_img_data):getter_bytes+=result.nbytes
        return result

    functions={
       'old_reusable_grouped':lambda:grouped_old(True),
       'old_allocated_grouped':lambda:grouped_old(False),
       'qt_decoder_grouped':grouped_qt,
       'qt_reader_native_stream':reader_stream,
       'qt_map_actual':map_actual,
       'old_decoder_native_stream':mmap_stream,
       'qt_map_old_decoder_adapter':map_with_old_decoder,
       'qt_mmap_decoder_grouped':lambda:grouped_qt(True),
       'old_hdf_decoder_grouped':grouped_old_hdf,
    }
    if args.only:
        assert set(args.only)<=functions.keys()
        functions={k:v for k,v in functions.items() if k in args.only}
    results={key:[] for key in functions}
    warmups={}
    reference=None
    cpu=lambda:psutil.cpu_times().user+psutil.cpu_times().system
    try:
        with patch.object(hdf.Hdf5Image,'gen_frames',bounded_gen),patch.object(hdf,'_decompress_bitshuffle_lz4',qt_decode),patch.object(type(config.img_model),'img_data',property(getter)):
            for label,fn in functions.items():
                stages.clear();worker_times.clear();getter_calls=getter_bytes=0
                start=time.perf_counter(); out=fn();elapsed=time.perf_counter()-start
                if reference is None:reference=out.copy()
                np.testing.assert_allclose(out,reference,rtol=5e-12,atol=1e-9)
                warmups[label]=elapsed
                print(f'Warm {label}: {count/elapsed:.2f} fps',flush=True)
            keys=list(functions)
            for repeat in range(args.repeats):
                order=keys[repeat:]+keys[:repeat]
                if repeat%2:order=order[::-1]
                for label in order:
                    gc.collect();stages.clear();worker_times.clear();getter_calls=getter_bytes=0
                    own0=time.process_time();busy0=cpu();start=time.perf_counter()
                    out=functions[label]();elapsed=time.perf_counter()-start
                    own=time.process_time()-own0;other=max(0,(cpu()-busy0-own)/elapsed)
                    np.testing.assert_allclose(out,reference,rtol=5e-12,atol=1e-9)
                    item={'seconds':elapsed,'fps':count/elapsed,'process_cores':own/elapsed,'other_busy_cores':other,
                          'stages_wall_seconds':dict(stages),'decoder_worker_wall_sum':sum(worker_times),
                          'decoder_calls':len(worker_times),'img_data_calls':getter_calls,'img_data_allocated_bytes':getter_bytes,
                          'relative_l2':float(np.linalg.norm(out-reference)/np.linalg.norm(reference))}
                    results[label].append(item)
                    print(f'{repeat} {label}: {item["fps"]:.2f} fps, CPU {item["process_cores"]:.2f}',flush=True)
    finally:
        pool.shutdown();mapped.close();fh.close();close_model(config)
    result={
       'source':str(args.hdf5.resolve()),'file_bytes':args.hdf5.stat().st_size,'frames':count,'shape':[height,width],
       'decoder_workers':args.workers,'integration_workers':args.workers,'threads_per_integration_worker':1,
       'settings':{'bins':2000,'method':'pixel_split','polarization':.965,'solid_angle':True,'precision':'float64','mask':'same supplied static mask','masked_pixels':int(np.count_nonzero(mask))},
       'mask_sha256':hashlib.sha256(mask).hexdigest(),'poni_sha256':hashlib.sha256(args.poni.read_bytes()).hexdigest(),
       'old_decoder':b.build_info(),'old_decoder_path':str(args.old_package),
       'versions':{p:version(p) for p in ['dioptrin','numpy','h5py','hdf5plugin','bitshuffle']},
       'source_hashes':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path('dioptas/model/MapModel.py'),Path('dioptas/model/CalibrationModel.py'),Path('dioptas/model/ImgModel.py'),Path('dioptas/model/loader/hdf5Loader.py'),Path('dioptas/model/util/integration.py'),Path(__file__)]},
       'warmup_seconds':warmups,'measurements':results,
       'summary':{k:{'median_fps':statistics.median(x['fps'] for x in v),'median_process_cores':statistics.median(x['process_cores'] for x in v)} for k,v in results.items()},
       'limits':'Full 625-frame file, warm OS cache, paired/reordered passes during concurrent user work. Mask/LUT/chunk-index/mmap preparation excluded, but all timed frame access/decode/flip/convert/integration/results included. Qt layers open/read metadata and first frame per run. Decoder task wall sums overlap and must not be added to end-to-end wall times. Old decoder adapter is benchmark-only and uses allocated frame buffers for ownership safety; production Qt code unchanged.'}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result['summary'],indent=2),flush=True)
    app.processEvents()


if __name__=='__main__':main()
