# -*- coding: utf8 -*-
# Dioptas - GUI program for fast processing of 2D X-ray data
# Copyright (C) 2017  Clemens Prescher (clemens.prescher@gmail.com)
# Institute for Geology and Mineralogy, University of Cologne
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

import numpy as np

s2pi = np.sqrt(2 * np.pi)
def gaussian(x, amplitude=1.0, center=0.0, sigma=1.0):
    """1 dimensional gaussian:
    gaussian(x, amplitude, center, sigma)
    """
    return (amplitude / (s2pi * sigma)) * np.exp(-(1.0 * x - center) ** 2 / (2 * sigma ** 2))

