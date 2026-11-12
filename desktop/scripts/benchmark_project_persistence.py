"""Release Rust project-save benchmark; Python only generates/checks fixtures.

Run with the checkout's reference CPython 3.13 environment. Scientific commands
and every .dio save/open execute in the real Rust processor over owned stdio.
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import struct
import subprocess
import time

import h5py
import numpy as np

ROOT = Path(__file__).resolve().parents[2]


def exact(stream, size):
    data = bytearray(size)
    view = memoryview(data)
    offset = 0
    while offset < size:
        count = stream.readinto(view[offset:])
        if not count:
            raise RuntimeError("Rust processor closed its response pipe")
        offset += count
    return bytes(data)


def raster_ids(value):
    if isinstance(value, dict):
        if isinstance(value.get("bufferId"), str):
            yield value["bufferId"]
        for child in value.values():
            yield from raster_ids(child)
    elif isinstance(value, list):
        for child in value:
            yield from raster_ids(child)


class Client:
    """Bounded buffer/product capabilities, with actual retained byte owners."""
    def __init__(self, executable, log):
        self.log = open(log, "wb")
        self.child = subprocess.Popen(
            [str(executable), "--source-root", str(ROOT)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self.log,
            env={**os.environ, "PATH": "/nonexistent", "DIOPTAS_PYTHON": "/nonexistent/python", "HDF5_PLUGIN_PRELOAD": "::"},
        )
        self.buffers = collections.OrderedDict()
        self.products = collections.OrderedDict()
        self.serial = 0
        self.last_transfer = None
        host, _ = self.call("__host__")
        assert host["runtime"] == "rust" and host["engine"] == "dioptrin", host

    def call(self, action, **payload):
        self.serial += 1
        known = dict(self.buffers)
        for product in self.products.values():
            known.update(product["buffers"])
        request = dict(id=self.serial, action=action, payload=payload,
                       cachedBuffers=list(known)[-64:],
                       cachedProducts={k: p["id"] for k, p in self.products.items()})
        started = time.perf_counter()
        self.child.stdin.write((json.dumps(request) + "\n").encode())
        self.child.stdin.flush()
        length, = struct.unpack("<I", exact(self.child.stdout, 4))
        header = json.loads(exact(self.child.stdout, length))
        assert header["id"] == self.serial
        binary = 0
        for item in header["buffers"]:
            data = exact(self.child.stdout, item["length"])
            binary += len(data)
            self.buffers.pop(item["id"], None)
            if len(data) <= 128 * 1024**2:
                self.buffers[item["id"]] = data
            while len(self.buffers) > 64 or sum(map(len, self.buffers.values())) > 128 * 1024**2:
                self.buffers.popitem(last=False)
        result = header["result"]
        assert result["ok"], (action, result)
        for field, descriptor in header.get("products", {}).items():
            if field not in result:
                old = self.products[field]
                assert (old["id"], old["bytes"]) == (descriptor["id"], descriptor["bytes"])
                result[field] = old["value"]
                continue
            owners = {key: self.buffers.get(key, known.get(key)) for key in set(raster_ids(result[field]))}
            assert all(value is not None for value in owners.values())
            cost = descriptor["bytes"] * 4 + sum(map(len, owners.values()))
            self.products.pop(field, None)
            if cost <= 64 * 1024**2:
                self.products[field] = dict(**descriptor, value=result[field], buffers=owners, cost=cost)
            while sum(p["cost"] for p in self.products.values()) > 64 * 1024**2:
                self.products.popitem(last=False)
        elapsed = time.perf_counter() - started
        self.last_transfer = dict(header_bytes=length, binary_bytes=binary)
        return result, elapsed

    def close(self):
        self.child.stdin.close()
        try:
            self.child.wait(timeout=30)
            assert self.child.returncode == 0
        finally:
            if self.child.poll() is None:
                self.child.kill()
                self.child.wait()
            self.log.close()


def digest_array(value):
    return hashlib.sha256(np.ascontiguousarray(value).tobytes()).hexdigest()


def manifest(path):
    """Read every numeric sample outside timing; hash bit patterns, not floats."""
    entries = {}
    with h5py.File(path, "r") as file:
        def visit(name, obj):
            if not isinstance(obj, h5py.Dataset) or obj.dtype.kind not in "biuf":
                return
            if name.endswith("desktop_metadata"):
                return  # JSON bytes are checked through loaded semantic state.
            digest = hashlib.sha256()
            if obj.ndim == 0:
                digest.update(np.asarray(obj[()]).tobytes())
            else:
                # ~4 MiB per slab, including large detector/series matrices.
                per_row = max(1, int(np.prod(obj.shape[1:])) * obj.dtype.itemsize)
                step = max(1, 4 * 1024**2 // per_row)
                for start in range(0, obj.shape[0], step):
                    digest.update(np.ascontiguousarray(obj[start:start + step]).tobytes())
            entries[name] = dict(shape=list(obj.shape), dtype=obj.dtype.str, sha256=digest.hexdigest())
        file.visititems(visit)
        pools = {name: len(file[name]) for name in ("cache", "payloads")}
    return dict(arrays=entries, pools=pools)


def state_signature(result):
    signature = {}
    if result.get("batch"):
        b = result["batch"]
        signature["batch"] = {key: b.get(key) for key in ("total", "selected", "normalized", "normalizationRange", "normalizationReference", "unit", "x", "pattern", "files", "entries")}
    if result.get("map"):
        m = result["map"]
        signature["map"] = {key: m.get(key) for key in ("points", "selected", "normalized", "normalizationRange", "normalizationReference", "unit", "values", "indices", "slots", "rois", "expressions", "active", "dimension", "displayShape", "snake", "transpose", "flip_horizontal", "flip_vertical", "excluded")}
    return signature


def seed(executable, directory, bins):
    native = Client(executable, directory / f"seed-{bins}.stderr.log")
    try:
        native.call("integration_settings", bins=bins, cake_bins=180, poisson_errors=True, trim_zeros=False)
        native.call("open_calibration", path=str(ROOT / "dioptas/tests/data/CeO2_Pilatus1M.poni"))
        result, _ = native.call("open_image", path=str(ROOT / "dioptas/tests/data/CeO2_Pilatus1M.tif"))
        x = np.asarray(result["pattern"]["x"], dtype=np.float64)
        y = np.asarray(result["pattern"]["y"], dtype=np.float64)
        # Missing edge bins are fixture preparation only, not a science fallback.
        good = np.isfinite(y)
        y = np.interp(np.arange(len(y)), np.flatnonzero(good), y[good])
        assert len(x) == bins and np.isfinite(x).all()
        return x, y
    finally:
        native.close()


def processed_fixture(path, points, x, base, layout):
    rng = np.random.default_rng(20261112)
    width = len(x)
    # Many realistic source entries, while distinguishing stacks from TIFF lists.
    stride = 500 if layout == "stack" else 1
    paths = [f"/benchmark/acquisition/scan_{i:05d}.{'h5' if layout == 'stack' else 'tif'}" for i in range((points + stride - 1) // stride)]
    data_digest, std_digest = hashlib.sha256(), hashlib.sha256()
    with h5py.File(path, "w") as file:
        result = file.create_group("processed/result")
        data = result.create_dataset("data", shape=(points, width), dtype="<f8")
        std = result.create_dataset("counting_std", shape=(points, width), dtype="<f8")
        axis = result.create_dataset("binning", data=x)
        axis.attrs["radial_unit"] = "2th_deg"
        result.attrs["desktop_wavelength_m"] = 4.066e-11
        grid = np.arange(width, dtype=np.float64)
        for first in range(0, points, 64):
            rows = np.arange(first, min(first + 64, points), dtype=np.float64)
            # Measured peak shapes with spatial/time scale, small peak shifts and noise.
            values = np.stack([np.interp(grid + 1.7 * np.sin(i / 301), grid, base) for i in rows])
            values *= (0.8 + 0.4 * (0.5 + 0.5 * np.sin(rows / 137)))[:, None]
            values += rng.normal(size=values.shape) * np.sqrt(np.maximum(values, 1)) * 0.03
            np.maximum(values, 0.001, out=values)
            sigmas = np.sqrt(values / 32)
            data[first:first + len(rows)] = values
            std[first:first + len(rows)] = sigmas
            data_digest.update(values.astype("<f8").tobytes())
            std_digest.update(sigmas.astype("<f8").tobytes())
        process = file.create_group("processed/process")
        process.create_dataset("files", data=np.asarray(paths, dtype=object), dtype=h5py.string_dtype())
        positions = np.column_stack([np.arange(points) // stride, np.arange(points) % stride])
        process.create_dataset("pos_map", data=positions)
        process.create_dataset("file_map", data=np.r_[np.arange(0, points, stride), points])
    return dict(shape=[points, width], source_files=len(paths), raw_sha256=data_digest.hexdigest(), std_sha256=std_digest.hexdigest())


def configure(native, kind, source, points, bins, rows, configs):
    native.call("integration_settings", bins=bins, cake_bins=180, poisson_errors=True, trim_zeros=False)
    native.call("open_calibration", path=str(ROOT / "dioptas/tests/data/CeO2_Pilatus1M.poni"))
    if kind in ("batch", "combined"):
        native.call("batch_open", path=str(source))
        native.call("batch_normalize", enabled=True, start=max(1, bins // 4), stop=3 * bins // 4, reference=points // 2 + 1)
        native.call("batch_select", index=points // 2)
    if kind in ("map", "combined"):
        native.call("map_batch", path=str(source))
        native.call("map_grid", rows=rows, columns=points // rows, snake=True)
        for index in range(6):
            name = chr(65 + index)
            if index:
                native.call("map_roi", op="add")
            native.call("map_roi", op="update", name=name,
                        minimum=2 + index * 3, maximum=7 + index * 3,
                        reduction="area", background=bool(index % 2))
        native.call("map_expression", name="Phase ratio", expression="A / (B + 1)")
        native.call("map_normalize", enabled=True, start=max(1, bins // 4), stop=3 * bins // 4, reference=points // 2 + 1)
        native.call("map_select", index=points // 2)
    # Keep a genuine full-resolution detector cache in every configuration too.
    native.call("open_image", path=str(ROOT / "dioptas/tests/data/CeO2_Pilatus1M.tif"))
    native.call("configuration", operation="rename", name="Large acquisition")
    for _ in range(1, configs):
        native.call("configuration", operation="duplicate")
    result, _ = native.call("state")
    return state_signature(result)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--processor", type=Path, default=ROOT / "desktop/backend/target/release/dioptas-processor")
    parser.add_argument("--cycles", type=int, default=8)
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--edit-cycles", type=int, default=4)
    args = parser.parse_args()
    directory = args.output.resolve()
    directory.mkdir(parents=True, exist_ok=True)
    cases = [("batch-stack", "batch", 10000, 2048, "stack", 100, 1),
             ("batch-tiffs", "batch", 10000, 2048, "tiff", 100, 1),
             ("map-stack", "map", 20000, 1024, "stack", 100, 1),
             ("map-tiffs", "map", 10000, 2048, "tiff", 100, 1),
             ("combined-two-config", "combined", 5000, 2048, "stack", 50, 2)]
    if args.smoke:
        cases = [("smoke-combined", "combined", 32, 128, "stack", 4, 2)]
    executable = args.processor.resolve()
    report = dict(source_head=subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
                  processor=str(executable), processor_sha256=hashlib.sha256(executable.read_bytes()).hexdigest(),
                  platform=platform.platform(), python=platform.python_version(),
                  cpu=subprocess.check_output(["sysctl", "-n", "machdep.cpu.brand_string"], text=True).strip(),
                  ram_bytes=int(subprocess.check_output(["sysctl", "-n", "hw.memsize"], text=True)),
                  hdf5_checker=h5py.version.hdf5_version, cycles=args.cycles,
                  benchmark_script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  edit_cycles=args.edit_cycles,
                  method="Release Rust stdio command latency, including response decode/cache; fsync+atomic publication; fresh Rust process per reopen; warm OS filesystem cache; no GUI/render timing; independent full numeric-array bit hashes outside timing",
                  fixture="Measured CeO2 Pilatus1M seed, generated varied profiles and counting std; representative volumes, not an actual 10k/20k-frame measured acquisition",
                  cases=[])
    seeds = {}
    for name, kind, points, bins, layout, rows, configs in cases:
        assert shutil.disk_usage(directory).free > 8 * 1024**3, "Less than 8 GiB free"
        if bins not in seeds:
            seeds[bins] = seed(executable, directory, bins)
        source = directory / f"{name}-input.h5"
        project = directory / f"{name}.dio"
        fixture = processed_fixture(source, points, *seeds[bins], layout)
        native = Client(executable, directory / f"{name}-initial.stderr.log")
        try:
            expected_state = configure(native, kind, source, points, bins, rows, configs)
            saved, elapsed = native.call("save_project", path=str(project))
            assert state_signature(saved) == expected_state
            cycles = [dict(cycle=0, save_seconds=elapsed, reopen_seconds=None,
                           bytes=project.stat().st_size, allocated_bytes=project.stat().st_blocks * 512, transfer=native.last_transfer)]
        finally:
            native.close()
        original = manifest(project)
        prefix = "native_batch" if kind == "batch" else "map/native_series"
        original_path = f"configurations/0/{prefix}/result/desktop_original"
        std_path = f"configurations/0/{prefix}/result/desktop_original_counting_std"
        assert original["arrays"][original_path]["sha256"] == fixture["raw_sha256"]
        assert original["arrays"][std_path]["sha256"] == fixture["std_sha256"]
        case = dict(name=name, kind=kind, configurations=configs, fixture=fixture,
                    map_grid=[rows, points // rows] if kind != "batch" else None,
                    input_bytes=source.stat().st_size, cycles=cycles,
                    numeric_datasets=len(original["arrays"]), numeric_manifest_sha256=hashlib.sha256(json.dumps(original, sort_keys=True).encode()).hexdigest())
        report["cases"].append(case)
        (directory / "results.json").write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(dict(case=name, **cycles[0])), flush=True)
        for cycle in range(1, args.cycles + 1):
            native = Client(executable, directory / f"{name}-{cycle}.stderr.log")
            try:
                reopened, open_time = native.call("open_project", path=str(project))
                assert state_signature(reopened) == expected_state, (name, cycle, "loaded semantic state")
                saved, elapsed = native.call("save_project", path=str(project))
                assert state_signature(saved) == expected_state
                entry = dict(cycle=cycle, save_seconds=elapsed, reopen_seconds=open_time,
                             bytes=project.stat().st_size, allocated_bytes=project.stat().st_blocks * 512, transfer=native.last_transfer)
            finally:
                native.close()
            current = manifest(project)
            assert current == original, (name, cycle, "numeric data or pool membership changed")
            cycles.append(entry)
            (directory / "results.json").write_text(json.dumps(report, indent=2) + "\n")
            print(json.dumps(dict(case=name, **entry)), flush=True)
        if kind == "combined" and args.edit_cycles:
            import fabio
            measured = np.asarray(fabio.open(ROOT / "dioptas/tests/data/CeO2_Pilatus1M.tif").data, dtype=np.float64)
            changed_image = directory / f"{name}-changed-detector.npy"
            expected_series = {key: value for key, value in original["arrays"].items() if "/native_batch/" in key or "/map/" in key}
            case["image_replacement_cycles"] = []
            for edit in range(1, args.edit_cycles + 1):
                np.save(changed_image, measured * (1 + 0.01 * edit))
                native = Client(executable, directory / f"{name}-edit-{edit}.stderr.log")
                try:
                    native.call("open_project", path=str(project))
                    native.call("open_image", path=str(changed_image))
                    native.call("configuration", operation="rename", name=f"Edited acquisition {edit:02d}")
                    _, save_time = native.call("save_project", path=str(project))
                finally:
                    native.close()
                edited = manifest(project)
                assert {key: value for key, value in edited["arrays"].items() if key in expected_series} == expected_series
                assert edited["pools"]["cache"] <= configs, edited["pools"]
                native = Client(executable, directory / f"{name}-edit-{edit}-reopen.stderr.log")
                try:
                    _, reopen_time = native.call("open_project", path=str(project))
                    _, resave_time = native.call("save_project", path=str(project))
                finally:
                    native.close()
                assert manifest(project) == edited, (name, edit, "edited data did not survive reopen/resave")
                entry = dict(edit=edit, save_seconds=save_time, reopen_seconds=reopen_time,
                             resave_seconds=resave_time, bytes=project.stat().st_size,
                             allocated_bytes=project.stat().st_blocks * 512, pools=edited["pools"])
                case["image_replacement_cycles"].append(entry)
                (directory / "results.json").write_text(json.dumps(report, indent=2) + "\n")
                print(json.dumps(dict(case=name, **entry)), flush=True)
        case["verified_every_cycle"] = True
        case["file_growth_bytes"] = cycles[-1]["bytes"] - cycles[0]["bytes"]
        case["file_spread_bytes"] = max(c["bytes"] for c in cycles) - min(c["bytes"] for c in cycles)
        (directory / "results.json").write_text(json.dumps(report, indent=2) + "\n")
    report["completed"] = True
    (directory / "results.json").write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
