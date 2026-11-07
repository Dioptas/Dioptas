"""Independent bundled cosmics.py/SciPy comparison; no Python in the Rust child."""

import contextlib
import io
import json
import os
import tempfile
import time
from pathlib import Path

os.environ["HDF5_PLUGIN_PRELOAD"] = "::"
import h5py
import numpy as np
from dioptas.model.util.cosmics import cosmicsimage
from dioptas.desktop.session import DesktopSession
from native_reference_client import Native, ROOT


def reference(data):
    with contextlib.redirect_stdout(io.StringIO()):
        model = cosmicsimage(data, sigclip=3.0, objlim=3.0, verbose=False)
        model.lacosmiciteration(False)
        model.clean(verbose=False)
        first = model.mask.copy()
        model.lacosmiciteration(False)
        model.clean(verbose=False)
    return model.mask, first


def main():
    rng = np.random.default_rng(731)
    fixtures = []
    for shape in [(1, 1), (1, 17), (19, 1), (2, 3), (7, 9), (43, 59)]:
        data = rng.poisson(100, size=shape).astype(float)
        data[shape[0] // 2, shape[1] // 2] += 8000
        data[0, 0] += 5000
        data[-1, -1] += 6000
        fixtures.append((f"edge-and-center-{shape[0]}x{shape[1]}", data))
    y, x = np.indices((65, 87))
    base = 80.0 + 0.08 * x + 0.2 * y
    data = base + rng.normal(0, 1, size=base.shape)
    data[17:24, 31:38] += 10000
    data[24, 34] += 400
    data[45, 11] += 1000
    data[45, 12] += 150
    data[46, 12] += 80
    fixtures.append(("cluster-with-weaker-neighbors", data))
    for seed in range(5):
        random = np.random.default_rng(seed)
        data = random.poisson(50 + seed * 100, size=(39, 53)).astype(float)
        locations = random.choice(data.size, size=45, replace=False)
        data.flat[locations] += random.uniform(100, 50000, len(locations))
        fixtures.append((f"random-hits-{seed}", data))
    fixtures += [
        ("negative-background", fixtures[-1][1] - 500.0),
        ("fractional-counts", fixtures[-1][1] * 0.123456789),
    ]
    data = np.full((25, 29), 100.0)
    data[8:17, 8:21] = 100000.0
    fixtures.append(("bright-extended-structure", data))
    fixtures.append(("measured-CeO2", None))
    receipts = []
    with tempfile.TemporaryDirectory() as tmp, Native(require_engine=False) as native:
        tmp = Path(tmp)
        for name, data in fixtures:
            if data is None:
                image = ROOT / "dioptas/tests/data/CeO2_Pilatus1M.tif"
                from PIL import Image

                data = np.asarray(Image.open(image))[::-1].astype(float)
            else:
                image = tmp / "input.npy"
                np.save(image, data[::-1])
            native.call("open_image", path=str(image))
            native.call("mask_edit", operation="clear")
            before = native.call("state")
            expected, first = reference(data)
            started = time.perf_counter()
            result = native.call("mask_edit", operation="cosmic")
            elapsed = time.perf_counter() - started
            np.testing.assert_array_equal(
                native.raster(result, "mask"), expected, err_msg=name
            )
            after = native.call("state")
            for field in ["rawImage", "image"]:
                assert after[field] == before[field], (name, field)
            if expected.any():
                native.call("undo_mask")
                np.testing.assert_array_equal(
                    native.raster(native.call("state"), "mask"),
                    np.zeros(data.shape, dtype=np.uint8),
                )
                native.call("redo_mask")
                np.testing.assert_array_equal(
                    native.raster(native.call("state"), "mask"), expected
                )
            else:
                assert after["state"]["canUndoMask"] == before["state"]["canUndoMask"]
            receipts.append(
                dict(
                    case=name,
                    shape=data.shape,
                    firstPass=int(first.sum()),
                    secondPassNew=int((expected & ~first).sum()),
                    masked=int(expected.sum()),
                    nativeSeconds=elapsed,
                )
            )
        # Preserve the existing command's additive behavior even in Unmask mode;
        # previous user pixels do not exclude hits or affect the detector itself.
        data = fixtures[7][1]
        image = tmp / "session.npy"
        np.save(image, data[::-1])
        native.call("open_image", path=str(image))
        native.call("mask_edit", operation="clear")
        painted = native.call(
            "mask_edit", operation="rectangle", points=[[1, 1], [5, 4]]
        )
        user = native.raster(painted, "mask").copy()
        expected, _ = reference(data)
        result = native.call("mask_edit", operation="cosmic", erase=True)
        np.testing.assert_array_equal(native.raster(result, "mask"), user | expected)
        assert result["state"]["maskDetails"]["mode"] is False
        # The public Python desktop command reads the same source and settings.
        ref = DesktopSession()
        assert ref.invoke("open_image", dict(path=str(image)))["ok"]
        assert ref.invoke(
            "mask_edit", dict(operation="rectangle", points=[[1, 1], [5, 4]])
        )["ok"]
        with contextlib.redirect_stdout(io.StringIO()):
            assert ref.invoke("mask_edit", dict(operation="cosmic", erase=True))["ok"]
        np.testing.assert_array_equal(
            native.raster(result, "mask"), ref.configuration.mask_model.get_img()
        )
        # The resulting owned user mask persists per configuration and offline.
        native.call("configuration", operation="duplicate")
        project = tmp / "cosmic.dio"
        native.call("save_project", path=str(project))
        image.unlink()
        loaded = native.call("open_project", path=str(project))
        np.testing.assert_array_equal(native.raster(loaded, "mask"), user | expected)
        selected = native.call("configuration", operation="select", index=0)
        np.testing.assert_array_equal(native.raster(selected, "mask"), user | expected)
        # LA Cosmic sees the processed scientific plane after orientation and
        # corrections. Dynamic plugin/user masks remain separate inputs/owners.
        data = fixtures[7][1]
        y, x = np.indices(data.shape)
        corrected = tmp / "corrected.npy"
        bg = tmp / "background.npy"
        flat = tmp / "flat.npy"
        np.save(corrected, data[::-1])
        np.save(bg, (2.0 + x * 0.01)[::-1])
        np.save(flat, (2.0 + y * 0.01 + x * 0.02)[::-1])
        native.call("open_image", path=str(corrected))
        native.call("integration_image_background", path=str(bg), scale=0.7, offset=1.2)
        native.call("integration_flat_field", path=str(flat))
        native.call("image_transform", operation="rotate_right")
        native.call("mask_edit", operation="clear")
        processed = np.rot90(
            (data - 0.7 * (2.0 + x * 0.01) - 1.2)
            / ((2.0 + y * 0.01 + x * 0.02) / (2.0 + y * 0.01 + x * 0.02).mean())
        )
        native.call(
            "mask_plugin",
            name="Threshold Mask",
            enabled=True,
            settings=dict(above_value=10000),
        )
        baseline = native.call("state")
        expected, _ = reference(processed)
        result = native.call("mask_edit", operation="cosmic")
        np.testing.assert_array_equal(
            native.raster(result, "mask"), expected | (processed > 10000)
        )
        after = native.call("state")
        assert after["image"] == baseline["image"]
        assert after["rawImage"] == baseline["rawImage"]
        native.call("mask_plugin", name="Threshold Mask", enabled=False)
        np.testing.assert_array_equal(
            native.raster(native.call("state"), "mask"), expected
        )
        receipts.append(
            dict(
                case="processed-oriented-plane-with-dynamic-plugin",
                shape=processed.shape,
                masked=int(expected.sum()),
            )
        )
        native.call("integration_image_background", reset=True)
        native.call("integration_flat_field", reset=True)
        native.call("image_transform", operation="reset")
        # Invalid inputs are deliberately atomic: SciPy's rank-filter treatment
        # of NaN is undefined, so the native operation requires finite science.
        for index, value in enumerate(
            [float("nan"), float("inf"), float("-inf"), 1e308]
        ):
            invalid = tmp / f"invalid-{index}.h5"
            with h5py.File(invalid, "w") as f:
                a = np.full((9, 11), 100.0)
                a[4, 5] = value
                f["frames"] = a
            native.call("open_image", path=str(invalid), dataset="frames")
            baseline = native.call("state")
            result = native.invoke("mask_edit", operation="cosmic")
            assert not result["ok"], result
            assert native.call("state") == baseline
    assert any(r.get("secondPassNew", 0) > 0 for r in receipts), (
        "Prove the second pass changes a fixture"
    )
    out = ROOT / "desktop/artifacts/native-lacosmic/parity.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(
            dict(comparisons=len(receipts), differentPixels=0, receipts=receipts),
            indent=2,
        )
        + "\n"
    )
    print(
        json.dumps(
            dict(comparisons=len(receipts), differentPixels=0, receipts=receipts),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
