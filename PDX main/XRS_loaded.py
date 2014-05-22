__author__ = 'Clemens Prescher'
import sys
from PyQt4 import QtGui
from Controller.MainController import MainController


if __name__ == "__main__":
    app = QtGui.QApplication(sys.argv)
    controller = MainController()
    controller.calibration_controller.load_calibration('ExampleData/calibration.poni')
    controller.integration_controller.file_controller.load_file_btn_click('ExampleData/Mg2SiO4_ambient_001.tif')
    controller.view.tabWidget.setCurrentIndex(2)
    controller.view.integration_widget.cake_rb.setChecked(True)
    controller.integration_controller.file_controller.update_img()
    app.exec_()