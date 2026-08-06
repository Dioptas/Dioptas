# SPDX-License-Identifier: MIT

import logging
import os

import numpy as np
from xypattern import Pattern
from xypattern.auto_background import SmoothBrucknerBackground

from .util import Signal
from .state import PatternParams
from .util.HelperModule import FileNameIterator, get_base_name
from .util.file_type import file_loading_error

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
        #: how the current pattern came to be: "integrated" or "file"
        self.pattern_source: str = "integrated"
        #: guards the reconcile against the sync's own partial writes
        self._syncing_file_params: bool = False

        # All user-settable parameters live in the evented params dataclass;
        # the properties below delegate to it.
        self.params: PatternParams = PatternParams()

        self.file_name_iterator: FileNameIterator = FileNameIterator()

        self._background_pattern: Pattern | None = None

        self.pattern_changed: Signal = Signal()

        self._applying_auto_bkg: bool = False

        # the auto-background params are canonical; this reaction pushes
        # them into the Pattern, which owns the computation, so a direct
        # params write behaves exactly like set_auto_background_subtraction
        self.params.events.connect(self._on_params_changed)

    _AUTO_BKG_FIELDS = (
        "auto_bkg_enabled",
        "auto_bkg_smoothing",
        "auto_bkg_iterations",
        "auto_bkg_poly_order",
        "auto_bkg_roi",
    )

    def _sync_file_params(self) -> None:
        """Writes the on-screen pattern source into the params (see ImgModel:
        attrs mirror the screen, params are the canonical undoable state).

        Guarded like ImgModel's: the two fields are written separately, and
        the reconcile must not act on the first while the second is stale.
        """
        self._syncing_file_params = True
        try:
            self.params.pattern_source = self.pattern_source
            self.params.pattern_filename = self.pattern_filename
        finally:
            self._syncing_file_params = False

    def _reconcile_file_params(self) -> None:
        """Makes the screen follow the pattern-file params (undo/restore).

        Only patterns that came from a *file* are reloaded: an "integrated"
        pattern's filename names the image it was integrated from, and the
        pattern itself is derived — the integration recomputes it from the
        restored image and calibration.
        """
        params = self.params
        if (params.pattern_source, params.pattern_filename) == (
            self.pattern_source,
            self.pattern_filename,
        ):
            return
        if params.pattern_source != "file":
            # nothing to re-read; the params simply describe the new source
            self.pattern_source = params.pattern_source
            self.pattern_filename = params.pattern_filename
            return
        if not os.path.isfile(params.pattern_filename):
            logger.warning(
                "Cannot restore pattern %s: the file is no longer there",
                params.pattern_filename,
            )
            self._sync_file_params()
            return
        try:
            self.load_pattern(params.pattern_filename)
        except Exception:
            logger.exception("Failed to restore pattern %s", params.pattern_filename)
            self._sync_file_params()

    def _on_params_changed(self, info) -> None:
        if info.signal.name in ("pattern_source", "pattern_filename"):
            if not self._syncing_file_params:
                self._reconcile_file_params()
            return
        if info.signal.name in self._AUTO_BKG_FIELDS and not self._applying_auto_bkg:
            self._apply_auto_background()

    def _apply_auto_background(self) -> None:
        """Applies the auto-background params to the pattern."""
        if not self.params.auto_bkg_enabled:
            self.pattern.auto_bkg = None
            self.pattern_changed.emit()
            return

        roi = self.params.auto_bkg_roi
        self.pattern.auto_bkg_roi = list(roi) if roi is not None else None
        self.pattern.auto_bkg = SmoothBrucknerBackground(
            self.params.auto_bkg_smoothing,
            self.params.auto_bkg_iterations,
            self.params.auto_bkg_poly_order,
        )
        self.pattern_changed.emit()

    def _clamped_roi(self, roi: list[float] | None) -> list[float] | None:
        """Keeps a user-supplied background roi inside the data range.

        Only applied at the API boundary: a roi restored from a project file
        must not be clamped against the pattern that happens to be loaded at
        that moment."""
        if roi is None:
            return None
        x, _ = self.pattern.original_data
        if x is None or len(x) < 2:
            return list(roi)

        roi = list(roi)
        if roi[0] > roi[1]:
            roi[0], roi[1] = roi[1], roi[0]
        x_step = x[1] - x[0]
        roi[0] = roi[0] if roi[0] > x[0] else x[0] - x_step / 2
        roi[0] = roi[0] if roi[0] < x[-1] - 1.5 * x_step else x[-1] - 1.5 * x_step
        roi[1] = roi[1] if roi[1] < x[-1] else x[-1] + x_step / 2
        roi[1] = roi[1] if roi[1] > x[0] + 1.5 * x_step else x[0] + 1.5 * x_step
        return roi

    @property
    def unit(self) -> str:
        return self.params.unit

    @unit.setter
    def unit(self, new_unit: str) -> None:
        self.params.unit = new_unit

    @property
    def file_iteration_mode(self) -> str:
        return self.params.file_iteration_mode

    @file_iteration_mode.setter
    def file_iteration_mode(self, new_mode: str) -> None:
        self.params.file_iteration_mode = new_mode

    def set_pattern(
        self,
        x: np.ndarray,
        y: np.ndarray,
        filename: str = "",
        unit: str = "",
    ) -> None:
        """Set the current data pattern."""
        self.pattern_filename = filename
        self.pattern_source = "integrated"
        self.pattern.data = (x, y)
        self.pattern.name = get_base_name(filename)
        self.unit = unit
        self._sync_file_params()
        self.pattern_changed.emit()

    def load_pattern(self, filename: str) -> None:
        """Loads a pattern from a tabular pattern file (2 column txt file)."""
        logger.info("Load pattern: {0}".format(filename))

        skiprows = 0
        if filename.endswith(".chi"):
            skiprows = 4
        # read the file before touching any state, so a failing load leaves
        # the model exactly as it was
        try:
            self.pattern.load(filename, skiprows)
        except (ValueError, IndexError, OSError, UnicodeDecodeError) as e:
            raise file_loading_error(filename, "pattern") from e

        self.pattern_filename = filename
        self.pattern_source = "file"
        self.file_name_iterator.update_filename(filename)
        self._sync_file_params()
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
        # suppressed while writing, so the (expensive) background extraction
        # runs once instead of once per field
        self._applying_auto_bkg = True
        try:
            self.params.auto_bkg_smoothing = parameters[0]
            self.params.auto_bkg_iterations = parameters[1]
            self.params.auto_bkg_poly_order = parameters[2]
            self.params.auto_bkg_roi = self._clamped_roi(roi)
            self.params.auto_bkg_enabled = True
        finally:
            self._applying_auto_bkg = False
        self._apply_auto_background()

    def unset_auto_background_subtraction(self) -> None:
        """Disables auto background extraction and removal."""
        logger.info("Unsetting auto background subtraction")
        self.params.auto_bkg_enabled = False
        self.pattern.auto_bkg = None
        self.pattern_changed.emit()
