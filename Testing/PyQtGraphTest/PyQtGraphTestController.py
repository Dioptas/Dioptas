__author__ = 'Doomgoroth'
import sys

from PyQt4 import QtGui, QtCore
import pyqtgraph as pg

from PyQtGraphTestView import PyQtGraphView
## Switch to using white background and black foreground
pg.setConfigOption('useOpenGL', False)
pg.setConfigOption('leftButtonPan', False)
pg.setConfigOption('background', 'k')
pg.setConfigOption('foreground', 'w')
pg.setConfigOption('antialias', True)

import matplotlib.pyplot as plt


class PyQtGraphTestController(object):
    def __init__(self):
        self.view = PyQtGraphView()
        self.create_signals()
        self.view.show()

        #self.first_plot()
        self.first_image()
        self.view.activateWindow()

    def first_image(self):
        img = plt.imread('../X-ray SuiteTry/Data/test_001.tif')
        self.view.plot_image_right(img, True, True, True)
        img = plt.imread('../X-ray SuiteTry/Data/test_002.tif')
        self.view.plot_image_left(img, True, True, True)

    def create_signals(self):
        self.connect_click_function(self.view.bench_btn, self.bench_mark_img_loading)

    def connect_click_function(self, emitter, function):
        self.view.connect(emitter, QtCore.SIGNAL('clicked()'), function)

    def bench_mark_img_loading(self):
        import matplotlib.pyplot as plt
        import time
        import numpy as np

        tpi = []
        for i in xrange(10):
            for num in xrange(1, 9):
                t0 = time.time()
                file_name = '../X-ray SuiteTry/Data/test_00' + str(num) + '.tif'
                img = plt.imread(file_name)

                self.view.plot_image_right(img)
                QtGui.QApplication.processEvents()
                t1 = time.time()
                print t1 - t0
                tpi.append(t1 - t0)
        print '###AVERAGE###'
        print np.average(tpi)


if __name__ == "__main__":
    app = QtGui.QApplication(sys.argv)
    controller = PyQtGraphTestController()
    app.exec_()