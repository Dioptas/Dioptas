# SPDX-License-Identifier: MIT

import logging
import os
import struct
from collections import deque
from concurrent.futures import ThreadPoolExecutor

import h5py
import hdf5plugin
import numpy as np

try:
    import bitshuffle

    HAS_BITSHUFFLE = True
except ImportError:
    HAS_BITSHUFFLE = False

logger = logging.getLogger(__name__)

BITSHUFFLE_FILTER_ID = 32008
_NUM_CPUS = max((os.cpu_count() or 4) - 1, 1)


def _decompress_bitshuffle_lz4(raw_bytes, shape, dtype):
    """Decompress a single bitshuffle-LZ4 compressed chunk and return as
    contiguous float64 with vertical flip applied.

    This runs inside a thread pool worker so the flip + type conversion
    happen in parallel across frames.
    """
    block_size = struct.unpack(">I", raw_bytes[8:12])[0]
    buf = np.frombuffer(raw_bytes, dtype=np.uint8, offset=12)
    frame = bitshuffle.decompress_lz4(buf, shape, dtype, block_size)
    return np.ascontiguousarray(frame[::-1], dtype=np.float64)


def _is_bitshuffle_compressed(dataset):
    """Check if an HDF5 dataset uses bitshuffle compression."""
    if not HAS_BITSHUFFLE:
        return False
    try:
        plist = dataset.id.get_create_plist()
        n_filters = plist.get_nfilters()
        for i in range(n_filters):
            filter_info = plist.get_filter(i)
            if filter_info[0] == BITSHUFFLE_FILTER_ID:
                return True
    except Exception:
        pass
    return False


class Hdf5Image:
    def __init__(self, filename):
        """
        Loads an Hdf5 image produced by ESRF
        :param filename: path to the hdf5 file to be loaded
        """

        self.filename = filename
        self.f = h5py.File(filename, "r")
        self.image_sources = find_image_sources(self.f)

        self.dataset = self.f[self.image_sources[0]]
        self.series_max = self.dataset.shape[0]
        self._is_bitshuffle = _is_bitshuffle_compressed(self.dataset)

    def get_image(self, ind):
        return self.dataset[ind][::-1]

    def select_source(self, source):
        self.dataset = self.f[source]
        self.series_max = self.dataset.shape[0]
        self._is_bitshuffle = _is_bitshuffle_compressed(self.dataset)

    def gen_frames(self, n_frames=None, decomp_workers=_NUM_CPUS):
        """Generator yielding all frames as contiguous float64 arrays.

        For bitshuffle-compressed datasets, decompression, vertical flip, and
        float64 conversion all happen in parallel worker threads.  For other
        datasets, frames are read sequentially through h5py.

        :param n_frames: number of frames to yield (default: all)
        :param decomp_workers: number of parallel decompression threads
        """
        n = self.series_max if n_frames is None else min(n_frames, self.series_max)

        if self._is_bitshuffle:
            yield from self._gen_frames_parallel(n, decomp_workers)
        else:
            for i in range(n):
                yield np.ascontiguousarray(
                    self.dataset[i][::-1], dtype=np.float64
                )

    def _gen_frames_parallel(self, n_frames, decomp_workers=_NUM_CPUS):
        """Read raw chunks and decompress bitshuffle-LZ4 in parallel threads.

        Each worker decompresses a chunk, applies the vertical flip, and
        converts to contiguous float64.  A sliding window of at most
        *decomp_workers* in-flight futures limits memory usage and CPU
        contention with downstream integration threads.
        """
        ds = self.dataset
        dtype = ds.dtype
        chunk_shape = ds.chunks
        frame_shape = chunk_shape[1:]

        # Verify each frame is a single chunk (required for read_direct_chunk)
        if chunk_shape[1:] != ds.shape[1:]:
            raise ValueError(
                f"Spatial chunking detected: chunk_shape={chunk_shape}, "
                f"dataset_shape={ds.shape}. Parallel bitshuffle "
                f"decompression requires one chunk per frame."
            )

        with ThreadPoolExecutor(max_workers=decomp_workers) as pool:
            pending = deque()
            idx = 0

            # Fill initial window
            while idx < n_frames and len(pending) < decomp_workers:
                raw = bytes(ds.id.read_direct_chunk((idx, 0, 0))[1])
                pending.append(
                    pool.submit(
                        _decompress_bitshuffle_lz4, raw, frame_shape, dtype
                    )
                )
                idx += 1

            # Yield results and refill window one-for-one
            while pending:
                yield pending.popleft().result()
                if idx < n_frames:
                    raw = bytes(ds.id.read_direct_chunk((idx, 0, 0))[1])
                    pending.append(
                        pool.submit(
                            _decompress_bitshuffle_lz4, raw, frame_shape, dtype
                        )
                    )
                    idx += 1


def find_image_sources(hd5_file):
    image_paths = []

    def traverse_groups(group, parent_path=""):
        if isinstance(group, h5py.Dataset):
            if len(group.shape) >= 3:
                image_paths.append(parent_path)
        else:  # node is a group
            for key in group.keys():
                traverse_groups(group[key], parent_path + "/" + key)

    traverse_groups(hd5_file)

    return image_paths
