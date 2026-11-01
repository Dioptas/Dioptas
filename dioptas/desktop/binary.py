# SPDX-License-Identifier: MIT
"""Small JSON headers followed by raw, immutable raster buffers (no sockets).

The native pipe and Tauri IPC use the same frame: little-endian uint32 header
length, UTF-8 JSON header, then the buffers listed in that header. A caller
advertises only buffers it still holds; those need not cross either boundary.
"""

from collections import OrderedDict
import hashlib
import json
import struct

import numpy as np


class RasterCache:
    """Cache immutable displays by content, detecting in-place array edits."""

    def __init__(self, max_bytes=128 * 1024 * 1024):
        self.max_bytes = max_bytes
        self.size = 0
        self.entries = OrderedDict()

    def raster(self, array, build, **options):
        source = np.ascontiguousarray(array)
        digest = hashlib.sha256(memoryview(source).cast("B")).hexdigest()
        key = (source.shape, source.dtype.str, digest, tuple(sorted(options.items())))
        cached = self.entries.get(key)
        if cached is not None:
            self.entries.move_to_end(key)
            return dict(cached)
        result = build(array, **options)
        data = result["data"]
        result["bufferId"] = hashlib.sha256(data).hexdigest()
        if len(data) <= self.max_bytes:
            self.entries[key] = result
            self.size += len(data)
            while self.size > self.max_bytes or len(self.entries) > 64:
                _, old = self.entries.popitem(last=False)
                self.size -= len(old["data"])
        return dict(result)


def encode_frame(identifier, result, known_buffers=()):
    buffers = {}
    known = set(known_buffers)

    def metadata(value):
        if isinstance(value, dict):
            if isinstance(value.get("data"), bytes) and "bufferId" in value:
                identity = value["bufferId"]
                if identity not in known:
                    buffers[identity] = value["data"]
                return {k: metadata(v) for k, v in value.items() if k != "data"}
            return {k: metadata(v) for k, v in value.items()}
        if isinstance(value, (tuple, list)):
            return [metadata(v) for v in value]
        return value

    header = json.dumps({
        "id": identifier, "result": metadata(result),
        "buffers": [{"id": key, "length": len(data)} for key, data in buffers.items()],
    }, allow_nan=False, separators=(",", ":")).encode("utf-8")
    # Return segments so Python need not copy large buffers into another frame.
    return (struct.pack("<I", len(header)), header, *buffers.values())
