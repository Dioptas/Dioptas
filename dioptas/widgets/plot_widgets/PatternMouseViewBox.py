# SPDX-License-Identifier: MIT
"""Pattern-plot gestures for plots with multiple curves or scatter populations."""

import numpy as np
import pyqtgraph as pg
from qtpy import QtCore


class PatternMouseViewBox(pg.ViewBox):
    """Left rectangle zoom, right/Ctrl-left pan, right-click out, double reset.

    Wheel zoom stops at the complete data range, as in PatternWidget. Bounds
    include every data population; diagnostic reference lines are ignored.
    """

    def __init__(self, **kwargs):
        super().__init__(enableMenu=False, **kwargs)
        self.setMouseMode(self.RectMode)
        self.setToolTip(
            "Left drag: zoom rectangle · right/Ctrl-left drag: pan · "
            "right/Ctrl-left click: zoom out · double right/Ctrl-left click: reset · wheel: zoom"
        )

    @staticmethod
    def _alternate(ev):
        return ev.button() == QtCore.Qt.RightButton or (
            ev.button() == QtCore.Qt.LeftButton
            and bool(ev.modifiers() & QtCore.Qt.ControlModifier)
        )

    def _data_bounds(self):
        arrays = []
        for item in self.addedItems:
            if isinstance(item, pg.PlotDataItem):
                x, y = item.getData()
                if x is not None and y is not None:
                    xy = np.column_stack((x, y))
                    arrays.append(xy[np.isfinite(xy).all(axis=1)])
        arrays = [a for a in arrays if len(a)]
        if not arrays:
            return None
        values = np.concatenate(arrays)
        return np.array([values.min(axis=0), values.max(axis=0)]).T

    def _covers_data(self, factor=1):
        bounds = self._data_bounds()
        return bounds is None or np.all(
            np.diff(np.asarray(self.viewRange()), axis=1) * factor
            >= np.diff(bounds, axis=1)
        )

    def mouseClickEvent(self, ev):
        if self._alternate(ev):
            ev.accept()
            bounds = self._data_bounds()
            # PatternWidget resets when the doubled horizontal span exceeds the curve.
            if (
                bounds is None
                or 2 * np.diff(self.viewRange()[0])[0] > np.diff(bounds[0])[0]
            ):
                self.autoRange()
            else:
                self.scaleBy((2, 2))
            self.sigRangeChangedManually.emit(self.state["mouseEnabled"])
        else:
            super().mouseClickEvent(ev)

    def mouseDoubleClickEvent(self, ev):
        if self._alternate(ev):
            ev.accept()
            self.autoRange()
            self.sigRangeChangedManually.emit(self.state["mouseEnabled"])
        else:
            ev.ignore()

    def mouseDragEvent(self, ev, axis=None):
        if self._alternate(ev):
            ev.accept()
            difference = self.mapToView(ev.lastPos()) - self.mapToView(ev.pos())
            enabled = self.state["mouseEnabled"]
            self.translateBy(
                x=difference.x() if enabled[0] and axis != 1 else 0,
                y=difference.y() if enabled[1] and axis != 0 else 0,
            )
            self.sigRangeChangedManually.emit(enabled)
        else:
            super().mouseDragEvent(ev, axis=axis)

    def wheelEvent(self, ev, axis=None):
        if ev.delta() <= 0 and self._covers_data():
            ev.accept()
            self.autoRange()
        else:
            super().wheelEvent(ev, axis=axis)
