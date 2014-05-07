__author__ = 'Clemens Prescher'
import numpy as np
import os


class SpectrumData(object):
    def __init__(self):
        self.spectrum = Spectrum()
        self.overlays = []
        self.phases = []

    def set_spectrum(self, x, y, name=''):
        self.spectrum = Spectrum(x, y, name=name)

    def load_spectrum(self, filename):
        self.spectrum.load_file(filename)

    def add_overlay(self, x, y, name=''):
        self.overlays.append(Spectrum(x, y, name))

    def add_overlay_file(self, filename):
        self.overlays.append(Spectrum())
        self.overlays[-1].load_file(filename)


    def del_overlay(self, ind):
        self.overlays.remove(self.overlays[ind])

    def add_phase(self):
        pass

    def del_phase(self, ind):
        pass


class Spectrum(object):
    def __init__(self, x=None, y=None, name=''):
        if x is None:
            self._x = np.linspace(0, 30, 100)
        else:
            self._x = x
        if y is None:
            self._y = np.zeros(self._x.shape)
        else:
            self._y = y
        self.name = name
        self.offset = 0
        self._scaling = 1

    def load_file(self, file_name, skiprows=0):
        try:
            data = np.loadtxt(file_name, skiprows=skiprows)
            self._x = data.T[0]
            self._y = data.T[1]
            self.name = os.path.basename(file_name).split('.')[:-1][0]

        except ValueError:
            print 'Wrong data format for spectrum file!'
            return -1

    def save_file(self, filename, header=''):
        data = np.dstack((self._x, self._y))
        np.savetxt(filename, data[0], header=header)

    @property
    def data(self):
        return self._x, self._y * self._scaling + self.offset

    @data.setter
    def data(self, (x, y)):
        self._x = x
        self._y = y
        self.scaling = 1
        self.offset = 0

    @property
    def scaling(self):
        return self._scaling

    @scaling.setter
    def scaling(self, value):
        if value < 0:
            self._scaling = 0
        else:
            self._scaling = value


def test():
    my_spectrum = Spectrum()
    my_spectrum.save_file('test.txt')


if __name__ == '__main__':
    test()

