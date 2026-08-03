# SPDX-License-Identifier: MIT

"""Arrangement of map points into the displayed grid.

A map is a list of integrated points in acquisition order plus a grid to lay
them out on. Real scans rarely map one-to-one onto that grid: beamlines drop
frames, scans run serpentine, and the fast axis is not always the one the
user wants running across. Everything that turns the ordered point list into
a 2D picture lives here, so the model only has to hold the numbers.

The layout is a two-step affair:

1. *slots* — a row-major list, one entry per grid cell, holding the index of
   the point shown there or None for a deliberate blank. This is what the
   user edits when they insert a dropped frame or reorder the list.
2. *transforms* — snake, transpose and the two mirrors, applied to the
   arranged grid. They express the scan convention rather than the data, so
   they stay separate from the slot list and can be toggled freely.

Blanks come out as NaN in the value grid and as :data:`BLANK` in the parallel
index grid, which is what maps a clicked cell back to a point.
"""

from __future__ import annotations

import os
import re

import numpy as np

__all__ = [
    "BLANK",
    "arrange",
    "default_slots",
    "fit_slots",
    "filename_number",
    "grid_for",
    "insert_blank",
    "move_slot",
    "possible_dimensions",
    "remove_blank",
    "slots_from_filenames",
]

#: index-grid entry for a cell that holds no point
BLANK = -1

#: largest gap-to-point ratio still treated as a numbering gap rather than as
#: filenames that simply happen to end in unrelated numbers
_MAX_GAP_SPAN_FACTOR = 4


def default_slots(num_points: int, num_slots: int) -> list[int | None]:
    """The plain arrangement: points in order, trailing cells left blank."""
    slots: list[int | None] = list(range(min(num_points, num_slots)))
    slots += [None] * (num_slots - len(slots))
    return slots


def fit_slots(
    slots: list[int | None] | None,
    num_points: int,
    num_slots: int,
    excluded=(),
) -> list[int | None]:
    """Normalizes *slots* to a usable arrangement of *num_points* points.

    Every point index appears exactly once: duplicates and indices left over
    from a shorter point list are dropped, and points that are not placed
    anywhere are appended. That way growing the grid or reloading a map with
    a different number of files degrades into the sequential arrangement for
    the part the stored slots say nothing about, instead of losing points.

    *excluded* points are left out entirely — their cell disappears and the
    points after them close up, instead of an empty box staying behind. The
    stored arrangement is not touched, so including a point again puts it
    back where it was.
    """
    excluded = {int(index) for index in excluded}
    if slots is None:
        slots = default_slots(num_points, num_slots)

    seen: set[int] = set()
    kept: list[int | None] = []
    for entry in slots:
        if entry is None:
            kept.append(None)
            continue
        index = int(entry)
        if index in excluded:
            # dropped without a placeholder: the cell itself goes
            continue
        if index < 0 or index >= num_points or index in seen:
            # a stale index leaves a blank rather than shifting the rest,
            # so the surrounding arrangement survives
            kept.append(None)
            continue
        seen.add(index)
        kept.append(index)

    unplaced = [
        i for i in range(num_points) if i not in seen and i not in excluded
    ]
    if unplaced:
        # fill existing blanks first, then extend
        for position, entry in enumerate(kept):
            if not unplaced:
                break
            if entry is None:
                kept[position] = unplaced.pop(0)
        kept.extend(unplaced)

    if len(kept) < num_slots:
        kept += [None] * (num_slots - len(kept))
    return kept[:num_slots]


def arrange(
    values,
    dimension: tuple[int, int],
    slots: list[int | None] | None = None,
    snake: bool = False,
    transpose: bool = False,
    flip_horizontal: bool = False,
    flip_vertical: bool = False,
    excluded=(),
) -> tuple[np.ndarray, np.ndarray]:
    """Lays *values* out on the grid, returning (value grid, index grid).

    The index grid holds the point index behind every cell, or :data:`BLANK`,
    and is what turns a clicked cell back into a point. Excluded points have
    no cell at all: the points after them close up and the freed cell joins
    the blanks at the end.
    """
    rows, columns = int(dimension[0]), int(dimension[1])
    num_slots = rows * columns
    values = np.asarray(values, dtype=float)
    num_points = len(values)

    slots = fit_slots(slots, num_points, num_slots, excluded=excluded)

    index_grid = np.full(num_slots, BLANK, dtype=int)
    for slot, point in enumerate(slots):
        if point is not None:
            index_grid[slot] = point
    index_grid = index_grid.reshape(rows, columns)

    if snake:
        index_grid[1::2] = index_grid[1::2, ::-1]
    if transpose:
        index_grid = index_grid.T
    if flip_vertical:
        index_grid = index_grid[::-1]
    if flip_horizontal:
        index_grid = index_grid[:, ::-1]
    index_grid = np.ascontiguousarray(index_grid)

    value_grid = np.full(index_grid.shape, np.nan, dtype=float)
    filled = index_grid != BLANK
    value_grid[filled] = values[index_grid[filled]]

    return value_grid, index_grid


def possible_dimensions(num_points: int) -> list[tuple[int, int]]:
    """Grids that hold exactly *num_points* points, squarest first."""
    dimension_pairs = []
    for n in range(1, int(np.floor(np.sqrt(num_points + 1))) + 1):
        if num_points % n == 0:
            dim1 = n
            dim2 = num_points // n
            dimension_pairs.append((dim1, dim2))
            if dim1 != dim2:
                dimension_pairs.append((dim2, dim1))
    dimension_pairs.sort(key=lambda x: ((x[0] + x[1]) / 2 - np.sqrt(num_points)) ** 2)
    return dimension_pairs


def grid_for(num_slots: int, columns: int) -> tuple[int, int]:
    """The smallest grid of *columns* columns that holds *num_slots* cells."""
    columns = max(1, int(columns))
    rows = max(1, -(-int(num_slots) // columns))
    return rows, columns


def insert_blank(slots: list[int | None], position: int) -> list[int | None]:
    """Inserts a blank cell at *position*, shifting everything after it."""
    slots = list(slots)
    position = max(0, min(int(position), len(slots)))
    slots.insert(position, None)
    return slots


def remove_blank(slots: list[int | None], position: int) -> list[int | None]:
    """Removes the blank cell at *position*, pulling everything after it up.

    Only blanks can be removed: dropping a cell that holds a point would take
    the point out of the arrangement entirely, which is what excluding it is
    for.
    """
    slots = list(slots)
    if not (0 <= position < len(slots)) or slots[position] is not None:
        return slots
    del slots[position]
    return slots


def move_slot(slots: list[int | None], source: int, target: int) -> list[int | None]:
    """Moves the cell at *source* to *target*, closing the gap behind it."""
    slots = list(slots)
    if not (0 <= source < len(slots)):
        return slots
    entry = slots.pop(source)
    target = max(0, min(int(target), len(slots)))
    slots.insert(target, entry)
    return slots


_TRAILING_NUMBER = re.compile(r"(\d+)(?!.*\d)")


def filename_number(filename: str) -> int | None:
    """The last run of digits in a filename's stem, as an int."""
    stem = os.path.splitext(os.path.basename(filename))[0]
    match = _TRAILING_NUMBER.search(stem)
    if match is None:
        return None
    return int(match.group(1))


def slots_from_filenames(filenames: list[str]) -> list[int | None] | None:
    """Slots with a blank wherever the filename numbering skips a value.

    Beamline scans write consecutively numbered files, so a missing number is
    a dropped frame — and a dropped frame silently shifts every point after
    it into the wrong cell. Returns None when the numbering says nothing
    useful: unnumbered or non-increasing names, no gaps at all, or gaps so
    large that the numbers are evidently not a scan index.
    """
    if len(filenames) < 2:
        return None

    numbers = [filename_number(name) for name in filenames]
    if any(number is None for number in numbers):
        return None
    if any(b <= a for a, b in zip(numbers, numbers[1:])):
        return None

    span = numbers[-1] - numbers[0] + 1
    if span == len(numbers):
        return None
    if span > len(numbers) * _MAX_GAP_SPAN_FACTOR:
        return None

    slots: list[int | None] = [None] * span
    for point, number in enumerate(numbers):
        slots[number - numbers[0]] = point
    return slots
