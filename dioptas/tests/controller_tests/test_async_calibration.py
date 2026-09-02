# SPDX-License-Identifier: MIT

from __future__ import annotations

import os
import threading

from dioptas.controller.CalibrationController import CalibrationController
from dioptas.model.DioptasModel import DioptasModel
from dioptas.widgets.CalibrationWidget import CalibrationWidget


def test_calibration_integration_runs_off_gui_thread(
    qtbot,
    test_data_path,
    monkeypatch,
):
    model = DioptasModel()
    model.current_configuration.auto_integrate_pattern = False
    model.calibration_model.load(
        os.path.join(test_data_path, "CeO2_Pilatus1M.poni")
    )
    model.img_model.load(os.path.join(test_data_path, "CeO2_Pilatus1M.tif"))
    widget = CalibrationWidget()
    qtbot.addWidget(widget)
    controller = CalibrationController(widget, model)

    real_compute = controller._integration_engine.compute
    started = threading.Event()
    release = threading.Event()
    worker_threads = []

    def controlled_compute(task):
        worker_threads.append(threading.get_ident())
        started.set()
        assert release.wait(timeout=5)
        return real_compute(task)

    monkeypatch.setattr(
        controller._integration_engine, "compute", controlled_compute
    )
    gui_thread = threading.get_ident()

    controller.update_all()

    assert started.wait(timeout=2)
    assert controller._integration_runner.is_busy
    assert worker_threads != [gui_thread]
    release.set()
    qtbot.waitUntil(lambda: not controller._integration_runner.is_busy, timeout=10000)

    assert model.pattern_model.pattern.x.size > 0
    assert model.cake_data.size > 0
    assert controller._integration_contexts == {}
    controller.shutdown()
