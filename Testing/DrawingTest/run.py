"""
This module tests a number of possibilities for filling a polygon.
We here use the QGraphicsItems from the QT library as they are used in
pyqtgraph and so very valid for X-ray suite:
--------------------------------------------------------------------------
--------------------------------------------------------------------------
Tested possibilits:

1 - Using the QGraphicsItem contains function (test_qt_graphics_object)
2 - Using a distance measure to the center of a circle -- works only for
    circles or ellipses  (with modified equation)
3 - Using Points in Polygon algorithm (test_qt_graphics_object3)
4 - Using skimage.draw polygon function
5 - Using skimage.draw circle function (also works for ellipse)
"""

import mod
import matplotlib.pyplot as plt
import numpy as np
from PyQt4 import QtGui
from sklearn_implementation import fill_polygon, fill_circle
import time


print '------------------------------------------------------------------'
print ' 1   -   Using QGraphicsObject.contains()'
print '------------------------------------------------------------------'
t_run = []
sizes = []

num = 20

for n in xrange(num):
    size = 100 * (n + 1)
    mask_data = np.zeros((size, size))
    t1 = time.time()
    my_object = QtGui.QGraphicsEllipseItem(
        size / 2, size / 2, size / 4., size / 4, )
    mask_data = mod.test_qt_graphics_object(mask_data, my_object)
    t_run.append(time.time() - t1)
    sizes.append(size * size / 4)
    print "Size %s took %s" % (size, t_run[n])

plt.plot(sizes, t_run, 'r--', label="QGraphObject.contains()")

t_run = []
sizes = []

print '-----------------------------------------------------------------'
print ' 2   -   Using own distance calculation.'
print '-----------------------------------------------------------------'

for n in xrange(num):
    size = 100 * (n + 1)
    mask_data = np.zeros((size, size))
    t1 = time.time()
    my_object = QtGui.QGraphicsEllipseItem(
        size / 2, size / 2, size / 4., size / 4, )
    mask_data = mod.test_qt_graphics_object2(mask_data, my_object)
    t_run.append(time.time() - t1)
    sizes.append(size * size / 4)
    print "Size %s took %s" % (size, t_run[n])

plt.plot(sizes, t_run, 'm-', label="cython distance method")

# ----------------------------------------------------------------------
# 3
t_run = []
sizes = []

print '-----------------------------------------------------------------'
print ' 3   -   Using Points in polygon algorithm'
print '-----------------------------------------------------------------'

for n in xrange(num):
    size = 100 * (n + 1)
    mask_data = np.zeros((size, size))
    t1 = time.time()
    my_object = QtGui.QGraphicsRectItem(
        size / 2, size / 2, size / 4., size / 4, )
    mask_data = mod.test_qt_graphics_object3(mask_data, my_object)
    t_run.append(time.time() - t1)
    sizes.append(size * size / 4)
    print "Size %s took %s" % (size, t_run[n])

plt.plot(sizes, t_run, 'b-', label="Pnp algorithm")


# ------------------------------------------------------------------------
# 4
t_run = []
sizes = []

print '-----------------------------------------------------------------'
print ' 4   -   Using FillPolygon algorithm from skimage library.'
print '-----------------------------------------------------------------'

for n in xrange(num):
    size = 100 * (n + 1)
    mask_data = np.zeros((size, size))
    t1 = time.time()
    my_object = QtGui.QGraphicsEllipseItem(
        size / 2, size / 2, size / 4., size / 4, )
    mask_data = fill_polygon(mask_data, my_object)
    t_run.append(time.time() - t1)
    sizes.append(size * size / 4)
    print "Size %s took %s" % (size, t_run[n])

plt.plot(sizes, t_run, 'g-.', label="skimage.polygon()")

# ------------------------------------------------------------------------
# 5
t_run = []
sizes = []

print '------------------------------------------------------------------'
print ' 5  -   Using FillCircle algorithm from skimage library.'
print '------------------------------------------------------------------'

for n in xrange(num):
    size = 100 * (n + 1)
    mask_data = np.zeros((size, size))
    t1 = time.time()
    my_object = QtGui.QGraphicsEllipseItem(
        size / 2, size / 2, size / 4., size / 4, )
    mask_data = fill_circle(mask_data, my_object)
    t_run.append(time.time() - t1)
    sizes.append(size * size / 4)
    print "Size %s took %s" % (size, t_run[n])

plt.plot(sizes, t_run, 'k--', label="skimage.circle()")
plt.legend(loc="best")
plt.show()
