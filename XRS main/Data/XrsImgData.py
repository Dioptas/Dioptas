__author__ = 'Clemens Prescher'

import numpy as np
import fabio
import pyFAI
import pyFAI.utils
import matplotlib.pyplot as plt
from XrsHelper import Observable, rotate_matrix_p90, rotate_matrix_m90
import os
from stat import S_ISREG, ST_CTIME, ST_MODE
import time


class XrsImgData(Observable):
    def __init__(self):
        super(XrsImgData, self).__init__()

        self.img_data = None
        self.integrator = None

        self.tth = None
        self.I = None

        self.file_iteration_mode = 'number'

        self.img_transformations = []

    def load_file(self, filename):
        self.filename = filename
        try:
            self.img_data_fabio = fabio.open(filename)
            self.img_data = self.img_data_fabio.data[::-1]
        except TypeError:
            self.img_data = plt.imread(filename)
            if len(self.img_data.shape) > 2:
                self.img_data = np.average(self.img_data, 2)
        self.perform_img_transformations()
        self.integrate_img()
        self.notify()

    def load_next_file(self):
        next_file_name = FileNameIterator.get_next_filename(self.filename, self.file_iteration_mode)
        if next_file_name is not None:
            self.load_file(next_file_name)

    def load_previous_file(self):
        previous_file_name = FileNameIterator.get_previous_filename(self.filename, self.file_iteration_mode)
        if previous_file_name is not None:
            self.load_file(previous_file_name)

    def set_calibration_file(self, filename):
        self.integrator = pyFAI.load(filename)

    def integrate_img(self):
        if self.integrator is not None:
            self.tth, self.I = self.integrator.integrate1d(
                self.img_data, 1000, unit='2th_deg', method="lut_ocl")

    def get_spectrum(self):
        return self.tth, self.I

    def get_img_data(self):
        return self.img_data

    def rotate_img_p90(self):
        self.img_data = rotate_matrix_p90(self.img_data)
        self.img_transformations.append(rotate_matrix_p90)
        self.notify()

    def rotate_img_m90(self):
        self.img_data = rotate_matrix_m90(self.img_data)
        self.img_transformations.append(rotate_matrix_m90)
        self.notify()

    def flip_img_horizontally(self):
        self.img_data = np.fliplr(self.img_data)
        self.img_transformations.append(np.fliplr)
        self.notify()

    def flip_img_vertically(self):
        self.img_data = np.flipud(self.img_data)
        self.img_transformations.append(np.flipud)
        self.notify()

    def reset_img_transformations(self):
        for transformation in reversed(self.img_transformations):
            if transformation == rotate_matrix_p90:
                self.img_data = rotate_matrix_m90(self.img_data)
            elif transformation == rotate_matrix_m90:
                self.img_data = rotate_matrix_p90(self.img_data)
            else:
                self.img_data = transformation(self.img_data)
        self.img_transformations = []
        self.notify()

    def perform_img_transformations(self):
        for transformation in self.img_transformations:
            self.img_data = transformation(self.img_data)


class FileNameIterator(object):
    @staticmethod
    def get_next_filename(filepath, mode='number'):
        complete_path = os.path.abspath(filepath)
        directory, file_str = os.path.split(complete_path)
        filename, file_type_str = file_str.split('.')

        if mode == 'number':
            file_number_str = FileNameIterator._get_ending_number(filename)
            file_number = int(file_number_str)
            file_base_str = filename[:-len(file_number_str)]

            format_str = '0' + str(len(file_number_str)) + 'd'
            number_str = ("{0:" + format_str + '}').format(file_number + 1)
            new_file_name = file_base_str + number_str + '.' + file_type_str
            new_complete_path = os.path.join(directory, new_file_name)
            if os.path.exists(new_complete_path):
                return new_complete_path
        elif mode == 'date':
            files_list = os.listdir(directory)
            files = []
            for file in files_list:
                if file.endswith(file_type_str):
                    files.append(file)

            paths = (os.path.join(directory, file) for file in files)
            entries = ((os.stat(path), path) for path in paths)

            entries = list(sorted(((stat[ST_CTIME], path)
                       for stat, path in entries if S_ISREG(stat[ST_MODE]))))

            for ind, entry in enumerate(entries):
                if entry[1] == complete_path:
                    try:
                        return entries[ind+1][1]
                    except IndexError:
                        return None


    @staticmethod
    def get_previous_filename(filepath, mode='number'):
        complete_path = os.path.abspath(filepath)
        directory, file_str = os.path.split(complete_path)
        filename, file_type_str = file_str.split('.')

        file_number_str = FileNameIterator._get_ending_number(filename)
        file_number = int(file_number_str)
        file_base_str = filename[:-len(file_number_str)]


        if mode=='number':
            format_str = '0' + str(len(file_number_str)) + 'd'
            number_str = ("{0:" + format_str + '}').format(file_number - 1)
            new_file_name = file_base_str + number_str + '.' + file_type_str

            new_complete_path = os.path.join(directory, new_file_name)
            if os.path.exists(new_complete_path):
                return new_complete_path

            format_str = '0' + str(len(file_number_str) - 1) + 'd'
            number_str = ("{0:" + format_str + '}').format(file_number - 1)
            new_file_name = file_base_str + number_str + '.' + file_type_str

            new_complete_path = os.path.join(directory, new_file_name)
            if os.path.exists(new_complete_path):
                return new_complete_path

        elif mode == 'date':
            files_list = os.listdir(directory)
            files = []
            for file in files_list:
                if file.endswith(file_type_str):
                    files.append(file)

            paths = (os.path.join(directory, file) for file in files)
            entries = ((os.stat(path), path) for path in paths)

            entries = list(sorted(((stat[ST_CTIME], path)
                       for stat, path in entries if S_ISREG(stat[ST_MODE]))))

            for ind, entry in enumerate(entries):
                if entry[1] == complete_path and ind is not 0:
                    return entries[ind-1][1]

    @staticmethod
    def _get_ending_number(basename):
        res = ''
        for char in reversed(basename):
            if char.isdigit():
                res += char
            else:
                return res[::-1]


def test():
    filename = '../ExampleData/test_999.tif'
    print FileNameIterator.get_next_filename(filename)

    filename = '../ExampleData/test_002.tif'
    print FileNameIterator.get_previous_filename(filename)

    filename = '../ExampleData/test_008.tif'
    print FileNameIterator.get_next_filename(filename, 'date')


if __name__ == '__main__':
    test()