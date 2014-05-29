__author__ = 'Clemens Prescher'
import sys
from PyQt4 import QtGui
from Controller.MainController import MainController
from Data.PhaseData import PhaseData


def test_calibration():
    app = QtGui.QApplication(sys.argv)
    controller = MainController()
    controller.calibration_controller.load_calibration('ExampleData/LaB6_p49_001.poni')
    controller.calibration_controller.set_calibrant(7)
    controller.calibration_controller.load_file('ExampleData/LaB6_p49_001.tif')
    controller.calibration_controller.refine()
    app.exec_()


if __name__ == "__main__":
    import numpy as np

    app = QtGui.QApplication(sys.argv)
    controller = MainController()
    controller.calibration_controller.load_calibration('ExampleData/LaB6_p49_001.poni')
    controller.view.tabWidget.setCurrentIndex(2)
    controller.integration_controller.image_controller.load_file_btn_click(
        '/Users/Doomgoroth/Programming/Large Projects/Py2DeX/PDX main/ExampleData/Mg2SiO4_ambient_001.tif')
    controller.integration_controller.image_controller.load_next_img()
    #get phase
    controller.integration_controller.phase_controller.add_phase('ExampleData/jcpds/dac_user/au_Anderson.jcpds')
    app.exec_()