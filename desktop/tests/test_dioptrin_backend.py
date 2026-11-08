"""Optional desktop engine selection and measured-image integration checks."""

import importlib.util
from pathlib import Path

import numpy as np
import pytest

from dioptas.desktop import engines
from dioptas.desktop.session import DesktopSession

DATA = Path(__file__).resolve().parents[2] / "dioptas/tests/data"


def call(session, action, **payload):
    result = session.invoke(action, payload)
    assert result["ok"], result.get("error")
    return result


def test_missing_optional_dependency_starts_with_pyfai(monkeypatch):
    find_spec = importlib.util.find_spec
    monkeypatch.setattr(
        engines.importlib.util, "find_spec",
        lambda name: None if name == "dioptrin" else find_spec(name),
    )
    session = DesktopSession()
    result = call(session, "example")
    assert result["state"]["calibration"]["engine"] == "pyfai"
    assert not session.configuration.calibration_model.use_dioptrin


def test_broken_optional_engine_falls_back_and_explicit_selection_preserves_session(monkeypatch):
    monkeypatch.setattr(engines.importlib.util, "find_spec", lambda name: object())

    def broken():
        raise ValueError("Incompatible native API")

    monkeypatch.setattr(engines, "DioptrinEngine", broken)
    session = DesktopSession()
    assert session._engine.id == "pyfai"
    result = session.invoke("calibration_engine", {"engine": "dioptrin"})
    assert not result["ok"] and "Incompatible native API" in result["error"]
    assert session._engine.id == "pyfai"
    assert not session.configuration.calibration_model.use_dioptrin


@pytest.fixture
def native():
    pytest.importorskip("dioptrin")
    session = DesktopSession()
    assert session._engine.id == "dioptrin"
    call(session, "example")
    call(session, "integration_settings", bins=300, cake_bins=40, trim_zeros=False)
    call(session, "open_calibration", path=str(DATA / "CeO2_Pilatus1M.poni"))
    assert session.configuration.calibration_model._dioptrin_integrator is not None
    return session


@pytest.mark.parametrize("unit", ["2th_deg", "q_A^-1", "q_nm^-1"])
def test_full_split_agreement_with_pyfai_across_mask_edits(native, unit):
    """Compare matching full-split methods; pyFAI's default csr uses bbox.

    These fixture bounds (0.3% pattern, 0.6% Poisson std, 0.5% cake in
    relative L2) are regression limits, not universal detector accuracy.
    """
    c = native.configuration.calibration_model
    for x in (None, 500, 650):
        if x is not None:
            call(native, "mask_stroke", points=[[x, 400]], radius=20)
        mask = native.configuration.mask_model.get_mask() if x is not None else None
        c.use_dioptrin = True
        c.integrate_1d(300, mask=mask, unit=unit, trim_zeros=False, calculate_errors=True)
        radial, intensity, errors = c.tth.copy(), c.int.copy(), c.sigma.copy()
        c.integrate_2d(mask=mask, rad_points=300, azimuth_points=40)
        cake = c.cake_img.copy()
        native_integrator = c._dioptrin_integrator
        c.use_dioptrin = False
        c.integrate_1d(300, mask=mask, unit=unit, method="full_csr", trim_zeros=False, calculate_errors=True)
        c.integrate_2d(mask=mask, rad_points=300, azimuth_points=40, method="full_csr")
        np.testing.assert_allclose(radial, c.tth, rtol=3e-7, atol=1e-7)
        for actual, reference, limit in (
            (intensity, c.int, 0.003), (errors, c.sigma, 0.006), (cake, c.cake_img, 0.005),
        ):
            assert np.linalg.norm(actual - reference) / np.linalg.norm(reference) < limit
        assert c._dioptrin_integrator is native_integrator


def test_supported_integration_uses_native_and_unsupported_options_use_pyfai(native, monkeypatch):
    c = native.configuration.calibration_model

    def forbidden(*args, **kwargs):
        raise AssertionError("Unexpected pyFAI integration")

    with monkeypatch.context() as patch:
        patch.setattr(c.pattern_geometry, "integrate1d", forbidden)
        patch.setattr(c.cake_geometry, "integrate2d", forbidden)
        c.integrate_1d(300)
        c.integrate_2d(rad_points=300, azimuth_points=40)
    reference = c.pattern_geometry.integrate1d
    calls = []

    def pyfai(*args, **kwargs):
        calls.append(kwargs)
        return reference(*args, **kwargs)

    monkeypatch.setattr(c.pattern_geometry, "integrate1d", pyfai)
    c.integrate_1d(300, azi_range=(-45, 45))
    c.correct_solid_angle = False
    c.integrate_1d(300)
    assert len(calls) == 2
    assert calls[0]["azimuth_range"] == (-45, 45)
    assert calls[1]["correctSolidAngle"] is False


@pytest.mark.parametrize("unsupported", ["spline", "curved", "nonuniform"])
def test_unsupported_detector_clears_flat_native_adapter(native, monkeypatch, unsupported):
    c = native.configuration.calibration_model
    if unsupported == "spline":
        # Bypass the model's file reader: this checks adapter admission only.
        c.params.__dict__["distortion_spline_filename"] = "distorted.spline"
    else:
        monkeypatch.setattr(c.detector, "IS_FLAT" if unsupported == "curved" else "uniform_pixel", False)
    c._create_dioptrin_integrator()
    assert c._dioptrin_integrator is None
    assert not c.can_use_dioptrin_batch("2th_deg")
