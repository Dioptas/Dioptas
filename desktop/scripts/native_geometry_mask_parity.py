"""Test-only Qt/NumPy/skimage comparisons for native transforms and geometric masks."""

import json
import os
import tempfile
from pathlib import Path

os.environ["HDF5_PLUGIN_PRELOAD"] = "::"
import h5py
import numpy as np
from dioptas.desktop.session import DesktopSession
from native_reference_client import Native, ROOT

GEOMETRY = dict(
    dist=0.13,
    poni1=0.0031,
    poni2=0.004,
    pixel1=0.0001,
    pixel2=0.00016,
    rot1=0.008,
    rot2=-0.013,
    rot3=0.02,
    wavelength=0.5e-10,
    polarization_factor=0.965,
)


def main():
    receipts = []
    with tempfile.TemporaryDirectory() as directory, Native() as n:
        d = Path(directory)
        rows, cols = np.indices((64, 83))
        data = (100 + rows * 2 + cols * 3).astype(np.uint32)
        source = d / "source.npy"
        np.save(source, data)
        ref = DesktopSession()

        def both(command, **payload):
            actual = n.call(command, **payload)
            expected = ref.invoke(command, payload)
            assert expected["ok"], expected
            return actual, expected

        both("open_image", path=str(source))
        both("manual_geometry", convention="pyfai", values=GEOMETRY)
        both("integration_settings", bins=80, cake_bins=36, trim_zeros=False)

        def masks():
            r = n.call("state")
            np.testing.assert_array_equal(
                n.raster(r, "mask"), ref.configuration.mask_model.get_display_mask()
            )
            assert (
                r["state"]["maskDetails"]["mode"] == ref.configuration.mask_model.mode
            )

        selections = [
            dict(operation="rectangle", points=[[4.5, 8.5], [23.5, 30.5]]),
            dict(operation="rectangle", points=[[29.2, 31.9], [1.5, 2.5]], erase=True),
            dict(operation="circle", points=[[35.8, 28.9], [48.4, 33.1]]),
            dict(operation="circle", points=[[1.3, 1.7], [22.2, 10.8]]),
            dict(operation="circle", points=[[25, 30], [25.2, 30.3]]),
            dict(operation="polygon", points=[[4, 8], [40, 8], [25, 34], [8, 31]]),
            dict(
                operation="polygon",
                points=[[7.2, 8.3], [60.7, 45.1], [8.9, 45.1], [60.7, 8.3]],
            ),
            dict(operation="polygon", points=[[4, 8], [10, 8], [20, 8]]),
            dict(operation="arc", points=[[40, 10], [55, 25], [40, 40], [58, 25]]),
            dict(
                operation="arc",
                points=[[25, 40], [10, 25], [25, 10], [5, 25]],
                erase=True,
            ),
            dict(operation="above", threshold=350),
            dict(operation="below", threshold=150, erase=True),
            *[dict(operation=op) for op in ["grow", "shrink", "invert", "clear"]],
        ]
        rng = np.random.default_rng(731)
        selections += [
            dict(
                operation="polygon",
                points=rng.uniform([0, 0], [82, 63], size=(8, 2)).tolist(),
                erase=bool(i % 2),
            )
            for i in range(20)
        ]
        for selection in selections:
            both("mask_edit", **selection)
            try:
                masks()
            except AssertionError as error:
                raise AssertionError(selection) from error
        for unit, lower, upper in [
            ("2th_deg", 0.4, 1.3),
            ("q_A^-1", 0.1, 0.3),
            ("d_A", 15.0, 30.0),
            ("2th_deg", None, 1.7),
            ("d_A", 25.0, None),
        ]:
            for outside in (False, True):
                both(
                    "mask_edit",
                    operation="range",
                    unit=unit,
                    lower=lower,
                    upper=upper,
                    outside=outside,
                    erase=outside,
                )
                masks()
        receipts.append(
            dict(
                geometricMasks=len(selections) + 10,
                reference="existing MaskWorkflow/MaskModel, NumPy and skimage; exact full-resolution masks",
            )
        )
        before = n.call("state")
        for bad in [
            dict(operation="arc", points=[[1, 1], [2, 2], [3, 3], [4, 4]]),
            dict(operation="range", lower=3, upper=2),
            dict(operation="rectangle", points=[[1, 1], [83, 10]]),
            dict(operation="polygon", points=[[1, 1], [2, 2]]),
        ]:
            assert not n.invoke("mask_edit", **bad)["ok"]
            assert n.call("state") == before
        # Corrections and user masks must follow the same source pixels.
        background = d / "background.npy"
        flat = d / "flat.npy"
        np.save(background, 2.0 + cols * 0.01)
        np.save(flat, 2.0 + rows * 0.01 + cols * 0.02)
        both(
            "integration_image_background", path=str(background), scale=0.7, offset=1.2
        )
        both("integration_flat_field", path=str(flat))
        processed = (
            data[::-1].astype(float) - 0.7 * (2.0 + cols * 0.01)[::-1] - 1.2
        ) / (
            (2.0 + rows * 0.01 + cols * 0.02)[::-1]
            / (2.0 + rows * 0.01 + cols * 0.02).mean()
        )
        expected_processed = processed.copy()
        transform_functions = {
            "rotate_right": lambda a: np.rot90(a),
            "rotate_left": lambda a: np.rot90(a, -1),
            "flip_horizontal": np.fliplr,
            "flip_vertical": np.flipud,
        }
        transforms = [
            "rotate_right",
            "flip_horizontal",
            "rotate_left",
            "flip_vertical",
            "rotate_left",
            "reset",
        ]
        for operation in transforms:
            actual, expected = both("image_transform", operation=operation)
            np.testing.assert_array_equal(
                n.raster(actual, "rawImage"),
                ref.configuration.img_model.raw_img_data.astype(np.float32),
            )
            expected_processed = (
                processed.copy()
                if operation == "reset"
                else transform_functions[operation](expected_processed)
            )
            np.testing.assert_array_equal(
                n.raster(actual, "image"), expected_processed.astype(np.float32)
            )
            masks()
            g = ref.configuration.calibration_model.pattern_geometry
            np.testing.assert_allclose(
                [
                    actual["state"]["calibration"]["pixelY"],
                    actual["state"]["calibration"]["pixelX"],
                ],
                [g.pixel1 * 1e6, g.pixel2 * 1e6],
            )
            assert actual["state"]["calibration"]["picks"] == []
        receipts.append(
            dict(
                transforms=transforms,
                counts="exact source/display orientation",
                corrections="background/flat response follow source; unequal pixel pitches swap",
            )
        )
        # Transform history is chronological with calibration; mask history stays
        # attached to source pixels across a transform and its Undo/Redo.
        n.call("mask_stroke", points=[[8, 9]], radius=2)
        original = n.call("state")
        original_mask = n.raster(original, "mask").copy()
        n.call("image_transform", operation="rotate_right")
        rotated = n.call("state")
        rotated_mask = n.raster(rotated, "mask").copy()
        undone = n.call("undo_calibration")
        np.testing.assert_array_equal(
            n.raster(undone, "rawImage"), n.raster(original, "rawImage")
        )
        np.testing.assert_array_equal(n.raster(undone, "mask"), original_mask)
        redone = n.call("redo_calibration")
        np.testing.assert_array_equal(n.raster(redone, "mask"), rotated_mask)
        n.call("undo_mask")
        n.call("redo_mask")
        np.testing.assert_array_equal(n.raster(n.call("state"), "mask"), rotated_mask)
        # Save source caches once and the transform log separately, then load
        # offline and reset. Current Python readers consume the native file too.
        project = d / "transformed.dio"
        n.call("save_project", path=str(project))
        reference = DesktopSession()
        loaded = reference.invoke("open_project", dict(path=str(project)))
        assert loaded["ok"], loaded
        np.testing.assert_array_equal(
            reference.configuration.img_model.raw_img_data, n.raster(redone, "rawImage")
        )
        with h5py.File(project) as f:
            doc = json.loads(f["state"][()])
            config = doc["configurations"][0]
            np.testing.assert_array_equal(
                f["cache"][config["image_data"]][:], data[::-1]
            )
        python_project = d / "python-transformed.dio"
        saved = reference.invoke("save_project", dict(path=str(python_project)))
        assert saved["ok"], saved
        imported = n.call("open_project", path=str(python_project))
        np.testing.assert_array_equal(
            n.raster(imported, "rawImage"),
            reference.configuration.img_model.raw_img_data.astype(np.float32),
        )
        external_reset = n.call("image_transform", operation="reset")
        expected_pixels = reference.configuration.calibration_model.pattern_geometry
        np.testing.assert_allclose(
            [
                external_reset["state"]["calibration"]["pixelY"],
                external_reset["state"]["calibration"]["pixelX"],
            ],
            [expected_pixels.pixel1 * 1e6, expected_pixels.pixel2 * 1e6],
        )
        source.unlink()
        background.unlink()
        flat.unlink()
        loaded = n.call("open_project", path=str(project))
        np.testing.assert_array_equal(
            n.raster(loaded, "image"), n.raster(redone, "image")
        )
        loaded = n.call("image_transform", operation="reset")
        np.testing.assert_array_equal(
            n.raster(loaded, "rawImage"), data[::-1].astype(np.float32)
        )
        # An invalid transformation in a project cannot partially replace state.
        with h5py.File(project, "r+") as f:
            doc = json.loads(f["state"][()])
            doc["configurations"][0]["img"]["transformations"] = ["unknown"]
            del f["state"]
            f["state"] = json.dumps(doc)
        baseline = n.call("state")
        assert not n.invoke("open_project", path=str(project))["ok"]
        assert n.call("state") == baseline
        stack = d / "transformed-stack.h5"
        stack_data = np.stack([data, data + 50, data + 100])
        with h5py.File(stack, "w") as f:
            f["frames"] = stack_data
        n.call("open_image", path=str(stack), dataset="frames")
        n.call("image_transform", operation="rotate_right")
        n.call("mask_edit", operation="clear")
        single = n.call("state")
        series = n.call("batch_load", paths=[str(stack)])
        matrix = n.raster({"data": series["batch"]["raster"]}, "data")
        np.testing.assert_array_equal(
            matrix[0], np.asarray(single["pattern"]["y"], dtype=np.float32)
        )
        advanced = n.call("next_image", direction=1)
        np.testing.assert_array_equal(
            n.raster(advanced, "rawImage"),
            np.rot90(stack_data[1, ::-1]).astype(np.float32),
        )
        batch = d / "transformed-batch.h5"
        n.call("integration_save_batch", path=str(batch))
        n.call("map_batch", path=str(batch))
        n.call("map_grid", rows=1, columns=3)
        selected = n.call("map_select", index=2, reintegrate=True)
        np.testing.assert_array_equal(
            n.raster(selected, "rawImage"),
            np.rot90(stack_data[2, ::-1]).astype(np.float32),
        )
        # Image-tab combine/save uses the same source orientation exactly once.
        a, b = d / "a.npy", d / "b.npy"
        np.save(a, data)
        np.save(b, data + 100)
        n.call("open_image", path=str(a))
        averaged = n.call("open_image", paths=[str(a), str(b)], batch_mode="average")
        np.testing.assert_array_equal(
            n.raster(averaged, "rawImage"),
            np.rot90((data[::-1].astype(float) + 50)).astype(np.float32),
        )
        output = d / "image-output"
        output.mkdir()
        saved = n.call(
            "open_image",
            paths=[str(a), str(b)],
            batch_mode="save",
            output_directory=str(output),
        )
        from PIL import Image

        np.testing.assert_array_equal(
            np.asarray(Image.open(saved["savedPaths"][0]))[::-1],
            np.rot90(processed).astype(np.int32),
        )
        receipts.append(
            dict(
                history="calibration transform Undo/Redo and mask Undo/Redo",
                bulk="navigation, Batch/Map reintegration, image average and staged export",
                projects="untransformed owned caches, transform log, offline reset and Python-reader compatibility",
            )
        )
    out = ROOT / "desktop/artifacts/native-geometry-mask/parity.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(receipts, indent=2) + "\n")
    print(json.dumps(receipts, indent=2))


if __name__ == "__main__":
    main()
