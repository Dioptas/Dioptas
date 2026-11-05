# SPDX-License-Identifier: MIT
"""Qt-style image export without importing a Qt application."""

import base64
import io
from pathlib import Path

import numpy as np
from PIL import Image


def save_tiff_data(path, data):
    """Qt's corrected int32 TIFF in the saved image's top-origin convention."""
    Image.fromarray(np.flipud(np.asarray(data, dtype=np.int32))).save(path)


def save_image(session, path=None, source="image", png_data=None, suggested_name=None):
    if source not in {"image", "cake"}:
        raise ValueError("Choose the detector image or cake to save.")
    if not session._has_image:
        raise ValueError("Open an image before saving it.")
    calibration = session.configuration.calibration_model
    if source == "cake" and session._cake is None:
        raise ValueError("Integrate a calibrated image before saving its cake.")
    path = session._path(path, f"{source}_export", save=True)
    if path is None:
        return {"cancelled": True}
    suffix = Path(path).suffix.lower()
    if not suffix:
        path += ".png"
        suffix = ".png"
    if suffix == ".png":
        if not isinstance(png_data, str):
            raise ValueError(
                "Save PNG from the image toolbar to include its display settings."
            )
        # Only a user-requested, encoded output PNG travels back from the view.
        # Scientific detector/cake buffers retain their binary native transport.
        encoded = base64.b64decode(png_data, validate=True)
        with Image.open(io.BytesIO(encoded)) as image:
            if image.format != "PNG":
                raise ValueError("The image export must contain a PNG.")
            image.verify()
        Path(path).write_bytes(encoded)
    elif suffix in {".tif", ".tiff"}:
        data = (
            session.configuration.img_model.img_data
            if source == "image"
            else calibration.cake_img
        )
        # Match Qt ImageController.save_img: corrected scientific data, int32,
        # flipped to the saved image's top-origin row convention.
        save_tiff_data(path, data)
    elif suffix in {".txt", ".csv"} and source == "cake":
        delimiter = "," if suffix == ".csv" else " "
        with open(path, "w") as output:
            np.savetxt(
                output, np.insert(calibration.cake_tth, 0, 0)[None],
                fmt="%.3f", delimiter=delimiter,
            )
            np.savetxt(
                output, np.column_stack((calibration.cake_azi, calibration.cake_img)),
                fmt=["%.2f"] + ["%.0f"] * calibration.cake_img.shape[1],
                delimiter=delimiter,
            )
    else:
        raise ValueError(
            "Save an image as PNG or TIFF; cake data also supports TXT and CSV."
        )
    return {"savedPath": path}
