# SPDX-License-Identifier: MIT

from __future__ import annotations

import os
import threading
from importlib import import_module

import numpy as np
from qtpy import QtCore, QtWidgets

from dioptas.controller.MapController import MapController
from dioptas.controller.integration.BatchController import BatchController
from dioptas.model.Configuration import Configuration
from dioptas.model.DioptasModel import DioptasModel
from dioptas.widgets.MapWidget import MapWidget
from dioptas.widgets.integration import IntegrationWidget


def test_map_loading_integrates_off_gui_thread(qtbot, test_data_path, monkeypatch):
    model = DioptasModel()
    model.current_configuration.auto_integrate_pattern = False
    model.current_configuration.auto_integrate_cake = False
    model.calibration_model.load(
        os.path.join(test_data_path, "CeO2_Pilatus1M.poni")
    )
    widget = MapWidget()
    qtbot.addWidget(widget)
    controller = MapController(widget, model)

    controller_module = import_module("dioptas.controller.MapPanelController")
    image = os.path.join(
        test_data_path, "map", "Fe3O4C_M1_map_1_P1_E1_001.tif"
    )
    monkeypatch.setattr(controller_module, "open_files_dialog", lambda *args: [image])
    real_compute = controller_module.compute_map_integration
    started = threading.Event()
    release = threading.Event()
    worker_threads = []

    def controlled_compute(state, filenames, callback):
        worker_threads.append(threading.get_ident())
        started.set()
        assert release.wait(timeout=5)
        return real_compute(state, filenames, callback)

    monkeypatch.setattr(controller_module, "compute_map_integration", controlled_compute)
    shown_modalities = []
    real_show = QtWidgets.QProgressDialog.show

    def record_show(dialog):
        shown_modalities.append(dialog.windowModality())
        return real_show(dialog)

    monkeypatch.setattr(QtWidgets.QProgressDialog, "show", record_show)
    gui_thread = threading.get_ident()

    controller.load_btn_clicked()

    assert started.wait(timeout=2)
    assert controller.panel_controller._map_runner.is_busy
    assert worker_threads != [gui_thread]
    assert shown_modalities == [QtCore.Qt.NonModal]
    progress_dialog = next(iter(controller.panel_controller._map_jobs.values()))[1]
    assert not progress_dialog.autoClose()
    assert not progress_dialog.autoReset()
    QtCore.QTimer.singleShot(0, release.set)
    qtbot.waitUntil(release.is_set, timeout=1000)
    qtbot.waitUntil(
        lambda: not controller.panel_controller._map_runner.is_busy,
        timeout=10000,
    )

    assert model.map_model.num_points == 1
    assert controller.panel_controller._map_jobs == {}
    assert widget.map_panel_widget.map_plot_control_widget.load_btn.isEnabled()


def test_map_shutdown_discards_an_outstanding_result(
    qtbot, test_data_path, monkeypatch
):
    model = DioptasModel()
    model.current_configuration.auto_integrate_pattern = False
    model.current_configuration.auto_integrate_cake = False
    model.calibration_model.load(
        os.path.join(test_data_path, "CeO2_Pilatus1M.poni")
    )
    widget = MapWidget()
    qtbot.addWidget(widget)
    controller = MapController(widget, model)

    controller_module = import_module("dioptas.controller.MapPanelController")
    image = os.path.join(
        test_data_path, "map", "Fe3O4C_M1_map_1_P1_E1_001.tif"
    )
    monkeypatch.setattr(controller_module, "open_files_dialog", lambda *args: [image])
    real_compute = controller_module.compute_map_integration
    started = threading.Event()
    release = threading.Event()

    def controlled_compute(state, filenames, callback):
        started.set()
        assert release.wait(timeout=5)
        return real_compute(state, filenames, callback)

    monkeypatch.setattr(controller_module, "compute_map_integration", controlled_compute)

    controller.load_btn_clicked()
    assert started.wait(timeout=2)
    progress_dialog = next(iter(controller.panel_controller._map_jobs.values()))[1]

    controller.panel_controller.shutdown()

    assert controller.panel_controller._map_jobs
    assert not progress_dialog.isVisible()
    release.set()
    qtbot.waitUntil(
        lambda: not controller.panel_controller._map_runner.is_busy,
        timeout=10000,
    )
    qtbot.waitUntil(
        lambda: not controller.panel_controller._map_jobs,
        timeout=1000,
    )
    assert model.map_model.pattern_x is None


def test_batch_integration_runs_off_gui_thread(qtbot, test_data_path, monkeypatch):
    model = DioptasModel()
    model.current_configuration.auto_integrate_pattern = False
    model.current_configuration.auto_integrate_cake = False
    model.calibration_model.load(
        os.path.join(test_data_path, "CeO2_Pilatus1M.poni")
    )
    widget = IntegrationWidget()
    qtbot.addWidget(widget)
    controller = BatchController(widget, model)
    raw_file = os.path.join(
        test_data_path,
        "lambda",
        "testasapo1_1009_00002_m1_part00000.nxs",
    )
    controller.load_raw_data([raw_file])
    controller.set_navigation_raw((0, model.batch_model.n_img_all - 1))
    widget.batch_widget.mode_widget.view_f_btn.setChecked(True)
    widget.batch_widget.position_widget.step_raw_widget.stop_txt.setValue(0)

    controller_module = import_module(
        "dioptas.controller.integration.BatchController"
    )
    real_compute = controller_module.compute_batch_integration
    started = threading.Event()
    release = threading.Event()
    worker_threads = []

    def controlled_compute(task, callback):
        worker_threads.append(threading.get_ident())
        started.set()
        assert release.wait(timeout=5)
        return real_compute(task, callback)

    monkeypatch.setattr(
        controller_module, "compute_batch_integration", controlled_compute
    )
    gui_thread = threading.get_ident()

    controller.integrate()

    assert started.wait(timeout=2)
    assert controller._batch_runner.is_busy
    assert worker_threads != [gui_thread]
    QtCore.QTimer.singleShot(0, release.set)
    qtbot.waitUntil(release.is_set, timeout=1000)
    qtbot.waitUntil(lambda: not controller._batch_runner.is_busy, timeout=10000)

    assert model.batch_model.data.shape[0] == 1
    assert controller._batch_jobs == {}
    assert widget.batch_widget.control_widget.integrate_btn.isEnabled()


def test_background_result_stays_with_its_source_configuration(qtbot, monkeypatch):
    model = DioptasModel()
    widget = IntegrationWidget()
    qtbot.addWidget(widget)
    controller = BatchController(widget, model)
    source_batch = model.batch_model
    source_batch.binning = np.linspace(1, 10, 100)
    source_batch.data = np.vstack(
        [np.linspace(10, 20, 100), np.linspace(20, 10, 100)]
    )
    source_batch.n_img = len(source_batch.data)

    controller_module = import_module(
        "dioptas.controller.integration.BatchController"
    )
    real_compute = controller_module.compute_batch_background
    started = threading.Event()
    release = threading.Event()

    def controlled_compute(task, callback):
        started.set()
        assert release.wait(timeout=5)
        return real_compute(task, callback)

    monkeypatch.setattr(
        controller_module, "compute_batch_background", controlled_compute
    )

    controller.extract_background()
    assert started.wait(timeout=2)
    model.configurations.append(Configuration(model.working_directories))
    model.select_configuration(1)
    release.set()
    qtbot.waitUntil(lambda: not controller._background_runner.is_busy, timeout=5000)

    assert source_batch.bkg is not None
    assert model.batch_model.bkg is None


def test_batch_result_application_failure_restores_controls(
    qtbot,
    test_data_path,
    monkeypatch,
):
    model = DioptasModel()
    model.current_configuration.auto_integrate_pattern = False
    model.current_configuration.auto_integrate_cake = False
    model.calibration_model.load(
        os.path.join(test_data_path, "CeO2_Pilatus1M.poni")
    )
    widget = IntegrationWidget()
    qtbot.addWidget(widget)
    controller = BatchController(widget, model)
    raw_file = os.path.join(
        test_data_path,
        "lambda",
        "testasapo1_1009_00002_m1_part00000.nxs",
    )
    controller.load_raw_data([raw_file])
    controller.set_navigation_raw((0, model.batch_model.n_img_all - 1))
    widget.batch_widget.mode_widget.view_f_btn.setChecked(True)
    widget.batch_widget.position_widget.step_raw_widget.stop_txt.setValue(0)

    controller_module = import_module(
        "dioptas.controller.integration.BatchController"
    )
    errors = []
    monkeypatch.setattr(
        controller_module,
        "apply_batch_integration",
        lambda *_args: (_ for _ in ()).throw(ValueError("bad result")),
    )
    monkeypatch.setattr(widget, "show_error_msg", errors.append)

    controller.integrate()
    qtbot.waitUntil(lambda: not controller._batch_runner.is_busy, timeout=10000)

    assert errors == ["bad result"]
    assert controller._batch_jobs == {}
    assert widget.batch_widget.control_widget.integrate_btn.isEnabled()


def test_map_shutdown_stops_live_watcher(qtbot, monkeypatch):
    model = DioptasModel()
    widget = MapWidget()
    qtbot.addWidget(widget)
    controller = MapController(widget, model)
    stop_live = []
    monkeypatch.setattr(
        controller.panel_controller,
        "stop_live",
        lambda: stop_live.append(True),
    )

    controller.panel_controller.shutdown()

    assert stop_live == [True]
