# SPDX-License-Identifier: MIT
"""Observed/predicted residual diagnostics with explicit training/held-out colours."""

import numpy as np
import pyqtgraph as pg
from qtpy import QtWidgets
from .plot_widgets.PatternMouseViewBox import PatternMouseViewBox


class PredictionResidualDialog(QtWidgets.QDialog):
    def __init__(self, result, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Crystal position residuals · experimental")
        self.resize(1150, 850)
        layout = QtWidgets.QVBoxLayout(self)
        note = QtWidgets.QLabel(
            "Residual = calculated − measured. Grey: initial model; "
            "blue: refined training; orange: refined held-out. Each point is one linked reflection centre. "
            "Omega uses measured exposure-midpoint centroids; these plots do not measure intensity."
        )
        note.setWordWrap(True)
        layout.addWidget(note)
        self.graphics = pg.GraphicsLayoutWidget()
        layout.addWidget(self.graphics)
        self.plots = []
        fit = result.refinement
        before = fit.initial_predictions.values - fit.observed
        after = fit.predictions.values - fit.observed
        specs = [
            (2, 0, "Measured omega (°)", "Δx (px)"),
            (0, 0, "Measured x (px)", "Δx (px)"),
            (2, 1, "Measured omega (°)", "Δy (px)"),
            (1, 1, "Measured y (px)", "Δy (px)"),
            (2, 2, "Measured omega (°)", "Δomega (°)"),
            (0, 2, "Measured x (px)", "Δomega (°)"),
        ]
        for i, (x, y, xlabel, ylabel) in enumerate(specs):
            plot = self.graphics.addPlot(
                row=i // 2, col=i % 2, viewBox=PatternMouseViewBox()
            )
            plot.setLabel("bottom", xlabel)
            plot.setLabel("left", ylabel)
            plot.addItem(pg.InfiniteLine(pos=0, angle=0, pen=pg.mkPen("#707780")))
            valid = fit.eligible & np.isfinite(before[:, y])
            plot.plot(
                fit.observed[valid, x],
                before[valid, y],
                pen=None,
                symbol="o",
                symbolSize=5,
                symbolBrush=None,
                symbolPen="#9299a1",
            )
            for training, color in [(True, "#47a8ed"), (False, "#ffac45")]:
                mask = (
                    fit.eligible & (fit.training == training) & np.isfinite(after[:, y])
                )
                plot.plot(
                    fit.observed[mask, x],
                    after[mask, y],
                    pen=None,
                    symbol="o",
                    symbolSize=5,
                    symbolBrush=color,
                    symbolPen=None,
                )
            self.plots.append(plot)
