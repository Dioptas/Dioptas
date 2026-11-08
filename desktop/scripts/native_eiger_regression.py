"""Optional local Eiger reproduction and warm-cache end-to-end series benchmark.

Uses external user test data read-only. The Rust children cannot execute Python;
NumPy/Pillow/h5py only inspect their results in this reference-test parent.
"""
import argparse, json, statistics, tempfile, time
from pathlib import Path
import h5py
import numpy as np
from PIL import Image
import native_reference_client as client


def setup(n, folder):
    n.call("integration_settings", bins=2000, cake_bins=90, trim_zeros=False)
    n.call("open_image", path=str(folder / "eiger_0000.h5"))
    n.call("open_calibration", path=str(folder / "eiger_0000.poni"))
    n.call("mask_file", path=str(folder / "eiger_0000.mask"))


def mask_check(folder):
    expected = np.asarray(Image.open(folder / "eiger_0000.mask"), dtype=np.uint8)
    receipts=[]
    for name, frame in [("eiger_0000.tiff",0),("eiger_0000.h5",0),("eiger_0000.h5",389)]:
        with client.Native() as n:
            n.call("integration_settings",bins=2000,cake_bins=90,trim_zeros=False)
            opened=n.call("open_image",path=str(folder/name),frame=frame)
            n.call("open_calibration",path=str(folder/"eiger_0000.poni"))
            result=n.call("mask_file",path=str(folder/"eiger_0000.mask"))
            mask=n.raster(result,"mask").astype(bool)
            np.testing.assert_array_equal(mask,expected.astype(bool))
            image=n.raster(opened,"image")
            invalid=(image>=2**31-1)|~np.isfinite(image)
            receipt=dict(file=name,frame=frame,maskMatchesSavedFile=True,
                         invalidPixels=int(invalid.sum()),maskedInvalidPixels=int((invalid&mask).sum()),
                         verticallyReversedMaskWouldCover=int((invalid&mask[::-1]).sum()))
            assert receipt["invalidPixels"] == receipt["maskedInvalidPixels"],receipt
            assert receipt["verticallyReversedMaskWouldCover"] < receipt["maskedInvalidPixels"],receipt
            receipts.append(receipt)
    return receipts


def benchmark(executable, folder, frames, threads=8, full_map=False):
    client.EXECUTABLE=Path(executable)
    with client.Native(env={"DIOPTAS_INTEGRATION_THREADS":str(threads)}) as n, tempfile.TemporaryDirectory() as temp:
        setup(n,folder)
        seconds=[]
        for _ in range(3):
            start=time.perf_counter()
            n.call("batch_load",paths=[str(folder/"eiger_0000.h5")],start=1,stop=frames)
            seconds.append(time.perf_counter()-start)
        target=Path(temp)/"result.h5"
        n.call("integration_save_batch",path=str(target))
        with h5py.File(target) as f:
            patterns=f["processed/result/data"][:]
        receipt=dict(seconds=seconds,medianFps=frames/statistics.median(seconds),threads=threads,
                     diagnostics=n.call("integration_diagnostics")["integrationDiagnostics"])
        if full_map:
            start=time.perf_counter()
            r=n.call("map_load",paths=[str(folder/"eiger_0000.h5")])
            receipt["fullMap"]={"seconds":time.perf_counter()-start,"frames":r["map"]["points"]}
            receipt["fullMap"]["fps"]=receipt["fullMap"]["frames"]/receipt["fullMap"]["seconds"]
        return receipt,patterns


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--data",type=Path,default=Path("/Users/clemens/Programming/Dioptrin/test_data"))
    p.add_argument("--baseline",type=Path)
    p.add_argument("--processor",type=Path,default=client.ROOT/"desktop/backend/target/release/dioptas-processor")
    p.add_argument("--frames",type=int,default=64)
    p.add_argument("--skip-mask",action="store_true")
    p.add_argument("--tune-threads",action="store_true")
    args=p.parse_args()
    client.EXECUTABLE=args.processor
    fingerprints={str(f):dict(size=f.stat().st_size,mtimeNs=f.stat().st_mtime_ns) for f in
                  [args.data/name for name in ["eiger_0000.h5","eiger_0000.tiff","eiger_0000.mask","eiger_0000.poni"]]}
    result=dict(frames=args.frames,bins=2000,cakeBins=90,cache="warm OS file cache; no frontend rendering; includes command, series construction and checkpoint restore",inputs=fingerprints)
    if not args.skip_mask:
        result["mask"]=mask_check(args.data)
        print("Mask",json.dumps(result["mask"]),flush=True)
    reference=None
    if args.baseline:
        result["before"],reference=benchmark(args.baseline,args.data,args.frames)
        print("Before",json.dumps(result["before"]),flush=True)
    result["after"],patterns=benchmark(args.processor,args.data,args.frames,full_map=True)
    print("After",json.dumps(result["after"]),flush=True)
    if reference is not None:
        np.testing.assert_allclose(patterns,reference,rtol=2e-12,atol=1e-9)
        result["science"]=dict(allFloat64PatternsMatch=True,exact=bool(np.array_equal(patterns,reference)),maxAbsDifference=float(np.max(np.abs(patterns-reference))))
    if args.tune_threads:
        result["threadSweep"]={}
        for threads in [4,12,16]:
            receipt,other=benchmark(args.processor,args.data,args.frames,threads)
            np.testing.assert_allclose(patterns,other,rtol=2e-12,atol=1e-9)
            result["threadSweep"][str(threads)]=receipt
            print("Threads",threads,json.dumps(receipt),flush=True)
    for name,stat in fingerprints.items():
        path=Path(name)
        assert path.stat().st_size==stat["size"] and path.stat().st_mtime_ns==stat["mtimeNs"]
    output=client.ROOT/"desktop/artifacts/standalone/eiger-regression.json"
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(result,indent=2)+"\n")
    print(output)

if __name__=="__main__": main()
