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


from dioptas.model.OverlayModel import OverlayModel
from dioptas.widgets.plot_widgets import PatternWidget


class OverlayInPatternController(object):
    def __init__(self, pattern_widget: PatternWidget, overlay_model: OverlayModel):
        self.model = overlay_model
        self.pattern_widget = pattern_widget

        self.connect()

    def connect(self):
        self.model.overlay_added.connect(self.overlay_added)
        self.model.overlay_removed.connect(self.overlay_removed)
        self.model.overlay_changed.connect(self.overlay_changed)

    def overlay_added(self):
        overlay = self.model.get_overlay(len(self.model.overlays) - 1)
        color = self.model.get_overlay_color(len(self.model.overlays) - 1)
        if overlay is not None:
            self.pattern_widget.add_overlay(overlay, color)

    def overlay_removed(self, index: int):
        self.pattern_widget.remove_overlay(index)

    def overlay_changed(self, index: int):
        overlay = self.model.get_overlay(index)
        if overlay is not None:
            self.pattern_widget.update_overlay(index, overlay)
