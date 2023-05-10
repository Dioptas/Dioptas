# -*- coding: utf-8 -*-
# Dioptas - GUI program for fast processing of 2D X-ray diffraction data
# Principal author: Clemens Prescher (clemens.prescher@gmail.com)
# Copyright (C) 2014-2019 GSECARS, University of Chicago, USA
# Copyright (C) 2015-2018 Institute for Geology and Mineralogy, University of Cologne, Germany
# Copyright (C) 2019-2020 DESY, Hamburg, Germany
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import numpy as np
from qtpy import QtWidgets
from pyqtgraph.opengl import GLSurfacePlotItem
from pyqtgraph.opengl import GLViewWidget, GLGridItem
from pyqtgraph import GraphicsLayoutWidget

from .HistogramLUTItem import HistogramLUTItem


class SurfaceWidget(QtWidgets.QWidget):
    iteration_name = ''

    def __init__(self):
        super(SurfaceWidget, self).__init__()

        self.lut_pg_layout = GraphicsLayoutWidget()
        self.pg_layout = GLViewWidget()
        self.pg_layout.setCameraPosition(distance=3)
        self.surf_view_item = None
        self.pressed_key = None
        self.show_range = np.array([0.0, 1.0])
        self.show_scale = np.array([2., 2., 1.])
        self.g_translate = 0
        self.g_pos = 0
        self.marker = 0
        self.marker_color = [1, 0, 0]
        self.marker_size = 5
        self.data = None

        self.create_graphics()

        self._lut_lo = QtWidgets.QVBoxLayout()
        self._lut_lo.setContentsMargins(0, 0, 0, 0)
        self._lut_lo.addWidget(self.lut_pg_layout)

        self._lut_w = QtWidgets.QWidget()
        self._lut_w.setMaximumHeight(80)
        self._lut_w.setLayout(self._lut_lo)

        self._layout = QtWidgets.QVBoxLayout()
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)
        self._layout.addWidget(self._lut_w)
        self._layout.addWidget(self.pg_layout)

        self.img_histogram_LUT_horizontal = HistogramLUTItem()
        self.img_histogram_LUT_horizontal.gradient.loadPreset('jet')

        self.img_histogram_LUT_horizontal.sigLevelsChanged.connect(self.update_color)
        self.img_histogram_LUT_horizontal.sigLevelChangeFinished.connect(self.update_color)
        self.img_histogram_LUT_horizontal.sigLookupTableChanged.connect(self.update_color)
        self.img_histogram_LUT_horizontal.sigResetClicked.connect(self._reset_clicked)

        self.lut_pg_layout.addItem(self.img_histogram_LUT_horizontal, 0, 1)

        self.setLayout(self._layout)

    def _reset_clicked(self):
        if self.data is not None:
            self.img_histogram_LUT_horizontal.setLevels(
                np.nanmin(self.data), np.nanmax(self.data)
            )

    def create_graphics(self):
        self.back_grid = GLGridItem()
        self.back_grid.rotate(90, 0, 1, 0)
        self.back_grid.setSize(1, 1, 0)
        self.back_grid.setSpacing(1, 0.1, 1)
        self.back_grid.setDepthValue(10)  # draw grid after surfaces since they may be translucent
        self.pg_layout.addItem(self.back_grid)

        self.base_grid = GLGridItem()
        self.base_grid.setSize(26, 4000, 0)
        self.base_grid.setSpacing(1, 100, 1)
        self.base_grid.setDepthValue(10)  # draw grid after surfaces since they may be translucent
        self.pg_layout.addItem(self.base_grid)

        # self.axis = CustomAxis(self.pg_layout)

        self.surf_view_item = GLSurfacePlotItem(z=np.array([[0]]),
                                                colors=np.array([[0, 0, 0, 0]]),
                                                smooth=False)
        self.surf_view_item.setGLOptions('translucent')
        self.pg_layout.addItem(self.surf_view_item)

    def update_color(self):
        if self.data is not None:
            colors = self.get_colors(self.data).reshape(-1, 4)
            self.surf_view_item.setData(z=self.data, colors=colors)

    def plot_surface(self, data, start, step):
        self.g_pos = int((self.g_translate - start) / step)
        colors = self.get_colors(data).reshape(-1, 4)

        abs_range = self.show_range * (np.nanmax(data) - np.nanmin(data)) + np.nanmin(data)
        self.data = np.copy(data)
        self.data[self.data > abs_range[1]] = abs_range[1]
        self.data[self.data < abs_range[0]] = abs_range[0]

        self.surf_view_item.setData(z=self.data, colors=colors)

        self.img_histogram_LUT_horizontal.imageChanged(img_data=self.data)
        self.img_histogram_LUT_horizontal.setLevels(np.nanmin(self.data), np.nanmax(self.data))

        # self.axis.setSize(*self.show_scale)

        self.update_grids(data)

    def update_grids(self, data):
        self.back_grid.setSize(np.nanmax(data), self.data.shape[1], 0)
        self.base_grid.setSize(self.data.shape[0], self.data.shape[1], 0)

        scale = [self.show_scale[0] / data.shape[0],
                 self.show_scale[1] / data.shape[1],
                 self.show_scale[2] / np.nanmax(data)]

        self.surf_view_item.resetTransform()
        self.surf_view_item.translate(-data.shape[0] / 2., -data.shape[1] / 2., 0)
        self.surf_view_item.scale(*scale, local=False)

        self.back_grid.resetTransform()
        self.back_grid.rotate(90, 0, 1, 0)
        self.back_grid.translate(-data.shape[0] / 2, 0, np.nanmax(data) / 2. + np.nanmin(data))
        self.back_grid.scale(*scale, local=False)

        self.base_grid.resetTransform()
        self.base_grid.translate(0, 0, np.nanmin(data))
        self.base_grid.scale(*scale, local=False)

        # self.axis.setSize(*self.show_scale)
        # self.axis.translate(-data.shape[0] / 2, 0, np.nanmax(data) / 2. + np.nanmin(data))
        # self.axis.diff = [self.show_scale[0] * self.g_pos / data.shape[0], 0, 0]

    def get_colors(self, data):
        lut = self.img_histogram_LUT_horizontal.gradient.getLookupTable(256) / 256.

        level = self.img_histogram_LUT_horizontal.getExpLevels()
        # int_data = ((data - np.nanmin(data)) / (np.nanmax(data) - np.nanmin(data)) * 255).astype(int)
        min = np.nanmin(data)
        if level[0] > 1:
            min = level[0]
        int_data = ((data - min) / (level[1] - min) * 255).astype(int)
        int_data[int_data > 255] = 255
        int_data[int_data < 0] = 0
        int_data = np.nan_to_num(int_data)
        int_data[int_data < 0] = 0
        colors_rgb = lut[int_data]
        colors = np.ones((colors_rgb.shape[0], colors_rgb.shape[1], 4))
        colors[..., :3] = colors_rgb

        colors[:, int(self.marker):int(self.marker) + self.marker_size, :3] = self.marker_color
        colors[self.g_pos, :, :3] = self.marker_color
        return colors
