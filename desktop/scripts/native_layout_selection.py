"""Matched native CSC/CSR/Automatic patterns, changed settings and persistence."""
from pathlib import Path
import json, tempfile
import numpy as np
import tifffile
from native_reference_client import Native, ROOT

OUT=ROOT/'desktop/artifacts/integration-layout-crossover'
OUT.mkdir(parents=True,exist_ok=True)
receipts=[]
arrays={}
def compare(a,b):
    result={}
    for key in ['x','y','sigma']:
        u,v=a.get(key),b.get(key)
        if u is None or v is None:
            assert u is None and v is None;continue
        u,v=np.asarray(u),np.asarray(v)
        assert u.shape==v.shape
        rel=float(np.linalg.norm(u-v)/max(np.linalg.norm(u),np.finfo(float).tiny))
        assert rel<2e-12,(key,rel)
        result[key]=dict(relativeL2=rel,maxAbsolute=float(np.max(abs(u-v))),bitwise=bool(np.array_equal(u.view('u8'),v.view('u8'))))
    return result

with Native(env={'RAYON_NUM_THREADS':'8'}) as n, tempfile.TemporaryDirectory(prefix='dioptas-layout-') as tmp:
    def call(command,**kw):return n.call(command,requested_products=dict(cake=False,rings=False),**kw)
    call('open_calibration',path=str(ROOT/'dioptas/tests/data/CeO2_Pilatus1M.poni'))
    call('integration_settings',bins=1000,trim_zeros=False,method='polygon')
    call('open_image',path=str(ROOT/'dioptas/tests/data/CeO2_Pilatus1M.tif'))
    assert call('state')['state']['integration']['sparseLayout']=='csr'
    mask=(tifffile.imread(ROOT/'dioptas/tests/data/CeO2_Pilatus1M.tif')[::-1] < 0).astype('u1')
    maskfile=Path(tmp)/'gaps.npy';np.save(maskfile,mask);call('mask_file',path=str(maskfile))
    for index,options in enumerate([
        dict(bins=128,poisson_errors=False),dict(bins=1000,poisson_errors=False),
        dict(bins=8000,poisson_errors=False),dict(bins=1000,poisson_errors=True),
        dict(bins=129,unit='q_A^-1',poisson_errors=True),dict(unit='d_A'),
        dict(unit='2th_deg',polarization=.7),dict(use_mask=False),dict(use_mask=True),
    ]):
        reference=call('integration_settings',sparse_layout='csc',**options)['pattern']
        for layout in ['csr','auto']:
            reply=call('integration_settings',sparse_layout=layout)
            assert reply['state']['integration']['sparseLayout']==layout
            for warm in [False,True]:
                got=call('integrate')['pattern'] if warm else reply['pattern']
                receipts.append(dict(case=index,options=options,layout=layout,warm=warm,metrics=compare(reference,got)))
                arrays[f'{index}_{layout}_{warm}']=np.asarray(got['y'])
    call('integration_settings',sparse_layout='auto')
    project=Path(tmp)/'layout.dio';call('save_project',path=str(project))
    call('integration_settings',sparse_layout='csr')
    restored=call('open_project',path=str(project))
    assert restored['state']['integration']['sparseLayout']=='auto'
    before=call('state')['state']['integration']['sparseLayout']
    invalid=n.invoke('integration_settings',sparse_layout='unknown',requested_products=dict(cake=False,rings=False))
    assert not invalid['ok']
    assert call('state')['state']['integration']['sparseLayout']==before

(OUT/'desktop-layout-equality.json').write_text(json.dumps(dict(comparisons=receipts,projectRestore=True,invalidAtomic=True),indent=2)+'\n')
np.savez(OUT/'desktop-layout-patterns.npz',**arrays)
print(f'{len(receipts)} native layout comparisons pass; project choice restores; invalid input is atomic')
