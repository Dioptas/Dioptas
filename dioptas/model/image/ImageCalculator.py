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

from ..util import Signal
from ..util.ImgCorrection import (
    ImgCorrectionManager,
    TransferFunctionCorrection,
)


class ImageCalculator:
    """
    Handles image corrections and processing.
    Manages absorption corrections, transfer functions, and background subtraction.
    """

    def __init__(self):
        self._img_corrections = ImgCorrectionManager()
        self.transfer_correction = TransferFunctionCorrection()

        # Cached corrected data
        self._img_data_background_subtracted = None
        self._img_data_absorption_corrected = None
        self._img_data_background_subtracted_absorption_corrected = None

        # Signals
        self.corrections_removed = Signal()

    def _calculate_img_data(
        self, img_data, background_data, background_scaling, background_offset
    ):
        """
        Calculates compound img_data based on the state of the object. This function is used internally to not compute
        those img arrays every time somebody requests the image data.
        """
        # check that all data has the same dimensions
        if background_data is not None:
            if img_data.shape != background_data.shape:
                background_data = None
        if self._img_corrections.has_items():
            if img_data.shape != self._img_corrections.shape:
                self._img_corrections.clear()
                self.transfer_correction.reset()
                self.corrections_removed.emit()

        # calculate the current _img_data
        if background_data is not None and not self._img_corrections.has_items():
            self._img_data_background_subtracted = img_data - (
                background_scaling * background_data + background_offset
            )
        elif background_data is None and self._img_corrections.has_items():
            self._img_data_absorption_corrected = (
                img_data / self._img_corrections.get_data()
            )
        elif background_data is not None and self._img_corrections.has_items():
            self._img_data_background_subtracted_absorption_corrected = (
                img_data - (background_scaling * background_data + background_offset)
            ) / self._img_corrections.get_data()

    def get_corrected_img_data(
        self, img_data, background_data, background_scaling, background_offset, factor,
        transfer_function_enabled=False, transfer_function_original_data=None, transfer_function_response_data=None
    ):
        """
        Get the corrected image data based on current corrections and background.
        :param img_data: raw image data
        :param background_data: background data
        :param background_scaling: background scaling factor
        :param background_offset: background offset
        :param factor: overall scaling factor
        :param transfer_function_enabled: whether transfer function correction is enabled
        :param transfer_function_original_data: original image data for transfer function
        :param transfer_function_response_data: response image data for transfer function
        :return: corrected image data
        """
        # Handle None img_data case
        if img_data is None:
            return None
        
        # Apply transfer function correction if enabled and data is available
        if (transfer_function_enabled and 
            transfer_function_original_data is not None and 
            transfer_function_response_data is not None):
            # Calculate transfer function data
            transfer_data = transfer_function_response_data / transfer_function_original_data
            # Apply transfer function correction
            img_data = img_data / transfer_data
        
        self._calculate_img_data(
            img_data, background_data, background_scaling, background_offset
        )

        if background_data is None and not self._img_corrections.has_items():
            return img_data * factor
        elif background_data is not None and not self._img_corrections.has_items():
            return self._img_data_background_subtracted * factor
        elif background_data is None and self._img_corrections.has_items():
            return self._img_data_absorption_corrected * factor
        elif background_data is not None and self._img_corrections.has_items():
            return self._img_data_background_subtracted_absorption_corrected * factor

    def add_img_correction(self, correction, name=None):
        """
        Adds a correction to be applied to the image. Corrections are applied multiplicative for each pixel and after
        each other, depending on the order of addition.
        :param correction: An Object inheriting the ImgCorrectionInterface.
        :type correction: ImgCorrectionInterface
        :param name: correction can be given a name, to selectively delete or obtain later.
        :type name: str
        """
        self._img_corrections.add(correction, name)

    def get_img_correction(self, name):
        """
        :param name: correction name which was specified during the addition of the image correction.
        :return: the specified correction
        """
        return self._img_corrections.get_correction(name)

    def delete_img_correction(self, name=None):
        """
        :param name: deletes a correction from the correction calculation with a specific name. if no name is specified
         the last added correction is deleted.
        """
        self._img_corrections.delete(name)

    def enable_transfer_function(self):
        """Enable transfer function correction."""
        if (
            self.transfer_correction.get_data() is not None
            and self.get_img_correction("transfer") is None
        ):
            self.add_img_correction(self.transfer_correction, "transfer")

    def disable_transfer_function(self):
        """Disable transfer function correction."""
        if self.get_img_correction("transfer") is not None:
            self.delete_img_correction("transfer")

    @property
    def img_corrections(self):
        return self._img_corrections

    def has_corrections(self):
        """
        :return: Whether the ImageCorrector object has active absorption corrections or not
        """
        return self._img_corrections.has_items()

    def clear_corrections(self):
        """
        Clear all corrections and reset transfer correction.
        """
        self._img_corrections.clear()
        self.transfer_correction.reset()
        self.corrections_removed.emit()
