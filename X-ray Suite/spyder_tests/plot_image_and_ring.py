# -*- coding: utf-8 -*-
"""
Created on Fri Nov 29 19:34:13 2013

@author: Clemens
"""

import matplotlib.pyplot as plt
import matplotlib.image as mpimg
import numpy as np
from scipy.optimize import basinhopping, minimize, fmin_cg

sin=np.sin
cos=np.cos
tan=np.tan
pixel_size=0.079

wavelength=0.31
lab6_d=np.loadtxt('LaB6_d_spacings.txt')
lab6_two_theta=2*np.arcsin(wavelength/(2*lab6_d))


def calculate_ring(two_theta, D, x_center, y_center, alpha, phi, gamma=np.linspace(-np.pi,+np.pi,1000)):
    x=(cos(alpha)*tan(two_theta)*sin(gamma)+sin(alpha))/  \
       (cos(alpha)-sin(alpha)*tan(two_theta)*sin(gamma))*D
    y=-(x*sin(alpha)+D*cos(alpha))*tan(two_theta)*cos(gamma)
    x_rot=x*cos(phi)-y*sin(phi) + x_center
    y_rot=x*sin(phi)+y*cos(phi) + y_center
    return x_rot, y_rot

img = mpimg.imread('LaB6_p49_40keV.tif')
plt.imshow(img, vmax=2500, extent=[0,2024*pixel_size, 0,2048*pixel_size])

#calculate ring:
pixel_size=0.079
x_center=1024*pixel_size
y_center=1024*pixel_size
alpha=0
phi=0

def minimization_function(x):
    D=x[0]+190
    x_center=(x[1]+1024)*pixel_size
    y_center=(x[2]+1024)*pixel_size
    alpha=x[3]/100
    phi=x[4]/100
    output=0
    for two_theta in lab6_two_theta[:4]:
        x,y = calculate_ring(two_theta,D,x_center, y_center, alpha, phi)
        binning=np.linspace(pixel_size/2.0, 2048.5*pixel_size,2048)
        x_bin=np.digitize(x,binning)
        y_bin=np.digitize(y,binning)
        index_array=np.array([x_bin, y_bin]).T
        
        #now we try to get only unqiue index values for each ring:
        flat_array = np.ascontiguousarray(index_array).view(np.dtype((np.void, \
                                                index_array.dtype.itemsize * \
                                                index_array.shape[1])))
        unique_index_array = np.unique(flat_array).view(index_array.dtype).reshape(-1, index_array.shape[1])
        try:
            output-= np.sum(img[unique_index_array])/np.float(len(unique_index_array))
        except:
            pass
    print str(output)
    return output
    

    
res = fmin_cg(minimization_function, [196.549-190,1024.4795-1024,1025.617-1024,  -0.0045*1000, 0 ],
              epsilon=0.5)
print res 
    
x= res
    
D=x[0]+190
x_center=(x[1]+1024)*pixel_size
y_center=(x[2]+1024)*pixel_size
alpha=x[3]/100
phi=x[4]/100
output=0
for two_theta in lab6_two_theta[:4]:
    x,y = calculate_ring(two_theta,D,x_center, y_center, alpha, phi)
    binning=np.linspace(pixel_size/2.0, 2048.5*pixel_size,2048)
    x_bin=np.digitize(x,binning)
    y_bin=np.digitize(y,binning)
    index_array=np.array([x_bin, y_bin]).T
    
    #now we try to get only unqiue index values for each ring:
    flat_array = np.ascontiguousarray(index_array).view(np.dtype((np.void, \
                                            index_array.dtype.itemsize * \
                                            index_array.shape[1])))
    unique_index_array = np.unique(flat_array).view(index_array.dtype).reshape(-1, index_array.shape[1])
    x_final=binning[unique_index_array[:,0]]
    y_final=binning[unique_index_array[:,1]]
    plt.scatter(x_final, y_final)
#print res
#plot_circles([196.549,1023.617, 1019.4795, 0, 0 ])