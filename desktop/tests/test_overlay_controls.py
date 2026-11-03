"""Qt OverlayController parity through the desktop worker's public commands."""

from pathlib import Path

import numpy as np
import pytest

from dioptas.desktop.session import DesktopSession

DATA = Path(__file__).resolve().parents[2] / "dioptas/tests/data"


def call(session, operation, **payload):
    result = session.invoke("integration_overlay", {"operation": operation, **payload})
    assert result["ok"], result.get("error")
    return result


@pytest.fixture
def session():
    s = DesktopSession()
    x = np.linspace(1, 10, 80)
    s.configuration.pattern_model.set_pattern(x, x * x + 10, "Measured pattern")
    s._refresh_integration_pattern()
    return s


def test_selection_identity_reorder_and_waterfall_persistence(session, tmp_path):
    first = call(session, "capture")["state"]["integration"]["overlays"][0]["uid"]
    call(session, "update", index=0, name="First", color="#24ab56", scale=1.5)
    call(session, "capture")
    call(session, "update", index=1, name="Second")
    result = call(session, "move", index=0, direction=1)
    assert [o["name"] for o in result["state"]["integration"]["overlays"]] == [
        "Second",
        "First",
    ]
    assert result["state"]["integration"]["overlays"][1]["uid"] == first
    call(session, "waterfall_separation", separation=50)
    result = call(session, "waterfall")
    assert [o["offset"] for o in result["state"]["integration"]["overlays"]] == [
        -100,
        -50,
    ]
    assert result["pattern"]["curves"][1]["color"] == "#24ab56"
    project = tmp_path / "overlay.dio"
    assert session.invoke("save_project", {"path": str(project)})["ok"]
    restored = DesktopSession()
    result = restored.invoke("open_project", {"path": str(project)})
    assert result["ok"], result
    assert result["state"]["integration"]["waterfallSeparation"] == 50
    assert [o["offset"] for o in result["state"]["integration"]["overlays"]] == [
        -100,
        -50,
    ]
    assert (
        call(session, "reset_offsets")["state"]["integration"]["overlays"][0]["offset"]
        == 0
    )
    assert not call(session, "visibility", visible=False)["pattern"]["curves"]
    assert len(call(session, "visibility", visible=True)["pattern"]["curves"]) == 2


def test_background_toggle_switch_reorder_remove_and_roundtrip(session, tmp_path):
    original = session.configuration.pattern_model.pattern.data[1].copy()
    call(session, "capture")
    call(session, "capture")
    result = call(session, "background", index=0)
    assert result["state"]["integration"]["overlays"][0]["background"]
    assert not result["state"]["integration"]["overlays"][0]["visible"]
    np.testing.assert_allclose(result["pattern"]["y"], 0, atol=1e-10)
    result = call(session, "background", index=1)
    assert result["state"]["integration"]["overlays"][0]["visible"]
    call(session, "move", index=1, direction=-1)
    assert (
        session.configuration.pattern_model.background_pattern
        is session._model.overlay_model.overlays[0]
    )
    call(session, "update", index=0, scale=0.5, offset=2)
    np.testing.assert_allclose(
        session.configuration.pattern_model.pattern.data[1], original * 0.5 - 2
    )
    project = tmp_path / "background.dio"
    assert session.invoke("save_project", {"path": str(project)})["ok"]
    restored = DesktopSession()
    result = restored.invoke("open_project", {"path": str(project)})
    assert result["ok"], result
    assert result["state"]["integration"]["overlays"][0]["background"]
    assert (
        restored.configuration.pattern_model.background_pattern
        is restored._model.overlay_model.overlays[0]
    )
    call(session, "background", index=0)
    assert session.configuration.pattern_model.background_pattern is None
    assert session._model.overlay_model.overlays[0].visible
    np.testing.assert_allclose(
        session.configuration.pattern_model.pattern.data[1], original
    )
    call(session, "background", index=0)
    call(session, "remove", index=0)
    assert session.configuration.pattern_model.background_pattern is None
    assert session.configuration.pattern_model.params.background_overlay_uid == ""
    call(session, "background", index=0)
    call(session, "clear")
    assert session.configuration.pattern_model.background_pattern is None


def test_match_intensity_equals_original_qt_controller(session):
    from dioptas.controller.integration.overlay.OverlayController import (
        OverlayController,
    )

    call(session, "capture")
    overlay = session._model.overlay_model.overlays[0]
    overlay._original_y *= 0.25
    call(session, "update", index=0, scale=2, offset=500)
    result = call(session, "match_intensity", index=0)
    actual = result["state"]["integration"]["overlays"][0]
    call(session, "update", index=0, scale=2, offset=500)
    qt = OverlayController.__new__(OverlayController)
    qt.model = session._model
    qt.match_intensity(0)
    assert overlay.scaling == pytest.approx(actual["scale"])
    assert overlay.offset == actual["offset"] == 0
    assert actual["scale"] == pytest.approx(4)


@pytest.mark.parametrize(
    "y,x", [(np.zeros(5), np.arange(5)), (np.ones(5), np.arange(100, 105))]
)
def test_match_intensity_no_overlap_or_zero_signal_keeps_edits(session, y, x):
    session._model.overlay_model.add_overlay(x, y)
    call(session, "update", index=0, scale=3, offset=17)
    result = call(session, "match_intensity", index=0)["state"]["integration"][
        "overlays"
    ][0]
    assert result["scale"] == 3 and result["offset"] == 17


def test_multifile_loading_cancel_and_rename(session, tmp_path):
    paths = []
    for i in range(2):
        path = tmp_path / f"overlay-{i}.xy"
        np.savetxt(path, np.column_stack([np.arange(10), np.arange(10) * (i + 1)]))
        paths.append(str(path))
    session._choose_file = lambda kind, save: paths if kind == "overlays" else None
    assert len(call(session, "load")["state"]["integration"]["overlays"]) == 2
    assert len(call(session, "load", paths=paths)["pattern"]["curves"]) == 4
    call(session, "update", index=0, name="Reference one")
    assert session._model.overlay_model.overlays[0].name == "Reference one"
    assert call(session, "load", paths=[])["cancelled"]
    call(session, "clear")
    assert not session._model.overlay_model.overlays


def test_overlay_files_plot_before_loading_a_current_pattern(tmp_path):
    session = DesktopSession()
    path = tmp_path / "reference.xy"
    np.savetxt(path, np.column_stack([np.arange(10), np.arange(10) ** 2]))
    result = call(session, "load", paths=[str(path)])
    assert result["pattern"]["x"] == []
    assert result["pattern"]["curves"][0]["y"] == list(np.arange(10) ** 2)
    result = call(session, "visibility", visible=False)
    assert result["pattern"]["curves"] == []
    assert not session.invoke("integration_overlay", {"operation": "capture"})["ok"]


@pytest.mark.parametrize("separation,expected", [(100, [-200, -100]), (-100, [200, 100]), (0, [0, 0])])
def test_signed_waterfall_model_and_persistence(session, separation, expected, tmp_path):
    call(session, "capture")
    call(session, "capture")
    call(session, "waterfall_separation", separation=separation)
    result = call(session, "waterfall")
    assert [o["offset"] for o in result["state"]["integration"]["overlays"]] == expected
    path = tmp_path / "signed-waterfall.dio"
    assert session.invoke("save_project", {"path": str(path)})["ok"]
    restored = DesktopSession()
    result = restored.invoke("open_project", {"path": str(path)})
    assert result["ok"]
    assert result["state"]["integration"]["waterfallSeparation"] == separation
    assert [o["offset"] for o in result["state"]["integration"]["overlays"]] == expected


def test_color_scale_one_undo_restores_all_previous_colors(session):
    call(session, "capture")
    call(session, "capture")
    before = call(session, "update", index=0, color="#ff3311")["state"]["integration"]["overlays"]
    previous = [o["color"] for o in before]
    call(session, "color_scale", colors=["#440154", "#fde725"])
    result = session.invoke("undo_mask")
    assert result["ok"], result
    assert [o["color"] for o in result["state"]["integration"]["overlays"]] == previous
    assert result["pattern"] and len(result["pattern"]["curves"]) == 2
    result = session.invoke("redo_mask")
    assert result["ok"], result
    assert [o["color"] for o in result["state"]["integration"]["overlays"]] == ["#440154", "#fde725"]
    assert not session.invoke("integration_overlay", {"operation": "color_scale", "colors": ["#123456", "invalid"]})["ok"]
    assert [o.color for o in session._model.overlay_model.overlays] == ["#440154", "#fde725"]


def test_overlay_edits_and_history_leave_detector_and_calibration_untouched(monkeypatch):
    session = DesktopSession()
    assert session.invoke("example")["ok"]
    assert session.invoke("open_calibration", {"path": str(DATA / "CeO2_Pilatus1M.poni")})["ok"]
    call(session, "capture")
    cake = session._cake
    image = session.configuration.img_model.raw_img_data
    diagnostic = (session._fit_dirty, session._fit_rms)

    def unexpected(*args, **kwargs):
        raise AssertionError("Overlay edits must not refresh detector/calibration data")

    monkeypatch.setattr(session, "_calculate", unexpected)
    monkeypatch.setattr(session, "_raster", unexpected)
    monkeypatch.setattr(session.configuration.img_model, "_calculate_img_data", unexpected)
    monkeypatch.setattr(session.configuration.calibration_model, "create_cake_geometry", unexpected)
    monkeypatch.setattr(session.configuration.mask_model, "set_mask_data", unexpected)
    for change in [dict(color="#f5bb55"), dict(visible=False), dict(scale=2), dict(offset=-20)]:
        result = call(session, "update", index=0, **change)
        assert result["patternOnly"]
        assert not {"cake", "mask", "image", "rawImage", "rings", "linked"}.intersection(result)
        for action in ["undo_mask", "redo_mask"]:
            result = session.invoke(action)
            assert result["ok"], result.get("error")
            assert result["patternOnly"]
            assert not {"cake", "mask", "image", "rawImage"}.intersection(result)
        assert session._cake is cake
        assert session.configuration.img_model.raw_img_data is image
        assert (session._fit_dirty, session._fit_rms) == diagnostic
    call(session, "original_color", color="#e9c46a")
    for action, color in [("undo_mask", "#ffffff"), ("redo_mask", "#e9c46a")]:
        result = session.invoke(action)
        assert result["ok"], result.get("error")
        assert result["state"]["integration"]["originalPatternColor"] == color
        assert result["patternOnly"]
        assert not {"cake", "mask", "image", "rawImage"}.intersection(result)
    call(session, "original_visibility", visible=False)
    for action, visible in [("undo_mask", True), ("redo_mask", False)]:
        result = session.invoke(action)
        assert result["ok"], result.get("error")
        assert result["state"]["integration"]["originalPatternVisible"] is visible
        assert result["patternOnly"]
        assert not {"cake", "mask", "image", "rawImage"}.intersection(result)
    assert session._cake is cake
    assert (session._fit_dirty, session._fit_rms) == diagnostic


def test_consecutive_scale_and_offset_edits_each_undo_as_one_group(session):
    call(session, "capture")
    call(session, "capture")
    for scale in [1.1, 1.2, 1.4, 2.0]:
        call(session, "update", index=0, scale=scale)
    assert session.invoke("undo_mask")["ok"]
    assert session._model.overlay_model.overlays[0].scaling == 1
    assert session.invoke("redo_mask")["ok"]
    assert session._model.overlay_model.overlays[0].scaling == 2
    for offset in [10, 20, 30, 150]:
        call(session, "update", index=0, offset=offset)
    assert session.invoke("undo_mask")["ok"]
    assert session._model.overlay_model.overlays[0].offset == 0
    assert session._model.overlay_model.overlays[0].scaling == 2
    assert session.invoke("redo_mask")["ok"]
    assert session._model.overlay_model.overlays[0].offset == 150
    call(session, "update", index=1, scale=3)
    call(session, "update", index=0, scale=4)
    assert session.invoke("undo_mask")["ok"]
    assert session._model.overlay_model.overlays[0].scaling == 2
    assert session._model.overlay_model.overlays[1].scaling == 3


def test_original_color_shares_overlay_history_and_project_persistence(session, tmp_path):
    call(session, "capture")
    call(session, "original_color", color="#e9c46a")
    call(session, "update", index=0, color="#c162ed")
    result = session.invoke("undo_mask")
    assert result["ok"]
    assert result["state"]["integration"]["originalPatternColor"] == "#e9c46a"
    assert result["state"]["integration"]["overlays"][0]["color"] != "#c162ed"
    result = session.invoke("undo_mask")
    assert result["ok"]
    assert result["state"]["integration"]["originalPatternColor"] == "#ffffff"
    for _ in range(2):
        assert session.invoke("redo_mask")["ok"]
    assert session.configuration.pattern_model.params.color == "#e9c46a"
    assert session._model.overlay_model.overlays[0].color == "#c162ed"
    path = tmp_path / "original-color.dio"
    assert session.invoke("save_project", {"path": str(path)})["ok"]
    restored = DesktopSession()
    result = restored.invoke("open_project", {"path": str(path)})
    assert result["ok"]
    assert result["state"]["integration"]["originalPatternColor"] == "#e9c46a"
    before = session._model.history.depth
    assert not session.invoke("integration_overlay", {"operation": "original_color", "color": "bad"})["ok"]
    assert session.configuration.pattern_model.params.color == "#e9c46a"
    assert session._model.history.depth == before


def test_original_visibility_shared_history_and_project_persistence(session, tmp_path):
    call(session, "capture")
    original_y = session._pattern["y"].copy()
    call(session, "original_visibility", visible=False)
    call(session, "original_color", color="#e9c46a")
    call(session, "update", index=0, visible=False)
    for _ in range(2):
        result = session.invoke("undo_mask")
        assert result["ok"]
        assert result["state"]["integration"]["originalPatternVisible"] is False
    result = session.invoke("undo_mask")
    assert result["ok"]
    assert result["state"]["integration"]["originalPatternVisible"] is True
    assert result["state"]["integration"]["originalPatternColor"] == "#ffffff"
    for _ in range(3):
        assert session.invoke("redo_mask")["ok"]
    assert session._pattern["y"] == original_y
    assert session.configuration.pattern_model.params.visible is False
    path = tmp_path / "original-hidden.dio"
    assert session.invoke("save_project", {"path": str(path)})["ok"]
    restored = DesktopSession()
    result = restored.invoke("open_project", {"path": str(path)})
    assert result["ok"]
    assert result["state"]["integration"]["originalPatternVisible"] is False
    assert result["state"]["integration"]["originalPatternColor"] == "#e9c46a"
    assert not session.invoke("integration_overlay", {"operation": "original_visibility", "visible": "false"})["ok"]
    assert session.configuration.pattern_model.params.visible is False
    result = call(session, "clear")
    assert result["state"]["integration"]["originalPatternVisible"] is True
    result = session.invoke("undo_mask")
    assert result["ok"]
    assert result["state"]["integration"]["originalPatternVisible"] is False


def test_original_visibility_history_without_overlays(session, tmp_path):
    call(session, "original_visibility", visible=False)
    assert session.invoke("undo_mask")["state"]["integration"]["originalPatternVisible"] is True
    assert session.invoke("redo_mask")["state"]["integration"]["originalPatternVisible"] is False
    path = tmp_path / "original-only-hidden.dio"
    assert session.invoke("save_project", {"path": str(path)})["ok"]
    result = DesktopSession().invoke("open_project", {"path": str(path)})
    assert result["ok"]
    assert result["state"]["integration"]["originalPatternVisible"] is False
    assert result["state"]["integration"]["overlays"] == []
