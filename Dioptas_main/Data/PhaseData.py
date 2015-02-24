# -*- coding: utf8 -*-
# Dioptas - GUI program for fast processing of 2D X-ray data
# Copyright (C) 2014  Clemens Prescher (clemens.prescher@gmail.com)
# GSECARS, University of Chicago
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

__author__ = 'Clemens Prescher'

from .HelperModule import Observable
from Data.jcpds import jcpds
import numpy as np

class PhaseLoadError(Exception):
    def __init__(self, filename):
        self.filename = filename

    def __repr__(self):
        return "Could not load {0} as jcpds file".format(self.filename)

class PhaseData(Observable):
    def __init__(self):
        super(PhaseData, self).__init__()
        self.phases = []
        self.reflections = []

    def add_phase(self, filename):
        jcpds_object = jcpds()
        try:
            jcpds_object.load_file(filename)
            self.phases.append(jcpds_object)
            self.reflections.append([])
        except (ZeroDivisionError, UnboundLocalError, ValueError):
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

    def get_rescaled_reflections(self, ind, spectrum, x_range,
                            y_range, wavelength, unit='tth'):
        positions = self.reflections[ind][:, 0]
        if unit is 'q' or unit is 'tth':
            positions = 2 * \
                        np.arcsin(wavelength / (2 * positions)) * 180.0 / np.pi
            if unit == 'q':
                positions = 4 * np.pi / wavelength * \
                            np.sin(positions / 360 * np.pi)

        x, y = spectrum.data
        max_intensity = np.min(
            [np.max(y[np.where((x > x_range[0]) &
                               (x < x_range[1]))]), y_range[1]])
        baseline = y_range[0] + 0.05 * (y_range[1] - y_range[0])
        if baseline < 0:
            baseline = 0

        intensities = self.reflections[ind][:, 1]

        # search for reflections within current spectrum view range
        intensities_for_scaling = intensities[
            np.where((positions > x_range[0]) &
                     (positions < x_range[1]))]
        # rescale intensity based on the lines visible
        if len(intensities_for_scaling):
            scale_factor = (max_intensity - baseline) / \
                           np.max(intensities_for_scaling)
        else:
            scale_factor = 1
        if scale_factor <= 0:
            scale_factor = 0.01

        intensities = scale_factor * self.reflections[ind][:, 1] + baseline
        return positions, intensities, baseline
