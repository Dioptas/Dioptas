# -*- coding: utf8 -*-
#     Py2DeX - GUI program for fast processing of 2D X-ray data
#     Copyright (C) 2014  Clemens Prescher (clemens.prescher@gmail.com)
#     GSECARS, University of Chicago
#
#     This program is free software: you can redistribute it and/or modify
#     it under the terms of the GNU General Public License as published by
#     the Free Software Foundation, either version 3 of the License, or
#     (at your option) any later version.
#
#     This program is distributed in the hope that it will be useful,
#     but WITHOUT ANY WARRANTY; without even the implied warranty of
#     MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#     GNU General Public License for more details.
#
#     You should have received a copy of the GNU General Public License
#     along with this program.  If not, see <http://www.gnu.org/licenses/>.

__author__ = 'Clemens Prescher'

from HelperModule import Observable
from Data.jcpds import jcpds
import numpy as np


class PhaseData(Observable):
    def __init__(self):
        super(PhaseData, self).__init__()
        self.phases = []
        self.reflections = []

    def add_phase(self, filename):
        self.phases.append(jcpds())
        self.phases[-1].read_file(filename)
        self.reflections.append([])

    def del_phase(self, ind):
        self.phases.remove(self.phases[ind])
        self.reflections.remove(self.reflections[ind])

    def set_pressure(self, ind, P):
        self.phases[ind].compute_d(pressure=P)
        self.get_lines_d(ind)

    def set_temperature(self, ind, T):
        self.phases[ind].compute_d(temperature=T)
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

    def rescale_reflections(self, ind, spectrum, x_range, y_range, wavelength, unit='tth'):
        positions = self.reflections[ind][:, 0]
        if unit is 'q' or unit is 'tth':
            positions = 2 * np.arcsin(wavelength / (2 * positions)) * 180.0 / np.pi
            if unit == 'Q':
                positions = 4 * np.pi / wavelength * np.sin(positions / 2)

        x, y = spectrum.data
        max_intensity = np.min([np.max(y[np.where((x > x_range[0]) & (x < x_range[1]))]), y_range[1]])
        baseline = y_range[0] + 0.05 * (y_range[1] - y_range[0])
        if baseline < 0:
            baseline = 0
        #search for reflections within spectrum range
        intensities = self.reflections[ind][:, 1]
        intensities_for_scaling = intensities[np.where((positions > x_range[0]) &
                                                       (positions < x_range[1]))]
        #rescale intensity
        if len(intensities_for_scaling):
            scale_factor = (max_intensity - baseline) / np.max(intensities_for_scaling)
        else:
            scale_factor = 1
        if scale_factor <= 0:
            scale_factor = 0.01

        intensities = scale_factor * self.reflections[ind][:, 1] + baseline
        return positions, intensities, baseline


def test_volume_calculation():
    import numpy as np
    import matplotlib.pyplot as plt

    phase_data = PhaseData()
    phase_data.add_phase('../ExampleData/jcpds/dac_user/au_Anderson.jcpds')
    phase_data.set_temperature_all(2000)
    pressure = np.linspace(0, 100)
    v = []
    for P in pressure:
        phase_data.set_pressure_all(P)
        v.append(phase_data.phases[0].v)
        try:
            print phase_data.phases[0].mod_pressure
        except AttributeError:
            pass
    v = np.array(v)

    plt.plot(pressure, v)
    plt.show()


def test_d_spacing_calculation():
    import numpy as np
    import matplotlib.pyplot as plt

    phase_data = PhaseData()
    phase_data.add_phase('../ExampleData/jcpds/dac_user/au_Anderson.jcpds')
    wavelength = 0.3344

    reflections = phase_data.get_lines_d(0)
    tth = 2 * np.arcsin(wavelength / (2 * reflections[:, 0])) / np.pi * 180
    int = reflections[:, 1] / np.max(reflections[:, 1])

    for i, v in enumerate(tth):
        plt.axvline(v, ymax=int[i])

    phase_data.set_pressure_all(30)
    reflections = phase_data.get_lines_d(0)
    tth = 2 * np.arcsin(wavelength / (2 * reflections[:, 0])) / np.pi * 180
    int = reflections[:, 1] / np.max(reflections[:, 1])

    for i, v in enumerate(tth):
        plt.axvline(v, ymax=int[i], color='r')
    plt.show()


if __name__ == '__main__':
    test_d_spacing_calculation()


