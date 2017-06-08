# -*- coding: utf8 -*-
# Dioptas - GUI program for fast processing of 2D X-ray data
# Copyright (C) 2015  Clemens Prescher (clemens.prescher@gmail.com)
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

import numpy as np

from .util import jcpds
from .util.cif import CifConverter


class PhaseLoadError(Exception):
    def __init__(self, filename):
        super(PhaseLoadError, self).__init__()
        self.filename = filename

    def __repr__(self):
        return "Could not load {0} as jcpds file".format(self.filename)


class PhaseModel(object):
    def __init__(self):
        super(PhaseModel, self).__init__()
        self.phases = []
        self.reflections = []

    def add_jcpds(self, filename):
        try:
            jcpds_object = jcpds()
            jcpds_object.load_file(filename)
            self.phases.append(jcpds_object)
            self.reflections.append([])
        except (ZeroDivisionError, UnboundLocalError, ValueError):
            raise PhaseLoadError(filename)

    def add_cif(self, filename, intensity_cutoff=0.5, minimum_d_spacing=0.5):
        try:
            cif_converter = CifConverter(0.31, minimum_d_spacing, intensity_cutoff)
            jcpds_object = cif_converter.convert_cif_to_jcpds(filename)
            self.phases.append(jcpds_object)
            self.reflections.append([])
        except (ZeroDivisionError, UnboundLocalError, ValueError) as e:
            print(e)
            raise PhaseLoadError(filename)

    def del_phase(self, ind):
        del self.phases[ind]
        del self.reflections[ind]

    def set_pressure(self, ind, pressure):
        self.phases[ind].compute_d(pressure=pressure)
        self.get_lines_d(ind)

    def set_temperature(self, ind, temperature):
        self.phases[ind].compute_d(temperature=temperature)
        self.get_lines_d(ind)

    def set_pressure_temperature(self, ind, pressure, temperature):
        self.phases[ind].compute_d(temperature=temperature, pressure=pressure)
        self.get_lines_d(ind)

    def set_pressure_all(self, P):
        for phase in self.phases:
            phase.compute_d(pressure=P)

    def get_lines_d(self, ind):
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

    def set_temperature_all(self, T):
        for phase in self.phases:
            phase.compute_d(temperature=T)

    def update_all_phases(self):
        for ind in range(len(self.phases)):
            self.get_lines_d(ind)

    def get_phase_line_positions(self, ind, unit, wavelength):
        positions = self.reflections[ind][:, 0]
        if unit is 'q' or unit is 'tth':
            positions = 2 * \
                        np.arcsin(wavelength / (2 * positions)) * 180.0 / np.pi
            if unit == 'q':
                positions = 4 * np.pi / wavelength * \
                            np.sin(positions / 360 * np.pi)
        return positions

    def get_phase_line_intensities(self, ind, positions, pattern, x_range, y_range):
        x, y = pattern.data
        if len(y) is not 0:
            y_in_range = y[(x > x_range[0]) & (x < x_range[1])]
            if len(y_in_range) is 0:
                return [], 0
            max_spectrum_intensity = np.min([np.max(y_in_range), y_range[1]])
        else:
            max_spectrum_intensity = 1

        baseline = y_range[0]
        phase_line_intensities = self.reflections[ind][:, 1]
        # search for reflections within current spectrum view range
        phase_line_intensities_in_range = phase_line_intensities[(positions > x_range[0]) & (positions < x_range[1])]

        # rescale intensity based on the lines visible
        if len(phase_line_intensities_in_range):
            scale_factor = (max_spectrum_intensity - baseline) / \
                           np.max(phase_line_intensities_in_range)
        else:
            scale_factor = 1
        if scale_factor <= 0:
            scale_factor = 0.01

        phase_line_intensities = scale_factor * self.reflections[ind][:, 1] + baseline
        return phase_line_intensities, baseline

    def get_rescaled_reflections(self, ind, pattern, x_range,
                                 y_range, wavelength, unit='tth'):
        positions = self.get_phase_line_positions(ind, unit, wavelength)

        intensities, baseline = self.get_phase_line_intensities(ind, positions, pattern, x_range, y_range)
        return positions, intensities, baseline
