# SPDX-License-Identifier: MIT

import logging
import os
import queue
import time

import numpy as np
import pyqtgraph as pg
from PIL import Image
from qtpy import QtWidgets, QtCore
from qtpy.QtGui import QTransform
from scipy.ndimage import zoom

from dioptas.model import map_layout
from dioptas.model.DioptasModel import DioptasModel
from dioptas.model.util.NewFileWatcher import NewFileInDirectoryWatcher
from dioptas.model.util.signal import Signal
from dioptas.widgets.MapGridPopup import MapGridPopup
from dioptas.widgets.MapPanelWidget import MapPanelWidget

from ..widgets.UtilityWidgets import get_progress_dialog, open_files_dialog
from ..widgets.UtilityWidgets import save_file_dialog

logger = logging.getLogger(__name__)


class MapPanelController:
    """Drives the map display panel.

    Deliberately has no activate()/deactivate(): the panel can be visible
    while another mode is active (integration map tab, floating window), so
    its model subscriptions have to stay live across mode switches.
    """

    _CONTOUR_UPSAMPLE = 3

    def __init__(self, widget: MapPanelWidget, dioptas_model: DioptasModel):
        self.widget = widget
        self.model = dioptas_model

        #: emitted with the point index when a point is picked in the map plot,
        #: so hosts can follow the selection with their own widgets
        self.point_selected = Signal(int)

        #: emitted with the slot index when a blank cell is picked — there is
        #: no point to select, but the cell still has a row in the list
        self.blank_selected = Signal(int)

        self._contour_items: list[pg.IsocurveItem] = []

        self.grid_popup = MapGridPopup(self.widget)

        # live mode: the watcher announces finished files from its poll
        # thread; they cross into the GUI thread through this queue, which a
        # timer drains in batches — one integration pass per tick, not per file
        self._live_watcher: NewFileInDirectoryWatcher | None = None
        self._live_prefix = ""
        self._live_queue: queue.Queue[str] = queue.Queue()
        self._live_timer = QtCore.QTimer(self.widget)
        self._live_timer.setInterval(500)
        self._live_timer.timeout.connect(self._drain_live_queue)

        self.create_signals()

    def create_signals(self):
        self.widget.map_plot_control_widget.save_map_btn.clicked.connect(self._save_map)
        self.widget.map_image_frame.smooth_btn.toggled.connect(self._smooth_toggled)
        self.widget.map_image_frame.smooth_slider.valueChanged.connect(
            self._smooth_slider_changed
        )
        self.widget.map_image_frame.contour_btn.toggled.connect(self._contour_toggled)
        self.widget.map_image_frame.contour_slider.valueChanged.connect(
            self._contour_slider_changed
        )
        self.widget.map_plot_control_widget.layer_cb.currentIndexChanged.connect(
            self._layer_cb_changed
        )

        self.widget.map_plot_control_widget.load_btn.clicked.connect(self.load_map)
        self.widget.map_plot_control_widget.live_btn.toggled.connect(
            self._live_toggled
        )
        self.widget.map_plot_control_widget.grid_btn.clicked.connect(
            self._grid_btn_clicked
        )
        self.grid_popup.sigGridChanged.connect(self._grid_changed)
        self.grid_popup.sigSnakeChanged.connect(self._snake_changed)
        self.grid_popup.sigTransposeChanged.connect(self._transpose_changed)
        self.grid_popup.sigFlipHorizontalChanged.connect(self._flip_horizontal_changed)
        self.grid_popup.sigFlipVerticalChanged.connect(self._flip_vertical_changed)
        self.grid_popup.sigDetectGapsRequested.connect(self._detect_gaps)
        self.widget.map_plot_widget.mouse_left_clicked.connect(self.map_point_selected)
        self.widget.map_plot_widget.mouse_moved.connect(self.map_plot_mouse_moved)

        self._connected_map_model = self.model.map_model
        self._connected_map_model.map_changed.connect(self.update_map)
        self.model.configuration_selected.connect(self.configuration_selected)
        # removing a configuration selects another one without emitting
        # configuration_selected, so the panel would keep showing the map of
        # the configuration that is gone
        self.model.configuration_removed.connect(self._configuration_removed)
        # stays connected across mode switches: the panel also follows images
        # loaded elsewhere, e.g. by stepping through files in the integration
        # view while the map tab is shown
        self.model.img_changed.connect(self.update_marker)

    def _live_toggled(self, checked: bool):
        if checked:
            if not self._start_live():
                self.widget.map_plot_control_widget.live_btn.setChecked(False)
        else:
            self._stop_live()

    def stop_live(self):
        """Turns live mode off, button included; safe to call any time."""
        live_btn = self.widget.map_plot_control_widget.live_btn
        if live_btn.isChecked():
            live_btn.setChecked(False)  # _live_toggled does the stopping
        else:
            self._stop_live()

    def _start_live(self) -> bool:
        """Watches the loaded map's folder and appends what appears there."""
        map_model = self.model.map_model
        if map_model.pattern_x is None or not map_model.filepaths:
            QtWidgets.QMessageBox.information(
                self.widget,
                "Live map",
                "Load the first image(s) of the scan as a map first — "
                "Live then appends every new file written to their folder.",
            )
            return False

        directory = os.path.dirname(os.path.abspath(map_model.filepaths[-1]))
        extensions = {
            os.path.splitext(path)[1].lstrip(".").lower()
            for path in map_model.filepaths
        }
        extensions.discard("")

        self._live_prefix = self._name_prefix(map_model.filepaths)

        if self._live_watcher is None:
            self._live_watcher = NewFileInDirectoryWatcher(
                directory, file_types=sorted(extensions)
            )
            self._live_watcher.file_added.connect(self._live_file_appeared)
        else:
            self._live_watcher.file_types = extensions
            self._live_watcher.path = directory

        self._catch_up(directory, extensions)
        self._live_watcher.activate()
        self._live_timer.start()
        return True

    @staticmethod
    def _name_prefix(filepaths: list[str]) -> str:
        """What the scan's files are called, before their running number.

        The common prefix of the loaded names, with any digits it ends in
        stripped: loading scan_11..scan_13 must not lock the prefix to
        "scan_1" and shut out scan_20. Only files bearing this prefix belong
        to the scan — another scan or a calibration image written into the
        same folder does not, whatever its extension and number say.
        """
        stems = [
            os.path.splitext(os.path.basename(path))[0] for path in filepaths
        ]
        return os.path.commonprefix(stems).rstrip("0123456789")

    def _belongs_to_scan(self, filepath: str) -> bool:
        return os.path.basename(filepath).startswith(self._live_prefix)

    def _stop_live(self):
        self._live_timer.stop()
        if self._live_watcher is not None:
            self._live_watcher.deactivate()
        # files left in the queue belong to the session that found them
        while True:
            try:
                self._live_queue.get_nowait()
            except queue.Empty:
                break

    def _live_file_appeared(self, filepath: str):
        # called on the watcher's poll thread; only the queue is touched
        self._live_queue.put(filepath)

    def _catch_up(self, directory: str, extensions: set[str]):
        """Queues the scan files written between loading the map and now.

        Only numbered continuations count: files carrying a number higher
        than the highest already in the map. Anything else in the folder — a
        calibration image, another scan — is none of live mode's business,
        and an unnumbered map has no way to tell the two apart.
        """
        map_model = self.model.map_model
        numbers = [
            map_layout.filename_number(path) for path in map_model.filepaths
        ]
        if any(number is None for number in numbers):
            return
        highest = max(numbers)

        try:
            names = os.listdir(directory)
        except OSError:
            return
        present = {os.path.abspath(path) for path in map_model.filepaths}
        candidates = []
        for name in names:
            if os.path.splitext(name)[1].lstrip(".").lower() not in extensions:
                continue
            if not self._belongs_to_scan(name):
                continue
            path = os.path.abspath(os.path.join(directory, name))
            if path in present:
                continue
            number = map_layout.filename_number(name)
            if number is None or number <= highest:
                continue
            candidates.append((number, path))
        for _, path in sorted(candidates):
            self._live_queue.put(path)

    #: files integrated per timer tick with the multithreaded batch engine:
    #: bigger batches are faster there, but the tick runs on the GUI thread,
    #: and one bounded batch per tick keeps the interface usable while a big
    #: catch-up works through the queue.
    _LIVE_BATCH_LIMIT = 25
    #: without the batch engine every file costs a full pyFAI pass on the
    #: GUI thread, so the per-tick bite is kept much smaller — the map falls
    #: behind a fast beamline more gracefully than the interface freezes
    _LIVE_SINGLE_LIMIT = 5

    def _live_drain_limit(self) -> int:
        configuration = self.model.map_model.configuration
        batch_capable = configuration.calibration_model.can_use_dioptrin_batch(
            configuration.integration_unit, configuration.oned_azimuth_range
        )
        return self._LIVE_BATCH_LIMIT if batch_capable else self._LIVE_SINGLE_LIMIT

    def _drain_live_queue(self):
        batch = []
        limit = self._live_drain_limit()
        while len(batch) < limit:
            try:
                filepath = self._live_queue.get_nowait()
            except queue.Empty:
                break
            # the watcher matches on extension alone; whether the file is
            # part of this scan is decided by its name
            if self._belongs_to_scan(filepath):
                batch.append(filepath)
        if not batch:
            return

        map_model = self.model.map_model
        points_before = len(map_model.point_infos)
        try:
            failed = map_model.append_files(batch)
        except Exception as e:
            # systemic — the unit changed, the calibration is gone: stopping
            # beats failing again on every tick
            self.stop_live()
            QtWidgets.QMessageBox.critical(
                self.widget,
                "Live map stopped",
                f"New images can no longer be added to the map:\n{e}",
            )
            return

        if failed:
            logger.warning(
                "Live map: %d file(s) could not be added: %s",
                len(failed),
                ", ".join(os.path.basename(path) for path in failed),
            )
        if len(map_model.point_infos) > points_before:
            self._follow_newest()

    def _follow_newest(self):
        """Selects the point that just arrived — at the beamline the newest
        frame is the one being watched."""
        map_model = self.model.map_model
        coordinates = map_model.get_point_coordinates(
            len(map_model.point_infos) - 1
        )
        if coordinates is not None:
            map_model.select_point(*coordinates)

    def load_map(self):
        """Asks for image files and builds a map from them."""
        self.stop_live()
        filenames = open_files_dialog(
            self.widget,
            "Load image data file(s)",
            self.model.working_directories["image"],
        )
        if len(filenames) == 0:
            return

        progressDialog = get_progress_dialog(
            "Integrating image data...",
            "Abort Integration",
            100,
            self.widget.map_pg_layout,
        )
        progressDialog.setMinimumDuration(0)
        progressDialog.setWindowModality(QtCore.Qt.ApplicationModal)
        label = progressDialog.findChild(QtWidgets.QLabel)
        if label is not None:
            label.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)

        t_start = time.time()

        def callback_fn(current, n_total):
            if progressDialog.wasCanceled():
                return False
            progressDialog.setValue(int(current / n_total * 100))
            elapsed = time.time() - t_start
            rate = current / elapsed if elapsed > 0 else 0
            progressDialog.setLabelText(
                f"Image {current} of {n_total}\n"
                f"{elapsed:.1f}s elapsed\n"
                f"{rate:.1f} img/s"
            )
            QtWidgets.QApplication.processEvents()
            return not progressDialog.wasCanceled()

        try:
            self.model.map_model.load(filenames, callback_fn=callback_fn)
            self.model.map_model.select_point(0, 0)
        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self.widget, "Error loading image data.", str(e)
            )
        finally:
            progressDialog.close()

    def _grid_btn_clicked(self):
        self._update_grid_popup()
        self.grid_popup.set_gaps_message("")
        self.grid_popup.popup_at(self.widget.map_plot_control_widget.grid_btn)

    def _update_grid_popup(self):
        map_model = self.model.map_model
        self.update_dimension_cb()
        self.grid_popup.set_state(
            dimension=map_model.dimension,
            num_points=map_model.num_points,
            snake=map_model.snake,
            transpose=map_model.transpose,
            flip_horizontal=map_model.flip_horizontal,
            flip_vertical=map_model.flip_vertical,
        )

    def _grid_changed(self, rows: int, columns: int):
        self.model.map_model.set_dimension((rows, columns))
        self._update_grid_popup()

    def _snake_changed(self, checked: bool):
        self.model.map_model.snake = checked

    def _transpose_changed(self, checked: bool):
        self.model.map_model.transpose = checked

    def _flip_horizontal_changed(self, checked: bool):
        self.model.map_model.flip_horizontal = checked

    def _flip_vertical_changed(self, checked: bool):
        self.model.map_model.flip_vertical = checked

    def _detect_gaps(self):
        map_model = self.model.map_model
        if map_model.map is None:
            self.grid_popup.set_gaps_message("No map loaded.")
            return
        inserted = map_model.detect_gaps()
        if inserted:
            self.grid_popup.set_gaps_message(
                f"Inserted {inserted} blank cell{'s' if inserted > 1 else ''} "
                "for missing file numbers."
            )
        else:
            self.grid_popup.set_gaps_message(
                "No gaps found in the file numbering."
            )
        self._update_grid_popup()

    def _smooth_toggled(self, checked: bool):
        self.widget.map_image_frame.smooth_slider.setVisible(checked)
        self.widget.map_image_frame.smooth_label.setVisible(checked)
        if checked:
            factor = self.widget.map_image_frame.smooth_slider.value()
        else:
            factor = 1
        self.widget.map_plot_widget.data_img_item.setSmoothFactor(factor)

    def _smooth_slider_changed(self, value: int):
        self.widget.map_image_frame.smooth_label.setText(str(value))
        if self.widget.map_image_frame.smooth_btn.isChecked():
            self.widget.map_plot_widget.data_img_item.setSmoothFactor(value)

    def _contour_slider_changed(self, value: int):
        self.widget.map_image_frame.contour_label.setText(str(value))
        if self.widget.map_image_frame.contour_btn.isChecked():
            self._update_contours()

    def _contour_toggled(self, checked: bool):
        self.widget.map_image_frame.contour_slider.setVisible(checked)
        self.widget.map_image_frame.contour_label.setVisible(checked)
        if checked:
            self._update_contours()
        else:
            self._clear_contours()

    def _update_contours(self):
        self._clear_contours()
        if self.model.map_model.map is None:
            return
        data = np.flipud(self.model.map_model.map).T
        factor = self._CONTOUR_UPSAMPLE
        data = np.asarray(data, dtype=float)
        if not np.any(np.isfinite(data)):
            return
        # blank cells would spread NaN over the whole interpolation
        data = np.nan_to_num(data, nan=float(np.nanmin(data)))
        data = zoom(data, factor, order=3)
        num_levels = self.widget.map_image_frame.contour_slider.value()
        d_min, d_max = float(data.min()), float(data.max())
        if d_min == d_max:
            return
        levels = np.linspace(d_min, d_max, num_levels + 2)[1:-1]
        pen = pg.mkPen(color=(255, 255, 255, 128), width=1)
        view_box = self.widget.map_plot_widget.img_view_box
        scale = QTransform.fromScale(1.0 / factor, 1.0 / factor)
        for level in levels:
            item = pg.IsocurveItem(data=data, level=level, pen=pen)
            item.setTransform(scale)
            view_box.addItem(item)
            self._contour_items.append(item)

    def _clear_contours(self):
        view_box = self.widget.map_plot_widget.img_view_box
        for item in self._contour_items:
            view_box.removeItem(item)
        self._contour_items.clear()

    def _save_map(self):
        filename = save_file_dialog(
            self.widget,
            "Save Image.",
            os.path.join(self.model.working_directories["image"]),
            ("PNG Image (*.png);; TIFF Data (*.tiff);; Tabular Text (*.txt)"),
        )

        if filename == "":
            return
        else:
            self.save_map(filename)

    def save_map(self, filename: str):
        if filename.endswith(".png"):
            self.widget.map_plot_widget.save_img(filename)
        elif filename.endswith(".tiff"):
            data = np.asarray(self.model.map_model.map, dtype=float)
            max_uint32 = np.iinfo(np.uint32).max
            if np.any(np.isfinite(data)):
                d_min, d_max = np.nanmin(data), np.nanmax(data)
                span = d_max - d_min
                normalized_data = (
                    (data - d_min) / span if span else np.zeros_like(data)
                )
            else:
                # a map of only blanks (window outside the pattern, a layer
                # that overflowed) still has to save, as an empty image
                normalized_data = np.zeros_like(data)
            # an integer image has no way to say "no data"; blanks go to zero
            normalized_data = np.nan_to_num(normalized_data, nan=0.0)
            normalized_data = (normalized_data * max_uint32).astype(np.uint32)
            im = Image.fromarray(normalized_data)
            im.save(filename)
        elif filename.endswith(".txt"):
            # %g so blank cells come out as "nan" rather than failing
            np.savetxt(filename, self.model.map_model.map, fmt="%g")

    def update_map(self):
        if self.model.map_model.map is None:
            # clear image
            self.widget.map_plot_widget.plot_image(np.array([[], []]))
            self._clear_contours()
        else:
            self.widget.map_plot_widget.plot_image(
                np.flipud(self.model.map_model.map), auto_level=True
            )
            self.update_dimension_cb()
            self.update_layer_cb()
            if self.widget.map_image_frame.contour_btn.isChecked():
                self._update_contours()
            # a new map, or a new grid for the same points, moves the point
            # the currently loaded image sits on
            self.update_marker()
        if self.grid_popup.isVisible():
            self._update_grid_popup()

    def update_dimension_cb(self):
        """Refreshes the quick-pick grid sizes shown in the grid popup."""
        map_model = self.model.map_model
        self.grid_popup.set_dimension_presets(
            list(map_model.possible_dimensions or []), map_model.dimension
        )

    def update_layer_cb(self):
        map_model = self.model.map_model
        layer_cb = self.widget.map_plot_control_widget.layer_cb
        names = map_model.layer_names()
        current = [layer_cb.itemText(i) for i in range(layer_cb.count())]
        layer_cb.blockSignals(True)
        try:
            if current != names:
                layer_cb.clear()
                layer_cb.addItems(names)
            if map_model.active_layer in names:
                layer_cb.setCurrentIndex(names.index(map_model.active_layer))
        finally:
            layer_cb.blockSignals(False)

    def _layer_cb_changed(self, _index):
        name = self.widget.map_plot_control_widget.layer_cb.currentText()
        if name:
            self.model.map_model.active_layer = name

    def _get_mouse_row_col(self, x, y):
        # bounds come from the model rather than the plotted image so that a
        # plot which has not caught up yet cannot index into a smaller map
        x, y = np.floor(x), np.floor(y)
        row = self.model.map_model.map.shape[0] - int(y) - 1
        col = int(x)
        return row, col

    def _row_col_in_map(self, row, col):
        map_data = self.model.map_model.map
        if map_data is None:
            return False
        map_shape = map_data.shape
        if row < 0 or col < 0 or row >= map_shape[0] or col >= map_shape[1]:
            return False
        return True

    def map_point_selected(self, clicked_x, clicked_y):
        # skip when no map is loaded
        if self.model.map_model.map is None:
            return

        row, col = self._get_mouse_row_col(clicked_x, clicked_y)

        # skip when the mouse is outside of the map
        if not self._row_col_in_map(row, col):
            return

        # a cell left blank by a dropped frame has no image behind it, but
        # it still has a row in the list worth pointing at
        index = self.model.map_model.get_point_index(row, col)
        if index is None:
            slot = self.model.map_model.get_slot_at(row, col)
            if slot is not None:
                self.blank_selected.emit(slot)
            return

        self.model.map_model.select_point(row, col)
        self.point_selected.emit(index)

    def set_marker_by_index(self, index: int):
        """Moves the selection marker onto the map point with the given index."""
        map_model = self.model.map_model
        if map_model.map is None:
            return
        coordinates = map_model.get_point_coordinates(index)
        if coordinates is None:
            return
        row, col = coordinates
        map_shape = map_model.map.shape
        self.widget.map_plot_widget.mouse_click_item.setVisible(True)
        self.widget.map_plot_widget.set_mouse_click_position(
            col + 0.5, map_shape[0] - row - 0.5  # 0.5 are there to shift to center
        )

    def update_marker(self):
        """Points the marker at the currently loaded image.

        Images can be loaded from anywhere (map click, file list, stepping
        through a directory in the integration view), so the marker follows
        the image model rather than any one of those controls. It is hidden
        while an image that is not part of the map is shown.
        """
        map_model = self.model.map_model
        if map_model.map is None:
            return
        img_model = self.model.img_model
        index = map_model.get_index_of_file(
            img_model.filename, img_model.series_pos - 1
        )
        if index is None:
            self.widget.map_plot_widget.mouse_click_item.setVisible(False)
        else:
            self.set_marker_by_index(index)

    def map_plot_mouse_moved(self, x, y):
        # shows the information for a point inside of the map
        # since pyqtgraph gives the coordinates in the image coordinate system
        # we need to flip the y axis

        # skip when no map is loaded
        if self.model.map_model.map is None:
            return

        row, col = self._get_mouse_row_col(x, y)

        # if the mouse is outside of the image, we don't want to show any information
        if not self._row_col_in_map(row, col):
            self.widget.map_plot_control_widget.mouse_x_label.setText(f"X: ")
            self.widget.map_plot_control_widget.mouse_y_label.setText(f"Y: ")
            self.widget.map_plot_control_widget.mouse_int_label.setText(f"I: ")
            self.widget.map_plot_control_widget.filename_label.setText(f"")
            return

        value = self.model.map_model.map[row, col]
        self.widget.map_plot_control_widget.mouse_x_label.setText(f"X: {col:.0f}")
        self.widget.map_plot_control_widget.mouse_y_label.setText(f"Y: {row:.0f}")
        self.widget.map_plot_control_widget.mouse_int_label.setText(
            "I: -" if not np.isfinite(value) else f"I: {value:.0f}"
        )

        point_info = self.model.map_model.get_point_info(row, col)
        if point_info is None:
            self.widget.map_plot_control_widget.filename_label.setText("(empty)")
            return

        if point_info.frame_index == 0:
            self.widget.map_plot_control_widget.filename_label.setText(
                f"{point_info.filename}"
            )
        else:
            self.widget.map_plot_control_widget.filename_label.setText(
                f"{point_info.filename} - Frame: {point_info.frame_index}"
            )

    def configuration_selected(self):
        # the watcher belongs to the previous configuration's map
        self.stop_live()
        self._update_map_model_connection()
        self.update_map()

    def _configuration_removed(self, _index=None):
        self.configuration_selected()

    def _update_map_model_connection(self):
        """Rebinds map_changed to the current configuration's map model.

        The map model is configuration-scoped, so the subscription made at
        construction time goes stale when the configuration changes (switch,
        add/remove, project load)."""
        if self.model.map_model is self._connected_map_model:
            return
        self._connected_map_model.map_changed.disconnect(self.update_map)
        self._connected_map_model = self.model.map_model
        self._connected_map_model.map_changed.connect(self.update_map)
