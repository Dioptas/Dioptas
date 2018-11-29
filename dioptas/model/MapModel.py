from qtpy import QtCore
import os
import numpy as np
import re


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

        self.map_data = {}
        self.map_roi_list = []
        self.roi_math = ''
        self.theta_center = 5.9
        self.theta_range = 0.05
        self.num_hor = 0
        self.num_ver = 0
        self.roi_num = 0
        self.pix_per_hor = 100
        self.pix_per_ver = 100
        self.units = '2th_deg'
        self.wavelength = 3.344e-11
        self.all_positions_defined_in_files = False
        self.positions_set_manually = False
        self.map_uses_patterns = False
        self.are_map_files_organized = False

        # Background for image
        self.bg_image = np.zeros([1920, 1200])

    def reset_map_data(self):
        self.map_data = {}
        self.all_positions_defined_in_files = False
        self.positions_set_manually = False
        self.are_map_files_organized = False
        self.map_cleared.emit()

    def add_file_to_map_data(self, filepath, map_working_directory, motors_info):
        """
        Add a single file to map_data data structure, including all metadata
        Args:
            filepath: path to the original image file (needed for sending command to open the file when clicked)
            map_working_directory: Where the integrated patterns are saved
            motors_info: contains the horizontal/vertical positions needed for the map

        """
        if len(self.map_data) == 0:
            self.all_positions_defined_in_files = True
        base_filename = os.path.basename(filepath)
        self.map_data[filepath] = {}

        pattern_file_name = map_working_directory + '/' + os.path.splitext(base_filename)[0] + '.xy'

        self.map_data[filepath]['image_file_name'] = filepath.replace('\\', '/')
        self.map_data[filepath]['pattern_file_name'] = pattern_file_name
        self.read_map_file_data(filepath, pattern_file_name)
        try:
            self.map_data[filepath]['pos_hor'] = str(round(float(motors_info['Horizontal']), 3))
            self.map_data[filepath]['pos_ver'] = str(round(float(motors_info['Vertical']), 3))
        except (KeyError, TypeError):
            self.all_positions_defined_in_files = False

    def read_map_file_data(self, filepath, pattern_file_name):
        """
        Adds the x, y data to the map_data data structure, along with x_units and wavelength
        Args:
            filepath: used as a key to the data structure
            pattern_file_name: used to read from the actual file

        """
        pattern_file = pattern_file_name.replace('\\', '/')
        current_pattern_file = open(pattern_file, 'r')
        file_units = '2th_deg'
        wavelength = self.wavelength
        self.map_data[filepath]['x_data'] = []
        self.map_data[filepath]['y_data'] = []
        for line in current_pattern_file:
            if 'Wavelength:' in line:
                wavelength = float(line.split()[-1])
            elif '2th_deg' in line:
                file_units = '2th_deg'
            elif 'q_A^-1' in line:
                file_units = 'q_A^-1'
            elif 'd_A' in line:
                file_units = 'd_A'
            elif line[0] is not '#':
                x_val = float(line.split()[0])
                y_val = float(line.split()[1])
                self.map_data[filepath]['x_data'].append(x_val)
                self.map_data[filepath]['y_data'].append(y_val)
        self.map_data[filepath]['x_units'] = file_units
        self.map_data[filepath]['wavelength'] = wavelength
        current_pattern_file.close()

    def organize_map_files(self):
        datalist = []
        for filepath, filedata in self.map_data.items():
            datalist.append([filepath, round(float(filedata['pos_hor']), 3), round(float(filedata['pos_ver']), 3)])
        self.sorted_datalist = sorted(datalist, key=lambda x: (x[1], x[2]))

        self.transposed_list = [[row[i] for row in self.sorted_datalist] for i in range(len(self.sorted_datalist[1]))]
        self.min_hor = self.sorted_datalist[0][1]
        self.min_ver = self.sorted_datalist[0][2]

        self.num_hor = self.transposed_list[2].count(self.min_ver)
        self.num_ver = self.transposed_list[1].count(self.min_hor)

        self.check_map()  # Determine if there is problem with map

        self.diff_hor = self.sorted_datalist[self.num_ver][1] - self.sorted_datalist[0][1]
        self.diff_ver = self.sorted_datalist[1][2] - self.sorted_datalist[0][2]

        self.hor_size = self.pix_per_hor * self.num_hor
        self.ver_size = self.pix_per_ver * self.num_ver

        self.hor_um_per_px = self.diff_hor / self.pix_per_hor
        self.ver_um_per_px = self.diff_ver / self.pix_per_ver

        self.new_image = np.zeros([self.hor_size, self.ver_size])
        self.are_map_files_organized = True

    def check_map(self):
        if self.num_ver*self.num_hor == len(self.sorted_datalist):
            return True
        else:
            self.map_problem.emit()
            return False

    def prepare_map_data(self):
        """
        Calculates the ROI math and create the map image
        """

        for map_item_name in self.map_data:
            wavelength = self.map_data[map_item_name]['wavelength']
            file_units = self.map_data[map_item_name]['x_units']
            sum_int = {}
            for roi in self.map_roi_list:
                sum_int[roi['roi_letter']] = 0
            for x_val, y_val in zip(self.map_data[map_item_name]['x_data'], self.map_data[map_item_name]['y_data']):
                if not self.map_data[map_item_name]['x_units'] == self.units:
                    x_val = self.convert_units(x_val, file_units, self.units, wavelength)
                roi_letters = self.is_val_in_roi_range(x_val)
                for roi_letter in roi_letters:
                    sum_int[roi_letter] += y_val
            try:
                current_math = self.calculate_roi_math(sum_int)
            except SyntaxError:
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

        if self.all_positions_defined_in_files and not self.positions_set_manually and not self.are_map_files_organized:
            self.organize_map_files()

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
            if not roi in [r['roi_letter'] for r in self.map_roi_list]:
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

    def convert_units(self, value, previous_unit, new_unit, wavelength):
        self.units = new_unit
        if previous_unit == '2th_deg':
            tth = value
        elif previous_unit == 'q_A^-1':
            tth = np.arcsin(
                value * 1e10 * wavelength / (4 * np.pi)) * 360 / np.pi
        elif previous_unit == 'd_A':
            tth = 2 * np.arcsin(wavelength / (2 * value * 1e-10)) * 180 / np.pi
        else:
            tth = 0

        if new_unit == '2th_deg':
            res = tth
        elif new_unit == 'q_A^-1':
            res = 4 * np.pi * \
                  np.sin(tth / 360 * np.pi) / \
                  wavelength / 1e10
        elif new_unit == 'd_A':
            res = wavelength / (2 * np.sin(tth / 360 * np.pi)) * 1e10
        else:
            res = 0
        return res

    def add_manual_map_positions(self, hor_min, ver_min, hor_step, ver_step, hor_num, ver_num, is_hor_first, file_list):
        """

        Args:
            hor_min: Horizontal minimum position
            ver_min: Vertical minimum position
            hor_step: Step in horizontal
            ver_step: Step in vertical
            hor_num: Number of horizontal positions
            ver_num: Number of vertical positions
            is_hor_first: True of horizontal changes first between files, False if vertical
            file_list: List of the file names, as they appear in the map_data

        Returns:
            Does not return, but sets the positions_set_manually flag to True

        """
        self.sorted_datalist = file_list

        ind = 0
        if is_hor_first:
            for ver_pos in np.linspace(ver_min, ver_min + ver_step * (ver_num - 1), ver_num):
                for hor_pos in np.linspace(hor_min, hor_min + hor_step * (hor_num - 1), hor_num):
                    if not self.sorted_datalist[ind] == 'Empty':
                        self.map_data[self.sorted_datalist[ind]]['pos_hor'] = str(round(hor_pos, 3))
                        self.map_data[self.sorted_datalist[ind]]['pos_ver'] = str(round(ver_pos, 3))
                    ind = ind + 1
        else:
            for hor_pos in np.linspace(hor_min, hor_min + hor_step * (hor_num - 1), hor_num):
                for ver_pos in np.linspace(ver_min, ver_min + ver_step * (ver_num - 1), ver_num):
                    if not self.sorted_datalist[ind] == 'Empty':
                        self.map_data[self.sorted_datalist[ind]]['pos_hor'] = str(round(hor_pos, 3))
                        self.map_data[self.sorted_datalist[ind]]['pos_ver'] = str(round(ver_pos, 3))
                    ind = ind + 1

        self.min_hor = hor_min
        self.min_ver = ver_min

        self.num_hor = hor_num
        self.num_ver = ver_num

        self.diff_hor = hor_step
        self.diff_ver = ver_step

        self.hor_size = self.pix_per_hor * self.num_hor
        self.ver_size = self.pix_per_ver * self.num_ver

        self.hor_um_per_px = self.diff_hor / self.pix_per_hor
        self.ver_um_per_px = self.diff_ver / self.pix_per_ver

        self.new_image = np.zeros([self.hor_size, self.ver_size])
        self.positions_set_manually = True

    def sort_map_files_by_natural_name(self):
        """

        Returns:
            sorted_datalist: a list of all the map files, sorted by natural filename
        """
        datalist = []
        for filepath, filedata in self.map_data.items():
            datalist.append(filepath)
        sorted_datalist = sorted(datalist, key=lambda s: [int(t) if t.isdigit() else t.lower() for t in
                                                          re.split('(\d+)', s)])
        return sorted_datalist

    @property
    def num_map_files(self):
        return len(self.map_data)
