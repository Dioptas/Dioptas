# -*- coding: utf8 -*-
import numpy as np
# this returns cheb parameter for fitted background
# best for synchrotron XRD is N_points = 10, N_iteration = 10, N_cheborder = 50

def fit_bg_cheb_auto(x, y_obs, N_points, N_iteration, N_cheborder, accurate=True):
    y_bg_smooth = smooth_bruckner(x, y_obs, N_points, N_iteration)

    # get cheb input parameters
    x_cheb = 2. * (x - x[0]) / (x[-1] - x[0]) - 1.
    cheb_parameters = np.polynomial.chebyshev.chebfit(x_cheb,
                                                      y_bg_smooth, N_cheborder)

    if accurate:
        return np.polynomial.chebyshev.chebval(x_cheb, cheb_parameters)
    else:
        return cheb_parameters


def smooth_bruckner(x, y_obs, N_smooth, N_iter):
    y_original = y_obs

    N_data = y_obs.size
    N = N_smooth
    y = np.empty(N_data + N + N)

    y[N:N + N_data] = y_original[0:N_data]
    y[0:N].fill(y_original[N])
    y[N + N_data:N_data + N + N].fill(y_original[-1])
    y_new = y

    y_avg = np.average(y)
    y_min = np.min(y)

    y_c = y_avg + 2. * (y_avg - y_min)

    y[np.where(y > y_c)] = y_c

    for j in range(0, N_iter):
        for i in range(N, N_data - 1 - N - 1):
            y_new[i] = np.min([y[i], np.average(y[i - N:i + N + 1])])
            y = y_new

    return y[N:N + N_data]
