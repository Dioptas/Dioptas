"""Compare dynamic Qt model processing with matched parallel decoder adapters."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import gc
import hashlib
import json
import logging
import mmap
import os
from pathlib import Path
import statistics
import tempfile
import threading
import time
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import dioptrin
import h5py
import numpy as np
from qtpy.QtWidgets import QApplication
from scripts.benchmark_qt_eiger_masking import configure,exact_subset,close_model,DATASET
from scripts.compare_fast_and_qt_eiger import load_old
import dioptas.model.loader.hdf5Loader as hdf
from dioptas.model.ImgModel import ImgModel


def main():
 p=argparse.ArgumentParser(description=__doc__)
 for name in ['hdf5','poni','mask','old-package','output']:p.add_argument('--'+name,type=Path,required=True)
 p.add_argument('--workers',type=int,default=8)
 p.add_argument('--frames',type=int,default=16)
 p.add_argument('--repeats',type=int,default=3)
 a=p.parse_args();dioptrin.set_rayon_threads(a.workers)
 app=QApplication.instance() or QApplication([])
 logging.getLogger().setLevel(logging.WARNING)
 b=load_old(a.old_package)
 with tempfile.TemporaryDirectory(prefix='dioptas-dynamic-readers-') as temp:
  subset=Path(temp)/'subset.h5'
  ids,hashes,decoded=exact_subset(a.hdf5,subset,a.frames)
  decoded_hashes=[hashlib.sha256(x).hexdigest() for x in decoded]
  del decoded;gc.collect()
  with h5py.File(subset) as f:
   ds=f[DATASET];count,h,w=ds.shape
   info=[ds.id.get_chunk_info_by_coord((i,0,0)) for i in range(count)]
   offsets=np.array([x.byte_offset for x in info],np.int64)
   lengths=np.array([x.size for x in info],np.int64)
  c=configure(a,subset,'threshold_230',('Threshold Mask',{'above_value':230}))
  c.img_model.img_changed.blocked=True
  cal=c.calibration_model;model=c.map_model
  pool=ThreadPoolExecutor(max_workers=a.workers)
  file=open(subset,'rb');mapped=mmap.mmap(file.fileno(),0,access=mmap.ACCESS_READ)
  tls=threading.local();buffers=np.empty((a.workers,h,w),np.float64)
  stages={}
  def old_decode(item):
   slot,index=item
   if not hasattr(tls,'raw'):tls.raw=np.empty((h,w),np.uint32)
   b.decompress_from_buffer(mapped,offsets[index:index+1],lengths[index:index+1],np.uint32,out=tls.raw)
   np.copyto(buffers[slot],tls.raw[::-1]);return buffers[slot]
  def grouped_impl(old):
   rows=[]
   with h5py.File(subset) as f:
    ds=f[DATASET]
    for start in range(0,count,a.workers):
     t=time.perf_counter();items=list(enumerate(range(start,min(start+a.workers,count))))
     if old:frames=list(pool.map(old_decode,items))
     else:
      raw=[bytes(ds.id.read_direct_chunk((i,0,0))[1]) for _,i in items]
      frames=list(pool.map(lambda data:hdf._decompress_bitshuffle_lz4(data,(h,w),np.dtype('uint32')),raw))
     stages['decode_wall']=stages.get('decode_wall',0)+time.perf_counter()-t
     t=time.perf_counter()
     for frame in frames:
      c.img_model._img_data=frame
      rows.append(c.integrate_image_1d(update_pattern_model=False)[1])
     stages['qt_model_mask_integration_wall']=stages.get('qt_model_mask_integration_wall',0)+time.perf_counter()-t
   return np.array(rows)
  def grouped(old):
   was_blocked=c.img_model.img_changed.blocked
   c.img_model.img_changed.blocked=True
   try:return grouped_impl(old)
   finally:c.img_model.img_changed.blocked=was_blocked
  original_gen=hdf.Hdf5Image.gen_frames
  def capped(self,n_frames=None,decomp_workers=None):return original_gen(self,n_frames=n_frames,decomp_workers=a.workers)
  def actual_map():
   model.load([str(subset)]);return np.asarray(model.pattern_intensities)
  def parallel_get(self,index):
   # Benchmark-only adapter: keep frames independently allocated, consume in
   # order, and close the prefetch pool as soon as the last frame is delivered.
   if getattr(self,'_bench_last_index',None)==index:return self._bench_last
   if not hasattr(self,'_bench_next') or index!=self._bench_next:
    previous=getattr(self,'_bench_iter',None)
    if previous is not None:previous.close()
    self._bench_iter=self.gen_frames(decomp_workers=a.workers);self._bench_next=0
   while self._bench_next<=index:
    self._bench_last=next(self._bench_iter);self._bench_last_index=self._bench_next;self._bench_next+=1
   if self._bench_next==self.series_max:self._bench_iter.close()
   return self._bench_last
  original_load=ImgModel.get_image_data
  def hdf_load(model,filename,pos=0):
   if str(filename)==str(subset):return model.load_hdf5(filename,pos)
   return original_load(model,filename,pos)
  def hdf_serial_map():
   with patch.object(ImgModel,'get_image_data',hdf_load):return actual_map()
  def parallel_map():
   with patch.object(ImgModel,'get_image_data',hdf_load),patch.object(hdf.Hdf5Image,'get_image',parallel_get):return actual_map()
  jobs={'old_parallel_decode_qt_processing':lambda:grouped(True),
        'qt_parallel_decode_qt_processing':lambda:grouped(False),
        'qt_map_current_serial_reader':actual_map,
        'qt_map_hdf_serial_adapter':hdf_serial_map,
        'qt_map_parallel_reader_adapter':parallel_map}
  results={name:[] for name in jobs};expected=None;warmups={}
  try:
   with patch.object(hdf.Hdf5Image,'gen_frames',capped):
    for name,fn in jobs.items():
     t=time.perf_counter();out=fn();warmups[name]=time.perf_counter()-t
     if expected is None:expected=out.copy()
     np.testing.assert_allclose(out,expected,rtol=5e-12,atol=1e-9)
     print('Warm',name,round(count/warmups[name],2),'fps',flush=True)
    names=list(jobs)
    for repeat in range(a.repeats):
     for name in (names if repeat%2==0 else names[::-1]):
      gc.collect();stages.clear();cpu=time.process_time();t=time.perf_counter()
      out=jobs[name]();elapsed=time.perf_counter()-t;cpu=time.process_time()-cpu
      np.testing.assert_allclose(out,expected,rtol=5e-12,atol=1e-9)
      assert cal._dioptrin_integrator.mask_mode=='dynamic'
      assert c.mask_plugin_manager.is_enabled('Threshold Mask')
      item={'seconds':elapsed,'fps':count/elapsed,'process_cores':cpu/elapsed,'stages_wall_seconds':stages.copy(),
            'relative_l2':float(np.linalg.norm(out-expected)/np.linalg.norm(expected))}
      results[name].append(item);print(repeat,name,round(item['fps'],2),'fps',flush=True)
  finally:pool.shutdown();mapped.close();file.close();close_model(c)
  result={'frames':count,'source_indices':ids,'source':str(a.hdf5),'compressed_chunk_hashes':hashes,'decoded_float64_hashes':decoded_hashes,
          'decoder_workers':a.workers,'within_frame_rayon_threads':a.workers,'mask':'supplied static mask OR built-in threshold >230',
          'settings':{'bins':2000,'method':'pixel_split','polarization':.965,'precision':'float64'},
          'warmup_seconds':warmups,'measurements':results,
          'summary':{name:{'median_fps':statistics.median(x['fps'] for x in values),'median_process_cores':statistics.median(x['process_cores'] for x in values)} for name,values in results.items()},
          'limits':'16-frame sampled subset, warm cache, no GUI rendering, concurrent work. First two grouped cases use the same Configuration image/mask/integration path and 8 decoder workers. Current Qt dynamic Map baseline inherently reads serially despite configured decoder budget; its benchmark-only adapter enables the same 8-worker Qt decoder without changing production code. Mask creation and integration remain sequential across frames, with within-frame Rayon threads matched. Preparation/LUT warmup excluded; timed frame read/decode included.'}
 a.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result['summary'],indent=2),flush=True);app.processEvents()


if __name__=='__main__':main()
