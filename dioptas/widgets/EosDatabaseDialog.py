# -*- coding: utf-8 -*-
# Dioptas - GUI program for fast processing of 2D X-ray diffraction data
"""
EoS material database browser dialog — pure view, opened as a compact
modal from the Phase panel. All content and behavior comes from
EosDatabaseController; the dialog only lays out widgets and re-emits
user actions as signals.
"""

import re

from qtpy import QtWidgets, QtCore

from .CustomWidgets import FlatButton, HorizontalLine


_SUBSCRIPT_DIGITS = str.maketrans("0123456789", "₀₁₂₃₄₅₆₇₈₉")
_SCREW_AXIS_PREFIX = re.compile(r"^([PABCIFR]\s*)([2346])([1-5])")


class _NumericTableItem(QtWidgets.QTableWidgetItem):
    """Sort formatted values by their number, ignoring error annotations."""

    def __lt__(self, other):
        def key(text):
            match = re.match(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?", text)
            return (0, float(match.group())) if match else (1, text.casefold())

        return key(self.text()) < key(other.text())


def _display_space_group(space_group: str) -> str:
    """Render compact Hermann-Mauguin symbols in crystallographic form."""
    displayed = _SCREW_AXIS_PREFIX.sub(
        lambda match: (
            f"{match.group(1)}{match.group(2)}"
            f"{match.group(3).translate(_SUBSCRIPT_DIGITS)}"
        ),
        space_group,
    )
    displayed = re.sub(
        r"_(\d)",
        lambda match: match.group(1).translate(_SUBSCRIPT_DIGITS),
        displayed,
    )
    return displayed


class EosDatabaseDialog(QtWidgets.QDialog):

    search_changed = QtCore.Signal(str)
    material_selected = QtCore.Signal(int)   # index in the supplied materials
    eos_selected = QtCore.Signal()
    load_clicked = QtCore.Signal()
    export_clicked = QtCore.Signal()
    report_clicked = QtCore.Signal()
    view_changed = QtCore.Signal(int)
    favourite_clicked = QtCore.Signal()
    diffraction_filter_changed = QtCore.Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("EoS Material Database")
        self.setMinimumSize(720, 520)
        self.setModal(True)
        self.setWindowModality(QtCore.Qt.ApplicationModal)
        self._selection_timer = QtCore.QTimer(self)
        self._selection_timer.setSingleShot(True)
        self._selection_timer.timeout.connect(self._show_selected_eos)

        self._create_widgets()
        self._create_layout()
        self._connect_signals()

    def showEvent(self, event):
        """
        On macOS, a QDialog shown via exec_() from a button click can come
        up without keyboard focus actually landing on a child widget — the
        text fields look interactive but don't accept clicks/typing until
        the window is explicitly activated. Force it here.
        """
        super().showEvent(event)
        self.raise_()
        self.activateWindow()
        self.search_input.setFocus(QtCore.Qt.OtherFocusReason)
        self._selection_timer.start(0)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._selection_timer.start(0)

    def _show_selected_eos(self):
        # Layout/word wrapping can resize the viewport after a refill. Scroll
        # once it has settled, retaining an explicitly empty held selection.
        rows = self.eos_table.selectionModel().selectedRows()
        if rows:
            self.eos_table.scrollTo(rows[0], QtWidgets.QAbstractItemView.EnsureVisible)

    def _create_widgets(self):
        self.search_input = QtWidgets.QLineEdit()
        self.search_input.setPlaceholderText(
            "Search all materials: Au, MgFe, gold, periclase, alumina…")
        self.clear_btn = FlatButton("Clear")
        self.view_tabs = QtWidgets.QTabBar()
        for title in ("Recent", "Favourites", "All"):
            self.view_tabs.addTab(title)
        self.materials_label = QtWidgets.QLabel("Materials:")
        self.hide_eos_only_cb = QtWidgets.QCheckBox(
            "Hide materials without diffraction data")
        self.hide_eos_only_cb.setToolTip(
            "Show only materials with a crystal structure or reference peak table.\n"
            "Materials requiring an assumed structure are also hidden.")
        self.favourite_btn = FlatButton("☆ Favourite")
        self.favourite_btn.setEnabled(False)
        self.empty_label = QtWidgets.QLabel()
        self.empty_label.setWordWrap(True)

        self.materials_table = QtWidgets.QTableWidget()
        self.materials_table.setColumnCount(3)
        self.materials_table.setHorizontalHeaderLabels(
            ["Material", "Space Group", "Diffraction"])
        self.materials_table.horizontalHeaderItem(2).setToolTip(
            "Data available for calculating diffraction phase lines.\n"
            "A space-group symbol alone is not a complete crystal structure.")
        self.eos_table = QtWidgets.QTableWidget()
        self.eos_table.setColumnCount(9)
        # Keep this label uppercase in the model as well as on screen. The
        # theme's text-transform happens only while painting, after Qt has
        # measured the narrower mixed-case text, and otherwise clips the F.
        self.eos_table.setHorizontalHeaderLabels(
            ["EoS", "T", "Authors", "Year", "FIT P RANGE",
             "K0 (GPa)", "K0′", "V0 (Å³)", "Assessment"])
        self.eos_table.horizontalHeaderItem(8).setToolTip(
            "Scoped numerical assessment, separate from source verification, "
            "original-author fit reproduction and recommendation for use. "
            "Hover over an assessment for its audit and limitations.")
        self.eos_table.setToolTip(
            "Fit P range is the experimental pressure interval used to "
            "constrain the published EoS, not a phase-stability range.\n"
            "Theoretical, reference-model, and qualitative-limit records "
            "have no defensible numeric fit interval.\n"
            "± values are publication-reported errors in the displayed "
            "units.\n‘error n/r’ means that no verified error is recorded; "
            "it does not mean zero.")
        for table in (self.materials_table, self.eos_table):
            table.setSelectionBehavior(
                QtWidgets.QAbstractItemView.SelectRows)
            table.setSelectionMode(
                QtWidgets.QAbstractItemView.SingleSelection)
            table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
            table.verticalHeader().setVisible(False)
            # Preserve library/recent order until the user chooses a column.
            table.horizontalHeader().setSortIndicator(
                -1, QtCore.Qt.AscendingOrder)
            table.setSortingEnabled(True)
        self.materials_table.setAlternatingRowColors(True)
        # Keep the material columns governed by persistent resize modes.
        # A one-shot resizeColumnsToContents() briefly shrinks the header to
        # the width of a single search result before Qt gets another layout
        # pass, which can leave a visible gap on some platforms.
        materials_header = self.materials_table.horizontalHeader()
        materials_header.setSectionResizeMode(
            0, QtWidgets.QHeaderView.Stretch)
        materials_header.setSectionResizeMode(
            1, QtWidgets.QHeaderView.ResizeToContents)
        materials_header.setSectionResizeMode(
            2, QtWidgets.QHeaderView.ResizeToContents)
        # keep the "Space Group" header readable even when all cell
        # contents are narrower
        materials_header.setMinimumSectionSize(120)
        eos_header = self.eos_table.horizontalHeader()
        eos_header.setObjectName("eos_database_header")
        # Set widths once so changing materials never shifts the columns.
        # Interactive sections support dragging and double-clicking a border
        # to fit its current contents; Qt keeps those widths on later refills.
        eos_header.setSectionResizeMode(QtWidgets.QHeaderView.Interactive)
        eos_header.setToolTip(
            "Drag column borders to resize; double-click a border to fit contents.")
        eos_widths = (95, 40, 150, 65, 150, 130, 120, 150, 155)
        for column, width in enumerate(eos_widths):
            eos_header.resizeSection(column, width)
        self.resize(sum(eos_widths) + 40, 660)

        self.export_btn = FlatButton("Export .eosmat…")
        self.export_btn.setEnabled(False)
        self.export_btn.setToolTip(
            "Save the selected material (all its EoS records) as a\n"
            ".eosmat file that can be loaded with the normal Add button")
        self.load_btn = QtWidgets.QPushButton("Load as Phase")
        self.report_btn = FlatButton("Open reconstruction report")
        self.report_btn.setEnabled(False)
        self.load_btn.setEnabled(False)
        self.load_btn.setDefault(True)
        self.close_btn = QtWidgets.QPushButton("Close")
        self.assume_structure_cb = QtWidgets.QCheckBox(
            "Use assumed tetragonal perovskite structure")
        self.assume_structure_cb.setVisible(False)
        self.structure_note = QtWidgets.QLabel()
        self.structure_note.setWordWrap(True)
        self.structure_note.setVisible(False)
        self.reproduction_note = QtWidgets.QLabel()
        self.reproduction_note.setWordWrap(True)
        self.reproduction_note.setVisible(False)

    def _create_layout(self):
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        search_row = QtWidgets.QHBoxLayout()
        search_row.addWidget(self.search_input, 1)
        search_row.addWidget(self.clear_btn)
        root.addLayout(search_row)

        root.addWidget(self.view_tabs)
        materials_row = QtWidgets.QHBoxLayout()
        materials_row.addWidget(self.materials_label)
        materials_row.addStretch()
        materials_row.addWidget(self.hide_eos_only_cb)
        materials_row.addWidget(self.favourite_btn)
        root.addLayout(materials_row)
        root.addWidget(self.empty_label)
        self.tables_splitter = QtWidgets.QSplitter(QtCore.Qt.Vertical)
        self.tables_splitter.setChildrenCollapsible(False)
        self.materials_table.setMinimumHeight(70)
        records = QtWidgets.QWidget()
        records_layout = QtWidgets.QVBoxLayout(records)
        records_layout.setContentsMargins(0, 0, 0, 0)
        records_layout.setSpacing(6)
        records_layout.addWidget(QtWidgets.QLabel("Equation of state records:"))
        records_layout.addWidget(self.eos_table)
        self.tables_splitter.addWidget(self.materials_table)
        self.tables_splitter.addWidget(records)
        self.tables_splitter.setStretchFactor(0, 1)
        self.tables_splitter.setStretchFactor(1, 2)
        self.tables_splitter.setSizes([140, 280])
        root.addWidget(self.tables_splitter, 1)
        root.addWidget(self.reproduction_note)
        root.addWidget(self.assume_structure_cb)
        root.addWidget(self.structure_note)

        root.addWidget(HorizontalLine())

        bottom = QtWidgets.QHBoxLayout()
        bottom.addWidget(self.export_btn)
        bottom.addWidget(self.report_btn)
        bottom.addStretch()
        bottom.addWidget(self.load_btn)
        bottom.addWidget(self.close_btn)
        root.addLayout(bottom)

    def _connect_signals(self):
        self.search_input.textChanged.connect(self.search_changed)
        self.clear_btn.clicked.connect(self.search_input.clear)
        self.view_tabs.currentChanged.connect(self.view_changed)
        self.favourite_btn.clicked.connect(self.favourite_clicked)
        self.hide_eos_only_cb.toggled.connect(self.diffraction_filter_changed)
        self.materials_table.selectionModel().selectionChanged.connect(
            self._emit_material_selected)
        self.materials_table.doubleClicked.connect(
            self._load_material_from_double_click)
        self.eos_table.doubleClicked.connect(
            self._load_eos_from_double_click)
        self.eos_table.selectionModel().selectionChanged.connect(
            self.eos_selected)
        self.eos_table.selectionModel().selectionChanged.connect(
            lambda *_: self._selection_timer.start(0))
        self.eos_table.horizontalHeader().sortIndicatorChanged.connect(
            lambda *_: self._selection_timer.start(0))
        self.tables_splitter.splitterMoved.connect(
            lambda *_: self._selection_timer.start(0))
        self.load_btn.clicked.connect(self.load_clicked)
        self.export_btn.clicked.connect(self.export_clicked)
        self.report_btn.clicked.connect(self.report_clicked)
        self.close_btn.clicked.connect(self.reject)

    def _emit_material_selected(self):
        self.material_selected.emit(self.selected_material_row())

    def _load_material_from_double_click(self, index):
        if index.isValid():
            self.materials_table.selectRow(index.row())
            self.load_clicked.emit()

    def _load_eos_from_double_click(self, index):
        if index.isValid():
            self.eos_table.selectRow(index.row())
            self.load_clicked.emit()

    # -- view interface used by the controller -------------------------

    def set_favourite(self, selected, favourite=False):
        self.favourite_btn.setEnabled(selected)
        self.favourite_btn.setText(
            "★ Favourite" if favourite else "☆ Favourite")
        self.favourite_btn.setToolTip(
            "Remove from favourites" if favourite else "Add to favourites")

    def set_materials_summary(self, count, searching, empty_message):
        self.materials_label.setText(
            f"{'Search results' if searching else 'Materials'} ({count}):")
        self.empty_label.setText(empty_message)
        self.empty_label.setVisible(count == 0)

    def fill_materials(self, rows):
        """Rows contain display name, space group, diffraction status and tooltip."""
        table = self.materials_table
        # Drop any previous selection first: after a refill the same row
        # index would still count as "selected" without ever firing
        # selectionChanged, leaving the EoS table below showing the
        # records of whatever material sat at that row before.
        table.clearSelection()
        # Sorting and replacing items can move the current index. Do not
        # let those intermediate changes select a partially populated row.
        selection_blocker = QtCore.QSignalBlocker(table.selectionModel())
        sorting_enabled = table.isSortingEnabled()
        table.setSortingEnabled(False)
        table.setRowCount(len(rows))
        for r, (name, space_group, diffraction_status, tooltip) in enumerate(rows):
            name_item = QtWidgets.QTableWidgetItem(name)
            name_item.setData(QtCore.Qt.UserRole, r)
            name_item.setToolTip(tooltip)
            table.setItem(r, 0, name_item)
            space_group_item = QtWidgets.QTableWidgetItem(
                _display_space_group(space_group)
            )
            table.setItem(r, 1, space_group_item)
            diffraction_item = QtWidgets.QTableWidgetItem(diffraction_status)
            diffraction_item.setToolTip(tooltip)
            table.setItem(r, 2, diffraction_item)
        table.setSortingEnabled(sorting_enabled)
        table.clearSelection()
        selection_blocker.unblock()


    def fill_eos_records(self, rows, selected_row=0,
                         reference_tooltips=None, thermal_tooltips=None,
                         reproduction_tooltips=None):
        """Rows include authors/year, thermal indicator and fit values."""
        table = self.eos_table
        selection_blocker = QtCore.QSignalBlocker(table.selectionModel())
        reference_tooltips = reference_tooltips or []
        thermal_tooltips = thermal_tooltips or []
        reproduction_tooltips = reproduction_tooltips or []
        table.clearSelection()
        sorting_enabled = table.isSortingEnabled()
        table.setSortingEnabled(False)
        table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            for c, text in enumerate(row):
                item_type = (_NumericTableItem if 3 <= c <= 7
                             else QtWidgets.QTableWidgetItem)
                item = item_type(text)
                if c in (5, 6, 7):
                    item.setTextAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
                elif c == 3:
                    item.setTextAlignment(QtCore.Qt.AlignCenter)
                if c == 0:
                    item.setData(QtCore.Qt.UserRole, r)
                if c in (2, 3) and r < len(reference_tooltips):
                    item.setToolTip(reference_tooltips[r])
                elif c == 1:
                    item.setTextAlignment(QtCore.Qt.AlignCenter)
                    if r < len(thermal_tooltips):
                        item.setToolTip(thermal_tooltips[r])
                elif c == 8 and r < len(reproduction_tooltips):
                    item.setToolTip(reproduction_tooltips[r])
                table.setItem(r, c, item)
        selected_item = (
            table.item(selected_row, 0)
            if 0 <= selected_row < len(rows) else None)
        table.setSortingEnabled(sorting_enabled)
        table.clearSelection()
        if selected_item is not None:
            table.selectRow(selected_item.row())
            table.scrollToItem(selected_item)
        selection_blocker.unblock()
        self._selection_timer.start(0)
        # A material without EoS records is still loadable — its peak
        # positions at ambient conditions are useful on their own.
        material_selected = self.selected_material_row() >= 0
        self.load_btn.setEnabled(material_selected)
        self.export_btn.setEnabled(material_selected)

    def selected_material_row(self) -> int:
        """Return the source index, independent of the current sort order."""
        return self._selected_source_row(self.materials_table)

    def set_reproduction_assessment(self, detail=""):
        self.reproduction_note.setText(detail.split("\n\n", 1)[0])
        self.reproduction_note.setToolTip(detail)
        self.reproduction_note.setVisible(bool(detail))

    def set_phase_load_enabled(self, enabled: bool, reason: str = ""):
        self.load_btn.setEnabled(enabled)
        self.load_btn.setToolTip(
            "" if enabled else reason or
            "No crystal structure or reference peak table is available for "
            "diffraction phase lines. The material can still be exported.")

    def selected_eos_row(self) -> int:
        """Return the source record index, independent of sort order."""
        return self._selected_source_row(self.eos_table)

    @staticmethod
    def _selected_source_row(table) -> int:
        rows = table.selectionModel().selectedRows()
        if not rows:
            return -1
        return table.item(rows[0].row(), 0).data(QtCore.Qt.UserRole)
