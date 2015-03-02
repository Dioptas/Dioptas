# -*- coding: utf8 -*-
# - GUI program for fast processing of 2D X-ray data
#     Copyright (C) 2014  Clemens Prescher (clemens.prescher@gmail.com)
#     GSECARS, University of Chicago
#
#     This program is free software: you can redistribute it and/or modify
#     it under the terms of the GNU General Public License as published by
#     the Free Software Foundation, either version 3 of the License, or
#     (at your option) any later version.
#
#     This program is distributed in the hope that it will be useful,
#     but WITHOUT ANY WARRANTY; without even the implied warranty of
#     MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#     GNU General Public License for more details.
#
#     You should have received a copy of the GNU General Public License
#     along with this program.  If not, see <http://www.gnu.org/licenses/>.
__author__ = 'Clemens Prescher'
import time
import numpy as np

size = 2048
super_sampling = 6


ar = np.ones((size,size))

ar[1,1] = 3

for super_sampling in range(1,30):
    t1 = time.time()
    new_ar = np.zeros((size*super_sampling,size*super_sampling))



    new_ar[::super_sampling, ::super_sampling] = ar
    for row in range(super_sampling):
        for col in range(super_sampling):
            new_ar[row::super_sampling, col::super_sampling] = ar
    new_ar/=super_sampling**2

    print "Time needed for sampling = {}, {}".format(super_sampling,time.time()-t1)