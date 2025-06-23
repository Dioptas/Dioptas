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
from typing import Optional, Dict, Any

from ..util import Signal
from .ImageState import ImageState
from .ImageCommands import (
    ImageCommandProcessor,
    BackgroundDimensionWrongException,
    RotationDirection,
    FlipDirection,
)
from ..util.FileNavigator import FileNavigator
from ..util.AutoProcessor import AutoProcessor

logger = logging.getLogger(__name__)


class ImageModel:
    """
    Refactored ImageModel that makes state explicit and accessible.

    This version provides:
    - Direct access to state via .state property
    - Command-based operations that return new states
    - Clear separation between state and operations
    - Type-safe command interface
    """

    def __init__(self):
        # Initialize state
        self._state = ImageState()

        # Initialize command processor
        self._command_processor = ImageCommandProcessor()

        # Initialize components that handle external concerns
        self.navigator = FileNavigator()
        self.auto_processor = AutoProcessor(load_callback=self._load_callback)

        # Signals
        self.img_changed = Signal()
        self.autoprocess_changed = Signal()
        self.transformations_changed = Signal()
        self.corrections_removed = Signal()

        # Connect component signals
        self._connect_components()

    def _connect_components(self):
        """Connect signals between components."""
        self.auto_processor.autoprocess_changed.connect(self._on_autoprocess_changed)

    def _on_autoprocess_changed(self):
        """Handle autoprocess changes."""
        self.autoprocess_changed.emit()

    def _load_callback(self, filename: str, pos: int = 0):
        """Callback for auto-processor to load files."""
        self.load(filename, pos)

    def _update_state(self, new_state: ImageState):
        """Update internal state and emit signals."""
        old_state = self._state
        self._state = new_state

        # Emit signals based on what changed
        if (
            old_state.raw_image_data is not new_state.raw_image_data
            or old_state.background_data is not new_state.background_data
        ):
            self.img_changed.emit()

        if old_state.transformations != new_state.transformations:
            self.transformations_changed.emit()

        if old_state.corrections != new_state.corrections:
            if len(new_state.corrections) < len(old_state.corrections):
                self.corrections_removed.emit()

    # State Access

    @property
    def state(self) -> ImageState:
        """Get current state (read-only)."""
        return self._state

    def set_state(self, new_state: ImageState):
        """Set state directly (for loading from saved state)."""
        self._state = new_state

        # Update components
        self.navigator.update_filename(new_state.filename)
        self.auto_processor.set_directory_path(new_state.directory_path)
        self.auto_processor.autoprocess = new_state.autoprocess

        # Apply transformations
        self._state = self._apply_transformations(new_state)

        # Emit signals
        self.img_changed.emit()
        self.transformations_changed.emit()
        self.autoprocess_changed.emit()

    # Command-based Operations (return new states)

    def load(self, filename: str, pos: int = 0) -> ImageState:
        """Load an image file and return new state."""
        new_state = self._command_processor.load_image(
            self._state, filename=filename, pos=pos
        )

        # Update navigator
        self.navigator.update_filename(filename)
        self.auto_processor.set_directory_path(
            self.navigator.set_directory_watcher_path(filename)
        )

        # Apply transformations
        new_state = self._apply_transformations(new_state)

        # Check if background is the same size as the image, if not reset background
        if (
            new_state.background_data is not None
            and new_state.background_data.shape != new_state.raw_image_data.shape
        ):
            logger.warning(
                f"Background data has different shape than image data, resetting background."
            )
            new_state = self._command_processor.reset_background(new_state)

        # Check if corrections are the same size as the image, if not reset corrections
        if new_state.corrections is not None:
            for _, correction in new_state.corrections.items():
                print(correction)
                if correction.shape() != new_state.raw_image_data.shape:
                    logger.warning(
                        f"Correction has different shape than image data, resetting correction."
                    )
                    new_state = self._command_processor.reset_corrections(new_state)

        # Update internal state
        self._update_state(new_state)

        return new_state

    def load_background(self, filename: str) -> ImageState:
        """Load background image and return new state."""
        try:
            new_state = self._command_processor.load_background(
                self._state, filename=filename
            )
            self._update_state(new_state)
            return new_state
        except BackgroundDimensionWrongException:
            # Reset background and emit signal
            new_state = self._state.copy(background_data=None)
            self._update_state(new_state)
            raise

    def rotate_img_p90(self) -> ImageState:
        """Rotate image by 90 degrees and return new state."""
        new_state = self._command_processor.rotate_image(
            self._state, direction=RotationDirection.PLUS_90
        )
        self._update_state(new_state)
        return new_state

    def rotate_img_m90(self) -> ImageState:
        """Rotate image by -90 degrees and return new state."""
        new_state = self._command_processor.rotate_image(
            self._state, direction=RotationDirection.MINUS_90
        )
        self._update_state(new_state)
        return new_state

    def flip_img_horizontally(self) -> ImageState:
        """Flip image horizontally and return new state."""
        new_state = self._command_processor.flip_image(
            self._state, direction=FlipDirection.HORIZONTAL
        )
        self._update_state(new_state)
        return new_state

    def flip_img_vertically(self) -> ImageState:
        """Flip image vertically and return new state."""
        new_state = self._command_processor.flip_image(
            self._state, direction=FlipDirection.VERTICAL
        )
        self._update_state(new_state)
        return new_state

    def reset_transformations(self) -> ImageState:
        """Reset transformations and return new state."""
        new_state = self._command_processor.reset_transformations(self._state)
        self._update_state(new_state)
        return new_state

    def add_img_correction(self, correction, name=None) -> ImageState:
        """Add image correction and return new state."""
        new_state = self._command_processor.add_correction(
            self._state, correction=correction, name=name
        )
        self._update_state(new_state)
        return new_state

    def set_factor(self, factor: float) -> ImageState:
        """Set processing factor and return new state."""
        new_state = self._command_processor.set_factor(self._state, factor=factor)
        self._update_state(new_state)
        return new_state

    def set_background_scaling(self, scaling: float) -> ImageState:
        """Set background scaling and return new state."""
        new_state = self._command_processor.set_background_scaling(
            self._state, scaling=scaling
        )
        self._update_state(new_state)
        return new_state

    def set_background_offset(self, offset: float) -> ImageState:
        """Set background offset and return new state."""
        new_state = self._command_processor.set_background_offset(
            self._state, offset=offset
        )
        self._update_state(new_state)
        return new_state

    def set_autoprocess(self, autoprocess: bool) -> ImageState:
        """Set autoprocess flag and return new state."""
        new_state = self._command_processor.set_autoprocess(
            self._state, autoprocess=autoprocess
        )
        self._update_state(new_state)
        self.auto_processor.autoprocess = autoprocess
        return new_state

    # Transfer function methods
    def enable_transfer_function(self) -> ImageState:
        """Enable transfer function correction and return new state."""
        new_state = self._command_processor.enable_transfer_function(self._state)
        self._update_state(new_state)
        return new_state

    def disable_transfer_function(self) -> ImageState:
        """Disable transfer function correction and return new state."""
        new_state = self._command_processor.disable_transfer_function(self._state)
        self._update_state(new_state)
        return new_state

    def load_transfer_function_original(self, filename: str) -> ImageState:
        """Load original image for transfer function and return new state."""
        new_state = self._command_processor.load_transfer_function_original(
            self._state, filename
        )
        self._update_state(new_state)
        return new_state

    def load_transfer_function_response(self, filename: str) -> ImageState:
        """Load response image for transfer function and return new state."""
        new_state = self._command_processor.load_transfer_function_response(
            self._state, filename
        )
        self._update_state(new_state)
        return new_state

    def reset_transfer_function(self) -> ImageState:
        """Reset transfer function data and return new state."""
        new_state = self._command_processor.reset_transfer_function(self._state)
        self._update_state(new_state)
        return new_state

    # Navigation methods (delegate to navigator)

    def load_next_file(self, step=1, pos=None) -> Optional[ImageState]:
        """Load the next file based on iteration mode."""
        next_file_name = self.navigator.get_next_filename(step=step, pos=pos)
        if next_file_name is not None:
            return self.load(next_file_name)
        return None

    def load_previous_file(self, step=1, pos=None) -> Optional[ImageState]:
        """Load the previous file based on iteration mode."""
        previous_file_name = self.navigator.get_previous_filename(step=step, pos=pos)
        if previous_file_name is not None:
            return self.load(previous_file_name)
        return None

    def set_file_iteration_mode(self, mode) -> ImageState:
        """Set file iteration mode and return new state."""
        self.navigator.set_file_iteration_mode(mode)
        new_state = self._command_processor.set_file_iteration_mode(
            self._state, mode=mode
        )
        self._update_state(new_state)
        return new_state

    # Computed Properties (derived from state)

    @property
    def img_data(self) -> Optional[np.ndarray]:
        """Get corrected image data (computed from state)."""
        return self._command_processor.corrector.get_corrected_img_data(
            self._state.raw_image_data,
            self._state.background_data,
            self._state.background_scaling,
            self._state.background_offset,
            self._state.factor,
            self._state.transfer_function_enabled,
            self._state.transfer_function_original_data,
            self._state.transfer_function_response_data,
        )

    @property
    def raw_img_data(self) -> Optional[np.ndarray]:
        """Get raw image data from state."""
        return self._state.raw_image_data

    @property
    def background_data(self) -> Optional[np.ndarray]:
        """Get background data from state."""
        return self._state.background_data

    @property
    def factor(self) -> float:
        """Get processing factor from state."""
        return self._state.factor

    @property
    def autoprocess(self) -> bool:
        """Get autoprocess flag from state."""
        return self._state.autoprocess

    @property
    def filename(self) -> str:
        """Get current filename from state."""
        return self._state.filename

    @property
    def series_pos(self) -> int:
        """Get series position from state."""
        return self._state.series_pos

    @property
    def series_max(self) -> int:
        """Get series maximum from state."""
        return self._state.series_max

    @property
    def file_iteration_mode(self) -> str:
        """Get file iteration mode from state."""
        return self._state.file_iteration_mode

    @property
    def background_filename(self) -> str:
        """Get background filename from state."""
        return self._state.background_filename

    @property
    def background_scaling(self) -> float:
        """Get background scaling from state."""
        return self._state.background_scaling

    @property
    def background_offset(self) -> float:
        """Get background offset from state."""
        return self._state.background_offset

    @property
    def img_transformations(self) -> list:
        """Get transformation list from state."""
        return self._state.transformations

    @property
    def img_corrections(self):
        """Get corrections from command processor."""
        return self._command_processor.corrector.img_corrections

    # State serialization methods

    def get_state(self) -> ImageState:
        """Get current state (alias for .state property)."""
        return self._state

    def _apply_transformations(self, state: ImageState) -> ImageState:
        """Apply transformations to the given state."""
        if state.raw_image_data is None:
            return state

        # Apply transformations to image data
        transformed_img = state.raw_image_data.copy()
        for transformation_name in state.transformations:
            if transformation_name == "rotate_matrix_p90":
                transformed_img = self._command_processor.transformer.rotate_img_p90(
                    transformed_img, None
                )[0]
            elif transformation_name == "rotate_matrix_m90":
                transformed_img = self._command_processor.transformer.rotate_img_m90(
                    transformed_img, None
                )[0]
            elif transformation_name == "flipud":
                transformed_img = np.flipud(transformed_img)
            elif transformation_name == "fliplr":
                transformed_img = np.fliplr(transformed_img)

        # Apply transformations to background data
        transformed_background = (
            self._command_processor.transformer._perform_img_transformations(
                state.background_data
            )
        )
        return state.copy(
            raw_image_data=transformed_img, background_data=transformed_background
        )

    # Legacy compatibility methods (for backward compatibility)

    def has_background(self) -> bool:
        """Check if background data is available."""
        return self._state.background_data is not None

    def has_corrections(self) -> bool:
        """Check if corrections are active."""
        return self._command_processor.corrector.has_corrections()

    def get_transformations_string_list(self) -> list:
        """Get list of transformation names."""
        return self._state.transformations

    def load_transformations_string_list(self, transformations) -> ImageState:
        """Load transformations from string list and return new state."""
        new_state = self._command_processor.set_transformations(
            self._state, transformations=transformations
        )
        self._update_state(new_state)
        return new_state

    def blockSignals(self, block=True):
        """Block all signals."""
        for member in vars(self):
            attr = getattr(self, member)
            if isinstance(attr, Signal):
                attr.blocked = block
