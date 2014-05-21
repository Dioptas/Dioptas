# -*- coding: utf8 -*-
__author__ = 'Clemens Prescher'

import os
from PyQt4 import QtGui, QtCore
from UiFiles.IntegrationUI import Ui_xrs_integration_widget
from ImgView import IntegrationImgView
from SpectrumView import SpectrumView
import numpy as np
import pyqtgraph as pg


class IntegrationView(QtGui.QWidget, Ui_xrs_integration_widget):
    def __init__(self):
        super(IntegrationView, self).__init__(None)
        self.setupUi(self)
        self.horizontal_splitter.setStretchFactor(0, 1)
        self.horizontal_splitter.setStretchFactor(1, 1)
        self.horizontal_splitter.setSizes([300, 200])
        self.vertical_splitter.setStretchFactor(0, 0)
        self.vertical_splitter.setStretchFactor(1, 1)
        self.vertical_splitter.setSizes([100, 700])
        self.img_view = IntegrationImgView(self.img_pg_layout, orientation='horizontal')
        self.spectrum_view = SpectrumView(self.spectrum_pg_layout)
        self.set_validator()
        self.set_correct_labels()

    def set_validator(self):
        self.phase_pressure_step_txt.setValidator(QtGui.QDoubleValidator())
        self.phase_temperature_step_txt.setValidator(QtGui.QDoubleValidator())
        self.overlay_scale_step_txt.setValidator(QtGui.QDoubleValidator())
        self.overlay_offset_step_txt.setValidator(QtGui.QDoubleValidator())

    def set_correct_labels(self):
        self.spec_unit_tth_rb.setText(u'2θ (°)')

    def switch_to_cake(self):
        self.img_view.img_view_box.setAspectLocked(False)
        self.img_view.activate_cross()

    def switch_to_img(self):
        self.img_view.img_view_box.setAspectLocked(True)
        self.img_view.deactivate_cross()
