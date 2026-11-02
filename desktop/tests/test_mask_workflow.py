"""Source-pixel and real-model parity for the desktop Mask mode."""

from pathlib import Path
from unittest.mock import Mock

import numpy as np
import pytest

from dioptas.desktop.session import DesktopSession
from dioptas.model.MaskModel import MaskModel
from dioptas.model.util.calc import convert_units
from dioptas.model.util.point import Point

ROOT = Path(__file__).resolve().parents[2]


def call(session, command, **args):
    result = session.invoke(command, args)
    assert result["ok"], result.get("error")
    return result


@pytest.fixture
def session():
    s = DesktopSession()
    call(s, "example")
    return s


def pixels(s):
    return s.configuration.mask_model.get_img().copy()


def test_mask_mode_defers_pattern_and_cake_until_requested(session, monkeypatch, tmp_path):
    s = session
    call(s, "open_calibration", path=str(s.example_paths()[1]))
    baseline = np.array(s._pattern["y"], dtype=float)
    pattern = Mock(wraps=s._integration_calculate_pattern)
    cake = Mock(wraps=s._integration_calculate_cake)
    monkeypatch.setattr(s, "_integration_calculate_pattern", pattern)
    monkeypatch.setattr(s, "_integration_calculate_cake", cake)

    def edit(command, **args):
        result = call(s, command, defer_integration=True, **args)
        assert result["state"]["integrationDirty"]
        assert result["pattern"] is None and result["cake"] is None
        assert result["state"]["elapsedMs"] is None
        pattern.assert_not_called()
        cake.assert_not_called()
        return result

    edit("mask_edit", operation="rectangle", points=[[11, 21], [41, 61]])
    edit("mask_stroke", points=[[100, 100], [110, 110]], radius=5)
    edit("undo_mask")
    edit("redo_mask")
    edit(
        "mask_plugin",
        name="Threshold Mask",
        settings={"above_value": 1000},
        enabled=True,
    )
    edit("mask_plugin", name="Threshold Mask", imprint=True)
    path = str(tmp_path / "deferred.mask")
    call(s, "mask_file", path=path, save=True, defer_integration=True)
    edit("clear_mask")
    edit("mask_file", path=path)
    edit("settings", use_mask=False)
    result = edit("settings", use_mask=True)
    assert result["state"]["maskedPixels"] > 0

    result = call(s, "integrate")
    assert not result["state"]["integrationDirty"]
    assert result["pattern"] is not None and result["cake"] is not None
    assert not np.allclose(result["pattern"]["y"], baseline, equal_nan=True)
    pattern.assert_called_once()
    cake.assert_called_once()
    # Deferral is request-scoped: normal calibration/integration settings keep
    # their immediate calculation, using the same underlying scientific model.
    result = call(s, "settings", use_mask=False)
    np.testing.assert_allclose(result["pattern"]["y"], baseline, equal_nan=True)


@pytest.mark.parametrize("dirty", [False, True])
def test_transparency_preserves_integration_and_pixels(session, monkeypatch, dirty):
    s = session
    call(s, "open_calibration", path=str(s.example_paths()[1]))
    if dirty:
        call(
            s, "mask_edit", operation="rectangle", points=[[11, 21], [41, 61]],
            defer_integration=True,
        )
    pattern, cake, rings = s._pattern, s._cake, s._rings
    elapsed = s._elapsed
    revision = s._revision
    calculate = Mock(wraps=s._calculate)
    raster = Mock(wraps=s._raster)
    monkeypatch.setattr(s, "_calculate", calculate)
    monkeypatch.setattr(s, "_raster", raster)
    for transparent in (False, True):
        result = call(s, "settings", transparent_mask=transparent, defer_integration=dirty)
        assert result["state"]["transparentMask"] is transparent
        assert result["state"]["integrationDirty"] is dirty
        assert s._pattern is pattern and s._cake is cake and s._rings is rings
        assert s._elapsed == elapsed
        assert not {"image", "mask", "pattern", "cake", "rings"} & result.keys()
        calculate.assert_not_called()
        raster.assert_not_called()
    assert s._revision == revision + 2


def test_geometry_and_unmask_are_model_equivalent(session):
    s = session
    expected = MaskModel(s.configuration.img_model.img_data.shape)
    call(s, "mask_edit", operation="rectangle", points=[[11, 21], [41, 61]])
    expected.mask_rect(21, 11, 40, 30)
    np.testing.assert_array_equal(pixels(s), expected.get_img())
    call(s, "mask_edit", operation="circle", points=[[50, 70], [100, 110]])
    expected.mask_ellipse(75, 90, 25, 20)
    call(
        s,
        "mask_edit",
        operation="polygon",
        points=[[12, 22], [40, 22], [25, 50]],
        erase=True,
    )
    expected.mode = False
    expected.mask_polygon(np.array([12, 40, 25]), np.array([22, 22, 50]))
    np.testing.assert_array_equal(pixels(s), expected.get_img())
    after = pixels(s)
    call(s, "undo_mask")
    assert not np.array_equal(pixels(s), after)
    call(s, "redo_mask")
    np.testing.assert_array_equal(pixels(s), after)


def test_arc_matches_qt_model_construction_and_degenerate_is_atomic(session):
    s = session
    vertices = [[100, 100], [120, 120], [140, 100], [120, 127]]
    call(s, "mask_edit", operation="arc", points=vertices)
    expected = MaskModel(pixels(s).shape)
    a, b, c, edge = [Point(*p) for p in vertices]
    center = expected.find_center_of_circle_from_three_points(a, b, c)
    r = expected.find_radius_of_circle_from_center_and_point(center, a)
    angles = expected.find_n_angles_on_arc_from_three_points_around_p0(
        center, a, b, c, 50
    )
    width = abs(r - expected.find_radius_of_circle_from_center_and_point(center, edge))
    polygon = expected.calc_arc_points_from_angles(center, r, -width, angles) + list(
        reversed(expected.calc_arc_points_from_angles(center, r, width, angles))
    )
    expected.mask_polygon(
        np.array([p.x() for p in polygon]), np.array([p.y() for p in polygon])
    )
    np.testing.assert_array_equal(pixels(s), expected.get_img())
    before = pixels(s)
    assert not s.invoke(
        "mask_edit",
        {"operation": "arc", "points": [[10, 10], [20, 20], [30, 30], [40, 40]]},
    )["ok"]
    np.testing.assert_array_equal(pixels(s), before)


@pytest.mark.parametrize("operation", ["grow", "shrink", "invert", "clear"])
def test_actions_match_mask_model(session, operation):
    s = session
    call(s, "mask_edit", operation="rectangle", points=[[50, 60], [80, 90]])
    expected = MaskModel(pixels(s).shape)
    expected.set_mask_data(pixels(s))
    getattr(
        expected,
        {"invert": "invert_mask", "clear": "clear_mask"}.get(operation, operation),
    )()
    call(s, "mask_edit", operation=operation)
    np.testing.assert_array_equal(pixels(s), expected.get_img())


@pytest.mark.parametrize(
    "extension,flip", [("mask", False), ("npy", True), ("edf", True), ("tif", False)]
)
def test_file_roundtrip_merge_history_and_project(session, tmp_path, extension, flip):
    s = session
    call(s, "mask_edit", operation="rectangle", points=[[11, 21], [41, 61]])
    expected = pixels(s)
    path = str(tmp_path / f"test.{extension}")
    call(s, "mask_file", path=path, save=True, flipud=flip)
    if extension == "npy":
        np.testing.assert_array_equal(np.load(path), np.flipud(expected))
    call(s, "clear_mask")
    call(s, "mask_file", path=path, flipud=flip)
    np.testing.assert_array_equal(pixels(s), expected)
    call(s, "mask_edit", operation="rectangle", points=[[101, 121], [141, 161]])
    merged = pixels(s)
    call(s, "mask_file", path=path, add=True, flipud=flip)
    np.testing.assert_array_equal(pixels(s), merged)
    call(s, "mask_file", path=path, flipud=flip)
    call(s, "undo_mask")
    np.testing.assert_array_equal(pixels(s), merged)
    project = str(tmp_path / "mask.dio")
    call(s, "save_project", path=project)
    call(s, "clear_mask")
    call(s, "open_project", path=project)
    np.testing.assert_array_equal(pixels(s), merged)


def test_invalid_load_does_not_destroy_mask_or_redo(session, tmp_path):
    s = session
    call(s, "mask_edit", operation="rectangle", points=[[11, 21], [41, 61]])
    call(s, "undo_mask")
    np.save(tmp_path / "wrong.npy", np.zeros((2, 3)))
    assert not s.invoke("mask_file", {"path": str(tmp_path / "wrong.npy")})["ok"]
    assert call(s, "state")["state"]["canRedoMask"]
    call(s, "redo_mask")
    assert pixels(s).sum() == 1200


@pytest.mark.parametrize(
    "operation", ["flip_horizontal", "flip_vertical", "rotate_left", "rotate_right"]
)
def test_mask_follows_source_image_transform_and_reset(session, operation):
    from dioptas.model.ImgModel import TRANSFORMATION_FUNCTIONS

    s = session
    call(s, "mask_edit", operation="rectangle", points=[[11, 21], [41, 61]])
    original = pixels(s)
    names = {
        "flip_horizontal": "fliplr",
        "flip_vertical": "flipud",
        "rotate_left": "rotate_matrix_m90",
        "rotate_right": "rotate_matrix_p90",
    }
    result = call(s, "image_transform", operation=operation)
    np.testing.assert_array_equal(
        pixels(s), TRANSFORMATION_FUNCTIONS[names[operation]](original)
    )
    # Edits after a transform address the displayed source array, not pre-transform coordinates.
    call(s, "mask_edit", operation="rectangle", points=[[2, 3], [5, 7]])
    assert pixels(s)[3:7, 2:5].all()
    call(s, "undo_mask")
    call(s, "image_transform", operation="reset")
    np.testing.assert_array_equal(pixels(s), original)


def test_radial_thresholds_and_mask_effect_on_real_integration(session):
    s = session
    poni = s.example_paths()[1]
    call(s, "open_calibration", path=str(poni))
    image = s.configuration.img_model.img_data
    call(s, "mask_edit", operation="above", threshold=1000)
    np.testing.assert_array_equal(pixels(s), image > 1000)
    call(s, "mask_edit", operation="below", threshold=0)
    np.testing.assert_array_equal(pixels(s), (image > 1000) | (image < 0))
    call(s, "clear_mask")
    calibration = s.configuration.calibration_model
    tth = np.rad2deg(calibration.get_pixel_two_theta_array())
    for unit, low, high in [
        ("2th_deg", 5.0, 8.0),
        ("q_A^-1", 2.0, 3.0),
        ("d_A", 2.0, 3.0),
    ]:
        radial = convert_units(tth, calibration.wavelength, "2th_deg", unit)
        result = call(
            s, "mask_edit", operation="range", unit=unit, lower=low, upper=high
        )
        np.testing.assert_array_equal(pixels(s), (radial >= low) & (radial <= high))
        call(s, "clear_mask")
    call(s, "settings", use_mask=False)
    baseline = np.array(s._pattern["y"], dtype=float)
    call(s, "mask_edit", operation="above", threshold=1000)
    masked = np.array(s._pattern["y"], dtype=float)
    assert not np.allclose(masked, baseline, equal_nan=True)
    assert s.configuration.use_mask
    call(s, "settings", use_mask=False)
    np.testing.assert_allclose(s._pattern["y"], baseline, equal_nan=True)


def test_plugin_settings_imprint_undo_and_project(session, tmp_path):
    s = session
    name = "Threshold Mask"
    call(s, "mask_plugin", name=name, settings={"above_value": 1000}, enabled=True)
    expected = s.configuration.img_model.img_data > 1000
    np.testing.assert_array_equal(s.configuration.mask_model.get_mask(), expected)
    assert not pixels(s).any()
    call(s, "mask_plugin", name=name, imprint=True)
    np.testing.assert_array_equal(pixels(s), expected)
    assert not s.configuration.mask_plugin_manager.is_enabled(name)
    call(s, "undo_mask")
    assert s.configuration.mask_plugin_manager.is_enabled(name)
    assert not pixels(s).any()
    call(s, "redo_mask")
    np.testing.assert_array_equal(pixels(s), expected)
    call(s, "mask_plugin", name=name, enabled=True)
    call(s, "mask_plugin", name=name, enabled=False)
    call(s, "mask_plugin", name=name, enabled=True)
    project = str(tmp_path / "plugins.dio")
    call(s, "save_project", path=project)
    call(s, "open_project", path=project)
    assert s.configuration.mask_plugin_manager.is_enabled(name)
    assert s.configuration.mask_plugin_manager.get_plugin(name).above_value == 1000


def test_plugin_failure_and_cancellation_are_atomic(session, monkeypatch):
    s = session
    manager = s.configuration.mask_plugin_manager
    plugin = manager.get_plugin("Threshold Mask")

    def cancelled(*args, **kwargs):
        assert s.invoke("progress")["progress"]["running"]
        s.invoke("cancel_refinement")
        return np.ones(pixels(s).shape, dtype=bool)

    monkeypatch.setattr(plugin, "compute_mask", cancelled)
    result = s.invoke(
        "mask_plugin",
        {"name": "Threshold Mask", "enabled": True, "settings": {"above_value": 2}},
    )
    assert not result["ok"] and "cancelled" in result["error"]
    assert not manager.is_enabled("Threshold Mask")
    assert plugin.above_value == 1e7
    assert not pixels(s).any()
    assert not s.invoke("progress")["progress"]["running"]


def test_cosmic_uses_original_algorithm_and_cancel_between_passes(session, monkeypatch):
    from dioptas.model.util.cosmics import cosmicsimage

    # A small real numerical image keeps the LA Cosmic regression inexpensive.
    image = np.full((32, 40), 100.0, dtype=float)
    image[15, 19] = 1e5
    s = session
    s.configuration.img_model._img_data = image.copy()
    s.configuration.img_model._img_data_corrections = None
    monkeypatch.setattr(
        type(s.configuration.img_model), "img_data", property(lambda _: image)
    )
    s.configuration.mask_model.set_dimension(image.shape)
    expected = MaskModel(image.shape)
    expected.remove_cosmic(image)
    call(s, "mask_edit", operation="cosmic")
    np.testing.assert_array_equal(pixels(s), expected.get_img())
    assert pixels(s)[15, 19]
    before = pixels(s)
    original = cosmicsimage.lacosmiciteration

    def cancel(self, *args, **kwargs):
        original(self, *args, **kwargs)
        s.invoke("cancel_refinement")

    monkeypatch.setattr(cosmicsimage, "lacosmiciteration", cancel)
    result = s.invoke("mask_edit", {"operation": "cosmic"})
    assert not result["ok"] and "cancelled" in result["error"]
    np.testing.assert_array_equal(pixels(s), before)


def test_mask_history_preserves_unchanged_fit_diagnostics_and_viewport(session):
    s = session
    from desktop.tests.test_session import SEEDS

    for x, y, ring in SEEDS:
        call(s, "pick_peak", x=x, y=y, ring=ring)
    call(s, "calibrate", automatic=False)
    before = s._fit_rms
    assert not s._fit_dirty
    call(s, "mask_edit", operation="rectangle", points=[[11, 21], [41, 61]])
    result = call(s, "undo_mask")
    assert "image" not in result
    assert not result["state"]["calibration"]["fitDirty"]
    assert result["state"]["calibration"]["rmsDegrees"] == before
    call(s, "redo_mask")
    assert not s._fit_dirty
