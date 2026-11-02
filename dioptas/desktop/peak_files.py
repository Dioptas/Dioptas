# SPDX-License-Identifier: MIT
"""Standalone picked-peak files; coordinates retain the scientific model's origin."""

import json
import math
import os
from pathlib import Path
import tempfile


def save_peaks(path, calibration, image, calibrant_name):
    document = {
        "format": "dioptas-calibration-peaks",
        "version": 1,
        "coordinates": "row-column-bottom-left",
        "imageShape": list(image.img_data.shape),
        "imageTransformations": list(image.params.transformations),
        "calibrant": {
            "name": calibrant_name,
            "dSpacingsAngstrom": list(calibration.calibrant.dspacing),
        },
        "groups": [
            {"ring": ring + 1, "points": [list(point) for point in positions]}
            for ring, positions in calibration.params.peak_selections
        ],
    }
    content = json.dumps(document, indent=2, allow_nan=False) + "\n"
    descriptor, temporary = tempfile.mkstemp(prefix=".dioptas-peaks-", dir=Path(path).parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(content)
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def load_peaks(path, calibration, image):
    """Validate the complete file before the caller replaces any picked groups."""
    document = json.loads(Path(path).read_text(encoding="utf-8"))
    if (
        not isinstance(document, dict)
        or document.get("format") != "dioptas-calibration-peaks"
        or type(document.get("version")) is not int
        or document["version"] != 1
        or document.get("coordinates") != "row-column-bottom-left"
    ):
        raise ValueError("Choose a Dioptas calibration peaks file (version 1).")
    if document.get("imageShape") != list(image.img_data.shape):
        raise ValueError("The saved peaks need an image with the same pixel dimensions.")
    if document.get("imageTransformations") != list(image.params.transformations):
        raise ValueError(
            "Apply the saved image's rotations and flips before loading its peaks."
        )
    reference = document.get("calibrant")
    if (
        not isinstance(reference, dict)
        or reference.get("dSpacingsAngstrom") != list(calibration.calibrant.dspacing)
    ):
        raise ValueError("Choose the saved peaks' calibrant before loading them.")
    groups = document.get("groups")
    if not isinstance(groups, list) or not groups:
        raise ValueError("The peaks file must contain picked peak groups.")
    height, width = image.img_data.shape
    selections = []
    for group in groups:
        if not isinstance(group, dict):
            raise ValueError("Invalid peak group in the peaks file.")
        ring, points = group.get("ring"), group.get("points")
        if type(ring) is not int or not 1 <= ring <= len(calibration.calibrant.dspacing):
            raise ValueError("Every peak group needs an available integer ring number.")
        if not isinstance(points, list) or not points:
            raise ValueError("Every peak group needs at least one point.")
        positions = []
        for point in points:
            if (
                not isinstance(point, list)
                or len(point) != 2
                or any(type(v) not in (int, float) or not math.isfinite(v) for v in point)
                or not 0 <= point[0] <= height - 1
                or not 0 <= point[1] <= width - 1
            ):
                raise ValueError(
                    "Peak coordinates must be finite positions inside the image."
                )
            positions.append(tuple(float(value) for value in point))
        selections.append((ring - 1, tuple(positions)))
    return tuple(selections)
