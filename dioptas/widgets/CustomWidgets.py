# -*- coding: utf-8 -*-
# Dioptas - GUI program for fast processing of 2D X-ray diffraction data
# Principal author: Clemens Prescher (clemens.prescher@gmail.com)
# Copyright (C) 2013-2019 GSECARS, University of Chicago, USA
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
import time

import os
from qtpy import QtCore, QtWidgets, QtGui
from math import floor, log10

from .. import icons_path


class NumberTextField(QtWidgets.QLineEdit):
    def __init__(self, *args, **kwargs):
        super(NumberTextField, self).__init__(*args, **kwargs)
        self.setValidator(QtGui.QDoubleValidator())
        self.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)

    def text(self):
        return super(NumberTextField, self).text().replace(",", ".")

    def value(self):
        return float(self.text())


class IntegerTextField(QtWidgets.QLineEdit):
    def __init__(self, *args, **kwargs):
        super(IntegerTextField, self).__init__(*args, **kwargs)
        self.setValidator(QtGui.QIntValidator())
        self.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)


class LabelAlignRight(QtWidgets.QLabel):
    def __init__(self, *args, **kwargs):
        super(LabelAlignRight, self).__init__(*args, **kwargs)
        self.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)


class LabelExpandable(QtWidgets.QLineEdit):
    def __init__(self, *args, **kwargs):
        super(LabelExpandable, self).__init__(*args, **kwargs)
        self.setStyleSheet(
            """
            color: #F1F1F1;
            background: #3C3C3C;
        """
        )
        self.setReadOnly(True)


class CleanLooksComboBox(QtWidgets.QComboBox):
    cleanlooks = QtWidgets.QStyleFactory.create("motif")

    def __init__(self, *args, **kwargs):
        super(CleanLooksComboBox, self).__init__(*args, **kwargs)
        self.setStyle(CleanLooksComboBox.cleanlooks)
        self.setLineEdit(CleanLooksLineEdit())
        self.lineEdit().clicked.connect(self.showPopup)
        self.popup_closed_time = time.time()

    def showPopup(self):
        if time.time() - self.popup_closed_time > 0.01:
            # prevents showing popup immediately after closing by clicking onto lineEdit.
            super(CleanLooksComboBox, self).showPopup()

    def hidePopup(self):
        super(CleanLooksComboBox, self).hidePopup()
        self.popup_closed_time = time.time()


class CleanLooksLineEdit(QtWidgets.QLineEdit):
    clicked = QtCore.Signal()

    def __init__(self, *args, **kwargs):
        super(CleanLooksLineEdit, self).__init__(*args, **kwargs)
        self.installEventFilter(self)
        self.setReadOnly(True)
        self.setStyleSheet(
            """
                margin: 2px; 
                background: #3C3C3C;
            """
        )

    def eventFilter(self, obj, event):
        if event.type() == QtCore.QEvent.MouseButtonPress:
            self.clicked.emit()
            return True
        if event.type() == QtCore.QEvent.MouseMove:
            return True
        return super(CleanLooksLineEdit, self).eventFilter(obj, event)


class SpinBoxAlignRight(QtWidgets.QSpinBox):
    def __init__(self, *args, **kwargs):
        super(SpinBoxAlignRight, self).__init__(*args, **kwargs)
        self.setAlignment(QtCore.Qt.AlignRight)


class DoubleSpinBoxAlignRight(QtWidgets.QDoubleSpinBox):
    def __init__(self, *args, **kwargs):
        super(DoubleSpinBoxAlignRight, self).__init__(*args, **kwargs)
        self.setAlignment(QtCore.Qt.AlignRight)


class DoubleMultiplySpinBoxAlignRight(QtWidgets.QDoubleSpinBox):
    def __init__(self, *args, **kwargs):
        super(DoubleMultiplySpinBoxAlignRight, self).__init__(*args, **kwargs)
        self.setAlignment(QtCore.Qt.AlignRight)

    def stepBy(self, p_int):
        self.setValue(self.calc_new_step(self.value(), p_int))

    def calc_new_step(self, value, p_int):
        pow10floor = 10 ** floor(log10(value))
        if p_int > 0:
            if value / pow10floor < 1.9:
                return pow10floor * 2.0
            elif value / pow10floor < 4.9:
                return pow10floor * 5.0
            else:
                return pow10floor * 10.0
        else:
            if value / pow10floor < 1.1:
                return pow10floor / 2.0
            elif value / pow10floor < 2.1:
                return pow10floor
            elif value / pow10floor < 5.1:
                return pow10floor * 2.0
            else:
                return pow10floor * 5.0


class ConservativeSpinBox(QtWidgets.QSpinBox):
    """
    This is a modification of the QSpinBox class. The ConservativeSpinbox does not emit the valueChanged signal for
    every keypress in the lineedit. The signal is only emitted for the following occasions:
      - pressing enter
      - the spinbox loses focus
      - pressing the up or down arrows
    Also the wheel events are disabled.

    This Spinbox is intended for usage with applications were the change in the spinbox value causes long calculations
    and does a valueChanged signal on every keypress results in a strange behavior.
    """

    valueChanged = QtCore.Signal()

    def __init__(self):
        super(QtWidgets.QSpinBox, self).__init__()

        self.lineEdit().editingFinished.connect(self.valueChanged)
        self.lineEdit().setAlignment(QtCore.Qt.AlignRight)

    def mousePressEvent(self, e: QtGui.QMouseEvent):
        opt = QtWidgets.QStyleOptionSpinBox()
        self.initStyleOption(opt)

        if (
            self.style()
            .subControlRect(
                QtWidgets.QStyle.CC_SpinBox, opt, QtWidgets.QStyle.SC_SpinBoxUp
            )
            .contains(e.pos())
        ):
            self.setValue(self.value() + 1)
            self.valueChanged.emit()
        elif (
            self.style()
            .subControlRect(
                QtWidgets.QStyle.CC_SpinBox, opt, QtWidgets.QStyle.SC_SpinBoxDown
            )
            .contains(e.pos())
        ):
            self.setValue(self.value() - 1)
            self.valueChanged.emit()

    def wheelEvent(self, e: QtGui.QWheelEvent):
        pass


class FlatButton(QtWidgets.QPushButton):
    def __init__(self, *args):
        super(FlatButton, self).__init__(*args)
        self.setFlat(True)
        self.setStyleSheet(
            """
            QPushButton {
                border: none;
                padding: 5px;
             
            }"""
        )

    def setHeight(self, height):
        self.setMinimumHeight(height)
        self.setMaximumHeight(height)

    def setWidth(self, width):
        self.setMinimumWidth(width)
        self.setMaximumWidth(width)


class CheckableFlatButton(FlatButton):
    def __init__(self, *args):
        super(CheckableFlatButton, self).__init__(*args)
        self.setCheckable(True)


class RotatedCheckableFlatButton(CheckableFlatButton):
    def __init__(self, *args):
        super(RotatedCheckableFlatButton, self).__init__(*args)

    def paintEvent(self, event):
        painter = QtWidgets.QStylePainter(self)
        painter.rotate(270)
        painter.translate(-1 * self.height(), 0)
        painter.drawControl(QtWidgets.QStyle.CE_PushButton, self.getSyleOptions())

    def minimumSizeHint(self):
        size = super(RotatedCheckableFlatButton, self).minimumSizeHint()
        size.transpose()
        return size

    def sizeHint(self):
        size = super(RotatedCheckableFlatButton, self).sizeHint()
        size.transpose()
        return size

    def getSyleOptions(self):
        options = QtWidgets.QStyleOptionButton()
        options.initFrom(self)
        size = options.rect.size()
        size.transpose()
        options.rect.setSize(size)
        if self.isFlat():
            options.features |= QtWidgets.QStyleOptionButton.Flat
        if self.menu():
            options.features |= QtWidgets.QStyleOptionButton.HasMenu
        if self.autoDefault() or self.isDefault():
            options.features |= QtWidgets.QStyleOptionButton.AutoDefaultButton
        if self.isDefault():
            options.features |= QtWidgets.QStyleOptionButton.DefaultButton
        if self.isDown() or (self.menu() and self.menu().isVisible()):
            options.state |= QtWidgets.QStyle.State_Sunken
        if self.isChecked():
            options.state |= QtWidgets.QStyle.State_On
        if not self.isFlat() and not self.isDown():
            options.state |= QtWidgets.QStyle.State_Raised

        options.text = self.text()
        options.icon = self.icon()
        options.iconSize = self.iconSize()
        return options


class SaveIconButton(FlatButton):
    def __init__(self):
        super(SaveIconButton, self).__init__()
        self.setIcon(QtGui.QIcon(os.path.join(icons_path, "save.ico")))


class OpenIconButton(FlatButton):
    def __init__(self):
        super(OpenIconButton, self).__init__()
        self.setIcon(QtGui.QIcon(os.path.join(icons_path, "open.ico")))


class ResetIconButton(FlatButton):
    def __init__(self):
        super(ResetIconButton, self).__init__()
        self.setIcon(QtGui.QIcon(os.path.join(icons_path, "reset.ico")))


class HorizontalLine(QtWidgets.QFrame):
    def __init__(self):
        super(HorizontalLine, self).__init__()
        self.setFrameShape(QtWidgets.QFrame.HLine)
        self.setFrameShadow(QtWidgets.QFrame.Sunken)
        self.setFixedHeight(1)


class VerticalLine(QtWidgets.QFrame):
    def __init__(self):
        super(VerticalLine, self).__init__()
        self.setFrameShape(QtWidgets.QFrame.VLine)
        self.setFrameShadow(QtWidgets.QFrame.Sunken)
        self.setFixedWidth(1)


class ListTableWidget(QtWidgets.QTableWidget):
    def __init__(self, columns=3):
        super(ListTableWidget, self).__init__()

        self.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.setColumnCount(columns)
        self.horizontalHeader().setVisible(False)
        self.verticalHeader().setVisible(False)
        self.horizontalHeader().setStretchLastSection(True)
        self.setShowGrid(False)


class NoRectDelegate(QtWidgets.QItemDelegate):
    def __init__(self):
        super(NoRectDelegate, self).__init__()

    def drawFocus(self, painter, option, rect):
        option.state &= ~QtWidgets.QStyle.State_HasFocus
        QtWidgets.QItemDelegate.drawFocus(self, painter, option, rect)


def HorizontalSpacerItem(minimum_width=0):
    return QtWidgets.QSpacerItem(
        minimum_width,
        0,
        QtWidgets.QSizePolicy.MinimumExpanding,
        QtWidgets.QSizePolicy.Minimum,
    )


def VerticalSpacerItem():
    return QtWidgets.QSpacerItem(
        0, 0, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.MinimumExpanding
    )
