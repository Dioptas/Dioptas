# SPDX-License-Identifier: MIT
"""Exercise the real background worker and GUI delivery without opening a page."""

import importlib
import json
import threading
from unittest.mock import MagicMock

import pytest
from qtpy import QtCore, QtGui, QtWidgets


@pytest.fixture
def notification_controller(qtbot, tmp_path):
    module = importlib.import_module("dioptas.controller.MainController")
    controller = module.MainController.__new__(module.MainController)
    controller.widget = QtWidgets.QWidget()
    qtbot.addWidget(controller.widget)
    controller.settings_directory = str(tmp_path / "settings")
    return controller


@pytest.mark.parametrize("answer", [
    QtWidgets.QMessageBox.Yes, QtWidgets.QMessageBox.No, 0,
], ids=["open-download", "decline", "dismiss"])
def test_release_is_not_announced_again_after_restart(
    notification_controller, monkeypatch, answer,
):
    controller = notification_controller
    dialogs = []
    opened = []
    monkeypatch.setattr(QtWidgets.QMessageBox, "exec_",
                        lambda dialog: dialogs.append(dialog.text()) or answer)
    monkeypatch.setattr(QtGui.QDesktopServices, "openUrl",
                        lambda url: opened.append(url.toString()))
    url = "https://github.com/Dioptas/Dioptas/releases/tag/0.12.0"
    controller._show_update_notification("0.12.0", url)
    controller._show_update_notification("0.12.0", url)

    # A fresh controller reads the persisted state instead of instance memory.
    restarted = type(controller).__new__(type(controller))
    restarted.widget = controller.widget
    restarted.settings_directory = controller.settings_directory
    restarted._show_update_notification("0.12.0", url)
    assert len(dialogs) == 1
    assert opened == ([url] if answer == QtWidgets.QMessageBox.Yes else [])


def test_new_release_gets_one_new_notification(notification_controller, monkeypatch):
    dialogs = []
    monkeypatch.setattr(QtWidgets.QMessageBox, "exec_",
                        lambda dialog: dialogs.append(dialog.text()) or QtWidgets.QMessageBox.No)
    controller = notification_controller
    for version in ["0.12.0", "0.12.0", "0.13.0", "0.13.0", "0.12.0"]:
        controller._show_update_notification(version, "https://example.com/release")
    assert len(dialogs) == 2
    assert "Dioptas 0.12.0 is available" in dialogs[0]
    assert "Dioptas 0.13.0 is available" in dialogs[1]


def test_invalid_saved_version_does_not_hide_updates(notification_controller, monkeypatch):
    controller = notification_controller
    settings = QtCore.QSettings(
        controller.settings_directory + "/updates.ini", QtCore.QSettings.IniFormat)
    settings.setValue("last_notified_version", "invalid")
    settings.sync()
    dialogs = []
    monkeypatch.setattr(QtWidgets.QMessageBox, "exec_",
                        lambda dialog: dialogs.append(dialog.text()) or QtWidgets.QMessageBox.No)
    controller._show_update_notification("0.12.0", "https://example.com/release")
    assert len(dialogs) == 1


def test_release_feed_result_reaches_notification_on_gui_thread(
    main_controller, qtbot, monkeypatch
):
    controller_module = importlib.import_module("dioptas.controller.MainController")
    checker = importlib.import_module("dioptas.model.UpdateChecker")
    monkeypatch.setattr(controller_module, "__version__", "0.10.0")
    gui_thread = threading.get_ident()
    request_threads, notifications = [], []
    url = "https://github.com/Dioptas/Dioptas/releases/tag/0.11.0"
    response = MagicMock()
    response.__enter__.return_value = response
    response.read.return_value = json.dumps({"tag_name": "0.11.0", "html_url": url}).encode()

    def fetch(request, **kwargs):
        assert request.full_url == "https://api.github.com/repos/Dioptas/Dioptas/releases/latest"
        request_threads.append(threading.get_ident())
        return response

    def notify(version, page):
        notifications.append((version, page, threading.get_ident()))

    monkeypatch.setattr(checker.urllib.request, "urlopen", fetch)
    monkeypatch.setattr(main_controller, "_show_update_notification", notify)
    main_controller._check_for_update()
    qtbot.waitUntil(lambda: bool(notifications), timeout=3000)
    assert notifications == [("0.11.0", url, gui_thread)]
    assert len(request_threads) == 1 and request_threads[0] != gui_thread


def test_failed_recheck_clears_old_result(main_controller, qtbot, monkeypatch):
    module = importlib.import_module("dioptas.controller.MainController")
    main_controller._update_result = {"version": "old", "url": "old"}
    show = MagicMock()
    monkeypatch.setattr(main_controller, "_show_update_notification", show)
    monkeypatch.setattr(module, "check_for_update", lambda version: None)
    main_controller._check_for_update()
    qtbot.waitUntil(lambda: not main_controller._update_timer.isActive(), timeout=3000)
    assert main_controller._update_result is None
    show.assert_not_called()


def test_closing_window_suppresses_late_notification(main_controller, qtbot, monkeypatch):
    module = importlib.import_module("dioptas.controller.MainController")
    show = MagicMock()
    monkeypatch.setattr(main_controller, "_show_update_notification", show)
    monkeypatch.setattr(module, "check_for_update", lambda version: {"version": "1.0", "url": "page"})
    main_controller._check_for_update()
    main_controller._closing = True
    qtbot.waitUntil(lambda: not main_controller._update_timer.isActive(), timeout=3000)
    show.assert_not_called()
