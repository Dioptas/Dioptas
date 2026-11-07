"""Independent image-correction and SmoothBruckner comparisons."""

import json
import tempfile
from pathlib import Path
import numpy as np
from pyFAI.geometry import Geometry
from dioptas.model.util.ImgCorrection import (
    CbnCorrection,
    ObliqueAngleDetectorAbsorptionCorrection,
)
from xypattern import Pattern
from xypattern.auto_background import SmoothBrucknerBackground
from native_reference_client import Native, ROOT


def main():
    receipts = []
    with tempfile.TemporaryDirectory() as directory, Native() as n:
        directory = Path(directory)
        shape = (48, 56)
        rows, cols = np.indices(shape)
        data = 500 + rows * 1.7 + cols * 0.8
        background = 10 + rows * 0.01
        flat = 0.7 + cols * 0.02 + rows * 0.005

        def plane(name, values):
            file = directory / (name + ".npy")
            np.save(file, values[::-1])
            return str(file)

        path = plane("detector", data)
        bgfile = plane("background", background)
        flatfile = plane("flat", flat)
        n.call("open_image", path=path)
        values = dict(
            dist=0.03,
            poni1=0.0021,
            poni2=0.0029,
            rot1=0.04,
            rot2=-0.03,
            rot3=0.01,
            pixel1=0.0001,
            pixel2=0.0001,
            wavelength=0.5e-10,
            polarization_factor=0.965,
        )
        n.call("integration_settings", bins=160, cake_bins=36)
        n.call("manual_geometry", convention="pyfai", values=values)
        original = n.call("state")["rawImage"]["bufferId"]
        r = n.call("integration_image_background", path=bgfile, scale=0.7, offset=-4)
        expected = data - (0.7 * background - 4)
        np.testing.assert_array_equal(n.raster(r, "image"), expected.astype(np.float32))
        assert r["rawImage"]["bufferId"] == original
        r = n.call("integration_flat_field", path=flatfile, enabled=True)
        expected /= flat / flat.mean()
        np.testing.assert_array_equal(n.raster(r, "image"), expected.astype(np.float32))
        g = Geometry(**{k: v for k, v in values.items() if k != "polarization_factor"})
        tth = g.center_array(shape, unit="2th_rad")
        azi = g.center_array(shape, unit="chi_rad")
        cases = [
            (
                "cbn",
                dict(
                    tilt=7, tilt_rotation=31, center_offset=0.02, center_offset_angle=45
                ),
            ),
            (
                "oiadac",
                dict(tilt=3, rotation=16, detector_thickness=44, absorption_length=120),
            ),
        ]
        for kind, params in cases:
            r = n.call(
                "integration_correction", kind=kind, enabled=True, parameters=params
            )
            if kind == "cbn":
                ref = CbnCorrection(
                    tth_array=np.rad2deg(tth), azi_array=np.rad2deg(azi), **params
                )
                ref.update()
            else:
                ref = ObliqueAngleDetectorAbsorptionCorrection(
                    tth_array=tth, azi_array=azi, **params
                )
            expected /= ref.get_data()
            np.testing.assert_allclose(
                n.raster(r, "image"), expected.astype(np.float32), rtol=2e-7, atol=1e-5
            )
            for row, col in [(0, 0), (15, 26), (47, 55)]:
                pixel = n.call("pixel", x=col, y=row)["pixel"]["value"]
                np.testing.assert_allclose(
                    pixel, expected[row, col], rtol=3e-13, atol=1e-9
                )
                assert (
                    n.call("pixel", x=col, y=row, source="raw_detector")["pixel"][
                        "value"
                    ]
                    == data[row, col]
                )
            assert r["rawImage"]["bufferId"] == original
            receipts.append(
                dict(
                    correction=kind,
                    reference="original Python correction",
                    maximumDisplayDifference=float(
                        np.max(abs(n.raster(r, "image") - expected.astype(np.float32)))
                    ),
                )
            )
        before = n.call("state")
        bad = plane("wrong-shape", np.ones((4, 7)))
        assert not n.invoke("integration_image_background", path=bad)["ok"]
        assert n.call("state") == before
        assert not n.invoke(
            "integration_correction",
            kind="cbn",
            enabled=True,
            parameters=dict(small_cbn_seat_radius=5, large_cbn_seat_radius=1),
        )["ok"]
        assert n.call("state") == before
        # A loaded pattern also works without a detector or calibration.
    with tempfile.TemporaryDirectory() as directory, Native() as n:
        directory = Path(directory)
        x = np.linspace(5, 30, 401)
        y = (
            20
            + 0.2 * x
            + 40 * np.exp(-(((x - 13) / 0.22) ** 2))
            + 15 * np.exp(-(((x - 22) / 0.4) ** 2))
        )
        file = directory / "pattern.xy"
        np.savetxt(file, np.c_[x, y])
        n.call("integration_open_pattern", path=str(file))
        for order, limits in [(8, None), (12, [7, 27])]:
            r = n.call(
                "integration_background",
                enabled=True,
                smoothing=0.2,
                iterations=30,
                order=order,
                range=limits,
            )
            reference = Pattern(x.copy(), y.copy())
            reference.auto_bkg_roi = limits
            reference.auto_bkg = SmoothBrucknerBackground(0.2, 30, order)
            xx, yy = reference.data
            np.testing.assert_array_equal(r["pattern"]["x"], xx)
            np.testing.assert_allclose(r["pattern"]["y"], yy, rtol=1e-8, atol=2e-9)
            receipts.append(
                dict(
                    background="SmoothBruckner/Chebyshev",
                    order=order,
                    range=limits,
                    maximumDifference=float(
                        np.max(abs(np.array(r["pattern"]["y"]) - yy))
                    ),
                )
            )
        r = n.call("integration_overlay", operation="capture")
        assert r["patternOnly"] and "cake" not in r and "mask" not in r
        r = n.call(
            "integration_overlay",
            operation="update",
            index=0,
            scale=1.5,
            offset=2,
            name="Reference",
        )
        assert r["state"]["integration"]["overlays"][0]["name"] == "Reference"
        yy = np.array(r["pattern"]["y"])
        np.testing.assert_allclose(r["pattern"]["curves"][0]["y"], 1.5 * yy + 2)
    output = ROOT / "desktop/artifacts/native-integration"
    output.mkdir(parents=True, exist_ok=True)
    (output / "processing-parity.json").write_text(
        json.dumps(receipts, indent=2) + "\n"
    )
    print(json.dumps(receipts, indent=2))


if __name__ == "__main__":
    main()
