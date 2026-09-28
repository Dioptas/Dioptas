# SPDX-License-Identifier: MIT
"""A companion pattern plot with shared radial interaction and its own y scale."""

import numpy as np
import pyqtgraph as pg
from qtpy import QtCore

from .PatternWidget import PatternWidget


class SpottinessWidget(PatternWidget):
    def __init__(self, pg_layout, main_pattern):
        self.main_pattern = main_pattern
        super().__init__(pg_layout)
        self.phase_lines = []
        self.pattern_plot.setXLink(main_pattern.pattern_plot)
        self.pattern_plot.enableAutoRange(x=False, y=True)
        main_pattern.pos_line.sigPositionChanged.connect(self._sync_cursor)
        main_pattern.phases_changed.connect(self.sync_phases)
        main_pattern.auto_range_status_changed.connect(self._sync_auto_range)
        self.view_box.sigRangeChangedManually.connect(
            main_pattern.emit_sig_range_changed
        )
        self._sync_cursor()

    def create_graphics(self):
        # The integration display adds/removes this plot when enabled/disabled.
        self.pattern_plot = pg.PlotItem()
        self.pattern_plot.setLabel("left", "Azimuthal std")
        self.pattern_plot.getAxis("bottom").enableAutoSIPrefix(False)
        self.pattern_plot.setMenuEnabled(False)
        self.pattern_plot.buttonsHidden = True
        self.view_box = self.pattern_plot.vb

    def create_main_plot(self):
        self.plot_item = self.pattern_plot.plot(pen="w", connect="finite")

    @property
    def auto_range(self):
        return self.main_pattern.auto_range

    @auto_range.setter
    def auto_range(self, enabled):
        self.main_pattern.auto_range = enabled
        self._sync_auto_range(enabled)

    def _sync_auto_range(self, enabled):
        self.pattern_plot.enableAutoRange(x=False, y=enabled)

    def _sync_cursor(self, *_):
        self.set_pos_line(self.main_pattern.get_pos_line())

    def myMouseClickEvent(self, ev):
        ev.accept()
        if ev.button() == QtCore.Qt.LeftButton and not (
            ev.modifiers() & QtCore.Qt.ControlModifier
        ):
            point = self.view_box.mapSceneToView(ev.scenePos())
            self.mouse_left_clicked.emit(point.x(), point.y())
        else:
            # The normal pattern handler implements a factor-two zoom out,
            # clamped to the full pattern range, and supports Ctrl-click too.
            x, _ = self.plot_item.getData()
            if x is not None and len(x):
                super().myMouseClickEvent(ev)

    def myMouseDoubleClickEvent(self, ev):
        ev.accept()
        super().myMouseDoubleClickEvent(ev)

    def myMouseDragEvent(self, ev, axis=None):
        self.auto_range = False
        super().myMouseDragEvent(ev, axis)

    def myWheelEvent(self, ev, axis=None, *args):
        x, _ = self.plot_item.getData()
        if x is not None and len(x):
            super().myWheelEvent(ev, axis, *args)

    def sync_phases(self):
        """Mirror reflection positions and visibility as full-height lines."""
        if self.pattern_plot.scene() is None:
            return
        phases = self.main_pattern.phases
        while len(self.phase_lines) > len(phases):
            for line in self.phase_lines.pop():
                self.pattern_plot.removeItem(line)
        while len(self.phase_lines) < len(phases):
            self.phase_lines.append([])
        for phase, lines in zip(phases, self.phase_lines):
            while len(lines) > len(phase.line_items):
                self.pattern_plot.removeItem(lines.pop())
            while len(lines) < len(phase.line_items):
                line = pg.InfiniteLine(movable=False)
                line.setZValue(-5)
                self.pattern_plot.addItem(line, ignoreBounds=True)
                lines.append(line)
            for index, (source, line) in enumerate(zip(phase.line_items, lines)):
                x, _ = source.getData()
                position = x[0] if x is not None and len(x) else np.nan
                line.setVisible(
                    phase.visible
                    and phase.line_visible[index]
                    and bool(np.isfinite(position))
                )
                if np.isfinite(position):
                    line.setValue(position)
                line.setPen(phase.pen)
