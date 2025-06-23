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
Image processing package for Dioptas.

This package contains all image-related functionality including:
- Image data management and loading
- Image transformations and corrections
- File navigation and auto-processing
- State-based architecture with improved testability

Package Structure:
├── Core Components (New Architecture)
│   ├── ImageState: Immutable state container
│   ├── ImageCommands: Type-safe command operations
│   ├── ImageModelRefactored: New model with explicit state access
│   └── ImageModelAdapter: Backward compatibility adapter
└── Tests
    ├── test_refactored.py: Core component tests
    ├── test_adapter.py: Adapter compatibility tests
    └── test_transfer_function.py: Transfer function tests
"""

# =============================================================================
# Core Components
# =============================================================================

from .ImageState import ImageState
from .ImageCommands import (
    ImageCommandProcessor, 
    RotationDirection, 
    FlipDirection,
    BackgroundDimensionWrongException
)
from .ImageModel import ImageModel



# =============================================================================
# Public API
# =============================================================================

__all__ = [
    # Core components (recommended for new code)
    'ImageState',
    'ImageCommandProcessor',
    'RotationDirection',
    'FlipDirection',
    'ImageModel',
    'NewBackgroundDimensionWrongException',
]

# =============================================================================
# Version and compatibility information
# =============================================================================

__version__ = "2.0.0"
__architecture__ = "state-based"

def get_architecture_info():
    """Get information about the current architecture."""
    return {
        "version": __version__,
        "architecture": __architecture__,
        "recommended_model": "ImageModelRefactored",
        "backward_compatible": "ImageModelAdapter",
        "deprecated": "ImageModel",
        "migration_guide": "docs/MIGRATION_GUIDE.md",
        "benefits": "docs/REFACTORING_BENEFITS.md"
    } 