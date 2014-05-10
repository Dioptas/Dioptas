__author__ = 'Clemens Prescher'
import numpy as np
import pyqtgraph as pg
from PyQt4 import QtGui
from collections import deque
import skimage.draw
import scipy.signal
from cosmics import cosmicsimage

import time
from sys import getsizeof


class MaskData(object):
    def __init__(self, mask_dimension=None):
        self.mask_dimension = mask_dimension
        self.reset_dimension()
        self.mode = True

    def set_dimension(self, mask_dimension):
        if not np.array_equal(mask_dimension, self.mask_dimension):
            self.mask_dimension = mask_dimension
            self.reset_dimension()

    def reset_dimension(self):
        if self.mask_dimension is not None:
            self._mask_data = np.zeros(self.mask_dimension, dtype=bool)
            self._undo_deque = deque(maxlen=50)
            self._redo_deque = deque(maxlen=50)

    def get_mask(self):
        return self._mask_data

    def get_img(self):
        return self._mask_data

    def update_deque(self):
        """
        Saves the current mask data into a deque, which can be popped later
        to provide an undo/redo feature.
        When performing a new action the old redo steps will be cleared..._
        """
        self._undo_deque.append(np.copy(self._mask_data))
        self._redo_deque.clear()

    def undo(self):
        try:
            old_data = self._undo_deque.pop()
            self._redo_deque.append(np.copy(self._mask_data))
            self._mask_data = old_data
        except IndexError:
            pass

    def redo(self):
        try:
            new_data = self._redo_deque.pop()
            self._undo_deque.append(np.copy(self._mask_data))
            self._mask_data = new_data
        except IndexError:
            pass

    def mask_below_threshold(self, img_data, threshold):
        self.update_deque()
        self._mask_data += (img_data < threshold)

    def mask_above_threshold(self, img_data, threshold):
        self.update_deque()
        self._mask_data += (img_data > threshold)

    def mask_QGraphicsRectItem(self, QGraphicsRectItem):
        rect = QGraphicsRectItem.rect()
        self.mask_rect(rect.top(), rect.left(), rect.height(), rect.width())

    def mask_QGraphicsPolygonItem(self, QGraphicsPolygonItem):
        """
        Masks a polygon given by a QGraphicsPolygonItem from the QtGui Library.
        Uses the sklimage.draw.polygon function.
        """

        # get polygon points
        poly_list = list(QGraphicsPolygonItem.shape().toFillPolygon())
        x = np.zeros(len(poly_list))
        y = np.zeros(len(poly_list))

        for i, point in enumerate(poly_list):
            x[i] = point.x()
            y[i] = point.y()
        self.mask_polygon(x, y)

    def mask_QGraphicsEllipseItem(self, QGraphicsEllipseItem):
        """
        Masks an Ellipse given by a QGraphicsEllipseItem from the QtGui
        Library. Uses the sklimage.draw.ellipse function.
        """
        bounding_rect = QGraphicsEllipseItem.rect()
        cx = bounding_rect.center().x()
        cy = bounding_rect.center().y()
        x_radius = bounding_rect.width() * 0.5
        y_radius = bounding_rect.height() * 0.5
        self.mask_ellipse(cx, cy, x_radius, y_radius)

    def mask_rect(self, x, y, width, height):
        """
        Masks a rectangle. x and y parameters are the upper left corner
        of the rectangle.
        """
        self.update_deque()
        if width > 0:
            x_ind1 = np.round(x)
            x_ind2 = np.round(x + width)
        else:
            x_ind1 = np.round(x + width)
            x_ind2 = np.round(x)
        if height > 0:
            y_ind1 = np.round(y)
            y_ind2 = np.round(y + height)
        else:
            y_ind1 = np.round(y + height)
            y_ind2 = np.round(y)

        if x_ind1 < 0:
            x_ind1 = 0
        if y_ind1 < 0:
            y_ind1 = 0

        self._mask_data[x_ind1:x_ind2, y_ind1:y_ind2] = self.mode

    def mask_polygon(self, x, y):
        """
        Masks the a polygon with given vertices. x and y are lists of
        the polygon vertices. Uses the draw.polygon implementation of
        the skimage library.
        """
        self.update_deque()
        rr, cc = skimage.draw.polygon(y, x, self._mask_data.shape)
        self._mask_data[rr, cc] = self.mode

    def mask_ellipse(self, cx, cy, x_radius, y_radius):
        """
        Masks an ellipse with center coordinates (cx, cy) and the radii
        given. Uses the draw.ellipse implementation of
        the skimage library.
        """
        self.update_deque()
        rr, cc = skimage.draw.ellipse(
            cy, cx, y_radius, x_radius, shape=self._mask_data.shape)
        self._mask_data[rr, cc] = self.mode

    def invert_mask(self):
        self.update_deque()
        self._mask_data = np.logical_not(self._mask_data)

    def clear_mask(self):
        self.update_deque()
        self._mask_data[:, :] = False

    def remove_cosmic(self, img):
        self.update_deque()
        test = cosmicsimage(img, sigclip=3.0, objlim=5.0, satlevel=-1)
        num = 10
        for i in xrange(num):
            test.lacosmiciteration(True)
            test.clean()
            self._mask_data += np.array(test.mask, dtype='bool')

        print test.mask

    def set_mode(self, mode):
        """
        sets the mode to unmask or mask which equals mode = False or True
        """
        self.mode = mode

    def set_mask(self, mask_data):
        self.update_deque()
        self._mask_data = mask_data

    def load_mask(self, filename):
        data = np.loadtxt(filename)
        self.mask_dimension = data.shape
        self.reset_dimension()
        self.set_mask(data)

    def add_mask(self, mask_data):
        self._mask_data += np.array(mask_data, dtype='bool')


def test_mask_data():
    # create Gaussian image:
    img_size = 500
    x = np.arange(img_size)
    y = np.arange(img_size)
    X, Y = np.meshgrid(x, y)
    center_x = img_size / 2
    center_y = img_size / 2
    width = 30000.0
    intensity = 5000.0
    img_data = intensity * \
               np.exp(-((X - center_x) ** 2 + (Y - center_y) ** 2) / width)
    mask_data = MaskData(img_data.shape)

    # test the undo and redo commands
    mask_data.mask_above_threshold(img_data, 4000)
    mask_data.mask_below_threshold(img_data, 230)
    mask_data.undo()
    mask_data.undo()
    mask_data.redo()
    mask_data.redo()
    mask_data.undo()

    mask_data.mask_rect(200, 400, 400, 100)
    mask_data.mask_QGraphicsRectItem(
        QtGui.QGraphicsRectItem(100, 10, 100, 100))
    mask_data.undo()

    mask_data.mask_polygon(
        np.array([0, 100, 150, 100, 0]), np.array([0, 0, 50, 100, 100]))
    mask_data.mask_QGraphicsPolygonItem(
        QtGui.QGraphicsEllipseItem(350, 350, 20, 20))

    # performing the plot
    pg.image(mask_data.get_img())


if __name__ == "__main__":
    print 'testing mask data'
    test_mask_data()
    pg.QtGui.QApplication.exec_()
