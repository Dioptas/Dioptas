# -*- coding: utf8 -*-


import numpy as np
import matplotlib.pyplot as plt

from from_dan import fit_bg_cheb_auto

def get_data(filename):
    data = np.loadtxt(filename)
    x = data[:,0]
    y = data[:,1]
    return x,y

x,y = get_data('Fe7C3_300_020.xy')
# x,y = get_data('test2.xy')

background = fit_bg_cheb_auto(x, y, 10,20,100)
plt.plot(x,y)
plt.plot(x,background)
plt.show()
