"""Picked groups round-trip independently of a complete project or fitted geometry."""

from copy import deepcopy
import json

import pytest

from dioptas.desktop.session import DesktopSession


def call(session, action, **payload):
    result = session.invoke(action, payload)
    assert result["ok"], result.get("error")
    return result


@pytest.fixture
def peaks(tmp_path):
    session = DesktopSession()
    call(session, "example")
    # Fractional source-pixel coordinates and repeated rings exercise lossless
    # persistence and group ordering, rather than calibration accuracy.
    groups = (
        (0, ((1.125, 2.5), (3.25, 4.75))),
        (2, ((100.5, 200.25),)),
        (0, ((10.125, 11.25),)),
    )
    session.configuration.calibration_model.params.peak_selections = groups
    path = tmp_path / "peaks.json"
    call(session, "save_peaks", path=str(path))
    return session, path, groups


def test_peak_file_round_trip_replacement_history_and_fit_state(peaks):
    session, path, groups = peaks
    before = call(session, "state")["state"]
    saved = call(session, "save_peaks", path=str(path.with_suffix("")))
    assert saved["savedPath"] == str(path)
    assert saved["state"]["calibration"] == before["calibration"]
    call(session, "clear_peaks")
    empty = call(session, "state")["state"]
    loaded = call(session, "load_peaks", path=str(path))
    assert session.configuration.calibration_model.params.peak_selections == groups
    assert loaded["state"]["calibration"]["fitDirty"]
    assert loaded["state"]["geometry"] == before["geometry"]
    assert loaded["state"]["calibration"]["picks"] == before["calibration"]["picks"]
    call(session, "undo_calibration")
    assert call(session, "state")["state"]["calibration"]["picks"] == empty["calibration"]["picks"]
    call(session, "redo_calibration")
    assert session.configuration.calibration_model.params.peak_selections == groups
    # Loading replaces, rather than accumulating duplicate selections.
    call(session, "load_peaks", path=str(path))
    assert session.configuration.calibration_model.params.peak_selections == groups


@pytest.mark.parametrize(
    "change",
    [
        lambda d: d.update(version=2),
        lambda d: d.update(coordinates="top-left"),
        lambda d: d.update(imageShape=[10, 10]),
        lambda d: d.update(imageTransformations=["flipud"]),
        lambda d: d["calibrant"].update(dSpacingsAngstrom=[1.0]),
        lambda d: d["groups"][0].update(ring=0),
        lambda d: d["groups"][0].update(ring=1.5),
        lambda d: d["groups"][0].update(points=[]),
        lambda d: d["groups"][-1].update(points=[[float("nan"), 2]]),
        lambda d: d["groups"][-1].update(points=[[-1, 2]]),
        lambda d: d["groups"][-1].update(points=[[1, 999999]]),
        lambda d: d["groups"][-1].update(points=[[True, 2]]),
    ],
)
def test_invalid_peak_file_preserves_existing_groups_and_fit_state(peaks, change):
    session, path, groups = peaks
    before = deepcopy(call(session, "state")["state"]["calibration"])
    document = json.loads(path.read_text())
    change(document)
    path.write_text(json.dumps(document))
    result = session.invoke("load_peaks", {"path": str(path)})
    assert not result["ok"]
    assert session.configuration.calibration_model.params.peak_selections == groups
    assert call(session, "state")["state"]["calibration"] == before


def test_file_dialog_cancellation_preserves_groups(peaks):
    session, _, groups = peaks
    session._choose_file = lambda kind, save: None
    before = call(session, "state")["state"]["calibration"]
    for action in ("load_peaks", "save_peaks"):
        assert call(session, action)["cancelled"]
        assert session.configuration.calibration_model.params.peak_selections == groups
        assert call(session, "state")["state"]["calibration"] == before


def test_empty_session_requires_image_and_picks(tmp_path):
    session = DesktopSession()
    path = str(tmp_path / "peaks.json")
    assert not session.invoke("load_peaks", {"path": path})["ok"]
    assert not session.invoke("save_peaks", {"path": path})["ok"]
    call(session, "example")
    assert not session.invoke("save_peaks", {"path": path})["ok"]
