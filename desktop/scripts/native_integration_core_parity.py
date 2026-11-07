"""Independent counts, resident/combined, plan reuse and angular-window checks."""

import json
import tempfile
import os

# The independent writer supplies direct chunks. Disable ambient HDF5 plugins
# before loading HDF5 so a system plugin with another HDF5 ABI cannot intervene.
os.environ["HDF5_PLUGIN_PRELOAD"] = "::"
from pathlib import Path
import h5py
import bitshuffle
import struct
import numpy as np
from pyFAI.geometry import Geometry
from native_reference_client import Native, ROOT


def main():
    receipts = []
    with tempfile.TemporaryDirectory() as directory, Native() as n:
        directory = Path(directory)
        shape = (80, 96)
        rows, cols = np.indices(shape)
        stored = (100 + rows * 5 + cols * 3).astype(np.uint32)
        stack = np.stack([stored, stored + 80, stored * 2 + 9])
        path = directory / "frames.h5"
        for index in reversed(range(h5py.h5pl.size())):
            h5py.h5pl.remove(index)
        if h5py.h5z.filter_avail(32008):
            h5py.h5z.unregister_filter(32008)
        with h5py.File(path, "w") as f:
            # Direct chunks avoid depending on a filter linked to the same
            # HDF5 ABI as h5py. Compression is the independent Bitshuffle codec.
            for name, data in [("frames", stack), ("different", stack + 999)]:
                dataset = f.create_dataset(
                    name,
                    shape=data.shape,
                    dtype=data.dtype,
                    chunks=(1, *shape),
                    compression=32008,
                    compression_opts=(0, 4, 4, 2048, 2),
                    allow_unknown_filter=True,
                )
                for index, frame in enumerate(data):
                    payload = (
                        struct.pack(">QI", frame.nbytes, 2048 * 4)
                        + bitshuffle.compress_lz4(frame, block_size=2048).tobytes()
                    )
                    dataset.id.write_direct_chunk((index, 0, 0), payload, filter_mask=0)
            f.create_dataset("gzip", data=stack, chunks=(1, *shape), compression="gzip")
        values = dict(
            dist=0.13,
            poni1=0.0038,
            poni2=0.0047,
            rot1=0.008,
            rot2=-0.013,
            rot3=0.02,
            pixel1=0.0001,
            pixel2=0.0001,
            wavelength=0.5e-10,
            polarization_factor=0.965,
        )
        n.call("manual_geometry", convention="pyfai", values=values)
        n.call("integration_settings", bins=128, cake_bins=36, poisson_errors=True)
        first = n.call("open_image", path=str(path), dataset="frames")
        assert first["nativeSource"]["loadPath"] == "combined-hdf5", first[
            "nativeSource"
        ]
        assert first["nativeSource"]["ordinaryDecodes"] == 0
        np.testing.assert_array_equal(
            n.raster(first, "rawImage"), stack[0, ::-1].astype(np.float32)
        )
        d1 = n.call("integration_diagnostics")["integrationDiagnostics"]
        for frame in range(3):
            if frame:
                combined = n.call("next_image", direction=1)
            else:
                combined = first
            np.testing.assert_array_equal(
                n.raster(combined, "rawImage"), stack[frame, ::-1].astype(np.float32)
            )
            resident = n.call("integrate")
            np.testing.assert_allclose(
                combined["pattern"]["y"],
                resident["pattern"]["y"],
                rtol=2e-12,
                atol=1e-10,
            )
            np.testing.assert_allclose(
                combined["pattern"]["sigma"],
                resident["pattern"]["sigma"],
                rtol=2e-12,
                atol=1e-10,
            )
            assert combined["cake"]["bufferId"] == resident["cake"]["bufferId"]
        d2 = n.call("integration_diagnostics")["integrationDiagnostics"]
        assert d2["patternPlanBuilds"] == d1["patternPlanBuilds"]
        assert d2["cakePlanBuilds"] == d1["cakePlanBuilds"]
        assert d2["combinedDecodes"] == 3 and d2["preparedHits"] == 3
        selected = n.call("open_image", path=str(path), dataset="different")
        np.testing.assert_array_equal(
            n.raster(selected, "rawImage"), (stack[0] + 999)[::-1].astype(np.float32)
        )
        assert (
            n.call("integration_diagnostics")["integrationDiagnostics"][
                "patternPlanBuilds"
            ]
            == d1["patternPlanBuilds"]
        )
        fallback = n.call("open_image", path=str(path), dataset="gzip")
        assert (
            fallback["nativeSource"]["loadPath"] == "native-reader"
            and fallback["nativeSource"]["ordinaryDecodes"] == 1
        )
        np.testing.assert_allclose(
            fallback["pattern"]["y"], first["pattern"]["y"], rtol=2e-12, atol=1e-10
        )
        # A fixed ROI shares the combined path, including when use-mask is off.
        n.call("integration_roi", limits=[12, 64, 18, 80])
        roi = n.call("open_image", path=str(path), dataset="frames")
        assert roi["nativeSource"]["loadPath"] == "combined-hdf5"
        np.testing.assert_allclose(
            roi["pattern"]["y"],
            n.call("integrate")["pattern"]["y"],
            rtol=2e-12,
            atol=1e-10,
        )
        # Dynamic plugins retain resident processing and invalidate their own mask.
        n.call(
            "mask_plugin",
            name="Threshold Mask",
            enabled=True,
            settings=dict(above_value=600),
        )
        dynamic = n.call("open_image", path=str(path), dataset="frames")
        assert dynamic["nativeSource"]["loadPath"] == "native-reader"
        n.call("mask_plugin", name="Threshold Mask", enabled=False)
        n.call("integration_roi", limits=None)
        before = n.call("state")
        assert not n.invoke("integration_settings", bins=111, azimuth_range=[20, 20])[
            "ok"
        ]
        assert n.call("state") == before
        n.call("integration_settings", bins=None)
        automatic = n.call("open_image", path=str(path), dataset="frames")
        g = Geometry(**{k: v for k, v in values.items() if k != "polarization_factor"})
        f2d = g.getFit2D()
        width, height = shape
        a = (
            max(abs(width - f2d["centerX"]), f2d["centerX"])
            if 0 < f2d["centerX"] < width
            else width
        )
        b = (
            max(abs(height - f2d["centerY"]), f2d["centerY"])
            if 0 < f2d["centerY"] < height
            else height
        )
        assert len(automatic["pattern"]["x"]) == int(np.hypot(a, b) * 2)
        assert automatic["nativeSource"]["ordinaryDecodes"] == 0
        receipts.append(
            dict(
                case="combined input and warm plans",
                frames=3,
                exactDisplayCounts=True,
                diagnostics=d2,
            )
        )
        # Constant normalized input establishes the expected intensity for every
        # populated bin independently of either library's splitting weights.
        scientific = (
            g.solidAngleArray(shape) * g.polarization(shape, factor=0.965) * 700
        )
        file = directory / "normalized.npy"
        np.save(file, scientific[::-1])
        n.call("open_image", path=str(file))
        for sector in [None, [-40, 70], [150, -140]]:
            r = n.call(
                "integration_settings",
                bins=80,
                azimuth_range=sector,
                cake_azimuth_range=sector,
            )
            y = np.array(r["pattern"]["y"])
            populated = y > 0
            np.testing.assert_allclose(y[populated], 700, rtol=3e-7, atol=2e-5)
            cake = n.raster(r, "cake")
            np.testing.assert_allclose(cake[cake > 0], 700, rtol=3e-7, atol=2e-5)
            assert populated.any()
            receipts.append(
                dict(
                    case="normalized angular sector",
                    sector=sector,
                    populated=int(populated.sum()),
                )
            )
        # Factor zero means unpolarized correction, not correction disabled.
        np.save(file, (g.polarization(shape, factor=0) * 700.0)[::-1])
        n.call("open_image", path=str(file))
        for supersampling in [1, 2]:
            r = n.call(
                "integration_settings",
                solid_angle=False,
                polarization=0,
                supersampling=supersampling,
                azimuth_range=[150, -140],
                cake_azimuth_range=[150, -140],
            )
            y = np.array(r["pattern"]["y"])
            np.testing.assert_allclose(y[y > 0], 700, rtol=3e-7, atol=2e-5)
            receipts.append(
                dict(case="uncorrected wrapped sector", supersampling=supersampling)
            )
        # High counts in the opposite sector must never wrap into this window.
        chi = np.degrees(g.center_array(shape, unit="chi_rad"))
        opposite = np.where(
            ((chi < -10) | (chi > 80)) & (g.center_array(shape, unit="2th_rad") > 0.01),
            1e6,
            0.0,
        )
        np.save(file, opposite[::-1])
        n.call("open_image", path=str(file))
        for supersampling in (1, 2):
            r = n.call(
                "integration_settings",
                solid_angle=False,
                polarization=0,
                supersampling=supersampling,
                azimuth_range=[20, 50],
                cake_azimuth_range=[20, 50],
            )
            assert not np.any(np.asarray(r["pattern"]["y"]) > 1e-9), (
                supersampling,
                max(r["pattern"]["y"]),
            )
            assert not np.any(n.raster(r, "cake") > 1e-9)
        receipts.append(dict(case="opposite-sector exclusion", supersampling=[1, 2]))
        # Independent supersampled sector weights and Poisson propagation. Build
        # the point-to-bin matrix with pyFAI coordinates and NumPy, not native LUTs.
        pol = 0.5 * (1 + np.cos(g.tth(rows, cols)) ** 2)
        raw = pol * (700 + 3 * rows + 5 * cols)
        np.save(file, raw[::-1])
        n.call("open_image", path=str(file))
        r = n.call(
            "integration_settings",
            bins=80,
            solid_angle=False,
            polarization=0,
            supersampling=2,
            poisson_errors=True,
            azimuth_range=[20, 50],
        )
        axis = np.asarray(r["pattern"]["x"])
        step = axis[1] - axis[0]
        edge = axis[0] - 0.5 * step
        weights = np.zeros((len(axis), raw.size))
        for dy in (0.25, 0.75):
            for dx in (0.25, 0.75):
                radial = np.degrees(g.tth(rows + dy - 0.5, cols + dx - 0.5)).ravel()
                angular = np.degrees(g.chi(rows + dy - 0.5, cols + dx - 0.5)).ravel()
                selected = (angular >= 20) & (angular < 50)
                bins = np.clip(
                    np.floor((radial - edge) / step).astype(int), 0, len(axis) - 1
                )
                np.add.at(weights, (bins[selected], np.flatnonzero(selected)), 0.25)
        denominator = weights @ pol.ravel()
        signal = weights @ raw.ravel()
        expected = np.divide(
            signal, denominator, out=np.zeros_like(signal), where=denominator > 0
        )
        sigma = np.divide(
            np.sqrt((weights**2) @ raw.ravel()),
            denominator,
            out=np.zeros_like(signal),
            where=denominator > 0,
        )
        np.testing.assert_allclose(r["pattern"]["y"], expected, rtol=3e-12, atol=1e-9)
        np.testing.assert_allclose(r["pattern"]["sigma"], sigma, rtol=3e-12, atol=1e-9)
        receipts.append(
            dict(case="independent NumPy sector weights and Poisson", supersampling=2)
        )
    output = ROOT / "desktop/artifacts/native-integration"
    output.mkdir(parents=True, exist_ok=True)
    (output / "core-parity.json").write_text(json.dumps(receipts, indent=2) + "\n")
    print(json.dumps(receipts, indent=2))


if __name__ == "__main__":
    main()
