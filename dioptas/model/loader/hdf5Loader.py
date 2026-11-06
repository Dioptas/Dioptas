# SPDX-License-Identifier: MIT

import logging
import os
import struct
from collections import deque
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor

import h5py
import hdf5plugin
import numpy as np
import numpy.typing as npt

try:
    import bitshuffle

    HAS_BITSHUFFLE = True
except ImportError:
    HAS_BITSHUFFLE = False

logger = logging.getLogger(__name__)

BITSHUFFLE_FILTER_ID = 32008
_NUM_CPUS: int = min(max((os.cpu_count() or 4) - 1, 1), 8)


class Hdf5ExternalLinkError(RuntimeError):
    """Raised when an HDF5 file contains an external link that cannot open."""

    def __init__(
        self,
        source_filename: str,
        link_filename: str,
        link_path: str,
    ) -> None:
        source_filename = os.path.abspath(source_filename)
        if os.path.isabs(link_filename):
            resolved_filename = link_filename
        else:
            resolved_filename = os.path.join(
                os.path.dirname(source_filename), link_filename
            )

        source_basename = os.path.basename(source_filename)
        if not os.path.isfile(resolved_filename):
            message = (
                f'Could not load "{source_basename}": its image data is stored '
                "in an external HDF5 companion file that is missing:\n"
                f'"{resolved_filename}"\n\n'
                "Copy the companion data file to that location and try again."
            )
        else:
            message = (
                f'Could not load "{source_basename}": its external HDF5 data '
                f'file "{resolved_filename}" could not be opened at dataset '
                f'"{link_path}". The companion file may be damaged or may not '
                "contain the expected dataset."
            )

        super().__init__(message)


def _decompress_bitshuffle_lz4(
    raw_bytes: bytes,
    shape: tuple[int, ...],
    dtype: np.dtype,
) -> npt.NDArray[np.float64]:
    """Decompress a single bitshuffle-LZ4 compressed chunk and return as
    contiguous float64 with vertical flip applied.

    This runs inside a thread pool worker so the flip + type conversion
    happen in parallel across frames.
    """
    block_size_bytes = struct.unpack(">I", raw_bytes[8:12])[0]
    block_size = block_size_bytes // np.dtype(dtype).itemsize
    buf = np.frombuffer(raw_bytes, dtype=np.uint8, offset=12)
    frame = bitshuffle.decompress_lz4(buf, shape, dtype, block_size)
    return np.ascontiguousarray(frame[::-1], dtype=np.float64)


def _is_bitshuffle_compressed(dataset: h5py.Dataset) -> bool:
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
        logger.debug("Could not check bitshuffle filter for dataset")
    return False


class Hdf5Image:
    def __init__(self, filename: str) -> None:
        """Loads an Hdf5 image produced by ESRF."""
        self.filename: str = filename
        self.f: h5py.File = h5py.File(filename, "r")
        try:
            self.image_sources: list[str] = find_image_sources(self.f)
        except Exception:
            self.f.close()
            raise

        self.dataset: h5py.Dataset = self.f[self.image_sources[0]]
        self.series_max: int = self.dataset.shape[0]
        self._is_bitshuffle: bool = _is_bitshuffle_compressed(self.dataset)

    def get_image(self, ind: int) -> npt.NDArray:
        return self.dataset[ind][::-1]

    def select_source(self, source: str) -> None:
        self.dataset = self.f[source]
        self.series_max = self.dataset.shape[0]
        self._is_bitshuffle = _is_bitshuffle_compressed(self.dataset)

    def gen_frames(
        self,
        n_frames: int | None = None,
        decomp_workers: int = _NUM_CPUS,
        *,
        start_frame: int = 0,
    ) -> Iterator[npt.NDArray[np.float64]]:
        """Yield independently owned, bottom-up float64 frames in order.

        Prefer indexed fast decoding; retain the existing decoder/general HDF5
        fallback for unsupported layouts or an unavailable optional codec.
        Source mutation and decoding failures propagate rather than replaying
        already consumed frames through a different decoder.
        """
        from .fastHdf5 import FastChunkReader, UnsupportedFastLayout

        stop = self.series_max if n_frames is None else min(start_frame + n_frames, self.series_max)
        if start_frame < 0 or start_frame > stop or decomp_workers < 1:
            raise ValueError('Invalid frame range or decoder worker count')
        try:
            reader = FastChunkReader(self.dataset, source_filename=self.filename)
        except UnsupportedFastLayout:
            reader = None
        if reader is not None:
            # At most 2 GiB of decoder payload. Native integration queues and
            # masks are not included in this admission bound.
            workers = min(decomp_workers, 8, max(1, (2 << 30) // max(1, reader.worker_bytes)))
            if reader.worker_bytes > (2 << 30):
                reader.close()
                reader = None
            else:
                try:
                    with ThreadPoolExecutor(max_workers=workers) as pool:
                        pending: deque = deque()
                        indices = iter(range(start_frame, stop))
                        for _ in range(workers):
                            index = next(indices, None)
                            if index is not None:
                                pending.append(pool.submit(reader.read, index))
                        while pending:
                            yield pending.popleft().result()
                            index = next(indices, None)
                            if index is not None:
                                pending.append(pool.submit(reader.read, index))
                    reader.check_source()
                finally:
                    reader.close()
                return

        # The stock bitshuffle fast path only handles a single LZ4 filter and
        # complete spatial chunks. General HDF5 handles everything else.
        properties = self.dataset.id.get_create_plist()
        filters = [properties.get_filter(i) for i in range(properties.get_nfilters())]
        lz4 = (self._is_bitshuffle and len(filters) == 1 and len(filters[0][2]) >= 5
               and filters[0][2][4] == 2 and self.dataset.chunks == (1, *self.dataset.shape[1:]))
        if lz4:
            chunks = [self.dataset.id.get_chunk_info_by_coord((i, 0, 0)) for i in range(start_frame, stop)]
            lz4 = all(c.filter_mask == 0 and c.byte_offset is not None for c in chunks)
        if lz4:
            yield from self._gen_frames_parallel(stop, decomp_workers, start_frame=start_frame)
        else:
            for i in range(start_frame, stop):
                yield np.ascontiguousarray(self.get_image(i), dtype=np.float64)

    def _gen_frames_parallel(
        self,
        n_frames: int,
        decomp_workers: int = _NUM_CPUS,
        *,
        start_frame: int = 0,
    ) -> Iterator[npt.NDArray[np.float64]]:
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
            pending: deque = deque()
            idx: int = start_frame

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


def find_image_sources(hd5_file: h5py.File) -> list[str]:
    image_paths: list[str] = []

    def traverse_groups(group: h5py.File | h5py.Group | h5py.Dataset, parent_path: str = "") -> None:
        if isinstance(group, h5py.Dataset):
            if len(group.shape) >= 3:
                image_paths.append(parent_path)
        else:  # node is a group
            for key in group.keys():
                child_path = parent_path + "/" + key
                try:
                    child = group[key]
                except (KeyError, OSError) as error:
                    link = group.get(key, getlink=True)
                    if isinstance(link, h5py.ExternalLink):
                        raise Hdf5ExternalLinkError(
                            str(hd5_file.filename),
                            os.fsdecode(link.filename),
                            link.path,
                        ) from error
                    raise
                traverse_groups(child, child_path)

    traverse_groups(hd5_file)

    return image_paths
