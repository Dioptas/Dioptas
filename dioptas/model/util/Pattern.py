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
from scipy.interpolate import interp1d

from xypattern import Pattern as XYPattern

logger = logging.getLogger(__name__)


class Pattern(XYPattern):
    pass


def combine_patterns(patterns):
    x_min = []
    for pattern in patterns:
        x = pattern.x
        x_min.append(np.min(x))

    sorted_pattern_ind = np.argsort(x_min)

    pattern = patterns[sorted_pattern_ind[0]]
    for ind in sorted_pattern_ind[1:]:
        x1, y1 = pattern.data
        x2, y2 = patterns[ind].data

        pattern2_interp1d = interp1d(x2, y2, kind="linear")

        overlap_ind_pattern1 = np.where((x1 <= np.max(x2)) & (x1 >= np.min(x2)))[0]
        left_ind_pattern1 = np.where((x1 <= np.min(x2)))[0]
        right_ind_pattern2 = np.where((x2 >= np.max(x1)))[0]

        combined_x1 = x1[left_ind_pattern1]
        combined_y1 = y1[left_ind_pattern1]
        combined_x2 = x1[overlap_ind_pattern1]
        combined_y2 = (y1[overlap_ind_pattern1] + pattern2_interp1d(combined_x2)) / 2
        combined_x3 = x2[right_ind_pattern2]
        combined_y3 = y2[right_ind_pattern2]

        combined_x = np.hstack((combined_x1, combined_x2, combined_x3))
        combined_y = np.hstack((combined_y1, combined_y2, combined_y3))

        pattern = Pattern(combined_x, combined_y)
