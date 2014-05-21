__author__ = 'Clemens Prescher'

import os
import sys
from PyQt4 import QtGui, QtCore
from UiFiles.MainUI import Ui_mainView

from Views.MaskView import MaskView
from Views.IntegrationView import IntegrationView
from Views.CalibrationView import CalibrationView


class MainView(QtGui.QWidget, Ui_mainView):
    def __init__(self):
        super(MainView, self).__init__(None)
        self.setupUi(self)

        self.calibration_widget = CalibrationView()
        self.mask_widget = MaskView()
        self.integration_widget = IntegrationView()

        self.calibration_layout = QtGui.QHBoxLayout()
        self.calibration_layout.setContentsMargins(0, 0, 0, 0)
        self.calibration_tab.setLayout(self.calibration_layout)
        self.calibration_layout.addWidget(self.calibration_widget)

        self.mask_layout = QtGui.QHBoxLayout()
        self.mask_layout.setContentsMargins(0, 0, 0, 0)
        self.mask_tab.setLayout(self.mask_layout)
        self.mask_layout.addWidget(self.mask_widget)

        self.integration_layout = QtGui.QHBoxLayout()
        self.integration_layout.setContentsMargins(0, 0, 0, 0)
        self.integration_tab.setLayout(self.integration_layout)
        self.integration_layout.addWidget(self.integration_widget)


if __name__ == "__main__":
    app = QtGui.QApplication(sys.argv)
    view = MainView()
    view.show()
    app.exec_()