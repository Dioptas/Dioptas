"""Compare native contrast levels with Qt's actual AutoLevel/dummy filter."""
import argparse
import json
import tempfile
from pathlib import Path
import numpy as np
from dioptas.widgets.plot_widgets.utils import AutoLevel, detector_gap_mask
from native_reference_client import Native, ROOT


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image',type=Path)
    args=parser.parse_args()
    receipts=[]
    with tempfile.TemporaryDirectory() as temp, Native() as native:
        temp=Path(temp)
        cases=[]
        for flag in [0,-1,np.iinfo(np.int32).max]:
            row,col=np.indices((96,128))
            data=(100+row+col).astype(np.int32)
            data[:,40:44]=flag
            data[12,17]=6_000_000
            path=temp/f'flag-{flag}.npy'
            np.save(path,data)
            cases.append((path,data))
        data=np.arange(96*128,dtype=float).reshape(96,128)*.123-100
        data[:,40:44]=-1
        data[0,0]=np.nan
        path=temp/'floating.npy'
        np.save(path,data)
        cases.append((path,data))
        if args.image:
            from PIL import Image
            cases.append((args.image,np.asarray(Image.open(args.image))))
        for path,data in cases:
            native.call('open_image',path=str(path))
            for filtered in [True,False]:
                for mode in ['minmax','mean3std','2.5percentile']:
                    qt=AutoLevel()
                    qt.mode=mode
                    qt.filter_dummy=filtered
                    expected=qt.get_range(data)
                    native_mode='percentile' if mode=='2.5percentile' else mode
                    actual=native.call('image_levels',source='detector',mode=native_mode,percentile=2.5,filter_gaps=filtered)['levels']
                    np.testing.assert_allclose(actual,expected,rtol=2e-12,atol=1e-9)
                    receipts.append(dict(file=path.name,mode=mode,filterGaps=filtered,levels=actual))
    output=ROOT/'desktop/artifacts/native-map-selection/autolevel-parity.json'
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(receipts,indent=2)+'\n')
    print(f'{len(receipts)} native/Qt AutoLevel comparisons passed; dummy fills 0, -1 and int32 max, floating data and a retained valid high count.')
    if args.image:
        keep=detector_gap_mask(data)
        print('Real image: dummy-filter excluded',int((~keep).sum()),'pixels; valid maximum',float(data[keep].max()))

if __name__=='__main__':main()
