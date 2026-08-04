# SPDX-License-Identifier: MIT

from __future__ import annotations

import logging
from math import sqrt, atan2, cos, sin

import fabio
import numpy as np
import skimage.draw
from PIL import Image

from .util.cosmics import cosmicsimage
from .util import Signal
from .state import MaskParams
from .util.point import Point
from .util.file_type import file_loading_error

logger = logging.getLogger(__name__)


class MaskModel:
    def __init__(self, mask_dimension: tuple[int, int] = (2048, 2048)) -> None:
        # All user-settable parameters live in the evented params dataclass;
        # the properties below delegate to it.
        self.params: MaskParams = MaskParams()

        self.mask_dimension: tuple[int, int] = mask_dimension
        self.reset_dimension()
        self.filename: str = ''

        self._mask_data: np.ndarray = np.zeros(self.mask_dimension, dtype=bool)

        self.mask_changed: Signal = Signal()

        self.mask_plugin_manager = None  # set by Configuration

    @property
    def mode(self) -> bool:
        return self.params.mode

    @mode.setter
    def mode(self, new_mode: bool) -> None:
        self.params.mode = new_mode

    @property
    def roi(self) -> tuple[int, int, int, int] | None:
        return self.params.roi

    @roi.setter
    def roi(self, new_roi: tuple[int, int, int, int] | None) -> None:
        self.params.roi = new_roi

    def set_dimension(self, mask_dimension: tuple[int, int]) -> None:
        if not np.array_equal(mask_dimension, self.mask_dimension):
            self.mask_dimension = mask_dimension
            self.reset_dimension()
            if self.mask_plugin_manager is not None:
                self.mask_plugin_manager.update_shape(mask_dimension)
            self.mask_changed.emit()

    def reset_dimension(self) -> None:
        if self.mask_dimension is not None:
            self._mask_data = np.zeros(self.mask_dimension, dtype=bool)

    @property
    def roi_mask(self) -> np.ndarray | None:
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

    def get_mask(self) -> np.ndarray:
        """Return combined mask: user-drawn + plugins + roi. Used for integration."""
        mask = self._mask_data
        mask = self._apply_plugin_masks(mask)
        if self.roi is not None:
            mask = np.logical_or(mask, self.roi_mask)
        return mask

    def get_display_mask(self) -> np.ndarray:
        """Return mask for display: user-drawn + plugins (no roi). Used by mask view."""
        return self._apply_plugin_masks(self._mask_data)

    def get_img(self) -> np.ndarray:
        return self._mask_data

    def _apply_plugin_masks(self, mask: np.ndarray) -> np.ndarray:
        if self.mask_plugin_manager is not None:
            plugin_mask = self.mask_plugin_manager.get_combined_mask()
            if plugin_mask is not None:
                mask = np.logical_or(mask, plugin_mask)
        return mask

    def set_mask_data(self, mask_data: np.ndarray) -> None:
        """Replaces the user-drawn mask without any further bookkeeping.

        Used by the undo history to write a snapshot back. Unlike
        :meth:`set_mask` this does not touch ``filename``, so restoring a step
        does not claim the mask came from a file.
        """
        self._mask_data = mask_data
        self.mask_dimension = mask_data.shape
        self.mask_changed.emit()

    def imprint_plugin_mask(self, plugin_name: str) -> None:
        """Bake a plugin's current mask into the user-drawn mask and disable it.

        Both effects land in one undo step because the history snapshots the
        mask data and the plugins' enabled state together — undoing restores
        the previous mask and re-enables the plugin without this method
        having to record anything.
        """
        if self.mask_plugin_manager is None:
            return
        entry = self.mask_plugin_manager.plugins.get(plugin_name)
        if entry is None or entry.cached_mask is None:
            return
        self._mask_data = np.logical_or(self._mask_data, entry.cached_mask)
        self.mask_plugin_manager.set_enabled(plugin_name, False)
        self.mask_changed.emit()

    def mask_below_threshold(self, img_data: np.ndarray, threshold: float) -> None:
        logger.debug("Masking below threshold: %s", threshold)
        self._mask_data[img_data < threshold] = self.mode
        self.mask_changed.emit()

    def mask_above_threshold(self, img_data: np.ndarray, threshold: float) -> None:
        logger.debug("Masking above threshold: %s", threshold)
        self._mask_data[img_data > threshold] = self.mode
        self.mask_changed.emit()

    def mask_QGraphicsRectItem(self, QGraphicsRectItem: object) -> None:
        rect = QGraphicsRectItem.rect()
        self.mask_rect(rect.top(), rect.left(), rect.height(), rect.width())

    def mask_QGraphicsPolygonItem(self, QGraphicsPolygonItem: object) -> None:
        """Masks a polygon given by a QGraphicsPolygonItem from the QtWidgets Library.
        Uses the skimage.draw.polygon function.
        """

        # get polygon points
        poly_list = list(QGraphicsPolygonItem.vertices)
        x = np.zeros(len(poly_list))
        y = np.zeros(len(poly_list))

        for i, point in enumerate(poly_list):
            x[i] = point.x()
            y[i] = point.y()
        self.mask_polygon(x, y)

    def mask_QGraphicsEllipseItem(self, QGraphicsEllipseItem: object) -> None:
        """Masks an Ellipse given by a QGraphicsEllipseItem from the QtWidgets
        Library. Uses the skimage.draw.ellipse function.
        """
        bounding_rect = QGraphicsEllipseItem.rect()
        cx = bounding_rect.center().x()
        cy = bounding_rect.center().y()
        x_radius = bounding_rect.width() * 0.5
        y_radius = bounding_rect.height() * 0.5
        self.mask_ellipse(int(cx), int(cy), int(x_radius), int(y_radius))

    def mask_rect(self, x: float, y: float, width: float, height: float) -> None:
        """Masks a rectangle. x and y parameters are the upper left corner
        of the rectangle.
        """
        logger.debug("Masking rectangle at (%s, %s) size %sx%s", x, y, width, height)
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
        self.mask_changed.emit()

    def mask_polygon(self, x: np.ndarray, y: np.ndarray) -> None:
        """Masks a polygon with given vertices. x and y are arrays of
        the polygon vertices. Uses the draw.polygon implementation of
        the skimage library.
        """
        logger.debug("Masking polygon with %d vertices", len(x))
        rr, cc = skimage.draw.polygon(y, x, self._mask_data.shape)
        self._mask_data[rr, cc] = self.mode
        self.mask_changed.emit()

    def mask_ellipse(self, cx: int, cy: int, x_radius: int, y_radius: int) -> None:
        """Masks an ellipse with center coordinates (cx, cy) and the radii
        given. Uses the draw.ellipse implementation of the skimage library.
        """
        logger.debug("Masking ellipse at (%.1f, %.1f)", cx, cy)
        rr, cc = skimage.draw.ellipse(
            cy, cx, y_radius, x_radius, shape=self._mask_data.shape)
        self._mask_data[rr, cc] = self.mode
        self.mask_changed.emit()

    def grow(self) -> None:
        logger.debug("Growing mask")
        self._mask_data[1:, :] = np.logical_or(self._mask_data[1:, :], self._mask_data[:-1, :])
        self._mask_data[:-1, :] = np.logical_or(self._mask_data[:-1, :], self._mask_data[1:, :])
        self._mask_data[:, 1:] = np.logical_or(self._mask_data[:, 1:], self._mask_data[:, :-1])
        self._mask_data[:, :-1] = np.logical_or(self._mask_data[:, :-1], self._mask_data[:, 1:])
        self.mask_changed.emit()

    def shrink(self) -> None:
        logger.debug("Shrinking mask")
        self._mask_data[1:, :] = np.logical_and(self._mask_data[1:, :], self._mask_data[:-1, :])
        self._mask_data[:-1, :] = np.logical_and(self._mask_data[:-1, :], self._mask_data[1:, :])
        self._mask_data[:, 1:] = np.logical_and(self._mask_data[:, 1:], self._mask_data[:, :-1])
        self._mask_data[:, :-1] = np.logical_and(self._mask_data[:, :-1], self._mask_data[:, 1:])
        self.mask_changed.emit()

    def invert_mask(self) -> None:
        logger.debug("Inverting mask")
        self._mask_data = np.logical_not(self._mask_data)
        self.mask_changed.emit()

    def clear_mask(self) -> None:
        logger.debug("Clearing mask")
        self._mask_data[:, :] = False
        self.mask_changed.emit()

    def remove_cosmic(self, img: np.ndarray) -> None:
        test = cosmicsimage(img, sigclip=3.0, objlim=3.0)
        num = 2
        for i in range(num):
            test.lacosmiciteration(True)
            test.clean()
            self._mask_data = np.logical_or(self._mask_data, np.array(test.mask, dtype='bool'))
        self.mask_changed.emit()

    def set_mode(self, mode: bool) -> None:
        """Sets the mode to unmask or mask which equals mode = False or True."""
        self.mode = mode

    def set_mask(self, mask_data: np.ndarray) -> None:
        self._mask_data = mask_data
        self.mask_dimension = mask_data.shape
        self.mask_changed.emit()

    def save_mask(self, filename: str, flipud: bool = False) -> None:
        """Save current mask to file."""
        logger.info("Saving mask to %s", filename)
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
        """Load an image mask from file."""
        try:
            if filename.endswith('.npy'):
                data = np.load(filename)
            elif filename.endswith('.edf'):
                data = fabio.open(filename).data
            else:
                try:
                    data = np.array(Image.open(filename))
                except IOError:
                    data = np.loadtxt(filename)
        except Exception as e:
            raise file_loading_error(filename, "mask") from e

        if flipud:
            data = np.flipud(data)
        return data

    def load_mask(self, filename: str, flipud: bool = False) -> bool:
        """Load mask from file and replace the current one."""
        logger.info("Loading mask from %s", filename)
        data = self.read_mask_file(filename, flipud)

        if self.mask_dimension == data.shape:
            self.filename = filename
            self.mask_dimension = data.shape
            self.reset_dimension()
            self.set_mask(data)
            return True
        return False

    def add_mask(self, filename: str, flipud: bool = False) -> bool:
        """Combine mask loaded from file with the current one."""
        logger.info("Adding mask from %s", filename)
        data = self.read_mask_file(filename, flipud)

        if self.get_mask().shape == data.shape:
            self._add_mask(data)
            return True
        return False

    def _add_mask(self, mask_data: np.ndarray) -> None:
        self._mask_data = np.logical_or(self._mask_data,
                                        np.array(mask_data, dtype='bool'))

    def find_center_of_circle_from_three_points(
        self, a: Point, b: Point, c: Point
    ) -> Point | None:
        xa, ya = a.x(), a.y()
        xb, yb = b.x(), b.y()
        xc, yc = c.x(), c.y()
        # Robust circumcenter calculation; returns None for collinear/degenerate points.
        denom = 2.0 * (xa * (yb - yc) + xb * (yc - ya) + xc * (ya - yb))
        if abs(denom) < 1e-12:
            return None

        xa2_ya2 = xa * xa + ya * ya
        xb2_yb2 = xb * xb + yb * yb
        xc2_yc2 = xc * xc + yc * yc
        x0 = (xa2_ya2 * (yb - yc) + xb2_yb2 * (yc - ya) + xc2_yc2 * (ya - yb)) / denom
        y0 = (xa2_ya2 * (xc - xb) + xb2_yb2 * (xa - xc) + xc2_yc2 * (xb - xa)) / denom
        self.center_for_arc = Point(x0, y0)
        return self.center_for_arc

    @staticmethod
    def find_radius_of_circle_from_center_and_point(p0: Point, a: Point) -> float:
        r = sqrt((a.x() - p0.x()) ** 2 + (a.y() - p0.y()) ** 2)
        return r

    def find_n_angles_on_arc_from_three_points_around_p0(
        self, p0: Point, pa: Point, pb: Point, pc: Point, n: int
    ) -> np.ndarray | None:
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
    def calc_angle_from_center_and_point(p0: Point, pa: Point) -> float:
        phi = atan2(pa.y() - p0.y(), pa.x() - p0.x())
        return phi

    @staticmethod
    def calc_arc_points_from_angles(
        p0: Point, r: float, width: float, phi_range: np.ndarray
    ) -> list[Point]:
        p = []
        for phi in phi_range:
            xn = p0.x() + (r - width) * cos(phi)
            yn = p0.y() + (r - width) * sin(phi)
            p.append(Point(xn, yn))
        return p
