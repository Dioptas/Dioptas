from StdSuites.Standard_Suite import _3c_

__author__ = 'Clemens Prescher'
import sys
import os

from PyQt4 import QtGui, QtCore
from Views.IntegrationView import IntegrationView
from Data.ImgData import ImgData
from Data.MaskData import MaskData
from Data.CalibrationData import CalibrationData
import pyqtgraph as pg
import time
## Switch to using white background and black foreground
pg.setConfigOption('useOpenGL', False)
pg.setConfigOption('leftButtonPan', False)
pg.setConfigOption('background', 'k')
pg.setConfigOption('foreground', 'w')
pg.setConfigOption('antialias', True)

import numpy as np


class IntegrationController(object):
    def __init__(self):
        self.view = IntegrationView()
        self.img_data = ImgData()
        self.mask_data = MaskData()
        self.calibration_data = CalibrationData()
        self.create_sub_controller()

    def create_sub_controller(self):
        self.file_controller = XrsIntegrationFileController(self.view, self.img_data, self.mask_data)
        self.spectrum_controller = XrsIntegrationSpectrumController(self.view, self.img_data, self.mask_data, self.calibration_data)

class XrsIntegrationSpectrumController(object):
    def __init__(self, view, img_data, mask_data, calibration_data):
        self.view = view
        self.img_data = img_data
        self.mask_data = mask_data
        self.calibration_data = calibration_data

    def initialize(self):
        self.calibration_data.lo








class XrsIntegrationFileController(object):
    def __init__(self, view, img_data, mask_data):
        self.view= view
        self.img_data = img_data
        self.mask_data = mask_data
        self._working_dir = ''
        self._reset_img_levels = False
        self.view.show()
        self.initialize()
        self.img_data.subscribe(self.update_img)
        self.create_signals()
        self.view.setWindowState(self.view.windowState() & ~QtCore.Qt.WindowMinimized | QtCore.Qt.WindowActive)
        self.view.activateWindow()
        self.view.raise_()

    def initialize(self):
        self.img_data.set_calibration_file('ExampleData/LaB6_p49_001.poni')
        self.img_data.load_file('ExampleData/test_001.tif')
        self.mask_data.set_dimension(self.img_data.get_img_data().shape)
        self.mask_data.set_mask(np.loadtxt('ExampleData/test.mask'))
        self.update_img(True)
        self.plot_mask()
        self.view.img_view.img_view_box.autoRange()

    def plot_img(self, reset_img_levels=None):
        if reset_img_levels==None:
            reset_img_levels=self._reset_img_levels
        self.view.img_view.plot_image(self.img_data.get_img_data(), reset_img_levels)
        if reset_img_levels:
            self.view.img_view.auto_range()

    def plot_mask(self):
        if self.view.mask_show_cb.isChecked():
            self.view.img_view.plot_mask(self.mask_data.get_img())
        else:
            self.view.img_view.plot_mask(np.zeros(self.mask_data.get_img().shape))

    def change_mask_colormap(self):
        if self.view.mask_transparent_cb.isChecked():
            self.view.img_view.set_color([255,0,0,100])
        else:
            self.view.img_view.set_color([255,0,0,255])
        self.plot_mask()

    def change_img_levels_mode(self):
        self.view.img_view.img_histogram_LUT.percentageLevel = self.view.img_levels_percentage_rb.isChecked()
        self.view.img_view.img_histogram_LUT.old_hist_x_range = self.view.img_view.img_histogram_LUT.hist_x_range
        self.view.img_view.img_histogram_LUT.first_image = False

    def create_signals(self):
        self.connect_click_function(self.view.next_img_btn, self.load_next_img)
        self.connect_click_function(self.view.prev_img_btn, self.load_previous_img)
        self.connect_click_function(self.view.load_img_btn, self.load_file_btn_click)
        self.connect_click_function(self.view.img_browse_by_name_rb, self.set_img_iteration_mode_number)
        self.connect_click_function(self.view.img_browse_by_date_rb, self.set_img_iteration_mode_date)
        self.connect_click_function(self.view.mask_show_cb, self.plot_mask)
        self.connect_click_function(self.view.mask_transparent_cb, self.change_mask_colormap)
        self.connect_click_function(self.view.img_levels_absolute_rb, self.change_img_levels_mode)
        self.connect_click_function(self.view.img_levels_percentage_rb, self.change_img_levels_mode)

    def connect_click_function(self, emitter, function):
        self.view.connect(emitter, QtCore.SIGNAL('clicked()'), function)

    def load_file_btn_click(self, filename = None):
        if filename is None:
            filename = str(QtGui.QFileDialog.getOpenFileName(self.view, caption="Load image data",
                                                             directory=self._working_dir))

        if filename is not '':
            self._working_dir = os.path.dirname(filename)
            self.img_data.load_file(filename)
            self.plot_img()

    def load_next_img(self):
        self.img_data.load_next_file()

    def load_previous_img(self):
        self.img_data.load_previous_file()

    def update_img(self, reset_img_levels=False):
        self.plot_img(reset_img_levels)
        self.view.img_filename_lbl.setText(os.path.basename(self.img_data.filename))

    def set_img_iteration_mode_number(self):
        self.img_data.file_iteration_mode = 'number'

    def set_img_iteration_mode_date(self):
        self.img_data.file_iteration_mode = 'date'



if __name__ == "__main__":
    app = QtGui.QApplication(sys.argv)
    controller = IntegrationController()
    app.exec_()