# -*- coding: utf8 -*-
# Dioptas - GUI program for fast processing of 2D X-ray diffraction data
# Copyright (C) 2017  Clemens Prescher (clemens.prescher@gmail.com)
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

from qtpy import QtCore, QtWidgets, QtGui
from math import floor, log10


class NumberTextField(QtWidgets.QLineEdit):
    def __init__(self, *args, **kwargs):
        super(NumberTextField, self).__init__(*args, **kwargs)
        self.setValidator(QtGui.QDoubleValidator())
        self.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)


class IntegerTextField(QtWidgets.QLineEdit):
    def __init__(self, *args, **kwargs):
        super(IntegerTextField, self).__init__(*args, **kwargs)
        self.setValidator(QtGui.QIntValidator())
        self.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)


class LabelAlignRight(QtWidgets.QLabel):
    def __init__(self, *args, **kwargs):
        super(LabelAlignRight, self).__init__(*args, **kwargs)
        self.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)


class CleanLooksComboBox(QtWidgets.QComboBox):
    cleanlooks = QtWidgets.QStyleFactory.create('motif')

    def __init__(self, *args, **kwargs):
        super(CleanLooksComboBox, self).__init__(*args, **kwargs)
        self.setStyle(CleanLooksComboBox.cleanlooks)


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
        pow10floor = 10**floor(log10(value))
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


class FlatButton(QtWidgets.QPushButton):
    def __init__(self, *args):
        super(FlatButton, self).__init__(*args)
        self.setFlat(True)


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
        painter.translate(-1*self.height(), 0)
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


class HorizontalLine(QtWidgets.QFrame):
    def __init__(self):
        super(HorizontalLine, self).__init__()
        self.setFrameShape(QtWidgets.QFrame.HLine)
        self.setFrameShadow(QtWidgets.QFrame.Sunken)


class VerticalLine(QtWidgets.QFrame):
    def __init__(self):
        super(VerticalLine, self).__init__()
        self.setFrameShape(QtWidgets.QFrame.VLine)
        self.setFrameShadow(QtWidgets.QFrame.Sunken)


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
    return QtWidgets.QSpacerItem(minimum_width, 0, QtWidgets.QSizePolicy.MinimumExpanding,
                                 QtWidgets.QSizePolicy.Minimum)


def VerticalSpacerItem():
    return QtWidgets.QSpacerItem(0, 0, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Expanding)
