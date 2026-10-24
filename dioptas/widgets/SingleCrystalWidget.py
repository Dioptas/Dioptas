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


class PositionTableModel(SpotTableModel):
    headers = (
        "Spot",
        "x (px)",
        "y (px)",
        "ω (°)",
        "ω RMS (°)",
        "Observations",
        "Quality",
    )

    def data(self, index, role=QtCore.Qt.DisplayRole):
        if not index.isValid() or self.table is None or role != QtCore.Qt.DisplayRole:
            return None
        row, column = index.row(), index.column()
        if column == 0:
            return row + 1
        if column == 6:
            return quality_labels(int(self.table.flags[row]))
        value = self.table.values[row, column - 1]
        return "—" if not math.isfinite(value) else f"{value:.6g}"


class SingleCrystalWidget(QtWidgets.QWidget):
    series_progress = QtCore.Signal(int, int, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        layout.addWidget(splitter)

        viewer = QtWidgets.QWidget()
        viewer_layout = QtWidgets.QVBoxLayout(viewer)
        viewer_layout.setContentsMargins(0, 0, 0, 0)
        graphics = pg.GraphicsLayoutWidget()
        viewer_layout.addWidget(graphics, 1)
        self.img_widget = MaskImgWidget(graphics)
        self.spot_overlay = pg.ScatterPlotItem(
            symbol="o", size=10, pen=pg.mkPen("k", width=2), brush="y", pxMode=True
        )
        self.img_widget.img_view_box.addItem(self.spot_overlay)
        self.predicted_overlay = pg.ScatterPlotItem(
            symbol="+", size=12, pen=pg.mkPen("#48d8eb", width=1.5), brush=None
        )
        self.img_widget.img_view_box.addItem(self.predicted_overlay)
        self.frame_label = QtWidgets.QLabel("No rotation series loaded.")
        frame_header = QtWidgets.QHBoxLayout()
        frame_header.addWidget(self.frame_label, 1)
        self.follow_search = QtWidgets.QCheckBox("Follow search")
        self.follow_search.setChecked(True)
        self.follow_search.setEnabled(False)
        self.follow_search.setToolTip(
            "Display the latest completed frame and its detections while searching. "
            "Uncheck or browse a frame to pause the live preview."
        )
        frame_header.addWidget(self.follow_search)
        viewer_layout.addLayout(frame_header)
        self.frame_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.frame_slider.setRange(0, 0)
        self.frame_slider.setEnabled(False)
        frame_controls = QtWidgets.QHBoxLayout()
        frame_controls.addWidget(self.frame_slider, 1)
        self.previous_frame_button = QtWidgets.QToolButton()
        self.previous_frame_button.setText("◀")
        self.previous_frame_button.setToolTip("Previous frame")
        self.next_frame_button = QtWidgets.QToolButton()
        self.next_frame_button.setText("▶")
        self.next_frame_button.setToolTip("Next frame")
        for button, step in (
            (self.previous_frame_button, -1),
            (self.next_frame_button, 1),
        ):
            button.setAutoRepeat(True)
            button.clicked.connect(
                lambda checked=False, delta=step: self.frame_slider.setValue(
                    self.frame_slider.value() + delta
                )
            )
            frame_controls.addWidget(button)
        self.frame_slider.valueChanged.connect(self.update_frame_buttons)
        self.frame_slider.rangeChanged.connect(self.update_frame_buttons)
        self.update_frame_buttons()
        viewer_layout.addLayout(frame_controls)
        splitter.addWidget(viewer)

        controls = QtWidgets.QWidget()
        controls.setMinimumWidth(500)
        panel = QtWidgets.QVBoxLayout(controls)
        title = QtWidgets.QLabel("Single crystal · experimental")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        panel.addWidget(title)
        description = QtWidgets.QLabel(
            "Open a rotation series and find spot positions in x, y and omega. "
            "These position candidates precede unit-cell finding and intensity integration."
        )
        description.setWordWrap(True)
        panel.addWidget(description)
        self.source_label = QtWidgets.QLabel("Load a detector image to start.")
        self.source_label.setWordWrap(True)
        panel.addWidget(self.source_label)
        self.sections = QtWidgets.QTabWidget()
        panel.addWidget(self.sections, 1)
        section_layouts = []
        for name in ("Series", "Detection", "Cell", "Predictions", "Positions"):
            page = QtWidgets.QWidget()
            section_layouts.append(QtWidgets.QVBoxLayout(page))
            self.sections.addTab(page, name)
        series_panel, detection_panel, cell_panel, prediction_panel, positions_panel = (
            section_layouts
        )
        self.load_button = QtWidgets.QPushButton("Open image…")
        self.series_button = QtWidgets.QPushButton("Open series from one frame…")
        series_panel.addWidget(self.series_button)
        self.omega_background_button = QtWidgets.QPushButton("Omega background…")
        series_panel.addWidget(self.omega_background_button)
        series_panel.addWidget(self.load_button)
        form = QtWidgets.QFormLayout()
        detection_panel.addLayout(form)

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
        self.link_radius = number("Link distance per frame (px)", 5, 0.1, 100)
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
        detection_panel.addWidget(self.detect_button)
        self.cell_button = QtWidgets.QPushButton("Geometry and find unit cell…")
        self.cell_button.setEnabled(False)
        cell_panel.addWidget(self.cell_button)
        self.cell_summary = QtWidgets.QPlainTextEdit()
        self.cell_summary.setReadOnly(True)
        self.cell_summary.setMaximumHeight(210)
        self.cell_summary.hide()
        cell_panel.addWidget(self.cell_summary)
        self.cell_export_button = QtWidgets.QPushButton("Export cell candidates…")
        self.cell_export_button.setEnabled(False)
        cell_panel.addWidget(self.cell_export_button)
        self.refine_button = QtWidgets.QPushButton("Unconstrained cell/orientation fit")
        self.refine_button.setEnabled(False)
        self.orthorhombic_button = QtWidgets.QPushButton(
            "Find orthorhombic setting and fit"
        )
        self.orthorhombic_button.setEnabled(False)
        cell_panel.addWidget(self.orthorhombic_button)
        cell_panel.addWidget(self.refine_button)
        self.prediction_enabled = QtWidgets.QCheckBox(
            "Show predicted Bragg centres (+)"
        )
        self.prediction_enabled.setChecked(True)
        prediction_panel.addWidget(self.prediction_enabled)
        self.prediction_model = QtWidgets.QComboBox()
        self.prediction_model.addItems(["Initial indexed model", "Refined model"])
        self.prediction_model.setEnabled(False)
        prediction_panel.addWidget(self.prediction_model)
        self.prediction_note = QtWidgets.QLabel(
            "Predictions require an indexed cell. No intensity or extinction model."
        )
        self.prediction_note.setWordWrap(True)
        prediction_panel.addWidget(self.prediction_note)
        self.refinement_summary = QtWidgets.QPlainTextEdit()
        self.refinement_summary.setReadOnly(True)
        self.refinement_summary.setMaximumHeight(210)
        self.refinement_summary.hide()
        prediction_panel.addWidget(self.refinement_summary)
        self.residual_button = QtWidgets.QPushButton("Residual plots…")
        self.residual_button.setEnabled(False)
        prediction_panel.addWidget(self.residual_button)
        self.refinement_export_button = QtWidgets.QPushButton(
            "Export predictions and refinement…"
        )
        self.refinement_export_button.setEnabled(False)
        prediction_panel.addWidget(self.refinement_export_button)
        self.status_label = QtWidgets.QLabel("Experimental spot engine ready.")
        self.status_label.setWordWrap(True)
        panel.addWidget(self.status_label)
        self.table_view = QtWidgets.QTableView()
        self.table_model = SpotTableModel(self.table_view)
        self.position_table_model = PositionTableModel(self.table_view)
        self.table_view.setModel(self.table_model)
        self.table_view.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.table_view.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.table_view.horizontalHeader().setStretchLastSection(True)
        self.table_view.horizontalHeader().setSectionResizeMode(
            QtWidgets.QHeaderView.ResizeToContents
        )
        positions_panel.addWidget(self.table_view, 1)
        self.export_button = QtWidgets.QPushButton("Export spots…")
        self.export_button.setEnabled(False)
        positions_panel.addWidget(self.export_button)
        self.measurement_note = QtWidgets.QLabel(
            "Raw counts with local background subtraction. Error estimates assume independent "
            "pixels and the noise settings above. Flagged spots are retained; overlaps are not separated. "
            "These measurements are not corrected crystallographic intensities."
        )
        self.measurement_note.setWordWrap(True)
        detection_panel.addWidget(self.measurement_note)
        hint = QtWidgets.QLabel(
            "Select any numbered image. Matching frames in that folder are found automatically; "
            "the angle preview shows the detected range and any missing frame numbers."
        )
        hint.setWordWrap(True)
        series_panel.addWidget(hint)
        for section in (series_panel, detection_panel, cell_panel, prediction_panel):
            section.addStretch(1)
        splitter.addWidget(controls)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)

    def show_spots(self, x, y, flags):
        self.spot_overlay.setData(
            x=x,
            y=y,
            brush=["r" if flag else "y" for flag in flags],
            pen=pg.mkPen("k", width=2),
            size=10,
        )

    def update_frame_buttons(self, *_):
        enabled = self.frame_slider.isEnabled()
        self.previous_frame_button.setEnabled(
            enabled and self.frame_slider.value() > self.frame_slider.minimum()
        )
        self.next_frame_button.setEnabled(
            enabled and self.frame_slider.value() < self.frame_slider.maximum()
        )

    def parameter_widgets(self):
        return (
            self.threshold,
            self.outer_radius,
            self.min_pixels,
            self.padding,
            self.background_margin,
            self.gain,
            self.read_noise,
            self.link_radius,
            self.saturation,
        )
