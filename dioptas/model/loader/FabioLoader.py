# SPDX-License-Identifier: MIT

from __future__ import annotations

import fabio
import numpy as np


class FabioLoader:
    def __init__(self, filename: str) -> None:
        """Loads an image file using the fabio library."""
        self.fabio_image: fabio.fabioimage.FabioImage = fabio.open(filename)
        self.series_max: int = self.fabio_image.nframes

    def get_image(self, ind: int = 0) -> np.ndarray:
        return self.fabio_image.get_frame(ind).data[::-1]
