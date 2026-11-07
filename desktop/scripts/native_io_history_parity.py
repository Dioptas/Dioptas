"""Workflow checks for masks, exports, image actions, polling and shared history."""

import json, tempfile, time
from pathlib import Path
import numpy as np, fabio
from PIL import Image
from native_reference_client import Native, ROOT


def main():
    receipts = []
    with (
        tempfile.TemporaryDirectory() as directory,
        Native(
            env={"DIOPTAS_CUSTOM_COMMANDS_FILE": str(Path(directory) / "commands.json")}
        ) as n,
    ):
        directory = Path(directory)
        shape = (36, 44)
        yy, xx = np.indices(shape)
        stored = (100 + xx * 3 + yy * 7).astype(np.uint16)
        source = directory / "image_0001.npy"
        np.save(source, stored)
        second = directory / "image_0002.npy"
        np.save(second, stored + 80)
        n.call("open_image", path=str(source))
        n.call(
            "manual_geometry",
            convention="pyfai",
            values=dict(
                dist=0.13,
                poni1=0.0018,
                poni2=0.0022,
                rot1=0.008,
                rot2=-0.013,
                rot3=0.02,
                pixel1=0.0001,
                pixel2=0.0001,
                wavelength=0.5e-10,
                polarization_factor=0.965,
            ),
        )
        n.call("integration_settings", bins=64, cake_bins=24, poisson_errors=True)
        # Independent subpixel forward geometry and unit-stable linked readout.
        from pyFAI.geometry import Geometry

        geometry = Geometry(
            dist=0.13,
            poni1=0.0018,
            poni2=0.0022,
            rot1=0.008,
            rot2=-0.013,
            rot3=0.02,
            pixel1=0.0001,
            pixel2=0.0001,
            wavelength=0.5e-10,
        )
        linked = n.call("validation_position", source="image", x=12.25, y=17.75)[
            "linked"
        ]
        expected = np.degrees(geometry.tth(np.array([17.25]), np.array([11.75])))[0]
        np.testing.assert_allclose(linked["twoTheta"], expected, rtol=2e-14)
        q = n.call("integration_settings", unit="q_A^-1")["linked"]
        np.testing.assert_allclose(
            q["radial"], 4 * np.pi * np.sin(np.radians(expected) / 2) / 0.5, rtol=2e-14
        )
        n.call("integration_settings", unit="2th_deg")
        mask = np.zeros(shape, dtype=np.int8)
        mask[4, 11] = 1
        mask[29, 30] = 1
        maskfile = directory / "source-mask.npy"
        np.save(maskfile, mask)
        loaded = n.call("mask_file", path=str(maskfile))
        np.testing.assert_array_equal(n.raster(loaded, "mask"), mask)
        for suffix in ("npy", "mask", "edf"):
            saved = directory / f"saved.{suffix}"
            n.call("mask_file", path=str(saved), save=True)
            data = (
                np.load(saved)
                if suffix == "npy"
                else np.asarray(Image.open(saved))
                if suffix == "mask"
                else fabio.open(str(saved)).data
            )
            np.testing.assert_array_equal(data, mask)
            n.call("clear_mask")
            r = n.call("mask_file", path=str(saved))
            np.testing.assert_array_equal(n.raster(r, "mask"), mask)
        textmask = directory / "mask.txt"
        np.savetxt(textmask, mask, fmt="%d")
        r = n.call("mask_file", path=str(textmask))
        np.testing.assert_array_equal(n.raster(r, "mask"), mask)
        flipped = n.call("mask_file", path=str(maskfile), flipud=True)
        np.testing.assert_array_equal(n.raster(flipped, "mask"), mask[::-1])
        r = n.call("undo_mask")
        np.testing.assert_array_equal(n.raster(r, "mask"), mask)
        pattern = n.call("state")["pattern"]
        raw = np.column_stack((pattern["x"], pattern["y"]))
        for suffix in ("xy", "xye", "chi", "dat", "fxye"):
            n.call("open_image", path=str(source))
            n.call("mask_file", path=str(maskfile))
            saved = directory / f"pattern.{suffix}"
            n.call("integration_save_pattern", path=str(saved))
            r = n.call("integration_open_pattern", path=str(saved))
            np.testing.assert_allclose(r["pattern"]["x"], raw[:, 0], rtol=2e-15)
            np.testing.assert_allclose(r["pattern"]["y"], raw[:, 1], rtol=2e-15)
        # Imported patterns convert with a loaded wavelength and remain visible.
        n.call("integration_settings", unit="q_A^-1")
        r = n.call("integration_settings", unit="2th_deg")
        np.testing.assert_allclose(r["pattern"]["x"], raw[:, 0], rtol=3e-14)
        n.call("open_image", path=str(source))
        original = n.call("state")
        n.call("integration_overlay", operation="capture")
        n.call("integration_overlay", operation="update", index=0, scale=1.2)
        scaled = n.call("integration_overlay", operation="update", index=0, scale=1.8)
        undone = n.call("undo_calibration")
        assert undone["state"]["integration"]["overlays"][0]["scale"] == 1.0
        # A read-only save does not destroy Redo.
        n.call("save_calibration", path=str(directory / "saved.poni"))
        redone = n.call("redo_calibration")
        assert redone["state"]["integration"]["overlays"][0]["scale"] == 1.8
        n.call("integration_roi", limits=[3, 31, 5, 38])
        n.call("undo_calibration")
        assert n.call("state")["state"]["integration"]["roi"] is None
        # Autocreate follows an explicit integration/settings recalculation too.
        auto = directory / "patterns"
        auto.mkdir()
        n.call("integration_autocreate", enabled=True, directory=str(auto))
        n.call("integrate")
        saved = auto / (source.stem + ".xy")
        assert saved.is_file()
        before_bytes = saved.read_bytes()
        n.call("integration_settings", bins=65)
        assert saved.read_bytes() != before_bytes
        n.call("integration_autocreate", enabled=False)
        n.call("integration_settings", bins=64)
        # Add/average preserve typed source files and use scientific raw data.
        r = n.call("open_image", paths=[str(source), str(second)], batch_mode="average")
        np.testing.assert_array_equal(
            n.raster(r, "rawImage"),
            (stored.astype(float) + 40)[::-1].astype(np.float32),
        )
        np.testing.assert_array_equal(np.load(source), stored)
        output = directory / "images"
        output.mkdir()
        r = n.call(
            "open_image",
            paths=[str(source), str(second)],
            batch_mode="save",
            output_directory=str(output),
        )
        assert r["imageBatchSaved"] and len(r["savedPaths"]) == 2
        np.testing.assert_array_equal(
            np.asarray(Image.open(output / "batch_image_0001.tiff")),
            stored.astype(np.int32),
        )
        before = n.call("state")
        assert not n.invoke(
            "open_image",
            paths=[str(source), str(second)],
            batch_mode="save",
            output_directory=str(output),
        )["ok"]
        assert n.call("state") == before
        # Stable incoming-file polling ignores the baseline, then requires two observations.
        n.call("integration_autoprocess", enabled=True, directory=str(directory))
        third = directory / "image_0003.npy"
        np.save(third, stored + 160)
        n.call("integration_autoprocess_poll")
        r = n.call("integration_autoprocess_poll")
        assert Path(r["state"]["imagePath"]).resolve() == third.resolve()
        n.call("integration_autoprocess", enabled=False)
        # Explicit custom actions use an isolated settings file and direct argv.
        n.call(
            "custom_command",
            operation="save",
            command=dict(
                id="test",
                name="Echo image",
                program="/usr/bin/printf",
                arguments=["%s", "{image_name}"],
                enabled=True,
                icon="terminal",
            ),
        )
        n.call("custom_command", operation="run", identifier="test")
        for _ in range(100):
            runs = n.call("custom_command")["customCommandRuns"]
            if not runs["test"]["running"]:
                break
            time.sleep(0.01)
        assert runs["test"]["exitCode"] == 0 and runs["test"]["output"] == third.name
        n.call("custom_command", operation="delete", identifier="test")
        receipts.append(
            {
                "maskFiles": "NPY/TIFF/EDF stored rows and explicit flip; mask Undo",
                "patternFiles": "five formats read back; imported unit conversion",
                "history": "grouped overlay changes, Redo after save, ROI Undo",
                "imageActions": "average plus staged save, no source/target overwrite",
                "incoming": "baseline plus stable two-observation poll",
            }
        )
    out = ROOT / "desktop/artifacts/native-integration/io-history-parity.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(receipts, indent=2) + "\n")
    print(json.dumps(receipts, indent=2))


if __name__ == "__main__":
    main()
