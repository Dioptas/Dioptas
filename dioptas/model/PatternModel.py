# SPDX-License-Identifier: MIT

import logging

import numpy as np
from xypattern import Pattern
from xypattern.auto_background import SmoothBrucknerBackground

from .util import Signal
from .util.HelperModule import FileNameIterator, get_base_name

logger = logging.getLogger(__name__)


class PatternModel:
    """
    Main Pattern handling class. Supporting:
        - setting background pattern
        - setting automatic background subtraction
        - file browsing

    all changes to the internal data throw a pattern_changed signal.
    """

    def __init__(self) -> None:
        super().__init__()
        self.pattern: Pattern = Pattern()
        self.pattern_filename: str = ""

        self.unit: str = ""
        self.file_iteration_mode: str = "number"
        self.file_name_iterator: FileNameIterator = FileNameIterator()

        self._background_pattern: Pattern | None = None

        self.pattern_changed: Signal = Signal()

    def set_pattern(
        self,
        x: np.ndarray,
        y: np.ndarray,
        filename: str = "",
        unit: str = "",
    ) -> None:
        """Set the current data pattern."""
        self.pattern_filename = filename
        self.pattern.data = (x, y)
        self.pattern.name = get_base_name(filename)
        self.unit = unit
        self.pattern_changed.emit()

    def load_pattern(self, filename: str) -> None:
        """Loads a pattern from a tabular pattern file (2 column txt file)."""
        logger.info("Load pattern: {0}".format(filename))
        self.pattern_filename = filename

        skiprows = 0
        if filename.endswith(".chi"):
            skiprows = 4
        self.pattern.load(filename, skiprows)
        self.file_name_iterator.update_filename(filename)
        self.pattern_changed.emit()

    def save_pattern(
        self, filename: str, header: str = "", subtract_background: bool = False
    ) -> None:
        """Saves the current data pattern."""
        logger.info("Saving pattern to %s", filename)
        self.pattern.save(filename, header, subtract_background, self.unit)

    def save_auto_background_as_pattern(
        self, filename: str, header: str | None = None
    ) -> None:
        """Saves the current automatic extracted background data pattern to file."""
        self.pattern.auto_background_pattern.save(filename, header, unit=self.unit)

    def get_pattern(self) -> Pattern:
        return self.pattern

    def load_next_file(self, step: int = 1) -> bool:
        """
        Loads the next file from a sequel of filenames (e.g. *_001.xy --> *_002.xy)
        It assumes that the file numbers are at the end of the filename
        """
        next_file_name = self.file_name_iterator.get_next_filename(
            mode=self.file_iteration_mode, step=step
        )
        if next_file_name is not None:
            self.load_pattern(next_file_name)
            return True
        return False

    def load_previous_file(self, step: int = 1) -> bool:
        """
        Loads the previous file from a sequel of filenames (e.g. *_002.xy --> *_001.xy)
        It assumes that the file numbers are at the end of the filename
        """
        next_file_name = self.file_name_iterator.get_previous_filename(
            mode=self.file_iteration_mode, step=step
        )
        if next_file_name is not None:
            self.load_pattern(next_file_name)
            return True
        return False

    def set_file_iteration_mode(self, mode: str) -> None:
        if mode == "number":
            self.file_iteration_mode = "number"
            self.file_name_iterator.create_timed_file_list = False
        elif mode == "time":
            self.file_iteration_mode = "time"
            self.file_name_iterator.create_timed_file_list = True
            self.file_name_iterator.update_filename(self.pattern_filename)

    @property
    def background_pattern(self) -> Pattern | None:
        return self._background_pattern

    @background_pattern.setter
    def background_pattern(self, pattern: Pattern | None) -> None:
        if pattern is not None:
            self.pattern.background_pattern = pattern
        else:
            self.pattern.background_pattern = None
        self._background_pattern = pattern
        self.pattern_changed.emit()

    def set_auto_background_subtraction(
        self,
        parameters: list[float],
        roi: list[float] | None = None,
    ) -> None:
        """
        Enables auto background extraction and removal from the data pattern.

        parameters is [window_width, iterations, polynomial_order].
        roi is [x_min, x_max] specifying the range for background subtraction.
        """
        logger.info("Setting auto background subtraction with parameters: %s", parameters)
        if roi is not None:
            x, _ = self.pattern.original_data
            roi = list(roi)

            # make sure the roi is within the data range
            if roi[0] > roi[1]:
                roi[0], roi[1] = roi[1], roi[0]
            x_step = x[1] - x[0]
            roi[0] = roi[0] if roi[0] > x[0] else x[0] - x_step / 2
            roi[0] = roi[0] if roi[0] < x[-1] - 1.5 * x_step else x[-1] - 1.5 * x_step
            roi[1] = roi[1] if roi[1] < x[-1] else x[-1] + x_step / 2
            roi[1] = roi[1] if roi[1] > x[0] + 1.5 * x_step else x[0] + 1.5 * x_step

        self.pattern.auto_bkg_roi = roi
        self.pattern.auto_bkg = SmoothBrucknerBackground(*parameters)
        self.pattern_changed.emit()

    def unset_auto_background_subtraction(self) -> None:
        """Disables auto background extraction and removal."""
        logger.info("Unsetting auto background subtraction")
        self.pattern.auto_bkg = None
        self.pattern_changed.emit()
