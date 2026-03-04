# SPDX-License-Identifier: MIT
from __future__ import annotations

import math
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
        "Percentile": (
            "percentile",
            "Clip extreme values at the given percentile",
        ),
        "Min/max": ("minmax", "Use data min/max to scale colormap range"),
        "Mean±3 Std": (
            "mean3std",
            "Use data mean ± 3 × standard deviation to scale colormap range",
        ),
    }

    # Logarithmic slider parameters
    _PERCENTILE_MIN = 0.01
    _PERCENTILE_MAX = 25.0
    _PERCENTILE_SLIDER_STEPS = 200

    def __init__(self, parent=None):
        super().__init__(parent)
        self._data = None
        self.setWindowTitle("Colormap configuration")
        self.setWindowFlags(QtCore.Qt.Popup)
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose)
        self.setFrameStyle(QtWidgets.QFrame.Panel | QtWidgets.QFrame.Raised)
        self.setWindowOpacity(0.95)
        self.setLineWidth(2)

        frameLayout = QtWidgets.QVBoxLayout(self)
        frameLayout.setContentsMargins(3, 3, 3, 3)
        frameLayout.setSpacing(3)

        colormapGroupBox = QtWidgets.QGroupBox("Colormap", self)
        frameLayout.addWidget(colormapGroupBox)
        colormapLayout = QtWidgets.QFormLayout(colormapGroupBox)
        colormapLayout.setContentsMargins(0, 6, 0, 0)
        colormapLayout.setLabelAlignment(QtCore.Qt.AlignRight)

        self._gradientComboBox = QtWidgets.QComboBox(self)
        for (
            name,
            gradient,
        ) in pyqtgraph.graphicsItems.GradientEditorItem.Gradients.items():
            icon = self._createQIconFromGradient(gradient)
            self._gradientComboBox.addItem(icon, name.capitalize(), gradient)
        self._gradientComboBox.currentIndexChanged.connect(
            self._gradientComboBoxCurrentIndexChanged
        )
        colormapLayout.addRow("Colormap:", self._gradientComboBox)

        self._normalizationComboBox = QtWidgets.QComboBox(self)
        for normalization in NormalizedImageItem.supportedNormalizations():
            description = NormalizedImageItem.getNormalizationDescription(
                normalization
            ).capitalize()
            self._normalizationComboBox.addItem(description, normalization)

        self._normalizationComboBox.setCurrentIndex(0)
        self._normalizationComboBox.currentIndexChanged.connect(
            self._normalizationComboBoxCurrentIndexChanged
        )
        colormapLayout.addRow("Normalization:", self._normalizationComboBox)

        rangeGroupBox = QtWidgets.QGroupBox("Range", self)
        frameLayout.addWidget(rangeGroupBox)
        rangeLayout = QtWidgets.QFormLayout(rangeGroupBox)
        rangeLayout.setContentsMargins(0, 6, 0, 0)
        rangeLayout.setLabelAlignment(QtCore.Qt.AlignRight)

        self._minEdit = QtWidgets.QLineEdit(self)
        self._minEdit.setValidator(QtGui.QDoubleValidator(1, float("inf"), -1))
        self._minEdit.setText("1")
        self._minEdit.editingFinished.connect(self._rangeChanged)
        rangeLayout.addRow("Min:", self._minEdit)

        self._maxEdit = QtWidgets.QLineEdit(self)
        self._maxEdit.setValidator(QtGui.QDoubleValidator(1, float("inf"), -1))
        self._maxEdit.setText("1")
        self._maxEdit.editingFinished.connect(self._rangeChanged)
        rangeLayout.addRow("Max:", self._maxEdit)

        reloadIcon = (
            QtWidgets.QApplication.instance()
            .style()
            .standardIcon(QtWidgets.QStyle.SP_BrowserReload)
        )
        self._autoscaleButton = QtWidgets.QPushButton(reloadIcon, "Reset", self)
        self._autoscaleButton.setToolTip("Scale colormap range with current mode")
        self._autoscaleButton.clicked.connect(self._autoscaleRequested)
        self._autoscaleButton.setAutoDefault(False)
        self._autoscaleButton.setEnabled(False)
        rangeLayout.addRow("", self._autoscaleButton)

        resetModeGroupBox = QtWidgets.QGroupBox("Reset Mode", self)
        frameLayout.addWidget(resetModeGroupBox)
        resetModesLayout = QtWidgets.QVBoxLayout(resetModeGroupBox)
        resetModesLayout.setContentsMargins(0, 6, 0, 0)
        resetModesLayout.setSpacing(0)

        current_mode, current_percentile = self._parse_auto_level_mode(
            utils.auto_level.mode
        )

        self._resetButtonGroup = QtWidgets.QButtonGroup(self)
        for text, (mode, tooltip) in self._RESET_MODES.items():
            radioButton = QtWidgets.QRadioButton(text, self)
            radioButton.setToolTip(tooltip)
            radioButton.setChecked(mode == current_mode)
            self._resetButtonGroup.addButton(radioButton)
            resetModesLayout.addWidget(radioButton)

            if mode == "percentile":
                sliderLayout = QtWidgets.QHBoxLayout()
                sliderLayout.setContentsMargins(20, 0, 0, 0)

                self._percentileSlider = QtWidgets.QSlider(
                    QtCore.Qt.Horizontal, self
                )
                self._percentileSlider.setRange(0, self._PERCENTILE_SLIDER_STEPS)
                self._percentileSlider.setValue(
                    self._percentile_to_slider(current_percentile)
                )
                self._percentileSlider.setToolTip("Adjust clipping percentile")
                self._percentileSlider.valueChanged.connect(
                    self._percentileSliderChanged
                )

                self._percentileLabel = QtWidgets.QLabel(self)
                self._percentileLabel.setFixedWidth(40)
                self._updatePercentileLabel()

                sliderLayout.addWidget(self._percentileSlider)
                sliderLayout.addWidget(self._percentileLabel)
                resetModesLayout.addLayout(sliderLayout)

        self._resetButtonGroup.buttonClicked.connect(self._resetModeChanged)

        filterLayout = QtWidgets.QHBoxLayout()
        filterLayout.setContentsMargins(0, 4, 0, 0)
        self._filterGapsCheckBox = QtWidgets.QCheckBox("Filter gaps", self)
        self._filterGapsCheckBox.setToolTip("Toggle detector gaps value filtering")
        self._filterGapsCheckBox.setChecked(utils.auto_level.filter_dummy)
        self._filterGapsCheckBox.toggled.connect(self._autoscaleRequested)
        filterLayout.addWidget(self._filterGapsCheckBox)
        resetModesLayout.addLayout(filterLayout)

        self._updateSliderVisibility()

        buttonBox = QtWidgets.QDialogButtonBox(parent=self)
        buttonBox.setStandardButtons(QtWidgets.QDialogButtonBox.Close)
        closeButton = buttonBox.button(QtWidgets.QDialogButtonBox.Close)
        closeButton.clicked.connect(self.close)
        closeButton.setAutoDefault(False)
        frameLayout.addWidget(buttonBox)

    def setData(self, data: Optional[np.ndarray] = None, copy: bool = True):
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
        for (
            name,
            description,
        ) in pyqtgraph.graphicsItems.GradientEditorItem.Gradients.items():
            if (
                gradient["mode"] == description["mode"]
                and gradient["ticks"] == description["ticks"]
            ):
                self._gradientComboBox.setCurrentText(name.capitalize())
                return

        icon = self._createQIconFromGradient(gradient)
        # Block signals to avoid emitting with previously selected gradient since index changes
        wasBlocked = self._gradientComboBox.blockSignals(True)
        self._gradientComboBox.insertItem(0, icon, "Custom", gradient)
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
        self._minEdit.setText(
            self._minEdit.validator().locale().toString(float(minimum))
        )
        self._maxEdit.setText(
            self._maxEdit.validator().locale().toString(float(maximum))
        )
        self._rangeChanged()

    def getRange(self) -> tuple[float, float]:
        """Returns the data range of the colormap (min, max)"""
        minimum, validated = (
            self._minEdit.validator().locale().toDouble(self._minEdit.text())
        )
        if not validated:
            minimum = 1
        maximum, validated = (
            self._maxEdit.validator().locale().toDouble(self._maxEdit.text())
        )
        if not validated:
            maximum = minimum
        return minimum, maximum

    def _getResetMode(self) -> str:
        button = self._resetButtonGroup.checkedButton()
        if button is not None and button.text() in self._RESET_MODES:
            mode = self._RESET_MODES[button.text()][0]
            if mode == "percentile":
                percentile = self._slider_to_percentile(
                    self._percentileSlider.value()
                )
                return f"{percentile}percentile"
            return mode
        return "percentile"  # Fallback

    @staticmethod
    def _parse_auto_level_mode(mode: str) -> tuple[str, float]:
        """Parse an AutoLevel mode string into (reset_mode, percentile).

        Returns e.g. ("percentile", 1.5) for "1.5percentile",
        ("minmax", 0.4) for "minmax", ("percentile", 0.4) for "default".
        """
        import re

        match = re.match(r"(\d+(?:\.\d*)?)percentile", mode)
        if match is not None:
            return "percentile", float(match.group(1))
        if mode in ("minmax", "mean3std"):
            return mode, 0.4
        # "default" or unknown → percentile with default value
        return "percentile", 0.4

    def _percentile_to_slider(self, percentile: float) -> int:
        """Convert a percentile value to slider position (logarithmic)."""
        percentile = max(self._PERCENTILE_MIN, min(self._PERCENTILE_MAX, percentile))
        pos = self._PERCENTILE_SLIDER_STEPS * math.log(
            percentile / self._PERCENTILE_MIN
        ) / math.log(self._PERCENTILE_MAX / self._PERCENTILE_MIN)
        return round(pos)

    def _slider_to_percentile(self, pos: int) -> float:
        """Convert a slider position to percentile value (logarithmic)."""
        value = self._PERCENTILE_MIN * (
            self._PERCENTILE_MAX / self._PERCENTILE_MIN
        ) ** (pos / self._PERCENTILE_SLIDER_STEPS)
        return round(value, 2)

    def _resetModeChanged(self, button):
        """Handle reset mode radio button change."""
        self._updateSliderVisibility()
        self._autoscaleRequested()

    def _updateSliderVisibility(self):
        """Show the percentile slider only when Percentile mode is selected."""
        button = self._resetButtonGroup.checkedButton()
        visible = button is not None and button.text() == "Percentile"
        self._percentileSlider.setVisible(visible)
        self._percentileLabel.setVisible(visible)

    def _percentileSliderChanged(self, value: int):
        """Handle slider value change: update label and re-trigger autoscale."""
        self._updatePercentileLabel()
        button = self._resetButtonGroup.checkedButton()
        if button is not None and button.text() == "Percentile":
            self._autoscaleRequested()

    def _updatePercentileLabel(self):
        """Update the label next to the slider with the current percentile."""
        percentile = self._slider_to_percentile(self._percentileSlider.value())
        self._percentileLabel.setText(f"{percentile}%")

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
        gradientEditorItem = (
            pyqtgraph.graphicsItems.GradientEditorItem.GradientEditorItem()
        )
        gradientEditorItem.setLength(100)
        gradientEditorItem.restoreState(gradient)
        qgradient = gradientEditorItem.getGradient()

        pixmap = QtGui.QPixmap(100, 100)
        painter = QtGui.QPainter(pixmap)
        brush = QtGui.QBrush(qgradient)
        painter.fillRect(QtCore.QRect(0, 0, 100, 100), brush)
        painter.end()
        return QtGui.QIcon(pixmap)
