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


class NumberTextField(QtGui.QLineEdit):
    def __init__(self, *args, **kwargs):
        super(NumberTextField, self).__init__(*args, **kwargs)
        self.setValidator(QtGui.QDoubleValidator())
        self.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)

class IntegerTextField(QtGui.QLineEdit):
    def __init__(self, *args, **kwargs):
        super(IntegerTextField, self).__init__(*args, **kwargs)
        self.setValidator(QtGui.QIntValidator())
        self.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)


class LabelAlignRight(QtGui.QLabel):
    def __init__(self, *args, **kwargs):
        super(LabelAlignRight, self).__init__(*args, **kwargs)
        self.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)


class CleanLooksComboBox(QtGui.QComboBox):
    cleanlooks = QtGui.QStyleFactory.create('cleanlooks')

    def __init__(self, *args, **kwargs):
        super(CleanLooksComboBox, self).__init__(*args, **kwargs)
        self.setStyle(CleanLooksComboBox.cleanlooks)


class SpinBoxAlignRight(QtGui.QSpinBox):
    def __init__(self, *args, **kwargs):
        super(SpinBoxAlignRight, self).__init__(*args, **kwargs)
        self.setAlignment(QtCore.Qt.AlignRight)


class DoubleSpinBoxAlignRight(QtGui.QDoubleSpinBox):
    def __init__(self, *args, **kwargs):
        super(DoubleSpinBoxAlignRight, self).__init__(*args, **kwargs)
        self.setAlignment(QtCore.Qt.AlignRight)


class FlatButton(QtGui.QPushButton ):
    def __init__(self, *args):
        super(FlatButton, self).__init__(*args)
        self.setFlat(True)


class CheckableFlatButton(QtGui.QPushButton):
    def __init__(self, *args):
        super(CheckableFlatButton, self).__init__(*args)
        self.setFlat(True)
        self.setCheckable(True)

class HorizontalLine(QtGui.QFrame):
    def __init__(self):
        super(HorizontalLine, self).__init__()
        self.setFrameShape(QtGui.QFrame.HLine)
        self.setFrameShadow(QtGui.QFrame.Sunken)


class ListTableWidget(QtGui.QTableWidget):
    def __init__(self, columns = 3):
        super(ListTableWidget, self).__init__()

        self.setSelectionBehavior(QtGui.QAbstractItemView.SelectRows)
        self.setSelectionMode(QtGui.QAbstractItemView.SingleSelection)
        self.setColumnCount(columns)
        self.horizontalHeader().setVisible(False)
        self.verticalHeader().setVisible(False)
        self.horizontalHeader().setStretchLastSection(True)
        self.setShowGrid(False)

class NoRectDelegate(QtGui.QItemDelegate):
    def __init__(self):
        super(NoRectDelegate, self).__init__()

    def drawFocus(self, painter, option, rect):
        option.state &= ~QtGui.QStyle.State_HasFocus
        QtGui.QItemDelegate.drawFocus(self, painter, option, rect)




def HorizontalSpacerItem(minimum_width=0):
    return QtGui.QSpacerItem(minimum_width, 0, QtGui.QSizePolicy.MinimumExpanding, QtGui.QSizePolicy.Minimum)

def VerticalSpacerItem():
    return QtGui.QSpacerItem(0, 0, QtGui.QSizePolicy.Minimum, QtGui.QSizePolicy.Expanding)
