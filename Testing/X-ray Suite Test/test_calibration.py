__author__ = 'Doomgoroth'

import matplotlib.pyplot as plt
import numpy as np

from ImageCalibration import ImageCalibration
from utilities import Point


if __name__ == "__main__":
    #do our calibration
    #my_calibration = ImageCalibration(Point(1023.09, 1024.74),19.9932,  -0.254300, 196.730e-3, 79e-6,1)
    #img = plt.imread('Data/Fe7C3_300_020.tif')
    #chi_data=np.loadtxt('Data/Fe7C3_300_020.chi',skiprows=4).T

    my_calibration = ImageCalibration(Point(1023.058, 1025.755), 24.25411, -0.260421, 196.7255e-3, 79e-6, 1)
    img = plt.imread('Data/LaB6_p49_001.tif')
    chi_data = np.loadtxt('Data/LaB6_p49_001_norm_polar_geom.chi', skiprows=4).T
    xy_data = np.loadtxt('Data/LaB6_p49_001.xy', skiprows=17).T

    x, y = my_calibration.integrate_image(img)
    print len(x)
    plt.plot(x, y)

    plt.plot(chi_data[0, :], chi_data[1, :], "r")
    plt.plot(xy_data[0, :], xy_data[1, :], 'g')
    plt.figure()
    plt.plot(chi_data[0, :], chi_data[1, :] - np.interp(chi_data[0, :], xy_data[0, :], xy_data[1, :]))
    plt.show()


