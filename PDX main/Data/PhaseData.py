__author__ = 'Clemens Prescher'

from HelperModule import Observable
from Data.jcpds import jcpds
import numpy as np


class PhaseData(Observable):
    def __init__(self):
        super(PhaseData, self).__init__()
        self.phases = []

    def add_phase(self, filename):
        self.phases.append(jcpds())
        self.phases[-1].read_file(filename)

    def del_phase(self, ind):
        self.phases.remove(self.phases[ind])

    def set_pressure(self, ind, P):
        self.phases[ind].compute_d(pressure=P)

    def set_temperature(self, ind, T):
        self.phases[ind].compute_d(temperature=T)

    def set_pressure_all(self, P):
        for phase in self.phases:
            phase.compute_d(pressure=P)

    def get_lines_d(self, ind, max_intensity=None):
        reflections = self.phases[ind].get_reflections()
        res = np.zeros((len(reflections), 5))
        for i, reflection in enumerate(reflections):
            res[i, 0] = reflection.d
            res[i, 1] = reflection.intensity
            res[i, 2] = reflection.h
            res[i, 3] = reflection.k
            res[i, 4] = reflection.l
        return res

    def set_temperature_all(self, T):
        for phase in self.phases:
            phase.compute_d(temperature=T)

    def get_reflections_data(self, ind, wavelength, spectrum, unit='tth'):
        """
        transforms the reflections data to fit to wavelength and spectrum data limits. It normalizes the Intensities
        to the maximum of the spectrum and only returns reflection lines within the x range of the spectrum
        Inputs:
            ind         -   ind of the phase
            wavelength  -   wavelength in nanometer
            spectrum    -   spectrum class to which the reflections should be adjusted
            unit        -   either 'tth' or 'Q' for obtaining positions in either unit

        output:
            (n,5) array -   whereby the n is the number of reflections found
                columns:
                    1       -   position in specified unit
                    2       -   intensity
                    3,4,5   -   h,k,l
        """
        #get data
        x, y = spectrum.data
        reflections = self.get_lines_d(ind)

        #calculate intensities

        reflections[:, 0] = 2 * np.arcsin(wavelength / (2 * reflections[:, 0])) * 180.0 / np.pi
        if unit == 'Q':
            reflections[:, 0] = 4 * np.pi / wavelength * np.sin(reflections[:, 0] / 2)

        reflections[:, 1] = reflections[:, 1] / np.max(reflections[:, 1]) * np.max(y)

        #search for reflections within spectrum range
        return reflections[np.where((reflections[:, 0] > np.min(x)) & (reflections[:, 0] < np.max(x)))]


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


