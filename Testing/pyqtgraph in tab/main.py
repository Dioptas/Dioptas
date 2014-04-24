import sys
from PyQt4 import QtGui, QtCore
from widgetUI import Ui_Form

import numpy as np
import pyqtgraph as pg
import matplotlib.pyplot as plt


class View(QtGui.QWidget, Ui_Form):
    def __init__(self):
        super(View, self).__init__(None)
        self.setupUi(self)
        self.create_img_view()
        self.show()

    def create_img_view(self):
        self.img_view_box = self.pg_layout.addViewBox()
        self.img_view_box.setAspectLocked()

        #create the item handling the Data img
        self.data_img_item = pg.ImageItem()
        self.img_view_box.addItem(self.data_img_item)

        self.img_histogram_LUT = pg.HistogramLUTItem(self.data_img_item)
        self.img_histogram_LUT.axis.hide()
        self.pg_layout.addItem(self.img_histogram_LUT)


if __name__=='__main__':
    app = QtGui.QApplication(sys.argv)
    view = View()
    app.exec_()