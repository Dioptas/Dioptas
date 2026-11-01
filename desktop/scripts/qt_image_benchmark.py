"""Time real Qt file stepping in an isolated app, without user settings writes.

Use the .dio captured by binary_native_smoke.js for matching geometry/settings.
Qt has an asynchronous processing path, so measure image paint and processing
completion independently. A 2 x 16 ms settling interval is also reported to
approximate the native benchmark's two requestAnimationFrame callbacks; this
is not a physical display/compositor latency measurement.
"""
import argparse
import json
import os
from pathlib import Path
import statistics
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[2]
source_parser=argparse.ArgumentParser(add_help=False)
source_parser.add_argument('--qt-source',type=Path,default=ROOT)
source_options,_=source_parser.parse_known_args()
QTROOT=source_options.qt_source.resolve()
sys.path.insert(0, str(QTROOT))
os.environ.setdefault('QT_API', 'pyqt6')

from qtpy import QtWidgets, QtCore, QtTest
import numpy as np
from dioptas.controller.MainController import MainController


def summary(values):
    return {'median':statistics.median(values), 'min':min(values), 'max':max(values), 'count':len(values)}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project',type=Path,required=True)
    parser.add_argument('--qt-source',type=Path,default=QTROOT)
    parser.add_argument('--samples',type=int,default=8)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--synchronous',action='store_true')
    parser.add_argument('--native-report',type=Path,default=ROOT/'desktop/artifacts/qt-comparison-native.json')
    args=parser.parse_args()
    if args.samples < 2 or args.samples % 2:
        parser.error('--samples must be positive and even, ending on image_001')
    app=QtWidgets.QApplication([])
    app.setApplicationName('Dioptas Qt file-switch benchmark')
    settings=tempfile.TemporaryDirectory(prefix='dioptas-qt-benchmark-')
    controller=MainController(use_settings=False,settings_directory=settings.name,run_async_processing=not args.synchronous)
    window=controller.widget
    native = json.loads(args.native_report.read_text())['binaryTransfer'] if args.native_report.exists() else {}
    size = native.get('windowSize',[1440,940])
    window.resize(*size)
    controller.show_window()
    cc=controller.calibration_controller
    model=controller.model
    paint={'time':0.,'file':None}
    measure={}
    item=cc.widget.img_widget.data_img_item
    original_paint=item.paint
    def painted(*a,**kw):
        result=original_paint(*a,**kw)
        paint['time']=time.perf_counter()
        paint['file']=model.img_model.filename
        if measure and Path(paint['file']).name==measure['file']:
            measure.setdefault('imagePaint',paint['time'])
        return result
    item.paint=painted
    view=cc.widget.img_widget.pg_layout
    original_view_paint=view.paintEvent
    def view_painted(event):
        result=original_view_paint(event)
        if measure and Path(model.img_model.filename).name==measure['file']:
            measure.setdefault('viewPaint',time.perf_counter())
        return result
    view.paintEvent=view_painted
    if controller.integration_coordinator is not None:
        def completed(*_):
            if measure and Path(model.img_model.filename).name==measure['file']:
                measure['complete']=time.perf_counter()
        controller.integration_coordinator.completed.connect(completed)

    def busy():
        job=controller.integration_coordinator
        return bool(job and job.is_busy)

    def wait_for(predicate,limit=15):
        start=time.perf_counter()
        while not predicate():
            if time.perf_counter()-start>limit:
                raise TimeoutError('Qt did not finish: '+str({'busy':busy(),'paint':paint,'file':model.img_model.filename}))
            app.processEvents(QtCore.QEventLoop.AllEvents,5)
            QtTest.QTest.qWait(1)

    reports=[]
    try:
        model.load(str(args.project.resolve()))
        cc.widget.set_wizard_step(0)
        controller.activate_mode(0)
        c=model.current_configuration
        c.calibration_model.use_dioptrin=False
        wait_for(lambda:not busy())
        QtTest.QTest.qWait(100)
        matched_pattern=model.pattern.data[1].copy()
        assert c.integration_rad_points==600 and c.cake_azimuth_points==90
        assert model.img_model.img_data.shape==(2048,2048)

        for label,pattern,cake in [('image_only',False,False),('pattern_only',True,False),('pattern_and_cake',True,True)]:
            c.auto_integrate_pattern=pattern
            c.auto_integrate_cake=cake
            wait_for(lambda:not busy())
            QtTest.QTest.qWait(100)
            # Start each sequence on image_001, then warm both image/histogram
            # caches and the persistent integrator before timing.
            if Path(model.img_model.filename).name!='image_001.tif':
                model.img_model.load(str(ROOT/'dioptas/tests/data/image_001.tif'))
                wait_for(lambda:not busy())
            times=[]
            for i in range(args.samples+4):
                direction=1 if i%2==0 else -1
                expected='image_002.tif' if direction==1 else 'image_001.tif'
                button=cc.widget.load_next_img_btn if direction==1 else cc.widget.load_previous_img_btn
                measure.clear()
                measure['file']=expected
                start=time.perf_counter()
                QtTest.QTest.mouseClick(button,QtCore.Qt.LeftButton)
                returned=time.perf_counter()
                wait_for(lambda:'viewPaint' in measure and not busy())
                first_paint=measure['imagePaint']
                viewport_paint=measure['viewPaint']
                complete=measure.get('complete',returned) if (pattern or cake) else returned
                if not args.synchronous and (pattern or cake):
                    assert 'complete' in measure and complete>=start, 'No integration completion timestamp'
                all_ready=max(complete,viewport_paint)
                # Let queued plot paints finish, then allow two frame intervals.
                app.processEvents(QtCore.QEventLoop.AllEvents,5)
                QtTest.QTest.qWait(16)
                QtTest.QTest.qWait(16)
                settled=time.perf_counter()
                assert c.auto_integrate_pattern==pattern and c.auto_integrate_cake==cake
                assert model.img_model.img_data.shape==(2048,2048)
                assert np.array_equal(cc.widget.img_widget.img_data,model.img_model.img_data)
                if i>=4:
                    times.append({'file':expected,'slotReturnMs':1000*(returned-start),
                        'detectorPaintMs':1000*(first_paint-start),
                        'viewportPaintMs':1000*(viewport_paint-start),
                        'processingCompleteMs':1000*(complete-start),
                        'allReadyMs':1000*(all_ready-start),'settledMs':1000*(settled-start)})
            row={'scenario':label,'samples':times,'summary':{
                key:summary([v[key] for v in times]) for key in ['slotReturnMs','detectorPaintMs','viewportPaintMs','processingCompleteMs','allReadyMs','settledMs']}}
            if pattern:
                current=model.pattern.data[1]
                row['patternRelativeL2DifferenceToSavedTauri']=float(np.linalg.norm(current-matched_pattern)/max(np.linalg.norm(matched_pattern),1e-30))
                np.testing.assert_allclose(current,matched_pattern,rtol=2e-5,atol=1e-5)
            reports.append(row)
            print(label,json.dumps({k:round(v['median'],2) for k,v in row['summary'].items()}),flush=True)
        assert [window.width(),window.height()]==size
        if 'devicePixelRatio' in native:
            assert window.devicePixelRatioF()==native['devicePixelRatio']
        result={'implementation':'Qt/Python','qtSourceRoot':str(QTROOT),'asyncProcessing':not args.synchronous,
            'files':['image_001.tif','image_002.tif'],'sourceShape':[2048,2048],
            'project':str(args.project.resolve()),'radialBins':c.integration_rad_points,'cakeAzimuthBins':c.cake_azimuth_points,
            'unit':c.integration_unit,'geometry':{key:float(getattr(c.calibration_model.pattern_geometry,key)) for key in ['dist','poni1','poni2','rot1','rot2','rot3','wavelength']},'windowSize':[window.width(),window.height()],
            'devicePixelRatio':window.devicePixelRatioF(),'qtVersion':QtCore.qVersion(),
            'paintEndpoint':'end of the detector GraphicsLayoutWidget.paintEvent; the ImageItem paint is also recorded',
            'settledEndpoint':'paint and all requested integrations complete, then two 16 ms Qt waits',
            'reports':reports}
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(result,indent=2)+'\n')
        window.grab().save(str(args.output.with_suffix('.png')))
    finally:
        window.close()
        app.processEvents()
        settings.cleanup()

if __name__=='__main__':main()
