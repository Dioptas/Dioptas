# SPDX-License-Identifier: MIT
"""Shared integration utilities for MapModel and BatchModel.

Provides frame generators and helpers that deduplicate the batch
integration logic shared between map and batch processing.
"""
from __future__ import annotations

import logging
import os

import numpy as np

logger = logging.getLogger(__name__)


def detect_fast_path(img_model) -> bool:
    """Check whether the img_model can bypass transformations/corrections.

    When True, raw frames from HDF5 bitshuffle parallel decompression can
    be fed directly to the integrator without applying the frame pipeline.
    """
    return (
        not img_model.img_transformations
        and img_model._background_data is None
        and not img_model._img_corrections.has_items()
        and img_model._factor == 1
    )


def try_open_bitshuffle_hdf5(filepath):
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


def _apply_frame(img_model, raw_frame, fast_path: bool):
    """Apply the img_model frame pipeline if *fast_path* is False."""
    if fast_path:
        return raw_frame
    return img_model._apply_frame_pipeline(raw_frame)


def _open_file_frames(filepath, img_model, fast_path, *, load=False):
    """Open *filepath* and return a generator yielding processed frames.

    Tries bitshuffle HDF5 parallel decompression first for fast frame
    iteration; falls back to ``img_model.load`` +
    ``img_model.load_series_img`` per frame.

    When *load* is True, ``img_model.load(filepath)`` is always called
    so that img_model state (img_data, series_max, etc.) reflects the
    file.  This is needed when callers rely on img_model metadata
    (e.g. for mask dimension).
    """
    hdf5_loader = try_open_bitshuffle_hdf5(filepath)
    if hdf5_loader is not None:
        if load:
            img_model.load(filepath)

        def bitshuffle_gen():
            for raw in hdf5_loader.gen_frames():
                yield _apply_frame(img_model, raw, fast_path)
        return bitshuffle_gen()

    # Fallback: always loads through img_model
    img_model.load(filepath)

    def fallback_gen():
        for i in range(img_model.series_max):
            img_model.load_series_img(i + 1)
            yield img_model.get_img_data_float64()
    return fallback_gen()


def iter_frames_sequential(img_model, filepaths, *, img_shape, abort_check=None, on_frame=None):
    """Yield image frames from *filepaths* sequentially.

    Used by MapModel for map integration.  Tries bitshuffle HDF5 parallel
    decompression first, falls back to standard loading via ``img_model``.

    Args:
        img_model: ImgModel instance for loading/processing frames.
        filepaths: list of file paths to iterate over.
        img_shape: expected image shape — raises ValueError on mismatch.
        abort_check: callable returning True when processing should stop.
        on_frame: ``on_frame(filepath, frame_index)`` called before each
            frame is yielded; use this to collect per-frame metadata.
    """
    fast_path = detect_fast_path(img_model)

    for filepath in filepaths:
        if abort_check and abort_check():
            return

        frame_iter = _open_file_frames(filepath, img_model, fast_path)

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


def iter_frames_indexed(img_model, files, source, indices, *, mask_model=None, abort_check=None):
    """Yield image frames at specific ``(file_index, frame_pos)`` positions.

    Used by BatchModel for batch integration with ``pos_map`` indexing.
    When a bitshuffle HDF5 is detected, uses parallel decompression with
    forward-seeking to the requested frame position.

    Args:
        img_model: ImgModel instance for loading/processing frames.
        files: array of file paths (indexed by ``file_index``).
        source: position-map array of ``(file_index, frame_pos)`` entries.
        indices: list of indices into *source* to process.
        mask_model: optional MaskModel — its dimension is updated on file change.
        abort_check: callable returning True when processing should stop.
    """
    fast_path = detect_fast_path(img_model)
    current_file = ""
    frame_iter = None
    next_frame_pos = 0

    for index in indices:
        if abort_check and abort_check():
            return
        file_index, pos = source[index]
        if file_index != current_file:
            current_file = file_index
            frame_iter = _open_file_frames(
                files[file_index], img_model, fast_path, load=True,
            )
            if mask_model is not None:
                mask_model.set_dimension(img_model.img_data.shape)
            next_frame_pos = 0

        # Advance to requested position
        frame = None
        while next_frame_pos <= pos:
            frame = next(frame_iter)
            next_frame_pos += 1
        yield frame


def convert_tth_to_d(tth_array, wavelength):
    """Convert two-theta (degrees) to d-spacing (Angstrom)."""
    return wavelength / (2 * np.sin(tth_array / 360 * np.pi)) * 1e10
