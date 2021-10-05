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

import os
from ..widgets.UtilityWidgets import save_file_dialog

# imports for type hinting in PyCharm -- DO NOT DELETE
from ..widgets.ConfigurationWidget import ConfigurationWidget
from ..model.DioptasModel import DioptasModel


class ConfigurationController(object):
    """
    Deals with all the signal handling and model upgrades related to be using multiple configurations.
    """

    def __init__(self, configuration_widget, dioptas_model, controllers=()):
        """
        :type configuration_widget: ConfigurationWidget
        :type dioptas_model: DioptasModel
        """
        self.widget = configuration_widget
        self.model = dioptas_model
        self.controllers = controllers

        self.update_configuration_widget()

        self.create_signals()

    def create_signals(self):
        self.widget.add_configuration_btn.clicked.connect(self.model.add_configuration)
        self.widget.remove_configuration_btn.clicked.connect(self.model.remove_configuration)

        self.widget.configuration_selected.connect(self.model.select_configuration)

        self.model.configuration_added.connect(self.update_configuration_widget)
        self.model.configuration_removed.connect(self.update_configuration_widget)
        self.model.configuration_selected.connect(self.configuration_selected)

        self.widget.next_file_btn.clicked.connect(self.load_next_file)
        self.widget.previous_file_btn.clicked.connect(self.load_previous_file)

        self.widget.next_folder_btn.clicked.connect(self.load_next_folder)
        self.widget.previous_folder_btn.clicked.connect(self.load_previous_folder)

        self.widget.factor_txt.editingFinished.connect(self.factor_txt_changed)

        self.widget.combine_patterns_btn.clicked.connect(self.combine_patterns_btn_clicked)
        self.widget.saved_combined_patterns_btn.clicked.connect(self.save_combined_patterns_btn_clicked)
        self.widget.combine_cakes_btn.clicked.connect(self.combine_cakes_btn_clicked)

    def update_configuration_widget(self):
        self.widget.update_configuration_btns(
            configurations=self.model.configurations,
            cur_ind=self.model.configuration_ind
        )

    def configuration_selected(self):
        self.widget.factor_txt.setText(str(self.model.img_model.factor))

    def combine_patterns_btn_clicked(self):
        self.model.combine_patterns = self.widget.combine_patterns_btn.isChecked()

    def save_combined_patterns_btn_clicked(self):
        img_filename, _ = os.path.splitext(os.path.basename(self.model.img_model.filename))
        filename = save_file_dialog(
            self.widget, "Save Combined Pattern Data.",
            os.path.join(self.model.working_directories['pattern'],
                         img_filename + '_combined.dat'), ('.dat'))

        if filename != '':
            self.model.save_combined_pattern(filename)

    def combine_cakes_btn_clicked(self):
        self.model.combine_cakes = self.widget.combine_cakes_btn.isChecked()

    def factor_txt_changed(self):
        self.model.img_model.factor = float(str(self.widget.factor_txt.text()))

    def load_next_file(self):
        pos = int(str(self.widget.file_iterator_pos_txt.text()))
        self.model.next_image(pos)

    def load_previous_file(self):
        pos = int(str(self.widget.file_iterator_pos_txt.text()))
        self.model.previous_image(pos)

    def load_next_folder(self):
        self.model.next_folder(mec_mode=bool(self.widget.mec_cb.isChecked()))

    def load_previous_folder(self):
        self.model.previous_folder(mec_mode=bool(self.widget.mec_cb.isChecked()))
