# SPDX-License-Identifier: MIT
"""Shared integration utilities for MapModel and BatchModel.

Provides frame generators and helpers that deduplicate the batch
integration logic shared between map and batch processing.
"""
from __future__ import annotations

import logging
import os
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import TYPE_CHECKING

import numpy as np
import numpy.typing as npt
import h5py

if TYPE_CHECKING:
    from dioptas.model.ImgModel import ImgModel
    from dioptas.model.MaskModel import MaskModel
    from dioptas.model.loader.hdf5Loader import Hdf5Image

logger = logging.getLogger(__name__)


def detect_fast_path(img_model: ImgModel) -> bool:
    """Check whether the img_model can bypass transformations/corrections.

    When True, raw frames from HDF5 bitshuffle parallel decompression can
    be fed directly to the integrator without applying the frame pipeline.
    """
    return (
        not img_model.img_transformations
        and img_model._background_data is None
        and not img_model._img_corrections.has_items()
        and img_model.factor == 1
    )


def try_open_bitshuffle_hdf5(filepath: str) -> Hdf5Image | None:
    """Try to open *filepath* as a bitshuffle-compressed HDF5.

    Returns an ``Hdf5Image`` instance if the file is a bitshuffle HDF5,
    otherwise returns ``None`` (closing any opened handle).
    """
    from dioptas.model.loader.hdf5Loader import Hdf5Image

    try:
        loader = Hdf5Image(filepath)
    except Exception:
        logger.debug("File %s is not a bitshuffle HDF5", filepath)
        return None

    if loader._is_bitshuffle:
        return loader

    loader.f.close()
    return None


def _apply_frame(
    img_model: ImgModel,
    raw_frame: npt.NDArray[np.float64],
    fast_path: bool,
) -> npt.NDArray[np.float64]:
    """Apply the img_model frame pipeline if *fast_path* is False."""
    if fast_path:
        return raw_frame
    return img_model._apply_frame_pipeline(raw_frame)


def _selected_reader(filepath, img_model):
    reader = try_open_bitshuffle_hdf5(filepath)
    if reader is None:
        return None
    source = getattr(img_model, 'selected_source', None)
    if (isinstance(source, str) and getattr(img_model, '_select_source', None) is not None
            and source in reader.image_sources):
        reader.select_source(source)
    elif len(reader.image_sources) > 1:
        # LImA/NeXus often exposes the SAME dataset through multiple hard links.
        # Resolve object identity, or the actual dataset selected by FabIO,
        # rather than treating equal shapes as sufficient evidence.
        image = getattr(getattr(img_model, 'loader', None), 'fabio_image', None)
        selected = getattr(image, 'dataset', None)
        matches = ([name for name in reader.image_sources if reader.f[name].id == selected.id]
                   if isinstance(selected, h5py.Dataset) else [])
        if matches:
            reader.select_source(matches[0])
        elif not all(reader.f[name].id == reader.dataset.id for name in reader.image_sources):
            reader.f.close()
            return None
    return reader


class _SeriesCursor:
    def __init__(self, reader, workers):
        self.reader = reader
        self.workers = workers
        self.iterator = None
        self.next_index = None
        self.last_index = None
        self.last_frame = None

    def get(self, index):
        if index < 0 or index >= self.reader.series_max:
            raise IndexError(index)
        if index == self.last_index:
            return self.last_frame
        if self.iterator is None or index != self.next_index:
            self.close()
            self.iterator = self.reader.gen_frames(
                decomp_workers=self.workers, start_frame=index
            )
        self.last_frame = next(self.iterator)
        self.last_index = index
        self.next_index = index + 1
        if self.next_index == self.reader.series_max:
            self.close()
        return self.last_frame

    def close(self):
        if self.iterator is not None:
            close = getattr(self.iterator, 'close', None)
            if close is not None:
                close()
            self.iterator = None


@contextmanager
def prefetch_series(img_model, workers=None):
    """Prefetch raw frames while keeping ImgModel corrections on the caller.

    Restore the original series callback and close files/workers on normal
    completion, cancellation and errors. Random/repeated selections remain
    valid and queued arrays retain independent ownership.
    """
    reader = _selected_reader(img_model.filename, img_model)
    if reader is None:
        yield
        return
    from dioptas.model.loader.hdf5Loader import _NUM_CPUS
    cursor = _SeriesCursor(reader, workers or _NUM_CPUS)
    original = img_model.series_get_image
    img_model.series_get_image = cursor.get
    try:
        yield
    finally:
        img_model.series_get_image = original
        try:
            cursor.close()
        finally:
            reader.f.close()


def _open_file_frames(
    filepath: str,
    img_model: ImgModel,
    fast_path: bool,
    *,
    load: bool = False,
    workers: int | None = None,
) -> Iterator[npt.NDArray[np.float64]]:
    """Open a bounded raw-frame stream, retaining source selection/corrections."""
    if load:
        img_model.load(filepath)
    hdf5_loader = _selected_reader(filepath, img_model)
    if hdf5_loader is not None:
        def bitshuffle_gen():
            frames = hdf5_loader.gen_frames(
                **({'decomp_workers': workers} if workers is not None else {})
            )
            try:
                for raw in frames:
                    yield _apply_frame(img_model, raw, fast_path)
            finally:
                try:
                    close = getattr(frames, 'close', None)
                    if close is not None:
                        close()
                finally:
                    hdf5_loader.f.close()
        return bitshuffle_gen()

    if not load:
        img_model.load(filepath)

    def fallback_gen():
        for i in range(img_model.series_max):
            img_model.load_series_img(i + 1)
            yield img_model.get_img_data_float64()
    return fallback_gen()


def iter_frames_sequential(
    img_model: ImgModel,
    filepaths: list[str],
    *,
    img_shape: tuple[int, ...],
    abort_check: Callable[[], bool] | None = None,
    on_frame: Callable[[str, int], None] | None = None,
    workers: int | None = None,
) -> Iterator[npt.NDArray[np.float64]]:
    """Yield image frames from *filepaths* sequentially.

    Used by MapModel for map integration.  Tries bitshuffle HDF5 parallel
    decompression first, falls back to standard loading via ``img_model``.
    """
    fast_path = detect_fast_path(img_model)

    for filepath in filepaths:
        if abort_check and abort_check():
            return

        frame_iter = _open_file_frames(filepath, img_model, fast_path, workers=workers)

        try:
            for frame_ind, frame in enumerate(frame_iter):
                if abort_check and abort_check():
                    return
                if frame_ind == 0 and frame.shape != img_shape:
                    raise ValueError(
                        f"Image '{os.path.basename(filepath)}' has shape "
                        f"{frame.shape}, expected {img_shape}"
                    )
                if on_frame:
                    on_frame(filepath, frame_ind)
                yield frame
        finally:
            frame_iter.close()


def iter_frames_indexed(
    img_model: ImgModel,
    files: npt.NDArray | list[str],
    source: npt.NDArray,
    indices: list[int] | npt.NDArray[np.int_],
    *,
    mask_model: MaskModel | None = None,
    workers: int | None = None,
    abort_check: Callable[[], bool] | None = None,
) -> Iterator[npt.NDArray[np.float64]]:
    """Yield image frames at specific ``(file_index, frame_pos)`` positions.

    Used by BatchModel for batch integration with ``pos_map`` indexing.
    When a bitshuffle HDF5 is detected, uses parallel decompression with
    forward-seeking to the requested frame position.
    """
    fast_path: bool = detect_fast_path(img_model)
    current_file: str | int = ""
    frame_iter: Iterator[npt.NDArray[np.float64]] | None = None
    next_frame_pos: int = 0

    try:
        for index in indices:
            if abort_check and abort_check():
                return
            file_index, pos = source[index]
            if file_index != current_file or pos < next_frame_pos:
                if frame_iter is not None:
                    frame_iter.close()
                current_file = file_index
                frame_iter = _open_file_frames(
                    files[file_index], img_model, fast_path, load=True, workers=workers,
                )
                if mask_model is not None:
                    mask_model.set_dimension(img_model.img_data.shape)
                next_frame_pos = 0

            # Advance to requested position
            frame: npt.NDArray[np.float64] | None = None
            while next_frame_pos <= pos:
                frame = next(frame_iter)
                next_frame_pos += 1
            yield frame
    finally:
        if frame_iter is not None:
            frame_iter.close()


def convert_tth_to_d(
    tth_array: npt.NDArray[np.float64],
    wavelength: float,
) -> npt.NDArray[np.float64]:
    """Convert two-theta (degrees) to d-spacing (Angstrom)."""
    return wavelength / (2 * np.sin(tth_array / 360 * np.pi)) * 1e10
