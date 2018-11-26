# -*- coding: utf-8 -*-
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
import time
import matplotlib.pyplot as plt
from pyFAI.azimuthalIntegrator import AzimuthalIntegrator

from Data.ImgCorrection import CbnCorrection

# defining geometry
image_shape = [2048, 2048] #pixel
detector_distance = 200 #mm
wavelength = 0.31 #angstrom
center_x = 1024 #pixel
center_y = 1024 #pixel
tilt = 0 #degree
rotation = 0 #degree
pixel_size = 79 #um

#some initialization
dummy_tth = np.linspace(0, 35, 2000)
dummy_int = np.ones(dummy_tth.shape)
geometry = AzimuthalIntegrator()
geometry.setFit2D(directDist=detector_distance,
                  centerX=center_x,
                  centerY=center_y,
                  tilt=tilt,
                  tiltPlanRotation=rotation,
                  pixelX=pixel_size,
                  pixelY=pixel_size)
geometry.wavelength = wavelength/1e10
dummy_img = geometry.calcfrom1d(dummy_tth, dummy_int, shape=image_shape, correctSolidAngle=True)


tth_array = geometry.twoThetaArray(image_shape)
azi_array = geometry.chiArray(image_shape)


cbn_correction = CbnCorrection(tth_array, azi_array,
                               diamond_thickness=2.2,
                               seat_thickness=5.3,
                               small_cbn_seat_radius=0.4,
                               large_cbn_seat_radius=1.95,
                               tilt=0,
                               tilt_rotation=0)

t1= time.time()
cbn_correction.get_data()
print("It took {0}s".format(time.time()-t1))

