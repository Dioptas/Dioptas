__author__ = 'Clemens Prescher'

import os
from PyQt4 import QtGui, QtCore
from UiFiles.MaskUI import Ui_xrs_mask_widget
from ImgView import MaskImgView
import numpy as np
import pyqtgraph as pg


class MaskView(QtGui.QWidget, Ui_xrs_mask_widget):
    def __init__(self):
        super(MaskView, self).__init__(None)
        self.setupUi(self)
        #self.splitter.setStretchFactor(0, 1)
        self.img_view = MaskImgView(self.img_pg_layout)
        self.img_view.add_mouse_move_observer(self.show_img_mouse_position)
        self.set_validator()

    def set_validator(self):
        self.above_thresh_txt.setValidator(QtGui.QIntValidator())
        self.below_thresh_txt.setValidator(QtGui.QIntValidator())


    def show_img_mouse_position(self,x,y):
        try:
            if x > 0 and y > 0:
                str = "x: %8.1f   y: %8.1f   I: %6.f" % (x, y, self.img_view.img_data.T[np.floor(x), np.floor(y)])
            else:
                str = "x: %.1f y: %.1f" % (x, y)
        except (IndexError, AttributeError):
            str = "x: %.1f y: %.1f" % (x, y)
        self.pos_lbl.setText(str)