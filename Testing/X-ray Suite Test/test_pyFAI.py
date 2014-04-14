__author__ = 'Doomgoroth'

import time
import pyFAI, pyFAI.utils
import fabio
import matplotlib.pyplot as plt

img_file = fabio.open('Data/LaB6_p49_001.tif')

integrator = pyFAI.load('Data/LaB6_p49_001.poni')
#print integrator

t1 = time.time()
tth, I = integrator.integrate1d(img_file.data, 1000, unit='2th_deg', method="numpy")
t2 = time.time()

t1 = time.time()
tth, I = integrator.integrate1d(img_file.data, 1000, unit='2th_deg', method="cython")
t2 = time.time()

print("CYTHON took  %.3fs." %
      (t2 - t1))

t1 = time.time()
tth, I = integrator.integrate1d(img_file.data, 1000, unit='2th_deg', method="mine")
t2 = time.time()

print("MINE took  %.3fs." %
      (t2 - t1))

t1 = time.time()
tth, I = integrator.xrpd_LUT(img_file.data, 1000)
t2 = time.time()

print("lut took  %.3fs." %
      (t2 - t1))

t1 = time.time()
tth, I = integrator.xrpd_LUT(img_file.data, 1000)
t2 = time.time()

print("lut took  %.3fs." %
      (t2 - t1))
t1 = time.time()
tth, I = integrator.xrpd_LUT(img_file.data, 1000)
t2 = time.time()

print("lut took  %.3fs." %
      (t2 - t1))

t1 = time.time()
tth, I = integrator.integrate1d(img_file.data, 1000, unit='2th_deg', method="lut_ocl")
t2 = time.time()

print("lut_ocl  took  %.3fs." %
      (t2 - t1))

t1 = time.time()
tth, I = integrator.integrate1d(img_file.data, 1000, unit='2th_deg', method="lut_ocl")
t2 = time.time()

print("lut_ocl  took  %.3fs." %
      (t2 - t1))
t1 = time.time()
tth, I = integrator.integrate1d(img_file.data, 1000, unit='2th_deg', method="lut_ocl")
t2 = time.time()

print("lut_ocl  took  %.3fs." %
      (t2 - t1))
t1 = time.time()
tth, I = integrator.integrate1d(img_file.data, 1000, unit='2th_deg', method="lut_ocl")
t2 = time.time()

print("lut_ocl  took  %.3fs." %
      (t2 - t1))

t1 = time.time()
tth, I = integrator.integrate1d(img_file.data, 1000, unit='2th_deg', method="splitpix")
t2 = time.time()

print("splitpix took  %.3fs." %
      (t2 - t1))

t1 = time.time()
tth, I = integrator.integrate1d(img_file.data, 1000, unit='2th_deg', method="numpy")
t2 = time.time()

print("numpy took  %.3fs." %
      (t2 - t1))


