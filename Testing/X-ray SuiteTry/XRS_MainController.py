import sys

from PyQt4 import QtGui, QtCore

from Views.XRS_MainView import XRS_MainView
from XRS_Data import XRS_ImageData


class XRS_MainController(object):
    def __init__(self, data):
        self.data = data
        self.main_view = XRS_MainView()
        self.plot_image(self.data.get_image_data())
        self.create_signals()
        self.main_view.show()
        self.main_view.setWindowState(
            self.main_view.windowState() & ~QtCore.Qt.WindowMinimized | QtCore.Qt.WindowActive)

        self.main_view.activateWindow()

    def plot_image(self, img_data):
        self.main_view.plot_image(img_data)

    def create_signals(self):
        self.data.subscribe(self.data_changed)
        self.connect_click_function(self.main_view.load_image_btn, self.load_data_click)
        self.connect_click_function(self.main_view.load_next_image_btn, self.data.load_next_image_file)
        self.connect_click_function(self.main_view.load_previous_image_btn, self.data.load_previous_image_file)

    def connect_click_function(self, emitter, function):
        self.main_view.connect(emitter, QtCore.SIGNAL('clicked()'), function)

    def data_changed(self, new_data):
        self.plot_image(new_data.get_image_data())
        self.main_view.image_file_name_lbl.setText(new_data.file_name)
        self.update_graph()

    def update_graph(self):
        self.main_view.graph_axes.plot_graph(data.get_spectrum())

    def load_data_click(self):
        self.bench_mark_img_loading()

    def bench_mark_img_loading(self):
        import matplotlib.pyplot as plt
        import time
        import numpy as np

        tpi = []
        for i in xrange(10):
            for num in xrange(1, 9):
                t0 = time.time()
                file_name = 'Data/test_00' + str(num) + '.tif'
                img = plt.imread(file_name)

                self.main_view.plot_image(img)
                #QtGui.QApplication.processEvents()
                t1 = time.time()
                print t1 - t0
                tpi.append(t1 - t0)
        print '###AVERAGE###'
        print np.average(tpi)


if __name__ == "__main__":
    app = QtGui.QApplication(sys.argv)
    data = XRS_ImageData()
    data.load_image_file('Data/test_001.tif')
    controller = XRS_MainController(data)
    app.exec_()