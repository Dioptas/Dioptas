"""Test-only binary stdio client; its Rust child cannot execute Python."""

import json
import os
import struct
import subprocess
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
EXECUTABLE = Path(os.environ.get("DIOPTAS_NATIVE_PROCESSOR", str(
    ROOT
    / "desktop/backend/target/debug"
    / ("dioptas-processor.exe" if os.name == "nt" else "dioptas-processor")
)))
PROCESSOR_ARGUMENTS = (["--resource-dir", os.environ["DIOPTAS_RESOURCE_DIR"]]
                       if "DIOPTAS_RESOURCE_DIR" in os.environ
                       else ["--source-root", str(ROOT)])


def exact(stream, size):
    out = bytearray()
    while len(out) < size:
        data = stream.read(size - len(out))
        if not data:
            raise RuntimeError("Native worker closed its pipe")
        out.extend(data)
    return out


class Native:
    def __init__(self, env=None, require_engine=True):
        self.child = subprocess.Popen(
            [str(EXECUTABLE), *PROCESSOR_ARGUMENTS],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env={
                **os.environ,
                **(env or {}),
                "PATH": "/nonexistent",
                "DIOPTAS_PYTHON": "/nonexistent/python",
            },
        )
        self.id = 0
        self.buffers = {}
        if require_engine:
            host = self.call("__host__")
            if host.get("engine") != "dioptrin":
                self.close()
                raise RuntimeError(
                    "Build desktop/backend with --all-features before running numerical reference checks"
                )

    def invoke(self, command_name, **payload):
        self.id += 1
        self.child.stdin.write(
            (
                json.dumps(dict(id=self.id, action=command_name, payload=payload))
                + "\n"
            ).encode()
        )
        self.child.stdin.flush()
        (size,) = struct.unpack("<I", exact(self.child.stdout, 4))
        header = json.loads(exact(self.child.stdout, size))
        assert header["id"] == self.id
        for b in header["buffers"]:
            self.buffers[b["id"]] = bytes(exact(self.child.stdout, b["length"]))
        return header["result"]

    def call(self, command_name, **payload):
        result = self.invoke(command_name, **payload)
        assert result["ok"], (command_name, result)
        return result

    def raster(self, result, key):
        r = result[key]
        dtype = {"u8": "u1", "f32le": "<f4"}[r["dtype"]]
        return np.frombuffer(self.buffers[r["bufferId"]], dtype).reshape(
            r["height"], r["width"]
        )

    def close(self):
        self.child.stdin.close()
        self.child.wait(timeout=10)
        assert self.child.returncode == 0, self.child.stderr.read().decode()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
