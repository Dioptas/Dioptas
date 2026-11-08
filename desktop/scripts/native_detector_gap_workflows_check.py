"""Real Eiger integration routes versus Custom geometry + an explicit dummy mask.

The reference has no detector-generated mask. Only the test driver uses Python;
both scientific workers are Rust processes with Python disabled.
"""
import argparse
import hashlib
import json
import shutil
import tempfile
from pathlib import Path

import h5py
import numpy as np
from native_reference_client import Native, ROOT, EXECUTABLE


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, required=True)
    folder = parser.parse_args().data.resolve()
    checks = []
    with tempfile.TemporaryDirectory() as directory, Native() as auto, Native() as explicit:
        directory = Path(directory)
        hdf = str(folder / "eiger_0000.h5")
        tiff = str(folder / "eiger_0000.tiff")
        named_poni = folder / "eiger_0000.poni"
        custom_poni = directory / "custom.poni"
        custom_poni.write_text(named_poni.read_text().replace(
            "Detector: Eiger2CdTe_9M", "Detector: Detector"
        ).replace('Detector_config: {"orientation": 2}',
                  'Detector_config: {"orientation":2,"pixel1":0.000075,"pixel2":0.000075}'))
        for worker, calibration in [(auto, named_poni), (explicit, custom_poni)]:
            worker.call("integration_settings", bins=2000, cake_bins=90,
                        trim_zeros=False, poisson_errors=True)
            worker.call("open_calibration", path=str(calibration))
        first = auto.call("open_image", path=hdf)
        raw = auto.raster(first, "rawImage")
        invalid = raw == np.float32(np.iinfo(np.uint32).max)
        assert int(invalid.sum()) == 887556
        np.testing.assert_array_equal(auto.raster(first, "mask"), invalid)
        mask_path = directory / "explicit.npy"
        np.save(mask_path, invalid)
        unmasked = explicit.call("open_image", path=hdf)
        assert not explicit.raster(unmasked, "mask").any()
        assert np.median(unmasked["pattern"]["y"]) > 1000 * np.median(first["pattern"]["y"])
        masked = explicit.call("mask_file", path=str(mask_path))

        def compare(label, a, b):
            for axis in ["x", "y"]:
                np.testing.assert_allclose(a["pattern"][axis], b["pattern"][axis],
                                           rtol=2e-12, atol=1e-8, err_msg=label)
            for key in ["sigma", "azimuthalStd"]:
                if a["pattern"].get(key) is not None:
                    np.testing.assert_allclose(a["pattern"][key], b["pattern"][key],
                                               rtol=2e-12, atol=1e-8, err_msg=label)
            if a.get("cake") and b.get("cake"):
                np.testing.assert_array_equal(auto.raster(a, "cake"), explicit.raster(b, "cake"), err_msg=label)
            checks.append(label)
            print("PASS", label, flush=True)
            auto.buffers.clear()
            explicit.buffers.clear()

        def both(label, command, **payload):
            a, b = [w.call(command, **payload) for w in [auto, explicit]]
            compare(label, a, b)
            return a, b

        def batch(label, command="batch_load", **payload):
            a, b = [w.call(command, **payload) for w in [auto, explicit]]
            for w, reply, name in [(auto, a, "auto"), (explicit, b, "explicit")]:
                output = directory / f"{name}.h5"
                w.call("integration_save_batch", path=str(output))
            with h5py.File(directory / "auto.h5") as fa, h5py.File(directory / "explicit.h5") as fb:
                np.testing.assert_allclose(fa["processed/result/data"][:], fb["processed/result/data"][:],
                                           rtol=2e-12, atol=1e-8, err_msg=label)
            compare(label, a, b)

        compare("single image, cake and explicit-only reference", first, masked)
        both("explicit reintegration", "integrate")
        both("pattern-only HDF5 decode", "open_image", path=hdf, frame=1, pattern_only=True)
        both("next HDF5 frame", "next_image", direction=1)
        batch("warm bulk Batch, all 625 profiles", paths=[hdf])
        both("Batch selected profile and recalculated cake", "batch_select", index=624)
        batch("Batch reintegration", reintegrate=True, start=1, stop=8, step=3)
        for layout in ["csr", "csc"]:
            both(f"{layout} pattern and cake", "integration_settings", sparse_layout=layout)
        both("azimuth-limited pattern and cake", "integration_settings",
             azimuth_range=[-130, 70], cake_azimuth_range=[-150, 100])
        both("detector ROI", "integration_roi", limits=[500, 2500, 400, 2400])
        batch("ROI/azimuth Batch fallback", paths=[hdf], start=1, stop=4)
        both("reset ROI", "integration_roi", limits=None)
        both("reset azimuth", "integration_settings", azimuth_range=None, cake_azimuth_range=None)
        background = directory / "background.npy"
        flat = directory / "flat.npy"
        np.save(background, np.full(invalid.shape, 7.0))
        np.save(flat, np.broadcast_to(np.linspace(0.8, 1.2, invalid.shape[1]), invalid.shape))
        both("image background subtraction", "integration_image_background", path=str(background), scale=0.7)
        both("flat-field correction", "integration_flat_field", path=str(flat))
        both("absorption correction", "integration_correction", kind="oiadac", enabled=True,
             parameters=dict(tilt=3, rotation=16, detector_thickness=44, absorption_length=120))
        batch("corrected Batch resident fallback", paths=[hdf], start=1, stop=4)
        both("reset absorption", "integration_correction", kind="oiadac", enabled=False)
        both("reset flat field", "integration_flat_field", reset=True)
        both("reset image background", "integration_image_background", reset=True)
        both("dynamic mask", "mask_plugin", name="Threshold Mask", enabled=True,
             settings=dict(above_enabled=True, above_value=1000))
        batch("dynamic-mask Batch fallback", paths=[hdf], start=1, stop=4)
        both("disable dynamic mask", "mask_plugin", name="Threshold Mask", enabled=False)
        auto.call("integration_settings", use_mask=False)
        batch("Batch with user mask disabled", paths=[hdf], start=1, stop=4)
        auto.call("integration_settings", use_mask=True)
        both("ordinary TIFF reader", "open_image", path=tiff)
        for worker, name in [(auto, "auto"), (explicit, "explicit")]:
            worker.call("integration_save_pattern", path=str(directory / f"{name}.xye"))
        np.testing.assert_allclose(np.loadtxt(directory / "auto.xye"), np.loadtxt(directory / "explicit.xye"),
                                   rtol=2e-12, atol=1e-8)
        checks.append("exported intensities and Poisson uncertainties")
        inputs = directory / "input"
        inputs.mkdir()
        for i in [1, 2]:
            shutil.copyfile(tiff, inputs / f"scan_{i:04}.tiff")
        batch("folder Batch", command="batch_folder", path=str(inputs))
        for worker in [auto, explicit]:
            worker.call("integration_autoprocess", enabled=True, directory=str(inputs))
        shutil.copyfile(tiff, inputs / "scan_0003.tiff")
        for worker in [auto, explicit]:
            worker.call("integration_autoprocess_poll")
        both("automatic processing of incoming image", "integration_autoprocess_poll")
        for worker in [auto, explicit]:
            worker.call("integration_autoprocess", enabled=False)
            worker.call("map_load", paths=[str(inputs / f"scan_{i:04}.tiff") for i in [1, 2, 3]])
            worker.call("map_poll", check_only=True)
        shutil.copyfile(tiff, inputs / "scan_0004.tiff")
        for worker in [auto, explicit]:
            worker.call("map_poll", check_only=True)
            reply = worker.call("map_poll")
            assert reply["map"]["points"] == 4
        both("live Map appended profile", "map_select", index=3, reintegrate=True)
        both("background before image export", "integration_image_background", path=str(background), scale=0.7)
        for worker, name in [(auto, "auto"), (explicit, "explicit")]:
            output = directory / f"saved-{name}"
            output.mkdir()
            reply = worker.call("open_image", paths=[str(inputs / f"scan_{i:04}.tiff") for i in [1, 2]],
                                batch_mode="save", output_directory=str(output))
            assert len(reply["savedPaths"]) == 2
        both("reset background after image export", "integration_image_background", reset=True)
        a, b = [worker.call("open_image", path=str(directory / f"saved-{name}" / "batch_scan_0001.tiff"))
                for worker, name in [(auto, "auto"), (explicit, "explicit")]]
        compare("reintegrate corrected batch image export", a, b)
        both("image multi-selection integration", "open_image", paths=[tiff, tiff], batch_mode="integrate")
        for operation in ["add", "average"]:
            both(f"image {operation}", "open_image", paths=[tiff, tiff], batch_mode=operation)
            both(f"reintegrate derived {operation}", "integrate")
        both("rotate detector", "image_transform", operation="rotate_right")
        both("add after detector rotation", "open_image", paths=[tiff, tiff], batch_mode="add")
        both("reset detector rotation", "image_transform", operation="reset")
        for worker, name in [(auto, "auto"), (explicit, "explicit")]:
            project = directory / f"{name}.dio"
            worker.call("save_project", path=str(project))
            worker.call("open_project", path=str(project))
        both("derived project cache reintegration", "integrate")
        both("restore original after derived project", "open_image", path=tiff)
        for worker in [auto, explicit]:
            worker.call("configuration", operation="duplicate")
        both("duplicated configuration", "integrate")
        # Cold bulk path starts with calibration alone, without any user mask
        # or previously opened pixels that could accidentally supply exclusions.
        with Native() as cold:
            cold.call("integration_settings", bins=2000, cake_bins=90, trim_zeros=False, poisson_errors=True)
            cold.call("open_calibration", path=str(named_poni))
            cold.call("batch_load", paths=[hdf])
            cold.call("integration_save_batch", path=str(directory / "cold.h5"))
        explicit.call("batch_load", paths=[hdf])
        explicit.call("integration_save_batch", path=str(directory / "explicit.h5"))
        with h5py.File(directory / "cold.h5") as fa, h5py.File(directory / "explicit.h5") as fb:
            np.testing.assert_allclose(fa["processed/result/data"][:], fb["processed/result/data"][:], rtol=2e-12, atol=1e-8)
        checks.append("cold bulk Batch, all 625 profiles")
    receipt = dict(processor=str(EXECUTABLE), processorSha256=hashlib.sha256(EXECUTABLE.read_bytes()).hexdigest(),
                   reference="Custom uniform detector without automatic mask + explicit 887556 dummy pixels",
                   checks=checks)
    output = ROOT / "desktop/artifacts/native-mask/real-eiger-workflows.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
