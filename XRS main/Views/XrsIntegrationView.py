__author__ = 'Clemens Prescher'

import os
from PyQt4 import QtGui, QtCore
from UiFiles.XrsIntegrationUI import Ui_xrs_integration_widget
from ImgView import MaskImgView
from SpectrumView import SpectrumView
import numpy as np
import pyqtgraph as pg


class XrsIntegrationView(QtGui.QWidget, Ui_xrs_integration_widget):
    def __init__(self):
        super(XrsIntegrationView, self).__init__(None)
        self.setupUi(self)
        self.horizontal_splitter.setStretchFactor(0,1)
        self.horizontal_splitter.setStretchFactor(1,1)
        self.horizontal_splitter.setSizes([300,200])
        self.vertical_splitter.setStretchFactor(0,0)
        self.vertical_splitter.setStretchFactor(1,1)
        self.vertical_splitter.setSizes([100,700])
        self.img_view = MaskImgView(self.img_pg_layout, orientation='horizontal')
        self.img_view.add_mouse_move_observer(self.show_img_mouse_position)
        self.spectrum_view = SpectrumView(self.spectrum_pg_layout)


    def show_img_mouse_position(self,x,y):
        try:
            if x > 0 and y > 0:
                x_pos_string = 'X: %4.1f' % x
                y_pos_string = 'Y: %4.1f' % y
                self.x_lbl.setText(x_pos_string)
                self.y_lbl.setText(y_pos_string)
            else:
                self.x_lbl.setText('')
                self.y_lbl.setText('')

        except (IndexError, AttributeError):
            self.x_lbl.setText('')
            self.y_lbl.setText('')