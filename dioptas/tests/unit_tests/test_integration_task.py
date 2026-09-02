# SPDX-License-Identifier: MIT

from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace
import sys

import numpy as np
from pyFAI.integrator.azimuthal import AzimuthalIntegrator
import pytest

from dioptas.model.integration_task import (
    PersistentIntegrationEngine,
    compute_integration,
)


def test_worker_task_matches_synchronous_pattern_integration(calibrated_config):
    config = calibrated_config
    config.auto_integrate_pattern = False
    task = config.create_integration_task(calculate_pattern=True)

    worker_result = compute_integration(task)
    expected_x, expected_y = config.calibration_model.integrate_1d(
        num_points=config.integration_rad_points,
        mask=config.mask_model.get_mask() if config.use_mask else None,
        unit=config.integration_unit,
        azi_range=config.oned_azimuth_range,
        trim_zeros=config.trim_trailing_zeros,
        calculate_errors=config.calculate_poisson_errors,
    )

    np.testing.assert_allclose(worker_result.pattern.radial, expected_x)
    np.testing.assert_allclose(worker_result.pattern.intensity, expected_y)


def test_fully_masked_worker_task_preserves_the_previous_pattern(
    calibrated_config,
):
    config = calibrated_config
    config.auto_integrate_pattern = False
    previous_x = np.array([1.0, 2.0])
    previous_y = np.array([3.0, 4.0])
    config.calibration_model.tth = previous_x
    config.calibration_model.int = previous_y
    config.pattern_model.set_pattern(previous_x, previous_y, "previous.tif")
    config.use_mask = True
    config.mask_model.set_mask_data(
        np.ones(config.img_model.img_data.shape, dtype=bool)
    )

    task = config.create_integration_task(calculate_pattern=True)
    result = compute_integration(task)
    config.apply_integration_result(result)

    assert not task.calculate_pattern
    assert result.pattern is None
    np.testing.assert_array_equal(config.pattern_model.pattern.x, previous_x)
    np.testing.assert_array_equal(config.pattern_model.pattern.y, previous_y)


def test_worker_task_matches_synchronous_cake_integration(calibrated_config):
    config = calibrated_config
    config.auto_integrate_pattern = False
    task = config.create_integration_task(
        calculate_pattern=False,
        calculate_cake=True,
    )

    worker_result = compute_integration(task)
    expected = config.calibration_model.integrate_2d(
        mask=config.mask_model.get_mask() if config.use_mask else None,
        unit=config.integration_unit,
        rad_points=config.integration_rad_points,
        azimuth_points=config.cake_azimuth_points,
        azimuth_range=config.cake_azimuth_range,
    )

    np.testing.assert_allclose(worker_result.cake.intensity, expected)
    np.testing.assert_allclose(
        worker_result.cake.radial,
        config.calibration_model.cake_tth,
    )
    np.testing.assert_allclose(
        worker_result.cake.azimuthal,
        config.calibration_model.cake_azi,
    )


def test_worker_cake_stays_in_two_theta_when_pattern_unit_changes(
    calibrated_config,
):
    config = calibrated_config
    config.auto_integrate_pattern = False
    config.integration_unit = "q_A^-1"
    task = config.create_integration_task(
        calculate_pattern=False,
        calculate_cake=True,
    )

    worker_result = compute_integration(task)
    config.integrate_image_2d()

    np.testing.assert_allclose(
        worker_result.cake.radial,
        config.calibration_model.cake_tth,
    )


def test_apply_worker_result_updates_models_and_emits(calibrated_config):
    config = calibrated_config
    config.auto_integrate_pattern = False
    task = config.create_integration_task(
        calculate_pattern=True,
        calculate_cake=True,
    )
    result = compute_integration(task)
    pattern_events = []
    cake_events = []
    config.pattern_model.pattern_changed.connect(lambda: pattern_events.append(True))
    config.cake_changed.connect(lambda: cake_events.append(True))

    config.apply_integration_result(result)

    np.testing.assert_allclose(config.pattern_model.pattern.x, result.pattern.radial)
    np.testing.assert_allclose(config.pattern_model.pattern.y, result.pattern.intensity)
    np.testing.assert_allclose(config.cake_img, result.cake.intensity)
    assert pattern_events == [True]
    assert cake_events == [True]


def test_persistent_engine_reuses_pyfai_until_geometry_changes(
    calibrated_config,
):
    task = calibrated_config.create_integration_task(calculate_pattern=True)
    created = []

    def factory():
        integrator = AzimuthalIntegrator()
        created.append(integrator)
        return integrator

    engine = PersistentIntegrationEngine(pyfai_factory=factory)

    engine.compute(task)
    first_integrator = engine.pyfai_integrator
    engine.compute(task)

    assert created == [first_integrator]

    changed_config = dict(task.geometry_config)
    changed_config["dist"] += 0.001
    engine.compute(replace(task, geometry_config=changed_config))

    assert len(created) == 2
    assert engine.pyfai_integrator is not first_integrator


def test_persistent_engine_reuses_dioptrin_until_geometry_changes(
    calibrated_config,
    monkeypatch,
):
    created = []

    class FakeDioptrinIntegrator:
        def __init__(self):
            self.integrations = 0
            self.method_updates = 0
            self.unit_updates = 0
            self.mask_updates = 0
            self.polarization_updates = 0

        def set_method(self, *_args, **_kwargs):
            self.method_updates += 1

        def set_unit(self, _unit):
            self.unit_updates += 1

        def set_mask(self, _mask):
            self.mask_updates += 1

        def set_polarization_factor(self, _factor):
            self.polarization_updates += 1

        def integrate1d(self, _image, num_points, **_kwargs):
            self.integrations += 1
            return SimpleNamespace(
                radial=np.linspace(1, 20, num_points),
                intensity=np.ones(num_points),
                errors=None,
            )

    class FakeIntegratorFactory:
        @staticmethod
        def from_poni_dict(*_args, **_kwargs):
            integrator = FakeDioptrinIntegrator()
            created.append(integrator)
            return integrator

    monkeypatch.setitem(
        sys.modules,
        "dioptrin",
        SimpleNamespace(Integrator=FakeIntegratorFactory),
    )
    base_task = calibrated_config.create_integration_task(calculate_pattern=True)
    task = replace(
        base_task,
        pattern_num_points=100,
        prefer_dioptrin=True,
        dioptrin_geometry_config={"distance": 0.2},
    )
    engine = PersistentIntegrationEngine()

    engine.compute(task)
    first_integrator = engine.dioptrin_integrator
    engine.compute(task)

    assert created == [first_integrator]
    assert first_integrator.integrations == 2
    assert first_integrator.method_updates == 1
    assert first_integrator.unit_updates == 1
    assert first_integrator.mask_updates == 1
    assert first_integrator.polarization_updates == 1

    changed_config = dict(task.geometry_config)
    changed_config["dist"] += 0.001
    engine.compute(
        replace(
            task,
            geometry_config=changed_config,
            dioptrin_geometry_config={"distance": 0.201},
        )
    )

    assert len(created) == 2
    assert engine.dioptrin_integrator is not first_integrator


def test_dioptrin_keeps_separate_persistent_units_for_q_pattern_and_cake(
    calibrated_config,
    monkeypatch,
):
    created = []

    class FakeIntegrator:
        def __init__(self):
            self.unit_updates = 0

        def set_method(self, *_args, **_kwargs):
            pass

        def set_unit(self, _unit):
            self.unit_updates += 1

        def set_mask(self, _mask):
            pass

        def set_polarization_factor(self, _factor):
            pass

        def integrate1d(self, _image, num_points, **_kwargs):
            return SimpleNamespace(
                radial=np.linspace(1, 20, num_points),
                intensity=np.ones(num_points),
                errors=None,
            )

        def integrate2d(
            self, _image, num_points, azimuth_points, **_kwargs
        ):
            return SimpleNamespace(
                radial=np.linspace(1, 20, num_points),
                azimuthal=np.linspace(-180, 180, azimuth_points),
                intensity=np.ones(num_points * azimuth_points),
            )

    class FakeFactory:
        @staticmethod
        def from_poni_dict(*_args, **_kwargs):
            integrator = FakeIntegrator()
            created.append(integrator)
            return integrator

    monkeypatch.setitem(
        sys.modules,
        "dioptrin",
        SimpleNamespace(Integrator=FakeFactory),
    )
    base_task = calibrated_config.create_integration_task(
        calculate_pattern=True,
        calculate_cake=True,
    )
    task = replace(
        base_task,
        unit="q_A^-1",
        pattern_num_points=100,
        cake_radial_points=100,
        cake_azimuth_points=12,
        prefer_dioptrin=True,
        dioptrin_geometry_config={"distance": 0.2},
    )
    engine = PersistentIntegrationEngine()

    engine.compute(task)
    engine.compute(task)

    assert list(engine._dioptrin_backends) == ["q_A^-1", "2th_deg"]
    assert len(created) == 2
    assert [integrator.unit_updates for integrator in created] == [1, 1]


def test_real_dioptrin_engine_is_reused_and_matches_live_path(
    calibrated_config,
):
    dioptrin = pytest.importorskip("dioptrin")
    try:
        dioptrin.validate_license()
    except Exception as exc:
        pytest.skip(f"Dioptrin license unavailable: {exc}")

    config = calibrated_config
    config.auto_integrate_pattern = False
    calibration = config.calibration_model
    calibration.use_dioptrin = True
    calibration._create_dioptrin_integrator()
    if calibration._dioptrin_integrator is None:
        pytest.skip("Dioptrin integrator could not be created")

    task = config.create_integration_task(calculate_pattern=True)
    engine = PersistentIntegrationEngine()

    first = engine.compute(task)
    backend = engine.dioptrin_integrator
    second = engine.compute(task)

    assert backend is not None
    assert engine.dioptrin_integrator is backend
    expected_x, expected_y = calibration.integrate_1d(
        num_points=config.integration_rad_points,
        unit=config.integration_unit,
        trim_zeros=config.trim_trailing_zeros,
    )
    np.testing.assert_allclose(first.pattern.radial, expected_x)
    np.testing.assert_allclose(first.pattern.intensity, expected_y)
    np.testing.assert_allclose(second.pattern.radial, expected_x)
    np.testing.assert_allclose(second.pattern.intensity, expected_y)
