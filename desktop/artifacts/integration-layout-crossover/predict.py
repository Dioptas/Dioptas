"""Broad resident 1D layout estimate, matching Dioptrin Automatic mode."""
import argparse,json
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--pixels',type=int,required=True)
p.add_argument('--bins',type=int,required=True)
p.add_argument('--threads',type=int,default=8)
p.add_argument('--poisson',action='store_true')
p.add_argument('--batch',action='store_true')
a=p.parse_args()
threshold=8_000_000
exception=a.pixels>=threshold and not a.poisson and a.bins>=2000
layout='csc' if a.batch or a.pixels<=0 or a.bins<=0 or a.threads<=0 or exception else 'csr'
print(json.dumps(dict(layout=layout,largeImageThresholdPixels=threshold,
 note='Ballpark: CSR generally; CSC for large images at high bins without errors. CSR is the desktop default; Automatic is optional. Parallel/streamed workers retain CSC. Manual overrides are available.'),indent=2))
