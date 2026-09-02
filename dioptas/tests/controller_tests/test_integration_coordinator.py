# SPDX-License-Identifier: MIT

from __future__ import annotations

import os
import threading

import pytest

from dioptas.controller.integration_coordinator import AsyncIntegrationCoordinator
from dioptas.model.DioptasModel import DioptasModel


def _loaded_model(test_data_path):
    model = DioptasModel()
    model.current_configuration.auto_integrate_pattern = False
    model.calibration_model.load(
        os.path.join(test_data_path, "CeO2_Pilatus1M.poni")
    )
    model.img_model.load(os.path.join(test_data_path, "CeO2_Pilatus1M.tif"))
    return model


def test_coordinator_debounces_and_merges_requests(
    qtbot,
    test_data_path,
    monkeypatch,
):
    model = _loaded_model(test_data_path)
    coordinator = AsyncIntegrationCoordinator(model, debounce_ms=25)
    real_compute = coordinator._integration_engine.compute
    tasks = []

    def recording_compute(task):
        tasks.append(task)
        return real_compute(task)

    monkeypatch.setattr(
        coordinator._integration_engine, "compute", recording_compute
    )
    config = model.current_configuration
    coordinator.request(
        config,
        calculate_pattern=True,
        calculate_cake=False,
    )
    generation = coordinator.request(
        config,
        calculate_pattern=False,
        calculate_cake=True,
    )
    completed = []
    coordinator.completed.connect(
        lambda configuration, result_generation: completed.append(
            (configuration, result_generation)
        )
    )

    qtbot.waitUntil(lambda: not coordinator.is_busy, timeout=10000)

    assert len(tasks) == 1
    assert tasks[0].calculate_pattern
    assert tasks[0].calculate_cake
    assert completed == [(config, generation)]
    coordinator.shutdown()


def test_coordinator_shutdown_detaches_configuration_scheduler(test_data_path):
    model = _loaded_model(test_data_path)
    coordinator = AsyncIntegrationCoordinator(model, debounce_ms=0)
    config = model.current_configuration

    coordinator.shutdown()

    assert config.integration_scheduler is None
    with pytest.raises(RuntimeError, match="after shutdown"):
        coordinator.request(
            config,
            calculate_pattern=True,
            calculate_cake=False,
        )


def test_coordinator_reports_task_snapshot_failure_and_recovers(
    qtbot,
    test_data_path,
    monkeypatch,
):
    model = _loaded_model(test_data_path)
    coordinator = AsyncIntegrationCoordinator(model, debounce_ms=0)
    config = model.current_configuration
    failures = []
    coordinator.failed.connect(
        lambda configuration, generation, exc: failures.append(
            (configuration, generation, exc)
        )
    )

    def fail_snapshot(**_kwargs):
        raise ValueError("bad snapshot")

    monkeypatch.setattr(config, "create_integration_task", fail_snapshot)
    generation = coordinator.request(
        config,
        calculate_pattern=True,
        calculate_cake=False,
        immediate=True,
    )

    qtbot.waitUntil(lambda: bool(failures), timeout=2000)

    assert failures[0][:2] == (config, generation)
    assert isinstance(failures[0][2], ValueError)
    assert not coordinator.is_busy
    coordinator.shutdown()


def test_coordinator_reports_result_application_failure_and_recovers(
    qtbot,
    test_data_path,
    monkeypatch,
):
    model = _loaded_model(test_data_path)
    coordinator = AsyncIntegrationCoordinator(model, debounce_ms=0)
    config = model.current_configuration
    failures = []
    completed = []
    coordinator.failed.connect(
        lambda configuration, generation, exc: failures.append(
            (configuration, generation, exc)
        )
    )
    coordinator.completed.connect(
        lambda configuration, generation: completed.append(
            (configuration, generation)
        )
    )

    def fail_apply(_result):
        raise ValueError("bad result")

    monkeypatch.setattr(config, "apply_integration_result", fail_apply)
    generation = coordinator.request(
        config,
        calculate_pattern=True,
        calculate_cake=False,
        immediate=True,
    )

    qtbot.waitUntil(lambda: bool(failures), timeout=10000)

    assert failures[0][:2] == (config, generation)
    assert isinstance(failures[0][2], ValueError)
    assert completed == []
    assert not coordinator.is_busy
    coordinator.shutdown()


def test_coordinator_discards_running_result_when_newer_request_arrives(
    qtbot,
    test_data_path,
    monkeypatch,
):
    model = _loaded_model(test_data_path)
    coordinator = AsyncIntegrationCoordinator(model, debounce_ms=0)
    real_compute = coordinator._integration_engine.compute
    first_started = threading.Event()
    release_first = threading.Event()
    call_count = 0

    def controlled_compute(task):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            first_started.set()
            assert release_first.wait(timeout=5)
        return real_compute(task)

    monkeypatch.setattr(
        coordinator._integration_engine, "compute", controlled_compute
    )
    config = model.current_configuration
    stale = []
    completed = []
    coordinator.stale_result_discarded.connect(
        lambda configuration, generation: stale.append(generation)
    )
    coordinator.completed.connect(
        lambda configuration, generation: completed.append(generation)
    )

    first_generation = coordinator.request(
        config,
        calculate_pattern=True,
        calculate_cake=False,
        immediate=True,
    )
    qtbot.waitUntil(first_started.is_set, timeout=2000)
    second_generation = coordinator.request(
        config,
        calculate_pattern=True,
        calculate_cake=False,
        immediate=True,
    )
    release_first.set()

    qtbot.waitUntil(lambda: not coordinator.is_busy, timeout=10000)

    assert call_count == 2
    assert stale == [first_generation]
    assert completed == [second_generation]
    coordinator.shutdown()


def test_coordinator_discards_result_when_image_changes_without_new_request(
    qtbot,
    test_data_path,
    monkeypatch,
):
    model = _loaded_model(test_data_path)
    coordinator = AsyncIntegrationCoordinator(model, debounce_ms=0)
    real_compute = coordinator._integration_engine.compute
    started = threading.Event()
    release = threading.Event()

    def controlled_compute(task):
        started.set()
        assert release.wait(timeout=5)
        return real_compute(task)

    monkeypatch.setattr(
        coordinator._integration_engine, "compute", controlled_compute
    )
    config = model.current_configuration
    stale = []
    completed = []
    coordinator.stale_result_discarded.connect(
        lambda configuration, generation: stale.append(generation)
    )
    coordinator.completed.connect(
        lambda configuration, generation: completed.append(generation)
    )

    generation = coordinator.request(
        config,
        calculate_pattern=True,
        calculate_cake=False,
        immediate=True,
    )
    qtbot.waitUntil(started.is_set, timeout=2000)
    model.img_model.load(os.path.join(test_data_path, "CeO2_Pilatus1M.tif"))
    release.set()

    qtbot.waitUntil(lambda: not coordinator.is_busy, timeout=10000)

    assert stale == [generation]
    assert completed == []
    coordinator.shutdown()


def test_coordinator_reuses_real_dioptrin_off_gui_thread(
    qtbot,
    test_data_path,
    monkeypatch,
):
    dioptrin = pytest.importorskip("dioptrin")
    try:
        dioptrin.validate_license()
    except Exception as exc:
        pytest.skip(f"Dioptrin license unavailable: {exc}")

    model = _loaded_model(test_data_path)
    calibration = model.calibration_model
    calibration.use_dioptrin = True
    calibration._create_dioptrin_integrator()
    if calibration._dioptrin_integrator is None:
        pytest.skip("Dioptrin integrator could not be created")

    coordinator = AsyncIntegrationCoordinator(model, debounce_ms=0)
    real_compute = coordinator._integration_engine.compute
    worker_threads = []
    backend_ids = []

    def recording_compute(task):
        worker_threads.append(threading.get_ident())
        result = real_compute(task)
        backend_ids.append(
            id(coordinator._integration_engine.dioptrin_integrator)
        )
        return result

    monkeypatch.setattr(
        coordinator._integration_engine, "compute", recording_compute
    )
    gui_thread = threading.get_ident()
    config = model.current_configuration

    coordinator.request(
        config,
        calculate_pattern=True,
        calculate_cake=False,
        immediate=True,
    )
    qtbot.waitUntil(lambda: not coordinator.is_busy, timeout=10000)

    coordinator.request(
        config,
        calculate_pattern=True,
        calculate_cake=False,
        immediate=True,
    )
    qtbot.waitUntil(lambda: not coordinator.is_busy, timeout=10000)

    assert len(backend_ids) == 2
    assert len(set(backend_ids)) == 1
    assert worker_threads and all(thread != gui_thread for thread in worker_threads)
    assert model.pattern_model.pattern.x.size > 0
    coordinator.shutdown()
