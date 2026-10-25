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


class CellCandidateModel(QtCore.QAbstractTableModel):
    """All returned candidates, with stable keys independent of table sorting."""

    headers = (
        "ID",
        "Axis",
        "Check",
        "Cell edges (Å)",
        "a (Å)",
        "b (Å)",
        "c (Å)",
        "α (°)",
        "β (°)",
        "γ (°)",
        "V (Å³)",
        "Train %",
        "Held out %",
        "RMS (Å⁻¹)",
    )

    def __init__(self, parent=None):
        super().__init__(parent)
        self.rows = []

    def set_result(self, result):
        import numpy as np

        self.beginResetModel()
        self.rows = []
        if result is not None:
            for sign, _, search in result.reports:
                for i, c in enumerate(search.candidates):
                    rms = (
                        float(np.sqrt(np.mean(c.residual[c.indexed] ** 2)))
                        if np.any(c.indexed)
                        else None
                    )
                    values = (
                        i + 1,
                        sign,
                        "Pass" if c.accepted else "Rejected",
                        ", ".join(f"{v:.3f}" for v in c.cell[:3]),
                        *map(float, c.cell),
                        c.volume,
                        100 * c.training_fraction,
                        100 * c.validation_fraction,
                        rms,
                    )
                    self.rows.append(((sign, i), values, search, c))
        self.endResetModel()

    def rowCount(self, parent=QtCore.QModelIndex()):
        return 0 if parent.isValid() else len(self.rows)

    def columnCount(self, parent=QtCore.QModelIndex()):
        return 0 if parent.isValid() else len(self.headers)

    def headerData(self, section, orientation, role=QtCore.Qt.DisplayRole):
        if role == QtCore.Qt.DisplayRole and orientation == QtCore.Qt.Horizontal:
            return self.headers[section]
        return None

    def data(self, index, role=QtCore.Qt.DisplayRole):
        if not index.isValid():
            return None
        key, values, search, candidate = self.rows[index.row()]
        if role == QtCore.Qt.UserRole:
            return key
        if role == QtCore.Qt.ToolTipRole:
            import numpy as np

            training = np.count_nonzero(candidate.indexed & search.training)
            heldout = np.count_nonzero(candidate.indexed & ~search.training)
            return (
                f"{'FFT grain search' if search.method == 'fft_grains' else 'Compact FFT'} · "
                f"training {training}/{np.count_nonzero(search.training)} · "
                f"held out {heldout}/{candidate.validation_count} · "
                f"control ≤{candidate.null_fraction:.1%}. "
                "Different orientations can share the same cell. Symmetry and primitivity are unproven."
            )
        value = values[index.column()]
        if role == QtCore.Qt.EditRole:
            return value
        if role == QtCore.Qt.DisplayRole:
            return (
                "—"
                if value is None
                else (
                    f"{value:.1f}"
                    if isinstance(value, float) and index.column() in (11, 12)
                    else f"{value:.4f}"
                    if isinstance(value, float)
                    else str(value)
                )
            )
        return None


class RankedCellModel(QtCore.QAbstractTableModel):
    """PhaseSmith fit-pool IDs remain stable when users sort by any diagnostic."""

    headers = (
        "",
        "Cell",
        "Cell edges (Å)",
        "α, β, γ (°)",
        "Δ score",
        "Train RMS (px)",
        "Held-out RMS (px)",
        "Train RMS ω (°)",
        "Held-out RMS ω (°)",
        "Score",
        "Symmetry order",
        "a (Å)",
        "b (Å)",
        "c (Å)",
        "α (°)",
        "β (°)",
        "γ (°)",
        "V (Å³)",
        "Fit status",
        "Primitive ID",
    )

    def __init__(self, parent=None):
        super().__init__(parent)
        self.rows = []

    def set_result(self, result):
        import numpy as np

        self.beginResetModel()
        self.rows = []
        if result is not None:
            for rank in result.comparison.ranking:
                fit = result.comparison.settings[rank.setting_index]
                cell = fit.cell
                values = (
                    rank.rank,
                    fit.setting.symbol,
                    ", ".join(f"{v:.3f}" for v in cell[:3]),
                    ", ".join(f"{v:.3f}".rstrip("0").rstrip(".") for v in cell[3:]),
                    rank.score_delta,
                    fit.training_metrics.get("rms_xy"),
                    fit.validation_metrics.get("rms_xy"),
                    fit.training_metrics.get("rms_omega"),
                    fit.validation_metrics.get("rms_omega"),
                    fit.training_score,
                    rank.symmetry_order,
                    *map(float, cell),
                    abs(float(np.linalg.det(fit.reciprocal_basis))) ** -1,
                    fit.status,
                    fit.primitive_id,
                )
                self.rows.append((rank.setting_index, values, rank, fit))
        self.endResetModel()

    def rowCount(self, parent=QtCore.QModelIndex()):
        return 0 if parent.isValid() else len(self.rows)

    def columnCount(self, parent=QtCore.QModelIndex()):
        return 0 if parent.isValid() else len(self.headers)

    def headerData(self, section, orientation, role=QtCore.Qt.DisplayRole):
        if role == QtCore.Qt.DisplayRole and orientation == QtCore.Qt.Horizontal:
            return self.headers[section]
        return None

    def data(self, index, role=QtCore.Qt.DisplayRole):
        if not index.isValid():
            return None
        key, values, rank, fit = self.rows[index.row()]
        if role == QtCore.Qt.UserRole:
            return key
        if role == QtCore.Qt.ToolTipRole:
            return (
                f"{rank.reason}. Primitive priority {rank.primitive_priority}; "
                f"training {fit.training_metrics['count']}, held out {fit.validation_metrics['count']}. "
                "Lattice metric only; symmetry order includes inversion, not space-group evidence. "
                "Click to display this fitted cell without another refinement."
            )
        value = values[index.column()]
        if role == QtCore.Qt.EditRole:
            return value
        if role == QtCore.Qt.DisplayRole:
            return (
                "—"
                if value is None
                else f"{value:.4f}"
                if isinstance(value, float)
                else str(value)
            )
        return None


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
        self.spot_overlay.setZValue(2)
        self.img_widget.img_view_box.addItem(self.spot_overlay)
        self.predicted_overlay = pg.ScatterPlotItem(
            symbol="+", size=12, pen=pg.mkPen("#48d8eb", width=1.5), brush=None
        )
        self.img_widget.img_view_box.addItem(self.predicted_overlay)
        self.predicted_overlay.hide()
        # A hollow ring leaves the measured centre and its quality colour visible.
        self.selected_spot_outline = pg.ScatterPlotItem(
            symbol="o", size=28, pen=pg.mkPen("k", width=7), brush=None, pxMode=True
        )
        self.selected_spot_overlay = pg.ScatterPlotItem(
            symbol="o",
            size=28,
            pen=pg.mkPen("#ff55dd", width=3),
            brush=None,
            pxMode=True,
        )
        for z, item in enumerate(
            (self.selected_spot_outline, self.selected_spot_overlay), start=10
        ):
            item.setZValue(z)
            item.setAcceptedMouseButtons(QtCore.Qt.NoButton)
            self.img_widget.img_view_box.addItem(item)
            item.hide()
        self.mouse_pixel_label = QtWidgets.QLabel("x: —   y: —   I: —")
        self.mouse_geometry_label = QtWidgets.QLabel("2θ: —   d: —   Q: —   χ: —")
        self.mouse_pixel_label.setToolTip(
            "Displayed pixel coordinates and raw detector counts."
        )
        self.mouse_geometry_label.setToolTip(
            "Calibrated scattering angle, d-spacing, Q = 2π/d and azimuth. "
            "Uses the cell-search detector geometry when available."
        )
        mouse_readout = QtWidgets.QHBoxLayout()
        mouse_readout.addWidget(self.mouse_pixel_label)
        mouse_readout.addWidget(self.mouse_geometry_label)
        mouse_readout.addStretch(1)
        viewer_layout.addLayout(mouse_readout)
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
        for name in ("Series", "Detection", "Cell", "Positions"):
            page = QtWidgets.QWidget()
            section_layouts.append(QtWidgets.QVBoxLayout(page))
            self.sections.addTab(page, name)
        series_panel, detection_panel, cell_panel, positions_panel = section_layouts
        self.cell_section = self.sections.widget(2)
        self.positions_section = self.sections.widget(3)
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
        self.cell_button = QtWidgets.QPushButton("Find lattices and rank cells…")
        self.cell_button.setEnabled(False)
        cell_panel.addWidget(self.cell_button)
        self.reciprocal_button = QtWidgets.QPushButton("Reciprocal space…")
        self.reciprocal_button.setEnabled(False)
        self.reciprocal_button.setToolTip(
            "Explore a rotatable 3D cloud of measured reciprocal positions for the selected cell."
        )
        cell_panel.addWidget(self.reciprocal_button)
        self.cell_tables = QtWidgets.QSplitter(QtCore.Qt.Vertical)
        self.cell_tables.setChildrenCollapsible(False)
        cell_panel.addWidget(self.cell_tables, 1)
        self.lattice_group = QtWidgets.QGroupBox("Lattice candidates")
        self.ranked_group = QtWidgets.QGroupBox("Ranked cell settings")
        lattice_panel, ranked_panel = (
            QtWidgets.QVBoxLayout(self.lattice_group),
            QtWidgets.QVBoxLayout(self.ranked_group),
        )
        self.cell_tables.addWidget(self.lattice_group)
        self.cell_tables.addWidget(self.ranked_group)
        self.cell_tables.setStretchFactor(0, 1)
        self.cell_tables.setStretchFactor(1, 1)
        self.cell_tables.setSizes([330, 450])
        self.rank_table_model = RankedCellModel(self)
        self.rank_table_proxy = QtCore.QSortFilterProxyModel(self)
        self.rank_table_proxy.setSourceModel(self.rank_table_model)
        self.rank_table_proxy.setSortRole(QtCore.Qt.EditRole)
        self.rank_table = QtWidgets.QTableView()
        self.rank_table.setModel(self.rank_table_proxy)
        self.rank_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.rank_table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.rank_table.setSortingEnabled(True)
        self.rank_table.sortByColumn(0, QtCore.Qt.AscendingOrder)
        self.rank_table.horizontalHeader().setSectionResizeMode(
            QtWidgets.QHeaderView.ResizeToContents
        )
        self.rank_table.verticalHeader().hide()
        self.rank_table.horizontalHeader().setMinimumSectionSize(30)
        for column, width in ((0, 34), (1, 40)):
            self.rank_table.horizontalHeader().setSectionResizeMode(
                column, QtWidgets.QHeaderView.Fixed
            )
            self.rank_table.setColumnWidth(column, width)
        for column in range(5, len(self.rank_table_model.headers)):
            self.rank_table.setColumnHidden(column, True)
        ranked_panel.addWidget(self.rank_table, 1)
        self.rank_table.setMinimumHeight(90)
        self.rank_table_button = QtWidgets.QPushButton("Full ranked table…")
        self.rank_table_button.clicked.connect(self.open_rank_table)
        self.rank_table_button.setEnabled(False)
        ranked_actions = QtWidgets.QHBoxLayout()
        ranked_actions.addWidget(self.rank_table_button)
        self.rank_summary = QtWidgets.QLabel(
            "Select a passing lattice to obtain ranked cells."
        )
        self.rank_summary.setWordWrap(True)
        ranked_panel.addWidget(self.rank_summary)
        self.rank_export_button = QtWidgets.QPushButton("Export ranked cells…")
        self.rank_export_button.setEnabled(False)
        ranked_actions.addWidget(self.rank_export_button)
        ranked_panel.addLayout(ranked_actions)
        self._rank_dialog = None
        self.cell_table_model = CellCandidateModel(self)
        self.cell_table_proxy = QtCore.QSortFilterProxyModel(self)
        self.cell_table_proxy.setSourceModel(self.cell_table_model)
        self.cell_table_proxy.setSortRole(QtCore.Qt.EditRole)
        self.cell_table = QtWidgets.QTableView()
        self.cell_table.setModel(self.cell_table_proxy)
        self.cell_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.cell_table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.cell_table.setSortingEnabled(True)
        self.cell_table.horizontalHeader().setMinimumSectionSize(30)
        self.cell_table.horizontalHeader().setSectionResizeMode(
            QtWidgets.QHeaderView.ResizeToContents
        )
        for column, width in ((0, 42), (1, 48)):
            self.cell_table.horizontalHeader().setSectionResizeMode(
                column, QtWidgets.QHeaderView.Fixed
            )
            self.cell_table.setColumnWidth(column, width)
        for table in (self.cell_table, self.rank_table):
            table.horizontalHeader().setStyleSheet(
                "QHeaderView::section { padding: 0 6px; }"
            )
        # Sidebar stays compact; the expanded table shows all numerical columns.
        for column in (*range(4, 12), 13):
            self.cell_table.setColumnHidden(column, True)
        self.cell_table.verticalHeader().hide()
        self.cell_table.setMinimumHeight(90)
        lattice_panel.addWidget(self.cell_table, 1)
        self.cell_table_button = QtWidgets.QPushButton("Full lattice table…")
        self.cell_table_button.clicked.connect(self.open_cell_table)
        self.cell_table_button.setEnabled(False)
        lattice_actions = QtWidgets.QHBoxLayout()
        lattice_actions.addWidget(self.cell_table_button)
        self.cell_summary = QtWidgets.QPlainTextEdit()
        self.cell_summary.setReadOnly(True)
        self.cell_summary.setMaximumHeight(65)
        self.cell_summary.hide()
        lattice_panel.addWidget(self.cell_summary)
        self.cell_export_button = QtWidgets.QPushButton("Export cell candidates…")
        self.cell_export_button.setEnabled(False)
        lattice_actions.addWidget(self.cell_export_button)
        lattice_panel.addLayout(lattice_actions)
        self.prediction_selected_cell_label = QtWidgets.QLabel(
            "No ranked cell selected."
        )
        self.prediction_selected_cell_label.setWordWrap(True)
        self.prediction_enabled = QtWidgets.QCheckBox("Show predicted positions (+)")
        self.prediction_enabled.setChecked(True)
        self.prediction_enabled.setToolTip(
            "Cyan +: positions predicted by the selected cell and orientation. "
            "Yellow/red circles: detected spots. Browse omega frames to compare them. "
            "Click a prediction for hkl and omega; weak or absent reflections may be predicted."
        )
        prediction_header = QtWidgets.QHBoxLayout()
        prediction_header.addWidget(self.prediction_enabled)
        prediction_header.addStretch(1)
        prediction_header.addWidget(self.prediction_selected_cell_label)
        ranked_panel.insertLayout(0, prediction_header)
        self.prediction_note = QtWidgets.QLabel(
            "Select a ranked cell to show its predicted positions."
        )
        self.prediction_note.setWordWrap(True)
        self.prediction_note.setToolTip(self.prediction_enabled.toolTip())
        ranked_panel.insertWidget(1, self.prediction_note)
        self.residual_button = QtWidgets.QPushButton("Residual plots…")
        self.residual_button.setEnabled(False)
        prediction_actions = QtWidgets.QHBoxLayout()
        prediction_actions.addWidget(self.residual_button)
        self.refinement_export_button = QtWidgets.QPushButton(
            "Export predicted positions…"
        )
        self.refinement_export_button.setEnabled(False)
        prediction_actions.addWidget(self.refinement_export_button)
        ranked_panel.addLayout(prediction_actions)
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
        self.position_details = QtWidgets.QGroupBox("Selected spot")
        details = QtWidgets.QFormLayout(self.position_details)
        self.position_cell_label = QtWidgets.QLabel()
        self.position_indexing_label = QtWidgets.QLabel()
        self.position_hkl_label = QtWidgets.QLabel()
        self.position_residual_label = QtWidgets.QLabel()
        for title, label in (
            ("Cell", self.position_cell_label),
            ("Indexed", self.position_indexing_label),
            ("hkl", self.position_hkl_label),
            ("Residual", self.position_residual_label),
        ):
            label.setWordWrap(True)
            label.setTextFormat(QtCore.Qt.PlainText)
            label.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
            details.addRow(title, label)
        self.position_residual_label.setToolTip(
            "Calculated minus measured linked-spot centroid. Δxy is detector distance; "
            "Δω compares the Bragg centre with the signal-weighted measured omega. "
            "These are not residuals to the current frame midpoint."
        )
        self.position_indexing_label.setToolTip(
            "Membership in the selected cell's fixed indexed/fit set. "
            "Tracks excluded from the cell search are not assessed."
        )
        self.position_frames_label = QtWidgets.QLabel("Observed frames")
        self.position_frames = QtWidgets.QComboBox()
        self.position_frames.setSizeAdjustPolicy(
            QtWidgets.QComboBox.AdjustToMinimumContentsLengthWithIcon
        )
        self.position_frames.setMinimumContentsLength(12)
        self.position_frames.setPlaceholderText("Choose an observed frame…")
        details.addRow(self.position_frames_label, self.position_frames)
        self.position_details.hide()
        positions_panel.addWidget(self.position_details)
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
        for section in (series_panel, detection_panel):
            section.addStretch(1)
        splitter.addWidget(controls)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)

    def show_spots(self, x, y, flags, *, row_ids=None):
        self.spot_overlay.setData(
            x=x,
            y=y,
            data=[None] * len(flags) if row_ids is None else row_ids,
            brush=["r" if flag else "y" for flag in flags],
            pen=pg.mkPen("k", width=2),
            size=10,
        )

    def show_selected_spot(self, x=None, y=None):
        for item in (self.selected_spot_outline, self.selected_spot_overlay):
            # Hide before clearing cached bounds so the old ring is repainted.
            item.hide()
            item.clear()
            if x is not None and y is not None:
                item.setData(x=[x], y=[y])
                item.show()

    def open_rank_table(self):
        if self._rank_dialog is not None:
            self._rank_dialog.show()
            self._rank_dialog.raise_()
            return
        dialog = QtWidgets.QDialog(self)
        self._rank_dialog = dialog
        dialog.setAttribute(QtCore.Qt.WA_DeleteOnClose)
        dialog.destroyed.connect(lambda: setattr(self, "_rank_dialog", None))
        dialog.setWindowTitle("Ranked cells · select a row to update predictions")
        layout = QtWidgets.QVBoxLayout(dialog)
        note = QtWidgets.QLabel(
            "Highest lattice symmetry among comparable fits first. "
            "Select any finite fitted row to compare its predicted spots; held-out residuals remain diagnostic."
        )
        note.setWordWrap(True)
        layout.addWidget(note)
        view = QtWidgets.QTableView()
        view.setModel(self.rank_table_proxy)
        view.setSelectionModel(self.rank_table.selectionModel())
        view.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        view.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        view.setSortingEnabled(True)
        view.horizontalHeader().setSectionResizeMode(
            QtWidgets.QHeaderView.ResizeToContents
        )
        view.verticalHeader().hide()
        layout.addWidget(view)
        dialog.resize(1250, 430)
        dialog.show()

    def open_cell_table(self):
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle("Candidate cells and grain orientations · experimental")
        layout = QtWidgets.QVBoxLayout(dialog)
        note = QtWidgets.QLabel(
            "All returned candidates within the search bounds. Select a row to use it for prediction/refinement. Multiple grains can share one cell."
        )
        note.setWordWrap(True)
        layout.addWidget(note)
        view = QtWidgets.QTableView()
        view.setModel(self.cell_table_proxy)
        view.setSelectionModel(self.cell_table.selectionModel())
        view.setColumnHidden(3, True)
        view.verticalHeader().hide()
        view.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        view.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        view.setSortingEnabled(True)
        view.horizontalHeader().setSectionResizeMode(
            QtWidgets.QHeaderView.ResizeToContents
        )
        layout.addWidget(view)
        dialog.resize(1200, 550)
        dialog.exec()

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
