"""The position and residual plots use the pattern plot gesture conventions."""

import numpy as np
import pyqtgraph as pg
from qtpy import QtCore
from dioptas.widgets.plot_widgets.PatternMouseViewBox import PatternMouseViewBox


class Event:
    def __init__(self, button=QtCore.Qt.RightButton, modifiers=QtCore.Qt.NoModifier):
        self._button, self._modifiers = button, modifiers
        self.accepted = False

    def button(self):
        return self._button

    def modifiers(self):
        return self._modifiers

    def accept(self):
        self.accepted = True

    def pos(self):
        return pg.Point(100, 100)

    def lastPos(self):
        return pg.Point(95, 96)

    def delta(self):
        return -120


def test_pattern_gestures_and_multiple_populations(qapp):
    view = PatternMouseViewBox()
    widget = pg.PlotWidget(viewBox=view)
    try:
        widget.plot([0, 10], [-2, 3])
        widget.plot([5, 20], [-4, 2])
        widget.addItem(pg.InfiniteLine(pos=0))
        widget.resize(500, 400)
        widget.show()
        qapp.processEvents()
        np.testing.assert_array_equal(view._data_bounds(), [[0, 20], [-4, 3]])
        assert view.state["mouseMode"] == view.RectMode
        view.setRange(xRange=(2, 4), yRange=(-1, 1), padding=0)
        event = Event()
        view.mouseClickEvent(event)
        assert event.accepted
        np.testing.assert_allclose(np.diff(view.viewRange(), axis=1).ravel(), [4, 4])
        view.mouseDragEvent(Event(QtCore.Qt.LeftButton, QtCore.Qt.ControlModifier))
        assert view.viewRange()[0][0] != 1
        view.mouseDoubleClickEvent(Event())
        assert view._covers_data()
        before = np.array(view.viewRange())
        view.wheelEvent(Event())
        np.testing.assert_allclose(view.viewRange(), before, atol=1e-10)
        view.setRange(xRange=(2, 4), yRange=(-1, 1), padding=0)
        view.mouseDoubleClickEvent(
            Event(QtCore.Qt.LeftButton, QtCore.Qt.ControlModifier)
        )
        assert view._covers_data()
    finally:
        widget.close()
