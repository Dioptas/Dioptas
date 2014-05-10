__author__ = 'Clemens Prescher'

import numpy as np
import os
from stat import S_ISREG, ST_CTIME, ST_MODE


class Observable(object):
    def __init__(self):
        self.observer = []
        self.notification = True

    def subscribe(self, function):
        self.observer.append(function)

    def unsubscribe(self, function):
        try:
            self.observer.remove(function)
        except ValueError:
            pass

    def notify(self):
        if self.notification:
            for observer in self.observer:
                observer()
    def turn_off_notification(self):
        self.notification = False

    def turn_on_notification(self):
        self.notification = True


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
        elif mode == 'time':
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
                        return entries[ind + 1][1]
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

        if mode == 'number':
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

        elif mode == 'time':
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
                    return entries[ind - 1][1]

    @staticmethod
    def _get_ending_number(basename):
        res = ''
        for char in reversed(basename):
            if char.isdigit():
                res += char
            else:
                return res[::-1]


def rotate_matrix_m90(matrix):
    return np.rot90(matrix, -1)


def rotate_matrix_p90(matrix):
    return np.rot90(matrix)


def get_base_name(filename):
    str = os.path.basename(filename)
    return str.split('.')[:-1][0]