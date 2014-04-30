import numpy as np
from skimage.draw import polygon, circle
from PyQt4 import QtGui
import matplotlib.pyplot as plt
import time


def fill_circle(mask_data, qt_circle_item):
    cx = qt_circle_item.boundingRect().center().x()
    cy = qt_circle_item.boundingRect().center().y()
    radius = qt_circle_item.boundingRect().width() * 0.5
    rr, cc = circle(cy, cx, radius, mask_data.shape)
    mask_data[rr, cc] = True


def fill_polygon(mask_data, qt_graphics_object):
    x, y = get_polygon_points(qt_graphics_object)
    rr, cc = polygon(y, x)
    mask_data[rr, cc] = True
    return mask_data


def get_polygon_points(qt_graphics_object):
    poly_list = list(qt_graphics_object.shape().toFillPolygon())
    x = np.zeros(len(poly_list))
    y = np.zeros(len(poly_list))

    for i, point in enumerate(poly_list):
        x[i] = point.x()
        y[i] = point.y()
    return x, y


def run():
    size = 20000
    mask_data = np.zeros((size, size))
    my_object = QtGui.QGraphicsRectItem(
        size / 2, size / 2, size / 4., size / 4,)
    mask_data = fill_polygon(mask_data, my_object)

    plt.imshow(mask_data)
    plt.show()


if __name__ == "__main__":
    run()
