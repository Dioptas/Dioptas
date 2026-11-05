"""Optional integration must never make the core pyFAI route require a key."""

import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import numpy as np
import pytest

import dioptas
from dioptas.model.integration_task import PersistentIntegrationEngine
from dioptas.model.util import release_smoke


class LicenseError(Exception):
    pass


class LicenseNotFoundError(LicenseError):
    pass


class LicenseExpiredError(LicenseError):
    pass


@pytest.mark.parametrize("failure", [None, LicenseNotFoundError,
                                    LicenseExpiredError, LicenseError],
                         ids=["absent", "legacy-no-key", "legacy-expired", "legacy-invalid"])
def test_unavailable_backend_falls_back_to_pyfai(failure, calibrated_config, monkeypatch):
    def unavailable(*args, **kwargs):
        raise failure("Unavailable legacy license")

    backend = None if failure is None else SimpleNamespace(
        validate_license=unavailable,
        LicenseError=LicenseError,
        LicenseNotFoundError=LicenseNotFoundError,
        LicenseExpiredError=LicenseExpiredError,
        Integrator=SimpleNamespace(from_poni_dict=unavailable),
    )
    monkeypatch.setitem(sys.modules, "dioptrin", backend)
    warnings = []
    monkeypatch.setattr(dioptas.QtWidgets.QMessageBox, "warning",
                        lambda *args: warnings.append(args))
    assert dioptas._check_dioptrin_license() is False
    assert bool(warnings) == (failure is LicenseExpiredError)

    config = calibrated_config
    config.auto_integrate_pattern = False
    cal = config.calibration_model
    cal.use_dioptrin = False
    x, y = cal.integrate_1d(num_points=128, trim_zeros=False)
    cal.use_dioptrin = True
    # Even a task already submitted with the preferred backend falls back.
    task = config.create_integration_task(calculate_pattern=True)
    engine = PersistentIntegrationEngine()
    try:
        result = engine.compute(task)
        assert engine.dioptrin_integrator is None
    finally:
        engine.close()
    expected_x, expected_y = cal.integrate_1d(
        num_points=config.integration_rad_points, trim_zeros=config.trim_trailing_zeros)
    np.testing.assert_allclose(result.pattern.radial, expected_x)
    np.testing.assert_allclose(result.pattern.intensity, expected_y)
    cal._create_dioptrin_integrator()
    assert cal.use_dioptrin is False
    fallback_x, fallback_y = cal.integrate_1d(num_points=128, trim_zeros=False)
    np.testing.assert_array_equal(fallback_x, x)
    np.testing.assert_array_equal(fallback_y, y)


def test_standalone_smoke_requires_dioptrin_but_source_does_not(monkeypatch):
    monkeypatch.setitem(sys.modules, "dioptrin", None)
    assert release_smoke.check_dioptrin_runtime() is None
    with pytest.raises(RuntimeError, match="backend is missing"):
        release_smoke.check_dioptrin_runtime(required=True)


def test_release_smoke_rejects_stale_backend(monkeypatch):
    monkeypatch.setitem(sys.modules, "dioptrin", SimpleNamespace())
    monkeypatch.setattr(release_smoke, "version", lambda name: "0.6.1")
    with pytest.raises(RuntimeError, match="Expected Dioptrin 0.7.0, got 0.6.1"):
        release_smoke.check_dioptrin_runtime(required=True)


def test_published_backend_works_without_activation(tmp_path):
    pytest.importorskip("dioptrin")
    # A fresh process cannot inherit a cached license. Its empty home and an
    # invalid legacy environment value must not prevent 0.7 integration/startup.
    env = dict(os.environ, HOME=str(tmp_path), DIOPTRIN_LICENSE="not-a-license",
               QT_QPA_PLATFORM="offscreen")
    code = """
import dioptas
from dioptas.model.util.release_smoke import check_dioptrin_runtime
assert dioptas._check_dioptrin_license()
assert check_dioptrin_runtime(required=True) == '0.7.0'
"""
    result = subprocess.run([sys.executable, "-c", code], env=env,
                            cwd=Path(__file__).parents[3], capture_output=True,
                            text=True, timeout=90)
    assert result.returncode == 0, result.stdout + result.stderr
