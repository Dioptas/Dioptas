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
"""Test ColormapDialog widget"""

import pytest
from qtpy import QtCore, QtWidgets
from qtpy.QtTest import QSignalSpy, QTest

import pyqtgraph.graphicsItems.GradientEditorItem

from ...widgets.plot_widgets.ColormapDialog import ColormapDialog


@pytest.fixture
def colormapDialog(qapp):
    """Fixture providing an instance of a ColormapDialog"""
    dialog = ColormapDialog()
    dialog.show()
    QTest.qWaitForWindowExposed(dialog)
    try:
        yield dialog
    finally:
        dialog.accept()
        qapp.processEvents()


def testRange(colormapDialog):
    """"Test getRange, setRange and sigRangeChanged"""
    assert colormapDialog.getRange() == (1, 1)

    signalSpy = QSignalSpy(colormapDialog.sigRangeChanged)

    colormapDialog.setRange(100, 1000)
    assert len(signalSpy) == 1
    assert signalSpy[0] == [100, 1000]
    assert colormapDialog.getRange() == (100, 1000)

    colormapDialog.setRange(2000, 1000)
    assert len(signalSpy) == 2
    assert signalSpy[1] == [1000, 2000]
    assert colormapDialog.getRange() == (1000, 2000)


def testCurrentGradient(colormapDialog):
    """Test getCurrentGradient, setCurrentGradient and sigCurrentGradientChanged"""
    for firstName, firstGradient in pyqtgraph.graphicsItems.GradientEditorItem.Gradients.items():
        break
    gradient = colormapDialog.getCurrentGradient()
    assert gradient == firstGradient
    assert colormapDialog._gradientComboBox.currentText() == firstName.capitalize()
 
    signalSpy = QSignalSpy(colormapDialog.sigCurrentGradientChanged)
    viridisGradient = pyqtgraph.graphicsItems.GradientEditorItem.Gradients['viridis']
    colormapDialog.setCurrentGradient(viridisGradient)
    gradient = colormapDialog.getCurrentGradient()
    assert gradient == viridisGradient
    assert colormapDialog._gradientComboBox.currentText() == 'Viridis'
    assert len(signalSpy) == 1
    assert signalSpy[0] == [viridisGradient]


def testCustomGradient(colormapDialog):
    """Test setCurrentGradient with a custom gradient"""
    signalSpy = QSignalSpy(colormapDialog.sigCurrentGradientChanged)

    customGradient = {
        'mode': 'rgb',
        'ticks': [(0.0, (0, 0, 0, 255)), (1.0, (0, 0, 0, 255))],
    }
    colormapDialog.setCurrentGradient(customGradient)
    gradient = colormapDialog.getCurrentGradient()
    assert gradient == customGradient
    assert colormapDialog._gradientComboBox.currentText() == 'Custom'
    assert len(signalSpy) == 1
    assert signalSpy[0] == [customGradient]

    customGradient2 = {
        'mode': 'rgb',
        'ticks': [(0.0, (255, 255, 255, 255)), (1.0, (255, 255, 255, 255))],
    }
    colormapDialog.setCurrentGradient(customGradient2)
    gradient = colormapDialog.getCurrentGradient()
    assert gradient == customGradient2
    assert colormapDialog._gradientComboBox.currentText() == 'Custom'
    assert len(signalSpy) == 2
    assert signalSpy[1] == [customGradient2]
