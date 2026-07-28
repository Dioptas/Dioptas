# SPDX-License-Identifier: MIT

import numpy as np

from ...model.DioptasModel import DioptasModel
from ...model.util.calc import convert_units
from ...widgets.plot_widgets import PatternWidget


class MapRoiInPatternController:
    """Connects the map intensity window to a region shown in a pattern plot.

    The map sums each pattern over a window of the radial axis; this lets the
    user set that window by dragging a region in the pattern.

    The map keeps its window in the unit it was integrated in, while the
    pattern plot can be switched between 2θ, Q and d at any time, so the
    region is converted in both directions.
    """

    def __init__(
        self,
        pattern_widget: PatternWidget,
        dioptas_model: DioptasModel,
        always_visible: bool = False,
    ):
        """
        :param always_visible: keep the region shown unconditionally, for
            plots that exist only to drive the map — the map mode sets its
            window there before any map has been built. Otherwise visibility
            is driven by :meth:`set_wanted` and by whether a map exists.
        """
        self.pattern_widget = pattern_widget
        self.model = dioptas_model

        self._always_visible = always_visible
        self._wanted = always_visible
        self._visible = False
        self._updating_roi = False

        self.connect()
        self.update_visibility()

    def connect(self):
        self.pattern_widget.map_interactive_roi.sigRegionChanged.connect(
            self.roi_changed
        )
        self.model.integration_unit_changed.connect(self.update_roi)
        self.model.configuration_selected.connect(self.configuration_selected)
        # removing a configuration switches to another one without emitting
        # configuration_selected
        self.model.configuration_removed.connect(self._configuration_removed)

        self._connected_map_model = self.model.map_model
        self._connected_map_model.map_changed.connect(self.map_changed)

    def set_wanted(self, wanted: bool):
        """Whether the host wants the region shown, e.g. while its map tab is
        selected. A region is only actually shown when a map exists as well."""
        if self._always_visible:
            return
        self._wanted = wanted
        self.update_visibility()

    def update_visibility(self):
        visible = self._always_visible or (
            self._wanted and self.model.map_model.map is not None
        )
        if visible == self._visible:
            return
        self._visible = visible
        if visible:
            self.pattern_widget.show_map_interactive_roi()
            self.update_roi()
        else:
            self.pattern_widget.hide_map_interactive_roi()

    def set_center(self, x: float):
        """Moves the region to be centered on *x*, in the displayed unit."""
        if not self._visible:
            return
        self.pattern_widget.map_interactive_roi.setCenter(x)

    def roi_changed(self, interactive_roi):
        if self._updating_roi or not self._visible:
            return
        region = interactive_roi.getRegion()
        window = self._to_map_unit(region)
        if window is None:
            return
        self.model.map_model.set_window(window)

    def map_changed(self):
        self.update_visibility()
        self.update_roi()

    def update_roi(self, *_args):
        """Puts the region where the map's window is, in the displayed unit."""
        if not self._visible:
            return
        window = self.model.map_model.window
        if window is None:
            return
        region = self._from_map_unit(window)
        if region is None:
            return
        self._updating_roi = True
        try:
            self.pattern_widget.set_map_interactive_roi(*region)
        finally:
            self._updating_roi = False

    def configuration_selected(self):
        self._update_map_model_connection()
        self.update_visibility()
        self.update_roi()

    def _configuration_removed(self, _index=None):
        self.configuration_selected()

    def _map_unit(self) -> str:
        # before a map has been integrated there is no recorded unit yet; a
        # window set now will be used with the unit active at integration time
        return self.model.map_model.pattern_unit or self.model.integration_unit

    def _convert(self, values, from_unit: str, to_unit: str):
        if from_unit == to_unit:
            return tuple(float(v) for v in values)
        wavelength = self.model.calibration_model.wavelength
        if not wavelength:
            return None
        try:
            converted = [
                convert_units(float(v), wavelength, from_unit, to_unit) for v in values
            ]
        except ZeroDivisionError:  # d spacing of zero
            return None
        # a region dragged past what the geometry can express (beyond the q
        # limit, through zero in d) has no counterpart to hand to the map
        if any(c is None or not np.isfinite(c) for c in converted):
            return None
        # d spacing runs the other way round, so a converted pair can come out
        # reversed; the region always wants (low, high)
        return tuple(sorted(converted))

    def _to_map_unit(self, region):
        return self._convert(region, self.model.integration_unit, self._map_unit())

    def _from_map_unit(self, window):
        return self._convert(window, self._map_unit(), self.model.integration_unit)

    def _update_map_model_connection(self):
        """Rebinds map_changed to the current configuration's map model."""
        if self.model.map_model is self._connected_map_model:
            return
        self._connected_map_model.map_changed.disconnect(self.map_changed)
        self._connected_map_model = self.model.map_model
        self._connected_map_model.map_changed.connect(self.map_changed)
