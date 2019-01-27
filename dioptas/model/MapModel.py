from qtpy import QtCore
import os
import numpy as np
import re

from .util.Pattern import Pattern


class MapModel(QtCore.QObject):
    """
    Model for 2D maps from loading multiple images

    """
    map_changed = QtCore.Signal()
    map_cleared = QtCore.Signal()
    map_problem = QtCore.Signal()
    roi_problem = QtCore.Signal()
    map_images_loaded = QtCore.Signal()

    def __init__(self):
        """
        Defines all object variables and creates a dummy image.
        :return:
        """
        super(MapModel, self).__init__()

        self.map = Map()
        self.theta_center = 5.9
        self.theta_range = 0.05

        self.map_roi_list = []
        self.roi_math = ''
        self.roi_num = 0

        # Background for image
        self.bg_image = np.zeros([1920, 1200])

    def reset_map_data(self):
        self.map_data = {}
        self.all_positions_defined_in_files = False
        self.positions_set_manually = False
        self.map_organized = False
        self.map_cleared.emit()

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

    def prepare_map_data(self):
        """
        Calculates the ROI math and creates the map image
        """

        for map_item_name in self.map_data:
            wavelength = self.map_data[map_item_name]['wavelength']
            file_unit = self.map_data[map_item_name]['x_units']
            sum_int = {}

            for roi in self.map_roi_list:
                sum_int[roi['roi_letter']] = 0

            for x_val, y_val in zip(self.map_data[map_item_name]['x_data'], self.map_data[map_item_name]['y_data']):
                if not self.map_data[map_item_name]['x_units'] == self.units:
                    x_val = self.convert_units(x_val, file_unit, self.units, wavelength)
                roi_letters = self.is_val_in_roi_range(x_val)
                for roi_letter in roi_letters:
                    sum_int[roi_letter] += y_val

            try:
                current_math = self.calculate_roi_math(sum_int)
            except SyntaxError:  # needed in case of problem with math
                return

            range_hor = self.pos_to_range(float(self.map_data[map_item_name]['pos_hor']), self.min_hor,
                                          self.pix_per_hor, self.diff_hor)
            range_ver = self.pos_to_range(float(self.map_data[map_item_name]['pos_ver']), self.min_ver,
                                          self.pix_per_ver, self.diff_ver)
            self.new_image[range_hor, range_ver] = current_math

    def update_map(self):
        if not self.all_positions_defined_in_files and not self.positions_set_manually:
            self.map_problem.emit()
            return

        if not self.check_roi_math():
            return

        self.prepare_map_data()

        self.map_changed.emit()

    def check_roi_math(self):
        """
        Returns: False if a ROI in the math is missing from the list.
        """
        if self.roi_math == '':
            for item in self.map_roi_list:
                self.roi_math = self.roi_math + item['roi_letter'] + '+'
            self.roi_math = self.roi_math.rsplit('+', 1)[0]

        rois_in_roi_math = re.findall('([A-Z])', self.roi_math)
        for roi in rois_in_roi_math:
            if roi not in [r['roi_letter'] for r in self.map_roi_list]:
                self.roi_problem.emit()
                return False
        return True

    def is_val_in_roi_range(self, val):
        """

        Args:
            val: x_value (ttheta, q, or d)

        Returns: ROI letters, a list of ROIs containing x_value, or an empty list if not in any ROI in map_roi_list

        """
        roi_letters = []
        for item in self.map_roi_list:
            if float(item['roi_start']) < val < float(item['roi_end']):
                roi_letters.append(item['roi_letter'])
        return roi_letters

    def add_roi_to_roi_list(self, roi):
        self.map_roi_list.append(roi)

    def calculate_roi_math(self, sum_int):
        """
        evaluates current_roi_math by replacing each ROI letter with the sum of the values in that range
        Args:
            sum_int: dictionary containing the ROI letters

        Returns:
        evaluated current_roi_math
        """
        current_roi_math = self.roi_math
        for roi_letter in sum_int:
            current_roi_math = current_roi_math.replace(roi_letter, str(sum_int[roi_letter]))
        return eval(current_roi_math)

    def pos_to_range(self, pos, min_pos, pix_per_pos, diff_pos):
        """
        Args:
            pos: hor/ver position of current map file
            min_pos: minimum corresponding map position
            pix_per_pos: pixels to draw for each map position in the corresponding direction
            diff_pos: difference in corresponding position between subsequent map files

        Returns:
            pos_range: a slice with the start and end pixels for drawing the current map file
        """
        range_start = round((pos - min_pos) / diff_pos * pix_per_pos)
        range_end = round(range_start + pix_per_pos)
        pos_range = slice(range_start, range_end)
        return pos_range


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
        map_point = MapPoint(pattern_filename, pattern, position, img_filename)
        self.points.append(map_point)

    def sort_points(self):
        """
        Sorts the current points according to x and y positions and saves them in the sorted_points variable.
        """
        datalist = []
        for ind, point in enumerate(self.points):
            datalist.append([ind, point.position[0], point.position[1]])

        self.sorted_points = sorted(datalist, key=lambda x: (x[1], x[2]))
        self.sorted_map = [[row[i] for row in self.sorted_points] for i in range(len(self.sorted_points[1]))]

    def get_map_dimensions(self):
        """
        Uses the sorted points and map to estimate minimum x and y position, the differences between points
        """
        self.min_x = self.sorted_map[1][0]
        self.min_y = self.sorted_map[2][0]

        self.num_x = self.sorted_map[2].count(self.min_y)
        self.num_y = self.sorted_map[1].count(self.min_x)

        self.diff_x = self.sorted_points[self.num_y][1] - self.sorted_points[0][1]
        self.diff_y = self.sorted_points[1][2] - self.sorted_points[0][2]

    def create_empty_map(self):
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

    def sort_map_points_by_name(self):
        """
        Returns:
            sorted_datalist: a list of all the map files, sorted by natural filename
        """
        return sorted(self.points, key=lambda point: [int(t) if t.isdigit() else t.lower() for t in
                                                                 re.split('(\\d+)', point.pattern_filename)])

    def add_manual_map_positions(self, min_x, min_y, diff_x, diff_y, num_x, num_y, is_hor_first):
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

        self.create_empty_map()
        self.positions_set_manually = True

    def is_empty(self):
        return len(self.points) == 0

    def __getitem__(self, index):
        return self.points[index]

    @property
    def num_points(self):
        return len(self.points)

    def reset(self):
        self.points = []
        self.sorted_points = []
        self.sorted_map = []


class MapPoint:
    def __init__(self, pattern_filename,  pattern, position=None, img_filename=None):
        """
        Defines a point in a map.
        :param img_filename: corresponding image filename
        :param pattern_filename: corresponding pattern filename
        :param position: tuple with the position of the map (x, y)
        :param pattern: corresponding pattern
        :type pattern: Pattern
        """
        self.pattern_filename = pattern_filename
        self.x_data = pattern.x
        self.y_data = pattern.y
        self.position = position
        self.img_filename = img_filename


class RoiManager:
    def __init__(self):
        self.rois = [] # list of rois


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