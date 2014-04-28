from PyQt4 import QtCore
import numpy as np
import time

from cpython cimport bool

cimport cython
cimport numpy as np
DTYPE_FLOAT64 = np.float64
ctypedef np.float64_t DTYPE_FLOAT64_t
DTYPE_BOOL = np.bool
ctypedef np.uint8_t DTYPE_BOOL_t


@cython.boundscheck(False)
@cython.wraparound(False)

def test_qt_graphics_object(mask_data, qt_graphics_object):
    rect = qt_graphics_object.boundingRect().getCoords()
    x_ind = np.arange(np.int32(rect[0]),
                      np.int32(np.round(rect[2])))
    y_ind = np.arange(np.int32(rect[1]),
                      np.int32(np.round(rect[3])))
    cdef int x, y
    for x in x_ind:
        for y in y_ind:
            if qt_graphics_object.contains(QtCore.QPointF(x, y)):
                mask_data[x, y] = True
    return mask_data

def test_qt_graphics_object2(mask_data, qt_graphics_object):
    rect = qt_graphics_object.boundingRect().getCoords()
    x_ind = np.arange(np.int32(rect[0]),
                      np.int32(np.round(rect[2])))
    y_ind = np.arange(np.int32(rect[1]),
                      np.int32(np.round(rect[3])))

    cdef double m1 = qt_graphics_object.boundingRect().center().x()
    cdef double m2 = qt_graphics_object.boundingRect().center().y()
    cdef double radiusSquared = (qt_graphics_object.boundingRect().width()*0.5)**2

    cdef int x, y
    cdef double dx, dy, distanceSquared

    for x in x_ind:
        for y in y_ind:
            dx = x - m1;
            dy = y - m2;
            distanceSquared = dx * dx + dy * dy;

            if distanceSquared <= radiusSquared:
                mask_data[x,y] = True
    return mask_data


def test_qt_graphics_object3(mask_data, qt_graphics_object):
    rect = qt_graphics_object.boundingRect().getCoords()
    x_ind = np.arange(np.int32(rect[0]),
                      np.int32(np.round(rect[2])))
    y_ind = np.arange(np.int32(rect[1]),
                      np.int32(np.round(rect[3])))

    polygon_vec = qt_graphics_object.shape().toFillPolygon()
    vert = list(polygon_vec)
    poly = []
    for point in vert:
        poly.append((point.x(), point.y()))

    cdef int x, y

    for x in x_ind:
        for y in y_ind:
            mask_data[x,y] = point_inside_polygon(x,y, poly)
    return mask_data


def point_inside_polygon(x,y,poly):
    cdef int n
    n = len(poly)
    cdef bool inside = False
    cdef double p1x, p1y
    p1x,p1y = poly[0]
    for i in range(n+1):
        p2x,p2y = poly[i % n]
        if y > min(p1y,p2y):
            if y <= max(p1y,p2y):
                if x <= max(p1x,p2x):
                    if p1y != p2y:
                        xinters = (y-p1y)*(p2x-p1x)/(p2y-p1y)+p1x
                    if p1x == p2x or x <= xinters:
                        inside = not inside
        p1x,p1y = p2x,p2y
    return inside