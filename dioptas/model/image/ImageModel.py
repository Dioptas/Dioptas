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

import logging

import numpy as np
from PIL import Image


from ..util import Signal
from .ImageDataManager import ImageDataManager
from .ImageLoader import ImageLoader
from ..util.FileNavigator import FileNavigator
from .ImageTransformer import ImageTransformer
from .ImageCalculator import ImageCalculator
from ..util.AutoProcessor import AutoProcessor

logger = logging.getLogger(__name__)


class ImageModel(object):
    """
    Main Image handling class. Supports several features:
        - loading image files in any format using fabio
        - iterating through files either by file number or time of creation
        - image transformations like rotating and flipping
        - setting a background image
        - setting an absorption correction (img_data is divided by this)

    In order to subscribe to changes of the data in the ImgModel, please use the img_changed QtSignal.
    The Signal will be called every time the img_data has changed.
    """

    def __init__(self):
        super(ImageModel, self).__init__()

        # Initialize components
        self.data_manager = ImageDataManager()
        self.loader = ImageLoader()
        self.navigator = FileNavigator()
        self.transformer = ImageTransformer()
        self.corrector = ImageCalculator()
        self.auto_processor = AutoProcessor(load_callback=self.load)

        # Connect component signals
        self._connect_components()

        # Legacy attributes for backward compatibility
        self.filename = self.data_manager.filename
        self.img_transformations = self.transformer.img_transformations
        self.file_iteration_mode = self.navigator.file_iteration_mode
        self.file_name_iterator = self.navigator.file_name_iterator
        self.series_pos = self.data_manager.series_pos
        self.series_max = self.data_manager.series_max
        self.selected_source = self.data_manager.selected_source
        self.background_filename = self.data_manager.background_filename
        self.transfer_correction = self.corrector.transfer_correction

        # Main signals
        self.img_changed = Signal()
        self.autoprocess_changed = Signal()
        self.transformations_changed = Signal()
        self.corrections_removed = Signal()

    def _connect_components(self):
        """Connect signals between components."""
        self.data_manager.data_changed.connect(self._on_data_changed)
        self.transformer.transformations_changed.connect(
            self._on_transformations_changed
        )
        self.corrector.corrections_removed.connect(self._on_corrections_removed)
        self.auto_processor.autoprocess_changed.connect(self._on_autoprocess_changed)

    def _on_data_changed(self):
        """Handle data changes from data manager."""
        self._update_legacy_attributes()
        self.img_changed.emit()

    def _on_transformations_changed(self):
        """Handle transformation changes."""
        self.img_transformations = self.transformer.img_transformations
        self.transformations_changed.emit()

    def _on_corrections_removed(self):
        """Handle corrections removed."""
        self.corrections_removed.emit()

    def _on_autoprocess_changed(self):
        """Handle autoprocess changes."""
        self.autoprocess_changed.emit()

    def _update_legacy_attributes(self):
        """Update legacy attributes for backward compatibility."""
        self.filename = self.data_manager.filename
        self.series_pos = self.data_manager.series_pos
        self.series_max = self.data_manager.series_max
        self.selected_source = self.data_manager.selected_source
        self.background_filename = self.data_manager.background_filename
        self.sources = self.data_manager.sources
        self.file_info = self.data_manager.file_info
        self.motors_info = self.data_manager.motors_info

    def load(self, filename, pos=0):
        """
        Loads an image file in any format known by fabIO, PIL or HDF5. Automatically performs all previous img
        transformations, recalculates background subtracted and absorption corrected image data.
        The img_changed signal will be emitted after the process.
        :param filename: path of the image file to be loaded
        :param pos: position of image in the image file to be loaded
        """
        filename = str(filename)  # since it could also be QString
        logger.info("Loading {0}.".format(filename))

        # Update data manager
        self.data_manager.filename = filename

        # Load image data
        image_file_data = self.loader.get_image_data(filename, pos)
        self.data_manager.set_loadable_attributes(image_file_data)

        # Update navigator
        self.navigator.update_filename(filename)
        self.auto_processor.set_directory_path(
            self.navigator.set_directory_watcher_path(filename)
        )

        # Apply transformations
        self._perform_img_transformations()

        # Update series position
        self.data_manager.series_pos = pos + 1

        # Update legacy attributes
        self._update_legacy_attributes()

        # self.img_changed.emit()

    def get_image_data(self, filename, pos=0):
        """Delegate to ImageLoader."""
        return self.loader.get_image_data(filename, pos)

    def set_loadable_attributes(self, loaded_data):
        """Delegate to ImageDataManager."""
        self.data_manager.set_loadable_attributes(loaded_data)

    def select_source(self, source):
        """Select a source from available sources."""
        self.data_manager.select_source(source)
        self._perform_img_transformations()
        self._calculate_img_data()
        self.img_changed.emit()

    def save(self, filename):
        """
        Saves the current file as another image file, the raw data is used for saving.
        :param filename: name of the saved file, extensions defines the format, please see fabio library for reference
        """
        try:
            if hasattr(self.loader, "loader") and hasattr(
                self.loader.loader, "fabio_image"
            ):
                self.loader.loader.fabio_image.save(filename)
            else:
                im_array = np.int32(np.copy(np.flipud(self.data_manager.img_data)))
                im = Image.fromarray(im_array)
                im.save(filename)
        except Exception as e:
            logger.error(f"Error saving file: {e}")

    def load_background(self, filename):
        """
        Loads an image file as background in any format known by fabIO. Automatically performs all previous img
        transformations, recalculates background subtracted and absorption corrected image data.
        The img_changed signal will be emitted after the process.
        :param filename: path of the image file to be loaded
        """
        self.data_manager.background_filename = filename

        background_data = self.loader.get_image_data(filename)["img_data"]
        self.data_manager.background_data = background_data

        # Apply transformations to background
        self._perform_background_transformations()

        if self.data_manager.background_data.shape != self.data_manager.img_data.shape:
            self.data_manager.background_data = None
            self._calculate_img_data()
            self.img_changed.emit()
            raise BackgroundDimensionWrongException()

        self._calculate_img_data()
        self.img_changed.emit()

    def add(self, filename):
        """
        Adds an image file in any format known by fabIO. Automatically performs all previous img transformations and
        recalculates background subtracted and absorption corrected image data.
        The img_changed signal will be emitted after the process.
        :param filename: path of the image file to be loaded
        """
        filename = str(filename)  # since it could also be QString

        img_data = self.loader.get_image_data(filename)["img_data"]

        # Apply transformations
        for transformation in self.transformer.img_transformations:
            img_data = transformation(img_data)

        if not self.data_manager.img_data.shape == img_data.shape:
            return

        logger.info("Adding {0}.".format(filename))

        if self.data_manager.img_data.dtype == np.uint16:
            self.data_manager.img_data = self.data_manager.img_data.astype(np.uint32)

        self.data_manager.img_data += img_data

        self._calculate_img_data()
        self.img_changed.emit()

    def reset_background(self):
        """Reset background data."""
        self.data_manager.reset_background()
        self.img_changed.emit()

    def has_background(self):
        """Check if background data is available."""
        return self.data_manager.has_background()

    @property
    def background_data(self):
        return self.data_manager.background_data

    @background_data.setter
    def background_data(self, new_data):
        self.data_manager.background_data = new_data

    @property
    def untransformed_background_data(self):
        """Get untransformed background data."""
        # Reset transformations temporarily
        original_transformations = self.transformer.img_transformations.copy()
        self.transformer.img_transformations = []
        background_data = np.copy(self.background_data)
        self.transformer.img_transformations = original_transformations
        return background_data

    @property
    def background_scaling(self):
        return self.data_manager.background_scaling

    @background_scaling.setter
    def background_scaling(self, new_value):
        self.data_manager.background_scaling = new_value

    @property
    def background_offset(self):
        return self.data_manager.background_offset

    @background_offset.setter
    def background_offset(self, new_value):
        self.data_manager.background_offset = new_value

    def load_series_img(self, pos):
        """Load image at specific position in series."""
        self.data_manager.load_series_img(pos)
        self._perform_img_transformations()
        self._calculate_img_data()
        self.img_changed.emit()

    def load_next_file(self, step=1, pos=None):
        """Load the next file based on iteration mode."""
        next_file_name = self.navigator.get_next_filename(step=step, pos=pos)
        if next_file_name is not None:
            self.load(next_file_name)

    def load_previous_file(self, step=1, pos=None):
        """Load the previous file based on iteration mode."""
        previous_file_name = self.navigator.get_previous_filename(step=step, pos=pos)
        if previous_file_name is not None:
            self.load(previous_file_name)

    def load_next_folder(self, mec_mode=False):
        """Load file in next folder."""
        next_file_name = self.navigator.get_next_folder(mec_mode=mec_mode)
        if next_file_name is not None:
            self.load(next_file_name)

    def load_previous_folder(self, mec_mode=False):
        """Load file in previous folder."""
        previous_file_name = self.navigator.get_previous_folder(mec_mode=mec_mode)
        if previous_file_name is not None:
            self.load(previous_file_name)

    def set_file_iteration_mode(self, mode):
        """Set file iteration mode."""
        self.navigator.set_file_iteration_mode(mode)
        self.file_iteration_mode = self.navigator.file_iteration_mode


    @property
    def img_data(self):
        """Get corrected image data."""
        return self.corrector.get_corrected_img_data(
            self.data_manager.img_data,
            self.data_manager.background_data,
            self.data_manager.background_scaling,
            self.data_manager.background_offset,
            self.data_manager.factor,
        )

    @img_data.setter
    def img_data(self, new_data):
        self.data_manager.img_data = new_data
        self._calculate_img_data()
        self.img_changed.emit()

    @property
    def raw_img_data(self):
        """Get raw image data without corrections."""
        return self.data_manager.img_data

    @property
    def untransformed_raw_img_data(self):
        """Get untransformed raw image data."""
        # Reset transformations temporarily
        original_transformations = self.transformer.img_transformations.copy()
        self.transformer.img_transformations = []
        img_data = np.copy(self.raw_img_data)
        self.transformer.img_transformations = original_transformations
        return img_data

    def rotate_img_p90(self):
        """Rotate image by 90 degrees."""
        transformed_img, transformed_background = self.transformer.rotate_img_p90(
            self.data_manager.img_data, self.data_manager.background_data
        )
        self.data_manager.img_data = transformed_img
        if transformed_background is not None:
            self.data_manager.background_data = transformed_background
        self._calculate_img_data()
        self.img_changed.emit()

    def rotate_img_m90(self):
        """Rotate image by -90 degrees."""
        transformed_img, transformed_background = self.transformer.rotate_img_m90(
            self.data_manager.img_data, self.data_manager.background_data
        )
        self.data_manager.img_data = transformed_img
        if transformed_background is not None:
            self.data_manager.background_data = transformed_background
        self._calculate_img_data()
        self.img_changed.emit()

    def flip_img_horizontally(self):
        """Flip image horizontally."""
        transformed_img, transformed_background = (
            self.transformer.flip_img_horizontally(
                self.data_manager.img_data, self.data_manager.background_data
            )
        )
        self.data_manager.img_data = transformed_img
        if transformed_background is not None:
            self.data_manager.background_data = transformed_background
        self._calculate_img_data()
        self.img_changed.emit()

    def flip_img_vertically(self):
        """Flip image vertically."""
        transformed_img, transformed_background = self.transformer.flip_img_vertically(
            self.data_manager.img_data, self.data_manager.background_data
        )
        self.data_manager.img_data = transformed_img
        if transformed_background is not None:
            self.data_manager.background_data = transformed_background
        self._calculate_img_data()
        self.img_changed.emit()

    def reset_transformations(self, img_changed=True):
        """Reset all transformations."""
        # Reset transformations on data
        if self.data_manager.img_data is not None:
            self.data_manager.img_data = self.transformer._reset_img_transformations(
                self.data_manager.img_data
            )
        if self.data_manager.background_data is not None:
            self.data_manager.background_data = (
                self.transformer._reset_background_transformations(
                    self.data_manager.background_data
                )
            )

        self.transformer.reset_transformations()
        self._calculate_img_data()
        if img_changed:
            self.img_changed.emit()

    def _perform_img_transformations(self):
        """Apply transformations to current image data."""
        if self.data_manager.img_data is not None:
            self.data_manager.img_data = self.transformer._perform_img_transformations(
                self.data_manager.img_data
            )

    def _perform_background_transformations(self):
        """Apply transformations to background data."""
        if self.data_manager.background_data is not None:
            self.data_manager.background_data = (
                self.transformer._perform_background_transformations(
                    self.data_manager.background_data
                )
            )

    def get_transformations_string_list(self):
        """Get list of transformation names."""
        return self.transformer.get_transformations_string_list()

    def load_transformations_string_list(self, transformations):
        """Load transformations from string list."""
        self.transformer.load_transformations_string_list(transformations)
        self._perform_img_transformations()
        self._perform_background_transformations()

    def add_img_correction(self, correction, name=None):
        """Add image correction."""
        self.corrector.add_img_correction(correction, name)
        self._calculate_img_data()
        self.img_changed.emit()

    def get_img_correction(self, name):
        """Get image correction by name."""
        return self.corrector.get_img_correction(name)

    def delete_img_correction(self, name=None):
        """Delete image correction."""
        self.corrector.delete_img_correction(name)
        self._calculate_img_data()
        self.img_changed.emit()

    def enable_transfer_function(self):
        """Enable transfer function correction."""
        self.corrector.enable_transfer_function()
        self._calculate_img_data()
        self.img_changed.emit()

    def disable_transfer_function(self):
        """Disable transfer function correction."""
        self.corrector.disable_transfer_function()

    @property
    def img_corrections(self):
        return self.corrector.img_corrections

    def has_corrections(self):
        """Check if corrections are active."""
        return self.corrector.has_corrections()

    @property
    def autoprocess(self):
        return self.auto_processor.autoprocess

    @autoprocess.setter
    def autoprocess(self, new_val):
        self.auto_processor.autoprocess = new_val

    @property
    def factor(self):
        return self.data_manager.factor

    @factor.setter
    def factor(self, new_value):
        self.data_manager.factor = new_value

    def blockSignals(self, block=True):
        """Block all signals."""
        for member in vars(self):
            attr = getattr(self, member)
            if isinstance(attr, Signal):
                attr.blocked = block

    def _calculate_img_data(self):
        """Trigger recalculation of corrected image data."""
        # This method is called to ensure the corrector has the latest data
        # The actual calculation happens in the img_data property getter
        pass


class BackgroundDimensionWrongException(Exception):
    pass
