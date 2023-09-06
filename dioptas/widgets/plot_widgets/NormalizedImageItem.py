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

from __future__ import absolute_import

from contextlib import contextmanager
from typing import Optional

import numpy as np
import pyqtgraph as pg


class Normalization:
    """Class defining the interface for implementing normalizations"""

    @staticmethod
    def apply(data: np.ndarray) -> np.ndarray:
        """Forward conversion of data to normalized data"""
        raise NotImplementedError()

    @staticmethod
    def revert(data: np.ndarray) -> np.ndarray:
        """Backward conversion of normalized data to data"""
        raise NotImplementedError()

    @staticmethod
    def invalid(data: np.ndarray) -> np.ndarray:
        """Returns True for data that cannot be normalized"""
        return np.zeros(data.shape, dtype=bool)


class LinearNormalization(Normalization):
    @staticmethod
    def apply(data: np.ndarray) -> np.ndarray:
        return data

    @staticmethod
    def revert(data: np.ndarray) -> np.ndarray:
        return data


class LogNormalization(Normalization):
    @staticmethod
    def apply(data: np.ndarray) -> np.ndarray:
        return np.log10(data)

    @staticmethod
    def revert(data: np.ndarray) -> np.ndarray:
        return np.power(10, data)

    @staticmethod
    def invalid(data: np.ndarray) -> np.ndarray:
        return data <= 0.0


class SqrtNormalization(Normalization):
    @staticmethod
    def apply(data: np.ndarray) -> np.ndarray:
        return np.sqrt(data)

    @staticmethod
    def revert(data: np.ndarray) -> np.ndarray:
        return data * data

    @staticmethod
    def invalid(data: np.ndarray) -> np.ndarray:
        return data < 0.0


class NormalizedImageItem(pg.ImageItem):
    """pyqtgraph image item with support for data normalization"""

    _NORMALIZATIONS = {
        "linear": LinearNormalization(),
        "log": LogNormalization(),
        "sqrt": SqrtNormalization(),
    }
    """Dict of normalization name: Normalization instances"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.__normalization = "linear"
        self.__rawImage = None

    def getData(self, copy: bool = True) -> Optional[np.ndarray]:
        """Returns the image data array

        :param copy: False to return the array used internally: do not modify!
        """
        if self.__rawImage is None:
            return None
        return np.array(self.__rawImage, copy=copy)

    def getNormalization(self) -> str:
        """Returns the currently used normalization"""
        return self.__normalization

    def setNormalization(self, normalization: str):
        """Set the data normalization to use"""
        if normalization not in self._NORMALIZATIONS:
            raise ValueError(f"Unsupported normalization: {normalization}")

        if normalization == self.__normalization:
            return

        # Get levels **before** changing the normalization
        levels = self.getLevels()
        self.__normalization = normalization
        self.setImage(image=self.__rawImage, levels=levels)

    def _getNorm(self) -> Normalization:
        return self._NORMALIZATIONS[self.getNormalization()]

    def setImage(self, image=None, *args, **kwargs):
        if image is None:
            return super().setImage(None, *args, **kwargs)

        self.__rawImage = image
        normalizedImage = self._getNorm().apply(image)
        return super().setImage(normalizedImage, *args, **kwargs)

    def getLevels(self):
        levels = super().getLevels()
        if levels is None:
            return None
        return self._getNorm().revert(levels)

    def setLevels(self, levels, update=True):
        if levels is None:
            return super().setLevels(levels, update)

        normalizedLevels = self._getNorm().apply(levels)
        return super().setLevels(normalizedLevels, update)

    @contextmanager
    def _useAsImage(self, image: Optional[np.ndarray]):
        """Context to temporarily use provided image as image attribute

        Used when calling ImageItem methods that needs to access a different
        image than the transformed one.
        """
        previousImage = self.image
        self.image = image
        try:
            yield
        finally:
            self.image = previousImage

    def quickMinMax(self, *args, **kwargs):
        with self._useAsImage(self.__rawImage):
            return super().quickMinMax(*args, **kwargs)

    def getHistogram(self, *args, **kwargs):
        with self._useAsImage(self.__rawImage):
            return super().getHistogram(*args, **kwargs)
