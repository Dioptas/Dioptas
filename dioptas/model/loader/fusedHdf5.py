# SPDX-License-Identifier: MIT
"""Immutable source descriptors for opt-in, single-frame native integration."""
from dataclasses import dataclass
import os

import h5py

from ..util.integration import detect_fast_path


def file_identity(path):
    stat = os.stat(path)
    return stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns


@dataclass(frozen=True)
class FusedHdf5Source:
    filename: str
    dataset: str
    frame: int
    identity: tuple[int, int, int, int]

    def check(self):
        if file_identity(self.filename) != self.identity:
            raise OSError("HDF5 source changed since the image was loaded; reopen it")


def describe_fused_source(img_model):
    """Capture the selected dataset, never infer it from a name or equal shapes.

    Only unchanged self-contained, full-frame Bitshuffle/LZ4 uint16/32 sources
    qualify. The native reader repeats admission and validates all chunk framing.
    Native integration also checks every count against the captured GUI image.
    """
    if not detect_fast_path(img_model):
        return None
    loader = img_model.loader
    if loader is None or img_model.series_get_image != getattr(loader, "get_image", None):
        return None
    image = getattr(loader, "fabio_image", loader)
    dataset = getattr(image, "dataset", None)
    if not isinstance(dataset, h5py.Dataset):
        return None
    try:
        path = os.path.abspath(img_model.filename)
        if (os.path.realpath(dataset.file.filename) != os.path.realpath(path)
                or dataset.is_virtual or len(dataset.shape) != 3
                or dataset.chunks != (1, *dataset.shape[1:])
                or dataset.dtype.kind != "u" or dataset.dtype.itemsize not in (2, 4)
                or not dataset.dtype.isnative
                or tuple(img_model.raw_img_data.shape) != dataset.shape[1:]):
            return None
        properties = dataset.id.get_create_plist()
        if properties.get_nfilters() != 1:
            return None
        codec, _, parameters, _ = properties.get_filter(0)
        if codec != 32008 or len(parameters) < 5 or parameters[4] != 2:
            return None
        frame = img_model.series_pos - 1
        if frame < 0 or frame >= dataset.shape[0]:
            return None
        identity = file_identity(path)
        if identity != img_model._loaded_file_signature:
            return None
        return FusedHdf5Source(path, dataset.name, frame, identity)
    except (OSError, ValueError, RuntimeError):
        return None
