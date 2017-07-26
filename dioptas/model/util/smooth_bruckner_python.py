# -*- coding: utf8 -*-
# Dioptas - GUI program for fast processing of 2D X-ray data
# Copyright (C) 2017  Clemens Prescher (clemens.prescher@gmail.com)
# Institute for Geology and Mineralogy, University of Cologne
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.


import numpy as np

def smooth_bruckner(y, smooth_points, iterations):
    y_original = y
    N_data = y.size
    N = smooth_points
    N_float = float(N)
    y = np.empty(N_data + N + N)

    y[0:N].fill(y_original[0])
    y[N:N + N_data] = y_original[0:N_data]
    y[N + N_data:N_data + N + N].fill(y_original[-1])

    y_avg = np.average(y)
    y_min = np.min(y)

    y_c = y_avg + 2. * (y_avg - y_min)
    y[y > y_c] = y_c

    window_size = N_float*2+1


    for j in range(0, iterations):
        window_avg = np.average(y[0: 2*N + 1])
        for i in range(N, N_data - 1 - N - 1):
            if y[i]>window_avg:
                y_new = window_avg
                #updating central value in average (first bracket)
                #and shifting average by one index (second bracket)
                window_avg += ((window_avg-y[i]) + (y[i+N+1]-y[i - N]))/window_size
                y[i] = y_new
            else:
                #shifting average by one index
                window_avg += (y[i+N+1]-y[i - N])/window_size
    return y[N:N + N_data]