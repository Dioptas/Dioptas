__author__ = 'Clemens Prescher'
import sys
from PyQt4 import QtGui
from Controller.IntegrationController import IntegrationController
from Controller.CalibrationController import CalibrationController
from Controller.MaskController import MaskController
from Controller.IntegrationController import IntegrationController


if __name__ == "__main__":
    app = QtGui.QApplication(sys.argv)
    controller = CalibrationController()
    app.exec_()