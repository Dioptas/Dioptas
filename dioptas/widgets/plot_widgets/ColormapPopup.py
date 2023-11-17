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
from __future__ import annotations

import pathlib
from typing import Optional

from qtpy import QtGui, QtCore, QtWidgets
import pyqtgraph.graphicsItems.GradientEditorItem
import numpy as np

from . import utils
from .NormalizedImageItem import NormalizedImageItem
from ... import style_path


class ColormapPopup(QtWidgets.QFrame):
    """Dialog providing control over the currently used colormap"""

    sigCurrentGradientChanged = QtCore.Signal(dict)
    """Signal emitted when the colormap gradient has changed"""

    sigCurrentNormalizationChanged = QtCore.Signal(str)
    """Signal emitted when the colormap normalization has changed"""

    sigRangeChanged = QtCore.Signal(float, float)
    """Signal emitted when the data range has changed"""

    _RESET_MODES = {  # Button text: (mode, tooltip)
        "Default": ("default", "Use default colormap range autoscale"),
        "Min/max": ("minmax", "Use data min/max to scale colormap range"),
        "Mean±3 Std": ("mean3std", "Use data mean ± 3 × standard deviation to scale colormap range"),
        "Percentile": ("1percentile", "Use data 1st and 99th percentile to scale colormap range"),
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self._data = None
        self.setWindowTitle("Colormap configuration")
        self.setWindowFlags(QtCore.Qt.Popup)
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose)
        self.setStyleSheet(
            pathlib.Path(style_path, "stylesheet.qss").read_text()
        )
        self.setFrameStyle(QtWidgets.QFrame.Panel | QtWidgets.QFrame.Raised)
        self.setLineWidth(2)

        frameLayout = QtWidgets.QVBoxLayout(self)
        frameLayout.setContentsMargins(3, 3, 3, 3)
        frameLayout.setSpacing(3)

        colormapGroupBox = QtWidgets.QGroupBox("Colormap", self)
        frameLayout.addWidget(colormapGroupBox)
        colormapLayout = QtWidgets.QFormLayout(colormapGroupBox)
        colormapLayout.setLabelAlignment(QtCore.Qt.AlignRight)

        self._gradientComboBox = QtWidgets.QComboBox(self)
        for name, gradient in pyqtgraph.graphicsItems.GradientEditorItem.Gradients.items():
            icon = self._createQIconFromGradient(gradient)
            self._gradientComboBox.addItem(icon, name.capitalize(), gradient)
        self._gradientComboBox.currentIndexChanged.connect(self._gradientComboBoxCurrentIndexChanged)
        colormapLayout.addRow('Colormap:', self._gradientComboBox)

        self._normalizationComboBox = QtWidgets.QComboBox(self)
        for normalization in NormalizedImageItem.supportedNormalizations():
            description = NormalizedImageItem.getNormalizationDescription(normalization).capitalize()
            self._normalizationComboBox.addItem(description, normalization)

        self._normalizationComboBox.setCurrentIndex(0)
        self._normalizationComboBox.currentIndexChanged.connect(self._normalizationComboBoxCurrentIndexChanged)
        colormapLayout.addRow('Normalization:', self._normalizationComboBox)

        rangeGroupBox = QtWidgets.QGroupBox("Range", self)
        frameLayout.addWidget(rangeGroupBox)
        rangeLayout = QtWidgets.QFormLayout(rangeGroupBox)
        rangeLayout.setLabelAlignment(QtCore.Qt.AlignRight)

        self._minEdit = QtWidgets.QLineEdit(self)
        self._minEdit.setValidator(QtGui.QDoubleValidator(1, float('inf'), -1))
        self._minEdit.editingFinished.connect(self._rangeChanged)
        rangeLayout.addRow('Min:', self._minEdit)

        self._maxEdit = QtWidgets.QLineEdit(self)
        self._maxEdit.setValidator(QtGui.QDoubleValidator(1, float('inf'), -1))
        self._maxEdit.editingFinished.connect(self._rangeChanged)
        rangeLayout.addRow('Max:', self._maxEdit)

        reloadIcon = QtWidgets.QApplication.instance().style().standardIcon(
            QtWidgets.QStyle.SP_BrowserReload
        )
        self._autoscaleButton = QtWidgets.QPushButton(reloadIcon, "Reset", self)
        self._autoscaleButton.setToolTip("Scale colormap range with current mode")
        self._autoscaleButton.clicked.connect(self._autoscaleRequested)
        self._autoscaleButton.setAutoDefault(False)
        self._autoscaleButton.setEnabled(False)
        rangeLayout.addRow("", self._autoscaleButton)

        resetModeGroupBox = QtWidgets.QGroupBox("Reset Mode", self)
        frameLayout.addWidget(resetModeGroupBox)
        resetModesLayout = QtWidgets.QGridLayout(resetModeGroupBox)

        self._resetButtonGroup = QtWidgets.QButtonGroup(self)
        for text, (mode, tooltip) in self._RESET_MODES.items():
            radioButton = QtWidgets.QRadioButton(text, self)
            radioButton.setToolTip(tooltip)
            radioButton.setChecked(mode == utils.auto_level.mode)
            self._resetButtonGroup.addButton(radioButton)

        for index, radioButton in enumerate(self._resetButtonGroup.buttons()):
            resetModesLayout.addWidget(radioButton, index // 2, index % 2, QtCore.Qt.AlignLeft)

        self._resetButtonGroup.buttonClicked.connect(self._autoscaleRequested)

        self._filterGapsCheckBox = QtWidgets.QCheckBox(self)
        self._filterGapsCheckBox.setToolTip("Toggle detector gaps value filtering")
        self._filterGapsCheckBox.setChecked(utils.auto_level.filter_dummy)
        self._filterGapsCheckBox.toggled.connect(self._autoscaleRequested)
        nrows = resetModesLayout.rowCount()
        resetModesLayout.addWidget(QtWidgets.QLabel('Filter gaps:'), nrows, 0, QtCore.Qt.AlignRight)
        resetModesLayout.addWidget(self._filterGapsCheckBox, nrows, 1, QtCore.Qt.AlignLeft)

        buttonBox = QtWidgets.QDialogButtonBox(parent=self)
        buttonBox.setStandardButtons(QtWidgets.QDialogButtonBox.Close)
        closeButton = buttonBox.button(QtWidgets.QDialogButtonBox.Close)
        closeButton.clicked.connect(self.close)
        closeButton.setAutoDefault(False)
        frameLayout.addWidget(buttonBox)

    def setData(self, data: Optional[np.ndarray], copy: bool = True):
        """Set data and histogram to use for autoscale"""
        self._data = None if data is None else np.array(data, copy=copy)
        self._autoscaleButton.setEnabled(data is not None)

    def getData(self, copy: bool = True) -> Optional[np.ndarray]:
        """Returns data used for autoscale if set else None"""
        if self._data is None:
            return None
        return np.array(self._data, copy=copy)

    def _gradientComboBoxCurrentIndexChanged(self, index: int):
        if index < 0:
            return
        gradient = self._gradientComboBox.itemData(index, QtCore.Qt.UserRole)
        self.sigCurrentGradientChanged.emit(gradient)

    def _normalizationComboBoxCurrentIndexChanged(self, index: int):
        if index < 0:
            return
        normalization = self._normalizationComboBox.itemData(index, QtCore.Qt.UserRole)
        self.sigCurrentNormalizationChanged.emit(normalization)

    def setCurrentGradient(self, gradient: dict):
        """Set the currently selected gradient

        If the gradient is not available, a 'Custom' item is added for it.
        """
        for name, description in pyqtgraph.graphicsItems.GradientEditorItem.Gradients.items():
            if gradient['mode'] == description['mode'] and gradient['ticks'] == description['ticks']:
                self._gradientComboBox.setCurrentText(name.capitalize())
                return

        icon = self._createQIconFromGradient(gradient)
        # Block signals to avoid emitting with previously selected gradient since index changes
        wasBlocked = self._gradientComboBox.blockSignals(True)
        self._gradientComboBox.insertItem(0, icon, 'Custom', gradient)
        self._gradientComboBox.blockSignals(wasBlocked)
        self._gradientComboBox.setCurrentIndex(0)

    def getCurrentGradient(self) -> dict:
        """Returns the currently selected gradient"""
        return self._gradientComboBox.currentData()

    def setCurrentNormalization(self, normalization: str):
        """Set the currently selected normalization"""
        index = self._normalizationComboBox.findData(normalization)
        if index < 0:
            raise ValueError(f"Unsupported normalization: {normalization}")
        self._normalizationComboBox.setCurrentIndex(index)

    def getCurrentNormalization(self) -> str:
        """Returns the currently selected normalization"""
        return self._normalizationComboBox.currentData()

    def _rangeChanged(self):
        minimum, maximum = self.getRange()
        if maximum < minimum:
            self.setRange(maximum, minimum)
            return
        self.sigRangeChanged.emit(minimum, maximum)

    def setRange(self, minimum: float, maximum: float):
        """Set the data range (min, max) of the colormap"""
        if maximum < minimum:
            minimum, maximum = maximum, minimum
        if np.allclose((minimum, maximum), self.getRange()):
            return
        self._minEdit.setText(self._minEdit.validator().locale().toString(float(minimum)))
        self._maxEdit.setText(self._maxEdit.validator().locale().toString(float(maximum)))
        self._rangeChanged()

    def getRange(self) -> tuple[float, float]:
        """Returns the data range of the colormap (min, max)"""
        minimum, validated = self._minEdit.validator().locale().toDouble(self._minEdit.text())
        if not validated:
            minimum = 1 
        maximum, validated = self._maxEdit.validator().locale().toDouble(self._maxEdit.text())
        if not validated:
            maximum = minimum
        return minimum, maximum

    def _getResetMode(self) -> str:
        button = self._resetButtonGroup.checkedButton()
        if button is not None and button.text() in self._RESET_MODES:
            return self._RESET_MODES[button.text()][0]
        return "default"  # Fallback

    def _autoscaleRequested(self, *args):
        utils.auto_level.mode = self._getResetMode()
        utils.auto_level.filter_dummy = self._filterGapsCheckBox.isChecked()
        colormapRange = utils.auto_level.get_range(self.getData(copy=False))
        if colormapRange is None:
             return
        self.setRange(*colormapRange)

    @staticmethod
    def _createQIconFromGradient(gradient: dict) -> QtGui.QIcon:
        """Generates a QIcon from a pyqtgraph gradient"""
        gradientEditorItem = pyqtgraph.graphicsItems.GradientEditorItem.GradientEditorItem()
        gradientEditorItem.setLength(100)
        gradientEditorItem.restoreState(gradient)
        qgradient = gradientEditorItem.getGradient()

        pixmap = QtGui.QPixmap(100, 100)
        painter = QtGui.QPainter(pixmap)
        brush = QtGui.QBrush(qgradient)
        painter.fillRect(QtCore.QRect(0, 0, 100, 100), brush)
        painter.end()
        return QtGui.QIcon(pixmap)
