__author__ = 'Clemens Prescher'
import sys
from PyQt4 import QtGui
from Controller.MainController import MainController


if __name__ == "__main__":
    app = QtGui.QApplication(sys.argv)
    controller = MainController()
    app.exec_()