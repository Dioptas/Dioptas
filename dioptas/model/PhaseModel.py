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

from .util import Signal
from .util.jcpds import jcpds, jcpds_reflection
from .util.cif import CifConverter
from .util.HelperModule import calculate_color


class PhaseLoadError(Exception):
    def __init__(self, filename):
        super(PhaseLoadError, self).__init__()
        self.filename = filename

    def __repr__(self):
        return "Could not load {0} as jcpds file".format(self.filename)


class PhaseModel(object):

    num_phases = 0

    def __init__(self):
        super(PhaseModel, self).__init__()
        self.phases = []  # type: list[jcpds]
        self.reflections = []
        self.phase_files = []
        self.phase_colors = []
        self.phase_visible = []

        self.same_conditions = True

        self.phase_added = Signal()
        self.phase_removed = Signal(int)  # phase ind
        self.phase_changed = Signal(int)  # phase ind
        self.phase_reloaded = Signal(int)  # phase ind

        self.reflection_added = Signal(int)
        self.reflection_deleted = Signal(int, int)  # phase index, reflection index

    def add_jcpds(self, filename):
        """
        Adds a jcpds file
        :param filename: filename of the jcpds file
        """
        try:
            jcpds_object = jcpds()
            jcpds_object.load_file(filename)
            self.phase_files.append(filename)
            self.add_jcpds_object(jcpds_object)
        except (ZeroDivisionError, UnboundLocalError, ValueError):
            raise PhaseLoadError(filename)

    def add_cif(self, filename, intensity_cutoff=0.5, minimum_d_spacing=0.5):
        """
        Adds a cif file. Internally it is converted to a jcpds format. It calculates the intensities for all of the
        reflections based on the atomic positions
        :param filename: name of the cif file
        :param intensity_cutoff: all reflections added to the jcpds will have larger intensity in % (0-100)
        :param minimum_d_spacing: all reflections added to the jcpds will have larger d spacing than specified here
        """
        try:
            cif_converter = CifConverter(0.31, minimum_d_spacing, intensity_cutoff)
            jcpds_object = cif_converter.convert_cif_to_jcpds(filename)
            self.phase_files.append(filename)
            self.add_jcpds_object(jcpds_object)
        except (ZeroDivisionError, UnboundLocalError, ValueError) as e:
            print(e)
            raise PhaseLoadError(filename)

    def add_jcpds_object(self, jcpds_object):
        """
        Adds a jcpds object to the phase list.
        :param jcpds_object: jcpds object
        :type jcpds_object: jcpds
        """
        self.phases.append(jcpds_object)
        self.reflections.append([])
        self.phase_colors.append(calculate_color(PhaseModel.num_phases + 9))
        self.phase_visible.append(True)
        PhaseModel.num_phases += 1
        if self.same_conditions and len(self.phases) > 2:
            self.phases[-1].compute_d(self.phases[-2].params['pressure'], self.phases[-2].params['temperature'])
        else:
            self.phases[-1].compute_d()
        self.get_lines_d(-1)
        self.phase_added.emit()
        self.phase_changed.emit(len(self.phases) - 1)

    def save_phase_as(self, ind, filename):
        """
        Save the phase specified with ind as a jcpds file.
        """
        self.phases[ind].save_file(filename)
        self.phase_changed.emit(ind)

    def del_phase(self, ind):
        """
        Deletes the a phase with index ind from the phase list
        """
        del self.phases[ind]
        del self.reflections[ind]
        del self.phase_files[ind]
        del self.phase_colors[ind]
        del self.phase_visible[ind]
        self.phase_removed.emit(ind)

    def reload(self, ind):
        """
        Reloads a phase specified by index ind from it's original source filename
        """
        self.clear_reflections(ind)
        self.phases[ind].reload_file()
        for _ in range(len(self.phases[ind].reflections)):
            self.reflection_added.emit(ind)
        self.get_lines_d(ind)
        self.phase_changed.emit(ind)

    def set_pressure(self, ind, pressure):
        """
        Sets the pressure of a phase with index ind. In case same_conditions is true, all phase pressures will be
        updated.
        """
        if self.same_conditions:
            for j in range(len(self.phases)):
                self._set_pressure(j, pressure)
                self.phase_changed.emit(j)
        else:
            self._set_pressure(ind, pressure)
            self.phase_changed.emit(ind)

    def _set_pressure(self, ind, pressure):
        self.phases[ind].compute_d(pressure=pressure)
        self.get_lines_d(ind)

    def set_temperature(self, ind, temperature):
        """
        Sets the temperature of a phase with index ind. In case same_conditions is true, all phase temperatures will be
        updated.
        """
        if self.same_conditions:
            for j in range(len(self.phases)):
                self._set_temperature(j, temperature)
                self.phase_changed.emit(j)
        else:
            self._set_temperature(ind, temperature)
            self.phase_changed.emit(ind)

    def _set_temperature(self, ind, temperature):
        if self.phases[ind].has_thermal_expansion():
            self.phases[ind].compute_d(temperature=temperature)
            self.get_lines_d(ind)

    def set_pressure_temperature(self, ind, pressure, temperature):
        self.phases[ind].compute_d(temperature=temperature, pressure=pressure)
        self.get_lines_d(ind)
        self.phase_changed.emit(ind)

    def set_param(self, ind, param, value):
        """
        Sets one of the jcpds parameters for the phase with index ind to a certain value. Automatically emits the
        phase_changed signal.
        """

        self.phases[ind].params[param] = value
        self.phases[ind].compute_v0()
        self.phases[ind].compute_d0()
        self.phases[ind].compute_d()
        self.get_lines_d(ind)
        self.phase_changed.emit(ind)

    def set_color(self, ind, color):
        """
        Changes the color of the phase with index ind.
        :param ind: index of phase
        :param color: tuple with RGB values (0-255)
        """
        self.phase_colors[ind] = color
        self.phase_changed.emit(ind)

    def set_phase_visible(self, ind, bool):
        """
        Sets the visible flag (bool) for phase with index ind.
        """
        self.phase_visible[ind] = bool
        self.phase_changed.emit(ind)

    def get_lines_d(self, ind):
        """
        Gets the reflections from the phase with index ind and saves them in a two-dimensional array.
        """
        reflections = self.phases[ind].get_reflections()
        res = np.zeros((len(reflections), 5))
        for i, reflection in enumerate(reflections):
            res[i, 0] = reflection.d
            res[i, 1] = reflection.intensity
            res[i, 2] = reflection.h
            res[i, 3] = reflection.k
            res[i, 4] = reflection.l
        self.reflections[ind] = res
        return res

    def get_phase_line_positions(self, ind, unit, wavelength):
        """
        Gets the line positions of phase with index ind in a specfic unit.
        :param ind: phase index
        :param unit: unit for the positions, possible values: '2th_deg', 'q_A^-1', 'd_A'
        :param wavelength: wavelength in nm
        """
        positions = self.reflections[ind][:, 0]
        if unit == 'q_A^-1' or unit == '2th_deg':
            positions = 2 * \
                        np.arcsin(wavelength / (2 * positions)) * 180.0 / np.pi
            if unit == 'q_A^-1':
                positions = 4 * np.pi / wavelength * \
                            np.sin(positions / 360 * np.pi)
        return positions

    def get_phase_line_intensities(self, ind, positions, pattern, x_range, y_range):
        """
        Gets the phase line intensities scaled to each other for a specific x and y range and also a maximum intensity
        based on a specific pattern.
        :param ind: phase index
        :param positions: positions of the lines
        :param pattern: pattern with what it will be plotted
        :param x_range: x range for which the relative intensities will be calculated
        :param y_range: y range for which the relative intensities will be calculated
        :return: array of intensities, baseline representing the start for the lines
        """
        x, y = pattern.data
        if len(y) != 0:
            y_in_range = y[(x > x_range[0]) & (x < x_range[1])]
            if len(y_in_range) == 0:
                return [], 0
            max_pattern_intensity = np.min([np.max(y_in_range), y_range[1]])
        else:
            max_pattern_intensity = 1

        baseline = y_range[0]
        phase_line_intensities = self.reflections[ind][:, 1]
        # search for reflections within current pattern view range
        phase_line_intensities_in_range = phase_line_intensities[(positions > x_range[0]) & (positions < x_range[1])]

        # rescale intensity based on the lines visible
        if len(phase_line_intensities_in_range):
            scale_factor = (max_pattern_intensity - baseline) / \
                           np.max(phase_line_intensities_in_range)
        else:
            scale_factor = 1
        if scale_factor <= 0:
            scale_factor = 0.01

        phase_line_intensities = scale_factor * self.reflections[ind][:, 1] + baseline
        return phase_line_intensities, baseline

    def get_rescaled_reflections(self, ind, pattern, x_range,
                                 y_range, wavelength, unit='2th_deg'):

        """
        Gets the phase line positions and intensities for a phase with index ind scaled to each other for a specific x
        and y range and also a maximum intensity based on a specific pattern.
        :param ind: phase index
        :param pattern: pattern with what it will be plotted
        :param x_range: x range for which the relative intensities will be calculated
        :param y_range: y range for which the relative intensities will be calculated
        :param wavelength: wavelength in nm
        :param unit: unit for the positions, possible values: '2th_deg', 'q_A^-1', 'd_A'
        :return: a tuple with: (array of positions, array of intensities, baseline value)
        """
        positions = self.get_phase_line_positions(ind, unit, wavelength)

        intensities, baseline = self.get_phase_line_intensities(ind, positions, pattern, x_range, y_range)
        return positions, intensities, baseline

    def add_reflection(self, ind):
        """
        Adds an empty reflection to the reflection table of a phase with index ind
        """
        self.phases[ind].add_reflection()
        self.get_lines_d(ind)
        self.reflection_added.emit(ind)

    def delete_reflection(self, phase_ind, reflection_ind):
        """
        Deletes a reflection from a phase with index phase index.
        """
        self.phases[phase_ind].delete_reflection(reflection_ind)
        self.get_lines_d(phase_ind)
        self.reflection_deleted.emit(phase_ind, reflection_ind)
        self.phase_changed.emit(phase_ind)

    def delete_multiple_reflections(self, phase_ind, indices):
        """
        Deletes multiple reflection from a phase with index phase index.
        """
        indices = np.array(sorted(indices))
        for reflection_ind in indices:
            self.delete_reflection(phase_ind, reflection_ind)
            indices -= 1

    def clear_reflections(self, phase_ind):
        """
        Deletes all reflections from a phase with index phase_ind
        """
        for ind in range(len(self.phases[phase_ind].reflections)):
            self.delete_reflection(phase_ind, 0)

    def update_reflection(self, phase_ind, reflection_ind, reflection):
        """
        Updates the reflection of a phase with a new jcpds_reflection
        :param phase_ind: index of the phase
        :param reflection_ind: index of the refection
        :param reflection: updated reflection
        :type reflection: jcpds_reflection
        """
        self.phases[phase_ind].reflections[reflection_ind] = reflection
        self.phases[phase_ind].params['modified'] = True
        self.phases[phase_ind].compute_d0()
        self.phases[phase_ind].compute_d()
        self.get_lines_d(phase_ind)
        self.phase_changed.emit(phase_ind)

    def reset(self):
        """
        Deletes all phases within the phase model.
        """
        for ind in range(len(self.phases)):
            self.del_phase(0)
