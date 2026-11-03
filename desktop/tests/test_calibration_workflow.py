"""Calibration parity properties: constraints, expert input and edit recovery."""

from pathlib import Path
import importlib.util
import json
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


def test_complete_fit_parameters_confirm_start_values_after_detector_setup():
    session = DesktopSession()
    call(session, "open_image", path=str(DATA / "CeO2_Pilatus1M.tif"))
    result = call(session, "calibration_setup", pixel_x=172, pixel_y=172)
    assert not result["state"]["calibration"]["setupConfirmed"]
    result = call(session, "fit_parameters", parameters={"dist": {"value": 200, "refine": True}})
    assert not result["state"]["calibration"]["setupConfirmed"]
    parameters = result["state"]["calibration"]["parameters"]
    parameters["wavelength"]["value"] = 0.406626
    invalid = {key: dict(entry) for key, entry in parameters.items()}
    invalid["dist"]["value"] = -1
    assert not session.invoke("fit_parameters", {"parameters": invalid})["ok"]
    assert not call(session, "state")["state"]["calibration"]["setupConfirmed"]
    result = call(session, "fit_parameters", parameters=parameters, polarization=0.99)
    assert result["state"]["calibration"]["setupConfirmed"]
    assert result["state"]["calibration"]["wavelength"] == pytest.approx(0.406626)


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


def test_linked_click_retains_azimuth_across_refreshes_and_unit_changes(fitted):
    reference = call(fitted, "validation_position", source="image", x=637.2, y=564.7)["linked"]
    c = fitted.configuration.calibration_model
    expected_azi = np.rad2deg(c.pattern_geometry.chi(np.array([564.]), np.array([637.]))[0])
    assert reference["azimuth"] == pytest.approx(expected_azi)
    assert reference["imagePoint"] == {"x": 637.5, "y": 564.5}
    refreshed = call(fitted, "integrate")["linked"]
    assert refreshed == reference
    changed = call(fitted, "settings", unit="q_A^-1")["linked"]
    assert changed["twoTheta"] == reference["twoTheta"]
    assert changed["radial"] != reference["radial"]
    back = call(fitted, "validation_position", source="cake", x=reference["twoTheta"], azimuth=reference["azimuth"] + 360)["linked"]
    assert back["azimuth"] == pytest.approx(expected_azi)
    assert back["imagePoint"]["x"] == pytest.approx(637.5, abs=1)
    assert back["imagePoint"]["y"] == pytest.approx(564.5, abs=1)
    pattern = call(fitted, "validation_position", source="pattern", x=changed["radial"])["linked"]
    assert pattern["azimuth"] == back["azimuth"]
    assert pattern["imagePoint"] == pytest.approx(back["imagePoint"])
    assert call(fitted, "image_transform", operation="flip_horizontal")["linked"] is None
    # A newly loaded image invalidates the old detector selection.
    assert call(fitted, "example")["linked"] is None


def test_first_pattern_click_has_a_radial_guide_without_inventing_azimuth(fitted):
    linked = call(fitted, "validation_position", source="pattern", x=10)["linked"]
    assert linked["twoTheta"] == pytest.approx(10)
    assert linked["azimuth"] is None
    assert linked["imagePoint"] is None


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


def test_refinement_publishes_detached_live_points_and_fitted_contours(fitted, monkeypatch):
    call(fitted, "workflow_settings", numberOfRings=4)
    publish = fitted._publish_calibration_progress
    previews = []

    def capture(*args, **kwargs):
        publish(*args, **kwargs)
        progress = fitted.invoke("progress")["progress"]
        previews.append((progress, json.dumps(progress)))

    monkeypatch.setattr(fitted, "_publish_calibration_progress", capture)
    result = call(fitted, "calibrate", automatic=True)
    # Live frames are ordinary JSON; later searches and final integration must
    # not mutate data already being serialized by a concurrent progress reader.
    assert all(json.dumps(progress) == saved for progress, saved in previews)
    searches = [p for p, _ in previews if p["label"] == "Finding peaks on ring"]
    assert [p["calibration"]["activeRing"] for p in searches] == [1, 2, 3, 4]
    assert not searches[0]["calibration"]["picks"]
    assert searches[1]["calibration"]["picks"]
    assert all(p["calibration"]["rings"] for p in searches)
    refined = [p for p, _ in previews if p["label"] == "Refining ring"]
    assert len(refined[-1]["calibration"]["picks"]) > len(refined[0]["calibration"]["picks"])
    assert refined[-1]["calibration"]["picks"] == result["state"]["calibration"]["picks"]
    assert refined[-1]["calibration"]["rings"] == result["rings"]
    assert "calibration" not in fitted.invoke("progress")["progress"]


@pytest.mark.parametrize("restart", [False, True])
def test_empty_automatic_search_restores_picked_peaks(fitted, monkeypatch, restart):
    c = fitted.configuration.calibration_model
    points = c.params.peak_selections
    geometry = c.pattern_geometry.get_config()
    monkeypatch.setattr(c, "search_peaks_on_ring", lambda *args: None)
    result = fitted.invoke("calibrate", {"automatic": True, "restart": restart})
    assert not result["ok"] and "restored" in result["error"]
    assert c.params.peak_selections == points
    assert c.pattern_geometry.dist == pytest.approx(geometry["dist"])
    assert c.is_calibrated
    assert "calibration" not in fitted.invoke("progress")["progress"]


@pytest.mark.parametrize("restart", [False, True])
def test_cancellation_is_readable_without_session_lock(fitted, monkeypatch, restart):
    c = fitted.configuration.calibration_model
    points = c.params.peak_selections
    geometry = c.get_pyFAI_config()
    entered = threading.Event()
    release = threading.Event()

    def search(*args):
        entered.set()
        assert release.wait(5)

    monkeypatch.setattr(c, "search_peaks_on_ring", search)
    result = {}
    worker = threading.Thread(
        target=lambda: result.update(fitted.invoke("calibrate", {"automatic": True, "restart": restart}))
    )
    worker.start()
    assert entered.wait(5)
    progress = fitted.invoke("progress")["progress"]
    assert progress["running"]
    assert progress["calibration"]["activeRing"] == 1
    assert progress["calibration"]["rings"]
    assert fitted.invoke("cancel_refinement")["ok"]
    release.set()
    worker.join(5)
    assert not worker.is_alive()
    assert not result["ok"] and "cancelled" in result["error"]
    assert c.params.peak_selections == points
    assert c.is_calibrated
    assert c.get_pyFAI_config() == geometry
    assert "calibration" not in fitted.invoke("progress")["progress"]


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


def test_calibrate_uses_complete_current_fields_without_separate_apply(picked):
    parameters = call(picked, "state")["state"]["calibration"]["parameters"]
    parameters["dist"] = {"value": 208.65, "refine": False}
    parameters["rot1"] = {"value": 0.0, "refine": False}
    # Complete fields must also confirm an as-yet-unconfirmed starting setup.
    picked._setup_confirmed = False
    result = call(picked, "calibrate", automatic=False, parameters=parameters, polarization=0.95)
    assert result["state"]["calibrated"]
    assert result["state"]["calibration"]["setupConfirmed"]
    assert result["state"]["geometry"]["dist"] == pytest.approx(0.20865, abs=1e-12)
    assert result["state"]["geometry"]["rot1"] == pytest.approx(0.0, abs=1e-12)
    assert result["state"]["calibration"]["polarization"] == 0.95


def test_invalid_current_fit_fields_do_not_start_calibration(picked):
    before = call(picked, "state")
    parameters = {key: dict(value) for key, value in before["state"]["calibration"]["parameters"].items()}
    parameters["dist"]["value"] = -1
    result = picked.invoke("calibrate", {"parameters": parameters, "automatic": False})
    assert not result["ok"]
    after = call(picked, "state")
    assert not after["state"]["calibrated"]
    assert after["state"]["calibration"]["parameters"] == before["state"]["calibration"]["parameters"]


def test_recalibration_uses_current_picks_instead_of_previous_geometry(engine_picked):
    session = engine_picked
    call(session, "calibrate", automatic=False)
    call(session, "remove_pick", index=0)
    c = session.configuration.calibration_model
    points = c.get_point_array().copy()
    # A fresh fit from the edited selection is the reference result.
    reference = call(session, "calibrate", automatic=False, restart=True)
    geometry = reference["state"]["geometry"]
    # Start with a different, valid geometry to distinguish restarting from
    # continuing refinement of the previous solution.
    altered = c.get_pyFAI_config()
    altered.update(dist=0.4, poni1=0.02, poni2=0.03, rot1=0.2, rot2=-0.2)
    c.set_pyFAI_config(altered)
    c.is_calibrated = True
    result = call(session, "calibrate", automatic=False, restart=True)
    for key in ("dist", "poni1", "poni2", "rot1", "rot2", "rot3", "wavelength"):
        assert result["state"]["geometry"][key] == pytest.approx(geometry[key], abs=1e-12)
    np.testing.assert_array_equal(c.get_point_array(), points)
    assert not result["state"]["calibration"]["fitDirty"]


def test_refinement_keeps_existing_pyfai_geometry(fitted):
    c = fitted.configuration.calibration_model
    geometry = c.pattern_geometry
    call(fitted, "remove_pick", index=0)
    result = call(fitted, "calibrate", automatic=False)
    assert c.pattern_geometry is geometry
    np.testing.assert_array_equal(geometry.data, c.get_point_array())
    assert not result["state"]["calibration"]["fitDirty"]
