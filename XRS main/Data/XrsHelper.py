__author__ = 'Clemens Prescher'

import numpy as np

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


def rotate_matrix_m90(matrix):
    return np.rot90(matrix, -1)


def rotate_matrix_p90(matrix):
    return np.rot90(matrix)