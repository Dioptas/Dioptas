# SPDX-License-Identifier: MIT

"""Popup for how map points are laid out on the grid.

The map plot's control strip is shared with the integration view, so it has
room for the grid size and little else. Everything else about the layout —
the scan conventions and the repair for dropped frames — lives here, one
click away.
"""

from __future__ import annotations

from qtpy import QtCore, QtGui, QtWidgets


class MapGridPopup(QtWidgets.QFrame):
    """Grid size, scan conventions and dropped-frame repair for the map."""

    sigGridChanged = QtCore.Signal(int, int)
    """Emitted with (rows, columns) when the user picks a grid size"""

    sigSnakeChanged = QtCore.Signal(bool)
    sigTransposeChanged = QtCore.Signal(bool)
    sigFlipHorizontalChanged = QtCore.Signal(bool)
    sigFlipVerticalChanged = QtCore.Signal(bool)

    sigDetectGapsRequested = QtCore.Signal()
    """Emitted when the user asks for the filename numbering to be checked"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Map grid")
        self.setWindowFlags(QtCore.Qt.Popup)
        self.setFrameStyle(QtWidgets.QFrame.Panel | QtWidgets.QFrame.Raised)
        self.setLineWidth(2)

        self._updating = False

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        layout.addWidget(self._create_size_group())
        layout.addWidget(self._create_orientation_group())
        layout.addWidget(self._create_gaps_group())

    def _create_size_group(self) -> QtWidgets.QWidget:
        group = QtWidgets.QGroupBox("Grid", self)
        grid = QtWidgets.QGridLayout(group)

        self.map_dimension_cb = QtWidgets.QComboBox()
        self.map_dimension_cb.setToolTip(
            "Grids that hold the loaded points exactly, with no blank cells"
        )
        self.map_dimension_cb.currentIndexChanged.connect(self._preset_changed)

        self.rows_sb = QtWidgets.QSpinBox()
        self.rows_sb.setRange(1, 100000)
        self.columns_sb = QtWidgets.QSpinBox()
        self.columns_sb.setRange(1, 100000)
        for spin_box in (self.rows_sb, self.columns_sb):
            spin_box.setKeyboardTracking(False)
            spin_box.valueChanged.connect(self._size_changed)

        grid.addWidget(QtWidgets.QLabel("Fits exactly:"), 0, 0)
        grid.addWidget(self.map_dimension_cb, 0, 1)
        grid.addWidget(QtWidgets.QLabel("Rows:"), 1, 0)
        grid.addWidget(self.rows_sb, 1, 1)
        grid.addWidget(QtWidgets.QLabel("Columns:"), 2, 0)
        grid.addWidget(self.columns_sb, 2, 1)

        self.capacity_lbl = QtWidgets.QLabel("")
        self.capacity_lbl.setWordWrap(True)
        grid.addWidget(self.capacity_lbl, 3, 0, 1, 2)
        return group

    def set_dimension_presets(self, dimensions, current):
        """Fills the quick-pick list of grids that hold the points exactly."""
        self._updating = True
        try:
            labels = [f"{rows}x{columns}" for rows, columns in dimensions]
            existing = [
                self.map_dimension_cb.itemText(i)
                for i in range(self.map_dimension_cb.count())
            ]
            if existing != labels:
                self.map_dimension_cb.clear()
                self.map_dimension_cb.addItems(labels)
            if current in dimensions:
                self.map_dimension_cb.setCurrentIndex(dimensions.index(current))
        finally:
            self._updating = False

    def _preset_changed(self, _index):
        if self._updating:
            return
        text = self.map_dimension_cb.currentText()
        if not text:
            return
        rows, columns = (int(value) for value in text.split("x"))
        self.sigGridChanged.emit(rows, columns)

    def _create_orientation_group(self) -> QtWidgets.QWidget:
        group = QtWidgets.QGroupBox("Scan", self)
        box = QtWidgets.QVBoxLayout(group)

        self.snake_cb = QtWidgets.QCheckBox("Serpentine (snake) scan")
        self.snake_cb.setToolTip(
            "Every other row was scanned in the opposite direction.\n"
            "Without this, alternating rows come out mirrored."
        )
        self.transpose_cb = QtWidgets.QCheckBox("Swap fast and slow axis")
        self.flip_horizontal_cb = QtWidgets.QCheckBox("Mirror left/right")
        self.flip_vertical_cb = QtWidgets.QCheckBox("Mirror top/bottom")

        for checkbox, signal in (
            (self.snake_cb, self.sigSnakeChanged),
            (self.transpose_cb, self.sigTransposeChanged),
            (self.flip_horizontal_cb, self.sigFlipHorizontalChanged),
            (self.flip_vertical_cb, self.sigFlipVerticalChanged),
        ):
            checkbox.toggled.connect(
                lambda checked, s=signal: None if self._updating else s.emit(checked)
            )
            box.addWidget(checkbox)
        return group

    def _create_gaps_group(self) -> QtWidgets.QWidget:
        group = QtWidgets.QGroupBox("Dropped frames", self)
        box = QtWidgets.QVBoxLayout(group)

        self.detect_gaps_btn = QtWidgets.QPushButton("Check filename numbering")
        self.detect_gaps_btn.setToolTip(
            "Look for numbers missing from the file names and leave a blank\n"
            "cell for each one. A frame the beamline dropped otherwise shifts\n"
            "every later point into the wrong place."
        )
        self.detect_gaps_btn.clicked.connect(self.sigDetectGapsRequested)
        box.addWidget(self.detect_gaps_btn)

        self.gaps_lbl = QtWidgets.QLabel("")
        self.gaps_lbl.setWordWrap(True)
        box.addWidget(self.gaps_lbl)
        return group

    def _size_changed(self, _value):
        if self._updating:
            return
        self.sigGridChanged.emit(self.rows_sb.value(), self.columns_sb.value())

    def set_state(
        self,
        dimension: tuple[int, int] | None,
        num_points: int,
        snake: bool,
        transpose: bool,
        flip_horizontal: bool,
        flip_vertical: bool,
    ):
        """Shows the layout the map currently has."""
        self._updating = True
        try:
            rows, columns = dimension if dimension else (1, 1)
            self.rows_sb.setValue(int(rows))
            self.columns_sb.setValue(int(columns))
            self.snake_cb.setChecked(snake)
            self.transpose_cb.setChecked(transpose)
            self.flip_horizontal_cb.setChecked(flip_horizontal)
            self.flip_vertical_cb.setChecked(flip_vertical)
        finally:
            self._updating = False

        cells = int(rows) * int(columns)
        blanks = cells - num_points
        if blanks > 0:
            self.capacity_lbl.setText(
                f"{num_points} points in {cells} cells — "
                f"{blanks} blank{'s' if blanks != 1 else ''}"
            )
        elif blanks < 0:
            self.capacity_lbl.setText(
                f"Too small for {num_points} points — needs {-blanks} more cells"
            )
        else:
            self.capacity_lbl.setText(f"{num_points} points, no blanks")

    def set_gaps_message(self, message: str):
        self.gaps_lbl.setText(message)

    def popup_at(self, widget: QtWidgets.QWidget):
        """Shows the popup next to *widget*, wherever it fits on screen.

        The button that opens this sits in the strip along the bottom of the
        map, so dropping straight down would put the popup off the screen
        entirely. It opens upwards instead whenever there is no room below,
        and is kept inside the screen horizontally either way.
        """
        self.adjustSize()
        self.move(self._position_for(widget, self.size()))
        self.show()
        # the frame is only added once shown, so the fit is checked again
        # against the size the popup actually ended up with
        self.move(self._position_for(widget, self.frameGeometry().size()))

    def _position_for(
        self, widget: QtWidgets.QWidget, size: QtCore.QSize
    ) -> QtCore.QPoint:
        below_left = widget.mapToGlobal(QtCore.QPoint(0, widget.height()))
        above_left = widget.mapToGlobal(QtCore.QPoint(0, 0))
        available = self._available_geometry(below_left)

        if below_left.y() + size.height() - 1 <= available.bottom():
            y = below_left.y()
        else:
            y = above_left.y() - size.height()
        # a popup taller than the screen still has to start on it
        y = max(available.top(), min(y, available.bottom() - size.height() + 1))

        x = max(
            available.left(),
            min(below_left.x(), available.right() - size.width() + 1),
        )
        return QtCore.QPoint(x, y)

    @staticmethod
    def _available_geometry(position: QtCore.QPoint) -> QtCore.QRect:
        screen = QtGui.QGuiApplication.screenAt(position)
        if screen is None:
            screen = QtGui.QGuiApplication.primaryScreen()
        return screen.availableGeometry()
