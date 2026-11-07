"""Matched native navigation timings; independent compressed-chunk count reference.

Read-only, sampled qualification of the local 625-frame Eiger source. This does
not benchmark Qt or qualify named-detector loading or every detector format.
"""

import argparse, json, os, platform, statistics, struct, time

os.environ["HDF5_PLUGIN_PRELOAD"] = "::"
from pathlib import Path
import h5py, bitshuffle, numpy as np
from native_reference_client import Native, ROOT


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--source", type=Path, required=True)
    p.add_argument("--poni", type=Path, required=True)
    p.add_argument("--mask", type=Path, required=True)
    p.add_argument("--repeats", type=int, default=2)
    args = p.parse_args()
    params = {
        k.strip().lower(): v.strip()
        for line in args.poni.read_text().splitlines()
        if not line.startswith("#") and ":" in line
        for k, v in [line.split(":", 1)]
    }
    # Explicit manual, flat uniform grid in both paths. Named detector/orientation
    # handling is deliberately not inferred from these benchmark parameters.
    geometry = {
        key: float(params[key])
        for key in ("poni1", "poni2", "rot1", "rot2", "rot3", "wavelength")
    }
    geometry.update(
        dist=float(params["distance"]),
        pixel1=75e-6,
        pixel2=75e-6,
        polarization_factor=0.965,
    )
    dataset = "entry_0000/instrument/eiger/data"
    indices = [0, 312, 624]
    before = args.source.stat()
    references = {}
    with h5py.File(args.source) as f:
        d = f[dataset]
        shape = d.shape[1:]
        dtype = d.dtype
        for index in indices:
            flags, chunk = d.id.read_direct_chunk((index, 0, 0))
            assert flags == 0
            nbytes, block_bytes = struct.unpack(">QI", chunk[:12])
            assert nbytes == int(np.prod(shape)) * dtype.itemsize
            references[index] = bitshuffle.decompress_lz4(
                np.frombuffer(chunk[12:], dtype="u1"),
                shape,
                dtype,
                block_size=block_bytes // dtype.itemsize,
            )
    rows = []
    initial = []
    diagnostics = []
    patterns = {}
    for mode in ("resident", "combined"):
        with Native(
            {
                "DIOPTAS_COMBINED_HDF5": "0" if mode == "resident" else "1",
                "DIOPTAS_INTEGRATION_THREADS": "8",
            }
        ) as n:
            n.call("manual_geometry", convention="pyfai", values=geometry)
            n.call(
                "integration_settings",
                bins=2000,
                cake_bins=90,
                polarization=0.965,
                poisson_errors=False,
            )
            n.call(
                "open_image",
                path=str(args.source),
                dataset=dataset,
                defer_integration=True,
            )
            n.call("mask_file", path=str(args.mask), defer_integration=True)
            start = time.perf_counter()
            r = n.call("open_image", path=str(args.source), dataset=dataset, frame=0)
            initial.append(
                dict(
                    mode=mode,
                    seconds=time.perf_counter() - start,
                    scope="initial plan construction; compressed chunks already warmed",
                )
            )
            for errors in (False, True):
                n.call("integration_settings", poisson_errors=errors)
                for repeat in range(args.repeats):
                    for index in indices:
                        start = time.perf_counter()
                        r = n.call(
                            "open_image",
                            path=str(args.source),
                            dataset=dataset,
                            frame=index,
                        )
                        elapsed = time.perf_counter() - start
                        np.testing.assert_array_equal(
                            n.raster(r, "rawImage"),
                            references[index][::-1].astype(np.float32),
                        )
                        expected = references[index]
                        x, y = shape[1] // 2, shape[0] // 2
                        pixel = n.call("pixel", x=x, y=y, source="raw_detector")[
                            "pixel"
                        ]["value"]
                        assert pixel == int(expected[shape[0] - 1 - y, x])
                        assert r["nativeSource"]["ordinaryDecodes"] == (
                            1 if mode == "resident" else 0
                        )
                        key = (errors, index)
                        if mode == "resident":
                            patterns[key] = r["pattern"]
                        else:
                            np.testing.assert_allclose(
                                r["pattern"]["x"],
                                patterns[key]["x"],
                                rtol=2e-12,
                                atol=1e-10,
                            )
                            np.testing.assert_allclose(
                                r["pattern"]["y"],
                                patterns[key]["y"],
                                rtol=2e-12,
                                atol=1e-9,
                            )
                            if errors:
                                np.testing.assert_allclose(
                                    r["pattern"]["sigma"],
                                    patterns[key]["sigma"],
                                    rtol=2e-12,
                                    atol=1e-9,
                                )
                        rows.append(
                            dict(
                                mode=mode,
                                poisson=errors,
                                repeat=repeat,
                                frame=index,
                                seconds=elapsed,
                            )
                        )
            d = n.call("integration_diagnostics")["integrationDiagnostics"]
            assert d["patternPlanBuilds"] == d["cakePlanBuilds"] == 1
            diagnostics.append(dict(mode=mode, **d))
    summaries = []
    for errors in (False, True):
        times = {
            mode: statistics.median(
                r["seconds"]
                for r in rows
                if r["mode"] == mode and r["poisson"] == errors
            )
            for mode in ("resident", "combined")
        }
        summaries.append(
            dict(
                poisson=errors,
                median_seconds=times,
                relative_reduction=1 - times["combined"] / times["resident"],
            )
        )
    after = args.source.stat()
    assert (before.st_size, before.st_mtime_ns) == (after.st_size, after.st_mtime_ns)
    report = dict(
        scope="native stdio open→complete image/pattern/cake response; 3 of 625 frames; two sequential mode passes; OS compressed-page cache warm; processes not CPU-isolated; explicit 75 µm flat uniform manual geometry; no Qt or named-detector qualification",
        source=str(args.source),
        source_bytes=before.st_size,
        shape=list(shape),
        frames=indices,
        bins=2000,
        cake_bins=90,
        workers=8,
        platform=platform.platform(),
        profile="optimized development packages",
        initial=initial,
        timings=rows,
        summary=summaries,
        diagnostics=diagnostics,
        counts="sampled stored pixels exact after independent Bitshuffle decode and display orientation/float32 conversion; selected scientific f64 readouts exact",
        patterns="resident/combined f64 intensity and Poisson errors compared at 2e-12 relative, 1e-9 absolute",
    )
    out = ROOT / "desktop/artifacts/native-integration/eiger-benchmark.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + "\n")
    print(
        json.dumps(
            dict(summary=summaries, initial=initial, diagnostics=diagnostics), indent=2
        )
    )


if __name__ == "__main__":
    main()
