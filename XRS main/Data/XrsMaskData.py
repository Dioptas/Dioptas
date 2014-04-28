__author__ = 'Clemens Prescher'
import numpy as np
import pyqtgraph as pg
from PyQt4 import QtGui, QtCore
from collections import deque
import skimage.draw


class XrsMaskData(object):

    def __init__(self, mask_dimension):
        self.mask_dimension = mask_dimension
        self._mask_data = np.zeros(mask_dimension, dtype=bool)
        self.mask_img = np.zeros((mask_dimension[0],
                                  mask_dimension[1], 4), dtype='uint8')

        # initialize undo/redo deque
        self._undo_deque = deque(maxlen=50)
        self._redo_deque = deque(maxlen=50)

    def get_mask(self):
        mask_data = np.copy(self._mask_data)
        mask_data[np.where(self._mask_data > 0)] = 1
        return mask_data

    def get_img(self):
        ind = np.where(self._mask_data > 0)
        self.mask_img[ind] = [0, 255, 0, 200]
        return self.mask_img

    def mask_below_threshold(self, img_data, threshold):
        self.update_deque()
        self._mask_data += (img_data <= threshold)

    def mask_above_threshold(self, img_data, threshold):
        self.update_deque()
        self._mask_data += (img_data >= threshold)

    def mask_QGraphicsRectItem(self, QGraphicsRectItem):
        rect = QGraphicsRectItem.rect()
        print rect.width()
        print rect.height()
        print rect.x()
        print rect.y()
        self.mask_rect(rect.left(), rect.top(), rect.width(), rect.height())

    def mask_QGraphicsPolygonItem(self, QGraphicsPolygonItem):
        """
        Masks a polygon given by a QGraphicsPolygonItem from the QtGui Library. Uses the sklimage.draw.polygon function.
        """

        #get polygon points
        poly_list = list(QGraphicsPolygonItem.shape().toFillPolygon())
        x = np.zeros(len(poly_list))
        y = np.zeros(len(poly_list))

        for i, point in enumerate(poly_list):
            x[i] = point.x()
            y[i] = point.y()
        self.mask_polygon(x, y)

    def mask_QGraphicsEllipseItem(self, QGraphicsEllipseItem):
        """
        Masks an Ellipse given by a QGraphicsEllipseItem from the QtGui Library. Uses the sklimage.draw.ellipse function.
        """
        bounding_rect = QGraphicsEllipseItem()
        cx = bounding_rect.center().x()
        cy = bounding_rect.center().y()
        x_radius = bounding_rect.width() * 0.5
        y_radius = bounding_rect.height() * 0.5
        self.mask_ellipse(cx, cy, x_radius, y_radius)

    def mask_rect(self, x, y, width, height):
        """
        Masks a rectangle. x and y parameters are the upper left corner of the rectangle.
        """
        self.update_deque()
        x_ind1 = np.round(x)
        x_ind2 = np.round(x + width)
        y_ind1 = np.round(y)
        y_ind2 = np.round(y + height)
        self._mask_data[x_ind1:x_ind2, y_ind1:y_ind2] = True

    def mask_polygon(self, x, y):
        """
        Masks the a polygon with given vertices. x and y are lists of the polygon vertices.
        Uses the draw.polygon implementation of the skimage library.
        """
        self.update_deque()
        rr, cc = skimage.draw.polygon(y, x, self._mask_data.shape)
        self._mask_data[rr, cc] = True

    def mask_ellipse(self, cx, cy, x_radius, y_radius):
        """
        Masks an ellipse with center coordinates (cx, cy) and the radii given. Uses the draw.ellipse implementation of
        the skimage library.
        """
        self.update_deque()
        rr, cc = skimage.draw.ellipse(cy, cx, y_radius, x_radius, self._mask_data.shape)
        self.mask_data[rr, cc] = True

    def update_deque(self):
        """
        Saves the current mask data into a deque, which can be popped later
        to provide an undo/redo feature. 
        When performing a new action the old redo steps will be cleared..._
        """
        self._undo_deque.append(np.copy(self._mask_data))
        self._redo_deque.clear()

    def undo(self):
        self._redo_deque.append(np.copy(self._mask_data))
        self._mask_data = self._undo_deque.pop()

    def redo(self):
        self._undo_deque.append(np.copy(self._mask_data))
        self._mask_data = self._redo_deque.pop()


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
    mask_data = XrsMaskData(img_data.shape)

    # test the undo and redo commands
    mask_data.mask_above_threshold(img_data, 4000)
    mask_data.mask_below_threshold(img_data, 230)
    mask_data.undo()
    mask_data.undo()
    mask_data.redo()
    mask_data.redo()
    mask_data.undo()

    mask_data.mask_rect(200, 400, 400, 100)
    mask_data.mask_QGraphicsRectItem(QtGui.QGraphicsRectItem(100, 10, 100, 100))
    mask_data.undo()

    mask_data.mask_polygon(np.array([0, 100, 150, 100, 0]), np.array([0, 0, 50, 100, 100]))
    mask_data.mask_QGraphicsPolygonItem(QtGui.QGraphicsEllipseItem(350, 350, 20, 20))

    #performing the plot
    pg.image(mask_data.get_img())


if __name__ == "__main__":
    import sys

    print 'testing mask data'
    test_mask_data()
    pg.QtGui.QApplication.exec_()
