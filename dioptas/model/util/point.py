# SPDX-License-Identifier: MIT


class Point:
    """A simple 2D point with .x() and .y() methods.

    Duck-type compatible with QPointF so it can be used interchangeably
    in code that calls .x() and .y().
    """

    __slots__ = ("_x", "_y")

    def __init__(self, x: float, y: float) -> None:
        self._x = float(x)
        self._y = float(y)

    def x(self) -> float:
        return self._x

    def y(self) -> float:
        return self._y

    def __repr__(self) -> str:
        return f"Point({self._x}, {self._y})"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Point):
            return self._x == other._x and self._y == other._y
        return NotImplemented
