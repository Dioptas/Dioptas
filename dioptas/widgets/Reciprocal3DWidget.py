# SPDX-License-Identifier: MIT
"""CPU-rendered, pickable perspective cloud with shaded sphere markers."""

import numpy as np
from qtpy import QtCore, QtGui, QtWidgets


def _rotation(axis, angle):
    c, s = np.cos(angle), np.sin(angle)
    if axis == 0:
        return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])


class Reciprocal3DWidget(QtWidgets.QWidget):
    spot_selected = QtCore.Signal(int, int)
    hovered = QtCore.Signal(str)
    colours = ("#ffac45", "#48d8eb", "#969da6")

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(650, 420)
        self.setMouseTracking(True)
        self.coords = np.empty((0, 3))
        self.tracks = self.frames = self.status = np.empty(0, dtype=int)
        self.selected_track = None
        self.basis = np.eye(3)
        self.guides = np.empty((0, 3))
        self.show_guides = True
        self.point_size_scale = 1.0
        self.perspective_enabled = True
        self._sphere_sprites = None
        self.names = ("q1", "q2", "q3")
        self._press = None
        self.reset_view()

    def set_points(self, coords, tracks, frames, status, basis, names):
        self.coords, self.tracks, self.frames, self.status = (
            coords,
            tracks,
            frames,
            status,
        )
        self.basis, self.names = basis, names
        self.centre = (
            (coords.min(axis=0) + coords.max(axis=0)) / 2
            if len(coords)
            else np.zeros(3)
        )
        self.radius = (
            max(float(np.max(np.linalg.norm(coords - self.centre, axis=1))), 1e-6)
            if len(coords)
            else 1
        )
        self._make_guides()
        self.reset_view()

    def _make_guides(self):
        self.guides = np.empty((0, 3))
        if not len(self.coords):
            return
        fractional = np.linalg.solve(self.basis.T, self.coords.T).T
        lo = np.minimum(np.floor(fractional.min(axis=0)), -1)
        hi = np.maximum(np.ceil(fractional.max(axis=0)), 1)
        segments = []
        for x, y, normal in ((0, 1, 2), (0, 2, 1), (1, 2, 0)):
            for a, b in ((x, y), (y, x)):
                step = max(1, int(np.ceil((hi[a] - lo[a]) / 18)))
                for value in np.arange(lo[a], hi[a] + 1, step):
                    line = np.zeros((2, 3))
                    line[:, a] = value
                    line[:, b] = (lo[b], hi[b])
                    segments.extend(line @ self.basis)
        self.guides = np.array(segments)

    def reset_view(self):
        self.rotation = _rotation(1, np.deg2rad(35)) @ _rotation(0, np.deg2rad(-25))
        self.zoom = 1.0
        self.pan = np.zeros(2)
        if len(self.coords):
            self.centre = (self.coords.min(axis=0) + self.coords.max(axis=0)) / 2
            self.radius = max(
                float(np.max(np.linalg.norm(self.coords - self.centre, axis=1))), 1e-6
            )
        else:
            self.centre, self.radius = np.zeros(3), 1.0
        self.update()

    def orient_plane(self, x, y):
        horizontal = self.basis[x] / np.linalg.norm(self.basis[x])
        normal = np.cross(self.basis[x], self.basis[y])
        normal /= np.linalg.norm(normal)
        vertical = np.cross(normal, horizontal)
        self.rotation = np.array([horizontal, vertical, normal])
        self.pan = np.zeros(2)
        self.zoom = 1.0
        self.update()

    def project(self, points):
        view = (points - self.centre) @ self.rotation.T
        scale = 0.43 * min(self.width(), self.height()) * self.zoom / self.radius
        xy = (
            view[:, :2] * self._perspective(view[:, 2])[:, None] * [scale, -scale]
            + [self.width() / 2, self.height() / 2]
            + self.pan
        )
        return xy, view[:, 2]

    def _perspective(self, depth):
        if not self.perspective_enabled:
            return np.ones_like(depth)
        # Camera is three cloud radii in front of the rotation pivot. All
        # measured points stay beyond the near plane, including after centring.
        distance = 3 * self.radius
        return distance / np.maximum(distance - depth, 0.1 * self.radius)

    def _point_diameters(self, depth):
        return self._point_size() * self._perspective(depth)

    def _make_sphere_sprites(self):
        # Cache a lit sphere for each population. Scaling these sprites avoids
        # creating a gradient for every measured point on every mouse move.
        sprites = []
        for colour in self.colours:
            pixmap = QtGui.QPixmap(64, 64)
            pixmap.fill(QtCore.Qt.transparent)
            painter = QtGui.QPainter(pixmap)
            painter.setRenderHint(QtGui.QPainter.Antialiasing)
            base = QtGui.QColor(colour)
            gradient = QtGui.QRadialGradient(24, 22, 39)
            gradient.setColorAt(0, base.lighter(190))
            gradient.setColorAt(0.25, base.lighter(135))
            gradient.setColorAt(0.55, base)
            gradient.setColorAt(1, base.darker(280))
            painter.setBrush(QtGui.QBrush(gradient))
            painter.setPen(QtGui.QPen(QtGui.QColor("#050608"), 2))
            painter.drawEllipse(QtCore.QRectF(1, 1, 62, 62))
            painter.end()
            sprites.append(pixmap)
        self._sphere_sprites = sprites

    def select_track(self, track):
        self.selected_track = track
        self.update()

    def centre_selected(self):
        points = self.coords[self.tracks == self.selected_track]
        if len(points):
            self.centre = points.mean(axis=0)
            self.radius = max(
                float(np.max(np.linalg.norm(self.coords - self.centre, axis=1))), 1e-6
            )
            self.pan = np.zeros(2)
            self.update()

    def _point_size(self):
        # Grow gently in screen pixels as the cloud spreads out, without
        # allowing markers to grow at the full geometric zoom rate.
        base = 5.5 if len(self.coords) < 10000 else 3.5
        return base * self.point_size_scale * min(1.8, self.zoom**0.18)

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.fillRect(self.rect(), QtGui.QColor("#101216"))
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        painter.setRenderHint(QtGui.QPainter.SmoothPixmapTransform)
        if self.show_guides and len(self.guides):
            xy, guide_depth = self.project(self.guides)
            painter.setPen(QtGui.QPen(QtGui.QColor("#39404c"), 0.7))
            lines = xy.reshape(-1, 2, 2)
            # Reference guides can extend beyond the measured cloud. Omit
            # segments crossing the camera's near plane rather than invert them.
            if self.perspective_enabled:
                lines = lines[
                    (guide_depth.reshape(-1, 2) < 2.9 * self.radius).all(axis=1)
                ]
            for a, b in lines:
                painter.drawLine(
                    QtCore.QPointF(*map(float, a)), QtCore.QPointF(*map(float, b))
                )
        if len(self.coords):
            xy, depth = self.project(self.coords)
            diameters = self._point_diameters(depth)
            if self._sphere_sprites is None:
                self._make_sphere_sprites()
            # Exact back-to-front order keeps the same frontmost sphere visible
            # and selectable even where depths are very close.
            for row in np.argsort(depth, kind="stable"):
                x, y = xy[row]
                diameter = float(diameters[row] + 1.5)
                if (
                    x + diameter < 0
                    or y + diameter < 0
                    or x - diameter > self.width()
                    or y - diameter > self.height()
                ):
                    continue
                painter.drawPixmap(
                    QtCore.QRectF(
                        float(x - diameter / 2),
                        float(y - diameter / 2),
                        diameter,
                        diameter,
                    ),
                    self._sphere_sprites[self.status[row]],
                    QtCore.QRectF(0, 0, 64, 64),
                )
            painter.setBrush(QtCore.Qt.NoBrush)
            for row in np.flatnonzero(self.tracks == self.selected_track):
                point = xy[row]
                selection_radius = max(8.0, float(diameters[row]) / 2 + 4)
                centre = QtCore.QPointF(*map(float, point))
                painter.setPen(QtGui.QPen(QtGui.QColor("black"), 5))
                painter.drawEllipse(centre, selection_radius, selection_radius)
                painter.setPen(QtGui.QPen(QtGui.QColor("#ff55dd"), 2.5))
                painter.drawEllipse(centre, selection_radius, selection_radius)
        else:
            painter.setPen(QtGui.QColor("#c8cdd6"))
            painter.drawText(
                self.rect(), QtCore.Qt.AlignCenter, "No reciprocal points to display"
            )
        origin = np.array([70.0, self.height() - 65.0])
        for i, colour in enumerate(("#ff6c6c", "#69db87", "#7daeff")):
            direction = self.rotation[:, i]
            end = origin + direction[:2] * [42, -42]
            painter.setPen(QtGui.QPen(QtGui.QColor(colour), 2))
            painter.drawLine(QtCore.QPointF(*origin), QtCore.QPointF(*end))
            painter.drawText(QtCore.QPointF(*(end + [4, -3])), self.names[i])
        painter.end()

    def _pick(self, pos):
        if not len(self.coords):
            return None
        xy, depth = self.project(self.coords)
        distance = np.sum((xy - pos) ** 2, axis=1)
        diameters = self._point_diameters(depth)
        # Prefer the actual sphere under the cursor over a hidden sphere whose
        # centre happens to be closer. Use the padded target only in empty space.
        rows = np.flatnonzero(distance <= ((diameters + 1.5) / 2) ** 2)
        if not len(rows):
            pick_radius = np.maximum(9.0, diameters / 2 + 6)
            rows = np.flatnonzero(distance <= pick_radius**2)
            if not len(rows):
                return None
            rows = rows[distance[rows] <= distance[rows].min() + 4]
        rows = rows[::-1]  # Last painted wins exact depth ties.
        return int(rows[np.argmax(depth[rows])])

    @staticmethod
    def _pos(event):
        point = event.position() if hasattr(event, "position") else event.pos()
        return np.array([point.x(), point.y()])

    def mousePressEvent(self, event):
        self._press = self._last = self._pos(event)
        self._dragged = False
        self._panning = event.button() != QtCore.Qt.LeftButton or bool(
            event.modifiers() & QtCore.Qt.ControlModifier
        )
        event.accept()

    def mouseMoveEvent(self, event):
        pos = self._pos(event)
        if self._press is not None:
            if np.linalg.norm(pos - self._press) > 3:
                self._dragged = True
            delta = pos - self._last
            if self._dragged:
                if self._panning:
                    self.pan += delta
                else:
                    self.rotation = (
                        _rotation(0, np.deg2rad(delta[1] * 0.45))
                        @ _rotation(1, np.deg2rad(delta[0] * 0.45))
                        @ self.rotation
                    )
                self.update()
            self._last = pos
        else:
            row = self._pick(pos)
            if row is not None:
                values = ", ".join(f"{v:.4f}" for v in self.coords[row])
                frame = (
                    f" · frame {self.frames[row] + 1}" if self.frames[row] >= 0 else ""
                )
                self.hovered.emit(f"Spot {self.tracks[row] + 1}{frame} · ({values})")
            else:
                self.hovered.emit(" ")
        event.accept()

    def mouseReleaseEvent(self, event):
        if self._press is not None and not self._dragged:
            if self._panning:
                self.zoom = max(1.0, self.zoom / 2)
                if self.zoom == 1:
                    self.pan = np.zeros(2)
                self.update()
            else:
                row = self._pick(self._pos(event))
                if row is not None:
                    self.spot_selected.emit(
                        int(self.tracks[row]), int(self.frames[row])
                    )
        self._press = None
        event.accept()

    def mouseDoubleClickEvent(self, event):
        self._press = None
        self.reset_view()
        event.accept()

    def wheelEvent(self, event):
        factor = np.exp(event.angleDelta().y() / 120 * 0.15)
        new_zoom = float(np.clip(self.zoom * factor, 1, 40))
        centre = np.array([self.width() / 2, self.height() / 2])
        cursor = self._pos(event) - centre
        self.pan = cursor - new_zoom / self.zoom * (cursor - self.pan)
        self.zoom = new_zoom
        if self.zoom == 1:
            self.pan = np.zeros(2)
        self.update()
        event.accept()
