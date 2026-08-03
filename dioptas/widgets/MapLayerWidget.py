# SPDX-License-Identifier: MIT

"""Editor for the windows a map is made from and the layers they produce.

Each row is one window of the pattern together with the way it is reduced to
a single number per point — a sum, a background-corrected peak area, a peak
position, a width. Below them sit layers computed from those by arithmetic,
so a ratio or a contrast is a layer like any other.
"""

from __future__ import annotations

import os

from qtpy import QtCore, QtGui, QtWidgets

from ..model.map_reduction import REDUCTION_LABELS, VALUE_KINDS
from .CustomWidgets import IconActionButton


class RowTintDelegate(QtWidgets.QStyledItemDelegate):
    """Paints hover and selection in each row's own colour.

    A single highlight colour for every row throws away the one thing that
    ties a window in this table to its region in the pattern plot. Blending
    the row's colour toward the table background gives "the same colour, but
    darker", which reads as a highlight without losing that link.
    """

    _HOVER_STRENGTH = 0.22
    _SELECTED_STRENGTH = 0.38

    def __init__(self, color_for_row, parent=None):
        super().__init__(parent)
        self._color_for_row = color_for_row

    def createEditor(self, parent, option, index):
        """Renames in place rather than in a box dropped over the row.

        The theme's line edit is a black field with a loud underline and the
        old name selected in blue — against a row drawn in the window's own
        colour that reads as something else entirely having appeared. Sitting
        it in the row, in that colour, keeps the rename where the name is.
        """
        editor = super().createEditor(parent, option, index)
        if isinstance(editor, QtWidgets.QLineEdit):
            color = self._color_for_row(index.row())
            base = option.palette.base().color()
            text = option.palette.text().color()
            if color is None:
                color = option.palette.highlight().color()
            editor.setStyleSheet(
                f"""
                QLineEdit {{
                    background-color: {_blend(base, color, 0.30).name()};
                    color: {text.name()};
                    border: none;
                    border-bottom: 2px solid {color.name()};
                    selection-background-color: {color.name()};
                    selection-color: {base.name()};
                    padding: 0px 2px;
                }}
                """
            )
        return editor

    def paint(self, painter, option, index):
        option = QtWidgets.QStyleOptionViewItem(option)
        state = QtWidgets.QStyle.StateFlag
        selected = bool(option.state & state.State_Selected)
        hovered = bool(option.state & state.State_MouseOver)
        color = self._color_for_row(index.row())

        if color is not None and (selected or hovered):
            base = option.palette.base().color()
            strength = (
                self._SELECTED_STRENGTH if selected else self._HOVER_STRENGTH
            )
            painter.fillRect(option.rect, _blend(base, color, strength))
            # the style would otherwise paint its own highlight on top
            option.state &= ~state.State_Selected
            option.state &= ~state.State_MouseOver
            if selected:
                option.font.setBold(True)
        super().paint(painter, option, index)


def _blend(base: QtGui.QColor, other: QtGui.QColor, fraction: float) -> QtGui.QColor:
    return QtGui.QColor(
        round(base.red() + (other.red() - base.red()) * fraction),
        round(base.green() + (other.green() - base.green()) * fraction),
        round(base.blue() + (other.blue() - base.blue()) * fraction),
    )


class ColorSwatch(QtWidgets.QPushButton):
    """The colour a window is drawn in, and the way to change it."""

    _SIZE = 18

    def __init__(self, color: str, parent=None):
        super().__init__(parent)
        self.setFixedSize(self._SIZE, self._SIZE)
        self.setFlat(True)
        self.setCursor(QtCore.Qt.PointingHandCursor)
        self.set_color(color)

    def set_color(self, color: str):
        self._color = QtGui.QColor(color)
        self.setStyleSheet(
            f"background-color: {self._color.name()};"
            "border: 1px solid rgba(255, 255, 255, 60);"
            "border-radius: 3px;"
        )
        self.setToolTip(f"Colour of this window ({self._color.name()}) — click to change")

    def color(self) -> QtGui.QColor:
        return self._color


class MapLayerWidget(QtWidgets.QWidget):
    """Table of map windows plus the expression layers built on them."""

    sigRoiChanged = QtCore.Signal(str, str, object)
    """(roi name, field, value) — field is x_min/x_max/reduction/
    subtract_background/name"""

    sigAddRoiRequested = QtCore.Signal()
    sigRemoveRoiRequested = QtCore.Signal(str)

    sigExpressionChanged = QtCore.Signal(str, str)
    """(layer name, expression)"""

    sigAddExpressionRequested = QtCore.Signal()
    sigRemoveExpressionRequested = QtCore.Signal(str)

    sigLayerSelected = QtCore.Signal(str)
    """Name of the layer the user picked to be drawn on the map"""

    _ROI_COLUMNS = ("", "", "Name", "From", "To", "Value")
    _EXPRESSION_COLUMNS = ("", "Name", "Expression")

    #: widest number a window range is expected to show, used to size the
    #: From/To columns
    _RANGE_SAMPLE = "00000.0"

    #: rows of each table kept reachable however the splitter is dragged
    _MIN_ROWS = 2

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._updating = False
        self._roi_names: list[str] = []
        self._expression_names: list[str] = []
        self._active_layer = ""
        #: layer name -> its "draw this" radio, all in one exclusive group
        self._show_buttons: dict[str, QtWidgets.QRadioButton] = {}
        self._show_group = QtWidgets.QButtonGroup(self)
        self._show_group.setExclusive(True)

        self.create_widgets()
        self.create_layout()

    def create_widgets(self):
        self.roi_table = QtWidgets.QTableWidget()
        self.roi_table.setColumnCount(len(self._ROI_COLUMNS))
        self.roi_table.setHorizontalHeaderLabels(self._ROI_COLUMNS)
        self.roi_table.verticalHeader().setVisible(False)
        self.roi_table.setSelectionBehavior(
            QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.roi_table.setToolTip(
            "Windows of the pattern, each giving one map layer.\n"
            "'Value' decides what the window is reduced to: the plain sum of\n"
            "counts, the peak area with the background taken off, the peak\n"
            "position (which makes a d-spacing map) or its width."
        )
        header = self.roi_table.horizontalHeader()
        modes = QtWidgets.QHeaderView.ResizeMode
        for column in range(5):
            header.setSectionResizeMode(column, modes.Fixed)
        header.setSectionResizeMode(5, modes.Stretch)
        self.roi_table.itemChanged.connect(self._roi_item_changed)
        self.roi_table.setItemDelegate(
            RowTintDelegate(self._roi_row_color, self.roi_table)
        )

        self.add_roi_btn = IconActionButton(
            "map_add.svg",
            "Add window\n\n"
            "A second window of the pattern, giving another map layer. It is\n"
            "shown straight away and drawn in its own colour.",
        )
        self.add_roi_btn.clicked.connect(self.sigAddRoiRequested)
        self.remove_roi_btn = IconActionButton(
            "map_delete.svg", "Remove the selected window"
        )
        self.remove_roi_btn.clicked.connect(self._remove_roi_clicked)

        self.expression_table = QtWidgets.QTableWidget()
        self.expression_table.setColumnCount(len(self._EXPRESSION_COLUMNS))
        self.expression_table.setHorizontalHeaderLabels(self._EXPRESSION_COLUMNS)
        self.expression_table.verticalHeader().setVisible(False)
        self.expression_table.setSelectionBehavior(
            QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.expression_table.setToolTip(
            "Layers computed from the windows above by their names, e.g.\n"
            "A/B for a phase fraction or (A-B)/(A+B) for a contrast that\n"
            "survives changes in illumination."
        )
        expression_header = self.expression_table.horizontalHeader()
        expression_header.setSectionResizeMode(0, modes.Fixed)
        expression_header.setSectionResizeMode(1, modes.Fixed)
        expression_header.setSectionResizeMode(2, modes.Stretch)
        self.expression_table.itemChanged.connect(self._expression_item_changed)
        self.expression_table.setItemDelegate(
            RowTintDelegate(lambda _row: self._accent(), self.expression_table)
        )

        self.add_expression_btn = IconActionButton(
            "map_add.svg",
            "Add computed layer\n\n"
            "Combines the windows above by name, e.g. A/B for a phase\n"
            "fraction or (A-B)/(A+B) for a contrast.",
        )
        self.add_expression_btn.clicked.connect(self.sigAddExpressionRequested)
        self.remove_expression_btn = IconActionButton(
            "map_delete.svg", "Remove the selected computed layer"
        )
        self.remove_expression_btn.clicked.connect(self._remove_expression_clicked)

        self.roi_help_btn = IconActionButton(
            "map_help.svg", "What the value kinds mean and how they are computed"
        )
        self.roi_help_btn.setFixedSize(22, 22)
        self.roi_help_btn.clicked.connect(self.show_roi_help)
        self.expression_help_btn = IconActionButton(
            "map_help.svg", "What can be written in an expression"
        )
        self.expression_help_btn.setFixedSize(22, 22)
        self.expression_help_btn.clicked.connect(self.show_expression_help)
        self._help_dialog = None

        self.message_lbl = QtWidgets.QLabel("")
        self.message_lbl.setWordWrap(True)

    def create_layout(self):
        """Each table in its own pane of a splitter.

        Sizing the tables to their rows meant adding a window pushed the
        computed layers down the panel, and eventually off it. Giving each a
        pane it fills — scrolling inside it when the rows do not fit — keeps
        both where they are. They stay on one tab rather than two because an
        expression refers to the windows by name, so the names have to be
        readable while it is written.
        """
        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(0, 5, 0, 0)
        outer.setSpacing(4)

        self.splitter = QtWidgets.QSplitter(QtCore.Qt.Vertical)
        self.splitter.setChildrenCollapsible(False)

        self.splitter.addWidget(
            self._table_pane(
                "Windows",
                self.roi_table,
                self.add_roi_btn,
                self.remove_roi_btn,
                self.roi_help_btn,
            )
        )
        self.splitter.addWidget(
            self._table_pane(
                "Computed layers",
                self.expression_table,
                self.add_expression_btn,
                self.remove_expression_btn,
                self.expression_help_btn,
            )
        )
        # windows are the common case and usually outnumber the expressions
        self.splitter.setStretchFactor(0, 3)
        self.splitter.setStretchFactor(1, 2)

        outer.addWidget(self.splitter)
        outer.addWidget(self.message_lbl)

        self._size_columns()
        self._apply_minimum_heights()

    @staticmethod
    def _table_pane(title, table, add_button, remove_button, help_button):
        """A titled table with its buttons in a column beside it.

        The same arrangement the phase and overlay lists use, so the map
        tables read as the same kind of control. The help button sits at the
        bottom of the column, apart from the actions above it.
        """
        pane = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(pane)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.addWidget(QtWidgets.QLabel(title))

        body = QtWidgets.QHBoxLayout()
        body.setSpacing(4)
        body.addWidget(table)
        side = QtWidgets.QVBoxLayout()
        side.setSpacing(8)
        side.addWidget(add_button)
        side.addWidget(remove_button)
        side.addStretch(1)
        # at the bottom, apart from the actions: it explains, it does not act
        side.addWidget(help_button)
        body.addLayout(side)
        layout.addLayout(body)
        return pane

    # --- appearance ------------------------------------------------------

    def _accent(self) -> QtGui.QColor:
        """The theme's accent, used where a row has no colour of its own."""
        accent = QtGui.QColor(os.environ.get("QTMATERIAL_PRIMARYCOLOR", ""))
        if not accent.isValid():
            accent = self.palette().highlight().color()
        return accent

    def _roi_row_color(self, row: int):
        swatch = self.roi_table.cellWidget(row, 1)
        if isinstance(swatch, ColorSwatch):
            return swatch.color()
        return self._accent()

    # --- sizing ----------------------------------------------------------

    def showEvent(self, event):
        # Sized here as well as at construction: this widget lives in a tab
        # that starts hidden, and the style may only be fully resolved by the
        # time it is first shown.
        super().showEvent(event)
        self._size_columns()
        self._apply_minimum_heights()

    def _size_columns(self):
        show_width = QtWidgets.QRadioButton().sizeHint().width() + 8
        metrics = self.roi_table.fontMetrics()
        range_width = metrics.horizontalAdvance(self._RANGE_SAMPLE) + 16
        name_width = metrics.horizontalAdvance("MMMM") + 16

        for table, columns in (
            (
                self.roi_table,
                (
                    (0, show_width),
                    (1, ColorSwatch._SIZE + 8),
                    (2, name_width),
                    (3, range_width),
                    (4, range_width),
                ),
            ),
            (self.expression_table, ((0, show_width), (1, name_width))),
        ):
            header = table.horizontalHeader()
            fixed = 0
            for column, wanted in columns:
                # never narrower than the header text the style draws
                width = max(wanted, header.sectionSizeHint(column))
                table.setColumnWidth(column, width)
                fixed += width
            # the stretching last column has to be able to hold its contents;
            # otherwise its cell widget is simply clipped
            table.setMinimumWidth(
                fixed + self._last_column_minimum(table) + 2 * table.frameWidth()
            )

    def _last_column_minimum(self, table: QtWidgets.QTableWidget) -> int:
        if table is not self.roi_table:
            return table.fontMetrics().horizontalAdvance("(A-B)/(A+B)") + 16
        probe = QtWidgets.QComboBox()
        for label, _, _ in VALUE_KINDS:
            probe.addItem(label)
        return probe.sizeHint().width() + 8

    def _row_height(self, table: QtWidgets.QTableWidget) -> int:
        if table.rowCount():
            return table.rowHeight(0)
        return table.verticalHeader().defaultSectionSize()

    def _apply_minimum_heights(self):
        """Keeps a couple of rows of each table visible whatever the split.

        A floor rather than a fixed height: the tables fill the pane they are
        given and scroll inside it, so adding a window does not move anything
        else on the panel.
        """
        for table in (self.roi_table, self.expression_table):
            height = (
                table.horizontalHeader().height()
                + self._MIN_ROWS * self._row_height(table)
                + 2 * table.frameWidth()
            )
            table.setMinimumHeight(height)

    # --- help -------------------------------------------------------------

    _ROI_HELP = """
<h3>What a window measures</h3>
<p>Each window turns the part of the pattern between <i>From</i> and <i>To</i>
into one number per map point. <b>Nothing is fitted</b> — every value comes
from the measured points directly, which keeps the maps fast and free of
convergence problems, at the price of assuming the window brackets a single
feature.</p>
<p><b>Background</b>, where it is subtracted, is the straight line joining the
two edges of the window; each edge is averaged over the outer 10&nbsp;% of the
window so one noisy channel cannot tilt it.</p>
<ul>
<li><b>Sum</b> — the counts in the window, as measured. Also tracks how much
sample the beam went through, so it often maps thickness as much as phase.</li>
<li><b>Sum − bkg</b> — the same after subtracting the background line.</li>
<li><b>Mean</b> — the average count.</li>
<li><b>Max</b> — the highest count.</li>
<li><b>Peak area</b> — the integral (trapezoid rule) of the
background-subtracted profile.</li>
<li><b>Peak pos.</b> — the intensity-weighted centre (centre of mass) of the
background-subtracted profile; parts below the background are ignored. Mapped
over a scan this is a d-spacing, and therefore strain, map. It is <i>not</i> a
peak fit: for a single peak in the window it is robust even for asymmetric
shapes, but a neighbouring peak inside the window pulls it sideways — keep the
window tight around one peak.</li>
<li><b>Peak FWHM</b> — the full width at half maximum, read by interpolating
where the profile crosses half its maximum on either side of the highest
point. Blank when the profile does not come back below half inside the
window.</li>
</ul>
<p>A point shows as blank (transparent) when its window holds nothing to
measure.</p>
"""

    _EXPRESSION_HELP = """
<h3>Computed layers</h3>
<p>An expression combines the windows above by their <b>names</b>, computed
per map point. Anything that is not plain arithmetic is rejected.</p>
<p><b>Allowed:</b></p>
<ul>
<li>window names (<code>A</code>, <code>B</code>, …) and numbers</li>
<li>operators <code>+&nbsp;&minus;&nbsp;*&nbsp;/&nbsp;**&nbsp;%</code> and
parentheses</li>
<li>functions <code>abs, sqrt, log, log10, exp, clip, minimum,
maximum</code></li>
<li><code>ovl(overlay, window)</code> — an <b>overlay</b> put through a
window: interpolated onto the map's axis (read in the map's unit) and
reduced with that window's range, value kind and background setting, giving
one number. With a single window in the expression the window argument can
be left out: <code>A - ovl(bkg_empty)</code> is the difference to that
reference. Overlay names that are not plain words go in quotes:
<code>ovl('my background', A)</code>.</li>
</ul>
<p><b>Examples:</b></p>
<ul>
<li><code>A/B</code> — a phase fraction</li>
<li><code>(A-B)/(A+B)</code> — a contrast that survives changes in
illumination</li>
<li><code>log10(A)</code> — compress a large dynamic range</li>
<li><code>clip(A/B, 0, 2)</code> — bound outliers</li>
<li><code>maximum(A, B)</code> — the stronger of two windows</li>
<li><code>A - ovl(bkg_empty)</code> — window A minus the same window of an
overlay</li>
</ul>
<p>Dividing by zero makes the affected points blank rather than failing the
whole layer. A layer whose expression cannot be evaluated is skipped and the
reason shown below the tables.</p>
"""

    def show_roi_help(self):
        self._show_help("Map windows", self._ROI_HELP)

    def show_expression_help(self):
        self._show_help("Computed layers", self._EXPRESSION_HELP)

    def _show_help(self, title: str, html: str):
        """Opens the help beside the tables, without blocking them.

        Non-modal on purpose: the text is a reference to keep open while
        editing, and a modal box would also freeze the whole application
        (and any test) until dismissed.
        """
        if self._help_dialog is not None:
            try:
                self._help_dialog.close()
            except RuntimeError:
                # delete-on-close destroyed it behind the wrapper already
                pass
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle(title)
        dialog.setAttribute(QtCore.Qt.WA_DeleteOnClose)
        # delete-on-close kills the C++ object when the user closes the
        # dialog; without dropping the reference the next open would call
        # close() on the dead wrapper. Bound to this dialog: the destruction
        # arrives deferred, and one replaced by a newer dialog must not
        # clear the newer one's reference.
        dialog.destroyed.connect(
            lambda _=None, closed=dialog: self._forget_help_dialog(closed)
        )
        layout = QtWidgets.QVBoxLayout(dialog)
        text = QtWidgets.QTextBrowser()
        text.setHtml(html)
        text.setOpenExternalLinks(False)
        layout.addWidget(text)
        dialog.resize(520, 560)
        dialog.show()
        self._help_dialog = dialog

    def _forget_help_dialog(self, closed):
        if self._help_dialog is closed:
            self._help_dialog = None

    # --- filling in ------------------------------------------------------

    def _make_show_button(
        self, table: QtWidgets.QTableWidget, row: int, name: str, color=None
    ):
        """Puts the 'draw this layer' radio in the row's first cell.

        One button group across both tables, so exactly one layer is drawn
        and picking any of them turns the previous one off. The radio takes
        the layer's own colour, and both it and the widget holding it are
        transparent — an opaque cell here would punch a dark hole in the
        row's colour, which is what makes it look out of place.
        """
        button = QtWidgets.QRadioButton()
        button.setToolTip(f"Draw '{name}' on the map")
        button.setChecked(name == self._active_layer)
        self.style_show_button(button, color if color is not None else self._accent())
        self._show_group.addButton(button)
        button.toggled.connect(
            lambda checked, layer=name: self._show_toggled(layer, checked)
        )

        holder = QtWidgets.QWidget()
        holder.setAttribute(QtCore.Qt.WA_TranslucentBackground, True)
        # by object name, so it does not cascade into the radio it holds
        holder.setObjectName("map_show_cell")
        holder.setStyleSheet("#map_show_cell { background: transparent; }")
        holder_layout = QtWidgets.QHBoxLayout(holder)
        holder_layout.setContentsMargins(0, 0, 0, 0)
        holder_layout.setAlignment(QtCore.Qt.AlignCenter)
        holder_layout.addWidget(button)
        table.setCellWidget(row, 0, holder)
        self._show_buttons[name] = button

    @staticmethod
    def style_show_button(button: QtWidgets.QRadioButton, color: QtGui.QColor):
        """Draws the radio as a ring in *color*, filled when it is the one
        being shown."""
        name = QtGui.QColor(color).name()
        button.setStyleSheet(
            f"""
            QRadioButton {{ background: transparent; }}
            QRadioButton::indicator {{
                width: 11px;
                height: 11px;
                border: 2px solid {name};
                border-radius: 7px;
                background: transparent;
                /* the theme draws its own dot in here otherwise */
                image: none;
            }}
            QRadioButton::indicator:checked {{
                background: {name};
                image: none;
            }}
            """
        )

    def _show_toggled(self, name: str, checked: bool):
        if self._updating or not checked:
            return
        self.sigLayerSelected.emit(name)

    def set_active_layer(self, name: str):
        """Marks which layer the map is currently drawing."""
        self._active_layer = name
        self._updating = True
        try:
            for layer_name, button in self._show_buttons.items():
                button.setChecked(layer_name == name)
        finally:
            self._updating = False

    def _reset_show_buttons(self, names: list[str]):
        """Forgets the buttons of rows that are about to be replaced."""
        for name in names:
            button = self._show_buttons.pop(name, None)
            if button is not None:
                self._show_group.removeButton(button)

    def set_rois(self, rois):
        """Shows the given MapRoiParams.

        The map is rebuilt on every edit, so this runs constantly. Rows are
        therefore updated in place whenever the windows themselves are the
        same ones — recreating them would drop the selection under the user
        and leave the replaced cell widgets painting until Qt gets round to
        deleting them.
        """
        names = [roi.name for roi in rois]
        self._updating = True
        try:
            if names == self._roi_names and self.roi_table.rowCount() == len(rois):
                for row, roi in enumerate(rois):
                    self._update_roi_row(row, roi)
                return
            self._reset_show_buttons(self._roi_names)
            self._roi_names = names
            self._clear_cell_widgets(self.roi_table)
            self.roi_table.setRowCount(len(rois))
            for row, roi in enumerate(rois):
                self._fill_roi_row(row, roi)
            self._apply_minimum_heights()
        finally:
            self._updating = False

    @staticmethod
    def _clear_cell_widgets(table: QtWidgets.QTableWidget):
        """Takes cell widgets out before their rows go.

        Qt only schedules the replaced widget for deletion, and until that
        happens it still paints — over whatever was drawn in its place.
        """
        for row in range(table.rowCount()):
            for column in range(table.columnCount()):
                widget = table.cellWidget(row, column)
                if widget is not None:
                    widget.hide()
                    table.removeCellWidget(row, column)

    def _update_roi_row(self, row: int, roi):
        """Refreshes an existing row without replacing its widgets."""
        swatch = self.roi_table.cellWidget(row, 1)
        if isinstance(swatch, ColorSwatch) and swatch.color().name() != roi.color:
            swatch.set_color(roi.color)
            name_item = self.roi_table.item(row, 2)
            if name_item is not None:
                name_item.setForeground(QtGui.QColor(roi.color))
            button = self._show_buttons.get(roi.name)
            if button is not None:
                self.style_show_button(button, QtGui.QColor(roi.color))
        self._set_text(self.roi_table.item(row, 3), f"{roi.x_min:.4g}")
        self._set_text(self.roi_table.item(row, 4), f"{roi.x_max:.4g}")
        value_cb = self.roi_table.cellWidget(row, 5)
        if isinstance(value_cb, QtWidgets.QComboBox):
            index = self._value_kind_index(roi)
            if value_cb.currentIndex() != index:
                value_cb.setCurrentIndex(index)
            value_cb.setToolTip(REDUCTION_LABELS.get(roi.reduction, ""))

    @staticmethod
    def _set_text(item, text: str):
        # writing an unchanged value would still emit itemChanged
        if item is not None and item.text() != text:
            item.setText(text)

    @staticmethod
    def _value_kind_index(roi) -> int:
        """Row of VALUE_KINDS matching the window's reduction.

        Matched in Python rather than with findData, which does not compare
        tuples reliably across the Qt bindings.
        """
        wanted = (roi.reduction, bool(roi.subtract_background))
        for index, (_, reduction, subtract) in enumerate(VALUE_KINDS):
            if (reduction, subtract) == wanted:
                return index
        # a background flag the list has no entry for (e.g. mean with
        # subtraction, set through a project file) still shows its kind
        for index, (_, reduction, _) in enumerate(VALUE_KINDS):
            if reduction == roi.reduction:
                return index
        return 0

    def _fill_roi_row(self, row: int, roi):
        self._make_show_button(
            self.roi_table, row, roi.name, QtGui.QColor(roi.color)
        )

        swatch = ColorSwatch(roi.color)
        swatch.clicked.connect(lambda _=False, name=roi.name: self._pick_color(name))
        self.roi_table.setCellWidget(row, 1, swatch)

        name_item = QtWidgets.QTableWidgetItem(roi.name)
        name_item.setForeground(QtGui.QColor(roi.color))
        self.roi_table.setItem(row, 2, name_item)
        self.roi_table.setItem(row, 3, QtWidgets.QTableWidgetItem(f"{roi.x_min:.4g}"))
        self.roi_table.setItem(row, 4, QtWidgets.QTableWidgetItem(f"{roi.x_max:.4g}"))

        value_cb = QtWidgets.QComboBox()
        for index, (label, reduction, subtract) in enumerate(VALUE_KINDS):
            value_cb.addItem(label, (reduction, subtract))
            value_cb.setItemData(
                index,
                REDUCTION_LABELS.get(reduction, label),
                QtCore.Qt.ToolTipRole,
            )
        value_cb.setCurrentIndex(self._value_kind_index(roi))
        value_cb.setToolTip(REDUCTION_LABELS.get(roi.reduction, ""))
        value_cb.currentIndexChanged.connect(
            lambda _index, name=roi.name, box=value_cb: self._emit_roi_change(
                name, "value_kind", box.currentData()
            )
        )
        self.roi_table.setCellWidget(row, 5, value_cb)

    def set_expressions(self, expressions: dict):
        """Shows the computed layers, in place where the set is unchanged.

        Same reason as the windows table: this runs on every map rebuild, so
        replacing the rows would take the selection away mid-edit.
        """
        names = list(expressions)
        self._updating = True
        try:
            if names == self._expression_names:
                for row, expression in enumerate(expressions.values()):
                    self._set_text(self.expression_table.item(row, 2), expression)
                return
            self._reset_show_buttons(self._expression_names)
            self._expression_names = names
            self._clear_cell_widgets(self.expression_table)
            self.expression_table.setRowCount(len(expressions))
            for row, (name, expression) in enumerate(expressions.items()):
                self._make_show_button(self.expression_table, row, name)
                self.expression_table.setItem(
                    row, 1, QtWidgets.QTableWidgetItem(name)
                )
                self.expression_table.setItem(
                    row, 2, QtWidgets.QTableWidgetItem(expression)
                )
            self._apply_minimum_heights()
        finally:
            self._updating = False

    def set_message(self, message: str):
        self.message_lbl.setText(message)

    # --- edits -----------------------------------------------------------

    def _emit_roi_change(self, name: str, field: str, value):
        if self._updating:
            return
        self.sigRoiChanged.emit(name, field, value)

    def _roi_item_changed(self, item: QtWidgets.QTableWidgetItem):
        if self._updating:
            return
        row, column = item.row(), item.column()
        if not (0 <= row < len(self._roi_names)):
            return
        name = self._roi_names[row]
        if column == 2:
            self.sigRoiChanged.emit(name, "name", item.text().strip())
            return
        try:
            value = float(item.text())
        except ValueError:
            self.set_message("That is not a number.")
            return
        self.sigRoiChanged.emit(name, "x_min" if column == 3 else "x_max", value)

    def _expression_item_changed(self, item: QtWidgets.QTableWidgetItem):
        if self._updating:
            return
        row = item.row()
        if not (0 <= row < len(self._expression_names)):
            return
        name = self._expression_names[row]
        if item.column() == 1:
            new_name = item.text().strip()
            expression_item = self.expression_table.item(row, 2)
            expression = expression_item.text() if expression_item else ""
            self.sigRemoveExpressionRequested.emit(name)
            if new_name:
                self.sigExpressionChanged.emit(new_name, expression)
        else:
            self.sigExpressionChanged.emit(name, item.text())

    def _pick_color(self, name: str):
        """Asks for a new colour for a window and reports it."""
        current = None
        for row, roi_name in enumerate(self._roi_names):
            if roi_name == name:
                widget = self.roi_table.cellWidget(row, 1)
                current = widget.color() if isinstance(widget, ColorSwatch) else None
                break
        chosen = QtWidgets.QColorDialog.getColor(
            current or QtGui.QColor("#40e0d0"),
            self,
            f"Colour for window {name}",
        )
        if chosen.isValid():
            self.sigRoiChanged.emit(name, "color", chosen.name())

    def _remove_roi_clicked(self):
        name = self._selected(self.roi_table, self._roi_names)
        if name is not None:
            self.sigRemoveRoiRequested.emit(name)

    def _remove_expression_clicked(self):
        name = self._selected(self.expression_table, self._expression_names)
        if name is not None:
            self.sigRemoveExpressionRequested.emit(name)

    @staticmethod
    def _selected(table: QtWidgets.QTableWidget, names: list[str]) -> str | None:
        row = table.currentRow()
        if 0 <= row < len(names):
            return names[row]
        return None
