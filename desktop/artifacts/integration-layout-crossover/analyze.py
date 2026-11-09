"""Fit a bounded layout prior; retain detector-family holdout results."""
from pathlib import Path
from collections import defaultdict
import json, csv, hashlib, platform, subprocess
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

OUT = Path(__file__).resolve().parent
meta = json.loads((OUT/'inputs.json').read_text())
raw = [json.loads(s) for s in (OUT/'results.jsonl').read_text().splitlines()]
groups = defaultdict(list)
for r in raw:
    groups[(r['image'], r['pixels'], r['bins'], r['batch'], r['errors'])].append(r)

def features(pixels, bins, batch, errors):
    x, z, e, b = np.log2(pixels/1e6), np.log2(bins/1000), float(errors), float(batch)
    return [1, x, z, z*z, x*z, e, e*x, e*z, b, b*x, b*z]

rows = []
for (image, pixels, bins, batch, errors), rs in groups.items():
    d = {}
    for layout in ['csr', 'csc', 'resident']:
        samples = [v for r in rs for t in r['records'] if t['layout']==layout for v in t['samplesMsPerFrame']]
        d[layout] = float(np.median(samples))
        d[layout+'Q25'], d[layout+'Q75'] = map(float, np.percentile(samples, [25,75]))
    ratio = d['csc']/d['csr']
    rows.append(dict(image=image,pixels=pixels,bins=bins,batch=batch,errors=errors,
        runs=len(rs), **d, ratio=ratio,
        winner='CSR' if ratio>1.1 else 'CSC' if ratio<1/1.1 else 'tie'))
X = np.array([features(r['pixels'],r['bins'],r['batch'],r['errors']) for r in rows])
y = np.log([r['ratio'] for r in rows])
coef = np.linalg.lstsq(X,y,rcond=None)[0]

def scores(actual,pred):
    decisive=abs(actual)>np.log(1.1)
    regret=np.where(pred>0,np.maximum(0,-actual),np.maximum(0,actual))
    return dict(cases=len(actual),decisiveCases=int(decisive.sum()),
        decisiveAccuracy=float(np.mean(np.sign(actual[decisive])==np.sign(pred[decisive]))),
        logRmse=float(np.sqrt(np.mean((actual-pred)**2))),
        meanSlowdown=float(np.mean(np.exp(regret))),worstSlowdown=float(np.max(np.exp(regret))))

holdouts={}
oof=np.zeros_like(y)
for family in ['pilatus300k','pilatus1m','marccd4m','eiger']:
    test=np.array([r['image'].startswith(family) for r in rows])
    c=np.linalg.lstsq(X[~test],y[~test],rcond=None)[0]
    oof[test]=X[test]@c
    holdouts[family]=scores(y[test],oof[test])
for r,p in zip(rows,X@coef):
    r['predictedRatio']=float(np.exp(p))
    r['recommendation']='CSR' if p>np.log(1.3) else 'CSC' if p<-np.log(1.3) else 'measure'
with (OUT/'summary.csv').open('w') as f:
    w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
model=dict(formula='ln(CSC_ms/CSR_ms) = dot(coefficients, [1,x,z,z*z,x*z,e,e*x,e*z,b,b*x,b*z]); x=log2(pixels/1e6), z=log2(bins/1000), e=Poisson, b=parallelFrames',
    coefficients=coef.tolist(), threads=8,pixelRange=[287625,10138296],binRange=[128,8000],
    training=scores(y,X@coef),detectorFamilyHoldout=holdouts,
    pooledHoldout=scores(y,oof),guardBandRatio=1.3,
    scope='Resident float64 fixed-mask polygon 1D, M4 Pro, 8 Rayon threads. Prior only; measure locally. Not a cake, strict, dynamic-mask or fused streaming predictor.',
    inputSha256=hashlib.sha256((OUT/'results.jsonl').read_bytes()).hexdigest())
(OUT/'predictor.json').write_text(json.dumps(model,indent=2)+'\n')
(OUT/'summary.json').write_text(json.dumps(dict(records=len(raw),uniqueCases=len(rows),model=model,rows=rows),indent=2)+'\n')

images=[m['id'] for m in meta['images']]
labels={m['id']:m['id']+f" ({m['pixels']/1e6:.2f} MP)" for m in meta['images']}
fig,axs=plt.subplots(2,2,figsize=(13,7),layout='constrained')
for batch in [False,True]:
 for errors in [False,True]:
    ax=axs[int(errors),int(batch)]
    a=np.full((len(images),len(meta['bins'])),np.nan)
    for r in rows:
        if r['batch']==batch and r['errors']==errors:a[images.index(r['image']),meta['bins'].index(r['bins'])]=r['ratio']
    im=ax.imshow(np.log2(a),vmin=-2,vmax=2,cmap='RdBu_r',aspect='auto')
    for (i,j),v in np.ndenumerate(a):
        if np.isfinite(v):ax.text(j,i,f'{v:.2f}',ha='center',va='center',fontsize=8,color='white' if abs(np.log2(v))>1 else 'black')
    ax.set_xticks(range(len(meta['bins'])),meta['bins']);ax.set_yticks(range(len(images)),[labels[x] for x in images],fontsize=8)
    ax.set_xlabel('Radial bins');ax.set_title(('Parallel frames' if batch else 'Single frame')+(' · Poisson errors' if errors else ' · intensity only'))
fig.colorbar(im,ax=axs,label='log₂(CSC time / CSR time): red = CSR faster; blue = CSC faster',shrink=.85)
fig.suptitle('Polygon 1D layout crossover · 8 threads · medians · ratios within 1/1.1–1.1 treated as ties')
for ext in ['png','svg']:fig.savefig(OUT/f'layout-crossover.{ext}',dpi=180)
plt.close(fig)

fig,axs=plt.subplots(1,2,figsize=(10,4),layout='constrained')
for batch in [False,True]:
 ax=axs[int(batch)]
 for errors,marker in [(False,'o'),(True,'^')]:
  for image in images:
   rr=sorted([r for r in rows if r['batch']==batch and r['errors']==errors and r['image']==image],key=lambda r:r['bins'])
   ax.plot([r['bins'] for r in rr],[r['ratio'] for r in rr],marker=marker,label=labels[image]+(' +σ' if errors else ''),lw=1,ms=4)
 ax.axhspan(1/1.1,1.1,color='gray',alpha=.2);ax.axhline(1,color='black',lw=.7)
 ax.set(xscale='log',yscale='log',xlabel='Radial bins',ylabel='CSC / CSR time',title='Parallel frames' if batch else 'Single frame')
 ax.grid(alpha=.15);ax.tick_params(which='both',direction='in',top=True,right=True)
axs[1].legend(fontsize=6,loc='upper left',bbox_to_anchor=(1.02,1))
for ext in ['png','svg']:fig.savefig(OUT/f'layout-curves.{ext}',dpi=180)
plt.close(fig)
print(json.dumps({k:v for k,v in model.items() if k not in ['scope','formula','inputSha256']},indent=2))
