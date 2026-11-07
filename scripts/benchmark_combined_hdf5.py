"""Full Qt open-to-pattern timing with one decode for display and integration.

Run with QT_QPA_PLATFORM=offscreen RAYON_NUM_THREADS=8 OMP_NUM_THREADS=1
OPENBLAS_NUM_THREADS=1. Uses real image/pattern controllers and the coordinator.
Offscreen paint preparation/event handling is included; physical monitor/GPU
presentation and human interaction are not measured. Both modes reopen the same
selected frame so the legacy loader cannot reuse its currentframe pixel cache.
"""
import argparse
import hashlib
import json
import time
from pathlib import Path

import numpy as np
from qtpy.QtWidgets import QApplication
from dioptas.model.DioptasModel import DioptasModel
from dioptas.controller.integration_coordinator import AsyncIntegrationCoordinator
from dioptas.widgets.integration import IntegrationWidget
from dioptas.controller.integration.ImageController import ImageController
from dioptas.controller.integration.PatternController import PatternController


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--hdf5', type=Path, required=True)
    p.add_argument('--poni', type=Path, required=True)
    p.add_argument('--mask-u8', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--frames', type=int, default=12)
    p.add_argument('--repeats', type=int, default=3)
    p.add_argument('--debounce-ms', type=int, default=25)
    args = p.parse_args()
    app = QApplication.instance() or QApplication([])
    model = DioptasModel(); config = model.current_configuration
    config.auto_integrate_pattern = False; config.auto_integrate_cake = False
    config.integration_rad_points = 2000; config.trim_trailing_zeros = False
    config.integration_unit = '2th_deg'; config.use_mask = True
    config.img_model.load(str(args.hdf5))
    cal = config.calibration_model; cal.load(str(args.poni))
    cal.use_dioptrin = True; cal.dioptrin_num_workers = 8; cal.polarization_factor = .965
    config.mask_model.set_mask_data(np.fromfile(args.mask_u8, np.uint8).reshape(config.img_model.raw_img_data.shape).astype(bool))
    widget = IntegrationWidget(); widget.resize(1200,900)
    image_controller = ImageController(widget, model)
    pattern_controller = PatternController(widget, model)
    coordinator = AsyncIntegrationCoordinator(model, debounce_ms=args.debounce_ms)
    callback = config.img_model.combined_frame_loader
    widget.show(); app.processEvents()
    config.auto_integrate_pattern = True
    failures = []; events = []; stats = {}
    coordinator.failed.connect(lambda *a: failures.append(str(a)))
    coordinator.completed.connect(lambda *a: events.append(time.perf_counter()))
    create = config.create_integration_task
    def timed_snapshot(**kwargs):
        start=time.perf_counter();task=create(**kwargs)
        stats['snapshot_seconds']=time.perf_counter()-start
        stats['prepared']=task.precomputed_pattern is not None
        stats['reread']=task.fused_hdf5_source is not None
        return task
    config.create_integration_task=timed_snapshot
    compute=coordinator.integration_engine.compute
    def timed_compute(task):
        start=time.perf_counter();result=compute(task)
        stats['worker_seconds']=time.perf_counter()-start
        return result
    coordinator.integration_engine.compute=timed_compute
    native=coordinator.integration_engine.load_combined
    def timed_native(request):
        stats['native_calls']=stats.get('native_calls',0)+1
        start=time.perf_counter();result=native(request)
        stats['native_load_seconds']=time.perf_counter()-start
        return result
    coordinator.integration_engine.load_combined=timed_native
    def drain():
        deadline=time.perf_counter()+60
        while coordinator.is_busy:
            app.processEvents()
            if time.perf_counter()>deadline:raise TimeoutError('Qt integration did not complete')
            time.sleep(.001)
        app.processEvents()
        if failures:raise AssertionError(failures)
    drain()
    report={'scope':'real Qt file load -> display update -> snapshot -> dedicated worker -> pattern model/plot update',
        'cache':'warm OS cache and prepared lookup; each timed operation reopens the frame',
        'frames':np.linspace(0,config.img_model.series_max-1,args.frames,dtype=int).tolist(),
        'shape':config.img_model.raw_img_data.shape,'bins':2000,'unit':'2th_deg','polarization':.965,
        'precision':'native integer display counts; float64 weights/sums/normalization/Poisson terms',
        'effective_mask_sha256':hashlib.sha256(config.create_integration_task(allow_fused=False).mask.tobytes()).hexdigest(),
        'debounce_ms':args.debounce_ms,'controllers':['ImageController','PatternController'],
        'display':'offscreen Qt at 1200x900; GPU/physical monitor presentation not measured',
        'cold':[],'timings':[]}
    # Warm compressed chunks without decoding any image for the timed path.
    dataset = config.img_model.loader.fabio_image.dataset
    for index in report['frames']:
        dataset.id.read_direct_chunk((index, 0, 0))
    references={}
    def run(mode,index,errors,repeat):
        drain();events.clear();stats.clear()
        config.img_model.combined_frame_loader=callback if mode=='combined' else None
        start=time.perf_counter();config.img_model.load(str(args.hdf5),index)
        load_seconds=time.perf_counter()-start
        drain()
        assert events and not failures
        assert stats['prepared']==(mode=='combined'),stats
        assert not stats['reread']
        assert stats.get('native_calls',0)==(1 if mode=='combined' else 0)
        end=events[-1]
        row=dict(stats,mode=mode,frame=index,poisson=errors,repeat=repeat,
                 load_display_seconds=load_seconds,open_to_pattern_seconds=end-start,
                 after_event_flush_seconds=time.perf_counter()-start)
        # Numeric and pixel checks are deliberately outside the timed interval.
        pattern=config.pattern_model.pattern
        result=(np.array(pattern.x),np.array(pattern.y),
            np.array(config.pattern_model.errors) if errors else None)
        pixels=config.img_model.raw_img_data
        digest=hashlib.sha256(pixels.tobytes()).hexdigest()
        key=(index,errors)
        if key in references:
            before=references[key]
            assert digest==before[0] and pixels.dtype.str==before[1]
            for a,b in zip(result,before[2]):
                if a is not None:np.testing.assert_allclose(a,b,rtol=2e-12,atol=1e-10)
            row['max_scaled_error']=float(np.max(np.abs(result[1]-before[2][1])/np.maximum(1,np.abs(before[2][1]))))
        else:references[key]=(digest,pixels.dtype.str,result)
        row['display_sha256']=digest
        return row
    try:
        for mode in ['legacy','combined']:
            report['cold'].append(run(mode,0,False,-1))
            print('Cold',mode,report['cold'][-1]['open_to_pattern_seconds'],flush=True)
        for errors in [False,True]:
            config.calculate_poisson_errors=errors;drain()
            for repeat in range(args.repeats):
                modes=['legacy','combined'] if repeat%2==0 else ['combined','legacy']
                for mode in modes:
                    for index in report['frames']:
                        report['timings'].append(run(mode,index,errors,repeat))
                    print('Completed',mode,'Poisson',errors,'pass',repeat,flush=True)
                    args.output.parent.mkdir(parents=True,exist_ok=True)
                    args.output.write_text(json.dumps(report,indent=2)+'\n')
    finally:
        coordinator.shutdown();widget.close();app.processEvents()
    # Keep controllers alive until all measured Qt deliveries are complete.
    assert image_controller and pattern_controller


if __name__=='__main__':main()
