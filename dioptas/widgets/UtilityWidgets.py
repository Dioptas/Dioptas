# -*- coding: utf8 -*-
# Dioptas - GUI program for fast processing of 2D X-ray diffraction data
# Copyright (C) 2015  Clemens Prescher (clemens.prescher@gmail.com)
# Institute for Geology and Mineralogy, University of Cologne
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from PyQt4 import QtCore, QtGui
import os

widget_path = os.path.dirname(__file__)


class CifConversionParametersDialog(QtGui.QDialog):
    """
    Dialog which is asking for Intensity Cutoff and minimum d-spacing when loading cif files.
    """

    def __init__(self, parent):
        super(CifConversionParametersDialog, self).__init__()

        self._parent = parent
        self._create_widgets()
        self._layout_widgets()
        self._style_widgets()

        self._connect_widgets()

    def _create_widgets(self):
        """
        Creates all necessary widgets.
        """
        self.int_cutoff_lbl = QtGui.QLabel("Intensity Cutoff:")
        self.min_d_spacing_lbl = QtGui.QLabel("Minimum d-spacing:")

        self.int_cutoff_txt = QtGui.QLineEdit("0.5")
        self.int_cutoff_txt.setToolTip("Reflections with lower Intensity won't be considered.")
        self.min_d_spacing_txt = QtGui.QLineEdit("0.5")
        self.min_d_spacing_txt.setToolTip("Reflections with smaller d_spacing won't be considered.")

        self.int_cutoff_unit_lbl = QtGui.QLabel("%")
        self.min_d_spacing_unit_lbl = QtGui.QLabel("A")

        self.ok_btn = QtGui.QPushButton("OK")

    def _layout_widgets(self):
        """
        Layouts the widgets into a gridlayout
        """
        self._layout = QtGui.QGridLayout()
        self._layout.addWidget(self.int_cutoff_lbl, 0, 0)
        self._layout.addWidget(self.int_cutoff_txt, 0, 1)
        self._layout.addWidget(self.int_cutoff_unit_lbl, 0, 2)
        self._layout.addWidget(self.min_d_spacing_lbl, 1, 0)
        self._layout.addWidget(self.min_d_spacing_txt, 1, 1)
        self._layout.addWidget(self.min_d_spacing_unit_lbl, 1, 2)
        self._layout.addWidget(self.ok_btn, 2, 1, 1, 2)

        self.setLayout(self._layout)

    def _style_widgets(self):
        """
        Makes everything pretty and set Double validators for the line edits.
        """
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

    def _connect_widgets(self):
        """
        Connecting actions to slots.
        """
        self.ok_btn.clicked.connect(self.accept)

    @property
    def int_cutoff(self):
        """
        Returns the intensity cutoff selected in the dialog.
        """
        return float(str(self.int_cutoff_txt.text()))

    @property
    def min_d_spacing(self):
        """
        Returns the minimum d-spacing selected in the dialog.
        """
        return float(str(self.min_d_spacing_txt.text()))

    def exec_(self):
        """
        Overwriting the dialog exec_ function to center the widget in the parent window before execution.
        """
        parent_center = self._parent.window().mapToGlobal(self._parent.window().rect().center())
        self.move(parent_center.x() - 101, parent_center.y() - 48)
        super(CifConversionParametersDialog, self).exec_()

class FileInfoWidget(QtGui.QWidget):
    def __init__(self, parent=None):
        super(FileInfoWidget, self).__init__(parent)
        self.setWindowTitle("File Info")

        self.text_lbl = QtGui.QLabel()
        self.text_lbl.setWordWrap(True)

        self._layout = QtGui.QVBoxLayout()
        self._layout.setContentsMargins(5, 5, 5, 5)
        self._layout.addWidget(self.text_lbl)
        self._layout.setSizeConstraint(QtGui.QLayout.SetFixedSize)

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
    widget = CifConversionParametersDialog(None)
    widget.show()
    widget.raise_()
    app.exec_()
