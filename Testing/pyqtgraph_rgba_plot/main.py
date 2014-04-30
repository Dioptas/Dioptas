import sys

from PyQt4 import QtGui
import pyqtgraph as pg
import numpy as np

from Testing.pyqtgraph_rgba_plot.widgetUI import Ui_Form


class View(QtGui.QWidget, Ui_Form):
    def __init__(self):
        super(View, self).__init__(None)
        self.setupUi(self)
        self.create_img_view()
        self.plot_image_2d()
        self.plot_mask_argb()
        self.show()

    def create_img_view(self):
        self.img_view_box = self.pg_layout2.addViewBox()
        self.img_view_box.setAspectLocked()

        #create the item handling the Data img
        self.data_img_item = pg.ImageItem()
        self.img_view_box.addItem(self.data_img_item)

        self.mask_img_item = pg.ImageItem()
        self.img_view_box.addItem(self.mask_img_item)

        self.img_histogram_LUT = pg.HistogramLUTItem(self.data_img_item)
        self.img_histogram_LUT.axis.hide()
        self.pg_layout2.addItem(self.img_histogram_LUT)

        self.img_view_box.setAspectLocked()

    def plot_image_argb(self):
        self.data_img = np.zeros((1000,1000,4), dtype = 'uint8')
        self.data_img[400:600, 400:600, :] = [0,255,0,255]
        self.data_img_item.setImage(self.data_img)

    def plot_image_2d(self):
        self.data_img = np.zeros((1000,1000), dtype = 'uint8')
        self.data_img[400:600, 400:600] = 255
        self.data_img_item.setImage(self.data_img)

    def plot_mask_argb(self):
        self.data_mask = np.zeros((1000,1000,4), dtype = 'uint8')
        self.data_mask[500:700, 500:700, : ] = [255,0,0,150]
        self.mask_img_item.setImage(self.data_mask)


if __name__=='__main__':
    app = QtGui.QApplication(sys.argv)
    view = View()
    app.exec_()