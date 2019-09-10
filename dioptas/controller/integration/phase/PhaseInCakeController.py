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

from ....model.util.HelperModule import get_partial_index

# imports for type hinting in PyCharm -- DO NOT DELETE
from ....model.DioptasModel import DioptasModel
from ....widgets.integration import IntegrationWidget
from ....widgets.plot_widgets.ImgWidget import IntegrationImgWidget


class PhaseInCakeController(object):
    """
    PhaseInCakeController handles all the interaction between the phase controls and the plotted lines in the cake view.
    """

    def __init__(self, integration_widget, dioptas_model):
        """
        :param integration_widget: Reference to an IntegrationWidget
        :param dioptas_model: reference to DioptasModel object

        :type integration_widget: IntegrationWidget
        :type dioptas_model: DioptasModel
        """
        self.model = dioptas_model
        self.phase_model = self.model.phase_model
        self.integration_widget = integration_widget
        self.cake_view_widget = integration_widget.integration_image_widget.cake_view  # type: IntegrationImgWidget

        self.connect()

    def connect(self):
        self.phase_model.phase_added.connect(self.add_phase_plot)
        self.model.phase_model.phase_removed.connect(self.cake_view_widget.del_cake_phase)

        self.phase_model.phase_changed.connect(self.update_phase_lines)
        self.phase_model.phase_changed.connect(self.update_phase_color)
        self.phase_model.phase_changed.connect(self.update_phase_visible)

        self.phase_model.reflection_added.connect(self.reflection_added)
        self.phase_model.reflection_deleted.connect(self.reflection_deleted)

    def get_phase_position_and_intensities(self, ind, clip=True):
        """
        Obtains the positions and intensities for lines of a phase with an index ind within the cake view.

        No clipping is used for the first call to add the CakePhasePlot to the ImgWidget. Subsequent calls are used with
        clipping. Thus, only lines within the cake_tth are returned. The visibility of each line is then estimated in
        the ImgWidget based on the length of the clipped and not clipped lists.

        :param ind: the index of the phase
        :param clip: whether or not the lists should be clipped. Clipped means that lines which have positions larger
                     than the
        :return: line_positions, line_intensities
        """
        if self.model.cake_tth is None:
            cake_tth = self.model.calibration_model.tth
        else:
            cake_tth = self.model.cake_tth
        reflections_tth = self.phase_model.get_phase_line_positions(ind, 'tth',
                                                                    self.model.calibration_model.wavelength * 1e10)
        reflections_intensities = [reflex[1] for reflex in self.phase_model.reflections[ind]]

        cake_line_positions = []
        cake_line_intensities = []

        for ind, tth in enumerate(reflections_tth):
            pos_ind = get_partial_index(cake_tth, tth)
            if pos_ind is not None:
                cake_line_positions.append(pos_ind + 0.5)
                cake_line_intensities.append(reflections_intensities[ind])
            elif clip is False:
                cake_line_positions.append(0)
                cake_line_intensities.append(reflections_intensities[ind])

        return cake_line_positions, cake_line_intensities

    def add_phase_plot(self):
        cake_line_positions, cake_line_intensities = self.get_phase_position_and_intensities(-1, False)

        self.cake_view_widget.add_cake_phase(cake_line_positions, cake_line_intensities,
                                             self.phase_model.phase_colors[-1])

    def update_phase_lines(self, ind):
        cake_line_positions, cake_line_intensities = self.get_phase_position_and_intensities(ind)
        self.cake_view_widget.update_phase_intensities(ind, cake_line_positions, cake_line_intensities)

    def update_phase_color(self, ind):
        self.cake_view_widget.set_cake_phase_color(ind, self.model.phase_model.phase_colors[ind])

    def update_phase_visible(self, ind):
        if self.phase_model.phase_visible[ind] and self.integration_widget.img_mode == 'Cake' and \
                self.integration_widget.img_phases_btn.isChecked():
            self.cake_view_widget.show_cake_phase(ind)
        else:
            self.cake_view_widget.hide_cake_phase(ind)

    def reflection_added(self, ind):
        self.cake_view_widget.phases[ind].add_line()

    def reflection_deleted(self, phase_ind, reflection_ind):
        self.cake_view_widget.phases[phase_ind].delete_line(reflection_ind)
