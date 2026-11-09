"""Independent pyFAI full-splitting oracle for the native Rust desktop.

Python is a reference process only; the tested worker cannot execute Python.
"""
import json
import tempfile
from pathlib import Path
import h5py
import numpy as np
import pyFAI
from pyFAI.detectors import Detector
from pyFAI.integrator.azimuthal import AzimuthalIntegrator
from pyFAI.ext.splitPixel import fullSplit1D_engine, fullSplit2D_engine
from native_reference_client import Native, ROOT

receipts = []
shape = (24, 32)
rows, cols = np.indices(shape)
data = (30 + rows * 3 + cols * 2 + 120 * np.exp(-((rows-13)**2+(cols-17)**2)/30)).astype(float)
geometry = dict(dist=.08, poni1=-.0013, poni2=-.0021, rot1=.007, rot2=-.011, rot3=.02, pixel1=.0001, pixel2=.00012, wavelength=.5e-10, polarization_factor=.6)

def edges(centers):
    centers=np.asarray(centers)
    step=centers[1]-centers[0]
    return [centers[0]-.5*step, centers[-1]+.5*step]

def limits_for_reference(bounds):
    return (bounds[0], bounds[1]/(1+np.finfo(np.float32).eps))

with tempfile.TemporaryDirectory(prefix="dioptas-pyfai-split-") as directory, Native() as native:
    directory=Path(directory)
    source=directory/'counts.h5'
    with h5py.File(source,'w') as f: f['counts']=data[::-1]
    native.call('manual_geometry', convention='pyfai', values=geometry)
    native.call('integration_settings', bins=64, cake_bins=24, method='pyfai_full', poisson_errors=True, trim_zeros=False)
    native.call('open_image', path=str(source), dataset='counts')
    native.call('display_products', cake=True)
    ai=AzimuthalIntegrator(detector=Detector(pixel1=geometry['pixel1'],pixel2=geometry['pixel2']), **{k:v for k,v in geometry.items() if k not in ('pixel1','pixel2','polarization_factor')})
    for unit in ('2th_deg','q_A^-1','d_A'):
      actual_unit='2th_deg' if unit=='d_A' else unit
      positions=ai.array_from_unit(shape,typ='corner',unit=actual_unit)
      for solid in (True,False):
        for sector in (None,[20.,65.],[150.,-150.]):
          result=native.call('integration_settings', unit=unit, solid_angle=solid, azimuth_range=sector, cake_azimuth_range=sector)
          assert result['state']['integration']['method']=='pyfai_full'
          x=np.asarray(result['pattern']['x'])
          if unit=='d_A': x=2*np.degrees(np.arcsin(geometry['wavelength']*1e10/(2*x)))
          radial=edges(x)
          azimuth=None if sector is None else np.radians([sector[0],sector[1]+(360 if sector[1]<=sector[0] else 0)])
          pol=ai.polarization(shape,factor=.6)
          sa=ai.solidAngleArray(shape) if solid else None
          reference=fullSplit1D_engine(positions,data,bins=64,pos0_range=limits_for_reference(radial),pos1_range=azimuth,solidangle=sa,polarization=pol,variance=data,chiDiscAtPi=sector is None or sector[1]>=sector[0])
          np.testing.assert_allclose(result['pattern']['y'],reference.intensity,rtol=3e-5,atol=2e-4)
          np.testing.assert_allclose(result['pattern']['sigma'],reference.sigma,rtol=3e-5,atol=2e-5)
          # Cakes remain 2theta, irrespective of the selected 1D coordinate.
          cake=native.raster(result,'cake')
          cr=edges(np.linspace(*result['cake']['radialRange'],64))
          ca=np.radians(edges(np.linspace(*result['cake']['azimuthRange'],24)))
          reference2=fullSplit2D_engine(ai.array_from_unit(shape,typ='corner',unit='2th_deg'),data,bins=(64,24),pos0_range=limits_for_reference(cr),pos1_range=limits_for_reference(ca),solidangle=sa,polarization=pol,chiDiscAtPi=sector is None or sector[1]>=sector[0])
          np.testing.assert_allclose(cake,reference2.intensity,rtol=1e-4,atol=8e-4)
          receipts.append(dict(unit=unit,solidAngle=solid,azimuth=sector,maxIntensityDifference=float(np.max(np.abs(np.asarray(result['pattern']['y'])-reference.intensity)))))
    # Masking, warm reuse, changing methods, project ownership and Batch grids.
    native.call('integration_settings', unit='2th_deg',azimuth_range=None,cake_azimuth_range=None,solid_angle=True)
    masked=native.call('integration_roi', limits=[2,20,3,28])
    mask=np.ones(shape,dtype=np.int8);mask[2:20,3:28]=0
    x=masked['pattern']['x']; radial=edges(x)
    ref=fullSplit1D_engine(ai.array_from_unit(shape,typ='corner',unit='2th_deg'),data,bins=64,pos0_range=limits_for_reference(radial),mask=mask,variance=data,solidangle=ai.solidAngleArray(shape),polarization=ai.polarization(shape,factor=.6))
    np.testing.assert_allclose(masked['pattern']['y'],ref.intensity,rtol=3e-5,atol=2e-4)
    warm=native.call('integrate')
    assert warm['pattern']['y']==masked['pattern']['y']
    project=directory/'pyfai.dio'
    native.call('save_project',path=str(project))
    native.call('integration_settings',method='polygon')
    restored=native.call('open_project',path=str(project))
    assert restored['state']['integration']['method']=='pyfai_full'
    np.testing.assert_allclose(restored['pattern']['y'],masked['pattern']['y'],rtol=0,atol=0)
    batch=native.call('batch_load',paths=[str(source)])
    assert batch['state']['integration']['method']=='pyfai_full'
    # Combined duplicate detector: normalization is absolute solid angle.
    native.call('configuration',operation='duplicate')
    combined=native.call('combination_settings',patterns=True,cakes=True)
    scale=geometry['pixel1']*geometry['pixel2']/geometry['dist']**2
    cx=combined['pattern']['x']; cr=edges(cx)
    ref=fullSplit1D_engine(ai.array_from_unit(shape,typ='corner',unit='2th_deg'),data,bins=64,pos0_range=limits_for_reference(cr),mask=mask,variance=data,solidangle=ai.solidAngleArray(shape),polarization=ai.polarization(shape,factor=.6))
    np.testing.assert_allclose(np.asarray(combined['pattern']['y'])*scale,ref.intensity,rtol=3e-5,atol=2e-4)
    np.testing.assert_allclose(np.asarray(combined['pattern']['sigma'])*scale*np.sqrt(2),ref.sigma,rtol=3e-5,atol=2e-5)
    receipts.append(dict(projectRoundTrip=True,masked=True,batch=True,combined=True))
    # A meaningful wrapped sector crosses the azimuthal seam with signal on
    # both sides. Mask only the singular beam pixel neighborhood for parity.
    with Native() as seam:
        gp={**geometry,'poni1':.00125,'poni2':.00198,'rot1':0.,'rot2':0.,'rot3':0.}
        seam.call('manual_geometry',convention='pyfai',values=gp)
        seam.call('integration_settings',method='pyfai_full',bins=64,cake_bins=24,trim_zeros=False,poisson_errors=True)
        seam.call('open_image',path=str(source),dataset='counts')
        seam.call('display_products',cake=True)
        seam.call('mask_stroke',points=[[16,12]],radius=2.)
        cmask=(((rows-12)**2+(cols-16)**2)<=4).astype(np.int8)
        sai=AzimuthalIntegrator(detector=Detector(pixel1=gp['pixel1'],pixel2=gp['pixel2']),**{k:v for k,v in gp.items() if k not in ('pixel1','pixel2','polarization_factor')})
        for sector in (None,[-45.,45.],[150.,-150.]):
            wrapped=sector is not None and sector[1]<sector[0]
            if wrapped:sai.setChiDiscAtZero()
            else:sai.setChiDiscAtPi()
            positions=sai.array_from_unit(shape,typ='corner',unit='2th_deg')
            r=seam.call('integration_settings',azimuth_range=sector,cake_azimuth_range=sector)
            bounds=edges(r['pattern']['x'])
            arange=None if sector is None else np.radians([sector[0],sector[1]+(360 if wrapped else 0)])
            reference=fullSplit1D_engine(positions,data,bins=64,pos0_range=limits_for_reference(bounds),pos1_range=arange,mask=cmask,variance=data,solidangle=sai.solidAngleArray(shape),polarization=sai.polarization(shape,factor=.6),chiDiscAtPi=not wrapped)
            assert np.count_nonzero(reference.intensity)>0
            np.testing.assert_allclose(r['pattern']['y'],reference.intensity,rtol=5e-5,atol=5e-4)
            np.testing.assert_allclose(r['pattern']['sigma'],reference.sigma,rtol=5e-5,atol=5e-5)
            cr=edges(np.linspace(*r['cake']['radialRange'],64));ca=np.radians(edges(np.linspace(*r['cake']['azimuthRange'],24)))
            ref2=fullSplit2D_engine(positions,data,bins=(64,24),pos0_range=limits_for_reference(cr),pos1_range=limits_for_reference(ca),mask=cmask,variance=data,solidangle=sai.solidAngleArray(shape),polarization=sai.polarization(shape,factor=.6),chiDiscAtPi=not wrapped)
            actual=seam.raster(r,'cake')
            # The compatibility kernel deliberately rejects negative raster
            # areas. At near-zero coverage, Cython rounding can also create or
            # remove bins whose finite intensity is a ratio of tiny sums.
            # Verify every meaningfully covered bin and retain all exceptions.
            supported=np.abs(ref2.count)>=1e-6
            np.testing.assert_allclose(actual[supported],ref2.intensity[supported],rtol=1e-4,atol=8e-4)
            mismatch=~np.isclose(actual,ref2.intensity,rtol=1e-4,atol=8e-4)
            differences=[dict(bin=index.tolist(),native=float(actual[tuple(index)]),pyFAI=float(ref2.intensity[tuple(index)]),referenceWeight=float(ref2.count[tuple(index)])) for index in np.argwhere(mismatch)]
            assert all(abs(d['referenceWeight'])<1e-6 for d in differences), differences
            receipts.append(dict(seam=True,azimuth=sector,negligibleCoverageDifferences=differences))
        # The direct beam is deliberately not a bitwise compatibility claim.
        beam=seam.call('clear_mask')
        assert np.all(np.isfinite(beam['pattern']['y']))
        assert np.all(np.asarray(beam['pattern']['sigma'])>=0)
output=ROOT/'desktop/artifacts/native-pyfai-splitting.json'
output.parent.mkdir(exist_ok=True,parents=True)
output.write_text(json.dumps(dict(pyFAI=pyFAI.version,comparisons=receipts),indent=2)+'\n')
print(f'pyFAI {pyFAI.version}: {len(receipts)-1} matched 1D/cake cases, ROI, warm plans, project, Batch, combined detectors and beam safety passed')
