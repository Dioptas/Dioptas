# -*- coding: utf-8 -*-
# Dioptas - GUI program for fast processing of 2D X-ray diffraction data
# Principal author: Clemens Prescher (clemens.prescher@gmail.com)
# Copyright (C) 2014-2019 GSECARS, University of Chicago, USA
# Copyright (C) 2015-2018 Institute for Geology and Mineralogy, University of Cologne, Germany
# Copyright (C) 2019-2020 DESY, Hamburg, Germany
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

from qtpy import QtCore, QtWidgets, QtGui
import os
from .CustomWidgets import FlatButton
from .. import style_path


class CifConversionParametersDialog(QtWidgets.QDialog):
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
        self.int_cutoff_lbl = QtWidgets.QLabel("Intensity Cutoff:")
        self.min_d_spacing_lbl = QtWidgets.QLabel("Minimum d-spacing:")

        self.int_cutoff_txt = QtWidgets.QLineEdit("0.5")
        self.int_cutoff_txt.setToolTip(
            "Reflections with lower Intensity won't be considered."
        )
        self.min_d_spacing_txt = QtWidgets.QLineEdit("0.5")
        self.min_d_spacing_txt.setToolTip(
            "Reflections with smaller d_spacing won't be considered."
        )

        self.int_cutoff_unit_lbl = QtWidgets.QLabel("%")
        self.min_d_spacing_unit_lbl = QtWidgets.QLabel("A")

        self.ok_btn = FlatButton("OK")

    def _layout_widgets(self):
        """
        Layouts the widgets into a gridlayout
        """
        self._layout = QtWidgets.QGridLayout()
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
        self.min_d_spacing_lbl.setAlignment(
            QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter
        )
        self.min_d_spacing_txt.setAlignment(
            QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter
        )
        self.min_d_spacing_txt.setMaximumWidth(40)

        self.int_cutoff_txt.setValidator(QtGui.QDoubleValidator())
        self.min_d_spacing_txt.setValidator(QtGui.QDoubleValidator())

        self.setWindowFlags(QtCore.Qt.FramelessWindowHint)

        file = open(os.path.join(style_path, "stylesheet.qss"))
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
        parent_center = self._parent.window().mapToGlobal(
            self._parent.window().rect().center()
        )
        self.move(parent_center.x() - 101, parent_center.y() - 48)
        super(CifConversionParametersDialog, self).exec_()


class FileInfoWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super(FileInfoWidget, self).__init__(parent)
        self.setWindowTitle("File Info")

        self.text_lbl = QtWidgets.QLabel()
        self.text_lbl.setWordWrap(True)

        self._layout = QtWidgets.QVBoxLayout()
        self._layout.setContentsMargins(5, 5, 5, 5)
        self._layout.addWidget(self.text_lbl)
        self._layout.setSizeConstraint(QtWidgets.QLayout.SetFixedSize)

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
        self.setWindowFlags(QtCore.Qt.Tool | QtCore.Qt.MSWindowsFixedSizeDialogHint)
        self.setAttribute(QtCore.Qt.WA_MacAlwaysShowToolWindow)

    def raise_widget(self):
        self.show()
        self.setWindowState(
            self.windowState() & ~QtCore.Qt.WindowMinimized | QtCore.Qt.WindowActive
        )
        self.activateWindow()
        self.raise_()


class ErrorMessageBox(QtWidgets.QDialog):
    def __init__(self, *args, **kwargs):
        super(ErrorMessageBox, self).__init__(*args, **kwargs)
        self.setWindowTitle("OOOPS! An error occurred!")

        self.text_lbl = QtWidgets.QLabel()
        self.text_lbl.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        self.scroll_area = QtWidgets.QScrollArea()

        self.scroll_area.setWidget(self.text_lbl)
        self.scroll_area.setWidgetResizable(True)
        self.ok_btn = QtWidgets.QPushButton("OK")

        _layout = QtWidgets.QGridLayout()
        _layout.addWidget(self.scroll_area, 0, 0, 1, 10)
        _layout.addWidget(self.ok_btn, 1, 9)

        self.setLayout(_layout)
        self.ok_btn.clicked.connect(self.close)

    def setText(self, text_str):
        self.text_lbl.setText(text_str)


def open_file_dialog(parent_widget, caption, directory, filter=None):
    filename = QtWidgets.QFileDialog.getOpenFileName(
        parent_widget, caption=caption, directory=directory, filter=filter
    )
    if isinstance(filename, tuple):  # PyQt5 returns a tuple...
        return str(filename[0])
    return str(filename)


def open_files_dialog(parent_widget, caption, directory, filter=None):
    filenames = QtWidgets.QFileDialog.getOpenFileNames(
        parent_widget, caption=caption, directory=directory, filter=filter
    )
    if isinstance(filenames, tuple):  # PyQt5 returns a tuple...
        filenames = filenames[0]
    return filenames


def save_file_dialog(parent_widget, caption, directory, filter=None):
    filename = QtWidgets.QFileDialog.getSaveFileName(
        parent_widget, caption, directory=directory, filter=filter
    )
    if isinstance(filename, tuple):  # PyQt5 returns a tuple...
        return set_extension(str(filename[0]), str(filename[1]))
    return str(filename)


def set_extension(filename, ext_filter):
    """
    Set extension to filename if not given.
    Extension is taken from filter string.

    :param filename: Name of file
    :param ext_filter: Filter string used in getSaveFileName dialog
    """
    name, ext = os.path.splitext(filename)

    # extension already given
    if ext != "":
        return filename

    # Extension can not be extracted from filter string
    if ext_filter.count("(") != 1:
        return filename

    ext = ext_filter[ext_filter.find("(") + 2 : ext_filter.find(")")]
    return f"{filename}{ext}"


def get_progress_dialog(
    message: str,
    abort_text: str,
    num_points: int,
    pos: tuple[float, float],
    parent=None,
) -> QtWidgets.QProgressDialog:
    progress_dialog = QtWidgets.QProgressDialog(
        message, abort_text, 0, num_points, parent=parent
    )
    progress_dialog.setWindowModality(QtCore.Qt.WindowModal)
    progress_dialog.setWindowFlags(QtCore.Qt.FramelessWindowHint)
    progress_dialog.move(
        int(pos[0] - progress_dialog.width() / 2), int(pos[1] - progress_dialog.height() / 2)
    )
    progress_dialog.show()
    return progress_dialog
