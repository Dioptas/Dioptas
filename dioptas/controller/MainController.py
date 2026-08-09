# SPDX-License-Identifier: MIT

import os
import logging
import json
import datetime
import threading
import subprocess
import shlex
from functools import partial
from sys import platform as _platform

from qtpy import QtWidgets, QtCore, QtGui

from ..widgets.MainWidget import MainWidget
from ..model.DioptasModel import DioptasModel, UnsupportedProjectFileError
from ..widgets.UtilityWidgets import save_file_dialog, open_file_dialog

from . import CalibrationController
from .integration import IntegrationController
from .MaskController import MaskController
from .ConfigurationController import ConfigurationController
from .MapController import MapController
from .MapPanelController import MapPanelController

from dioptas import __version__
from ..model.UpdateChecker import check_for_update

logger = logging.getLogger(__name__)


class MainController:
    """
    Creates the main controller for Dioptas. Creates all the data objects and connects them with the other controllers
    """

    def __init__(self, use_settings=True, settings_directory="default", config_file=None):
        """
        :param use_settings: whether to use previously auto saved state of dioptas
        :param settings_directory: directory where the settings are saved
        :param config_file: a json file path with configuration, currently only used for quick_actions
        """
        self.use_settings = use_settings
        self.widget = MainWidget()

        # create data
        if settings_directory == "default":
            self.settings_directory = os.path.join(os.path.expanduser("~"), ".Dioptas")
        else:
            self.settings_directory = settings_directory

        self.model = DioptasModel()

        self.calibration_controller = CalibrationController(
            self.widget.calibration_widget, self.model
        )
        self.mask_controller = MaskController(self.widget.mask_widget, self.model)
        self.integration_controller = IntegrationController(
            self.widget.integration_widget, self.model
        )
        # The map panel moves between the map mode and its own window, so it
        # is owned here rather than by the mode it happens to sit in.
        self.map_panel_controller = MapPanelController(
            self.widget.map_widget.map_panel_widget, self.model
        )
        self.map_controller = MapController(
            self.widget.map_widget, self.model, self.map_panel_controller
        )
        self._map_panel_host = self.widget.map_widget.map_panel_host
        self._closing = False

        self.calibration_controller.activate()
        self.integration_controller.image_controller.deactivate()
        self.map_controller.deactivate()
        self.mask_controller.deactivate()

        self.configuration_controller = ConfigurationController(
            configuration_widget=self.widget.configuration_widget,
            dioptas_model=self.model,
            controllers=[
                self.calibration_controller,
                self.mask_controller,
                self.integration_controller,
                self,
            ],
        )

        self.create_signals()
        self.update_title()

        if use_settings:
            QtCore.QTimer.singleShot(0, self.load_default_settings)
            self.setup_backup_timer()

        if config_file is not None:
            self.configuration = json.load(open(config_file, "r"))
            self.create_external_actions()

        self.current_tab_index = 0

        if use_settings:
            self._check_for_update()

    def _check_for_update(self):
        """Run update check in a background thread to avoid blocking startup."""

        def _do_check():
            result = check_for_update(__version__)
            if result is not None:
                self._update_result = result

        def _on_check_finished():
            result = getattr(self, "_update_result", None)
            if result is not None:
                self._show_update_notification(result["version"], result["url"])

        self._update_thread = threading.Thread(target=_do_check, daemon=True)
        self._update_timer = QtCore.QTimer(self.widget)
        self._update_timer.setSingleShot(True)
        self._update_timer.setInterval(500)
        self._update_timer.timeout.connect(
            lambda: (
                _on_check_finished()
                if not self._update_thread.is_alive()
                else self._update_timer.start(500)
            )
        )
        self._update_thread.start()
        self._update_timer.start(500)

    def _show_update_notification(self, version: str, url: str):
        from qtpy.QtGui import QDesktopServices
        from qtpy.QtCore import QUrl

        msg = QtWidgets.QMessageBox(self.widget)
        msg.setIcon(QtWidgets.QMessageBox.Information)
        msg.setWindowTitle("Update Available")
        msg.setText(
            f"Dioptas {version} is available (you have {__version__})."
        )
        msg.setInformativeText("Would you like to open the download page?")
        msg.setStandardButtons(
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
        )
        msg.setDefaultButton(QtWidgets.QMessageBox.Yes)
        if msg.exec_() == QtWidgets.QMessageBox.Yes:
            QDesktopServices.openUrl(QUrl(url))

    def show_window(self):
        """
        Displays the main window on the screen and makes it active.
        """
        self.widget.show()

        if _platform == "darwin":
            self.widget.setWindowState(
                self.widget.windowState() & ~QtCore.Qt.WindowMinimized
                | QtCore.Qt.WindowActive
            )
            self.widget.activateWindow()
            self.widget.raise_()

    def create_signals(self):
        """
        Creates subscriptions for changing tabs and also newly loaded files which will update the title of the main
                window.
        """
        self.widget.closeEvent = self.close_event
        self.widget.show_configuration_menu_btn.toggled.connect(
            self.widget.configuration_widget.setVisible
        )

        self.widget.calibration_mode_btn.toggled.connect(
            self.widget.calibration_widget.setVisible
        )
        self.widget.mask_mode_btn.toggled.connect(self.widget.mask_widget.setVisible)
        self.widget.integration_mode_btn.toggled.connect(
            self.widget.integration_widget.setVisible
        )
        self.widget.map_mode_btn.toggled.connect(self.widget.map_widget.setVisible)

        self.widget.mode_btn_group.buttonToggled.connect(self.tab_changed)

        self.model.img_changed.connect(self.update_title)
        self.model.pattern_changed.connect(self.update_title)

        map_panel = self.widget.map_widget.map_panel_widget
        map_panel.map_plot_control_widget.undock_btn.clicked.connect(
            self.map_undock_btn_clicked
        )
        self.widget.map_widget.map_panel_host.dock_btn.clicked.connect(
            self.map_dock_btn_clicked
        )
        self.widget.map_panel_window.closed.connect(self._map_window_closed)
        self.model.view.events.map_docked.connect(self._map_docked_changed)

        self.widget.save_btn.clicked.connect(self.save_btn_clicked)
        self.widget.load_btn.clicked.connect(self.load_btn_clicked)
        self.widget.reset_btn.clicked.connect(self.reset_btn_clicked)

        self._next_image_shortcut = QtGui.QShortcut(
            QtGui.QKeySequence("Ctrl+Right"), self.widget
        )
        self._next_image_shortcut.activated.connect(
            lambda: self.model.next_image()
        )
        self._previous_image_shortcut = QtGui.QShortcut(
            QtGui.QKeySequence("Ctrl+Left"), self.widget
        )
        self._previous_image_shortcut.activated.connect(
            lambda: self.model.previous_image()
        )

        # Undo/redo work in every mode, not just the mask: the history is a
        # single application-wide stack (see model/state/snapshot.py). Both
        # redo sequences are bound because Ctrl+Shift+Z is the platform
        # convention here while Ctrl+Y is what the mask mode always used.
        self._undo_shortcut = QtGui.QShortcut(
            QtGui.QKeySequence.StandardKey.Undo, self.widget
        )
        self._undo_shortcut.activated.connect(self.undo)
        self._redo_shortcuts = [
            QtGui.QShortcut(QtGui.QKeySequence.StandardKey.Redo, self.widget),
            QtGui.QShortcut(QtGui.QKeySequence("Ctrl+Y"), self.widget),
        ]
        for shortcut in self._redo_shortcuts:
            shortcut.activated.connect(self.redo)

        self.widget.undo_btn.clicked.connect(self.undo)
        self.widget.redo_btn.clicked.connect(self.redo)
        self.model.history.changed.connect(self.update_history_buttons)
        self.update_history_buttons()

    def undo(self):
        self.model.history.undo()

    def redo(self):
        self.model.history.redo()

    def update_history_buttons(self):
        """Greys the sidebar buttons out at the ends of the history and names
        the step each would apply, together with its shortcut."""
        history = self.model.history
        undo_key = _shortcut_text(QtGui.QKeySequence.StandardKey.Undo)
        redo_key = _shortcut_text(QtGui.QKeySequence.StandardKey.Redo)

        self.widget.set_history_enabled(history.can_undo, history.can_redo)
        self.widget.undo_btn.setToolTip(
            f"Undo {history.undo_label} ({undo_key})"
            if history.can_undo
            else f"Nothing to undo ({undo_key})"
        )
        self.widget.redo_btn.setToolTip(
            f"Redo {history.redo_label} ({redo_key})"
            if history.can_redo
            else f"Nothing to redo ({redo_key})"
        )

    def tab_changed(self):
        """
        Function which is called when a tab has been selected (calibration, mask, or integration). Performs
        needed initialization tasks.
        :return:
        """
        if self.widget.calibration_mode_btn.isChecked():
            ind = 0
        elif self.widget.mask_mode_btn.isChecked():
            ind = 1
        elif self.widget.integration_mode_btn.isChecked():
            ind = 2
        elif self.widget.map_mode_btn.isChecked():
            ind = 3
        else:
            return

        if ind == self.current_tab_index:
            return

        old_index = self.current_tab_index
        self.current_tab_index = ind
        logger.info("Switched to %s mode", ["calibration", "mask", "integration", "map"][ind])

        # changing from mask tab will reintegrate the image
        if old_index == 1:  # mask tab
            if self.model.use_mask and self.model.calibration_model.is_calibrated:
                self.model.current_configuration.integrate_image_1d()
                if self.model.current_configuration.auto_integrate_cake:
                    self.model.current_configuration.integrate_image_2d()

        # update the GUI
        if ind == 2:  # integration tab
            self.integration_controller.image_controller.update_image()

        self.activate_mode(ind)
        self.update_image_display_state(old_index, ind)

    def place_map_panel(self):
        """Moves the map panel between the map mode and its own window.

        Undocked it stays in its window whatever mode is shown, which is how
        the map is used next to the integration view.
        """
        window = self.widget.map_panel_window
        if self.model.view.map_docked:
            host = self.widget.map_widget.map_panel_host
        else:
            host = window

        if host is self._map_panel_host:
            return

        self._map_panel_host.release_panel()
        host.take_panel(self.widget.map_widget.map_panel_widget)
        self._map_panel_host = host

        window.setVisible(host is window)

    def map_undock_btn_clicked(self):
        self.model.view.map_docked = not self.model.view.map_docked

    def map_dock_btn_clicked(self):
        self.model.view.map_docked = True

    def _map_docked_changed(self, docked, _old=None):
        self.widget.map_widget.map_panel_widget.map_plot_control_widget.undock_btn.setText(
            "Undock" if docked else "Dock"
        )
        self.place_map_panel()

    def _map_window_closed(self):
        # on shutdown every window is closed; docking back then would undo the
        # state that was just saved and reparent widgets on their way out
        if self._closing:
            return
        if not self.model.view.map_docked:
            self.model.view.map_docked = True

    def activate_mode(self, mode_ind):
        controllers = [
            self.calibration_controller,
            self.mask_controller,
            self.integration_controller.image_controller,
            self.map_controller
        ]
        for i, controller in enumerate(controllers):
            if i == mode_ind:
                controller.activate()
            else:
                controller.deactivate()

    def update_image_display_state(self, old_index, new_index):
        img_widgets = [
            self.widget.calibration_widget.img_widget,
            self.widget.mask_widget.img_widget,
            self.widget.integration_widget.img_widget,
            self.widget.map_widget.img_plot_widget
        ]
        old_display_state = img_widgets[old_index].get_display_state()
        img_widgets[new_index].set_display_state(*old_display_state)

    def update_title(self):
        """
        Updates the title bar of the main window. The title bar will always show the current version of Dioptas, the
        image or pattern filenames loaded and the current calibration name.
        """
        img_filename = os.path.basename(self.model.img_model.filename)
        pattern_filename = os.path.basename(self.model.pattern.filename)
        calibration_name = self.model.calibration_model.calibration_name
        year = datetime.datetime.now().year
        dioptas_str = "Dioptas " + __version__ + " - © {} C. Prescher".format(year)

        if img_filename == "" and pattern_filename == "":
            self.widget.setWindowTitle(dioptas_str)
            self.widget.integration_widget.img_frame.setWindowTitle(dioptas_str)
            return

        str = ""
        if img_filename != "":
            str += img_filename
        elif img_filename == "" and pattern_filename != "":
            str += pattern_filename
        if not img_filename == pattern_filename and pattern_filename != "":
            str += ", " + pattern_filename
        if calibration_name != "":
            str += ", calibration: " + calibration_name
        str += " | " + dioptas_str 
        self.widget.setWindowTitle(str)
        self.widget.integration_widget.img_frame.setWindowTitle(str)

    def save_default_settings(self):
        if not os.path.exists(self.settings_directory):
            os.mkdir(self.settings_directory)
        self.model.save(os.path.join(self.settings_directory, "config.dio"))

    def load_default_settings(self):
        config_path = os.path.join(self.settings_directory, "config.dio")
        if os.path.isfile(config_path):
            self.show_window()
            if QtWidgets.QMessageBox.Yes == QtWidgets.QMessageBox.question(
                    self.widget,
                    "Recovering previous state.",
                    "Should Dioptas recover your previous Work?",
                    QtWidgets.QMessageBox.Yes,
                    QtWidgets.QMessageBox.No,
            ):
                try:
                    self.model.load(os.path.join(self.settings_directory, "config.dio"))
                    logger.info("Restored previous session from %s", config_path)
                except Exception as e:
                    logger.error("Failed to restore previous state: %s", e)
                    QtWidgets.QMessageBox.critical(
                        self.widget,
                        "Error restoring previous state.",
                        str(e),
                    )
            else:
                self.load_directories()

    def setup_backup_timer(self):
        """Periodically backs up the session, but only when something changed.

        The backup writes the whole project (including image data), so the
        write frequency stays bounded by the timer; the dirty flag only
        removes the pointless writes of an idle session."""
        self._backup_dirty = False
        for signal in (
            self.model.configuration_params_changed,
            self.model.img_changed,
            self.model.pattern_changed,
            self.model.configuration_added,
            self.model.configuration_removed,
        ):
            signal.connect(self._mark_backup_dirty)
        self.model.view.events.connect(self._mark_backup_dirty)

        self.backup_timer = QtCore.QTimer(self.widget)
        self.backup_timer.timeout.connect(self.save_backup_if_changed)
        self.backup_timer.setInterval(600000)  # every 10 minutes
        self.backup_timer.start()

    def _mark_backup_dirty(self, *_args):
        self._backup_dirty = True

    def save_backup_if_changed(self):
        if not self._backup_dirty:
            return
        self.save_default_settings()
        self._backup_dirty = False

    def save_directories(self):
        """
        Currently used working directories for images, spectra, etc. are saved as csv file in the users directory for
        reuse when Dioptas is started again without loading a configuration
        """
        working_directories_path = os.path.join(
            self.settings_directory, "working_directories.json"
        )
        json.dump(self.model.working_directories, open(working_directories_path, "w"))

    def load_directories(self):
        """
        Loads previously used Dioptas directory paths.
        """
        working_directories_path = os.path.join(
            self.settings_directory, "working_directories.json"
        )
        if os.path.exists(working_directories_path):
            self.model.working_directories = json.load(
                open(working_directories_path, "r")
            )

    def close_event(self, ev):
        """
        Intervention of the Dioptas close event to save settings before closing the Program.
        """
        logger.info("Closing Dioptas")
        self._closing = True
        if self.use_settings:
            self.save_default_settings()
            self.save_directories()
        QtWidgets.QApplication.closeAllWindows()
        ev.accept()

    def save_btn_clicked(self):
        try:
            default_file_name = os.path.join(
                self.model.working_directories["project"], "config.dio"
            )
        except (TypeError, KeyError):
            default_file_name = "."
        filename = save_file_dialog(
            self.widget,
            "Save Current Dioptas Project",
            default_file_name,
            filter="Dioptas Project (*.dio)",
        )

        if filename is not None and filename != "":
            logger.info("Saving project to %s", filename)
            self.model.save(filename)
            self.model.working_directories["project"] = os.path.dirname(filename)

    def load_btn_clicked(self):
        try:
            default_file_name = os.path.join(
                self.model.working_directories["project"], "config.dio"
            )
        except (TypeError, KeyError):
            default_file_name = "."
        filename = open_file_dialog(
            self.widget,
            "Load a Dioptas Project",
            default_file_name,
            filter="Dioptas Project (*.dio)",
        )
        if filename is not None and filename != "":
            logger.info("Loading project from %s", filename)
            try:
                self.model.load(filename)
            except UnsupportedProjectFileError as error:
                QtWidgets.QMessageBox.critical(
                    self.widget, "Cannot open this project file", str(error)
                )
                return
            self.model.working_directories["project"] = os.path.dirname(filename)

    def reset_btn_clicked(self):
        if QtWidgets.QMessageBox.Yes == QtWidgets.QMessageBox.question(
                self.widget,
                "Resetting Dioptas.",
                "Do you really want to reset Dioptas?\nAll unsaved work will be lost!",
                QtWidgets.QMessageBox.Yes,
                QtWidgets.QMessageBox.No,
        ):
            self.model.reset()

    def create_external_actions(self):
        self.widget.create_external_actions(self.configuration["external_actions"])
        for action in self.configuration["external_actions"]:
            self.widget.external_action_btns[action["name"]].clicked.connect(
                partial(
                    self.execute_action,
                    action
                )
            )

    def execute_action(self, action):
        command = format(action["command"])
        arguments = action["arguments"]
        img_path = self.model.img_model.filename
        frame_index = self.model.img_model.series_pos

        combined_arguments = f"{arguments} \"{img_path}\" {frame_index}"
        command_str = " ".join([command, combined_arguments])

        # prepare command_str for Popen
        args = shlex.split(command_str)

        def run_command():
            """Run the command with arguments pulse the image file path."""
            subprocess.Popen(args, shell=True)

        threading.Thread(target=run_command).start()

        return command_str


def _shortcut_text(standard_key) -> str:
    """The shortcut to advertise for a standard action, as the user's keyboard
    shows it.

    Qt lists several bindings per action and its first choice for Redo is
    Ctrl+Y, but the Z-based variant is the platform convention on macOS and
    reads better next to the Undo shortcut shown beside it, so that one wins
    when it is available.
    """
    bindings = QtGui.QKeySequence.keyBindings(standard_key)
    if not bindings:
        return ""
    native = QtGui.QKeySequence.SequenceFormat.NativeText
    for binding in bindings:
        if binding.toString().endswith("Z"):
            return binding.toString(native)
    return bindings[0].toString(native)
