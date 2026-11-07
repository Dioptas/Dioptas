"""Native Batch/Map state and independent NumPy/Qt-model numerical checks."""

import json, os, tempfile

os.environ["HDF5_PLUGIN_PRELOAD"] = "::"
from pathlib import Path
import h5py, numpy as np
from scipy.ndimage import zoom
from dioptas.model.map_reduction import reduce_window
from dioptas.model.map_layout import arrange
from native_reference_client import Native, ROOT


def main():
    receipts = []
    with tempfile.TemporaryDirectory() as tmp, Native() as n:
        tmp = Path(tmp)
        source = tmp / "scan_0001.h5"
        shape = (48, 56)
        yy, xx = np.indices(shape)
        frames = np.stack(
            [(100 + yy * 2 + xx * 3 + i * 31).astype(np.uint32) for i in range(6)]
        )
        with h5py.File(source, "w") as f:
            f.create_dataset("frames", data=frames)
        geometry = dict(
            dist=0.13,
            poni1=0.0024,
            poni2=0.0028,
            rot1=0.008,
            rot2=-0.013,
            rot3=0.02,
            pixel1=0.0001,
            pixel2=0.0001,
            wavelength=0.5e-10,
            polarization_factor=0.965,
        )
        n.call("manual_geometry", convention="pyfai", values=geometry)
        n.call("integration_settings", bins=64, cake_bins=24, poisson_errors=True)
        n.call("open_image", path=str(source), dataset="frames")
        ordinary = []
        for i in range(6):
            ordinary.append(
                n.call("open_image", path=str(source), dataset="frames", frame=i)[
                    "pattern"
                ]["y"]
            )
        before = n.call("integration_diagnostics")["integrationDiagnostics"]
        r = n.call("batch_load", paths=[str(source)])
        b = r["batch"]
        data = (
            n.raster(r, "batch")
            if False
            else np.frombuffer(n.buffers[b["raster"]["bufferId"]], dtype="<f4").reshape(
                6, 64
            )
        )
        np.testing.assert_array_equal(data, np.asarray(ordinary, dtype=np.float32))
        after = n.call("integration_diagnostics")["integrationDiagnostics"]
        assert (
            after["patternPlanBuilds"] == before["patternPlanBuilds"]
            and after["cakePlanBuilds"] == before["cakePlanBuilds"]
        )
        assert after["residentIntegrations"] - before["residentIntegrations"] == 7, (
            before,
            after,
        )
        r = n.call("batch_load", paths=[str(source)], start=2, stop=6, step=2)
        assert [e["frame"] for e in r["batch"]["entries"]] == [2, 4, 6]
        original = np.asarray(ordinary)[[1, 3, 5]]
        raw_file = tmp / "raw.h5"
        n.call("integration_save_batch", path=str(raw_file))
        with h5py.File(raw_file) as f:
            np.testing.assert_allclose(
                f["processed/result/data"][:], original, rtol=2e-12, atol=1e-10
            )
        # Read the native file through Qt's actual model, then read its saved
        # processed HDF5 back through Rust. No reference model enters the child.
        from dioptas.model.BatchModel import BatchModel

        qt = BatchModel(None)
        qt.load_proc_data(str(raw_file))
        np.testing.assert_allclose(qt.data, original, rtol=2e-12, atol=1e-10)
        qt.used_mask = None
        qt.used_calibration = None
        qt_file = tmp / "qt-processed.h5"
        qt.save_proc_data(str(qt_file))
        returned = n.call("batch_open", path=str(qt_file))
        np.testing.assert_allclose(
            returned["batch"]["pattern"]["y"], original[0], rtol=2e-12, atol=1e-10
        )
        n.call("batch_open", path=str(raw_file))
        r = n.call("batch_normalize", enabled=True, start=4, stop=50, reference=2)
        normalized = (
            original
            * original[1, 3:50].mean()
            / original[:, 3:50].mean(axis=1)[:, None]
        )
        np.testing.assert_allclose(
            r["batch"]["pattern"]["y"], normalized[0], rtol=3e-14
        )
        n.call("batch_normalize", enabled=True, start=4, stop=50, reference=2)
        normalized_file = tmp / "normalized.h5"
        n.call("integration_save_batch", path=str(normalized_file))
        n.call("batch_open", path=str(normalized_file))
        r = n.call("batch_normalize", enabled=False)
        np.testing.assert_allclose(r["batch"]["pattern"]["y"], original[0], rtol=3e-14)
        n.call("batch_unit", unit="d_A")
        r = n.call("batch_snapshot")
        assert len(r["batch"]["x"]) == 64
        n.call("batch_unit", unit="2th_deg")
        n.call("map_batch", path=str(raw_file))
        r = n.call("map_grid", rows=1, columns=3)
        x = np.asarray(r["map"]["unit"] and n.call("batch_snapshot")["batch"]["x"])
        # A map keeps its stored unit independently of global Integration settings.
        n.call("integration_settings", unit="q_A^-1")
        selected = n.call("map_select", index=1)
        assert selected["pattern"]["unit"] == "2th_deg"
        selected = n.call("map_select", index=1, reintegrate=True)
        assert selected["pattern"]["unit"] == "2th_deg"
        n.call("integration_settings", unit="2th_deg")
        # Both stored series have the same axis; choose strict physical endpoints.
        low, high = float(x[5]), float(x[55])
        for kind in ("sum", "mean", "max", "area", "center", "width"):
            for background in (False, True):
                r = n.call(
                    "map_roi",
                    op="update",
                    name="A",
                    minimum=low,
                    maximum=high,
                    reduction=kind,
                    background=background,
                )
                expected = reduce_window(x, original, (low, high), kind, background)
                np.testing.assert_allclose(
                    np.asarray(r["map"]["values"], dtype=float).ravel(),
                    expected,
                    rtol=3e-12,
                    atol=2e-10,
                    equal_nan=True,
                )
        n.call("map_roi", op="update", name="A", reduction="sum", background=False)
        n.call("map_roi", op="add")
        n.call(
            "map_roi",
            op="update",
            name="B",
            minimum=float(x[10]),
            maximum=float(x[45]),
            reduction="mean",
        )
        r = n.call(
            "map_expression",
            name="contrast",
            expression="(A-B)/(A+B) + sqrt(abs(B))/100",
        )
        a = reduce_window(x, original, (low, high), "sum")
        b = reduce_window(x, original, (x[10], x[45]), "mean")
        expected = (a - b) / (a + b) + np.sqrt(np.abs(b)) / 100
        np.testing.assert_allclose(
            np.asarray(r["map"]["values"]).ravel(), expected, rtol=1e-13
        )
        before = n.call("map_snapshot")["map"]
        bad = n.invoke("map_expression", name="bad", expression="__import__('os')")
        assert not bad["ok"]
        assert n.call("map_snapshot")["map"] == before
        n.call("map_arrange", op="insert", slot=1)
        r = n.call(
            "map_grid",
            rows=2,
            columns=3,
            snake=True,
            transpose=True,
            flip_horizontal=True,
            flip_vertical=True,
        )
        slots = r["map"]["slots"]
        expected_grid, indices = arrange(
            expected,
            (2, 3),
            slots,
            snake=True,
            transpose=True,
            flip_horizontal=True,
            flip_vertical=True,
        )
        np.testing.assert_array_equal(r["map"]["indices"], indices)
        np.testing.assert_allclose(
            np.asarray(r["map"]["values"], dtype=float), expected_grid, equal_nan=True
        )
        n.call("map_arrange", op="exclude", index=1)
        r = n.call("map_snapshot")
        expected_grid, indices = arrange(
            expected,
            (2, 3),
            r["map"]["slots"],
            snake=True,
            transpose=True,
            flip_horizontal=True,
            flip_vertical=True,
            excluded=[1],
        )
        np.testing.assert_array_equal(r["map"]["indices"], indices)
        np.testing.assert_allclose(
            np.asarray(r["map"]["values"], dtype=float), expected_grid, equal_nan=True
        )
        # Independent scipy reference, including masked blanks and mirrored edges.
        for factor in (1, 2, 3, 5):
            r = n.call("map_display", smooth=factor, contours=0)
            actual = n.raster(r, "mapPreview")
            data = np.flipud(expected_grid)
            finite = np.isfinite(data)
            filled = np.where(finite, data, np.nanmin(data))
            ref = zoom(filled, factor, order=3)
            ref[~zoom(finite, factor, order=0)] = np.nan
            np.testing.assert_allclose(
                actual, ref.astype(np.float32), rtol=2e-6, atol=1e-7, equal_nan=True
            )
        # Live appends only matching numbered files after stable observations;
        # unreadable files do not prevent a readable continuation or later retry.
        points = n.call("map_snapshot")["map"]["points"]
        new = tmp / "scan_0002.h5"
        with h5py.File(new, "w") as f:
            f.create_dataset("frames", data=frames[:1])
        n.call("map_poll", check_only=True)
        r = n.call("map_poll")
        assert r["map"]["points"] == points + 1
        corrupt = tmp / "scan_0003.h5"
        corrupt.write_bytes(b"not an HDF5 file")
        new = tmp / "scan_0004.h5"
        with h5py.File(new, "w") as f:
            f.create_dataset("frames", data=frames[1:2])
        n.call("map_poll", check_only=True)
        r = n.call("map_poll")
        assert r["map"]["points"] == points + 2 and "retrying" in r["mapWarning"]
        with h5py.File(corrupt, "w") as f:
            f.create_dataset("frames", data=frames[2:3])
        n.call("map_poll", check_only=True)
        r = n.call("map_poll")
        assert r["map"]["points"] == points + 3
        receipts.append(
            {
                "batch": "same owner as navigation; exact f32 matrix; one warm pattern/cake plan",
                "map": "12 reductions, expressions, transforms, exclusions and SciPy cubic previews",
                "hdf5": "raw/normalized series roundtrip; normalization restores original f64 samples",
            }
        )
    output = ROOT / "desktop/artifacts/native-integration/series-parity.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(receipts, indent=2) + "\n")
    print(json.dumps(receipts, indent=2))


if __name__ == "__main__":
    main()
