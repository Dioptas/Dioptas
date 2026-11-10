"""Independent Qt weighted_spread helper over pyFAI full-splitting overlaps.

The shipping worker is Rust with Python unavailable. Qt's pyFAI workflow selects
bbox overlaps; this test explicitly matches the desktop's full-splitting method.
"""
import json
import tempfile
from pathlib import Path
import fabio
import h5py
import numpy as np
import pyFAI
from pyFAI.detectors import Detector
from pyFAI.integrator.azimuthal import AzimuthalIntegrator
from pyFAI.ext.splitPixelFullCSR import FullSplitCSR_1d
from dioptas.model.util.spottiness import weighted_spread, relative_spread
from native_reference_client import Native, ROOT

receipts = []
with tempfile.TemporaryDirectory(prefix="dioptas-spread-") as tmp, Native() as native:
    tmp = Path(tmp)
    fixture = ROOT / "dioptas/tests/data/CeO2_Pilatus1M.tif"
    ai = pyFAI.load(str(fixture.with_suffix('.poni')))
    native.call('open_calibration', path=str(fixture.with_suffix('.poni')))
    native.call('integration_settings', bins=96, cake_bins=12, method='pyfai_full', azimuthal_std=True, poisson_errors=True, trim_zeros=False)
    native.call('open_image', path=str(fixture))
    data = fabio.open(str(fixture)).data[::-1].astype(float)
    # Exclude direct-beam singular pixels; full polygon behavior there is an
    # existing approximation, not a bitwise pyFAI compatibility claim.
    beam_mask = (ai.center_array(data.shape, unit='2th_rad') < np.radians(1.)).astype(np.int8)
    np.save(tmp/'beam.npy', beam_mask)
    native.call('mask_file',path=str(tmp/'beam.npy'))
    # Match scientific source order, independently established in detector tests.
    for unit, solid, sector in [('2th_deg', True, None), ('q_A^-1', False, [20., 65.])]:
        actual = native.call('integration_settings', unit=unit, solid_angle=solid, azimuth_range=sector)
        p = actual['pattern']; x = np.asarray(p['x']); step = x[1] - x[0]
        # pyFAI expands upper bounds by float32 epsilon.
        bounds = (x[0]-step/2, (x[-1]+step/2)/(1+np.finfo(np.float32).eps))
        mask = beam_mask
        lut = FullSplitCSR_1d(ai.array_from_unit(data.shape,typ='corner',unit=unit), bins=len(x), pos0_range=bounds,
            pos1_range=None if sector is None else np.radians(sector), mask=mask)
        norm = ai.polarization(data.shape, factor=.99).astype(float)
        if solid: norm *= ai.solidAngleArray(data.shape)
        mean, std = weighted_spread(lut.lut, data, norm)
        actual_mean = np.asarray(p['spottiness']['mean'], dtype=float)
        actual_std = np.asarray(p['spottiness']['std'], dtype=float)
        np.testing.assert_allclose(actual_mean, mean, rtol=1e-4, atol=.005)
        np.testing.assert_allclose(actual_std, std, rtol=2e-4, atol=.01, equal_nan=True)
        np.testing.assert_allclose(np.asarray(p['spottiness']['relative'],float), relative_spread(actual_mean,actual_std),rtol=2e-15,atol=0,equal_nan=True)
        assert not np.allclose(actual_std, np.asarray(p['sigma']))
        receipts.append(dict(image=fixture.name,unit=unit,solidAngle=solid,sector=sector,maxMeanDifference=float(np.nanmax(abs(actual_mean-mean))),maxStdDifference=float(np.nanmax(abs(actual_std-std)))))
    # Constant zero/negative/tiny means and a spatially heterogeneous frame.
    source = tmp/'special.h5'; shape=(32,40)
    yy,xx=np.indices(shape)
    special=np.stack([np.zeros(shape),np.full(shape,-2.),np.full(shape,1e-14),10+yy*3+xx])
    with h5py.File(source,'w') as f: f['counts']=special[:,::-1]
    native.call('clear_mask')
    native.call('manual_geometry',convention='pyfai',values=dict(dist=.08,poni1=-.002,poni2=-.003,rot1=0.,rot2=0.,rot3=0.,pixel1=.0001,pixel2=.0001,wavelength=5e-11,polarization_factor=0.))
    native.call('integration_settings',unit='2th_deg',bins=40,solid_angle=False,polarization=0.,azimuth_range=None)
    for frame in range(4):
        actual=native.call('open_image',path=str(source),dataset='counts',frame=frame,keep_calibration=True)
        diag=actual['pattern']['spottiness']
        mean=np.asarray(diag['mean'],float);std=np.asarray(diag['std'],float)
        np.testing.assert_allclose(np.asarray(diag['relative'],float),relative_spread(mean,std),rtol=2e-15,atol=0,equal_nan=True)
        if frame<3:
            if frame == 0:
                np.testing.assert_allclose(mean,0,atol=0)
                np.testing.assert_allclose(std,0,atol=0)
            elif frame == 1:
                assert np.all(mean < 0)
            else:
                assert np.all((mean > 0) & (mean < 1e-12))
            assert all(v is None for v in diag['relative'])
        receipts.append(dict(syntheticFrame=frame,undefinedRatios=all(v is None for v in diag['relative'])))
    # Native image background and flat correction precede population analysis.
    background=np.full(shape,3.)
    flat=1.+xx/50.
    np.save(tmp/'background.npy',background[::-1])
    np.save(tmp/'flat.npy',flat[::-1])
    native.call('integration_image_background',path=str(tmp/'background.npy'),scale=.5,offset=0.)
    actual=native.call('integration_flat_field',path=str(tmp/'flat.npy'),enabled=True)
    ai2=AzimuthalIntegrator(detector=Detector(pixel1=.0001,pixel2=.0001),dist=.08,poni1=-.002,poni2=-.003,wavelength=5e-11)
    x=np.asarray(actual['pattern']['spottiness']['x']);step=x[1]-x[0]
    lut=FullSplitCSR_1d(ai2.array_from_unit(shape,typ='corner',unit='2th_deg'),bins=len(x),pos0_range=(x[0]-step/2,(x[-1]+step/2)/(1+np.finfo(np.float32).eps)))
    mean,std=weighted_spread(lut.lut,(special[3]-.5*background)/(flat/flat.mean()),ai2.polarization(shape,factor=0.).astype(float))
    np.testing.assert_allclose(np.asarray(actual['pattern']['spottiness']['mean'],float),mean,rtol=1e-5,atol=1e-5)
    np.testing.assert_allclose(np.asarray(actual['pattern']['spottiness']['std'],float),std,rtol=2e-5,atol=1e-5)
    receipts.append(dict(imageBackground=True,flatCorrection=True))
output=ROOT/'desktop/artifacts/spottiness-reference.json'
output.parent.mkdir(parents=True,exist_ok=True)
output.write_text(json.dumps(dict(pyFAI=pyFAI.version,reference='Qt weighted_spread on independent pyFAI full CSR',comparisons=receipts),indent=2)+'\n')
print(f'{len(receipts)} independent spottiness cases passed')
