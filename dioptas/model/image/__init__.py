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
- Image data management
- Image loading from various formats
- Image transformations
- Image corrections and processing
- File navigation
- Auto-processing
"""

from .ImageDataManager import ImageDataManager
from .ImageLoader import ImageLoader
from .FileNavigator import FileNavigator
from .ImageTransformer import ImageTransformer
from .ImageCorrector import ImageCalculator
from .AutoProcessor import AutoProcessor
from .ImageModel import ImageModel, BackgroundDimensionWrongException

__all__ = [
    'ImageDataManager',
    'ImageLoader', 
    'FileNavigator',
    'ImageTransformer',
    'ImageCalculator',
    'AutoProcessor',
    'ImageModel',
    'BackgroundDimensionWrongException',
] 