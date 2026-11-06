"""Paired production Qt Map timings of selectable CSR/CSC fixed-mask layouts."""
import argparse
import gc
import hashlib
import json
import os
from pathlib import Path
from statistics import median
import time
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import dioptrin
import numpy as np
import psutil
from qtpy.QtWidgets import QApplication
from scripts.benchmark_qt_eiger_masking import configure,close_model


def main():
 p=argparse.ArgumentParser(description=__doc__)
 for name in ('hdf5','poni','mask','output'):p.add_argument('--'+name,type=Path,required=True)
 p.add_argument('--workers',type=int,choices=(4,8),required=True)
 p.add_argument('--repeats',type=int,default=3)
 a=p.parse_args();app=QApplication.instance() or QApplication([])
 c=configure(a,a.hdf5,'static_mask',None);reference=None;samples=[];warmups=[]
 def run(layout,warm=False):
  nonlocal reference
  c.calibration_model.dioptrin_sparse_layout=layout
  assert c.calibration_model._dioptrin_integrator.sparse_layout==layout
  gc.collect();cpu=psutil.Process().cpu_times();host=psutil.cpu_times();t=time.perf_counter()
  c.map_model.load([str(a.hdf5)])
  elapsed=time.perf_counter()-t;after=psutil.Process().cpu_times();h=psutil.cpu_times()
  output=np.asarray(c.map_model.pattern_intensities)
  if reference is None:reference=output.copy()
  np.testing.assert_allclose(output,reference,rtol=5e-12,atol=1e-9)
  assert output.shape==(625,2000)
  own=after.user+after.system-cpu.user-cpu.system
  item={'layout':layout,'seconds':elapsed,'fps':len(output)/elapsed,
   'process_cpu_seconds':own,'other_busy_cores':max(0,(h.user+h.system-host.user-host.system-own)/elapsed),
   'relative_l2':float(np.linalg.norm(output-reference)/np.linalg.norm(reference))}
  (warmups if warm else samples).append(item)
  print('first' if warm else 'warm',layout,round(item['fps'],2),'fps',flush=True)
 try:
  for layout in ('csr','csc'):run(layout,True)
  for i in range(a.repeats):
   for layout in (('csr','csc') if i%2==0 else ('csc','csr')):run(layout)
  result={'date':'2026-11-06','workers':a.workers,'source':str(a.hdf5),'settings':{'bins':2000,'unit':'2th_deg','method':'pixel_split','precision':'float64','polarization':.965,'solid_angle':True,'mask':'original static mask','frame_native_threads':1},
   'samples':samples,'warmups':warmups,'median_fps':{layout:median(s['fps'] for s in samples if s['layout']==layout) for layout in ('csr','csc')},
   'native_binary':{str(f):hashlib.sha256(f.read_bytes()).hexdigest() for f in Path(dioptrin.__file__).parent.glob('*.so')},
   'limits':'Production selectable layout API, same Qt configuration and full 625-frame Eiger file; alternating paired warm-cache runs. Includes file opening/reading/decompression, fixed-mask preparation, normalization, native integration and Map assembly; excludes GUI rendering and Configuration creation. Background work measured per sample.'}
  a.output.write_text(json.dumps(result,indent=2)+'\n');print(result['median_fps'],flush=True)
 finally:close_model(c)
 app.processEvents()
if __name__=='__main__':main()
