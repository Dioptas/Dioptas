"""Alternate the frozen and candidate release kernels; retain every sample."""
from pathlib import Path
import subprocess, os, json
import numpy as np
BASE=Path(__file__).resolve().parent
OUT=BASE/'auto-comparison'
OUT.mkdir(exist_ok=True)
OLD=BASE/'before/runner/target/release/compare-integration-cached'
NEW=BASE.parent/'integration-layout-crossover/selector-runner/target/release/compare-polygon-auto'
for rep in range(3):
    for kind in (['before','after'] if rep%2==0 else ['after','before']):
        d=OUT/kind/f'run{rep+1}';d.mkdir(parents=True,exist_ok=True)
        for f in ['input.json','image.f64','mask.u8']:
            if not (d/f).exists():os.link(BASE/'before'/f,d/f)
        with (d/'run.log').open('w') as log:
            subprocess.run([str(OLD if kind=='before' else NEW),str(d)],env={**os.environ,'RAYON_NUM_THREADS':'8'},stdout=log,stderr=log,check=True)
        print(kind,rep+1,'done',flush=True)
    for name in ['polygon_1d','pyfai_1d','polygon_cake','pyfai_cake']:
        a=np.fromfile(OUT/'before'/f'run{rep+1}'/(name+'.f64'),dtype='<f8')
        b=np.fromfile(OUT/'after'/f'run{rep+1}'/(name+'.f64'),dtype='<f8')
        if name in ['polygon_1d','polygon_cake']:
            np.testing.assert_allclose(a,b,rtol=2e-14,atol=2e-10)
        else:
            assert np.array_equal(a.view('u8'),b.view('u8')),(name,np.max(abs(a-b)))
print('Polygon CSR/CSC patterns and cakes agree within 2e-14 relative / 2e-10 absolute tolerance; compatibility outputs remain bitwise identical')
for kind in ['before','after']:
    agg={}
    for rep in range(3):
        j=json.loads((OUT/kind/f'run{rep+1}/timing.json').read_text())
        for t in j['timing']:
            r=agg.setdefault(t['case'],{'coldMs':[],'warmMs':[]})
            for k in r:r[k]+=t[k]
    print(kind,{name:{k:float(np.median(v)) for k,v in r.items()} for name,r in agg.items()})
    (OUT/kind/'aggregate.json').write_text(json.dumps(agg,indent=2)+'\n')
