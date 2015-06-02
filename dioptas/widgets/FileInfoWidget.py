# -*- coding: utf8 -*-
__author__ = 'Clemens Prescher'

from PyQt4 import QtGui, QtCore


class FileInfoWidget(QtGui.QWidget):
    def __init__(self, parent=None):
        super(FileInfoWidget, self).__init__(parent)
        self.setWindowTitle("File Info")

        self.text_lbl = QtGui.QLabel()
        self.text_lbl.setWordWrap(True)

        self._layout = QtGui.QVBoxLayout()
        self._layout.setContentsMargins(5,5,5,5)
        self._layout.addWidget(self.text_lbl)
        self._layout.setSizeConstraint( QtGui.QLayout.SetFixedSize )

        self.setStyleSheet(
            """
            QWidget{
                background: rgb(0,0,0);
            }
            QLabel{
                color: #00DD00;
            }"""
        )
        self.setLayout(self._layout)
        self.setWindowFlags(QtCore.Qt.Tool | QtCore.Qt.WindowTitleHint | QtCore.Qt.WindowCloseButtonHint |
                            QtCore.Qt.CustomizeWindowHint | QtCore.Qt.MSWindowsFixedSizeDialogHint |
                            QtCore.Qt.X11BypassWindowManagerHint)
        self.setAttribute(QtCore.Qt.WA_MacAlwaysShowToolWindow)

    def raise_widget(self):
        self.show()
        self.setWindowState(self.windowState() & ~QtCore.Qt.WindowMinimized | QtCore.Qt.WindowActive)
        self.activateWindow()
        self.raise_()


if __name__ == '__main__':
    app = QtGui.QApplication([])
    widget = FileInfoWidget()
    widget.raise_widget()
    app.exec_()
