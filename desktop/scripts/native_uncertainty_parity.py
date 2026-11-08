"""Independent NumPy integration weights and propagated counting variances.

Python is an oracle only; the Rust child has no Python executable on PATH.
"""
import json
import tempfile
from pathlib import Path

import numpy as np
from pyFAI.geometry import Geometry

from native_reference_client import Native, ROOT


def main():
    receipts = []
    with tempfile.TemporaryDirectory() as directory, Native() as n:
        directory = Path(directory)
        shape = (24, 32)
        rows, cols = np.indices(shape)
        raw = 100 + 2.0 * rows + cols
        background = 20 + rows * 0.2
        flat = 1 + cols * 0.03
        original = 2 + rows * 0.02
        response = 3 + cols * 0.01

        def plane(name, data):
            path = directory / (name + ".npy")
            np.save(path, data[::-1])
            return str(path)

        n.call("open_image", path=plane("raw", raw))
        geometry = dict(dist=0.03, poni1=-0.001, poni2=-0.0015,
                        rot1=0.008, rot2=-0.013, rot3=0.02,
                        pixel1=0.0001, pixel2=0.0001, wavelength=0.5e-10)
        n.call("manual_geometry", convention="pyfai",
               values={**geometry, "polarization_factor": 0.965})
        n.call("integration_image_background", path=plane("bg", background),
               scale=2, offset=900)
        n.call("integration_flat_field", path=plane("flat", flat))
        n.call("integration_transfer", source="original", path=plane("original", original))
        n.call("integration_transfer", source="response", path=plane("response", response))
        n.call("integration_transfer", enabled=True)
        n.call("combination_settings", factor=2)
        gain = 2 * flat.mean() / flat * original / response
        corrected = (raw - 2 * background - 900) * gain
        g = Geometry(**geometry)
        tth, azi = g.tth(rows, cols), g.chi(rows, cols)
        pol = 0.5 * (1 + np.cos(tth)**2 - 0.965 * np.cos(2*azi) * np.sin(tth)**2)
        p1 = (rows + 0.5)*geometry["pixel1"] - geometry["poni1"]
        p2 = (cols + 0.5)*geometry["pixel2"] - geometry["poni2"]
        solid_angle = (geometry["dist"] / np.sqrt(p1*p1+p2*p2+geometry["dist"]**2))**3
        for solid in [False, True]:
            for background_poisson in [False, True]:
                n.call("integration_image_background", poisson=background_poisson)
                r = n.call("integration_settings", bins=40, cake_bins=12,
                           supersampling=3, poisson_errors=True, trim_zeros=False,
                           solid_angle=solid, azimuth_range=[20, 65])
                axis = np.asarray(r["pattern"]["x"])
                step = axis[1] - axis[0]
                edge = axis[0] - step / 2
                weights = np.zeros((len(axis), raw.size))
                for dy in (1 / 6, 1 / 2, 5 / 6):
                    for dx in (1 / 6, 1 / 2, 5 / 6):
                        radial = np.degrees(g.tth(rows + dy - 0.5, cols + dx - 0.5)).ravel()
                        azimuth = np.degrees(g.chi(rows + dy - 0.5, cols + dx - 0.5)).ravel()
                        selected = (azimuth >= 20) & (azimuth < 65)
                        bins = np.clip(np.floor((radial - edge) / step).astype(int), 0, len(axis) - 1)
                        np.add.at(weights, (bins[selected], np.flatnonzero(selected)), 1 / 9)
                norm = pol * (solid_angle if solid else 1)
                denominator = weights @ norm.ravel()
                variance = (raw + (4 * background if background_poisson else 0)) * gain**2
                expected = np.divide(weights @ corrected.ravel(), denominator,
                                     out=np.zeros(len(axis)), where=denominator > 0)
                sigma = np.divide(np.sqrt(weights**2 @ variance.ravel()), denominator,
                                  out=np.zeros(len(axis)), where=denominator > 0)
                np.testing.assert_allclose(r["pattern"]["y"], expected, rtol=3e-12, atol=1e-8)
                np.testing.assert_allclose(r["pattern"]["sigma"], sigma, rtol=3e-12, atol=1e-9)
                assert np.any(expected < 0) and np.all(sigma[expected < 0] > 0)
                receipts.append(dict(solid_angle=solid, background_poisson=background_poisson,
                                     maximum_std_difference=float(np.max(abs(sigma - r["pattern"]["sigma"])))))
    output = ROOT / "desktop/artifacts/native-integration/uncertainty-parity.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(receipts, indent=2) + "\n")
    print(json.dumps(receipts, indent=2))


if __name__ == "__main__":
    main()
