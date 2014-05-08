__author__ = 'Clemens Prescher'
import numpy as np
import os
from HelperClasses import Observable, FileNameIterator


class SpectrumData(Observable):
    def __init__(self):
        Observable.__init__(self)
        self.spectrum = Spectrum()
        self.overlays = []
        self.phases = []

        self.file_iteration_mode = 'number'

    def set_spectrum(self, x, y, filename=''):
        self.spectrum_filename = filename
        self.spectrum = Spectrum(x, y, name=os.path.basename(filename).split('.')[:-1][0])
        self.notify()

    def load_spectrum(self, filename):
        self.spectrum_filename = filename
        self.spectrum.load(filename)
        self.notify()

    def load_next(self):
        next_file_name = FileNameIterator.get_next_filename(self.spectrum_filename, self.file_iteration_mode)
        if next_file_name is not None:
            self.load_spectrum(next_file_name)

    def load_previous(self):
        previous_file_name = FileNameIterator.get_previous_filename(self.spectrum_filename, self.file_iteration_mode)
        if previous_file_name is not None:
            self.load_spectrum(previous_file_name)

    def add_overlay(self, x, y, name=''):
        self.overlays.append(Spectrum(x, y, name))
        self.notify()

    def add_overlay_file(self, filename):
        self.overlays.append(Spectrum())
        self.overlays[-1].load(filename)
        self.notify()

    def del_overlay(self, ind):
        self.overlays.remove(self.overlays[ind])
        self.notify()

    def set_file_iteration_mode(self, mode):
        """
        The file iteration_mode determines how to browse between files in a specific folder:
        possible values:
        'number'    - browsing by ending number (like in file_001.txt)
        'time'      - browsing by data of creation
        """
        if not (mode is 'number' or mode is 'time'):
            return -1
        else:
            self.mode = mode

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

    def load(self, filename, skiprows=0):
        try:
            data = np.loadtxt(filename, skiprows=skiprows)
            self._x = data.T[0]
            self._y = data.T[1]
            self.name = os.path.basename(filename).split('.')[:-1][0]

        except ValueError:
            print 'Wrong data format for spectrum file!'
            return -1

    def save(self, filename, header=''):
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
    my_spectrum.save('test.txt')


if __name__ == '__main__':
    test()

