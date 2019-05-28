# -*- coding: utf-8 -*-
# Dioptas - GUI program for fast processing of 2D X-ray diffraction data
# Principal author: Clemens Prescher (clemens.prescher@gmail.com)
# Copyright (C) 2014-2019 GSECARS, University of Chicago, USA
# Copyright (C) 2015-2018 Institute for Geology and Mineralogy, University of Cologne, Germany
# Copyright (C) 2019 DESY, Hamburg, Germany
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

from ....model.util.calc import convert_units
from ....model.util.HelperModule import get_partial_index

# imports for type hinting in PyCharm -- DO NOT DELETE
from ....model.DioptasModel import DioptasModel
from ....widgets.integration import IntegrationWidget


class PhaseInPatternController(object):
    """
    PhaseInPatternController handles all the interaction between the phases and the pattern view.
    """

    def __init__(self, integration_widget, dioptas_model):
        """
        :param integration_widget: Reference to an IntegrationWidget
        :param dioptas_model: reference to DioptasModel object

        :type integration_widget: IntegrationWidget
        :type dioptas_model: DioptasModel
        """
        self.model = dioptas_model
        self.integration_widget = integration_widget
        self.pattern_widget = integration_widget.pattern_widget

        self.connect()

    def connect(self):
        self.model.phase_model.phase_added.connect(self.add_phase_plot)
        self.model.phase_model.phase_removed.connect(self.pattern_widget.del_phase)

        self.model.phase_model.phase_changed.connect(self.update_phase_lines)
        self.model.phase_model.phase_changed.connect(self.update_phase_legend)
        self.model.phase_model.phase_changed.connect(self.update_phase_color)
        self.model.phase_model.phase_changed.connect(self.update_phase_visible)

        self.model.phase_model.reflection_added.connect(self.reflection_added)
        self.model.phase_model.reflection_deleted.connect(self.reflection_deleted)

        # pattern signals
        self.pattern_widget.view_box.sigRangeChangedManually.connect(self.update_all_phase_lines)
        self.pattern_widget.pattern_plot.autoBtn.clicked.connect(self.update_all_phase_lines)
        self.model.pattern_changed.connect(self.pattern_data_changed)

    def add_phase_plot(self):
        """
        Adds a phase to the Pattern Plot
        """
        axis_range = self.pattern_widget.pattern_plot.viewRange()
        x_range = axis_range[0]
        y_range = axis_range[1]
        positions, intensities, baseline = \
            self.model.phase_model.get_rescaled_reflections(
                -1, self.model.pattern,
                x_range, y_range,
                self.model.calibration_model.wavelength * 1e10,
                self.get_unit())

        self.pattern_widget.add_phase(self.model.phase_model.phases[-1].name,
                                      positions,
                                      intensities,
                                      baseline,
                                      self.model.phase_model.phase_colors[-1])

    def update_phase_lines(self, ind, axis_range=None):
        """
        Updates the intensities of a specific phase with index ind.
        :param ind: Index of the phase
        :param axis_range: list/tuple of visible x_range and y_range -- ((x_min, x_max), (y_min, y_max))
        """
        if axis_range is None:
            axis_range = self.pattern_widget.view_box.viewRange()

        x_range = axis_range[0]
        y_range = axis_range[1]
        positions, intensities, baseline = self.model.phase_model.get_rescaled_reflections(
            ind, self.model.pattern,
            x_range, y_range,
            self.model.calibration_model.wavelength * 1e10,
            self.get_unit()
        )

        self.pattern_widget.update_phase_intensities(ind, positions, intensities, y_range[0])

    def update_all_phase_lines(self):
        for ind in range(len(self.model.phase_model.phases)):
            self.update_phase_lines(ind)

    def pattern_data_changed(self):
        """
        Function is called after the pattern data has changed.
        """
        self.pattern_widget.update_phase_line_visibilities()

    def update_phase_legend(self, ind):
        name = self.model.phase_model.phases[ind].name
        parameter_str = ''
        pressure = self.model.phase_model.phases[ind].params['pressure']
        temperature = self.model.phase_model.phases[ind].params['temperature']
        if pressure != 0:
            parameter_str += '{:0.2f} GPa '.format(pressure)
        if temperature != 0 and temperature != 298 and temperature is not None:
            parameter_str += '{:0.2f} K '.format(temperature)
        self.pattern_widget.rename_phase(ind, parameter_str + name)

    def update_phase_color(self, ind):
        self.pattern_widget.set_phase_color(ind, self.model.phase_model.phase_colors[ind])

    def update_phase_visible(self, ind):
        if self.model.phase_model.phase_visible[ind]:
            self.pattern_widget.show_phase(ind)
        else:
            self.pattern_widget.hide_phase(ind)

    def reflection_added(self, ind):
        self.pattern_widget.phases[ind].add_line()
        self.update_phase_lines(ind)

    def reflection_deleted(self, phase_ind, reflection_ind):
        self.pattern_widget.phases[phase_ind].delete_line(reflection_ind)

    def get_unit(self):
        """
        returns the unit currently selected in the GUI
                possible values: 'tth', 'q', 'd'
        """
        if self.integration_widget.pattern_tth_btn.isChecked():
            return 'tth'
        elif self.integration_widget.pattern_q_btn.isChecked():
            return 'q'
        elif self.integration_widget.pattern_d_btn.isChecked():
            return 'd'
