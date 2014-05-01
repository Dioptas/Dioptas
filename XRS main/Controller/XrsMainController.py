from StdSuites.Standard_Suite import _3c_

__author__ = 'Clemens Prescher'
import sys
import os

from PyQt4 import QtGui, QtCore
from Views.XrsMainView import XrsMainView
from Data.XrsImgData import XrsImgData
import pyqtgraph as pg
import time
## Switch to using white background and black foreground
pg.setConfigOption('useOpenGL', False)
pg.setConfigOption('leftButtonPan', False)
pg.setConfigOption('background', 'k')
pg.setConfigOption('foreground', 'w')
pg.setConfigOption('antialias', True)

import numpy as np
import matplotlib.pyplot as plt


class XrsMainController(object):
    def __init__(self):
        self.view = XrsMainView()
        self.data = XrsImgData()
        self.create_signals()
        self._working_dir = ''
        self.view.show()

        self.first_image()
        self.view.setWindowState(self.view.windowState() & ~QtCore.Qt.WindowMinimized | QtCore.Qt.WindowActive)
        self.view.activateWindow()
        self.view.raise_()

    def first_image(self):
        self.data.set_calibration_file('ExampleData/LaB6_p49_001.poni')
        self.data.load_file('ExampleData/Mg2SiO4_076.tif')
        self.plot_data()

    def plot_data(self):
        self.view.plot_image(np.rot90(self.data.get_img_data(), -1), True)
        x, y = self.data.get_spectrum()
        self.view.plot_graph(x, y)
        self.view.set_img_filename(os.path.basename(self.data.filename))

    def create_signals(self):
        self.connect_click_function(self.view.next_file_btn, self.load_next_file)
        self.connect_click_function(self.view.previous_file_btn, self.load_previous_file)
        self.connect_click_function(self.view.load_file_btn, self.load_file_btn_click)

    def connect_click_function(self, emitter, function):
        self.view.connect(emitter, QtCore.SIGNAL('clicked()'), function)

    def load_file_btn_click(self, filename = None):
        if filename is None:
            filename = str(QtGui.QFileDialog.getOpenFileName(self.view, caption="Load image data",
                                                             directory=self._working_dir))

        if filename is not '':
            self._working_dir = os.path.dirname(filename)
            self.data.load_file(filename)
            self.plot_data()

    def load_next_file(self):
        t1 = time.time()
        self.data.load_next_file()
        self.plot_data()
        QtGui.QApplication.processEvents()
        t2 = time.time()

        print("It  took  %.3fs." % (t2 - t1))

    def load_previous_file(self):
        self.data.load_previous_file()
        self.plot_data()


if __name__ == "__main__":
    app = QtGui.QApplication(sys.argv)
    controller = XrsMainController()
    app.exec_()