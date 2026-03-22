# SPDX-License-Identifier: MIT


class Point:
    """A simple 2D point with .x() and .y() methods.

    Duck-type compatible with QPointF so it can be used interchangeably
    in code that calls .x() and .y().
    """

    __slots__ = ("_x", "_y")

    def __init__(self, x, y):
        self._x = float(x)
        self._y = float(y)

    def x(self):
        return self._x

    def y(self):
        return self._y

    def __repr__(self):
        return f"Point({self._x}, {self._y})"

    def __eq__(self, other):
        if isinstance(other, Point):
            return self._x == other._x and self._y == other._y
        return NotImplemented
