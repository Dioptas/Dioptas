__author__ = 'Clemens Prescher'
import sys
from PyQt4 import QtGui
from Controller.MainController import MainController


if __name__ == "__main__":
    app = QtGui.QApplication(sys.argv)
    controller = MainController()
    controller.calibration_controller.load_calibration('ExampleData/LaB6_p49_001.poni')
    controller.calibration_controller.set_calibrant(7)
    controller.calibration_controller.load_file('ExampleData/LaB6_p49_001.tif')
    controller.calibration_controller.refine()
    app.exec_()