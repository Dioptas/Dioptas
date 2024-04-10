# -*- coding: utf-8 -*-
# Dioptas - GUI program for fast processing of 2D X-ray data
# Copyright (C) 2019 Clemens Prescher (clemens.prescher@gmail.com)
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

from qtpy import QtCore
import numpy as np
import re

from xypattern import Pattern

from .BatchModel import BatchModel


class MapModel(BatchModel):
    """
    Model for 2D maps from multiple pattern.
    """
    map_changed = QtCore.Signal()
    map_cleared = QtCore.Signal()
    map_problem = QtCore.Signal()
    roi_problem = QtCore.Signal()

    def __init__(self, configuration):
        super(MapModel, self).__init__(configuration)

        self.map = Map()
        self.theta_center = 5.9
        self.theta_range = 0.

        self.rois = []
        self.roi_math = ''

        self.possible_dimensions = []
        self.dimension_index = 0

        # Background for image
        self.bg_image = np.zeros([1920, 1200])

    def reset(self):
        self.reset_data()
        self.map.reset()
        self.reset_rois()
        self.possible_dimensions = []
        self.map_cleared.emit()

    def load_img_map(self, filenames, callback_fn=None):
        self.set_image_files(filenames)
        self.integrate_raw_data(0, len(filenames), 1, use_all=True, callback_fn=callback_fn)

        self.configuration.img_model.blockSignals(True)

        for n in range(self.data.shape[0]):
            self.add_map_point(None, Pattern(self.binning, self.data[n, :]), img_filename=filenames[n])

        self.possible_dimensions = find_possible_dimensions(self.data.shape[0])
        self.map.set_manual_positions(0, 0, 1, 1, self.possible_dimensions[0][0], self.possible_dimensions[0][1], True)

        self.configuration.img_model.blockSignals(False)

    def add_map_point(self, pattern_filename, pattern, position=None, img_filename=None):
        """
        Adds a Point to the map.
        :param pattern_filename: filename of the corresponding map
        :param pattern: Pattern object containing the x and y values of the integrated pattern
        :type pattern: Pattern
        :param position: tuple with x and y position
        :param img_filename: corresponding img filename
        """
        self.map.add_point(pattern_filename, pattern, position, img_filename)

    def add_roi(self, start, end, name=''):
        self.rois.append(Roi(start, end, name))

    def reset_rois(self):
        self.rois = []
        self.roi_math = ''

    def calculate_map_data(self):
        """
        Calculates the ROI math and creates the map image.
        """
        self.map.prepare()

        for point in self.map:
            sum_roi = {}
            for roi in self.rois:
                indices_in_roi = roi.ind_in_roi(point.x_data)
                sum_roi[roi.name] = np.sum(point.y_data[indices_in_roi])

            try:
                current_math = self.calculate_roi_math(sum_roi)
            except SyntaxError:  # needed in case of problem with math
                return

            self.map.set_image_intensity(point.position, current_math)
        self.map_changed.emit()

    def create_simple_summing_roi_math(self):
        """
        Sets the roi_math to be summing of all ROIs.
        """
        self.roi_math = '+'.join([roi.name for roi in self.rois])

    def check_roi_math(self):
        """
        Returns: False if a ROI in the math string is missing from the Rois
        """
        names_in_roi_math = re.findall('([a-zA-Z]+)', self.roi_math)
        for name in names_in_roi_math:
            if name not in [roi.name for roi in self.rois]:
                return False
        return True

    def calculate_roi_math(self, sum_int):
        """
        Evaluates current_roi_math by replacing each ROI name with the sum of the values in that range
        :param sum_int: dictionary with ROI names as key and there respective integral sums as values
        :return: the result of the roi_math equation
        """
        if self.roi_math == '':
            self.create_simple_summing_roi_math()
        current_roi_math = self.roi_math
        for roi_letter in sum_int:
            current_roi_math = current_roi_math.replace(roi_letter, str(sum_int[roi_letter]))
        return eval(current_roi_math)

    def is_empty(self):
        return len(self.map) == 0


class Map:
    def __init__(self):
        self.points = []  # list of MapPoints
        self.sorted_points = []  # list of (points index, x, y)
        self.sorted_map = []  # list of point indices, xs, ys (has a length of 3)

        self.px_per_point_x = 100
        self.px_per_point_y = 100

    def add_point(self, pattern_filename, pattern, position=None, img_filename=None):
        """
        Adds a Point to the map
        :param pattern_filename: filename of the corresponding map
        :param pattern: Pattern object containing the x and y values of the integrated pattern
        :type pattern: Pattern
        :param position: tuple with x and y position
        :param img_filename: corresponding img filename
        """
        self.points.append(MapPoint(pattern_filename, pattern, position, img_filename))

    def prepare(self):
        """
        Prepares the map for inserting intensities
        """
        self._sort_points()
        self._get_map_dimensions()
        self._create_empty_map()

    def _sort_points(self):
        """
        Sorts the current points according to x and y positions and saves them in the sorted_points variable.
        """
        datalist = []
        for ind, point in enumerate(self.points):
            datalist.append([ind, point.position[0], point.position[1]])

        self.sorted_points = sorted(datalist, key=lambda x: (x[1], x[2]))
        self.sorted_map = [[row[i] for row in self.sorted_points] for i in range(len(self.sorted_points[1]))]

    def _get_map_dimensions(self):
        """
        Uses the sorted points and map to estimate minimum x and y position, the differences between points
        """
        self.min_x = self.sorted_map[1][0]
        self.min_y = self.sorted_map[2][0]

        self.num_x = self.sorted_map[2].count(self.min_y)
        self.num_y = self.sorted_map[1].count(self.min_x)

        self.diff_x = self.sorted_points[self.num_y][1] - self.sorted_points[0][1]
        self.diff_y = self.sorted_points[1][2] - self.sorted_points[0][2]

    def _create_empty_map(self):
        """
        Uses the estimated map dimension to calculate
        """
        self.hor_size = self.px_per_point_x * self.num_x
        self.ver_size = self.px_per_point_y * self.num_y

        self.um_per_px_in_x = self.diff_x / self.px_per_point_x
        self.um_per_px_in_y = self.diff_y / self.px_per_point_y

        self.new_image = np.zeros([self.hor_size, self.ver_size])

    def all_positions_defined(self):
        for point in self.points:
            if point.position is None:
                return False
        return True

    def sort_points_by_name(self):
        """
        Returns:
            sorted_datalist: a list of all the map files, sorted by natural filename
        """
        return sorted(self.points, key=lambda point: [int(t) if t.isdigit() else t.lower() for t in
                                                      re.split('(\\d+)', point.pattern_filename)])

    def set_manual_positions(self, min_x, min_y, diff_x, diff_y, num_x, num_y, is_hor_first):
        """
        Args:
            min_x: Horizontal minimum position
            min_y: Vertical minimum position
            diff_x: Step in horizontal
            diff_y: Step in vertical
            num_x: Number of horizontal positions
            num_y: Number of vertical positions
            is_hor_first: True of horizontal changes first between files, False if vertical

        """
        x_grid = np.linspace(min_x, min_x + diff_x * (num_x - 1), num_x)
        y_grid = np.linspace(min_y, min_y + diff_y * (num_y - 1), num_y)

        ind = 0
        if is_hor_first:
            for y in y_grid:
                for x in x_grid:
                    self.points[ind].position = (x, y)
                    ind += 1
        else:
            for x in x_grid:
                for y in y_grid:
                    self.points[ind].position = (x, y)
                    ind += 1

        self.min_x = min_x
        self.min_y = min_y

        self.num_x = num_x
        self.num_y = num_y

        self.diff_x = diff_x
        self.diff_y = diff_y

        self._create_empty_map()
        self.positions_set_manually = True

    def set_image_intensity(self, position, intensity):
        range_hor = self.pos_to_range(position[0], self.min_x, self.px_per_point_x, self.diff_x)
        range_ver = self.pos_to_range(position[1], self.min_y, self.px_per_point_y, self.diff_y)
        self.new_image[range_hor, range_ver] = intensity

    def pos_to_range(self, pos, min_pos, px_per_point, diff_pos):
        """
        Args:
            pos: x or y position of point
            min_pos: minimum x or y value map position
            px_per_point: pixels to draw for each map point in the corresponding direction
            diff_pos: difference in corresponding direction between subsequent map files
        Returns:
            pos_range: a slice with the start and end pixels for drawing the current map file
        """
        range_start = round((pos - min_pos) / diff_pos * px_per_point)
        range_end = round(range_start + px_per_point)
        pos_range = slice(int(range_start), int(range_end))
        return pos_range

    def position_from_xy(self, x, y):
        """gives the position in units for a point clicked in the x, y space"""
        hor = self.min_x + x // self.px_per_point_x * self.diff_x
        ver = self.min_y + y // self.px_per_point_y * self.diff_y
        return hor, ver

    def filenames_from_position(self, pos):
        """
        Gives the filenames for a certain position in the map
        :param pos: tuple horizontal and vertical position
        :return: (pattern_filename, image_filename)
        """
        for point in self.points:
            if abs(float(point.position[0]) - pos[0]) < 2E-4 and \
                    abs(point.position[1] - pos[1]) < 2E-4:
                return point.pattern_filename, point.img_filename
        return None, None
        # dist_sqr = {}
        # for filename, filedata in self.map_model.map_data.items():
        #     dist_sqr[filename] = abs(float(filedata['pos_hor']) - hor) ** 2 + abs(float(filedata['pos_ver']) - ver) ** 2
        #
        # return min(dist_sqr, key=dist_sqr.get)

    def is_empty(self):
        return len(self.points) == 0

    def __getitem__(self, index):
        return self.points[index]

    def __len__(self):
        return len(self.points)

    def reset(self):
        self.points = []
        self.sorted_points = []
        self.sorted_map = []


class MapPoint:
    def __init__(self, pattern_filename, pattern, position=None, img_filename=None):
        """
        Defines a point in a map.
        :param pattern_filename: corresponding pattern filename
        :param pattern: corresponding pattern
        :type pattern: Pattern
        :param position: tuple with the position of the map (x, y)
        :param img_filename: corresponding image filename
        """
        self.pattern_filename = pattern_filename
        self.x_data = pattern.x
        self.y_data = pattern.y
        self.position = position
        self.img_filename = img_filename


class Roi:
    def __init__(self, start, end, name=None):
        """
        Defines a ROI
        :param start: start_value of the ROI
        :param end: end_value of the ROI
        :param name: name of the ROI
        """
        self.start = start
        self.end = end
        self.name = name

    def is_in_roi(self, x):
        """
        whether value x is in the ROI
        :param x: x-value
        :type x: float
        :return: True or False
        :rtype: bool
        """
        return self.start < x < self.end

    def ind_in_roi(self, x_array):
        """
        Gets the indices of a numpy array which are in the ROI
        :param x_array: a numpy array
        :return: list of indices
        """
        return np.where((x_array > self.start) & (x_array < self.end))[0]

    @property
    def center(self):
        return self.range / 2 + self.start

    @property
    def range(self):
        return self.end - self.start


def find_possible_dimensions(num_points):
    dimension_pairs = []
    for n in range(1, int(np.floor(np.sqrt(num_points + 1))) + 1):
        if num_points % n == 0:
            dim1 = n
            dim2 = num_points // n
            dimension_pairs.append((dim1, dim2))
            if dim1 != dim2:
                dimension_pairs.append((dim2, dim1))
    dimension_pairs.sort(key=lambda x: ((x[0]+x[1])/2 - np.sqrt(num_points)) ** 2)
    return dimension_pairs
