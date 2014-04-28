__author__ = 'Clemens Prescher'
import numpy as np
import matplotlib.pyplot as plt
import time
from PyQt4 import QtGui, QtCore
from collections import deque

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

    def mask_qt_graphics_object(self, qt_graphics_object):
        t1 = time.time()
        self.update_deque()
        # lets first get the rectanle
        rect = qt_graphics_object.boundingRect().getCoords()
        x_ind = np.arange(np.int32(rect[0]),
                          np.int32(np.round(rect[2])))
        y_ind = np.arange(np.int32(rect[1]),
                          np.int32(np.round(rect[3])))

        for x in x_ind:
            for y in y_ind:
                if qt_graphics_object.contains(QtCore.QPointF(x, y)):
                    self._mask_data[x, y] = True

        print "Time elapsed: %s" % (time.time()-t1)

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
    img_size = 2500
    x = np.arange(img_size)
    y = np.arange(img_size)
    X, Y = np.meshgrid(x, y)
    center_x = img_size / 2
    center_y = img_size / 2
    width = 30000.0
    intensity = 500
    img_data = intensity * \
        np.exp(-((X - center_x) ** 2 + (Y - center_y) ** 2) / width)
    mask_data = XrsMaskData(img_data.shape)

    # test the undo and redo commands
    mask_data.mask_above_threshold(img_data, 200)
    mask_data.mask_below_threshold(img_data, 150)
    mask_data.undo()
    mask_data.undo()
    mask_data.redo()
    mask_data.redo()
    mask_data.undo()

    # test the QGraphics commands
    my_object = QtGui.QGraphicsEllipseItem(20, 20, 300, 300)
    mask_data.mask_qt_graphics_object(my_object)
    my_object2 = QtGui.QGraphicsRectItem(100, 300, 10, 200)
    mask_data.mask_qt_graphics_object(my_object2)
    mask_data.mask_qt_graphics_object(
        QtGui.QGraphicsRectItem(300, 100, 200, 10))
    mask_data.mask_qt_graphics_object(
        QtGui.QGraphicsRectItem(300, 300, 200, 200))
    mask_data.mask_qt_graphics_object(
        QtGui.QGraphicsRectItem(0, 0, 200, 200))
    mask_data.mask_qt_graphics_object(
        QtGui.QGraphicsRectItem(0, 0, 1300, 1300))
    mask_data.undo()
    mask_data.undo()
    mask_data.redo()
    mask_data.undo()

    plt.imshow(img_data)
    plt.imshow(mask_data.get_img())
    plt.show()


if __name__ == "__main__":
    print 'testing mask data'
    test_mask_data()
