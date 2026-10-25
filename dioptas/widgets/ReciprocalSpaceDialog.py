# SPDX-License-Identifier: MIT
"""Rotatable measured reciprocal-space cloud, linked to detector observations."""

import numpy as np
from qtpy import QtCore, QtWidgets

from .Reciprocal3DWidget import Reciprocal3DWidget
from .ReciprocalSliceDialog import ReciprocalSliceDialog


class ReciprocalSpaceDialog(QtWidgets.QDialog):
    spot_selected = QtCore.Signal(int, int)
    max_points = 50000

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("3D reciprocal space · experimental")
        self.resize(1100, 800)
        self.snapshot = None
        self.selected_track = None
        self._slices = None
        layout = QtWidgets.QVBoxLayout(self)
        controls = QtWidgets.QHBoxLayout()
        self.mode = QtWidgets.QComboBox()
        self.mode.addItems(
            ["Reciprocal q (Å⁻¹, |q| = 1/d)", "Fractional cell indices (h, k, l)"]
        )
        controls.addWidget(self.mode)
        self.observations = QtWidgets.QCheckBox("Individual frame observations")
        controls.addWidget(self.observations)
        self.guides = QtWidgets.QCheckBox("Lattice guides")
        self.guides.setChecked(True)
        self.guides.setToolTip(
            "Integer index reference planes; not a list of allowed reflections."
        )
        controls.addWidget(self.guides)
        controls.addStretch()
        controls.addWidget(QtWidgets.QLabel("Point size"))
        self.point_size = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.point_size.setRange(50, 250)
        self.point_size.setSingleStep(10)
        self.point_size.setPageStep(25)
        self.point_size.setValue(100)
        self.point_size.setFixedWidth(110)
        self.point_size.setAccessibleName("3D point size")
        self.point_size.setToolTip(
            "Adjust point diameter from 50% to 250%. Zoom scaling is retained."
        )
        controls.addWidget(self.point_size)
        self.point_size_value = QtWidgets.QLabel("100%")
        self.point_size_value.setFixedWidth(40)
        controls.addWidget(self.point_size_value)
        self.slice_button = QtWidgets.QPushButton("Slices…")
        controls.addWidget(self.slice_button)
        layout.addLayout(controls)
        views = QtWidgets.QHBoxLayout()
        self.layers = []
        for category, name in enumerate(("Unindexed", "Indexed", "Excluded")):
            check = QtWidgets.QCheckBox(name)
            check.setStyleSheet(f"color: {Reciprocal3DWidget.colours[category]}")
            check.setChecked(True)
            check.toggled.connect(self.redraw)
            views.addWidget(check)
            self.layers.append(check)
        views.addStretch()
        for name, axes in (
            ("hk view", (0, 1)),
            ("hl view", (0, 2)),
            ("kl view", (1, 2)),
        ):
            button = QtWidgets.QPushButton(name)
            button.clicked.connect(
                lambda checked=False, axes=axes: self.canvas.orient_plane(*axes)
            )
            views.addWidget(button)
        self.centre_selected = QtWidgets.QPushButton("Centre selected")
        self.centre_selected.clicked.connect(lambda: self.canvas.centre_selected())
        views.addWidget(self.centre_selected)
        reset = QtWidgets.QPushButton("Reset view")
        reset.clicked.connect(lambda: self.redraw(reset=True))
        views.addWidget(reset)
        layout.addLayout(views)
        self.description = QtWidgets.QLabel()
        self.description.setWordWrap(True)
        layout.addWidget(self.description)
        self.canvas = Reciprocal3DWidget()
        layout.addWidget(self.canvas, 1)
        self.hover = QtWidgets.QLabel(" ")
        layout.addWidget(self.hover)
        help_text = QtWidgets.QLabel(
            "Drag to rotate · wheel to zoom · right/Ctrl-drag to pan · click a spot to select it · double-click to reset.\n"
            "Cyan: indexed · orange: no accepted assignment · grey: excluded from cell search. "
            "Measured positions, with the selected cell’s existing assignments. Orthographic 3D view."
        )
        help_text.setWordWrap(True)
        layout.addWidget(help_text)
        self.canvas.spot_selected.connect(self.spot_selected)
        self.canvas.hovered.connect(self.hover.setText)
        self.mode.currentIndexChanged.connect(lambda: self.redraw(reset=True))
        self.observations.toggled.connect(lambda: self.redraw(reset=True))
        self.guides.toggled.connect(self._guides_changed)
        self.point_size.valueChanged.connect(self._point_size_changed)
        self.slice_button.clicked.connect(self.show_slices)
        self.clear_snapshot()

    def _point_size_changed(self, value):
        self.canvas.point_size_scale = value / 100
        self.point_size_value.setText(f"{value}%")
        self.canvas.update()

    def _guides_changed(self, checked):
        self.canvas.show_guides = checked
        self.canvas.update()

    def set_snapshot(self, snapshot):
        self.snapshot = snapshot
        self.redraw(reset=True)
        if self._slices is not None:
            self._slices.set_snapshot(snapshot)
            self._slices.select_track(self.selected_track)

    def clear_snapshot(self):
        self.snapshot = None
        self.select_track(None)
        self.redraw(reset=True)
        if self._slices is not None:
            self._slices.clear_snapshot()

    def redraw(self, *args, reset=False):
        old_view = (
            self.canvas.rotation.copy(),
            self.canvas.zoom,
            self.canvas.pan.copy(),
            self.canvas.centre.copy(),
            self.canvas.radius,
        )
        if self.snapshot is None:
            coords, tracks, frames, status = (
                np.empty((0, 3)),
                *(np.empty(0, dtype=int) for _ in range(3)),
            )
            basis = np.eye(3)
            self.description.setText(
                "Select a fitted cell to explore reciprocal space."
            )
        else:
            fractional = self.mode.currentIndex() == 1
            coords, tracks, frames, status = self.snapshot.points(
                self.observations.isChecked(), fractional
            )
            total = len(coords)
            visible = np.array([check.isChecked() for check in self.layers])[status]
            ids = np.flatnonzero(visible)
            if len(ids) > self.max_points:
                ids = ids[np.linspace(0, len(ids) - 1, self.max_points, dtype=int)]
            coords, tracks, frames, status = (
                coords[ids],
                tracks[ids],
                frames[ids],
                status[ids],
            )
            basis = np.eye(3) if fractional else self.snapshot.reciprocal_basis
            units = (
                "fractional indices (not rounded)"
                if fractional
                else "Å⁻¹; reciprocal lengths = 1/d"
            )
            self.description.setText(
                f"{self.snapshot.name} · {len(coords):,} / {total:,} measured points shown · {units} · {self.snapshot.omitted_tracks} nonfinite track centres omitted"
            )
        names = ("h", "k", "l") if self.mode.currentIndex() == 1 else ("q1", "q2", "q3")
        self.canvas.set_points(coords, tracks, frames, status, basis, names)
        if not reset:
            (
                self.canvas.rotation,
                self.canvas.zoom,
                self.canvas.pan,
                self.canvas.centre,
                self.canvas.radius,
            ) = old_view
        self.canvas.select_track(self.selected_track)
        self.centre_selected.setEnabled(
            self.selected_track is not None
            and bool(np.any(tracks == self.selected_track))
        )
        self.slice_button.setEnabled(self.snapshot is not None)
        self.hover.setText(" ")
        self.canvas.update()

    def select_track(self, track):
        self.selected_track = track
        self.canvas.select_track(track)
        self.centre_selected.setEnabled(
            track is not None and bool(np.any(self.canvas.tracks == track))
        )
        if self._slices is not None:
            self._slices.select_track(track)

    def show_slices(self):
        if self.snapshot is None:
            return
        if self._slices is None:
            self._slices = ReciprocalSliceDialog(self)
            self._slices.spot_selected.connect(self.spot_selected)
        self._slices.set_snapshot(self.snapshot)
        self._slices.select_track(self.selected_track)
        self._slices.show()
        self._slices.raise_()
