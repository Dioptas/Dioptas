# -*- coding: utf8 -*-
__author__ = 'Clemens Prescher'

from PyQt4 import QtCore, QtGui
import os

widget_path = os.path.dirname(__file__)


class CifConversionParametersWidget(QtGui.QDialog):
    def __init__(self):
        super(CifConversionParametersWidget, self).__init__()

        self.create_widgets()
        self.layout_widgets()
        self.style_widgets()

        self.connect_widgets()

    def create_widgets(self):
        self.int_cutoff_lbl = QtGui.QLabel("Intensity Cutoff:")
        self.min_d_spacing_lbl = QtGui.QLabel("Minimum d-spacing:")

        self.int_cutoff_txt = QtGui.QLineEdit("0.5")
        self.int_cutoff_txt.setToolTip("Reflections with lower Intensity won't be considered.")
        self.min_d_spacing_txt = QtGui.QLineEdit("0.5")
        self.min_d_spacing_txt.setToolTip("Reflections with smaller d_spacing won't be considered.")

        self.int_cutoff_unit_lbl = QtGui.QLabel("%")
        self.min_d_spacing_unit_lbl = QtGui.QLabel("A")

        self.ok_btn = QtGui.QPushButton("OK")

    def layout_widgets(self):
        self._layout = QtGui.QGridLayout()
        self._layout.addWidget(self.int_cutoff_lbl, 0, 0)
        self._layout.addWidget(self.int_cutoff_txt, 0, 1)
        self._layout.addWidget(self.int_cutoff_unit_lbl, 0, 2)
        self._layout.addWidget(self.min_d_spacing_lbl, 1, 0)
        self._layout.addWidget(self.min_d_spacing_txt, 1, 1)
        self._layout.addWidget(self.min_d_spacing_unit_lbl, 1, 2)
        self._layout.addWidget(self.ok_btn, 2, 1, 1, 2)

        self.setLayout(self._layout)

    def style_widgets(self):
        self.int_cutoff_lbl.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        self.int_cutoff_txt.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        self.int_cutoff_txt.setMaximumWidth(40)
        self.min_d_spacing_lbl.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        self.min_d_spacing_txt.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        self.min_d_spacing_txt.setMaximumWidth(40)

        self.int_cutoff_txt.setValidator(QtGui.QDoubleValidator())
        self.min_d_spacing_txt.setValidator(QtGui.QDoubleValidator())

        self.setWindowFlags(QtCore.Qt.FramelessWindowHint)

        file = open(os.path.join(widget_path, "stylesheet.qss"))
        stylesheet = file.read()
        self.setStyleSheet(stylesheet)
        file.close()

    def connect_widgets(self):
        self.ok_btn.clicked.connect(self.accept)

    @property
    def int_cutoff(self):
        return float(str(self.int_cutoff_txt.text()))

    @property
    def min_d_spacing(self):
        return float(str(self.min_d_spacing_txt.text()))


if __name__ == '__main__':
    app = QtGui.QApplication([])
    widget = CifConversionParametersWidget(None)
    widget.show()
    widget.raise_()
    app.exec_()
