# SPDX-License-Identifier: MIT
"""Linked, non-modal reciprocal slices without a platform-specific 3D backend."""

import numpy as np
import pyqtgraph as pg
from qtpy import QtCore, QtWidgets

from .plot_widgets.PatternMouseViewBox import PatternMouseViewBox


class ReciprocalSliceDialog(QtWidgets.QDialog):
    spot_selected = QtCore.Signal(int, int)  # track, frame (-1 for a linked centre)
    planes = ((0, 1, 2), (0, 2, 1), (1, 2, 0))
    max_points_per_slice = 50000

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Reciprocal space · experimental")
        self.resize(1350, 720)
        self.snapshot = None
        self.selected_track = None
        layout = QtWidgets.QVBoxLayout(self)
        controls = QtWidgets.QHBoxLayout()
        self.mode = QtWidgets.QComboBox()
        self.mode.addItems(
            ["Fractional cell indices (h, k, l)", "Reciprocal q (Å⁻¹, |q| = 1/d)"]
        )
        self.mode.setMinimumWidth(260)
        controls.addWidget(self.mode)
        self.observations = QtWidgets.QCheckBox("Individual frame observations")
        self.observations.setToolTip(
            "Show each detected frame position separately to inspect the spread within linked spots."
        )
        controls.addWidget(self.observations)
        controls.addWidget(QtWidgets.QLabel("Full slice thickness"))
        self.thickness = QtWidgets.QDoubleSpinBox()
        self.thickness.setRange(0.001, 100)
        self.thickness.setDecimals(3)
        self.thickness.setValue(0.3)
        self.thickness.setSingleStep(0.05)
        self.thickness.setSuffix(" r.l.u.")
        self.thickness.setToolTip(
            "Total width along the hidden coordinate; both ± half-width boundaries are included."
        )
        controls.addWidget(self.thickness)
        self.grid_enabled = QtWidgets.QCheckBox("Integer index grid")
        self.grid_enabled.setChecked(True)
        self.grid_enabled.setToolTip(
            "Reference integer indices, not predicted or allowed reflections."
        )
        controls.addWidget(self.grid_enabled)
        controls.addStretch(1)
        layout.addLayout(controls)
        layers = QtWidgets.QHBoxLayout()
        self.centres, self.centre_labels = [], []
        for name in ("l", "k", "h"):
            label = QtWidgets.QLabel(f"{name} =")
            spin = QtWidgets.QDoubleSpinBox()
            spin.setRange(-1e5, 1e5)
            spin.setDecimals(3)
            spin.setSingleStep(1)
            layers.addWidget(label)
            layers.addWidget(spin)
            self.centre_labels.append(label)
            self.centres.append(spin)
            spin.valueChanged.connect(self.redraw)
        self.centre_selected = QtWidgets.QPushButton("Centre slices on selected spot")
        self.centre_selected.clicked.connect(self.centre_on_selection)
        layers.addWidget(self.centre_selected)
        reset = QtWidgets.QPushButton("Reset views")
        reset.clicked.connect(lambda: self.redraw(reset=True))
        layers.addWidget(reset)
        layout.addLayout(layers)
        self.description = QtWidgets.QLabel()
        self.description.setWordWrap(True)
        layout.addWidget(self.description)
        self.graphics = pg.GraphicsLayoutWidget()
        layout.addWidget(self.graphics, 1)
        self.plots, self.populations, self.grids, self.highlights = [], [], [], []
        for column in range(3):
            plot = self.graphics.addPlot(
                row=0, col=column, viewBox=PatternMouseViewBox()
            )
            plot.setAspectLocked(True)
            plot.getAxis("bottom").enableAutoSIPrefix(False)
            plot.getAxis("left").enableAutoSIPrefix(False)
            populations = []
            for colour in ("#ffac45", "#48d8eb", "#969da6"):
                item = plot.plot(
                    [],
                    [],
                    pen=None,
                    symbol="o",
                    symbolSize=7,
                    symbolBrush=colour,
                    symbolPen=pg.mkPen("k", width=0.7),
                )
                item.scatter.sigClicked.connect(self._clicked)
                populations.append(item)
            for item, z in zip(populations, (1, 2, 0)):
                item.setZValue(z)
            grid = pg.PlotCurveItem(
                pen=pg.mkPen("#666e79", width=0.7), connect="finite"
            )
            grid.setZValue(-5)
            plot.addItem(grid, ignoreBounds=True)
            highlight = plot.plot(
                [],
                [],
                pen=None,
                symbol="o",
                symbolSize=16,
                symbolBrush=None,
                symbolPen=pg.mkPen("#ff55dd", width=2.5),
            )
            highlight.scatter.setAcceptedMouseButtons(QtCore.Qt.NoButton)
            highlight.setZValue(10)
            self.plots.append(plot)
            self.populations.append(populations)
            self.grids.append(grid)
            self.highlights.append(highlight)
        self.selection_note = QtWidgets.QLabel(
            "Click a point to select its spot in the image and position table."
        )
        self.selection_note.setWordWrap(True)
        layout.addWidget(self.selection_note)
        legend = QtWidgets.QLabel(
            "Cyan: indexed · orange: no accepted assignment · grey: excluded from cell search. "
            "Membership is the selected cell's frozen assignment set. Empty grid points do not establish absences."
        )
        legend.setWordWrap(True)
        layout.addWidget(legend)
        self.mode.currentIndexChanged.connect(self._mode_changed)
        self.observations.toggled.connect(self.redraw)
        self.thickness.valueChanged.connect(self.redraw)
        self.grid_enabled.toggled.connect(self.redraw)
        self.clear_snapshot()

    def set_snapshot(self, snapshot):
        self.snapshot = snapshot
        self.redraw(reset=True)

    def clear_snapshot(self):
        self.snapshot = None
        self.selected_track = None
        self.description.setText(
            "Select a ranked cell to explore measured reciprocal positions."
        )
        self.centre_selected.setEnabled(False)
        self.selection_note.setText(
            "Click a point to select its spot in the image and position table."
        )
        for plot in self.plots:
            plot.setTitle("No reciprocal data")
        for groups, grid, highlight in zip(
            self.populations, self.grids, self.highlights
        ):
            for item in groups:
                item.scatter.hide()
                item.scatter.clear()
                item.setData([], [], data=[])
            grid.setData([], [])
            highlight.scatter.hide()
            highlight.scatter.clear()
            highlight.setData([], [])

    def _mode_changed(self, *_):
        fractional = self.mode.currentIndex() == 0
        self.grid_enabled.setEnabled(fractional)
        self.thickness.setValue(0.3 if fractional else 0.03)
        self.thickness.setSingleStep(0.05 if fractional else 0.01)
        self.thickness.setSuffix(" r.l.u." if fractional else " Å⁻¹")
        for label, spin, name in zip(
            self.centre_labels,
            self.centres,
            ("l", "k", "h") if fractional else ("q3", "q2", "q1"),
        ):
            label.setText(f"{name} =")
            blocker = QtCore.QSignalBlocker(spin)
            spin.setValue(0)
            spin.setSingleStep(1 if fractional else 0.1)
            del blocker
        self.redraw(reset=True)

    def _points(self):
        return self.snapshot.points(
            self.observations.isChecked(), self.mode.currentIndex() == 0
        )

    def redraw(self, *_, reset=False):
        if self.snapshot is None:
            return
        coords, tracks, frames, status = self._points()
        names = ("h", "k", "l") if self.mode.currentIndex() == 0 else ("q1", "q2", "q3")
        counts = []
        for i, (x, y, normal) in enumerate(self.planes):
            visible = np.flatnonzero(
                abs(coords[:, normal] - self.centres[i].value())
                <= self.thickness.value() / 2
            )
            count = len(visible)
            if count > self.max_points_per_slice:
                visible = visible[
                    np.linspace(0, count - 1, self.max_points_per_slice, dtype=int)
                ]
            counts.append(
                f"{count}" if len(visible) == count else f"{len(visible)}/{count}"
            )
            for category, item in enumerate(self.populations[i]):
                item.scatter.hide()
                item.scatter.clear()
                rows = visible[status[visible] == category]
                item.setData(
                    coords[rows, x],
                    coords[rows, y],
                    data=[(int(tracks[j]), int(frames[j])) for j in rows],
                )
            plot = self.plots[i]
            plot.setTitle(
                f"{names[x]}–{names[y]} · {names[normal]}={self.centres[i].value():g} · {counts[-1]} points"
            )
            units = "" if self.mode.currentIndex() == 0 else "Å⁻¹"
            plot.setLabel("bottom", names[x], units=units)
            plot.setLabel("left", names[y], units=units)
            self._draw_grid(i, coords, x, y)
            if reset:
                plot.autoRange()
        kind = (
            "frame observations"
            if self.observations.isChecked()
            else "linked spot centres"
        )
        convention = (
            "Fractional indices; use reciprocal-q mode for Cartesian distances and angles."
            if self.mode.currentIndex() == 0
            else "Sample-frame reciprocal vectors, |q| = 1/d."
        )
        self.description.setText(
            f"{self.snapshot.name} · {len(coords)} {kind} · "
            f"{self.snapshot.omitted_tracks} tracks lack finite centres. "
            f"{convention} Slice boundaries include ± half the stated thickness."
        )
        self.select_track(self.selected_track)

    def _draw_grid(self, i, coords, x, y):
        grid = self.grids[i]
        grid.setData([], [])
        if (
            self.mode.currentIndex() != 0
            or not self.grid_enabled.isChecked()
            or not len(coords)
        ):
            return
        lo = np.floor(coords[:, [x, y]].min(axis=0)) - 1
        hi = np.ceil(coords[:, [x, y]].max(axis=0)) + 1
        xs, ys = [], []
        for axis in (0, 1):
            step = max(1, int(np.ceil((hi[axis] - lo[axis]) / 80)))
            for value in np.arange(lo[axis], hi[axis] + 1, step):
                a, b = (0, 1) if axis == 0 else (1, 0)
                segment = np.empty((2, 2))
                segment[:, a] = value
                segment[:, b] = (lo[b], hi[b])
                xs.extend([*segment[:, 0], np.nan])
                ys.extend([*segment[:, 1], np.nan])
        grid.setData(xs, ys)

    def select_track(self, track):
        self.selected_track = track
        self.centre_selected.setEnabled(track is not None and self.snapshot is not None)
        if self.snapshot is None:
            return
        coords, tracks, _, _ = self._points()
        present = track is not None and np.any(tracks == track)
        self.centre_selected.setEnabled(bool(present))
        shown = 0
        for i, (x, y, normal) in enumerate(self.planes):
            rows = (tracks == track) & (
                abs(coords[:, normal] - self.centres[i].value())
                <= self.thickness.value() / 2
            )
            self.highlights[i].scatter.hide()
            self.highlights[i].scatter.clear()
            self.highlights[i].setData(coords[rows, x], coords[rows, y])
            shown += int(np.count_nonzero(rows))
        self.selection_note.setText(
            "Click a point to select its spot in the image and position table."
            if track is None
            else f"Selected spot {track + 1} · {shown} points in the current slices. "
            "Use Centre slices on selected spot to bring it into view."
        )

    def centre_on_selection(self):
        if self.snapshot is None or self.selected_track is None:
            return
        coords, tracks, _, _ = self._points()
        rows = coords[tracks == self.selected_track]
        if not len(rows):
            return
        point = rows.mean(axis=0)
        for spin, (_, _, normal) in zip(self.centres, self.planes):
            blocker = QtCore.QSignalBlocker(spin)
            spin.setValue(float(point[normal]))
            del blocker
        self.redraw(reset=True)

    def _clicked(self, _item, points, event=None):
        if event is not None and PatternMouseViewBox._alternate(event):
            event.ignore()
            return
        if not points:
            return

        def distance(p):
            delta = p.pos() - event.pos()
            return delta.x() ** 2 + delta.y() ** 2

        point = min(points, key=distance) if event is not None else points[0]
        track, frame = point.data()
        self.spot_selected.emit(track, frame)
