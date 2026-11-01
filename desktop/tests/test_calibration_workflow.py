"""Calibration parity properties: constraints, expert input and edit recovery."""

from pathlib import Path
import importlib.util
import threading

import numpy as np
import pytest

from dioptas.desktop.session import DesktopSession
from dioptas.pipeline import Pipeline

DATA = Path(__file__).resolve().parents[2] / "dioptas/tests/data"
SEEDS = [
    (637, 564, 1),
    (671, 511, 2),
    (668, 703, 3),
    (350.5, 592.8, 1),
    (554.3, 367.9, 1),
]


def call(session, action, **payload):
    result = session.invoke(action, payload)
    assert result["ok"], result.get("error")
    return result


@pytest.fixture
def session():
    s = DesktopSession()
    call(s, "example")
    return s


@pytest.fixture
def picked(session):
    for x, y, ring in SEEDS:
        call(session, "pick_peak", x=x, y=y, ring=ring)
    return session


@pytest.fixture
def fitted(picked):
    call(picked, "calibrate", automatic=False)
    return picked


@pytest.fixture(params=["pyfai", "dioptrin"])
def engine_picked(session, request):
    if request.param == "dioptrin" and importlib.util.find_spec("dioptrin") is None:
        pytest.skip("Optional Dioptrin engine not installed")
    call(session, "calibration_engine", engine=request.param)
    for x, y, ring in SEEDS:
        call(session, "pick_peak", x=x, y=y, ring=ring)
    return session


def test_distance_and_tilt_constraints_are_honored(engine_picked):
    picked = engine_picked
    call(
        picked,
        "fit_parameters",
        parameters={
            "dist": {"value": 208.65, "refine": False},
            "rot1": {"value": 0.0, "refine": False},
        },
        polarization=0.95,
    )
    result = call(picked, "calibrate", automatic=False)
    assert result["state"]["geometry"]["dist"] == pytest.approx(0.20865, abs=1e-12)
    assert result["state"]["geometry"]["rot1"] == pytest.approx(0.0, abs=1e-12)
    assert result["state"]["calibration"]["polarization"] == 0.95
    assert not result["state"]["calibration"]["parameters"]["dist"]["refine"]


def test_wavelength_can_be_refined_with_distance_fixed(engine_picked):
    picked = engine_picked
    call(
        picked,
        "fit_parameters",
        parameters={
            "dist": {"value": 208.65, "refine": False},
            "wavelength": {"value": 0.405, "refine": True},
        },
    )
    result = call(picked, "calibrate", automatic=False)
    assert result["state"]["calibration"]["fitWavelength"]
    assert result["state"]["geometry"]["dist"] == pytest.approx(0.20865, abs=1e-12)
    assert 0.39 < result["state"]["geometry"]["wavelength"] * 1e10 < 0.42


def test_peak_reassignment_and_multidelete_have_undo(session):
    call(session, "pick_peak", x=637, y=564, ring=1)
    call(session, "pick_peak", x=671, y=511, ring=2)
    before = session.configuration.calibration_model.params.peak_selections
    changed = call(session, "reassign_pick", index=0, ring=3)
    assert changed["state"]["calibration"]["picks"][0]["ring"] == 3
    call(session, "undo_calibration")
    assert session.configuration.calibration_model.params.peak_selections == before
    call(session, "redo_calibration")
    assert session.configuration.calibration_model.points_index[0] == 2
    call(session, "remove_picks", indices=[0, 1])
    assert not session.configuration.calibration_model.points
    result = call(session, "undo_calibration")
    assert len(result["state"]["calibration"]["picks"]) == 2
    assert result["state"]["calibration"]["canRedo"]


def test_orientation_round_trip_preserves_pixels_and_clears_stale_peaks(session):
    original = session.configuration.img_model.img_data.copy()
    call(session, "pick_peak", x=637, y=564, ring=1, automatic=False)
    result = call(session, "image_transform", operation="rotate_right")
    assert result["state"]["shape"] == [original.shape[1], original.shape[0]]
    assert not result["state"]["calibration"]["picks"]
    call(session, "image_transform", operation="rotate_left")
    np.testing.assert_array_equal(session.configuration.img_model.img_data, original)
    call(session, "image_transform", operation="flip_horizontal")
    call(session, "image_transform", operation="reset")
    np.testing.assert_array_equal(session.configuration.img_model.img_data, original)


def reference_geometry(session):
    p = Pipeline()
    p.load_calibration(str(DATA / "CeO2_Pilatus1M.poni"))
    c = p.calibration_model
    return c.get_calibration_parameter()


def test_manual_pyfai_geometry_needs_no_peaks_and_saves(session, tmp_path):
    values, _ = reference_geometry(session)
    values = {
        k: values[k]
        for k in [
            "dist",
            "poni1",
            "poni2",
            "rot1",
            "rot2",
            "rot3",
            "pixel1",
            "pixel2",
            "wavelength",
            "polarization_factor",
        ]
    }
    result = call(session, "manual_geometry", convention="pyfai", values=values)
    assert result["state"]["calibrated"] and not result["state"]["calibration"]["picks"]
    assert result["state"]["calibration"]["geometrySource"] == "manual"
    output = tmp_path / "manual.poni"
    call(session, "save_calibration", path=str(output))
    p = Pipeline()
    p.load_calibration(str(output))
    assert p.calibration_model.pattern_geometry.dist == pytest.approx(values["dist"])


def test_manual_fit2d_keeps_nonsquare_pixel_axes(session):
    _, values = reference_geometry(session)
    values = {
        k: values[k]
        for k in [
            "directDist",
            "centerX",
            "centerY",
            "tilt",
            "tiltPlanRotation",
            "pixelX",
            "pixelY",
            "wavelength",
            "polarization_factor",
        ]
    }
    values.update(pixelX=100.0, pixelY=150.0)
    result = call(session, "manual_geometry", convention="fit2d", values=values)
    assert result["state"]["calibration"]["pixelX"] == pytest.approx(100.0)
    assert result["state"]["calibration"]["pixelY"] == pytest.approx(150.0)


def test_linked_validation_uses_current_pattern_units(fitted):
    call(fitted, "settings", unit="q_A^-1")
    reference = call(fitted, "validation_position", source="image", x=637, y=564)[
        "linked"
    ]
    q = reference["radial"]
    expected = (
        4
        * np.pi
        * np.sin(np.deg2rad(reference["twoTheta"]) / 2)
        / (fitted.configuration.calibration_model.pattern_geometry.wavelength * 1e10)
    )
    assert q == pytest.approx(expected)
    assert reference["contours"]
    back = call(fitted, "validation_position", source="pattern", x=q)["linked"]
    assert back["twoTheta"] == pytest.approx(reference["twoTheta"])


def test_detector_and_distortion_file_controls(session):
    result = call(session, "detector_file", path=str(DATA / "detector.h5"))
    assert result["state"]["calibration"]["detectorFile"]
    call(session, "detector_file", reset=True)
    result = call(
        session, "distortion_file", path=str(DATA / "distortion/f4mnew.spline")
    )
    assert result["state"]["calibration"]["distortionFile"].endswith(".spline")
    result = call(session, "distortion_file", reset=True)
    assert result["state"]["calibration"]["distortionFile"] is None


def test_mask_load_rejects_wrong_dimensions(session, tmp_path):
    path = tmp_path / "wrong.npy"
    np.save(path, np.zeros((7, 8)))
    shape = session.configuration.img_model.img_data.shape
    assert not session.invoke("mask_file", {"path": str(path)})["ok"]
    assert session.configuration.mask_model.get_img().shape == shape


def test_automatic_refinement_finds_real_rings(fitted):
    call(fitted, "workflow_settings", numberOfRings=4)
    result = call(fitted, "calibrate", automatic=True)
    assert len(set(p["ring"] for p in result["state"]["calibration"]["picks"])) >= 3
    assert result["state"]["calibration"]["rmsDegrees"] < 0.05
    assert not fitted.invoke("progress")["progress"]["running"]


def test_empty_automatic_search_restores_picked_peaks(fitted, monkeypatch):
    c = fitted.configuration.calibration_model
    points = c.params.peak_selections
    geometry = c.pattern_geometry.get_config()
    monkeypatch.setattr(c, "search_peaks_on_ring", lambda *args: None)
    result = fitted.invoke("calibrate", {"automatic": True})
    assert not result["ok"] and "restored" in result["error"]
    assert c.params.peak_selections == points
    assert c.pattern_geometry.dist == pytest.approx(geometry["dist"])


def test_cancellation_is_readable_without_session_lock(fitted, monkeypatch):
    c = fitted.configuration.calibration_model
    points = c.params.peak_selections
    entered = threading.Event()
    release = threading.Event()

    def search(*args):
        entered.set()
        assert release.wait(5)

    monkeypatch.setattr(c, "search_peaks_on_ring", search)
    result = {}
    worker = threading.Thread(
        target=lambda: result.update(fitted.invoke("calibrate", {"automatic": True}))
    )
    worker.start()
    assert entered.wait(5)
    assert fitted.invoke("progress")["progress"]["running"]
    assert fitted.invoke("cancel_refinement")["ok"]
    release.set()
    worker.join(5)
    assert not worker.is_alive()
    assert not result["ok"] and "cancelled" in result["error"]
    assert c.params.peak_selections == points


def test_custom_calibrant_is_owned_and_survives_project_reopen(session, tmp_path):
    source = tmp_path / "user-reference.D"
    source.write_text((DATA.parents[1] / "resources/calibrants/CeO2.D").read_text())
    result = call(session, "open_calibrant", path=str(source))
    assert result["state"]["calibration"]["calibrant"] == "user-reference (custom)"
    project = tmp_path / "custom.dio"
    call(session, "save_project", path=str(project))
    source.unlink()
    restored = DesktopSession()
    result = call(restored, "open_project", path=str(project))
    assert result["state"]["calibration"]["calibrant"] == "user-reference (custom)"
    assert restored._calibrant_path().is_file()
    assert (
        restored.configuration.calibration_model.calibrant.dSpacing
        == session.configuration.calibration_model.calibrant.dSpacing
    )


def test_image_stepping_uses_existing_file_iterator(tmp_path):
    from PIL import Image

    for number in (1, 2):
        Image.fromarray(np.full((30, 40), number, dtype=np.uint16)).save(
            tmp_path / f"scan_{number:03d}.tif"
        )
    session = DesktopSession()
    call(session, "open_image", path=str(tmp_path / "scan_001.tif"))
    assert np.all(session.configuration.img_model.img_data == 1)
    call(session, "next_image", direction=1)
    assert np.all(session.configuration.img_model.img_data == 2)
    call(session, "next_image", direction=-1)
    assert np.all(session.configuration.img_model.img_data == 1)


def test_validation_reference_preserves_loaded_geometry_and_uses_its_wavelength(session, tmp_path):
    call(session, "open_calibration", path=str(DATA / "CeO2_Pilatus1M.poni"))
    c = session.configuration.calibration_model
    geometry = c.get_pyFAI_config()
    c.start_values["wavelength"] = 0.5e-10
    result = call(session, "validation_calibrant", calibrant="LaB6")
    assert c.get_pyFAI_config() == geometry
    assert c.calibrant.wavelength == pytest.approx(geometry["wavelength"])
    assert not result["state"]["calibration"]["fitDirty"]
    assert result["state"]["calibration"]["calibrant"] == "LaB6"
    call(session, "save_calibration", path=str(tmp_path / "unchanged.poni"))
