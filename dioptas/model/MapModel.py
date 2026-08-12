# SPDX-License-Identifier: MIT
from __future__ import annotations

import logging
import os.path
import time

import h5py
import numpy as np
from dioptas.model.util.signal import Signal
from . import map_expression, map_layout, map_reduction
from .state import MapParams, MapRoiParams, load_params, save_params

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .Configuration import Configuration

logger = logging.getLogger(__name__)


class MapPointInfo:
    filename: str
    frame_index: int

    def __init__(self, filepath, frame_index=0):
        self.filepath = filepath
        self.filename = os.path.basename(filepath)
        self.frame_index = frame_index


class MapModel:
    def __init__(self, configuration: "Configuration"):
        """
        Creates a new map-model. The configuration specified will serve as
        integrator for the processed files.
        :param configuration: Configuration to be used for integration
        """
        super().__init__()
        self.map_changed = Signal()

        # point_integrated is emitted with the index of the integrated point
        # it will be a fractional number, when the image file contains multiple frames
        self.point_integrated = Signal(float)

        # (field, new, old) of a change to one of the ROIs' own params, which
        # are separate evented objects from MapParams
        self.roi_params_changed = Signal(str, object, object)

        self.configuration = configuration

        # All user-settable parameters live in the evented params dataclass;
        # the properties below delegate to it.
        self.params = MapParams()

        self.filepaths = None
        self.point_infos = []
        self.pattern_intensities = None
        self.pattern_x = None
        #: integration unit pattern_x is expressed in; None while no map data
        #: exists. Consumers displaying the pattern in a different unit have
        #: to convert the window into this unit before setting it.
        self.pattern_unit = None
        #: values of the active layer, one per point — what gets laid out
        self.window_intensities = None
        self.possible_dimensions = None
        self.map = None
        #: point index behind every cell of :attr:`map`, or
        #: :data:`map_layout.BLANK` — the inverse of the layout
        self.index_map = None
        #: slot index behind every cell, for tracing blank cells to their
        #: row in the arrangement
        self.slot_map = None

        #: layer name -> values, dropped whenever anything it depends on
        #: changes. Reductions are cheap but the map redraws often.
        self._layer_cache: dict[str, np.ndarray] = {}

        #: resolves an overlay name to its (x, y) data. Injected by the
        #: model that owns the overlays; the map model itself has no path
        #: to them.
        self.overlay_lookup = None
        #: overlay name -> its y values interpolated onto pattern_x
        self._overlay_interp_cache: dict[str, np.ndarray | None] = {}

        # rebuilding is suspended while a bulk change (load, project restore)
        # sets several params in a row, so the map is built once at the end
        self._suspend_rebuild = False

        # side effects of settings changes live here (not in the property
        # setters), so a direct params write behaves exactly like the
        # property write
        self.params.events.connect(self._on_params_changed)
        self._subscribed_rois = []
        self._resubscribe_rois()

    _LAYOUT_FIELDS = (
        "dimension",
        "slots",
        "snake",
        "transpose",
        "flip_horizontal",
        "flip_vertical",
        "excluded_points",
    )

    def _on_params_changed(self, info) -> None:
        field = info.signal.name
        if field == "rois":
            self._resubscribe_rois()
        if self._suspend_rebuild:
            return
        if field in ("rois", "expressions"):
            self._invalidate_layers()
            self._recompute_window_intensities()
            self._rebuild_map()
        elif field == "active_layer":
            self._recompute_window_intensities()
            self._rebuild_map()
        elif field in self._LAYOUT_FIELDS:
            self._rebuild_map()

    def _resubscribe_rois(self):
        """Follows the ROIs currently in the list.

        Their params are separate evented objects, so changing one does not
        reach the MapParams group event the model listens to.
        """
        for roi in self._subscribed_rois:
            try:
                roi.events.disconnect(self._on_roi_params_changed)
            except (ValueError, KeyError):
                pass
        self._subscribed_rois = list(self.params.rois)
        for roi in self._subscribed_rois:
            roi.events.connect(self._on_roi_params_changed)

    def _on_roi_params_changed(self, info) -> None:
        if info is not None:
            new, old = info.args
            self.roi_params_changed.emit(info.signal.name, new, old)
        self._roi_changed()

    def _roi_changed(self) -> None:
        """Recomputes everything an ROI edit invalidates."""
        if self._suspend_rebuild:
            return
        self._invalidate_layers()
        self._recompute_window_intensities()
        self._rebuild_map()

    def _invalidate_layers(self):
        self._layer_cache.clear()
        self._overlay_interp_cache.clear()

    def overlays_changed(self):
        """Recomputes every expression layer that references an overlay.

        Called from outside when an overlay is added, removed or edited —
        the interpolated overlay this model cached is stale either way.
        """
        if not any(
            map_expression.OVL + "(" in expression
            for expression in self.params.expressions.values()
        ):
            return
        self._invalidate_layers()
        self._recompute_window_intensities()
        self._rebuild_map()

    def _interpolated_overlay(self, name: str) -> np.ndarray | None:
        """The overlay's intensities on the map's own radial axis.

        None when the overlay cannot be found. Points outside the overlay's
        range become NaN rather than an extrapolated guess, so a window the
        overlay does not cover reads blank instead of quietly wrong.
        """
        if name in self._overlay_interp_cache:
            return self._overlay_interp_cache[name]
        resolved = None
        if self.overlay_lookup is not None and self.pattern_x is not None:
            found = self.overlay_lookup(name)
            if found is not None:
                overlay_x, overlay_y = np.asarray(found[0]), np.asarray(found[1])
                order = np.argsort(overlay_x)  # d spacing runs descending
                resolved = np.interp(
                    self.pattern_x,
                    overlay_x[order],
                    overlay_y[order],
                    left=np.nan,
                    right=np.nan,
                )
        self._overlay_interp_cache[name] = resolved
        return resolved

    def overlay_window_value(self, overlay_name: str, window_name: str | None):
        """One number: the overlay put through the given window.

        The overlay is interpolated onto the map's radial axis and reduced
        with the window's range, value kind and background setting — this is
        what ovl(overlay, window) means in an expression. None when either
        cannot be resolved.
        """
        roi = self.get_roi(window_name) if window_name else None
        if roi is None or self.pattern_x is None:
            return None
        overlay_y = self._interpolated_overlay(overlay_name)
        if overlay_y is None:
            return None
        values = map_reduction.reduce_window(
            self.pattern_x,
            overlay_y[None, :],
            (roi.x_min, roi.x_max),
            reduction=roi.reduction,
            subtract_background=roi.subtract_background,
        )
        return float(values[0])

    def overlay_exists(self, name: str) -> bool:
        return self.overlay_lookup is not None and self.overlay_lookup(name) is not None

    # --- ROIs and layers -------------------------------------------------

    @property
    def rois(self) -> list[MapRoiParams]:
        return self.params.rois

    @property
    def active_layer(self) -> str:
        return self.params.active_layer

    @active_layer.setter
    def active_layer(self, name: str) -> None:
        self.params.active_layer = name

    @property
    def active_roi(self) -> MapRoiParams | None:
        """The ROI the active layer refers to, or the first one.

        An expression layer is not an ROI, but the pattern plot still has to
        put its draggable region somewhere — the first ROI is the sensible
        place, and is what a map with one window has always used.
        """
        rois = self.params.rois
        if not rois:
            return None
        for roi in rois:
            if roi.name == self.params.active_layer:
                return roi
        return rois[0]

    def get_roi(self, name: str) -> MapRoiParams | None:
        for roi in self.params.rois:
            if roi.name == name:
                return roi
        return None

    def add_roi(
        self,
        name: str | None = None,
        window: tuple[float, float] | None = None,
        reduction: str = "sum",
    ) -> MapRoiParams:
        """Adds a window, defaulting to a fresh name beside the last one."""
        if name is None:
            name = self._next_roi_name()
        if window is None:
            window = self._default_window()
        roi = MapRoiParams(
            name=name,
            x_min=float(min(window)),
            x_max=float(max(window)),
            reduction=reduction,
            color=_roi_color(len(self.params.rois)),
        )
        # a new list object: mutating the existing one would not emit
        self.params.rois = self.params.rois + [roi]
        return roi

    def remove_roi(self, name: str) -> bool:
        """Removes a window. The last one cannot go — the map needs a layer."""
        remaining = [roi for roi in self.params.rois if roi.name != name]
        if len(remaining) == len(self.params.rois) or not remaining:
            return False
        self._suspend_rebuild = True
        try:
            self.params.rois = remaining
            self.params.expressions = {
                key: expression
                for key, expression in self.params.expressions.items()
                if name not in map_expression.referenced_names(expression)
            }
            # the active layer can be the removed ROI, or an expression that
            # went with it
            if self.params.active_layer not in self.layer_names():
                self.params.active_layer = remaining[0].name
        finally:
            self._suspend_rebuild = False
        self._invalidate_layers()
        self._recompute_window_intensities()
        self._rebuild_map()
        return True

    def set_roi_value_kind(
        self, name: str, reduction: str, subtract_background: bool
    ) -> bool:
        """Sets what a window is reduced to, in one step.

        The UI offers the reduction and its background handling as a single
        choice, so they are applied together — otherwise the map would be
        rebuilt once for each half, briefly showing a combination the user
        never picked.
        """
        roi = self.get_roi(name)
        if roi is None:
            return False
        self._suspend_rebuild = True
        try:
            roi.reduction = reduction
            roi.subtract_background = bool(subtract_background)
        finally:
            self._suspend_rebuild = False
        self._roi_changed()
        return True

    def rename_roi(self, name: str, new_name: str) -> bool:
        """Renames a window, following it through expressions and selection."""
        roi = self.get_roi(name)
        if roi is None or not new_name or self.get_roi(new_name) is not None:
            return False
        if new_name in map_expression.reserved_names():
            # "sqrt" or "ovl" as a window name would shadow the expression
            # grammar's own words
            return False
        if new_name in self.params.expressions:
            # windows are looked up first, so a window taking an expression
            # layer's name would make that layer unreachable
            return False
        self._suspend_rebuild = True
        try:
            roi.name = new_name
            self.params.expressions = {
                key: map_expression.rename(expression, name, new_name)
                for key, expression in self.params.expressions.items()
            }
            if self.params.active_layer == name:
                self.params.active_layer = new_name
        finally:
            self._suspend_rebuild = False
        self._invalidate_layers()
        self._recompute_window_intensities()
        self._rebuild_map()
        return True

    def _next_roi_name(self) -> str:
        # expression layers share the namespace: a window taking one of
        # their names would shadow the expression
        taken = {roi.name for roi in self.params.rois} | set(
            self.params.expressions
        )
        for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
            if letter not in taken:
                return letter
        index = len(self.params.rois) + 1
        while f"R{index}" in taken:
            index += 1
        return f"R{index}"

    def _default_window(self) -> tuple[float, float]:
        existing = self.active_roi
        if existing is not None:
            width = existing.x_max - existing.x_min
            return (existing.x_max, existing.x_max + width)
        if self.pattern_x is not None and len(self.pattern_x):
            return tuple(get_center_window(self.pattern_x))
        return (0.0, 1.0)

    @property
    def expressions(self) -> dict[str, str]:
        return self.params.expressions

    def set_expression(self, name: str, expression: str) -> bool:
        """Adds or replaces a layer computed from the ROI layers.

        Refuses a name a window already holds: windows are looked up first,
        so the expression layer would be unreachable and the layer list
        ambiguous.
        """
        if not name or self.get_roi(name) is not None:
            return False
        updated = dict(self.params.expressions)
        updated[name] = expression
        self.params.expressions = updated
        return True

    def remove_expression(self, name: str) -> bool:
        if name not in self.params.expressions:
            return False
        updated = dict(self.params.expressions)
        del updated[name]
        self._suspend_rebuild = True
        try:
            self.params.expressions = updated
            if self.params.active_layer == name:
                rois = self.params.rois
                self.params.active_layer = rois[0].name if rois else ""
        finally:
            self._suspend_rebuild = False
        self._invalidate_layers()
        self._recompute_window_intensities()
        self._rebuild_map()
        return True

    def layer_names(self) -> list[str]:
        """Every layer that can be shown, ROIs before expressions."""
        return [roi.name for roi in self.params.rois] + list(
            self.params.expressions
        )

    def layer_values(self, name: str) -> np.ndarray | None:
        """The values of one layer, one per point, or None if it cannot be
        computed (unknown name, no data, expression that does not evaluate)."""
        if name in self._layer_cache:
            return self._layer_cache[name]
        if self.pattern_x is None or self.pattern_intensities is None:
            return None
        if len(self.pattern_intensities) == 0:
            return None

        roi = self.get_roi(name)
        if roi is not None:
            values = map_reduction.reduce_window(
                self.pattern_x,
                self.pattern_intensities,
                (roi.x_min, roi.x_max),
                reduction=roi.reduction,
                subtract_background=roi.subtract_background,
            )
        elif name in self.params.expressions:
            values = map_expression.evaluate(
                self.params.expressions[name],
                {roi.name: self.layer_values(roi.name) for roi in self.params.rois},
                ovl=self.overlay_window_value,
            )
        else:
            return None

        if values is None:
            return None
        self._layer_cache[name] = values
        return values

    # --- window ----------------------------------------------------------

    @property
    def window(self) -> list[float] | None:
        """The range of the active ROI — the map's original single window."""
        roi = self.active_roi
        if roi is None:
            return None
        return [roi.x_min, roi.x_max]

    @window.setter
    def window(self, new_window: list[float] | None) -> None:
        if new_window is None:
            return
        roi = self.active_roi
        if roi is None:
            self.add_roi(window=tuple(new_window))
            return
        x_min, x_max = float(min(new_window)), float(max(new_window))
        if (roi.x_min, roi.x_max) == (x_min, x_max):
            return
        self._suspend_rebuild = True
        try:
            roi.x_min = x_min
            roi.x_max = x_max
        finally:
            self._suspend_rebuild = False
        self._roi_changed()

    @property
    def dimension(self) -> tuple[int, int] | None:
        return self.params.dimension

    @dimension.setter
    def dimension(self, new_dimension: tuple[int, int] | None) -> None:
        self.params.dimension = new_dimension

    @property
    def slots(self) -> list[int | None] | None:
        return self.params.slots

    @slots.setter
    def slots(self, new_slots: list[int | None] | None) -> None:
        self.params.slots = new_slots

    @property
    def snake(self) -> bool:
        return self.params.snake

    @snake.setter
    def snake(self, value: bool) -> None:
        self.params.snake = bool(value)

    @property
    def transpose(self) -> bool:
        return self.params.transpose

    @transpose.setter
    def transpose(self, value: bool) -> None:
        self.params.transpose = bool(value)

    @property
    def flip_horizontal(self) -> bool:
        return self.params.flip_horizontal

    @flip_horizontal.setter
    def flip_horizontal(self, value: bool) -> None:
        self.params.flip_horizontal = bool(value)

    @property
    def flip_vertical(self) -> bool:
        return self.params.flip_vertical

    @flip_vertical.setter
    def flip_vertical(self, value: bool) -> None:
        self.params.flip_vertical = bool(value)

    @property
    def excluded_points(self) -> list[int]:
        return self.params.excluded_points

    @excluded_points.setter
    def excluded_points(self, value) -> None:
        self.params.excluded_points = sorted({int(i) for i in value})

    @property
    def num_points(self) -> int:
        """Number of point values being laid out on the grid."""
        if self.window_intensities is not None:
            return len(self.window_intensities)
        return len(self.point_infos)

    @property
    def num_slots(self) -> int:
        """Number of grid cells, blanks included."""
        if self.dimension is None:
            return 0
        return int(self.dimension[0]) * int(self.dimension[1])

    def get_slots(self) -> list[int | None]:
        """The full arrangement, normalized and padded to the grid.

        Excluded points are still in here, at their place — the list shows
        them struck through where they belong. Only the map layout leaves
        them out (see :meth:`get_row_of_visible_slot` for the translation).
        """
        return map_layout.fit_slots(self.slots, self.num_points, self.num_slots)

    def get_row_of_visible_slot(self, visible_slot: int) -> int | None:
        """The arrangement row behind a cell of the drawn map.

        The map closes up over excluded points while the arrangement keeps
        them, so the two run out of step by one row per excluded point
        before the cell. None for the trailing blanks that only exist
        because of exclusions — they have no row of their own.
        """
        excluded = set(self.excluded_points)
        count = -1
        for row, entry in enumerate(self.get_slots()):
            if entry is not None and entry in excluded:
                continue
            count += 1
            if count == visible_slot:
                return row
        return None

    def get_point_of_slot(self, slot: int) -> int | None:
        """The point shown in the given cell of the arrangement, if any."""
        slots = self.get_slots()
        if not (0 <= slot < len(slots)):
            return None
        return slots[slot]

    def get_slot_of_point(self, index: int | None) -> int | None:
        """Where the given point sits in the arrangement, if anywhere."""
        if index is None:
            return None
        slots = self.get_slots()
        try:
            return slots.index(int(index))
        except ValueError:
            return None

    def get_slot_labels(self) -> list[str]:
        """One label per grid cell, in arrangement order.

        Blank cells read as an em dash so a gap is visible in a plain list;
        multi-frame files get their frame appended, as the file list has
        always shown them.
        """
        labels = []
        for point in self.get_slots():
            if point is None or point >= len(self.point_infos):
                labels.append("—")
                continue
            info = self.point_infos[point]
            if info.frame_index == 0:
                labels.append(info.filename)
            else:
                labels.append(f"{info.filename}:{info.frame_index}")
        return labels

    def load(self, filepaths: list[str], callback_fn=None):
        """Loads a list of files, integrates them and creates a map"""
        logger.info("Loading map data from %d files", len(filepaths))
        if len(filepaths) == 0:
            raise ValueError("No files to load")

        self.filepaths = filepaths

        self.integrate(callback_fn=callback_fn)

        if len(self.pattern_intensities) == 0:
            return

        self._apply_new_data()

    def append_files(self, filepaths: list[str]) -> list[str]:
        """Integrates *filepaths* with the current settings and appends them
        to the existing map — the live path, where files arrive one by one
        while the scan is still running.

        Nothing the user arranged is reset: the grid keeps its number of
        columns and gains rows as needed, and a custom arrangement gets the
        new points after its last entry — behind trailing blanks left for
        dropped frames on purpose. Files already in the map are ignored.

        Returns the files that could not be added (unreadable, or not
        matching the map's geometry); the map keeps growing without them.
        """
        if self.pattern_x is None or self.pattern_intensities is None:
            raise ValueError("There is no map to append to — load one first")
        if not self.configuration.calibration_model.is_calibrated:
            raise ValueError("Detector geometry is not calibrated")
        if self.configuration.integration_unit != self.pattern_unit:
            raise ValueError(
                "The integration unit changed since the map was integrated — "
                "reload the map to use the new unit"
            )

        # normalized comparison: the watcher announces absolute paths, the
        # map may hold them as they came from the file dialog
        present = {os.path.abspath(info.filepath) for info in self.point_infos}
        new_files = [
            path for path in filepaths if os.path.abspath(path) not in present
        ]
        if not new_files:
            return []

        # same protection as integrate(): constant pattern length, and no
        # img_changed storm while frames pass through the shared img model
        trim_trailing_zeros_backup = self.configuration.trim_trailing_zeros
        self.configuration.trim_trailing_zeros = False
        self.configuration.img_model.img_changed.blocked = True
        try:
            appended_infos, appended_intensities, failed = (
                self._integrate_new_files(new_files)
            )
        finally:
            self.configuration.trim_trailing_zeros = trim_trailing_zeros_backup
            self.configuration.img_model.img_changed.blocked = False

        if not appended_infos:
            return failed

        self.point_infos.extend(appended_infos)
        self.pattern_intensities = np.vstack(
            [self.pattern_intensities, appended_intensities]
        )
        appended_files = list(
            dict.fromkeys(info.filepath for info in appended_infos)
        )
        self.filepaths = list(self.filepaths) + appended_files
        self._apply_appended_data()
        return failed

    def _integrate_new_files(
        self, new_files: list[str]
    ) -> tuple[list[MapPointInfo], list[np.ndarray], list[str]]:
        """(infos, intensities, failed files) for the files being appended.

        Several files at once go through dioptrin's multithreaded batch
        engine when it is available — the beamline may well write frames
        faster than one-by-one integration keeps up, and a growing backlog
        arrives here as ever bigger batches. If the batch trips over one bad
        file the whole set is retried one by one, where only the bad file is
        dropped.
        """
        cal = self.configuration.calibration_model
        unit = self.configuration.integration_unit
        azi_range = self.configuration.oned_azimuth_range

        if len(new_files) > 1 and cal.can_use_dioptrin_batch(unit, azi_range):
            try:
                infos, intensities = self._integrate_files_dioptrin(new_files)
                return infos, intensities, []
            except Exception:
                logger.warning(
                    "Batch integration of the appended files failed; "
                    "retrying them one by one",
                    exc_info=True,
                )

        infos, intensities, failed = [], [], []
        for filepath in new_files:
            try:
                file_infos, file_intensities = self._integrate_single_file(
                    filepath
                )
            except Exception:
                # a single bad frame must not end a running live session
                logger.warning(
                    "Could not append %s to the map", filepath, exc_info=True
                )
                failed.append(filepath)
                continue
            infos.extend(file_infos)
            intensities.extend(file_intensities)
        return infos, intensities, failed

    def _integrate_files_dioptrin(
        self, filepaths: list[str]
    ) -> tuple[list[MapPointInfo], list[np.ndarray]]:
        """Appended frames through the same engine as the bulk load."""
        from dioptas.model.util.integration import iter_frames_sequential

        cal = self.configuration.calibration_model
        unit = self.configuration.integration_unit
        num_points = self.configuration.integration_rad_points

        self.configuration.img_model.load(filepaths[0])
        img_shape = self.configuration.img_model.img_data.shape

        if self.configuration.use_mask:
            mask = self.configuration.mask_model.get_mask()
        elif self.configuration.mask_model.roi is not None:
            mask = self.configuration.mask_model.roi_mask
        else:
            mask = None

        num_points = cal.sync_dioptrin_for_batch(mask, unit, num_points, img_shape)

        all_infos: list[MapPointInfo] = []

        def frame_generator():
            yield from iter_frames_sequential(
                self.configuration.img_model,
                filepaths,
                img_shape=img_shape,
                on_frame=lambda fp, fi: all_infos.append(MapPointInfo(fp, fi)),
            )

        infos: list[MapPointInfo] = []
        intensities: list[np.ndarray] = []
        for i, result in enumerate(
            cal.dioptrin_batch1d_iter(frame_generator(), num_points)
        ):
            if not result.is_ok():
                raise RuntimeError(
                    f"Dioptrin batch integration failed: {result.error}"
                )
            y = np.array(result.result.intensity)
            if len(y) != len(self.pattern_x):
                raise ValueError(
                    "The integrated pattern has a different length than the map's"
                )
            infos.append(all_infos[i])
            intensities.append(y)
        return infos, intensities

    def _integrate_single_file(
        self, filepath: str
    ) -> tuple[list[MapPointInfo], list[np.ndarray]]:
        """Integrates every frame of one file, validated against the map."""
        self.configuration.img_model.load(filepath)
        infos: list[MapPointInfo] = []
        intensities: list[np.ndarray] = []
        for frame_ind in range(self.configuration.img_model.series_max):
            self.configuration.img_model.load_series_img(frame_ind + 1)
            x, y = self.configuration.integrate_image_1d(update_pattern_model=False)
            if len(x) != len(self.pattern_x):
                raise ValueError(
                    "The integrated pattern has a different length than the map's"
                )
            infos.append(MapPointInfo(filepath, frame_ind))
            intensities.append(y)
        return infos, intensities

    def _apply_appended_data(self):
        """Grows the layout around freshly appended points and rebuilds.

        The counterpart of :meth:`_apply_new_data` for appending: where that
        one derives fresh defaults, this one preserves every choice the user
        made and only makes room."""
        self._suspend_rebuild = True
        try:
            # window_intensities still has the old length, and num_points
            # reads from it — recompute before sizing anything
            self._invalidate_layers()
            self._recompute_window_intensities()
            num_points = len(self.point_infos)
            self.possible_dimensions = map_layout.possible_dimensions(num_points)

            if self.slots is not None:
                slots = list(self.slots)
                known = {entry for entry in slots if entry is not None}
                slots += [
                    index for index in range(num_points) if index not in known
                ]
                if len(slots) > self.num_slots:
                    self.dimension = map_layout.grid_for(
                        len(slots), self.dimension[1]
                    )
                self.slots = slots
            elif num_points > self.num_slots:
                self.dimension = map_layout.grid_for(num_points, self.dimension[1])
        finally:
            self._suspend_rebuild = False

        self._rebuild_map()

    def integrate(self, callback_fn=None):
        """Integrates all files in the filepaths list and stores the results"""
        logger.info("Integrating map data")
        if not self.configuration.calibration_model.is_calibrated:
            raise ValueError("Detector geometry is not calibrated")

        # initialize data structures
        self.pattern_x = []
        self.pattern_intensities = []
        self.point_infos = []
        self.pattern_unit = self.configuration.integration_unit

        # disable trimming trailing zeros for integration, otherwise the
        # integration will result in patterns with different length, which
        # will cause problems when creating the map
        trim_trailing_zeros_backup = self.configuration.trim_trailing_zeros
        self.configuration.trim_trailing_zeros = False

        self.configuration.img_model.img_changed.blocked = True

        try:
            self._integrate(callback_fn=callback_fn)
        except Exception as e:
            self._reset()
            raise e
        finally:
            # reset model to previous state
            self.configuration.trim_trailing_zeros = trim_trailing_zeros_backup
            self.configuration.img_model.img_changed.blocked = False

    def _integrate(self, callback_fn=None):
        cal = self.configuration.calibration_model
        unit = self.configuration.integration_unit
        azi_range = self.configuration.oned_azimuth_range

        if cal.can_use_dioptrin_batch(unit, azi_range):
            self._integrate_dioptrin_batch(callback_fn=callback_fn)
        else:
            self._integrate_pyFAI(callback_fn=callback_fn)

    def _integrate_pyFAI(self, callback_fn=None):
        frame_count = 0
        n_total = None
        last_callback_time = time.monotonic()

        for file_ind, filepath in enumerate(self.filepaths):
            self.configuration.img_model.load(filepath)

            series_max = self.configuration.img_model.series_max
            if n_total is None:
                n_total = len(self.filepaths) * series_max

            for frame_ind in range(series_max):
                self.configuration.img_model.load_series_img(frame_ind + 1)
                x, y = self.configuration.integrate_image_1d(
                    update_pattern_model=False
                )

                if file_ind == 0 and frame_ind == 0:
                    self.pattern_x = x
                else:
                    if len(x) != len(self.pattern_x):
                        raise ValueError(
                            "The integrated patterns have different length, this is not supported"
                        )

                self.point_infos.append(MapPointInfo(filepath, frame_ind))
                self.pattern_intensities.append(y)

                frame_count += 1
                self.point_integrated.emit(
                    file_ind + (frame_ind + 1) / series_max
                )

                now = time.monotonic()
                if callback_fn is not None and now - last_callback_time > 0.1:
                    last_callback_time = now
                    if not callback_fn(frame_count, n_total):
                        self.pattern_intensities = np.array(self.pattern_intensities)
                        return

        # Final callback to ensure progress reaches 100%
        if callback_fn is not None:
            callback_fn(frame_count, n_total)

        self.pattern_intensities = np.array(self.pattern_intensities)

    def _integrate_dioptrin_batch(self, callback_fn=None):
        """Load frames through ImgModel, integrate via batch1d_iter with generator."""
        from dioptas.model.util.integration import iter_frames_sequential, convert_tth_to_d

        cal = self.configuration.calibration_model
        unit = self.configuration.integration_unit
        num_points = self.configuration.integration_rad_points

        # Load first file to get shape and configure integrator.
        # The mask must be fetched AFTER loading so that
        # update_mask_dimension has resized it to match the image.
        self.configuration.img_model.load(self.filepaths[0])
        img_shape = self.configuration.img_model.img_data.shape
        first_series_max = self.configuration.img_model.series_max

        if self.configuration.use_mask:
            mask = self.configuration.mask_model.get_mask()
        elif self.configuration.mask_model.roi is not None:
            mask = self.configuration.mask_model.roi_mask
        else:
            mask = None

        num_points = cal.sync_dioptrin_for_batch(mask, unit, num_points, img_shape)

        # Estimate total frames from first file; refined if files differ
        n_total = len(self.filepaths) * first_series_max

        aborted = False
        # Built lazily by frame generator; consumed in result loop
        all_infos = []

        def frame_generator():
            yield from iter_frames_sequential(
                self.configuration.img_model,
                self.filepaths,
                img_shape=img_shape,
                abort_check=lambda: aborted,
                on_frame=lambda fp, fi: all_infos.append(MapPointInfo(fp, fi)),
            )

        result_iter = cal.dioptrin_batch1d_iter(frame_generator(), num_points)

        last_callback_time = time.monotonic()
        frame_count = 0
        for i, result in enumerate(result_iter):
            if aborted:
                # Drain remaining pre-fetched results from dioptrin without
                # processing them. This ensures the iterator is fully
                # consumed so cleanup doesn't crash on worker threads.
                continue

            if not result.is_ok():
                raise RuntimeError(
                    f"Dioptrin batch integration failed: {result.error}"
                )

            x = np.array(result.result.radial)
            y = np.array(result.result.intensity)
            frame_count = i + 1

            if frame_count == 1:
                self.pattern_x = x
            else:
                if len(x) != len(self.pattern_x):
                    raise ValueError(
                        "The integrated patterns have different length, "
                        "this is not supported"
                    )

            self.point_infos.append(all_infos[i])
            self.pattern_intensities.append(y)

            self.point_integrated.emit(frame_count)

            # Throttle callback to avoid GUI overhead dominating throughput
            now = time.monotonic()
            if callback_fn is not None and now - last_callback_time > 0.1:
                last_callback_time = now
                if not callback_fn(frame_count, n_total):
                    aborted = True
                    # Don't break — let the for loop drain remaining
                    # pre-fetched results so dioptrin shuts down cleanly.

        # Final callback to ensure progress reaches 100%
        if callback_fn is not None and not aborted:
            callback_fn(frame_count, n_total)

        self.pattern_intensities = np.array(self.pattern_intensities)

        if unit == "d_A":
            self.pattern_x = convert_tth_to_d(
                self.pattern_x, cal.pattern_geometry.wavelength
            )

    def set_integration_results(
        self,
        pattern_x,
        pattern_intensities,
        point_infos: list[MapPointInfo],
        filepaths: list[str],
        pattern_unit: str | None = None,
        keep_layout: bool = False,
    ):
        """Sets pre-computed integration results and rebuilds the map.

        This allows populating the model without re-integrating, e.g. when
        results were computed in a worker thread. *pattern_unit* defaults to
        the configuration's current integration unit, which is correct for
        results just computed with it; project files pass their stored unit.
        Pass *keep_layout* when the caller has already restored an
        arrangement that belongs to this data, as loading a project does.
        """
        self.pattern_x = pattern_x
        self.pattern_intensities = pattern_intensities
        self.point_infos = point_infos
        self.filepaths = filepaths
        self.pattern_unit = (
            pattern_unit
            if pattern_unit is not None
            else self.configuration.integration_unit
        )

        self._apply_new_data(keep_layout=keep_layout)

    def _apply_new_data(self, keep_layout: bool = False):
        """Derives the defaults a fresh set of points needs, then builds the
        map. Params are written in one suspended batch so the map is built
        once rather than after every field."""
        self._suspend_rebuild = True
        try:
            if not keep_layout:
                # an arrangement describes one particular set of files; the
                # next map has to start from the plain one
                self.slots = None
                self.excluded_points = []

            if not self.params.rois:
                self.add_roi(window=tuple(get_center_window(self.pattern_x)))
            if self.params.active_layer not in self.layer_names():
                self.params.active_layer = self.params.rois[0].name
            self._invalidate_layers()
            self._recompute_window_intensities()

            self.possible_dimensions = map_layout.possible_dimensions(self.num_points)

            if self.dimension is None or (
                not keep_layout and self.dimension not in self.possible_dimensions
            ):
                self.dimension = self.possible_dimensions[0]
            elif self.num_slots < self.num_points:
                # a grid kept from a smaller map cannot hold these points
                self.dimension = self.possible_dimensions[0]
        finally:
            self._suspend_rebuild = False

        self._rebuild_map()

    def _recompute_window_intensities(self):
        """Puts the active layer's values where the layout picks them up."""
        if self.pattern_x is None or self.pattern_intensities is None:
            return
        values = self.layer_values(self.params.active_layer)
        if values is None:
            # an expression that stopped evaluating must not silently leave
            # the previous layer's values on screen
            values = self.layer_values(
                self.params.rois[0].name if self.params.rois else ""
            )
        if values is not None:
            self.window_intensities = values

    def _rebuild_map(self):
        """Lays the current point values out on the grid and announces it."""
        if self.window_intensities is None or self.dimension is None:
            return
        self.map, self.index_map = map_layout.arrange(
            self.window_intensities,
            self.dimension,
            slots=self.slots,
            snake=self.snake,
            transpose=self.transpose,
            flip_horizontal=self.flip_horizontal,
            flip_vertical=self.flip_vertical,
            excluded=self.excluded_points,
        )
        # the same transforms applied to the slot numbers themselves, so a
        # clicked cell — blank ones included — can be traced to its slot
        num_slots = self.num_slots
        _, self.slot_map = map_layout.arrange(
            np.arange(num_slots),
            self.dimension,
            slots=list(range(num_slots)),
            snake=self.snake,
            transpose=self.transpose,
            flip_horizontal=self.flip_horizontal,
            flip_vertical=self.flip_vertical,
        )
        self.map_changed.emit()

    def _reset(self):
        self.filepaths = None
        self.point_infos = []
        self.pattern_intensities = None
        self.pattern_x = None
        self.pattern_unit = None
        self.window_intensities = None
        self.possible_dimensions = None
        self.map = None
        self.index_map = None
        self.slot_map = None
        self._suspend_rebuild = True
        try:
            self.dimension = None
            self.slots = None
            self.excluded_points = []
        finally:
            self._suspend_rebuild = False
        self.map_changed.emit()

    def set_window(self, window: tuple[float, float]):
        """Sets the window in the pattern for generating the map
        :param window: tuple/list of lower value and upper value of the window
        """
        self.window = window

    def set_dimension(self, dimension: tuple[int, int]):
        """Sets the grid the points are laid out on.

        Any grid with room for every point is allowed, not only the exact
        factorizations of the point count: a scan that dropped a frame still
        wants its original grid, with the missing cell left blank.
        """
        rows, columns = int(dimension[0]), int(dimension[1])
        if rows < 1 or columns < 1 or rows * columns < self.num_points:
            return
        self.dimension = (rows, columns)

    def set_columns(self, columns: int):
        """Sets the number of columns, growing the grid to fit the cells."""
        if self.dimension is None:
            return
        self.set_dimension(
            map_layout.grid_for(max(self.num_slots, self.num_points), columns)
        )

    def insert_blank(self, position: int):
        """Inserts a blank cell, shifting every later point one cell on.

        This is the repair for a dropped frame: without it every point after
        the gap sits in the wrong place.
        """
        if self.dimension is None:
            return
        self._set_slots(map_layout.insert_blank(self.get_slots(), position))

    def remove_blank(self, position: int):
        """Removes the blank cell at *position*, pulling later points back."""
        if self.dimension is None:
            return
        self._set_slots(map_layout.remove_blank(self.get_slots(), position))

    def can_remove_blank(self, position: int) -> bool:
        """Whether removing the blank at *position* changes anything.

        The grid keeps its cell count, so a removed blank only shifts the
        entries after it one row earlier — and a new blank appears at the
        end. A blank with nothing after it is therefore structural: it
        belongs to the grid size, and "removing" it would visibly do
        nothing. Shrinking the grid is what gets rid of those.
        """
        slots = self.get_slots()
        if not (0 <= position < len(slots)) or slots[position] is not None:
            return False
        return any(entry is not None for entry in slots[position + 1:])

    def move_slot(self, source: int, target: int):
        """Moves one cell of the arrangement to another position."""
        if self.dimension is None:
            return
        self._set_slots(map_layout.move_slot(self.get_slots(), source, target))

    def _set_slots(self, slots: list[int | None]):
        """Stores an arrangement, growing the grid if it no longer fits."""
        self._suspend_rebuild = True
        try:
            if len(slots) > self.num_slots:
                self.dimension = map_layout.grid_for(len(slots), self.dimension[1])
            self.slots = slots
        finally:
            self._suspend_rebuild = False
        self._rebuild_map()

    def set_point_excluded(self, index: int, excluded: bool = True):
        """Blanks out a single point without moving any of the others."""
        current = set(self.excluded_points)
        if excluded:
            current.add(int(index))
        else:
            current.discard(int(index))
        self.excluded_points = current

    def is_point_excluded(self, index: int) -> bool:
        return int(index) in set(self.excluded_points)

    def detect_gaps(self) -> int:
        """Inserts a blank wherever the filename numbering skips a value.

        Returns the number of blanks inserted; zero means the numbering shows
        no gaps, or says nothing this can act on.
        """
        if self.dimension is None or self.num_points == 0:
            return 0
        if any(info.frame_index != 0 for info in self.point_infos):
            # frames inside one file are numbered by the file, not the name
            return 0
        slots = map_layout.slots_from_filenames(
            [info.filepath for info in self.point_infos]
        )
        if slots is None:
            return 0
        self._set_slots(slots)
        return len(slots) - self.num_points

    def get_point_info(self, row_index: int, column_index: int) -> MapPointInfo | None:
        """Returns the point info for the specified row and column index"""
        ind = self.get_point_index(row_index, column_index)
        if ind is None or ind > len(self.point_infos) - 1:
            return None
        return self.point_infos[ind]

    def get_slot_at(self, row_index: int, column_index: int) -> int | None:
        """The slot behind the cell at that position, blank cells included."""
        if self.slot_map is None:
            return None
        rows, columns = self.slot_map.shape
        if not (0 <= row_index < rows and 0 <= column_index < columns):
            return None
        return int(self.slot_map[row_index, column_index])

    def get_point_index(self, row_index: int, column_index: int) -> int | None:
        """Returns the index into the point list of the cell at that position,
        or None when the cell is blank or outside the map."""
        if self.index_map is None:
            return None
        rows, columns = self.index_map.shape
        if not (0 <= row_index < rows and 0 <= column_index < columns):
            return None
        index = int(self.index_map[row_index, column_index])
        return None if index == map_layout.BLANK else index

    def get_point_coordinates(self, index: int) -> tuple[int, int] | None:
        """Returns the row and column the given point is laid out at"""
        if self.index_map is None:
            return None
        hits = np.argwhere(self.index_map == int(index))
        if len(hits) == 0:
            return None
        row, column = hits[0]
        return int(row), int(column)

    def get_index_of_file(self, filepath: str, frame_index: int = 0) -> int | None:
        """Returns the point index for an image file, or None if it is not part
        of the map.

        Inverse of :meth:`get_point_info`. Used to keep a map selection marker
        in sync with images loaded from outside the map (e.g. by stepping
        through files in the integration view).
        """
        if filepath is None:
            return None
        for index, point_info in enumerate(self.point_infos):
            if (
                point_info.filepath == filepath
                and point_info.frame_index == frame_index
            ):
                return index
        return None

    def select_point(self, row_index: int, column_index: int):
        """Selects the point at the specified row and column index, will trigger a load of the image through the
        configuration. Thus the image_changed signal will be sent to all listeners"""
        point_ind = self.get_point_index(row_index, column_index)
        if point_ind is None:
            return
        self.select_point_by_index(point_ind)

    def select_point_by_index(self, index: int):
        """Selects the point at the specified index (considering the list of images), will trigger a load of the
        image through the configuration. Thus the image_changed signal will be sent to all listeners
        """
        if index < 0 or index >= len(self.point_infos):
            return
        point_info = self.point_infos[index]
        self.configuration.img_model.load(
            point_info.filepath,
            point_info.frame_index,
        )

    def save_in_hdf5(self, hdf5_group):
        """Save map state into the given HDF5 group. Skips if no map data."""
        if self.filepaths is None:
            return

        g = hdf5_group.create_group("map")
        save_params(g, self.params)
        g.create_dataset("pattern_x", data=self.pattern_x)
        g.create_dataset("pattern_intensities", data=self.pattern_intensities)
        if self.pattern_unit is not None:
            g.attrs["pattern_unit"] = self.pattern_unit
        g.create_dataset("window", data=np.array(self.window, dtype="f8"))
        g.create_dataset("dimension", data=np.array(self.dimension, dtype="i"))

        dt = h5py.string_dtype()
        g.create_dataset("filepaths", data=self.filepaths, dtype=dt)

        pi_group = g.create_group("point_infos")
        pi_filepaths = [p.filepath for p in self.point_infos]
        pi_frame_indices = [p.frame_index for p in self.point_infos]
        pi_group.create_dataset("filepaths", data=pi_filepaths, dtype=dt)
        pi_group.create_dataset("frame_indices", data=pi_frame_indices)

    def load_from_hdf5(self, hdf5_group):
        """Restore map state from the given HDF5 group."""
        if "map" not in hdf5_group:
            return

        g = hdf5_group["map"]
        pattern_x = g["pattern_x"][...]
        pattern_intensities = g["pattern_intensities"][...]
        filepaths = [fp.decode() if isinstance(fp, bytes) else fp for fp in g["filepaths"][...]]

        pi_fps = g["point_infos"]["filepaths"][...]
        pi_fis = g["point_infos"]["frame_indices"][...]
        point_infos = [
            MapPointInfo(
                fp.decode() if isinstance(fp, bytes) else fp,
                int(fi),
            )
            for fp, fi in zip(pi_fps, pi_fis)
        ]

        window = tuple(g["window"][...])
        dimension = tuple(int(v) for v in g["dimension"][...])

        # Files written before the unit was stored fall back to the current
        # integration unit, which is what those versions implicitly assumed.
        pattern_unit = g.attrs.get("pattern_unit")
        if isinstance(pattern_unit, bytes):
            pattern_unit = pattern_unit.decode()

        stored = load_params(g, MapParams)

        # Set the layout before set_integration_results so it uses the saved
        # values instead of computing defaults that may not match the data
        # after an HDF5 round-trip.
        self._suspend_rebuild = True
        try:
            if stored is not None and stored.rois:
                self.params.rois = stored.rois
                self.params.active_layer = stored.active_layer
                self.params.expressions = dict(stored.expressions)
            else:
                # project files from before layers had a single window
                self.params.rois = [
                    MapRoiParams(
                        name="A",
                        x_min=float(min(window)),
                        x_max=float(max(window)),
                        color=_roi_color(0),
                    )
                ]
                self.params.active_layer = "A"
            self._resubscribe_rois()
            self.dimension = dimension
            if stored is not None:
                self.slots = stored.slots
                self.snake = stored.snake
                self.transpose = stored.transpose
                self.flip_horizontal = stored.flip_horizontal
                self.flip_vertical = stored.flip_vertical
                self.excluded_points = stored.excluded_points
        finally:
            self._suspend_rebuild = False

        self.set_integration_results(
            pattern_x,
            pattern_intensities,
            point_infos,
            filepaths,
            pattern_unit=pattern_unit,
            keep_layout=True,
        )


#: colours new ROIs cycle through — distinguishable on the dark pattern plot
_ROI_COLORS = (
    "#40e0d0",
    "#ffa040",
    "#c080ff",
    "#80ff80",
    "#ff8080",
    "#ffe040",
)


def _roi_color(index: int) -> str:
    return _ROI_COLORS[index % len(_ROI_COLORS)]


def get_center_window(x, window_range=3) -> list[float]:
    """
    Estimates a window of [x_min, x_max] centered in the x value list.
    :param x: a numpy array
    :param window_range: the window will be estimated with +- range * x_step
    :return: windows with [x_min, x_max]
    """
    window_center = x[int(len(x) / 2)]
    x_step = np.mean(np.diff(x))
    return [
        window_center - window_range * x_step,
        window_center + window_range * x_step,
    ]


def ind_in_window(x_array, window: tuple[float, float]) -> np.ndarray:
    """
    Gets the indices of a numpy array which are in the window
    :param x_array: a numpy array
    :param window: tuple/list of lower value and upper value of the window
    :return: list of indices
    """
    return np.where((x_array > window[0]) & (x_array < window[1]))[0]


def get_window_intensities(
    pattern_x, intensities, window: tuple[float, float]
) -> np.ndarray:
    """
    Estimates the intensities inside the specified window
    :param pattern_x: a numpy array of x values from the pattern
    :param intensities: a 2D numpy array holding the intensities of all patterns
    :param window: tuple/list of lower value and upper value of the summing window
    :return: an 1D array containing the sum of  intensities inside the window for each pattern
    """
    indices = ind_in_window(pattern_x, window)
    return np.sum(intensities[:, indices], axis=1)
