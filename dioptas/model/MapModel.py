from PyQt4 import QtCore
import os
import numpy as np
from PIL import Image


class MapModel(QtCore.QObject):
    """
    Model for 2D maps from loading multiple images

    """

    def __init__(self):
        """
        Defines all object variables and creates a dummy image.
        :return:
        """
        super(MapModel, self).__init__()

        self.map_data = {}
        self.map_roi = {}
        self.theta_center = 5.9
        self.theta_range = 0.1
        self.num_hor = 0
        self.num_ver = 0
        self.roi_num = 0
        self.pix_per_hor = 100
        self.pix_per_ver = 100
        self.map_loaded = False
        self.units = '2th_deg'
        self.wavelength = 0.3344

        # Background for image
        self.bg_image = np.zeros([1920, 1200])

    def btn_show_map_clicked(self):  # move to controller?
        self.update_map()

    def btn_roi_add_clicked(self):  # partially move to controller or widget?
        # calculate ROI position
        tth_start = self.theta_center - self.theta_range
        tth_end = self.theta_center + self.theta_range
        roi_start = self.convert_units(tth_start, '2th_deg', self.units, self.wavelength)
        roi_end = self.convert_units(tth_end, '2th_deg', self.units, self.wavelength)

        # add ROI to list
        roi_name = self.generate_roi_name(roi_start, roi_end)
        roi_list_item = QtGui.QListWidgetItem(self.roi_list)
        roi_num = self.roi_num
        roi_list_item.setText(roi_name)
        self.roi_list.setItemSelected(roi_list_item, True)
        self.map_roi[roi_num] = {}
        self.map_roi[roi_num]['roi_name'] = roi_name

        # add ROI to pattern view
        ov = pq.LinearRegionItem.Vertical
        self.map_roi[roi_num]['Obj'] = pq.LinearRegionItem(values=[roi_start, roi_end], orientation=ov, movable=True,
                                                           brush=pq.mkBrush(color=(255, 0, 255, 100)))
        self.map_roi[roi_num]['List_Obj'] = self.roi_list.item(self.roi_list.count() - 1)
        self.spec_plot.addItem(self.map_roi[roi_num]['Obj'])
        self.map_roi[roi_num]['Obj'].sigRegionChangeFinished.connect(self.make_roi_changed(roi_num))
        self.roi_num = self.roi_num + 1

    def generate_roi_name(self, roi_start, roi_end):
        roi_name = '{:.3f}'.format(roi_start) + '-' + '{:.3f}'.format(roi_end)
        return roi_name

    def update_map(self):
        # order map files
        self.datalist = []
        for filename, filedata in self.map_data.items():
            self.datalist.append([filename, round(float(filedata['pos_hor']), 3), round(float(filedata['pos_ver']), 3)])
        self.sorted_datalist = sorted(self.datalist, key=lambda x: (x[1], x[2]))

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

        # read each file and prepare map image
        for filename, filedata in self.map_data.items():
            range_hor = self.pos_to_range(float(filedata['pos_hor']), self.min_hor, self.pix_per_hor, self.diff_hor)
            range_ver = self.pos_to_range(float(filedata['pos_ver']), self.min_ver, self.pix_per_ver, self.diff_ver)

            spec_file = self.map_data[filename]['spectrum_file_name']
            curr_spec_file = open(spec_file, 'r')
            sum_int = 0
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
                    if self.is_in_roi_range(x_val):
                        sum_int += float(line.split()[1])

            self.new_image[range_hor, range_ver] = sum_int

        self.map_loaded = True

    def pos_to_range(self, pos, min_pos, pix_per_pos, diff_pos):
        range_start = (pos - min_pos) / diff_pos * pix_per_pos
        range_end = range_start + pix_per_pos
        pos_range = slice(range_start, range_end)
        return pos_range

    def xy_to_horver(self, x, y):
        hor = self.min_hor + x // self.pix_per_hor * self.diff_hor
        ver = self.min_ver + y // self.pix_per_ver * self.diff_ver
        return hor, ver

    def horver_to_file_name(self, hor, ver):
        for filename, filedata in self.map_data.items():
            if abs(float(filedata['pos_hor']) - hor) < 2E-4 and abs(float(filedata['pos_ver']) - ver) < 2E-4:
                return filename
        dist_sqr = {}
        for filename, filedata in self.map_data.items():
            dist_sqr[filename] = abs(float(filedata['pos_hor']) - hor) ** 2 + abs(float(filedata['pos_ver']) - ver) ** 2

        return min(dist_sqr, key=dist_sqr.get)

    def check_map(self):
        if self.num_ver * self.num_hor == len(self.datalist):
            print("Correct number of files for map")
        else:
            print("Warning! Number of files in map not consistent with map positions")

    def is_in_roi_range(self, tt):
        for item in self.roi_list.selectedItems():
            roi_name = item.text().split('-')
            if float(roi_name[0]) < tt < float(roi_name[1]):
                return True
        return False

    def add_map_data(self, filename, working_directory, motors_info):
        base_filename = os.path.basename(filename)
        # self.all_file_list.addItem(filename)
        self.map_data[filename] = {}
        self.map_data[filename]['image_file_name'] = filename
        self.map_data[filename]['spectrum_file_name'] = working_directory + '\\' + \
                                                        os.path.splitext(base_filename)[0] + '.xy'
        self.map_data[filename]['pos_hor'] = str(round(float(motors_info['Horizontal']), 3))
        self.map_data[filename]['pos_ver'] = str(round(float(motors_info['Vertical']), 3))

    def reset_map_data(self):
        self.map_data = {}

    def convert_all_units(self, previous_unit, new_unit, wavelength):
        # also, use this for converting the range if the file is in another unit.
        self.roi_list.selectAll()
        for item in self.roi_list.selectedItems():
            roi_name = item.text().split('-')
            roi_start = self.convert_units(float(roi_name[0]), previous_unit, new_unit, wavelength)
            roi_end = self.convert_units(float(roi_name[1]), previous_unit, new_unit, wavelength)
            roi_new_name = self.generate_roi_name(roi_start, roi_end)
            # row = self.roi_list.row(item)
            # self.roi_list.takeItem(row)
            # self.roi_list.insertItem(row, roi_new_name)
            item.setText(roi_new_name)
            for key in self.map_roi:
                if self.map_roi[key]['List_Obj'] == item:
                    self.map_roi[key]['Obj'].setRegion((roi_start, roi_end))
                    break

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

