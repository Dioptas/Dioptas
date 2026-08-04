# SPDX-License-Identifier: MIT
"""Best-effort detection of what kind of file the user picked, used to build
clear error messages when a file cannot be loaded as the expected type
(e.g. a *.poni calibration selected in the image-loading dialog)."""

import os

# extensions typically produced by detectors / image writers
_IMAGE_EXTENSIONS = {
    ".tif", ".tiff", ".cbf", ".edf", ".mar345", ".mar2300", ".mar3450",
    ".mccd", ".img", ".sfrm", ".spe", ".h5", ".hdf5", ".nxs",
}

_PATTERN_EXTENSIONS = {".xy", ".chi", ".xye", ".fxye"}

# keys that appear at the start of lines in pyFAI *.poni files (old and new
# format)
_PONI_LINE_KEYS = (
    "poni1:", "poni2:", "distance:", "pixelsize1:", "pixelsize2:",
    "detector:", "detector_config:", "wavelength:", "rot1:", "rot2:", "rot3:",
)


def detect_file_type(filename):
    """Guesses the Dioptas-relevant type of a file from its extension and a
    peek at its content.

    :return: one of "calibration", "pattern", "image", "phase", "project",
        "mask" or "unknown"
    """
    ext = os.path.splitext(filename)[1].lower()
    if ext == ".poni":
        return "calibration"
    if ext == ".jcpds":
        return "phase"
    if ext == ".dio":
        return "project"
    if ext == ".mask":
        return "mask"

    try:
        with open(filename, "rb") as f:
            head = f.read(8192)
    except OSError:
        return "unknown"

    try:
        text = head.decode("utf-8")
    except UnicodeDecodeError:
        text = None

    if text is None or "\x00" in text:
        # binary content — in the context of Dioptas almost certainly a
        # detector image
        return "image"

    lines = [line.strip() for line in text.splitlines()]
    lines = [line for line in lines if line and not line.startswith("#")]

    poni_key_count = sum(
        1 for line in lines if line.lower().startswith(_PONI_LINE_KEYS)
    )
    if poni_key_count >= 2:
        return "calibration"

    numeric_row_count = 0
    for line in lines[:20]:
        columns = line.replace(",", " ").split()
        if len(columns) < 2:
            continue
        try:
            [float(value) for value in columns]
        except ValueError:
            continue
        numeric_row_count += 1
    if numeric_row_count >= 2:
        return "pattern"

    if ext in _IMAGE_EXTENSIONS:
        return "image"
    if ext in _PATTERN_EXTENSIONS:
        return "pattern"
    return "unknown"


class FileLoadingError(IOError):
    """Raised when a file cannot be loaded as the expected type. The message
    is written for the user and can be shown in a dialog as-is."""


_EXPECTED_PHRASES = {
    "image": "an image",
    "pattern": "a pattern",
    "calibration": "a calibration",
    "mask": "a mask",
}

_DETECTED_HINTS = {
    "calibration": 'It looks like a pyFAI calibration file — '
                   'use "Load Calibration" to open it.',
    "pattern": "It looks like a diffraction pattern file — "
               'open it with the "Load" button below the pattern '
               "in the Integration view.",
    "image": "It contains binary data, most likely a detector image — "
             'use "Load Image" to open it.',
    "phase": "It looks like a JCPDS phase file — "
             "open it in the Phase tab of the Integration view.",
    "project": "It looks like a Dioptas project file — "
               'open it with "Open Project".',
}

_SUPPORTED_FORMATS = {
    "image": "Supported image formats include TIFF, CBF, EDF, MarCCD, SPE "
             "and HDF5-based files.",
    "pattern": "Pattern files are text files with two numeric columns, "
               "e.g. *.xy, *.chi or *.dat.",
    "calibration": "Calibration files are pyFAI *.poni files.",
    "mask": "Mask files are *.mask, *.npy, *.edf or two-column text files "
            "matching the image dimensions.",
}


def file_loading_error(filename, expected):
    """Builds a :class:`FileLoadingError` with a user-readable explanation of
    why *filename* could not be loaded as *expected* ("image", "pattern",
    "calibration" or "mask"), including a hint at what the file actually
    looks like and where to load it instead.
    """
    basename = os.path.basename(str(filename))
    if not os.path.isfile(str(filename)):
        return FileLoadingError(
            'Could not load "{}": the file does not exist.'.format(basename)
        )

    first_line = 'Could not load "{}" as {}.'.format(
        basename, _EXPECTED_PHRASES[expected]
    )
    detected = detect_file_type(str(filename))
    hint = _DETECTED_HINTS.get(detected)
    if detected == expected or hint is None or (
        expected == "mask" and detected == "image"
    ):
        # no useful redirection possible — explain what would have worked
        hint = "The file format was not recognized. " + _SUPPORTED_FORMATS[expected]
    return FileLoadingError(first_line + "\n" + hint)
