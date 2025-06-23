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
ImageState - Immutable state container for image data and metadata.

This class represents the complete state of an image model, including:
- Image data and metadata
- Background data and settings
- Transformations
- Corrections
- File navigation state
- Auto-processing settings
"""

import datetime
import numpy as np
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from ..util.ImgCorrection import ImgCorrectionInterface


@dataclass(frozen=True)
class ImageState:
    """
    Immutable state container for image data and metadata.

    This class uses dataclass with frozen=True to ensure immutability.
    All state changes create new instances rather than modifying existing ones.
    """

    # Version information
    version: str = "3.0"
    timestamp: str = field(default_factory=lambda: datetime.datetime.now().isoformat())

    # Core image data
    raw_image_data: Optional[np.ndarray] = None
    background_data: Optional[np.ndarray] = None

    # File and navigation state
    filename: str = ""
    background_filename: str = ""
    series_pos: int = 1
    series_max: int = 1
    file_iteration_mode: str = "number"
    selected_source: str = ""

    # Processing parameters
    factor: float = 1.0
    background_scaling: float = 1.0
    background_offset: float = 0.0

    # Transformations
    transformations: List[str] = field(default_factory=list)

    # Corrections
    corrections: Dict[str, ImgCorrectionInterface] = field(default_factory=dict)

    # Auto-processing
    autoprocess: bool = False
    directory_path: str = ""

    # Metadata
    file_info: Dict[str, Any] = field(default_factory=dict)
    motors_info: Dict[str, Any] = field(default_factory=dict)
    sources: List[str] = field(default_factory=list)

    # Transfer function state
    transfer_function_enabled: bool = False
    transfer_function_original_filename: Optional[str] = None
    transfer_function_response_filename: Optional[str] = None
    transfer_function_original_data: Optional[np.ndarray] = None
    transfer_function_response_data: Optional[np.ndarray] = None

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert state to a dictionary for serialization.

        Note: numpy arrays are converted to lists for JSON serialization.
        """
        state_dict = {}

        # Copy all fields, handling numpy arrays specially
        for field_name, field_value in self.__dict__.items():
            if isinstance(field_value, np.ndarray):
                state_dict[field_name] = field_value.tolist()
            else:
                state_dict[field_name] = field_value

        return state_dict

    @classmethod
    def from_dict(cls, state_dict: Dict[str, Any]) -> "ImageState":
        """
        Create state from a dictionary (for deserialization).

        Args:
            state_dict: Dictionary representation of state

        Returns:
            New ImageState instance
        """
        # Convert lists back to numpy arrays where appropriate
        processed_dict = {}
        numpy_fields = {
            "raw_image_data",
            "background_data",
            "transfer_function_original_data",
            "transfer_function_response_data",
        }

        for field_name, field_value in state_dict.items():
            if field_name in numpy_fields and field_value is not None:
                processed_dict[field_name] = np.array(field_value)
            else:
                processed_dict[field_name] = field_value

        return cls(**processed_dict)

    def copy(self, **kwargs) -> "ImageState":
        """
        Create a copy of this state with optional changes.

        Args:
            **kwargs: Fields to change in the new state

        Returns:
            New ImageState instance with the specified changes
        """
        return ImageState(**{**self.__dict__, **kwargs})
