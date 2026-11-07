"""Format-2 .dio cross-reader, offline-cache and configuration ownership checks."""

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
    poni1=0.0016,
    poni2=0.002,
    pixel1=0.0001,
    pixel2=0.0001,
    rot1=0.008,
    rot2=-0.013,
    rot3=0.02,
    wavelength=0.5e-10,
    polarization_factor=0.965,
)


def science(n):
    r = n.call("state")
    return dict(
        image=n.raster(r, "rawImage").copy() if r.get("rawImage") else None,
        pattern=r.get("pattern"),
        integration=r["state"]["integration"],
        calibration=r["state"]["calibration"],
    )


def assert_science(a, b):
    if a["image"] is None:
        assert b["image"] is None
    else:
        np.testing.assert_array_equal(a["image"], b["image"])
    if a["pattern"] is not None:
        np.testing.assert_allclose(
            a["pattern"]["x"], b["pattern"]["x"], rtol=2e-12, atol=1e-12
        )
        np.testing.assert_allclose(
            a["pattern"]["y"], b["pattern"]["y"], rtol=2e-12, atol=1e-10
        )
    for key in (
        "roi",
        "supersampling",
        "solidAngle",
        "polarization",
        "poissonErrors",
        "patternBackground",
        "flatField",
        "corrections",
    ):
        assert a["integration"][key] == b["integration"][key], key


def main():
    receipts = []
    with tempfile.TemporaryDirectory() as directory, Native() as n:
        d = Path(directory)
        shape = (32, 40)
        rows, cols = np.indices(shape)
        data = np.stack(
            [(100 + rows * 2 + cols * 3 + i * 50).astype(np.uint32) for i in range(3)]
        )
        source = d / "frames.h5"
        with h5py.File(source, "w") as f:
            f.create_dataset("frames", data=data)
        background = d / "background.npy"
        np.save(background, np.full(shape, 4.0))
        flat = d / "flat.npy"
        np.save(flat, 2 + cols * 0.01)
        n.call("open_image", path=str(source), dataset="frames")
        n.call("manual_geometry", convention="pyfai", values=GEOMETRY)
        n.call("integration_settings", bins=64, cake_bins=24, poisson_errors=True)
        n.call(
            "integration_image_background", path=str(background), scale=0.7, offset=1.2
        )
        n.call("integration_flat_field", path=str(flat))
        n.call(
            "mask_plugin",
            name="Threshold Mask",
            enabled=True,
            settings=dict(above_value=300),
        )
        n.call("integration_roi", limits=[2, 30, 3, 38])
        n.call("integration_overlay", operation="capture")
        n.call(
            "integration_phase",
            operation="load",
            path=str(ROOT / "dioptas/tests/data/jcpds/mo.jcpds"),
        )
        n.call(
            "integration_phase",
            operation="update",
            index=0,
            pressure=20,
            temperature=500,
        )
        n.call("configuration", operation="rename", name="Reference")
        n.call("batch_load", paths=[str(source)], start=1, stop=3, step=2)
        batch = d / "batch.h5"
        n.call("integration_save_batch", path=str(batch))
        n.call("map_batch", path=str(batch))
        n.call("map_grid", rows=1, columns=2)
        n.call("map_normalize", enabled=True, start=2, stop=55, reference=1)
        n.call("batch_normalize", enabled=True, start=2, stop=55, reference=2)
        n.call("batch_select", index=1)
        n.call("configuration", operation="duplicate")
        n.call("configuration", operation="rename", name="Sample")
        n.call("integration_settings", bins=80, cake_bins=20)
        n.call("open_image", path=str(source), dataset="frames", frame=2)
        # Opening a same-shape frame retains settings, masks and image corrections.
        n.call("integration_image_background", scale=0.2, offset=0.5)
        second = science(n)
        n.call("configuration", operation="select", index=0)
        first = science(n)
        assert first["image"].shape == shape
        n.call("configuration", operation="select", index=1)
        assert_science(second, science(n))
        # A setting Undo in one configuration must not revert shared phase edits.
        n.call("integration_settings", bins=81)
        n.call("configuration", operation="select", index=0)
        n.call("integration_phase", operation="update", index=0, pressure=25)
        n.call("configuration", operation="select", index=1)
        n.call("undo_calibration")
        assert n.call("state")["state"]["integration"]["phases"][0]["pressure"] == 25
        second = science(n)
        n.call("configuration", operation="select", index=0)
        first = science(n)
        project = d / "native.dio"
        n.call("save_project", path=str(project))
        # The existing Python reader consumes native output, including both maps.
        ref = DesktopSession()
        result = ref.invoke("open_project", dict(path=str(project)))
        assert result["ok"], result
        assert len(ref._model.configurations) == 2
        for i, expected in enumerate((first, second)):
            c = ref._model.configurations[i]
            np.testing.assert_array_equal(
                c.img_model.raw_img_data,
                expected["image"].astype(float),
            )
            assert c.integration_rad_points == [64, 80][i]
            assert c.map_model.num_points == 2
        receipts.append(
            dict(case="Rust writer → existing Python reader", configurations=2, maps=2)
        )
        # The Python writer produces a fresh format-2 file, without native
        # per-configuration documents. Include a source-only image scale factor.
        ref.configuration.batch_model.bkg = np.full_like(
            ref.configuration.batch_model.data, 2.0
        )
        ref.configuration.img_model.factor = 1.25
        ref._calculate()
        python_project = d / "python.dio"
        result = ref.invoke("save_project", dict(path=str(python_project)))
        assert result["ok"], result
        expected_display = ref.configuration.img_model.img_data.astype(np.float32)
        loaded = n.call("open_project", path=str(python_project))
        np.testing.assert_array_equal(n.raster(loaded, "image"), expected_display)
        assert loaded["state"]["configurationCount"] == 2
        assert loaded["map"]["points"] == 2
        assert loaded["batch"]["selected"] == 1
        assert loaded["batch"]["files"][0]["frames"] == 3
        for i in range(2):
            r = n.call("configuration", operation="select", index=i)
            np.testing.assert_array_equal(
                n.raster(r, "rawImage"),
                [first, second][i]["image"],
            )
        n.call("configuration", operation="select", index=0)
        python_roundtrip = d / "python-roundtrip.dio"
        n.call("save_project", path=str(python_roundtrip))
        with h5py.File(python_roundtrip) as f:
            np.testing.assert_array_equal(f["react_desktop_batch/file_map"][:], [0, 3])
            assert f["react_desktop_batch/pos_map_all"].shape == (3, 2)
            np.testing.assert_allclose(f["react_desktop_batch/bkg"][:], 2.0)
        # Reopen with the ordinary Python reader once more after Rust wrote it.
        result = DesktopSession().invoke(
            "open_project", dict(path=str(python_roundtrip))
        )
        assert result["ok"], result
        receipts.append(
            dict(
                case="existing Python writer → Rust → Python reader",
                configurations=2,
                imageScale=1.25,
            )
        )
        # Unknown document fields and HDF5 objects survive a native load/edit/save.
        with h5py.File(project, "r+") as f:
            doc = json.loads(f["state"][()])
            doc["future_root"] = {"note": "retained"}
            doc["configurations"][1]["params"]["future_setting"] = [3, 4]
            del f["state"]
            f["state"] = json.dumps(doc)
            f.attrs["future_attribute"] = "retained"
            g = f.create_group("future_payload")
            g.create_dataset("data", data=np.arange(7))
            g.attrs["detail"] = "untouched"
            f["configurations/1"].create_dataset(
                "future_config_data", data=np.arange(4)
            )
        n.call("open_project", path=str(project))
        assert_science(first, science(n))
        n.call("configuration", operation="select", index=1)
        assert_science(second, science(n))
        again = d / "again.dio"
        n.call("save_project", path=str(again))
        with h5py.File(again) as f:
            doc = json.loads(f["state"][()])
            assert doc["future_root"] == {"note": "retained"}
            assert doc["configurations"][1]["params"]["future_setting"] == [3, 4]
            assert f.attrs["future_attribute"] == "retained"
            np.testing.assert_array_equal(f["future_payload/data"][:], np.arange(7))
            np.testing.assert_array_equal(
                f["configurations/1/future_config_data"][:], np.arange(4)
            )
        # Cached images/backgrounds/flat responses remain owned after originals move.
        source.unlink()
        background.unlink()
        flat.unlink()
        n.call("open_project", path=str(again))
        assert_science(second, science(n))
        n.call("configuration", operation="select", index=0)
        assert_science(first, science(n))
        r = n.call("map_normalize", enabled=False)
        assert not r["map"]["normalized"]
        r = n.call("batch_normalize", enabled=False)
        assert not r["batch"]["normalized"]
        assert not n.call("state")["state"]["integration"]["autoProcess"]
        assert not n.call("state")["state"]["integration"]["autoSave"]
        offline = d / "offline.dio"
        n.call("save_project", path=str(offline))
        n.call("open_project", path=str(offline))
        # Legacy/future/corrupt documents fail before replacing any live state.
        baseline = n.call("state")
        for version in (1, 3):
            bad = d / f"unsupported-{version}.dio"
            with h5py.File(bad, "w") as f:
                f.attrs["format_version"] = version
                f["state"] = "{}"
            assert not n.invoke("open_project", path=str(bad))["ok"]
            assert n.call("state") == baseline
        corrupt = d / "corrupt.dio"
        corrupt.write_bytes(b"broken")
        assert not n.invoke("open_project", path=str(corrupt))["ok"]
        assert n.call("state") == baseline
        assert not n.invoke("save_project", path=str(d / "missing" / "out.dio"))["ok"]
        assert n.call("state") == baseline
        receipts.append(
            dict(
                case="native roundtrip",
                science="f64 profiles, masks, corrections and independent configurations",
                offline="image/background/flat caches",
                extensions="unknown JSON, root attributes and binary groups retained",
                failure="no session replacement",
            )
        )
        # Removing a configuration reindexes complete preserved HDF5 groups.
        n.call("configuration", operation="remove")
        assert n.call("state")["state"]["configurationCount"] == 1
        removed = d / "removed.dio"
        n.call("save_project", path=str(removed))
        with h5py.File(removed) as f:
            np.testing.assert_array_equal(
                f["configurations/0/future_config_data"][:], np.arange(4)
            )
        custom = d / "session-reference.D"
        custom.write_text((ROOT / "dioptas/resources/calibrants/CeO2.D").read_text())
        n.call("open_calibrant", path=str(custom))
        n.call("workflow_settings", algorithm="Blob", numberOfRings=3, searchSize=5)
        n.call("pick_peak", x=5, y=5, ring=1, automatic=False, search_size=1)
        n.call(
            "integration_phase",
            operation="load_database",
            material_id="gold",
            reference=0,
        )
        n.call(
            "integration_phase",
            operation="load",
            path=str(ROOT / "dioptas/tests/data/cif/fcc.cif"),
            minimum_d_spacing=0.5,
            intensity_cutoff=0.5,
        )
        calibration = n.call("state")["state"]["calibration"]
        editors = [
            n.call("integration_phase_editor", index=i)["phaseEditor"] for i in range(3)
        ]
        complete = d / "calibration-materials.dio"
        n.call("save_project", path=str(complete))
        custom.unlink()
        loaded = n.call("open_project", path=str(complete))
        for key, value in calibration.items():
            if key not in ("canUndo", "canRedo"):
                assert loaded["state"]["calibration"][key] == value, key
        for i, expected in enumerate(editors):
            actual = n.call("integration_phase_editor", index=i)["phaseEditor"]
            assert actual == expected, (
                i,
                {
                    k: (v, actual.get(k))
                    for k, v in expected.items()
                    if v != actual.get(k)
                },
            )
        # Invalid stored measured coordinates must not partially replace a session.
        baseline = n.call("state")
        import shutil

        invalid = d / "invalid-picks.dio"
        shutil.copyfile(complete, invalid)
        with h5py.File(invalid, "r+") as f:
            doc = json.loads(f["state"][()])
            doc["configurations"][0]["calibration"]["peak_selections"] = [
                [0, [[99999, 0]]]
            ]
            del f["state"]
            f["state"] = json.dumps(doc)
        assert not n.invoke("open_project", path=str(invalid))["ok"]
        assert n.call("state") == baseline
        invalid_range = d / "invalid-normalization.dio"
        shutil.copyfile(python_project, invalid_range)
        with h5py.File(invalid_range, "r+") as f:
            batch_group = f["react_desktop_batch"]
            metadata = json.loads(batch_group.attrs["metadata"])
            metadata["normalization_range"] = [55, 2]
            batch_group.attrs["metadata"] = json.dumps(metadata)
        assert not n.invoke("open_project", path=str(invalid_range))["ok"]
        assert n.call("state") == baseline
        receipts.append(
            dict(
                case="calibration and materials",
                picks="row/column groups retained; invalid coordinates rejected atomically",
                customCalibrant="owned without source",
                workflow="Blob settings",
                materials="legacy, Peritheos gold and CIF editors preserved",
            )
        )
    out = ROOT / "desktop/artifacts/native-project/parity.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(receipts, indent=2) + "\n")
    print(json.dumps(receipts, indent=2))


if __name__ == "__main__":
    main()
