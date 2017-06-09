# -*- coding: utf8 -*-

import logging

logger = logging.getLogger(__name__)

import numpy as np

try:
    from .smooth_bruckner import smooth_bruckner
except ImportError as e:
    print(e)
    logger.warning(
        "Could not import the Fortran version of smooth_bruckner. Using python implementation instead. Please"
        " run 'f2py -c -m smooth_bruckner smooth_bruckner.f95' in the model/util folder for faster"
        " implementation")
    from .smooth_bruckner_python import smooth_bruckner


def extract_background(x, y, smooth_width=0.1, iterations=50, cheb_order=50):
    """
    Performs a background subtraction using bruckner smoothing and a chebyshev polynomial.
    Standard parameters are found to be optimal for synchrotron XRD.
    :param x: x-data of pattern
    :param y: y-data of pattern
    :param smooth_width: width of the window in x-units used for bruckner smoothing
    :param iterations: number of iterations for the bruckner smoothing
    :param cheb_order: order of the fitted chebyshev polynomial
    :return: vector of extracted y background
    """
    smooth_points = int((float(smooth_width) / (x[1] - x[0])))

    y_smooth = smooth_bruckner(y, smooth_points, iterations)
    # get cheb input parameters
    x_cheb = 2. * (x - x[0]) / (x[-1] - x[0]) - 1.
    cheb_parameters = np.polynomial.chebyshev.chebfit(x_cheb,
                                                      y_smooth,
                                                      cheb_order)

    return np.polynomial.chebyshev.chebval(x_cheb, cheb_parameters)
