from StdSuites.Standard_Suite import _3c_

__author__ = 'Clemens Prescher'
import sys

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
        self.view.show()

        self.first_image()
        self.view.setWindowState(self.view.windowState() & ~QtCore.Qt.WindowMinimized | QtCore.Qt.WindowActive)
        self.view.activateWindow()
        self.view.raise_()

    def first_image(self):
        self.data.set_calibration_file('../ExampleData/LaB6_p49_001.poni')
        self.data.load_file('../ExampleData/test_001.tif')
        self.plot_data()

    def plot_data(self):
        self.view.plot_image(np.rot90(self.data.get_img_data(), -1), True)
        x, y = self.data.get_spectrum()
        self.view.plot_graph(x, y)
        self.view.set_img_filename(self.data.filename)

    def create_signals(self):
        self.connect_click_function(self.view.next_file_btn, self.load_next_file)
        self.connect_click_function(self.view.previous_file_btn, self.load_previous_file)

    def connect_click_function(self, emitter, function):
        self.view.connect(emitter, QtCore.SIGNAL('clicked()'), function)

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