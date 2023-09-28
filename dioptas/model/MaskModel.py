# -*- coding: utf-8 -*-
# Dioptas - GUI program for fast processing of 2D X-ray diffraction data
# Principal author: Clemens Prescher (clemens.prescher@gmail.com)
# Copyright (C) 2014-2019 GSECARS, University of Chicago, USA
# Copyright (C) 2015-2018 Institute for Geology and Mineralogy, University of Cologne, Germany
# Copyright (C) 2019-2020 DESY, Hamburg, Germany
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from collections import deque

import fabio
import numpy as np
import skimage.draw
from PIL import Image
from qtpy import QtCore
from math import sqrt, atan2, cos, sin

from .util.cosmics import cosmicsimage


class MaskModel(object):
    def __init__(self, mask_dimension=(2048, 2048)):
        self.mask_dimension = mask_dimension
        self.reset_dimension()
        self.filename = ''
        self.mode = True
        self.roi = None

        self._mask_data = np.zeros(self.mask_dimension, dtype=bool)
        self._undo_deque = deque(maxlen=50)
        self._redo_deque = deque(maxlen=50)

    def set_dimension(self, mask_dimension):
        if not np.array_equal(mask_dimension, self.mask_dimension):
            self.mask_dimension = mask_dimension
            self.reset_dimension()

    def reset_dimension(self):
        if self.mask_dimension is not None:
            self._mask_data = np.zeros(self.mask_dimension, dtype=bool)
            self._undo_deque = deque(maxlen=50)
            self._redo_deque = deque(maxlen=50)

    @property
    def roi_mask(self):
        if self.roi is not None:
            roi_mask = np.ones(self.mask_dimension)
            x1, x2, y1, y2 = self.roi
            if x1 < 0:
                x1 = 0
            if y1 < 0:
                y1 = 0
            roi_mask[int(x1):int(x2), int(y1):int(y2)] = 0

            return roi_mask

        else:
            return None

    def get_mask(self):
        if self.roi is None:
            return self._mask_data
        elif self.roi is not None:
            return np.logical_or(self._mask_data, self.roi_mask)

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
        Masks a polygon given by a QGraphicsPolygonItem from the QtWidgets Library.
        Uses the sklimage.draw.polygon function.
        """

        # get polygon points
        poly_list = list(QGraphicsPolygonItem.vertices)
        x = np.zeros(len(poly_list))
        y = np.zeros(len(poly_list))

        for i, point in enumerate(poly_list):
            x[i] = point.x()
            y[i] = point.y()
        self.mask_polygon(x, y)

    def mask_QGraphicsEllipseItem(self, QGraphicsEllipseItem):
        """
        Masks an Ellipse given by a QGraphicsEllipseItem from the QtWidgets
        Library. Uses the skimage.draw.ellipse function.
        """
        bounding_rect = QGraphicsEllipseItem.rect()
        cx = bounding_rect.center().x()
        cy = bounding_rect.center().y()
        x_radius = bounding_rect.width() * 0.5
        y_radius = bounding_rect.height() * 0.5
        self.mask_ellipse(int(cx), int(cy), int(x_radius), int(y_radius))

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

        x_ind1, x_ind2, y_ind1, y_ind2 = int(x_ind1), int(x_ind2), int(y_ind1), int(y_ind2)
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

    def grow(self):
        self.update_deque()
        self._mask_data[1:, :] = np.logical_or(self._mask_data[1:, :], self._mask_data[:-1, :])
        self._mask_data[:-1, :] = np.logical_or(self._mask_data[:-1, :], self._mask_data[1:, :])
        self._mask_data[:, 1:] = np.logical_or(self._mask_data[:, 1:], self._mask_data[:, :-1])
        self._mask_data[:, :-1] = np.logical_or(self._mask_data[:, :-1], self._mask_data[:, 1:])

    def shrink(self):
        self.update_deque()
        self._mask_data[1:, :] = np.logical_and(self._mask_data[1:, :], self._mask_data[:-1, :])
        self._mask_data[:-1, :] = np.logical_and(self._mask_data[:-1, :], self._mask_data[1:, :])
        self._mask_data[:, 1:] = np.logical_and(self._mask_data[:, 1:], self._mask_data[:, :-1])
        self._mask_data[:, :-1] = np.logical_and(self._mask_data[:, :-1], self._mask_data[:, 1:])

    def invert_mask(self):
        self.update_deque()
        self._mask_data = np.logical_not(self._mask_data)

    def clear_mask(self):
        self.update_deque()
        self._mask_data[:, :] = False

    def remove_cosmic(self, img):
        self.update_deque()
        test = cosmicsimage(img, sigclip=3.0, objlim=3.0)
        num = 2
        for i in range(num):
            test.lacosmiciteration(True)
            test.clean()
            self._mask_data = np.logical_or(self._mask_data, np.array(test.mask, dtype='bool'))

    def set_mode(self, mode):
        """
        sets the mode to unmask or mask which equals mode = False or True
        """
        self.mode = mode

    def set_mask(self, mask_data):
        self.update_deque()
        self._mask_data = mask_data

    def save_mask(self, filename: str, flipud: bool = False):
        """Save current mask to file

        :param filename: Path of the file to write
        :param flipud: True to apply a vertical flip before saving the mask
        """
        im_array = np.int8(self.get_img())
        if flipud:
            im_array = np.flipud(im_array)

        if filename.endswith('.npy'):
            np.save(filename, im_array)
        elif filename.endswith('.edf'):
            fabio.edfimage.EdfImage(im_array).write(filename)
        else:
            im = Image.fromarray(im_array)
            try:
                im.save(filename, "tiff", compression="tiff_deflate")
            except OSError:
                try:
                    im.save(filename, "tiff", compression="tiff_adobe_deflate")
                except IOError:
                    im.save(filename, "tiff")

        self.filename = filename

    @staticmethod
    def read_mask_file(filename: str, flipud: bool = False) -> np.ndarray:
        """Load an image mask from file.

        :param filename: Path to the file to read
        :param flipud: True to apply a vertical flip to the mask
        """
        if filename.endswith('.npy'):
            data = np.load(filename)
        elif filename.endswith('.edf'):
            data = fabio.open(filename).data
        else:
            try:
                data = np.array(Image.open(filename))
            except IOError:
                data = np.loadtxt(filename)

        if flipud:
            data = np.flipud(data)
        return data

    def load_mask(self, filename: str, flipud: bool = False):
        """Load mask from file and replace the current one

        :param filename: Path to the file to read
        :param flipud: True to apply a vertical flip to the loaded mask
        """
        data = self.read_mask_file(filename, flipud)

        if self.mask_dimension == data.shape:
            self.filename = filename
            self.mask_dimension = data.shape
            self.reset_dimension()
            self.set_mask(data)
            return True
        return False

    def add_mask(self, filename: str, flipud: bool = False):
        """Combine mask loaded from file with the current one

        :param filename: Path to the file to read
        :param flipud: True to apply a vertical flip to the loaded mask
        """
        data = self.read_mask_file(filename, flipud)

        if self.get_mask().shape == data.shape:
            self._add_mask(data)
            return True
        return False

    def _add_mask(self, mask_data):
        self.update_deque()
        self._mask_data = np.logical_or(self._mask_data,
                                        np.array(mask_data, dtype='bool'))

    def find_center_of_circle_from_three_points(self, a, b, c):
        xa, ya = a.x(), a.y()
        xb, yb = b.x(), b.y()
        xc, yc = c.x(), c.y()
        # if (xa == xb and ya == yb) or (xa == xc and ya == yc) or (xb == xc and yb == yc):
        #     return None
        mid_ab_x = (xa + xb) / 2.0
        mid_ab_y = (ya + yb) / 2.0
        mid_bc_x = (xb + xc) / 2.0
        mid_bc_y = (yb + yc) / 2.0
        slope_ab = (yb - ya) / (xb - xa)
        slope_bc = (yc - yb) / (xc - xb)
        slope_p_ab = -1.0 / slope_ab
        slope_p_bc = -1.0 / slope_bc
        b_p_ab = mid_ab_y - slope_p_ab * mid_ab_x
        b_p_bc = mid_bc_y - slope_p_bc * mid_bc_x
        x0 = (b_p_bc - b_p_ab) / (slope_p_ab - slope_p_bc)
        y0 = slope_p_ab * x0 + b_p_ab
        self.center_for_arc = QtCore.QPointF(x0, y0)
        return self.center_for_arc

    @staticmethod
    def find_radius_of_circle_from_center_and_point(p0, a):
        r = sqrt((a.x() - p0.x()) ** 2 + (a.y() - p0.y()) ** 2)
        return r

    def find_n_angles_on_arc_from_three_points_around_p0(self, p0, pa, pb, pc, n):
        phi_a = self.calc_angle_from_center_and_point(p0, pa)
        phi_b = self.calc_angle_from_center_and_point(p0, pb)
        phi_c = self.calc_angle_from_center_and_point(p0, pc)
        if phi_c < phi_a < phi_b or phi_b < phi_c < phi_a:
            phi_range = np.linspace(phi_a, phi_c + 2 * np.pi, n)
        elif phi_a < phi_b < phi_c or phi_c < phi_b < phi_a:
            phi_range = np.linspace(phi_a, phi_c, n)
        elif phi_a < phi_c < phi_b or phi_b < phi_a < phi_c:
            phi_range = np.linspace(phi_a + 2 * np.pi, phi_c, n)
        else:
            return None
        return phi_range

    @staticmethod
    def calc_angle_from_center_and_point(p0, pa):
        phi = atan2(pa.y() - p0.y(), pa.x() - p0.x())
        return phi

    @staticmethod
    def calc_arc_points_from_angles(p0, r, width, phi_range):
        p = []
        for phi in phi_range:
            xn = p0.x() + (r - width) * cos(phi)
            yn = p0.y() + (r - width) * sin(phi)
            p.append(QtCore.QPointF(xn, yn))
        return p
