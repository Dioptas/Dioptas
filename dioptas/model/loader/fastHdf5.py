# SPDX-License-Identifier: MIT
"""Indexed bitshuffle/LZ4 decoding with bounded, independently owned frames.

HDF5 is used for discovery/indexing, never for decompression on this path.
Sources are treated as immutable for one iterator; changed files fail explicitly.
"""
from __future__ import annotations

import os
import struct
import threading

import numpy as np

try:
    import bslz4_to_sparse as _codec
except (ImportError, OSError):
    _codec = None


class UnsupportedFastLayout(ValueError):
    """The ordinary HDF5 reader must handle this layout instead."""


def _identity(stat):
    return stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns


class FastChunkReader:
    """One immutable index, reusable typed decoder workspace per worker."""

    def __init__(self, dataset, source_filename=None):
        if _codec is None or not hasattr(_codec, 'decompress_from_buffer'):
            raise UnsupportedFastLayout('fast decoder is unavailable')
        self.shape = dataset.shape
        self.dtype = dataset.dtype
        if (len(self.shape) != 3 or self.dtype.kind != 'u'
                or self.dtype.itemsize not in (2, 4) or not self.dtype.isnative
                or dataset.chunks != (1, *self.shape[1:])):
            raise UnsupportedFastLayout('requires native u16/u32, one complete frame per chunk')
        properties = dataset.id.get_create_plist()
        if properties.get_nfilters() != 1:
            raise UnsupportedFastLayout('requires only bitshuffle/LZ4')
        filter_id, _, parameters, _ = properties.get_filter(0)
        if filter_id != 32008 or len(parameters) < 5 or parameters[4] != 2:
            raise UnsupportedFastLayout('requires bitshuffle/LZ4')
        self.root_path = os.fspath(source_filename or dataset.file.filename)
        self.root_identity = _identity(os.stat(self.root_path))
        self.path = os.fspath(dataset.file.filename)
        self.identity = _identity(os.stat(self.path))
        chunks = [dataset.id.get_chunk_info_by_coord((i, 0, 0)) for i in range(self.shape[0])]
        if any(c.filter_mask or c.byte_offset is None or c.size < 12
               or c.byte_offset + c.size > self.identity[2] for c in chunks):
            raise UnsupportedFastLayout('requires allocated, filtered chunks within the source file')
        self.locations = [(c.byte_offset, c.size) for c in chunks]
        self.raw_bytes = int(np.prod(self.shape[1:])) * self.dtype.itemsize
        # Decoder payload cap; consumer queues/native integrators are additional.
        self.worker_bytes = self.raw_bytes + int(np.prod(self.shape[1:])) * 8 + max((c.size for c in chunks), default=0)
        self.local = threading.local()
        self.streams = []
        self.lock = threading.Lock()
        self.fd = os.open(self.path, os.O_RDONLY)
        if _identity(os.fstat(self.fd)) != self.identity:
            self.close()
            raise OSError('HDF5 source changed while preparing its chunk index')

    def check_source(self):
        if (_identity(os.fstat(self.fd)) != self.identity
                or _identity(os.stat(self.path)) != self.identity
                or _identity(os.stat(self.root_path)) != self.root_identity):
            raise OSError('HDF5 source changed during integration; reopen it before retrying')

    def read(self, index):
        self.check_source()
        offset, length = self.locations[index]
        if hasattr(os, 'pread'):
            encoded = os.pread(self.fd, length, offset)
        else:
            if not hasattr(self.local, 'stream'):
                self.local.stream = open(self.path, 'rb')
                with self.lock:
                    self.streams.append(self.local.stream)
            self.local.stream.seek(offset)
            encoded = self.local.stream.read(length)
        if len(encoded) != length or struct.unpack('>Q', encoded[:8])[0] != self.raw_bytes:
            raise OSError('Invalid or truncated bitshuffle frame')
        if not hasattr(self.local, 'pixels'):
            self.local.pixels = np.empty(self.shape[1:], self.dtype)
        _codec.decompress_from_buffer(
            encoded, np.array([0], np.int64), np.array([length], np.int64),
            self.dtype.type, out=self.local.pixels,
        )
        self.check_source()
        # Typed workspace is reused, but queued frames must own independent data
        # until their consumers finish. Convert/flip exactly once here.
        return np.ascontiguousarray(self.local.pixels[::-1], dtype=np.float64)

    def close(self):
        for stream in self.streams:
            stream.close()
        self.streams.clear()
        if getattr(self, 'fd', None) is not None:
            os.close(self.fd)
            self.fd = None
