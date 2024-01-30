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

from functools import partial

from qtpy import QtWidgets, QtCore

from .CustomWidgets import LabelAlignRight, HorizontalSpacerItem, CheckableFlatButton, FlatButton, NumberTextField, \
    IntegerTextField, VerticalLine, SaveIconButton


class ConfigurationWidget(QtWidgets.QWidget):
    configuration_selected = QtCore.Signal(int)  # configuration index

    def __init__(self, parent=None):
        super(ConfigurationWidget, self).__init__(parent)
        self.create_widgets()
        self.create_layout()
        self.style_widgets()

    def create_widgets(self):
        self.configuration_lbl = LabelAlignRight("Configuration:")

        self.configuration_btns = []
        self.configurations_btn_widget = QtWidgets.QWidget()
        self.configuration_btn_group = QtWidgets.QButtonGroup()

        self.add_configuration_btn = FlatButton("+")
        self.remove_configuration_btn = FlatButton("-")

        self.factor_lbl = LabelAlignRight("Factor: ")
        self.factor_txt = NumberTextField("1")

        self.file_lbl = LabelAlignRight("File: ")
        self.previous_file_btn = FlatButton("<")
        self.next_file_btn = FlatButton(">")
        self.file_iterator_pos_lbl = LabelAlignRight(" Pos: ")
        self.file_iterator_pos_txt = IntegerTextField("1")

        self.folder_lbl = LabelAlignRight(" Folder:")
        self.next_folder_btn = FlatButton(">")
        self.previous_folder_btn = FlatButton("<")
        self.mec_cb = QtWidgets.QCheckBox("MEC")

        self.combine_patterns_btn = CheckableFlatButton("Combine Patterns")
        self.combine_cakes_btn = CheckableFlatButton("Combine Cakes")
        self.saved_combined_patterns_btn = SaveIconButton()
        self.saved_combined_patterns_btn.setToolTip("Save combined pattern")

    def create_layout(self):
        self.main_layout = QtWidgets.QHBoxLayout()
        self.main_layout.addWidget(self.configuration_lbl)
        self.main_layout.addWidget(self.add_configuration_btn)
        self.main_layout.addWidget(self.remove_configuration_btn)
        self.main_layout.addWidget(self.configurations_btn_widget)
        self.main_layout.addSpacerItem(HorizontalSpacerItem())
        self.main_layout.addWidget(self.file_lbl)
        self.main_layout.addWidget(self.previous_file_btn)
        self.main_layout.addWidget(self.next_file_btn)
        self.main_layout.addWidget(self.file_iterator_pos_lbl)
        self.main_layout.addWidget(self.file_iterator_pos_txt)
        self.main_layout.addWidget(VerticalLine())
        self.main_layout.addWidget(self.folder_lbl)
        self.main_layout.addWidget(self.previous_folder_btn)
        self.main_layout.addWidget(self.next_folder_btn)
        self.main_layout.addWidget(self.mec_cb)
        self.main_layout.addSpacerItem(HorizontalSpacerItem())
        self.main_layout.addWidget(self.factor_lbl)
        self.main_layout.addWidget(self.factor_txt)
        self.main_layout.addSpacerItem(QtWidgets.QSpacerItem(20, 0, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Minimum))
        self.main_layout.addWidget(self.combine_patterns_btn)
        self.main_layout.addWidget(self.saved_combined_patterns_btn)
        self.main_layout.addWidget(self.combine_cakes_btn)
        self.setLayout(self.main_layout)

        self.configurations_btn_layout = QtWidgets.QHBoxLayout(self.configurations_btn_widget)

    def style_widgets(self):
        self.main_layout.setSpacing(6)
        self.main_layout.setContentsMargins(6, 0, 6, 0)
        self.configurations_btn_layout.setSpacing(0)
        self.configurations_btn_layout.setContentsMargins(0, 0, 0, 0)

        btns = [self.add_configuration_btn, self.remove_configuration_btn, self.next_file_btn, self.previous_file_btn,
                self.next_folder_btn, self.previous_folder_btn, self.saved_combined_patterns_btn]

        for btn in btns:
            btn.setFixedSize(25, 25)

        self.saved_combined_patterns_btn.setIconSize(QtCore.QSize(13, 13))

    def update_configuration_btns(self, configurations, cur_ind):
        for btn in self.configuration_btns:
            self.configuration_btn_group.removeButton(btn)
            self.configurations_btn_layout.removeWidget(btn)
            btn.deleteLater()  # somehow needs tobe deleted, otherwise remains in the button group

        self.configuration_btns = []

        for ind, configuration in enumerate(configurations):
            new_button = CheckableFlatButton(str(ind + 1))
            new_button.setFixedSize(25, 25)
            self.configuration_btn_group.addButton(new_button)
            self.configuration_btns.append(new_button)
            self.configurations_btn_layout.addWidget(new_button)
            if ind == cur_ind:
                new_button.setChecked(True)
            new_button.clicked.connect(partial(self.configuration_selected.emit, ind))
