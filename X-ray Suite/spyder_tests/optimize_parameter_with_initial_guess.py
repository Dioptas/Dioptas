# -*- coding: utf-8 -*-
"""
Created on Sat Nov 30 00:30:13 2013

@author: Clemens
"""

from scipy import ndimage, interpolate
import numpy as np

import matplotlib.pyplot as plt
import matplotlib.image as mpimg
from scipy.optimize import basinhopping, minimize, fmin_cg


sin=np.sin
cos=np.cos
tan=np.tan

img1= mpimg.imread('LaB6_p49_40keV.tif')
img = ndimage.gaussian_filter(img1,10)
pixel_size=0.079


wavelength=0.31
lab6_d=np.loadtxt('LaB6_d_spacings.txt')
lab6_two_theta=2*np.arcsin(wavelength/(2*lab6_d))


plt.imshow(img1, vmax=2500) #extent=[2024*pixel_size, 0, 0,2048*pixel_size])
#binning=np.linspace(pixel_size/2.0, 2048.5*pixel_size,2048)
binning=np.linspace(pixel_size/2.0, 2047.5*pixel_size,2048)
#binning=np.linspace(0, 2500,2048)
img_inter = interpolate.RectBivariateSpline(binning, binning, img1)

def calculate_ring(two_theta, D, x_center, y_center, alpha, phi, gamma=np.linspace(-np.pi,+np.pi,1000)):
    x=(cos(alpha)*tan(two_theta)*sin(gamma)+sin(alpha))/  \
       (cos(alpha)-sin(alpha)*tan(two_theta)*sin(gamma))*D
    y=-(x*sin(alpha)+D*cos(alpha))*tan(two_theta)*cos(gamma)
    x_rot=x*cos(phi)-y*sin(phi) + x_center
    y_rot=x*sin(phi)+y*cos(phi) + y_center
    return x_rot, y_rot
    
    
points_on_circle=np.array(\
[	[840.016, 998.047],
	[940.725, 854.989],
	[1163.83, 898.887],
	[1168.48, 1140.59],
	[983.074, 1201.53],
	[1024.91, 1208.78],
	[1024.91, 830.199],
	[837.434, 1024.39],
	[1209.8, 1024.9],
])*pixel_size

def minimize_with_points(x):
    D=x[0]
    x_center=x[1]*pixel_size
    y_center=x[2]*pixel_size
    alpha=x[3]
    phi=x[4]
    weight=0
    for point in points_on_circle:
        x_rot=(point[0]-x_center)*cos(phi)-(point[1]-y_center)*sin(phi) 
        y_rot=(point[0]-x_center)*sin(phi)+(point[1]-y_center)*cos(phi)
        weight += (lab6_two_theta[0]-np.arccos(\
                    (x_rot*sin(alpha)+D*cos(alpha))/\
                    np.sqrt(D**2+x_rot**2+y_rot**2)))**2
    return weight
    
    
res = minimize(minimize_with_points, [196.549,1020.4795,1025.617,  -0.0045,0 ],
               method='Nelder-Mead',options={'maxiter': 200})
                                  
        
print res.x
def minimization_function(x):
    D=x[0]
    x_center=x[1]*pixel_size
    y_center=x[2]*pixel_size
    alpha=x[3]
    phi=x[4]
    output=0
    for two_theta in lab6_two_theta[:8]:
        x,y = calculate_ring(two_theta,D,x_center, y_center, alpha, phi)
        ring_int=0
        for ind in xrange(len(x)):
            ring_int+=img_inter(x[ind],y[ind])
        output-= (ring_int/np.float(len(x)))**2
    return output[0]
    

    
#res = minimize(minimization_function, res.x,
#               method='Nelder-Mead', tol=1e-5, options={'maxiter': 200})
#print res.x
#print res.message
#    
x=res.x
    
D=x[0]
x_center=x[1]*pixel_size
y_center=x[2]*pixel_size
alpha=x[3]
phi=x[4]
for two_theta in lab6_two_theta[:8]:
    x,y = calculate_ring(two_theta,D,x_center, y_center, alpha, phi)
    #utput-= np.sum(np.sum(img_inter(x,y)))/np.float(len(x))
    plt.scatter(x/pixel_size, y/pixel_size)
    