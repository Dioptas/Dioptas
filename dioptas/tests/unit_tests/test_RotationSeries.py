"""Explicit scan metadata, one-run selection and position-only export."""

import json

import numpy as np
import pytest
from fabio.tifimage import TifImage
from qtpy import QtWidgets

from dioptas.controller.MainController import MainController
from dioptas.model.rotation_series import (
    SeriesTask,
    export_positions,
    import_series,
    locate_positions,
    read_frame,
    series_files,
)
from dioptas.widgets.RotationSeriesDialog import RotationSeriesDialog


def make_run(tmp_path, metadata=True):
    for i in range(5):
        image = np.full((48, 60), 5, np.uint16)
        if 1 <= i <= 3:
            image[20:23, 25:28] += 100
        p = tmp_path / f"sample_{i + 10:03d}.tif"
        TifImage(data=image).write(str(p))
        if metadata:
            (tmp_path / (tmp_path.name + p.name + ".txt")).write_text(
                f"omega0 = {-5 + i * 0.5}\nomegaR = .5\nchi = {20 + i}\nexp. time = .5\n"
            )
    return tmp_path / "sample_012.tif"


def test_import_preserves_frame_ids_and_explicit_start_width_metadata(tmp_path):
    seed = make_run(tmp_path)
    series = import_series(seed)
    assert series.frame_numbers == (10, 11, 12, 13, 14)
    np.testing.assert_allclose(
        series.omega_bounds[:, 0], [-5, -4.5, -4, -3.5, -3], atol=0, rtol=0
    )
    np.testing.assert_allclose(np.diff(series.omega_bounds), 0.5, atol=0, rtol=0)
    assert series.source_records[0]["values"]["chi"] == 20
    assert not series.omega_bounds.flags.writeable
    assert len(series.files) == 5
    assert read_frame(series.files[0]).shape == (48, 60)


def test_manual_angles_keep_source_and_missing_numeric_frame_gap(tmp_path):
    seed = make_run(tmp_path)
    (tmp_path / "sample_011.tif").unlink()
    series = import_series(seed, manual_angles=(10, 0.5, 0.25))
    np.testing.assert_allclose(
        series.omega_bounds[:, 0], [10, 11, 11.5, 12], atol=0, rtol=0
    )
    assert series.source_records[0]["values"]["omega0"] == -5
    assert "user override" in series.angle_source
    assert len(series_files(seed)[0]) == 4
    with pytest.raises(ValueError):
        import_series(seed, manual_angles=(0, 0, 1))


def test_missing_metadata_requires_explicit_angles_and_dialog_confirmation(
    qapp, tmp_path
):
    seed = make_run(tmp_path, metadata=False)
    with pytest.raises(ValueError, match="metadata are missing"):
        import_series(seed)
    dialog = RotationSeriesDialog(str(seed))
    assert not dialog.sidecars.isEnabled()
    dialog.start.setValue(-10)
    dialog.step.setValue(0.5)
    dialog.width.setValue(0.25)
    dialog.confirm()
    assert dialog.result() == QtWidgets.QDialog.Accepted
    np.testing.assert_allclose(
        dialog.series.omega_bounds[0], [-10, -9.75], atol=0, rtol=0
    )


def test_positions_and_exports_contain_no_integrated_intensity(tmp_path):
    seed = make_run(tmp_path)
    result = locate_positions(
        SeriesTask(import_series(seed), np.zeros((48, 60), bool), {})
    )
    assert len(result.table) == 1
    assert len(result.table.observations) == 3
    np.testing.assert_allclose(result.table.values[0, :3], [26, 26, -3.75], atol=1e-12)
    paths = export_positions(result, str(tmp_path / "positions.csv"))
    assert "intensity" not in paths[0].read_text().splitlines()[0]
    assert len(paths[1].read_text().splitlines()) == 4
    metadata = json.loads(paths[2].read_text())
    assert metadata["source_records"][0]["values"]["chi"] == 20
    assert metadata["frame_numbers"] == [10, 11, 12, 13, 14]


def test_ui_browsing_preserves_positions_and_settings_invalidate(qapp, tmp_path):
    seed = make_run(tmp_path)
    c = MainController(
        use_settings=False, run_async_processing=False, experimental_single_crystal=True
    )
    try:
        c.widget.single_crystal_mode_btn.click()
        sc = c.single_crystal_controller
        sc.load_series(import_series(seed))
        w = c.widget.single_crystal_widget
        assert w.detect_button.text() == "Find 3D positions"
        w.detect_button.click()
        result = sc.result
        assert result is not None and len(result.table) == 1
        assert w.table_view.model() is w.position_table_model
        w.frame_slider.setValue(2)
        assert sc.result is result
        assert "midpoint -3.75" in w.frame_label.text()
        assert len(w.spot_overlay.getData()[0]) == 1
        w.table_view.selectRow(0)
        assert len(w.position_plot.listDataItems()) == 2
        w.threshold.setValue(6)
        assert sc.result is None
        assert not w.export_button.isEnabled()
    finally:
        c.widget.close()


def test_background_series_browsing_and_stale_work(qapp, qtbot, tmp_path, monkeypatch):
    import importlib
    import threading

    module = importlib.import_module("dioptas.controller.SingleCrystalController")
    original = module.locate_positions
    started, release = threading.Event(), threading.Event()

    def delayed(task, progress=None):
        started.set()
        assert release.wait(10)
        return original(task, progress=progress)

    monkeypatch.setattr(module, "locate_positions", delayed)
    c = MainController(
        use_settings=False, run_async_processing=True, experimental_single_crystal=True
    )
    try:
        sc = c.single_crystal_controller
        c.widget.single_crystal_mode_btn.click()
        sc.load_series(import_series(make_run(tmp_path)))
        w = c.widget.single_crystal_widget
        w.detect_button.click()
        qtbot.waitUntil(started.is_set, timeout=5000)
        w.frame_slider.setValue(2)
        release.set()
        qtbot.waitUntil(lambda: sc.result is not None, timeout=5000)
        assert len(sc.result.table) == 1
        release.clear()
        started.clear()
        w.detect_button.click()
        qtbot.waitUntil(started.is_set, timeout=5000)
        w.threshold.setValue(6)
        release.set()
        qtbot.waitUntil(lambda: not sc._runner.is_busy, timeout=5000)
        assert sc.result is None
        assert w.position_table_model.rowCount() == 0
        assert not w.export_button.isEnabled()
    finally:
        release.set()
        c.widget.close()
