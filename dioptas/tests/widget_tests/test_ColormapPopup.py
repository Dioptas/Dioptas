# SPDX-License-Identifier: MIT
"""Test ColormapPopup widget"""

import numpy as np
import pytest
from qtpy import QtCore, QtWidgets
from qtpy.QtTest import QSignalSpy, QTest

import pyqtgraph.graphicsItems.GradientEditorItem

from ...widgets.plot_widgets.ColormapPopup import ColormapPopup


def testRange(qWidgetFactory):
    """Test getRange, setRange and sigRangeChanged"""
    colormapPopup = qWidgetFactory(ColormapPopup)
    assert colormapPopup.getRange() == (1, 1)

    signalSpy = QSignalSpy(colormapPopup.sigRangeChanged)

    colormapPopup.setRange(100, 1000)
    assert len(signalSpy) == 1
    assert signalSpy[0] == [100, 1000]
    assert colormapPopup.getRange() == (100, 1000)

    colormapPopup.setRange(2000, 1000)
    assert len(signalSpy) == 2
    assert signalSpy[1] == [1000, 2000]
    assert colormapPopup.getRange() == (1000, 2000)


def testCurrentGradient(qWidgetFactory):
    """Test getCurrentGradient, setCurrentGradient and sigCurrentGradientChanged"""
    colormapPopup = qWidgetFactory(ColormapPopup)
    for firstName, firstGradient in pyqtgraph.graphicsItems.GradientEditorItem.Gradients.items():
        break
    gradient = colormapPopup.getCurrentGradient()
    assert gradient == firstGradient
    assert colormapPopup._gradientComboBox.currentText() == firstName.capitalize()
 
    signalSpy = QSignalSpy(colormapPopup.sigCurrentGradientChanged)
    viridisGradient = pyqtgraph.graphicsItems.GradientEditorItem.Gradients['viridis']
    colormapPopup.setCurrentGradient(viridisGradient)
    gradient = colormapPopup.getCurrentGradient()
    assert gradient == viridisGradient
    assert colormapPopup._gradientComboBox.currentText() == 'Viridis'
    assert len(signalSpy) == 1
    assert signalSpy[0] == [viridisGradient]


def testCustomGradient(qWidgetFactory):
    """Test setCurrentGradient with a custom gradient"""
    colormapPopup = qWidgetFactory(ColormapPopup)
    signalSpy = QSignalSpy(colormapPopup.sigCurrentGradientChanged)

    customGradient = {
        'mode': 'rgb',
        'ticks': [(0.0, (0, 0, 0, 255)), (1.0, (0, 0, 0, 255))],
    }
    colormapPopup.setCurrentGradient(customGradient)
    gradient = colormapPopup.getCurrentGradient()
    assert gradient == customGradient
    assert colormapPopup._gradientComboBox.currentText() == 'Custom'
    assert len(signalSpy) == 1
    assert signalSpy[0] == [customGradient]

    customGradient2 = {
        'mode': 'rgb',
        'ticks': [(0.0, (255, 255, 255, 255)), (1.0, (255, 255, 255, 255))],
    }
    colormapPopup.setCurrentGradient(customGradient2)
    gradient = colormapPopup.getCurrentGradient()
    assert gradient == customGradient2
    assert colormapPopup._gradientComboBox.currentText() == 'Custom'
    assert len(signalSpy) == 2
    assert signalSpy[1] == [customGradient2]


@pytest.mark.parametrize("normalization", ["log", "sqrt"])
def testCurrentNormalization(qWidgetFactory, normalization):
    """Test getCurrentNormalization, setCurrentNormalization and sigCurrentNormalizationChanged"""
    colormapPopup = qWidgetFactory(ColormapPopup)

    default_normalization = colormapPopup.getCurrentNormalization()
    assert default_normalization == "linear"
    assert colormapPopup._normalizationComboBox.currentText() == "Linear"
    assert colormapPopup._normalizationComboBox.currentData() == "linear"

    signalSpy = QSignalSpy(colormapPopup.sigCurrentNormalizationChanged)
    colormapPopup.setCurrentNormalization(normalization)
    returned_normalization = colormapPopup.getCurrentNormalization()
    assert returned_normalization == normalization
    assert colormapPopup._normalizationComboBox.currentData() == normalization
    assert len(signalSpy) == 1
    assert signalSpy[0] == [normalization]


def testResetMode(qWidgetFactory):
    """Test reset range and changing reset mode"""
    colormapPopup = qWidgetFactory(ColormapPopup)
    colormapPopup.setData(np.arange(101))

    buttons = colormapPopup._resetButtonGroup.buttons()
    percentileButton, minmaxButton, mean3stdButton = buttons

    # Default is Percentile with slider at 0.4%
    assert colormapPopup._resetButtonGroup.checkedButton() == percentileButton
    mode = colormapPopup._getResetMode()
    assert mode == "0.4percentile"

    QTest.mouseClick(colormapPopup._autoscaleButton, QtCore.Qt.LeftButton)
    range_ = colormapPopup.getRange()
    assert range_ == (0.4, 99.6)

    minmaxButton.click()
    mode = colormapPopup._getResetMode()
    range_ = colormapPopup.getRange()
    assert mode == "minmax"
    assert range_ == (0, 100)
    assert not colormapPopup._percentileSlider.isVisible()

    # Move slider to ~1% and switch back to percentile
    colormapPopup._percentileSlider.setValue(
        colormapPopup._percentile_to_slider(1.0)
    )
    percentileButton.click()
    mode = colormapPopup._getResetMode()
    assert "percentile" in mode
    range_ = colormapPopup.getRange()
    assert np.allclose(range_, (1.0, 99.0), atol=0.1)
    assert colormapPopup._percentileSlider.isVisible()

    mean3stdButton.click()
    mode = colormapPopup._getResetMode()
    range_ = colormapPopup.getRange()
    assert mode == "mean3std"
    assert range_ == (0, 100)
    assert not colormapPopup._percentileSlider.isVisible()
