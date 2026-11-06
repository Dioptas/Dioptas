"""Paired before/after reader measurement through unmodified Qt MapModel."""
import argparse
from contextlib import contextmanager,ExitStack
import gc
import hashlib
import json
import os
from pathlib import Path
from statistics import median
import tempfile
import time
from unittest.mock import patch
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import dioptrin
import numpy as np
from qtpy.QtWidgets import QApplication
from scripts.benchmark_qt_eiger_masking import configure,exact_subset,close_model
from dioptas.model.loader import fastHdf5
import dioptas.model.util.integration as util


@contextmanager
def no_prefetch(*args,**kwargs):
    yield


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['hdf5','poni','mask','output']:p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--workers',type=int,default=8)
    p.add_argument('--repeats',type=int,default=3)
    a=p.parse_args();dioptrin.set_rayon_threads(a.workers)
    app=QApplication.instance() or QApplication([])
    assert fastHdf5._codec is not None
    results={};references={}
    with tempfile.TemporaryDirectory(prefix='dioptas-reader-pair-') as tmp:
        sample=Path(tmp)/'sample.h5'
        ids,chunk_hashes,frames=exact_subset(a.hdf5,sample,16)
        frame_hashes=[hashlib.sha256(f).hexdigest() for f in frames];del frames;gc.collect()
        for case,path,plugin in [('static_full',a.hdf5,None),('threshold_sample',sample,('Threshold Mask',{'above_value':230}))]:
            c=configure(a,path,'static_mask' if plugin is None else 'threshold_230',plugin)
            model=c.map_model
            outputs={};samples=[];warm={}
            original_read=fastHdf5.FastChunkReader.read
            calls=[]
            def tracked(self,index):
                calls.append(index);return original_read(self,index)
            def run(fast,_model=model):
                with ExitStack() as stack:
                    if not fast:
                        stack.enter_context(patch.object(fastHdf5,'_codec',None))
                        stack.enter_context(patch.object(util,'prefetch_series',no_prefetch))
                    stack.enter_context(patch.object(fastHdf5.FastChunkReader,'read',tracked))
                    start=time.perf_counter();cpu=time.process_time()
                    _model.load([str(path)])
                    elapsed=time.perf_counter()-start;cpu=time.process_time()-cpu
                out=np.asarray(_model.pattern_intensities).copy()
                return out,elapsed,cpu
            for fast in [False,True]:
                calls.clear();out,elapsed,cpu=run(fast)
                warm[str(fast)]=elapsed;outputs[fast]=out
                print('Warm',case,fast,len(out)/elapsed,flush=True)
            np.testing.assert_allclose(outputs[True],outputs[False],rtol=5e-12,atol=1e-9)
            reference=outputs[False].copy()
            for repeat in range(a.repeats):
                for fast in ([False,True] if repeat%2==0 else [True,False]):
                    gc.collect();calls.clear();out,elapsed,cpu=run(fast)
                    np.testing.assert_allclose(out,reference,rtol=5e-12,atol=1e-9)
                    assert len(calls)>=(len(out)-1) if fast else len(calls)==0
                    samples.append({'fast':fast,'repeat':repeat,'seconds':elapsed,'fps':len(out)/elapsed,
                                    'process_cores':cpu/elapsed,'fast_decoded_frames':len(calls),
                                    'relative_l2':float(np.linalg.norm(out-reference)/np.linalg.norm(reference))})
                    print(case,'fast' if fast else 'before',round(len(out)/elapsed,2),'fps','fast frames',len(calls),flush=True)
            results[case]={'frames':len(reference),'warmups':warm,'samples':samples,
                           'before_median_fps':median(x['fps'] for x in samples if not x['fast']),
                           'after_median_fps':median(x['fps'] for x in samples if x['fast'])}
            close_model(c);del c,model;gc.collect()
    record={'results':results,'decoder_workers':a.workers,'integration_workers':a.workers,'fixed_threads_per_worker':1,
            'dynamic_rayon_threads':a.workers,'threshold_indices':ids,'threshold_compressed_hashes':chunk_hashes,'threshold_frame_hashes':frame_hashes,
            'codec':fastHdf5._codec.build_info(),'source':str(a.hdf5),'settings':{'bins':2000,'method':'pixel_split','polarization':.965,'precision':'float64','static_mask':str(a.mask),'threshold':230},
            'source_hashes':{str(f):hashlib.sha256(f.read_bytes()).hexdigest() for f in [Path('dioptas/model/loader/fastHdf5.py'),Path('dioptas/model/loader/hdf5Loader.py'),Path('dioptas/model/util/integration.py'),Path('dioptas/model/MapModel.py'),Path(__file__)]},
            'limits':'Three alternating paired passes, warm OS cache, concurrent user work. Before disables new optional fast codec and per-frame prefetch to reproduce prior reader behavior; fixed mode still uses its existing 8-decoder stock pipeline, dynamic mode uses the prior serial loader. After uses production reader and prefetch, no adapter. File loading, masks, processing, normalization, integration and map reduction are timed; fixture/reference preparation and LUT warmup excluded. GUI rendering excluded.'}
    a.output.write_text(json.dumps(record,indent=2)+'\n');print(json.dumps({k:{'before':v['before_median_fps'],'after':v['after_median_fps']} for k,v in results.items()},indent=2),flush=True)
    app.processEvents()


if __name__=='__main__':main()
