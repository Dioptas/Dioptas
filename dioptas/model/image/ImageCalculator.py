# -*- coding: utf-8 -*-
# Dioptas - GUI program for fast processing of 2D X-ray diffraction data
# Principal author: Clemens Prescher (clemens.prescher@gmail.com)
# Copyright (C) 2014-2019 GSECARS, University of Chicago, USA
# Copyright (C) 2015-2018 Institute for Geology and Mineralogy, University of Cologne, Germany
# Copyright (C) 2019-2020 DESY, Hamburg, Germany
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import numpy as np
from typing import Optional

from dioptas.model.image.ImageState import ImageState
from ..util.ImgCorrection import ImgCorrectionInterface


class ImageCalculator:
    """
    Handles image corrections and processing.
    Manages absorption corrections, transfer functions, and background subtraction.
    """

    def _calculate_img_data(self, state: ImageState) -> np.ndarray:
        """
        Calculates compound img_data based on the state of the object. This function is used internally to not compute
        those img arrays every time somebody requests the image data.
        """
        self.check_background_shape(state)
        self.check_corrections_shape(state)

        # calculate the current _img_data
        img = state.raw_image_data.astype(np.float32)
        bkg = (
            state.background_data.astype(np.float32)
            if state.background_data is not None
            else None
        )

        img = self.subtract_background(
            img,
            bkg,
            state.background_scaling,
            state.background_offset,
        )
        img = self.apply_corrections(img, state.corrections)

        if state.transfer_function_enabled:
            img = self.apply_transfer_function(
                img,
                state.transfer_function_original_data,
                state.transfer_function_response_data,
            )

        return img

    def get_corrected_img_data(
        self,
        state: ImageState,
    ) -> np.ndarray:
        """
        Get the corrected image data based on current corrections and background.
        :param state: image state
        :return: corrected image data
        """
        return self._calculate_img_data(state)

    def apply_corrections(
        self,
        img_data: np.ndarray,
        corrections: dict[str, ImgCorrectionInterface],
    ) -> np.ndarray:
        """
        Apply corrections to the image data.
        """
        for correction in corrections.values():
            img_data /= correction.get_data()
        return img_data

    def subtract_background(
        self,
        img_data: np.ndarray,
        background_data: Optional[np.ndarray],
        background_scaling: float = 1.0,
        background_offset: float = 0.0,
    ) -> np.ndarray:
        """
        Subtract background from the image data.
        """
        if background_data is None:
            return img_data
        return img_data - (background_scaling * background_data + background_offset)

    def apply_transfer_function(
        self,
        img_data: np.ndarray,
        transfer_function_original_data: np.ndarray,
        transfer_function_response_data: np.ndarray,
    ) -> np.ndarray:
        """
        Apply transfer function correction to the image data.
        """
        return (
            img_data / transfer_function_response_data * transfer_function_original_data
        )

    def check_background_shape(self, state: ImageState) -> None:
        """
        Check that the background shape is the same as the image data shape.
        If not, remove the background.
        """
        if state.background_data is not None:
            if state.raw_image_data.shape != state.background_data.shape:
                state.background_data = None

    def check_corrections_shape(self, state: ImageState) -> None:
        """
        Check that the correction shape is the same as the image data shape.
        If not, remove the correction with the wrong shape.
        """
        if state.corrections:
            for name, correction in state.corrections.items():
                if correction.shape() != state.raw_image_data.shape:
                    state.corrections.pop(name)
