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

"""
ImageModelAdapter - Backward compatibility adapter for ImageModel.

This adapter provides the same interface as the old ImageModel but uses
the new refactored components internally. This allows for gradual migration
without breaking existing code.
"""

import logging
import warnings
from typing import Optional, Any

from ..util import Signal
from .ImageModel import ImageModel
from .ImageState import ImageState

logger = logging.getLogger(__name__)


class ImageModelAdapter:
    """
    Adapter that provides the old ImageModel interface using new refactored components.
    
    This allows existing code to work without changes while we migrate to the new
    architecture. The adapter maintains the same public API as the original ImageModel.
    """
    
    def __init__(self):
        # Use the refactored model internally
        self._refactored_model = ImageModel()
        
        # Expose the same signals as the original ImageModel
        self.img_changed = self._refactored_model.img_changed
        self.autoprocess_changed = self._refactored_model.autoprocess_changed
        self.transformations_changed = self._refactored_model.transformations_changed
        self.corrections_removed = self._refactored_model.corrections_removed
        
        # Legacy attributes for backward compatibility
        self._update_legacy_attributes()
    
    def _update_legacy_attributes(self):
        """Update legacy attributes to match current state."""
        state = self._refactored_model.state
        self.filename = state.filename
        self.series_pos = state.series_pos
        self.series_max = state.series_max
        self.selected_source = state.selected_source
        self.background_filename = state.background_filename
        self.file_iteration_mode = state.file_iteration_mode
        self.img_transformations = state.transformations
        self.transfer_correction = None  # TODO: Implement when corrections are added
        self.file_name_iterator = self._refactored_model.navigator.file_name_iterator
        self.sources = getattr(state, 'sources', [])
        self.file_info = getattr(state, 'file_info', {})
        self.motors_info = getattr(state, 'motors_info', {})
    
    # Legacy API methods that delegate to refactored model
    
    def load(self, filename, pos=0):
        """Load an image file (legacy interface)."""
        new_state = self._refactored_model.load(filename, pos)
        self._update_legacy_attributes()
        return new_state
    
    def get_image_data(self, filename, pos=0):
        """Get image data (legacy interface)."""
        return self._refactored_model._command_processor.loader.get_image_data(filename, pos)
    
    def set_loadable_attributes(self, loaded_data):
        """Set loadable attributes (legacy interface)."""
        # This would need to be implemented in the refactored model
        logger.warning("set_loadable_attributes not yet implemented in refactored model")
    
    def select_source(self, source):
        """Select source (legacy interface)."""
        # This would need to be implemented in the refactored model
        logger.warning("select_source not yet implemented in refactored model")
        self._update_legacy_attributes()
    
    def save(self, filename):
        """Save image (legacy interface)."""
        # This would need to be implemented in the refactored model
        logger.warning("save not yet implemented in refactored model")
    
    def load_background(self, filename):
        """Load background image (legacy interface)."""
        new_state = self._refactored_model.load_background(filename)
        self._update_legacy_attributes()
        return new_state
    
    def add(self, filename):
        """Add image (legacy interface)."""
        # This would need to be implemented in the refactored model
        logger.warning("add not yet implemented in refactored model")
        self._update_legacy_attributes()
    
    def rotate_img_p90(self):
        """Rotate image by 90 degrees (legacy interface)."""
        new_state = self._refactored_model.rotate_img_p90()
        self._update_legacy_attributes()
        return new_state
    
    def rotate_img_m90(self):
        """Rotate image by -90 degrees (legacy interface)."""
        new_state = self._refactored_model.rotate_img_m90()
        self._update_legacy_attributes()
        return new_state
    
    def flip_img_horizontally(self):
        """Flip image horizontally (legacy interface)."""
        new_state = self._refactored_model.flip_img_horizontally()
        self._update_legacy_attributes()
        return new_state
    
    def flip_img_vertically(self):
        """Flip image vertically (legacy interface)."""
        new_state = self._refactored_model.flip_img_vertically()
        self._update_legacy_attributes()
        return new_state
    
    def reset_transformations(self, img_changed=True):
        """Reset transformations (legacy interface)."""
        new_state = self._refactored_model.reset_transformations()
        self._update_legacy_attributes()
        return new_state
    
    def add_img_correction(self, correction, name=None):
        """Add image correction (legacy interface)."""
        new_state = self._refactored_model.add_img_correction(correction, name)
        self._update_legacy_attributes()
        return new_state
    
    def get_img_correction(self, name):
        """Get image correction (legacy interface)."""
        return self._refactored_model.get_img_correction(name)
    
    def delete_img_correction(self, name=None):
        """Delete image correction (legacy interface)."""
        new_state = self._refactored_model.delete_img_correction(name)
        self._update_legacy_attributes()
        return new_state
    
    def enable_transfer_function(self):
        """Enable transfer function (legacy interface)."""
        new_state = self._refactored_model.enable_transfer_function()
        self._update_legacy_attributes()
        return new_state
    
    def disable_transfer_function(self):
        """Disable transfer function (legacy interface)."""
        new_state = self._refactored_model.disable_transfer_function()
        self._update_legacy_attributes()
        return new_state
    
    def load_series_img(self, pos):
        """Load series image (legacy interface)."""
        new_state = self._refactored_model.load_series_img(pos)
        self._update_legacy_attributes()
        return new_state
    
    def load_next_file(self, step=1, pos=None):
        """Load next file (legacy interface)."""
        new_state = self._refactored_model.load_next_file(step, pos)
        if new_state:
            self._update_legacy_attributes()
        return new_state
    
    def load_previous_file(self, step=1, pos=None):
        """Load previous file (legacy interface)."""
        new_state = self._refactored_model.load_previous_file(step, pos)
        if new_state:
            self._update_legacy_attributes()
        return new_state
    
    def load_next_folder(self, mec_mode=False):
        """Load next folder (legacy interface)."""
        new_state = self._refactored_model.load_next_folder(mec_mode)
        if new_state:
            self._update_legacy_attributes()
        return new_state
    
    def load_previous_folder(self, mec_mode=False):
        """Load previous folder (legacy interface)."""
        new_state = self._refactored_model.load_previous_folder(mec_mode)
        if new_state:
            self._update_legacy_attributes()
        return new_state
    
    def set_file_iteration_mode(self, mode):
        """Set file iteration mode (legacy interface)."""
        new_state = self._refactored_model.set_file_iteration_mode(mode)
        self._update_legacy_attributes()
        return new_state
    
    def reset_background(self):
        """Reset background (legacy interface)."""
        # Create new state with background reset
        current_state = self._refactored_model.state
        new_state = current_state.copy(
            background_data=None,
            background_filename="",
            background_scaling=1.0,
            background_offset=0.0
        )
        self._refactored_model.set_state(new_state)
        self._update_legacy_attributes()
        return new_state
    
    def has_background(self):
        """Check if background exists (legacy interface)."""
        return self._refactored_model.has_background()
    
    def has_corrections(self):
        """Check if corrections exist (legacy interface)."""
        return self._refactored_model.has_corrections()
    
    def get_transformations_string_list(self):
        """Get transformations list (legacy interface)."""
        return self._refactored_model.get_transformations_string_list()
    
    def load_transformations_string_list(self, transformations):
        """Load transformations from list (legacy interface)."""
        new_state = self._refactored_model.load_transformations_string_list(transformations)
        self._update_legacy_attributes()
        return new_state
    
    def blockSignals(self, block=True):
        """Block signals (legacy interface)."""
        self._refactored_model.blockSignals(block)
    
    # Property getters that delegate to refactored model
    
    @property
    def img_data(self):
        """Get corrected image data (legacy interface)."""
        return self._refactored_model.img_data
    
    @img_data.setter
    def img_data(self, new_data):
        """Set image data (legacy interface)."""
        # Create new state with the new image data
        current_state = self._refactored_model.state
        new_state = current_state.copy(raw_image_data=new_data)
        self._refactored_model.set_state(new_state)
        self._update_legacy_attributes()
    
    @property
    def raw_img_data(self):
        """Get raw image data (legacy interface)."""
        return self._refactored_model.raw_img_data
    
    @property
    def untransformed_raw_img_data(self):
        """Get untransformed raw image data (legacy interface)."""
        # This would need to be implemented in the refactored model
        logger.warning("untransformed_raw_img_data not yet implemented in refactored model")
        return self.raw_img_data
    
    @property
    def background_data(self):
        """Get background data (legacy interface)."""
        return self._refactored_model.background_data
    
    @background_data.setter
    def background_data(self, new_data):
        """Set background data (legacy interface)."""
        current_state = self._refactored_model.state
        new_state = current_state.copy(background_data=new_data)
        self._refactored_model.set_state(new_state)
        self._update_legacy_attributes()
    
    @property
    def untransformed_background_data(self):
        """Get untransformed background data (legacy interface)."""
        # This would need to be implemented in the refactored model
        logger.warning("untransformed_background_data not yet implemented in refactored model")
        return self.background_data
    
    @property
    def background_scaling(self):
        """Get background scaling (legacy interface)."""
        return self._refactored_model.background_scaling
    
    @background_scaling.setter
    def background_scaling(self, new_value):
        """Set background scaling (legacy interface)."""
        new_state = self._refactored_model.set_background_scaling(new_value)
        self._update_legacy_attributes()
    
    @property
    def background_offset(self):
        """Get background offset (legacy interface)."""
        return self._refactored_model.background_offset
    
    @background_offset.setter
    def background_offset(self, new_value):
        """Set background offset (legacy interface)."""
        new_state = self._refactored_model.set_background_offset(new_value)
        self._update_legacy_attributes()
    
    @property
    def factor(self):
        """Get processing factor (legacy interface)."""
        return self._refactored_model.factor
    
    @factor.setter
    def factor(self, new_value):
        """Set processing factor (legacy interface)."""
        new_state = self._refactored_model.set_factor(new_value)
        self._update_legacy_attributes()
    
    @property
    def autoprocess(self):
        """Get autoprocess flag (legacy interface)."""
        return self._refactored_model.autoprocess
    
    @autoprocess.setter
    def autoprocess(self, new_val):
        """Set autoprocess flag (legacy interface)."""
        new_state = self._refactored_model.set_autoprocess(new_val)
        self._update_legacy_attributes()
    
    @property
    def img_corrections(self):
        """Get image corrections (legacy interface)."""
        return self._refactored_model.img_corrections
    
    # Additional methods for accessing the new functionality
    
    @property
    def refactored_model(self):
        """Get access to the underlying refactored model."""
        return self._refactored_model
    
    @property
    def state(self):
        """Get current state (new interface)."""
        return self._refactored_model.state
    
    def set_state(self, state: ImageState):
        """Set state directly (new interface)."""
        self._refactored_model.set_state(state)
        self._update_legacy_attributes()
    
    # Component access (for backward compatibility)
    
    @property
    def data_manager(self):
        """Access to data manager (for backward compatibility)."""
        warnings.warn("data_manager access is deprecated. Use .state instead.", DeprecationWarning, stacklevel=2)
        return self._refactored_model
    
    @property
    def loader(self):
        """Access to loader (for backward compatibility)."""
        warnings.warn("loader access is deprecated. Use command processor instead.", DeprecationWarning, stacklevel=2)
        return self._refactored_model._command_processor.loader
    
    @property
    def navigator(self):
        """Access to navigator (for backward compatibility)."""
        return self._refactored_model.navigator
    
    @property
    def transformer(self):
        """Access to transformer (for backward compatibility)."""
        warnings.warn("transformer access is deprecated. Use command processor instead.", DeprecationWarning, stacklevel=2)
        return self._refactored_model._command_processor.transformer
    
    @property
    def corrector(self):
        """Access to corrector (for backward compatibility)."""
        warnings.warn("corrector access is deprecated. Use command processor instead.", DeprecationWarning, stacklevel=2)
        return self._refactored_model._command_processor.calculator
    
    @property
    def auto_processor(self):
        """Access to auto processor (for backward compatibility)."""
        return self._refactored_model.auto_processor 