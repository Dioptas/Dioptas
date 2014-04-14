# -*- coding: utf-8 -*-
"""
Created on Wed Nov 27 07:20:48 2013

@author: Clemens
"""

import numpy as np
import pylab as pl

sin = np.sin
cos = np.cos
tan = np.tan


def calc_two_theta_hammer(x, y, D, beta, phi):
    first_term = np.cos(phi) ** 2 * (np.cos(beta) * x + np.sin(beta) * y) ** 2
    second_term = (-np.sin(beta) * x + np.cos(beta) * y) ** 2
    third_term = (D + np.sin(phi) * (np.cos(beta) * x + np.sin(beta) * y)) ** 2

    two_theta = np.sqrt(np.arctan((first_term + second_term) / third_term))
    return two_theta


alpha_vals = np.linspace((-10 / 180.) * np.pi, (+10 / 180.) * np.pi, 20)
alpha_vals = [00 / .180 * np.pi]
gamma = np.linspace(-np.pi, +np.pi, 1000)

two_theta = 0.9
D = 200

phi = (00 / 180.) * np.pi

for alpha in alpha_vals:
    x = (cos(alpha) * tan(two_theta) * sin(gamma) + sin(alpha)) / \
        (cos(alpha) - sin(alpha) * tan(two_theta) * sin(gamma)) * D
    y = -(x * sin(alpha) + D * cos(alpha)) * tan(two_theta) * cos(gamma)

    x_rot = x * cos(phi) - y * sin(phi)
    y_rot = x * sin(phi) + y * cos(phi)
    #binning=np.linspace(-10,10,100)
    #x_rot=binning[np.digitize(x_rot,binning)]
    #y_rot=binning[np.digitize(y_rot,binning)]
    pi_half = np.pi
    print calc_two_theta_hammer(x_rot, y_rot, D, -alpha, -phi)
    pl.plot(x_rot, y_rot)
 