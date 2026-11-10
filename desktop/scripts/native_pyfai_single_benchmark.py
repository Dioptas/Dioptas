"""Matched single-image pyFAI timing and exact preserved-executable comparison.

Use the native stdio/binary-raster contract, including the GUI's buffer cache.
Numerical checks and hashes run outside timed command intervals.
"""

import argparse
from contextlib import ExitStack
import hashlib
import json
import os
import platform
import statistics
import struct
import threading
import time
from pathlib import Path

os.environ["HDF5_PLUGIN_PRELOAD"] = "::"
import h5py
import numpy as np
import native_reference_client as client
from native_pyfai_series_benchmark import cpu_context, busy


class CachedNative(client.Native):
    def __init__(self, env=None):
        self.logs = []
        super().__init__(env)
        self.drainer = threading.Thread(target=self.drain, daemon=True)
        self.drainer.start()

    def drain(self):
        for line in self.child.stderr:
            self.logs.append(line.decode())

    def invoke(self, command_name, **payload):
        self.id += 1
        self.child.stdin.write(
            (
                json.dumps(
                    dict(
                        id=self.id,
                        action=command_name,
                        payload=payload,
                        cachedBuffers=list(self.buffers),
                    )
                )
                + "\n"
            ).encode()
        )
        self.child.stdin.flush()
        (size,) = struct.unpack("<I", client.exact(self.child.stdout, 4))
        header = json.loads(client.exact(self.child.stdout, size))
        assert header["id"] == self.id
        for b in header["buffers"]:
            self.buffers[b["id"]] = bytes(client.exact(self.child.stdout, b["length"]))
        result = header["result"]
        # Keep only the buffers referenced by the current response, as the GUI
        # does; do not retain all 625 detector images in this test driver.
        keep = set()

        def visit(value):
            if isinstance(value, dict):
                if "bufferId" in value:
                    keep.add(value["bufferId"])
                for v in value.values():
                    visit(v)
            elif isinstance(value, list):
                for v in value:
                    visit(v)

        visit(result)
        self.buffers = {k: v for k, v in self.buffers.items() if k in keep}
        return result

    def close(self):
        self.child.stdin.close()
        self.child.wait(timeout=10)
        self.drainer.join(timeout=5)
        assert self.child.returncode == 0, "".join(self.logs)


def signature(n, result):
    output = {}
    pattern = result.get("pattern")
    if pattern:
        for key in ("x", "y", "sigma", "azimuthalStd"):
            value = pattern.get(key)
            output[key] = (
                None
                if value is None
                else hashlib.sha256(
                    np.asarray(value, dtype="<f8").tobytes()
                ).hexdigest()
            )
    for key in ("rawImage", "image", "mask", "cake"):
        raster = result.get(key)
        if raster and "bufferId" in raster:
            output[key] = hashlib.sha256(n.buffers[raster["bufferId"]]).hexdigest()
            output[key + "Metadata"] = {
                k: v for k, v in raster.items() if k != "bufferId"
            }
    return output


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source", type=Path, required=True)
    p.add_argument("--before", type=Path, required=True)
    p.add_argument("--after", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--repeats", type=int, default=2)
    p.add_argument("--frames", type=int, default=625)
    p.add_argument("--integration-repeats", type=int, default=100)
    p.add_argument("--wait-idle", action="store_true")
    p.add_argument(
        "--variants",
        nargs="+",
        choices=["before", "after"],
        default=["before", "after"],
    )
    args = p.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    source_stat = args.source.stat()
    with h5py.File(args.source) as f:
        shape = list(f["entry_0000/instrument/eiger/data"].shape)
    frames = list(
        dict.fromkeys(np.linspace(0, shape[0] - 1, args.frames, dtype=int).tolist())
    )
    report = dict(
        source=str(args.source),
        shape=shape,
        bins=2000,
        threads=8,
        method="pyfai_full",
        residentLayout="csr",
        masks="automatic acquisition mask",
        corrections="none",
        cake=False,
        rings=False,
        frames=frames,
        machine=platform.platform(),
        scope="Warm-plan single-image commands over native stdio with cached buffers; includes requested display pixels and packet transfer. No GUI rendering or physical scanout. OS pages warm; external CPU context recorded.",
        executables={
            v: dict(
                path=str(path), sha256=hashlib.sha256(path.read_bytes()).hexdigest()
            )
            for v, path in [("before", args.before), ("after", args.after)]
        },
        records=[],
        initial=[],
        signatures={},
        summaries=[],
    )

    def save():
        (args.output / "results.json").write_text(json.dumps(report, indent=2) + "\n")

    report["pairedInterleaving"] = True
    for repeat in range(args.repeats):
        for poisson in [False, True]:
            with ExitStack() as stack:
                natives, results, before = {}, {}, {}
                for variant in args.variants:
                    client.EXECUTABLE = (
                        args.before if variant == "before" else args.after
                    )
                    n = stack.enter_context(
                        CachedNative(
                            {
                                "DIOPTAS_INTEGRATION_THREADS": "8",
                                "RAYON_NUM_THREADS": "8",
                            }
                        )
                    )
                    natives[variant] = n

                    def call(action, n=n, **kw):
                        return n.call(
                            action,
                            requested_products=dict(cake=False, rings=False),
                            **kw,
                        )

                    call(
                        "integration_settings",
                        bins=2000,
                        cake_bins=90,
                        trim_zeros=False,
                        method="pyfai_full",
                        sparse_layout="csr",
                        poisson_errors=poisson,
                        polarization=0.965,
                    )
                    call("open_calibration", path=str(args.source.with_suffix(".poni")))
                    started = time.perf_counter()
                    result = call("open_image", path=str(args.source))
                    report["initial"].append(
                        dict(
                            repeat=repeat,
                            poisson=poisson,
                            variant=variant,
                            seconds=time.perf_counter() - started,
                            elapsedMs=result["state"]["elapsedMs"],
                        )
                    )
                    results[variant] = result
                pids = {n.child.pid for n in natives.values()}

                def context():
                    return [p for p in cpu_context(-1) if p["pid"] not in pids]

                for mode in ["load-integrate", "integrate", "load-only"]:
                    if args.wait_idle:
                        idle_started = time.perf_counter()
                        while True:
                            if not busy(context()):
                                time.sleep(1)
                                if not busy(context()):
                                    break
                            if time.perf_counter() - idle_started > 180:
                                raise RuntimeError(
                                    f"Unrelated CPU work did not settle: {context()}"
                                )
                            time.sleep(2)
                    cpu_before = context()
                    rows = {v: [] for v in args.variants}
                    for variant, n in natives.items():
                        before[variant] = n.call("integration_diagnostics")[
                            "integrationDiagnostics"
                        ]
                    indices = (
                        frames
                        if mode == "load-integrate"
                        else (
                            [frames[-1]] * args.integration_repeats
                            if mode == "integrate"
                            else frames[:: max(1, len(frames) // 25)]
                        )
                    )
                    for i, frame in enumerate(indices):
                        order = (
                            args.variants
                            if (i + repeat) % 2 == 0
                            else list(reversed(args.variants))
                        )
                        for variant in order:
                            n = natives[variant]
                            current = (
                                results[variant]
                                .get("nativeSource", {})
                                .get("frame", frame)
                            )
                            if mode == "integrate":
                                action, kw = "integrate", {}
                            elif i == 0 or current == frame:
                                action, kw = (
                                    "open_image",
                                    dict(path=str(args.source), frame=frame),
                                )
                            else:
                                action, kw = (
                                    "next_image",
                                    dict(
                                        direction=1 if frame > current else -1,
                                        step=abs(frame - current),
                                    ),
                                )
                            if mode == "load-only":
                                kw["defer_integration"] = True
                            started = time.perf_counter()
                            result = n.call(
                                action,
                                requested_products=dict(cake=False, rings=False),
                                **kw,
                            )
                            elapsed = time.perf_counter() - started
                            results[variant] = result
                            rows[variant].append(
                                dict(
                                    frame=frame,
                                    action=action,
                                    seconds=elapsed,
                                    elapsedMs=result["state"]["elapsedMs"],
                                )
                            )
                            key = f"{mode}:{int(poisson)}:{frame}"
                            sig = signature(n, result)
                            if key not in report["signatures"]:
                                report["signatures"][key] = sig
                            assert report["signatures"][key] == sig, (
                                variant,
                                repeat,
                                key,
                            )
                        if mode == "load-integrate" and i % 125 == 0:
                            print(
                                json.dumps(
                                    dict(
                                        repeat=repeat,
                                        poisson=poisson,
                                        mode=mode,
                                        frame=frame,
                                    )
                                ),
                                flush=True,
                            )
                    cpu_after = context()
                    for variant, n in natives.items():
                        after = n.call("integration_diagnostics")[
                            "integrationDiagnostics"
                        ]
                        record = dict(
                            repeat=repeat,
                            variant=variant,
                            poisson=poisson,
                            mode=mode,
                            rows=rows[variant],
                            medianMs=statistics.median(
                                r["seconds"] * 1000 for r in rows[variant]
                            ),
                            medianIntegrationMs=statistics.median(
                                r["elapsedMs"] for r in rows[variant]
                            )
                            if mode != "load-only"
                            else None,
                            cpuBefore=cpu_before,
                            cpuAfter=cpu_after,
                            externalBusy=busy(cpu_before) or busy(cpu_after),
                            diagnosticsDelta={
                                k: after[k] - before[variant].get(k, 0) for k in after
                            },
                        )
                        report["records"].append(record)
                        print(
                            json.dumps(
                                {k: v for k, v in record.items() if k != "rows"}
                            ),
                            flush=True,
                        )
                    save()
    for mode in ["load-integrate", "integrate", "load-only"]:
        for poisson in [False, True]:
            values = {
                v: [
                    row
                    for r in report["records"]
                    if r["mode"] == mode
                    and r["poisson"] == poisson
                    and r["variant"] == v
                    for row in r["rows"]
                ]
                for v in args.variants
            }
            report["summaries"].append(
                dict(
                    mode=mode,
                    poisson=poisson,
                    medianMs={
                        v: statistics.median(r["seconds"] * 1000 for r in rows)
                        for v, rows in values.items()
                    },
                    medianIntegrationMs={
                        v: statistics.median(r["elapsedMs"] for r in rows)
                        if mode != "load-only"
                        else None
                        for v, rows in values.items()
                    },
                )
            )
    report["bitwiseEqual"] = True
    report["sourceUnchanged"] = (source_stat.st_size, source_stat.st_mtime_ns) == (
        args.source.stat().st_size,
        args.source.stat().st_mtime_ns,
    )
    assert report["sourceUnchanged"]
    save()
    print(json.dumps(report["summaries"], indent=2), flush=True)


if __name__ == "__main__":
    main()
