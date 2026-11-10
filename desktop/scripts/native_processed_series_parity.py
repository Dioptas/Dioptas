"""Compare threaded corrected/plugin series with the existing native path."""
import argparse
import json
import os
import struct
import tempfile
from pathlib import Path

os.environ["HDF5_PLUGIN_PRELOAD"] = "::"
import bitshuffle
import h5py
import numpy as np
import native_reference_client as client
from native_series_pipeline_benchmark import stored


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--before", type=Path, required=True)
    p.add_argument("--after", type=Path, required=True)
    args = p.parse_args()
    receipts = []
    with tempfile.TemporaryDirectory(prefix="dioptas-processed-parity-") as directory:
        directory = Path(directory)
        shape = 48, 64
        y, x = np.indices(shape)
        paths = []
        for part in range(2):
            path = directory / f"source_{part}.h5"
            with h5py.File(path, "w") as f:
                d = f.create_dataset("frames", shape=(16, *shape), dtype="uint32", chunks=(1, *shape),
                    compression=32008, compression_opts=(0,4,4,2048,2), allow_unknown_filter=True)
                for i in range(16):
                    frame = part * 16 + i
                    counts = (100 + x*3 + y*2 + frame*7).astype("uint32")
                    counts[(frame*7) % shape[0], (frame*13) % shape[1]] = 10000 + frame
                    encoded = struct.pack(">QI", counts.nbytes, 8192) + bitshuffle.compress_lz4(counts, block_size=2048).tobytes()
                    d.id.write_direct_chunk((i,0,0), encoded)
            paths.append(str(path))
        for name, values in dict(background=180.+x*0.2, flat=0.8+x/160., original=1.+y/100., response=1.+x/120., mask=((x+y)%17==0)).items():
            np.save(directory / (name + ".npy"), values)
        geometry = dict(dist=0.13, poni1=0.0024, poni2=0.0032, rot1=0.008, rot2=-0.013,
                        rot3=0.02, pixel1=0.0001, pixel2=0.0001, wavelength=0.5e-10, polarization_factor=0.965)
        cases = [
            ("corrected", [], True, "polygon", True),
            ("corrected-no-errors", [], True, "polygon", False),
            ("threshold", ["Threshold Mask"], False, "polygon", True),
            ("cosmic", ["Cosmic Ray Mask"], False, "polygon", True),
            ("spot", ["Spot Mask"], False, "polygon", True),
            ("combined", ["Threshold Mask", "Cosmic Ray Mask", "Spot Mask"], True, "polygon", True),
            ("pyfai", ["Threshold Mask"], True, "pyfai_full", True),
            ("pyfai-fixed", [], False, "pyfai_full", True),
            ("pyfai-fixed-no-errors", [], False, "pyfai_full", False),
            ("pyfai-fixed-sector", [], False, "pyfai_full", True),
            ("pyfai-fixed-spread", [], False, "pyfai_full", True),
            ("pyfai-fixed-no-solid-angle", [], False, "pyfai_full", True),
            ("pyfai-fixed-q", [], False, "pyfai_full", True),
            ("pyfai-fixed-d", [], False, "pyfai_full", True),
            ("pyfai-fixed-mask-disabled", [], False, "pyfai_full", True),
            ("subpixel", ["Spot Mask"], True, "subpixel", True),
            ("sector-spread", ["Threshold Mask"], True, "polygon", True),
            ("mask-disabled", ["Threshold Mask"], True, "polygon", True),
        ]
        for name, plugins, corrected, method, errors in cases:
            reference = {}
            for label, executable in [("before",args.before),("after",args.after)]:
                client.EXECUTABLE = executable
                with client.Native({"DIOPTAS_INTEGRATION_THREADS":"4"}) as native:
                    native.call("manual_geometry", convention="pyfai", values=geometry)
                    settings = dict(bins=64, cake_bins=16, trim_zeros=False, poisson_errors=errors, method=method, sparse_layout="csc")
                    if method == "subpixel": settings["supersampling"] = 2
                    if name == "sector-spread": settings.update(azimuth_range=[-130.,70.], azimuthal_std=True)
                    if name == "pyfai-fixed-sector": settings["azimuth_range"] = [-130.,70.]
                    if name == "pyfai-fixed-spread": settings["azimuthal_std"] = True
                    if name == "pyfai-fixed-no-solid-angle": settings["solid_angle"] = False
                    native.call("integration_settings", **settings)
                    if name in ("pyfai-fixed-q", "pyfai-fixed-d"):
                        native.call("integration_settings", unit="q_A^-1" if name.endswith("-q") else "d_A")
                    native.call("open_image", path=paths[0])
                    native.call("mask_file", path=str(directory / "mask.npy"))
                    if corrected:
                        native.call("integration_image_background", path=str(directory / "background.npy"), scale=0.7, offset=1.2, poisson=True)
                        native.call("integration_flat_field", path=str(directory / "flat.npy"))
                        for source in ["original", "response"]:
                            native.call("integration_transfer", source=source, path=str(directory / (source+".npy")))
                        native.call("integration_transfer", enabled=True)
                        native.call("integration_correction", kind="plate", enabled=True, parameters=dict(absorption_coefficient=0.5, thickness=0.1, plate_tilt=3., plate_rotation=16.))
                    for plugin in plugins:
                        settings = {"above_enabled":True,"above_value":900.} if plugin=="Threshold Mask" else ({"iterations":2,"window_size":3} if plugin=="Cosmic Ray Mask" else {"num_bins":64,"smooth_sigma":0.3,"method":"median"})
                        native.call("mask_plugin", name=plugin, enabled=True, settings=settings)
                    if name in ("mask-disabled", "pyfai-fixed-mask-disabled"): native.call("integration_settings", use_mask=False)
                    for view in ["batch", "map"]:
                        before = native.call("integration_diagnostics")["integrationDiagnostics"]
                        payload = dict(paths=paths)
                        if view == "batch": payload.update(start=2, stop=32, step=3)
                        result = native.call(view+"_load", **payload)
                        after = native.call("integration_diagnostics")["integrationDiagnostics"]
                        count = 11 if view == "batch" else 32
                        if label == "after":
                            assert after["processedFrameIntegrations"] - before["processedFrameIntegrations"] == count, (name,view,after,before)
                            assert after["seriesPipelineRuns"] - before["seriesPipelineRuns"] == 2
                        if view == "batch":
                            entries = result["batch"]["entries"]
                            assert [(Path(e["path"]).resolve(),e["frame"]-1) for e in entries] == [(Path(paths[i//16]).resolve(),i%16) for i in range(1,32,3)]
                        arrays = stored(native, view, directory)
                        if view == "map": arrays["map_values"] = np.asarray(result["map"]["values"],dtype=float)
                        if label == "before": reference[view] = arrays
                        else:
                            for key, values in arrays.items():
                                np.testing.assert_allclose(values, reference[view][key], rtol=3e-12, atol=1e-8, equal_nan=True, err_msg=f"{name}/{view}/{key}")
                        native.buffers.clear()
            receipts.append(name)
            print("PASS",name,flush=True)
    print(json.dumps(dict(cases=receipts, views=["batch","map"], multiSource=True, stride=True)))


if __name__ == "__main__":
    main()
