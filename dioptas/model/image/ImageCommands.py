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
from abc import ABC, abstractmethod
from typing import Optional, Any
from enum import Enum

from .ImageState import ImageState
from .ImageLoader import ImageLoader
from .ImageTransformer import ImageTransformer
from .ImageCalculator import ImageCalculator
from ..util.ImgCorrection import ImgCorrectionInterface

logger = logging.getLogger(__name__)


class RotationDirection(Enum):
    """Enum for rotation directions."""

    PLUS_90 = "p90"
    MINUS_90 = "m90"


class FlipDirection(Enum):
    """Enum for flip directions."""

    HORIZONTAL = "horizontal"
    VERTICAL = "vertical"


class ImageCommand(ABC):
    """Abstract base class for image operations."""

    @abstractmethod
    def execute(self, state: ImageState, **kwargs) -> ImageState:
        """Execute the command and return new state."""
        pass


class LoadImageCommand(ImageCommand):
    """Command to load an image file."""

    def __init__(self, loader: ImageLoader):
        self.loader = loader

    def execute(self, state: ImageState, filename: str, pos: int = 0) -> ImageState:
        """Load image and return updated state."""
        logger.info(f"Loading {filename}.")

        # Load image data
        image_file_data = self.loader.get_image_data(filename, pos)

        # Create new state with loaded data
        new_state = state.copy(
            filename=filename,
            raw_image_data=image_file_data.get("img_data"),
            file_info=image_file_data.get("file_info", ""),
            motors_info=image_file_data.get("motors_info", {}),
            series_pos=pos + 1,
            sources=image_file_data.get("sources"),
        )

        return new_state


class LoadBackgroundCommand(ImageCommand):
    """Command to load background image."""

    def __init__(self, loader: ImageLoader, transformer: ImageTransformer):
        self.loader = loader
        self.transformer = transformer

    def execute(self, state: ImageState, filename: str) -> ImageState:
        """Load background and return updated state."""
        background_data = self.loader.get_image_data(filename)["img_data"]

        # Apply transformations to background
        background_data = self.transformer._perform_img_transformations(background_data)

        # Check dimensions
        if (
            state.raw_image_data is not None
            and background_data is not None
            and background_data.shape != state.raw_image_data.shape
        ):
            raise BackgroundDimensionWrongException()

        new_state = state.copy(
            background_filename=filename, background_data=background_data
        )

        return new_state


class ResetBackgroundCommand(ImageCommand):
    """Command to reset background."""

    def execute(self, state: ImageState) -> ImageState:
        """Reset background and return updated state."""
        return state.copy(background_data=None, background_filename=None)


class RotateImageCommand(ImageCommand):
    """Command to rotate image."""

    def __init__(self, transformer: ImageTransformer):
        self.transformer = transformer

    def execute(self, state: ImageState, direction: RotationDirection) -> ImageState:
        """Rotate image and return updated state."""
        if state.raw_image_data is None:
            return state

        if direction == RotationDirection.PLUS_90:
            transformed_img, transformed_background = self.transformer.rotate_img_p90(
                state.raw_image_data, state.background_data
            )
        elif direction == RotationDirection.MINUS_90:
            transformed_img, transformed_background = self.transformer.rotate_img_m90(
                state.raw_image_data, state.background_data
            )
        else:
            raise ValueError(f"Unknown rotation direction: {direction}")

        new_state = state.copy(
            raw_image_data=transformed_img,
            background_data=transformed_background,
            transformations=self.transformer.get_transformations_string_list(),
        )

        return new_state


class FlipImageCommand(ImageCommand):
    """Command to flip image."""

    def __init__(self, transformer: ImageTransformer):
        self.transformer = transformer

    def execute(self, state: ImageState, direction: FlipDirection) -> ImageState:
        """Flip image and return updated state."""
        if state.raw_image_data is None:
            return state

        if direction == FlipDirection.HORIZONTAL:
            transformed_img, transformed_background = (
                self.transformer.flip_img_horizontally(
                    state.raw_image_data, state.background_data
                )
            )
        elif direction == FlipDirection.VERTICAL:
            transformed_img, transformed_background = (
                self.transformer.flip_img_vertically(
                    state.raw_image_data, state.background_data
                )
            )
        else:
            raise ValueError(f"Unknown flip direction: {direction}")

        new_state = state.copy(
            raw_image_data=transformed_img,
            background_data=transformed_background,
            transformations=self.transformer.get_transformations_string_list(),
        )

        return new_state


class ResetTransformationsCommand(ImageCommand):
    """Command to reset transformations."""

    def __init__(self, transformer: ImageTransformer):
        self.transformer = transformer

    def execute(self, state: ImageState) -> ImageState:
        """Reset transformations and return updated state."""

        reset_img, reset_background = self.transformer.reset_img_transformations(
            state.raw_image_data, state.background_data
        )

        return state.copy(
            raw_image_data=reset_img,
            background_data=reset_background,
            transformations=self.transformer.get_transformations_string_list(),
        )


class AddCorrectionCommand(ImageCommand):
    """Command to add image correction."""

    def __init__(self, corrector: ImageCalculator):
        self.corrector = corrector

    def execute(
        self, state: ImageState, correction: ImgCorrectionInterface, name: Optional[str] = None
    ) -> ImageState:
        """Add correction and return updated state."""
        # This would need to be implemented based on how corrections are serialized
        # For now, we'll just update the corrections dict
        corrections = state.corrections.copy()
        if name:
            corrections[name] = correction

        new_state = state.copy(corrections=corrections)
        return new_state


class SetParameterCommand(ImageCommand):
    """Command to set various parameters."""

    def execute(self, state: ImageState, **params) -> ImageState:
        """Set parameters and return updated state."""
        return state.copy(**params)


class ImageCommandProcessor:
    """Processes commands with proper type safety."""

    def __init__(self):
        self.loader = ImageLoader()
        self.transformer = ImageTransformer()
        self.corrector = ImageCalculator()

        # Initialize commands
        self._load_image = LoadImageCommand(self.loader)
        self._load_background = LoadBackgroundCommand(self.loader, self.transformer)
        self._reset_background = ResetBackgroundCommand()
        self._rotate_image = RotateImageCommand(self.transformer)
        self._flip_image = FlipImageCommand(self.transformer)
        self._reset_transformations = ResetTransformationsCommand(self.transformer)
        self._add_correction = AddCorrectionCommand(self.corrector)
        self._set_parameter = SetParameterCommand()

    # Type-safe command methods

    def load_image(self, state: ImageState, filename: str, pos: int = 0) -> ImageState:
        """Load an image file."""
        return self._load_image.execute(state, filename=filename, pos=pos)

    def load_background(self, state: ImageState, filename: str) -> ImageState:
        """Load background image."""
        return self._load_background.execute(state, filename=filename)

    def reset_background(self, state: ImageState) -> ImageState:
        """Reset background."""
        return self._reset_background.execute(state)

    def rotate_image(
        self, state: ImageState, direction: RotationDirection
    ) -> ImageState:
        """Rotate image."""
        return self._rotate_image.execute(state, direction=direction)

    def flip_image(self, state: ImageState, direction: FlipDirection) -> ImageState:
        """Flip image."""
        return self._flip_image.execute(state, direction=direction)

    def reset_transformations(self, state: ImageState) -> ImageState:
        """Reset transformations."""
        return self._reset_transformations.execute(state)

    def add_correction(
        self, state: ImageState, correction: Any, name: Optional[str] = None
    ) -> ImageState:
        """Add image correction."""
        return self._add_correction.execute(state, correction=correction, name=name)

    def set_parameter(self, state: ImageState, **params) -> ImageState:
        """Set parameters."""
        return self._set_parameter.execute(state, **params)

    # Convenience methods for common operations

    def set_factor(self, state: ImageState, factor: float) -> ImageState:
        """Set processing factor."""
        return self.set_parameter(state, factor=factor)

    def set_background_scaling(self, state: ImageState, scaling: float) -> ImageState:
        """Set background scaling."""
        return self.set_parameter(state, background_scaling=scaling)

    def set_background_offset(self, state: ImageState, offset: float) -> ImageState:
        """Set background offset."""
        return self.set_parameter(state, background_offset=offset)

    def set_autoprocess(self, state: ImageState, autoprocess: bool) -> ImageState:
        """Set autoprocess flag and return new state."""
        return state.copy(autoprocess=autoprocess)

    def set_file_iteration_mode(self, state: ImageState, mode: str) -> ImageState:
        """Set file iteration mode and return new state."""
        return state.copy(file_iteration_mode=mode)

    def set_transformations(
        self, state: ImageState, transformations: list
    ) -> ImageState:
        """Set transformations list and return new state."""
        return state.copy(transformations=transformations)

    # Transfer function commands
    def enable_transfer_function(self, state: ImageState) -> ImageState:
        """Enable transfer function correction and return new state."""
        if (
            state.transfer_function_original_data is not None
            and state.transfer_function_response_data is not None
        ):
            return state.copy(transfer_function_enabled=True)
        return state

    def disable_transfer_function(self, state: ImageState) -> ImageState:
        """Disable transfer function correction and return new state."""
        return state.copy(transfer_function_enabled=False)

    def load_transfer_function_original(
        self, state: ImageState, filename: str
    ) -> ImageState:
        """Load original image for transfer function and return new state."""
        try:
            original_data = self.loader.get_image_data(filename)["img_data"]
            return state.copy(
                transfer_function_original_filename=filename,
                transfer_function_original_data=original_data,
            )
        except Exception as e:
            logger.error(f"Failed to load transfer function original image: {e}")
            return state

    def load_transfer_function_response(
        self, state: ImageState, filename: str
    ) -> ImageState:
        """Load response image for transfer function and return new state."""
        try:
            response_data = self.loader.get_image_data(filename)["img_data"]
            return state.copy(
                transfer_function_response_filename=filename,
                transfer_function_response_data=response_data,
            )
        except Exception as e:
            logger.error(f"Failed to load transfer function response image: {e}")
            return state

    def reset_transfer_function(self, state: ImageState) -> ImageState:
        """Reset transfer function data and return new state."""
        return state.copy(
            transfer_function_enabled=False,
            transfer_function_original_filename=None,
            transfer_function_response_filename=None,
            transfer_function_original_data=None,
            transfer_function_response_data=None,
        )

    # Legacy string-based interface (deprecated)
    def execute(self, command_name: str, state: ImageState, **kwargs) -> ImageState:
        """Execute a command by name (deprecated - use typed methods instead)."""
        if command_name == "load_image":
            return self.load_image(state, kwargs["filename"], kwargs.get("pos", 0))
        elif command_name == "load_background":
            return self.load_background(state, kwargs["filename"])
        elif command_name == "rotate_image":
            direction = RotationDirection(kwargs["direction"])
            return self.rotate_image(state, direction)
        elif command_name == "flip_image":
            direction = FlipDirection(kwargs["direction"])
            return self.flip_image(state, direction)
        elif command_name == "add_correction":
            return self.add_correction(state, kwargs["correction"], kwargs.get("name"))
        elif command_name == "set_parameter":
            return self.set_parameter(state, **kwargs)
        else:
            raise ValueError(f"Unknown command: {command_name}")


class BackgroundDimensionWrongException(Exception):
    """Exception raised when background dimensions don't match image dimensions."""

    pass
