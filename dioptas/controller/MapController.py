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


from dioptas.model import DioptasModel
from dioptas.widgets.MapWidget import MapWidget

from ..widgets.UtilityWidgets import open_files_dialog


class MapController(object):
    def __init__(self, widget: MapWidget, dioptas_model: DioptasModel):
        self.widget = widget
        self.model = dioptas_model
        self.map_model = dioptas_model.map_model

        self.create_signals()

    def create_signals(self):
        self.widget.control_widget.load_btn.clicked.connect(self.load_btn_clicked)

        self.map_model.filenames_changed.connect(self.update_file_list)

    def load_btn_clicked(self):
        filenames = open_files_dialog(
            self.widget,
            "Load image data file(s)",
            self.model.working_directories["image"],
        )
        try:
            self.map_model.create_map(filenames)
        except ValueError as e:
            self.update_file_list()

    def update_file_list(self):
        self.widget.control_widget.file_list.clear()
        self.widget.control_widget.file_list.addItems(self.map_model.filenames)
        self.widget.control_widget.file_list.setCurrentRow(0)
