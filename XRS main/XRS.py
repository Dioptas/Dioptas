__author__ = 'Clemens Prescher'
import sys
from PyQt4 import QtGui
from Controller.XrsIntegrationController import XrsIntegrationController
from Controller.XrsCalibrationController import XrsCalibrationController
from Controller.XrsMaskController import XrsMaskController
from Controller.XrsIntegrationController import XrsIntegrationController


if __name__ == "__main__":
    app = QtGui.QApplication(sys.argv)
    controller = XrsIntegrationController()
    app.exec_()