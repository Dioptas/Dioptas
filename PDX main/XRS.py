__author__ = 'Clemens Prescher'
import sys
from PyQt4 import QtGui
from Controller.MainController import MainController


if __name__ == "__main__":
    app = QtGui.QApplication(sys.argv)
    app.setStyle('plastique')
    # possible values:
    # "windows", "motif", "cde", "plastique", "windowsxp", or "macintosh"
    controller = MainController()
    app.exec_()