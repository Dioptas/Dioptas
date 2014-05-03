from StdSuites.Standard_Suite import _3c_

__author__ = 'Clemens Prescher'
import sys
import os

from PyQt4 import QtGui, QtCore
from Views.XrsIntegrationView import XrsIntegrationView
from Data.XrsImgData import XrsImgData
from Data.XrsMaskData import XrsMaskData
import pyqtgraph as pg
import time
## Switch to using white background and black foreground
pg.setConfigOption('useOpenGL', False)
pg.setConfigOption('leftButtonPan', False)
pg.setConfigOption('background', 'k')
pg.setConfigOption('foreground', 'w')
pg.setConfigOption('antialias', True)

import numpy as np


class XrsIntegrationController(object):
    def __init__(self):
        self.view = XrsIntegrationView()
        self.img_data = XrsImgData()
        self.mask_data = XrsMaskData()
        self.img_data.subscribe(self.update_img)
        self.create_signals()
        self._working_dir = ''
        self._reset_img_levels = False
        self.view.show()
        self.initialize()
        self.view.setWindowState(self.view.windowState() & ~QtCore.Qt.WindowMinimized | QtCore.Qt.WindowActive)
        self.view.activateWindow()
        self.view.raise_()

    def initialize(self):
        self.img_data.set_calibration_file('ExampleData/LaB6_p49_001.poni')
        self.img_data.load_file('ExampleData/test_001.tif')
        self.mask_data.set_mask(np.loadtxt('ExampleData/test.mask'))
        self.plot_img(True)

    def plot_img(self, reset_img_levels=None):
        if reset_img_levels==None:
            reset_img_levels=self._reset_img_levels
        self.view.img_view.plot_image(self.img_data.get_img_data(), reset_img_levels)
        if reset_img_levels:
            self.view.img_view.auto_range()

    def create_signals(self):
        self.connect_click_function(self.view.next_img_btn, self.load_next_img)
        self.connect_click_function(self.view.prev_img_btn, self.load_previous_img)
        self.connect_click_function(self.view.load_img_btn, self.load_file_btn_click)
        self.connect_click_function(self.view.img_browse_by_name_rb, self.set_img_iteration_mode_number)
        self.connect_click_function(self.view.img_browse_by_date_rb, self.set_img_iteration_mode_date)

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

    def update_img(self):
        self.plot_img()
        self.view.img_filename_lbl.setText(os.path.basename(self.img_data.filename))

    def set_img_iteration_mode_number(self):
        self.img_data.file_iteration_mode = 'number'

    def set_img_iteration_mode_date(self):
        self.img_data.file_iteration_mode = 'date'

if __name__ == "__main__":
    app = QtGui.QApplication(sys.argv)
    controller = XrsIntegrationController()
    app.exec_()