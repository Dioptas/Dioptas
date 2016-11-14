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
        self.wavelength = 0.3344
        self.all_positions_defined_in_files = False
        self.positions_set_manually = False

        # Background for image
        self.bg_image = np.zeros([1920, 1200])

    def reset_map_data(self):
        self.map_data = {}
        self.all_positions_defined_in_files = False
        self.map_cleared.emit()

    def add_map_data(self, filename, working_directory, motors_info):
        base_filename = os.path.basename(filename)
        self.map_data[filename] = {}
        self.map_data[filename]['image_file_name'] = filename.replace('\\', '/')
        self.map_data[filename]['spectrum_file_name'] = working_directory + '/' + \
                                                        os.path.splitext(base_filename)[0] + '.xy'
        try:
            self.map_data[filename]['pos_hor'] = str(round(float(motors_info['Horizontal']), 3))
            self.map_data[filename]['pos_ver'] = str(round(float(motors_info['Vertical']), 3))
        except KeyError:
            self.all_positions_defined_in_files = False

    def organize_map_files(self):
        datalist = []
        for filename, filedata in self.map_data.items():
            datalist.append([filename, round(float(filedata['pos_hor']), 3), round(float(filedata['pos_ver']), 3)])
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

    def check_map(self):
        if self.num_ver*self.num_hor == len(self.sorted_datalist):
            pass
        else:
            self.map_problem.emit()

    def read_map_files_and_prepare_map_data(self):
        for filename, filedata in self.map_data.items():
            spec_file = self.map_data[filename]['spectrum_file_name'].replace('\\', '/')
            curr_spec_file = open(spec_file, 'r')
            sum_int = {}
            for roi in self.map_roi_list:
                sum_int[roi['roi_letter']] = 0
            file_units = '2th_deg'
            wavelength = self.wavelength
            for line in curr_spec_file:
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
                    x_val = self.convert_units(x_val, file_units, self.units, wavelength)
                    in_roi = self.is_in_roi_range(x_val)
                    if in_roi:
                        sum_int[in_roi] += float(line.split()[1])

            curr_math = self.calculate_roi_math(sum_int)
            range_hor = self.pos_to_range(float(filedata['pos_hor']), self.min_hor, self.pix_per_hor, self.diff_hor)
            range_ver = self.pos_to_range(float(filedata['pos_ver']), self.min_ver, self.pix_per_ver, self.diff_ver)
            self.new_image[range_hor, range_ver] = curr_math

    def update_map(self):
        if not self.all_positions_defined_in_files and not self.positions_set_manually:
            self.map_problem.emit()
            return

        if self.all_positions_defined_in_files and not self.positions_set_manually:
            self.organize_map_files()

        if self.roi_math == '':
            for item in self.map_roi_list:
                self.roi_math = self.roi_math + item['roi_letter'] + '+'
            self.roi_math = self.roi_math.rsplit('+', 1)[0]

        self.read_map_files_and_prepare_map_data()

        self.map_changed.emit()

    def is_in_roi_range(self, tt):
        for item in self.map_roi_list:
            if float(item['roi_start']) < tt < float(item['roi_end']):
                return item['roi_letter']
        return False

    def calculate_roi_math(self, sum_int):
        curr_roi_math = self.roi_math
        for key in sum_int:
            curr_roi_math = curr_roi_math.replace(key, str(sum_int[key]))
        return eval(curr_roi_math)

    def pos_to_range(self, pos, min_pos, pix_per_pos, diff_pos):
        range_start = (pos - min_pos) / diff_pos * pix_per_pos
        range_end = range_start + pix_per_pos
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
        # self.sorted_datalist = self.sort_map_files_by_natural_name()
        self.sorted_datalist = []
        for index in range(file_list.count()):
            self.sorted_datalist.append(str(file_list.item(index).text()))

        ind = 0
        if is_hor_first:
            for ver_pos in np.linspace(ver_min, ver_min + ver_step * (ver_num - 1), ver_num):
                for hor_pos in np.linspace(hor_min, hor_min + hor_step * (hor_num - 1), hor_num):
                    if not self.sorted_datalist[ind] == 'Empty':
                        self.map_data[self.sorted_datalist[ind]]['pos_hor'] = hor_pos
                        self.map_data[self.sorted_datalist[ind]]['pos_ver'] = ver_pos
                    ind = ind + 1
        else:
            for hor_pos in np.linspace(hor_min, hor_min + hor_step * (hor_num - 1), hor_num):
                for ver_pos in np.linspace(ver_min, ver_min + ver_step * (ver_num - 1), ver_num):
                    if not self.sorted_datalist[ind] == 'Empty':
                        self.map_data[self.sorted_datalist[ind]]['pos_hor'] = hor_pos
                        self.map_data[self.sorted_datalist[ind]]['pos_ver'] = ver_pos
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
        datalist = []
        for filename, filedata in self.map_data.items():
            datalist.append(filename)
        sorted_datalist = sorted(datalist, key=lambda s: [int(t) if t.isdigit() else t.lower() for t in
                                                          re.split('(\d+)', s)])
        return sorted_datalist
