# -*- coding: utf8 -*-

import numpy as np

s2pi = np.sqrt(2 * np.pi)
def gaussian(x, amplitude=1.0, center=0.0, sigma=1.0):
    """1 dimensional gaussian:
    gaussian(x, amplitude, center, sigma)
    """
    return (amplitude / (s2pi * sigma)) * np.exp(-(1.0 * x - center) ** 2 / (2 * sigma ** 2))

