# SPDX-License-Identifier: MIT

from __future__ import annotations

import fabio
import numpy as np


class FabioLoader:
    def __init__(self, filename: str, frame_index: int = 0) -> None:
        """Loads an image file using the fabio library."""
        self.fabio_image: fabio.fabioimage.FabioImage = fabio.open(
            filename, frame=frame_index or None)
        self.series_max: int = self.fabio_image.nframes

    def get_image(self, ind: int = 0) -> np.ndarray:
        if ind == self.fabio_image.currentframe:
            # fabio.open has already decoded this frame.
            return self.fabio_image.data[::-1]
        return self.fabio_image.get_frame(ind).data[::-1]
