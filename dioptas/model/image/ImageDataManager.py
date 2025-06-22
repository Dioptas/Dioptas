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

import copy
import numpy as np

from ..util import Signal


class ImageDataManager:
    """
    Manages the core image data and metadata state.
    Handles image data, background data, metadata, and related properties.
    """

    def __init__(self):
        self.filename = ""
        self.file_info = ""
        self.motors_info = {}
        
        # Series information
        self.series_pos = 1
        self.series_max = 1
        self.selected_source = None
        self.series_get_image = None
        self.sources = None
        self._select_source = None
        
        # Image data
        self._img_data = None
        self._img_data_fabio = None
        
        # Background data
        self.background_filename = ""
        self._background_data = None
        self._background_scaling = 1
        self._background_offset = 0
        
        # Processing factor
        self._factor = 1
        
        # Loadable data configuration
        self.loadable_data = [
            {
                "name": "img_data",
                "default": np.zeros((2048, 2048)),
                "attribute": "_img_data",
            },
            {"name": "file_info", "default": "", "attribute": "file_info"},
            {"name": "motors_info", "default": {}, "attribute": "motors_info"},
            {"name": "img_data_fabio", "default": None, "attribute": "_img_data_fabio"},
            {"name": "series_pos", "default": 1, "attribute": "series_pos"},
            {"name": "series_max", "default": 1, "attribute": "series_max"},
            {
                "name": "series_get_image",
                "default": None,
                "attribute": "series_get_image",
            },
            {"name": "sources", "default": None, "attribute": "sources"},
            {"name": "select_source", "default": None, "attribute": "_select_source"},
        ]
        
        # Set initial loadable attributes
        self.set_loadable_attributes({})
        
        # Signals
        self.data_changed = Signal()

    def set_loadable_attributes(self, loaded_data):
        """
        Sets all attributes that change with the loading of an image to either their defaults or a given value.
        This assures that no leftover data will be kept when it is not overwritten by the new image.
        :param loaded_data: dictionary containing values to be loaded into the attributes corresponding to their keys.
        """
        for attribute in self.loadable_data:
            if attribute["name"] in loaded_data:
                # Set img_data directly to avoid triggering the setter and signal emission
                if attribute["name"] == "img_data":
                    self._img_data = loaded_data[attribute["name"]]
                else:
                    self.__setattr__(attribute["attribute"], loaded_data[attribute["name"]])
            else:
                # Set default values directly to avoid triggering the setter and signal emission
                if attribute["name"] == "img_data":
                    self._img_data = copy.copy(attribute["default"])
                else:
                    self.__setattr__(
                        attribute["attribute"], copy.copy(attribute["default"])
                    )

    @property
    def img_data(self):
        """Raw image data without any corrections or transformations."""
        return self._img_data

    @img_data.setter
    def img_data(self, new_data):
        self._img_data = new_data
        self.data_changed.emit()

    @property
    def background_data(self):
        return self._background_data

    @background_data.setter
    def background_data(self, new_data):
        self._background_data = new_data
        self.data_changed.emit()

    @property
    def background_scaling(self):
        return self._background_scaling

    @background_scaling.setter
    def background_scaling(self, new_value):
        self._background_scaling = new_value
        self.data_changed.emit()

    @property
    def background_offset(self):
        return self._background_offset

    @background_offset.setter
    def background_offset(self, new_value):
        self._background_offset = new_value
        self.data_changed.emit()

    @property
    def factor(self):
        return self._factor

    @factor.setter
    def factor(self, new_value):
        self._factor = new_value
        self.data_changed.emit()

    def has_background(self):
        """Check if background data is available."""
        return self._background_data is not None

    def reset_background(self):
        """Reset background data to None."""
        self.background_filename = ""
        self._background_data = None
        self.data_changed.emit()

    def select_source(self, source):
        """Select a source from available sources."""
        if self._select_source is not None:
            self._select_source(source)
            self.selected_source = source
            self.series_max = self.series_get_image.series_max if hasattr(self.series_get_image, 'series_max') else 1
            self.series_pos = min(self.series_pos, self.series_max)
            if self.series_get_image is not None:
                self._img_data = self.series_get_image(self.series_pos - 1)
            self.data_changed.emit()

    def load_series_img(self, pos):
        """Load image at specific position in series."""
        pos = min(max(pos, 1), self.series_max)
        if self.series_pos == pos:
            return

        self.series_pos = pos
        if self.series_get_image is not None:
            self._img_data = self.series_get_image(pos - 1)
        self.data_changed.emit() 