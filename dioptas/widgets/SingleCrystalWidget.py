# SPDX-License-Identifier: MIT
"""Presentation for experimental raw detector spot measurements."""

import math

import pyqtgraph as pg
from qtpy import QtCore, QtWidgets

from .plot_widgets import MaskImgWidget
from ..model.single_crystal import quality_labels


class SpotTableModel(QtCore.QAbstractTableModel):
    headers = (
        "Spot",
        "x (px)",
        "y (px)",
        "Counts",
        "σ(counts)",
        "I/σ",
        "Background",
        "Quality",
    )

    def __init__(self, parent=None):
        super().__init__(parent)
        self.table = None

    def set_result(self, table):
        self.beginResetModel()
        self.table = table
        self.endResetModel()

    def rowCount(self, parent=QtCore.QModelIndex()):
        return 0 if parent.isValid() or self.table is None else len(self.table)

    def columnCount(self, parent=QtCore.QModelIndex()):
        return 0 if parent.isValid() else len(self.headers)

    def headerData(self, section, orientation, role=QtCore.Qt.DisplayRole):
        if role == QtCore.Qt.DisplayRole and orientation == QtCore.Qt.Horizontal:
            return self.headers[section]
        return None

    def data(self, index, role=QtCore.Qt.DisplayRole):
        if not index.isValid() or self.table is None or role != QtCore.Qt.DisplayRole:
            return None
        row, column = index.row(), index.column()
        if column == 0:
            return row + 1
        if column == 7:
            return quality_labels(int(self.table.flags[row]))
        values = self.table.values[row]
        value = (
            values[2] / values[3]
            if column == 5 and values[3] > 0
            else (
                math.nan
                if column == 5
                else values[{1: 0, 2: 1, 3: 2, 4: 3, 6: 4}[column]]
            )
        )
        return "—" if not math.isfinite(value) else f"{value:.5g}"


class SingleCrystalWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        layout.addWidget(splitter)

        graphics = pg.GraphicsLayoutWidget()
        self.img_widget = MaskImgWidget(graphics)
        self.spot_overlay = pg.ScatterPlotItem(
            symbol="o", size=13, pen=pg.mkPen("y", width=2), brush=None
        )
        self.img_widget.img_view_box.addItem(self.spot_overlay)
        splitter.addWidget(graphics)

        controls = QtWidgets.QWidget()
        controls.setMinimumWidth(500)
        panel = QtWidgets.QVBoxLayout(controls)
        title = QtWidgets.QLabel("Single crystal · experimental")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        panel.addWidget(title)
        description = QtWidgets.QLabel(
            "Find spots in an unknown sample and measure their detector counts. "
            "No material or structure is required. Indexing is a later step."
        )
        description.setWordWrap(True)
        panel.addWidget(description)
        self.source_label = QtWidgets.QLabel("Load a detector image to start.")
        self.source_label.setWordWrap(True)
        panel.addWidget(self.source_label)
        self.load_button = QtWidgets.QPushButton("Open image…")
        panel.addWidget(self.load_button)
        form = QtWidgets.QFormLayout()
        panel.addLayout(form)

        def number(label, default, minimum, maximum, decimals=2):
            widget = QtWidgets.QDoubleSpinBox()
            widget.setRange(minimum, maximum)
            widget.setDecimals(decimals)
            widget.setValue(default)
            form.addRow(label, widget)
            return widget

        self.threshold = number("Detection threshold (σ)", 5, 0.1, 100)
        self.outer_radius = number("Background radius (px)", 8, 3, 128, 0)
        self.min_pixels = number("Minimum connected pixels", 3, 1, 4096, 0)
        self.padding = number("Integration padding (px)", 2, 0, 128, 0)
        self.background_margin = number("Background ring width (px)", 4, 1, 128, 0)
        self.gain = number("Photons/electrons per count", 1, 0.0001, 1e8, 4)
        self.read_noise = number("Read noise (counts)", 0, 0, 1e8)
        self.saturation_enabled = QtWidgets.QCheckBox("Flag saturated pixels")
        form.addRow(self.saturation_enabled)
        self.saturation = number("Saturation level (counts)", 65535, 1, 1e12, 0)
        self.saturation.setEnabled(False)
        self.saturation_enabled.toggled.connect(self.saturation.setEnabled)
        self.zero_padding = QtWidgets.QCheckBox("Exclude zero-valued detector padding")
        self.zero_padding.setToolTip(
            "Also excludes valid zero-count pixels. Enable only when zero marks padding in these images."
        )
        form.addRow(self.zero_padding)

        self.detect_button = QtWidgets.QPushButton("Find spots and extract counts")
        panel.addWidget(self.detect_button)
        self.status_label = QtWidgets.QLabel("Experimental spot engine ready.")
        self.status_label.setWordWrap(True)
        panel.addWidget(self.status_label)
        self.table_view = QtWidgets.QTableView()
        self.table_model = SpotTableModel(self.table_view)
        self.table_view.setModel(self.table_model)
        self.table_view.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.table_view.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.table_view.horizontalHeader().setStretchLastSection(True)
        self.table_view.horizontalHeader().setSectionResizeMode(
            QtWidgets.QHeaderView.ResizeToContents
        )
        panel.addWidget(self.table_view, 1)
        self.export_button = QtWidgets.QPushButton("Export spots…")
        self.export_button.setEnabled(False)
        panel.addWidget(self.export_button)
        note = QtWidgets.QLabel(
            "Raw counts with local background subtraction. Error estimates assume independent "
            "pixels and the noise settings above. Flagged spots are retained; overlaps are not separated. "
            "These measurements are not corrected crystallographic intensities."
        )
        note.setWordWrap(True)
        panel.addWidget(note)
        splitter.addWidget(controls)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)

    def parameter_widgets(self):
        return (
            self.threshold,
            self.outer_radius,
            self.min_pixels,
            self.padding,
            self.background_margin,
            self.gain,
            self.read_noise,
            self.saturation,
        )
