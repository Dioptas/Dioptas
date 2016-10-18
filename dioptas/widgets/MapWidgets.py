from qtpy import QtCore, QtGui, QtWidgets
import pyqtgraph as pq
from pyqtgraph import GraphicsLayoutWidget
import os
import numpy as np
from .plot_widgets.HistogramLUTItem import HistogramLUTItem
from PIL import Image
import time


class Map2DWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super(Map2DWidget, self).__init__(parent)

        # setup MAP window
        self.setWindowTitle("2D Map")
        self.setGeometry(200, 100, 800, 600)

        # setup initial data structures and default parameters
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

        # WIDGETS
        # not in use - file list
        # self.all_file_list = QtWidgets.QListWidget(self)
        # self.all_file_list.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.show_map_btn = QtWidgets.QPushButton(self)
        self.lbl_map_pos = QtWidgets.QLabel()
        # Map Image and Histogram
        self.map_image = pq.ImageItem()
        self.map_histogram_LUT = HistogramLUTItem(self.map_image, orientation='vertical')

        # Background for image
        self.bg_image = np.zeros([1920, 1200])
        self.map_bg_image = pq.ImageItem()
        bg_rect = QtCore.QRectF(0, 0, 1920, 1200)
        self.map_bg_image.setImage(self.bg_image, opacity=0.5)
        self.map_bg_image.setRect(bg_rect)
        self.reset_zoom_btn = QtWidgets.QPushButton(self)

        # ROI Widgets
        self.roi_list = QtWidgets.QListWidget(self)
        self.roi_list.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.roi_add_btn = QtWidgets.QPushButton(self)
        self.roi_del_btn = QtWidgets.QPushButton(self)
        self.roi_clear_btn = QtWidgets.QPushButton(self)
        self.roi_toggle_btn = QtWidgets.QPushButton(self)
        self.roi_select_all_btn = QtWidgets.QPushButton(self)

        # Background control
        self.add_bg_btn = QtWidgets.QPushButton(self)
        self.show_bg_chk = QtWidgets.QCheckBox(self)
        self.show_map_chk = QtWidgets.QCheckBox(self)

        # positions
        # self.all_file_list.setGeometry(QtCore.QRect(10, 70, 200, 500))
        # self.all_file_list.setVisible(0)

        # ROI positions
        self.roi_grid = QtWidgets.QGridLayout()
        self.roi_grid.addWidget(self.roi_add_btn, 0, 0, 1, 1)
        self.roi_grid.addWidget(self.roi_del_btn, 0, 1, 1, 1)
        self.roi_grid.addWidget(self.roi_clear_btn, 1, 0, 1, 1)
        self.roi_grid.addWidget(self.roi_toggle_btn, 1, 1, 1, 1)
        self.roi_grid.addWidget(self.roi_select_all_btn, 2, 0, 1, 1)

        # Widget Properties
        self.setWindowTitle("2D Map")
        self.show_map_btn.setText("Update Map")
        self.roi_add_btn.setText("Add Range")
        self.roi_del_btn.setText("Remove Range")
        self.roi_clear_btn.setText("Clear")
        self.roi_toggle_btn.setText("Toggle Show")
        self.roi_toggle_btn.setCheckable(True)
        self.roi_toggle_btn.setChecked(True)
        self.roi_select_all_btn.setText("Select All")
        self.add_bg_btn.setText("Add BG Image")
        self.show_bg_chk.setText("Show BG Image?")
        self.show_map_chk.setText("Show Map?")
        self.reset_zoom_btn.setText("Reset Zoom")

        # Layout
        self.main_vbox = QtWidgets.QVBoxLayout()
        self.hbox = QtWidgets.QHBoxLayout()
        self.lbl_hbox = QtWidgets.QHBoxLayout()
        self.bg_hbox = QtWidgets.QHBoxLayout()
        self.roi_vbox = QtWidgets.QVBoxLayout()
        self.roi_vbox.addWidget(self.show_map_btn)
        self.roi_vbox.addWidget(self.roi_list)
        self.roi_vbox.addLayout(self.roi_grid)
        self.hbox.addLayout(self.roi_vbox)
        self.hbox.addStretch(1)

        self.bg_hbox.addWidget(self.add_bg_btn)
        self.bg_hbox.addWidget(self.show_bg_chk)
        self.bg_hbox.addWidget(self.show_map_chk)
        self.bg_hbox.addStretch(1)

        self.lbl_hbox.addWidget(self.reset_zoom_btn)
        self.lbl_hbox.addStretch(1)
        self.lbl_hbox.addWidget(self.lbl_map_pos)

        self.hist_layout = GraphicsLayoutWidget()
        self.map_view_box = self.hist_layout.addViewBox(0, 0)

        self.map_view_box.addItem(self.map_bg_image, ignoreBounds=True)  # MAPBG
        self.map_view_box.addItem(self.map_image)
        self.map_histogram_LUT = HistogramLUTItem(self.map_image, orientation='vertical')
        self.hist_layout.addItem(self.map_histogram_LUT, 0, 1)

        self.hbox.addWidget(self.hist_layout)

        self.main_vbox.addLayout(self.hbox)
        self.main_vbox.addLayout(self.lbl_hbox)
        self.main_vbox.addLayout(self.bg_hbox)
        self.main_vbox.addStretch(1)
        self.setLayout(self.main_vbox)

        # button connections
        self.show_map_btn.clicked.connect(self.btn_show_map_clicked)
        # self.all_file_list.itemSelectionChanged.connect(self.all_file_list_selected)
        self.roi_add_btn.clicked.connect(self.btn_roi_add_clicked)
        self.roi_del_btn.clicked.connect(self.btn_roi_del_clicked)
        self.roi_clear_btn.clicked.connect(self.btn_roi_clear_clicked)
        self.roi_toggle_btn.clicked.connect(self.btn_roi_toggle_clicked)
        self.roi_select_all_btn.clicked.connect(self.btn_roi_select_all_clicked)
        self.add_bg_btn.clicked.connect(self.btn_add_bg_image_clicked)
        self.show_bg_chk.stateChanged.connect(self.chk_show_bg_changed)
        self.show_map_chk.stateChanged.connect(self.chk_show_map_changed)
        self.reset_zoom_btn.clicked.connect(self.reset_zoom_btn_clicked)

        self.map_image.mouseClickEvent = self.myMouseClickEvent
        self.hist_layout.scene().sigMouseMoved.connect(self.map_mouse_move_event)
        self.map_view_box.mouseClickEvent = self.do_nothing

        self.setWindowFlags(QtCore.Qt.Tool | QtCore.Qt.WindowTitleHint | QtCore.Qt.WindowCloseButtonHint |
                            QtCore.Qt.CustomizeWindowHint | QtCore.Qt.MSWindowsFixedSizeDialogHint |
                            QtCore.Qt.X11BypassWindowManagerHint)
        self.setAttribute(QtCore.Qt.WA_MacAlwaysShowToolWindow)

    def btn_show_map_clicked(self):
        self.update_map()

    def btn_roi_add_clicked(self):
        # calculate ROI position
        tth_start = self.theta_center - self.theta_range
        tth_end = self.theta_center + self.theta_range
        roi_start = self.convert_units(tth_start, '2th_deg', self.units, self.wavelength)
        roi_end = self.convert_units(tth_end, '2th_deg', self.units, self.wavelength)

        # add ROI to list
        roi_name = self.generate_roi_name(roi_start, roi_end)
        roi_list_item = QtWidgets.QListWidgetItem(self.roi_list)
        roi_num = self.roi_num
        roi_list_item.setText(roi_name)
        roi_list_item.setSelected(True)
        self.map_roi[roi_num] = {}
        self.map_roi[roi_num]['roi_name'] = roi_name

        # add ROI to pattern view
        ov = pq.LinearRegionItem.Vertical
        self.map_roi[roi_num]['Obj'] = pq.LinearRegionItem(values=[roi_start, roi_end], orientation=ov, movable=True,
                                                          brush=pq.mkBrush(color=(255, 0, 255, 100)))
        self.map_roi[roi_num]['List_Obj'] = self.roi_list.item(self.roi_list.count()-1)
        self.spec_plot.addItem(self.map_roi[roi_num]['Obj'])
        self.map_roi[roi_num]['Obj'].sigRegionChangeFinished.connect(self.make_roi_changed(roi_num))
        self.roi_num = self.roi_num + 1

    # create a function for each ROI when ROI is modified
    def make_roi_changed(self, curr_map_roi):
        def roi_changed():
            tth_start, tth_end = self.map_roi[curr_map_roi]['Obj'].getRegion()
            new_roi_name = self.generate_roi_name(tth_start, tth_end)
            row = self.roi_list.row(self.map_roi[curr_map_roi]['List_Obj'])
            self.roi_list.takeItem(row)
            self.roi_list.insertItem(row, new_roi_name)
            self.map_roi[curr_map_roi]['roi_name'] = new_roi_name
            self.map_roi[curr_map_roi]['List_Obj'] = self.roi_list.item(row)
            self.roi_list.item(row).setSelected(True)
        return roi_changed

    def generate_roi_name(self, roi_start, roi_end):
        roi_name = '{:.3f}'.format(roi_start) + '-' + '{:.3f}'.format(roi_end)
        return roi_name

    def btn_roi_del_clicked(self):
        for each_roi in self.roi_list.selectedItems():
            for key in self.map_roi:
                if self.map_roi[key]['List_Obj'] == each_roi:
                    self.spec_plot.removeItem(self.map_roi[key]['Obj'])
                    del self.map_roi[key]
                    break
            self.roi_list.takeItem(self.roi_list.row(each_roi))

    def btn_roi_clear_clicked(self):
        self.roi_list.clear()
        for key in self.map_roi:
            self.spec_plot.removeItem(self.map_roi[key]['Obj'])
        self.map_roi.clear()

    def btn_roi_toggle_clicked(self):
        if self.roi_toggle_btn.isChecked():
            for key in self.map_roi:
                self.map_roi[key]['Obj'].show()
        else:
            for key in self.map_roi:
                self.map_roi[key]['Obj'].hide()

    # not in use
    # def all_file_list_selected(self):
    #     print self.all_file_list.selectedItems()
        # print self.map_data[self.all_file_list.selectedItems()]
        # self.update_map()
        """
        print str(len(self.all_file_list.selectedItems())) + " item(s) selected"
        for each_selected_item in self.all_file_list.selectedItems():
            print each_selected_item.text()
        """

    def raise_widget(self, img_model, spec_plot, working_dir):
        self.img_model = img_model
        self.spec_plot = spec_plot
        self.working_dir = working_dir
        self.show()
        self.setWindowState(self.windowState() & ~QtCore.Qt.WindowMinimized | QtCore.Qt.WindowActive)
        self.activateWindow()
        self.raise_()

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

        self.hor_size = self.pix_per_hor*self.num_hor
        self.ver_size = self.pix_per_ver*self.num_ver

        self.hor_um_per_px = self.diff_hor/self.pix_per_hor
        self.ver_um_per_px = self.diff_ver/self.pix_per_ver

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

        if self.show_bg_chk.isChecked():
            opac = 0.5
        else:
            opac = 1.0
        self.map_image.setOpacity(opac)
        self.map_image.setImage(self.new_image, True)
        self.auto_range()
        self.map_loaded = True
        self.show_map_chk.setChecked(True)

    def pos_to_range(self, pos, min_pos, pix_per_pos, diff_pos):
        range_start = (pos-min_pos)/diff_pos*pix_per_pos
        range_end = range_start + pix_per_pos
        pos_range = slice(range_start, range_end)
        return pos_range

    def xy_to_horver(self, x, y):
        hor = self.min_hor + x//self.pix_per_hor*self.diff_hor
        ver = self.min_ver + y//self.pix_per_ver*self.diff_ver
        return hor, ver

    def horver_to_file_name(self, hor, ver):
        for filename, filedata in self.map_data.items():
            if abs(float(filedata['pos_hor']) - hor) < 2E-4 and abs(float(filedata['pos_ver']) - ver) < 2E-4:
                return filename
        dist_sqr = {}
        for filename, filedata in self.map_data.items():
            dist_sqr[filename] = abs(float(filedata['pos_hor'])-hor)**2 + abs(float(filedata['pos_ver'])-ver)**2

        return min(dist_sqr, key=dist_sqr.get)

    def check_map(self):
        if self.num_ver*self.num_hor == len(self.datalist):
            print("Correct number of files for map")
        else:
            print("Warning! Number of files in map not consistent with map positions")

    def is_in_roi_range(self, tt):
        for item in self.roi_list.selectedItems():
            roi_name = item.text().split('-')
            if float(roi_name[0]) < tt < float(roi_name[1]):
                return True
        return False

    def btn_roi_select_all_clicked(self):
        self.roi_list.selectAll()

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
        # self.all_file_list.clear()

    # Auto-range for map image
    def auto_range(self):
        hist_x, hist_y = self.map_histogram_LUT.hist_x, self.map_histogram_LUT.hist_y
        min_level = hist_x[0]
        max_level = hist_x[-1]
        self.map_histogram_LUT.setLevels(min_level, max_level)

    def reset_zoom_btn_clicked(self):
        self.map_view_box.autoRange()

    # replaces the LMB click event for loading the spectrum according to map pos, complete unzoom on right-click
    def myMouseClickEvent(self, ev):
        if ev.button() == QtCore.Qt.RightButton or \
                (ev.button() == QtCore.Qt.LeftButton and
                         ev.modifiers() & QtCore.Qt.ControlModifier):
            self.map_view_box.autoRange()

        elif ev.button() == QtCore.Qt.LeftButton:
            pos = ev.pos()
            x = pos.x()
            y = pos.y()
            hor, ver = self.xy_to_horver(x, y)
            file_name = self.horver_to_file_name(hor, ver)
            self.img_model.load(str(file_name))

    # shows position and file_name when mouse is within map image
    def map_mouse_move_event(self, pos):
        pos = self.map_image.mapFromScene(pos)
        x = pos.x()
        y = pos.y()
        try:
            hor, ver = self.xy_to_horver(x, y)
            file_name = self.horver_to_file_name(hor, ver)
            self.lbl_map_pos.setText(str(file_name) + ":\t hor=" + str(round(hor, 3)) + '\tver:=' + str(round(ver, 3)))
        except Exception:
            pass

    # prevents right-click from opening menu
    def do_nothing(self, ev):
        pass

    def btn_add_bg_image_clicked(self):
        if not self.map_loaded:
            msg = "Please load a map, choose a region and update the map"
            bg_msg = QtWidgets.QMessageBox()
            bg_msg.setIcon(QtWidgets.QMessageBox.Information)
            bg_msg.setText("No Map Loaded")
            bg_msg.setInformativeText("See additional info...")
            bg_msg.setWindowTitle("Error: No Map")
            bg_msg.setStandardButtons(QtWidgets.QMessageBox.Ok)
            bg_msg.setDetailedText(msg)
            bg_msg.exec_()
            return

        load_name, _ = QtWidgets.QFileDialog.getOpenFileName(self, 'Choose file name for loading background image',
                                                      self.working_dir['image'], 'TIFF Files (*.tif)')

        if not load_name:
            print("No file chosen for background")
            return
        load_name_file = str(load_name).rsplit('/', 1)[-1]
        loaded_bg_image = Image.open(str(load_name).replace('/', '\\'))
        bg_image_tags = loaded_bg_image.tag

        img_px_size_hor = 0.00035  # 3.5 microns in mm
        img_px_size_ver = 0.00035
        img_hor_px = 1920.0
        img_ver_px = 1200.0
        img_width_mm = img_hor_px*img_px_size_hor
        img_height_mm = img_ver_px*img_px_size_ver

        self.bg_hor_ver = self.get_bg_hor_ver(bg_image_tags)
        bg_w_px = img_width_mm/self.hor_um_per_px
        bg_h_px = img_height_mm/self.ver_um_per_px
        bg_hor = float(self.bg_hor_ver['Horizontal'])
        bg_ver = float(self.bg_hor_ver['Vertical'])

        bg_hor_shift = -(-(bg_hor - img_width_mm/2.0)+self.min_hor)/self.hor_um_per_px + self.pix_per_hor/2
        bg_ver_shift = -(-(bg_ver - img_height_mm/2.0)+self.min_ver)/self.ver_um_per_px + self.pix_per_ver/2

        if load_name_file.split('_', 1)[0] == 'ds' or load_name_file.split('_', 1)[0] == 'ms':
            loaded_bg_image = np.fliplr(loaded_bg_image)

        self.bg_image = np.rot90(loaded_bg_image, 3)

        self.map_bg_image.setImage(self.bg_image)
        bg_rect = QtCore.QRectF(bg_hor_shift, bg_ver_shift, bg_w_px, bg_h_px)
        self.map_bg_image.setRect(bg_rect)
        self.show_bg_chk.setChecked(True)

    def get_bg_hor_ver(self, tags):
        result = {}

        useful_tags = ['Horizontal:', 'Vertical:']

        for tag in tags:
            for key in useful_tags:
                if key in str(tags[tag]):
                    k, v = str(tags[tag][0]).split(':')
                    result[str(k)] = str(v)
        return result

    def chk_show_bg_changed(self):
        if self.show_bg_chk.isChecked():
            self.map_image.setOpacity(0.5)
            self.map_bg_image.setOpacity(0.5)
            self.show_map_chk.setEnabled(True)
        else:
            self.map_image.setOpacity(1.0)
            self.map_bg_image.setOpacity(0.0)
            self.show_map_chk.setChecked(True)
            self.show_map_chk.setEnabled(False)

    def chk_show_map_changed(self):
        if self.show_map_chk.isChecked():
            if self.show_bg_chk.isChecked():
                self.map_image.setOpacity(0.5)
                self.map_bg_image.setOpacity(0.5)
            else:
                self.map_image.setOpacity(1.0)
                self.map_bg_image.setOpacity(0.0)
        else:
            self.map_image.setOpacity(0.0)
            self.map_bg_image.setOpacity(1.0)

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
