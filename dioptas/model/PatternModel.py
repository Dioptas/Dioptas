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
        self.errors: np.ndarray | None = None
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
        errors: np.ndarray | None = None,
    ) -> None:
        """Set the current data pattern."""
        if errors is not None and len(errors) != len(x):
            raise ValueError("Pattern errors must have the same length as the data")
        self.pattern_filename = filename
        self.pattern_source = "integrated"
        self.pattern.data = (x, y)
        self.errors = None if errors is None else np.asarray(errors)
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

        self.errors = None
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
        if filename.endswith(".xye"):
            self._save_xye(filename, header, subtract_background)
        elif filename.endswith(".fxye") and self.errors is not None:
            self._save_fxye(filename, header, subtract_background)
        else:
            # Keep xypattern's legacy .fxye sqrt(abs(y)) behavior when an
            # existing script saves without opting into propagated errors.
            self.pattern.save(filename, header, subtract_background, self.unit)

    def _data_for_save(
        self, subtract_background: bool
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        if self.errors is None:
            raise ValueError(
                "Poisson errors were not calculated for the current pattern"
            )
        x, y = self.pattern.data if subtract_background else self.pattern.original_data
        x = np.asarray(x)
        y = np.asarray(y)
        original_x = np.asarray(self.pattern.original_data[0])

        if len(self.errors) == len(x):
            errors = self.errors
        else:
            # Background subtraction can restrict the saved pattern to the
            # background overlap or the automatic-background ROI. Those x
            # values are an exact subset of the integration grid, so retain
            # the corresponding propagated errors.
            selected = np.isin(original_x, x)
            errors = self.errors[selected]
            if len(errors) != len(x) or not np.array_equal(original_x[selected], x):
                raise ValueError("Pattern errors do not match the current pattern")

        return x, y, errors

    def _save_xye(
        self, filename: str, header: str, subtract_background: bool
    ) -> None:
        x, y, errors = self._data_for_save(subtract_background)
        with open(filename, "w") as file_handle:
            if header:
                file_handle.write(header)
                if not header.endswith("\n"):
                    file_handle.write("\n")
            np.savetxt(
                file_handle,
                np.column_stack((x, y, errors)),
                fmt="%.7E",
            )

    def _save_fxye(
        self, filename: str, header: str, subtract_background: bool
    ) -> None:
        x, y, errors = self._data_for_save(subtract_background)
        factor = 1 if "CONQ" in header else 100
        header = header.replace("NUM_POINTS", f"{len(x):.6g}")
        header = header.replace("MIN_X_VAL", f"{factor * x[0]:.6g}")
        header = header.replace(
            "STEP_X_VAL", f"{factor * (x[1] - x[0]):.6g}"
        )
        with open(filename, "w") as file_handle:
            file_handle.write(header)
            file_handle.write("\n")
            np.savetxt(
                file_handle,
                np.column_stack((factor * x, y, errors)),
                delimiter="\t",
                fmt="%.6g",
            )

    def save_auto_background_as_pattern(
        self, filename: str, header: str | None = None
    ) -> None:
        """Saves the current automatic extracted background data pattern to file."""
        self.pattern.auto_background_pattern.save(filename, header, unit=self.unit)

    def get_pattern(self) -> Pattern:
        return self.pattern

    def load_next_file(self, step: int = 1) -> bool:
        """Load the next numbered pattern file.

        For example, ``sample_001.xy`` advances to ``sample_002.xy``. The
        number is expected at the end of the filename stem.
        """
        next_file_name = self.file_name_iterator.get_next_filename(
            mode=self.file_iteration_mode, step=step
        )
        if next_file_name is not None:
            self.load_pattern(next_file_name)
            return True
        return False

    def load_previous_file(self, step: int = 1) -> bool:
        """Load the previous numbered pattern file.

        For example, ``sample_002.xy`` moves to ``sample_001.xy``. The
        number is expected at the end of the filename stem.
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
