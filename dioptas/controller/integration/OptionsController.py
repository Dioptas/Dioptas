# -*- coding: utf8 -*-
# Dioptas - GUI program for fast processing of 2D X-ray data
# Copyright (C) 2017  Clemens Prescher (clemens.prescher@gmail.com)
# Institute for Geology and Mineralogy, University of Cologne
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


# imports for type hinting in PyCharm -- DO NOT DELETE
from ...widgets.integration import IntegrationWidget
from ...model.DioptasModel import DioptasModel


class OptionsController(object):
    """
    IntegrationPatternController handles all the interaction from the IntegrationView with the pattern data.
    It manages the auto integration of image files to  in addition to pattern browsing and changing of units
    (2 Theta, Q, A)
    """

    def __init__(self, widget, dioptas_model):
        """
        :param widget: Reference to an IntegrationWidget
        :param dioptas_model: reference to DioptasModel object

        :type widget: IntegrationWidget
        :type dioptas_model: DioptasModel
        """

        self.integration_widget = widget
        self.options_widget = self.integration_widget.integration_control_widget.integration_options_widget

        self.model = dioptas_model

        self.connect_signals()

    def connect_signals(self):
        self.options_widget.correct_solid_angle_cb.stateChanged.connect(self.correct_solid_angle_cb_clicked)
        self.model.configuration_selected.connect(self.update_gui)
        self.model.pattern_changed.connect(self.update_gui)

        self.options_widget.cake_azimuth_points_sb.valueChanged.connect(self.cake_azimuth_points_changed)
        self.options_widget.cake_azimuth_min_txt.editingFinished.connect(self.cake_azimuth_range_changed)
        self.options_widget.cake_azimuth_max_txt.editingFinished.connect(self.cake_azimuth_range_changed)

    def correct_solid_angle_cb_clicked(self):
        self.model.current_configuration.correct_solid_angle = self.options_widget.correct_solid_angle_cb.isChecked()

    def update_gui(self):
        self.options_widget.blockSignals(True)
        self.options_widget.correct_solid_angle_cb.setChecked(self.model.current_configuration.correct_solid_angle)
        self.options_widget.bin_count_txt.setText("{:1.0f}".format(self.model.calibration_model.num_points))

        self.options_widget.cake_azimuth_points_sb.setValue(self.model.current_configuration.cake_azimuth_points)
        self.options_widget.cake_azimuth_min_txt.setText(
            '{}'.format(self.model.current_configuration.cake_azimuth_range[0]))
        self.options_widget.cake_azimuth_max_txt.setText(
            '{}'.format(self.model.current_configuration.cake_azimuth_range[1]))
        self.options_widget.blockSignals(False)

    def cake_azimuth_range_changed(self):
        range_min = float(self.options_widget.cake_azimuth_min_txt.text())
        range_max = float(self.options_widget.cake_azimuth_max_txt.text())
        self.model.current_configuration.cake_azimuth_range = (range_min, range_max)

    def cake_azimuth_points_changed(self):
        self.model.current_configuration.cake_azimuth_points = int(
            self.options_widget.cake_azimuth_points_sb.value())


