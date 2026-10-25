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
        w.frame_slider.setValue(0)
        w.table_view.selectRow(0)
        assert w.frame_slider.value() == 2
        assert sc.result is result
        assert not w.position_details.isHidden()
        assert w.position_indexing_label.text().startswith("Not assessed")
        assert w.position_frames.count() == 3
        assert "file #11" in w.position_frames.itemText(0)
        assert "ω -4.5 → -4°" in w.position_frames.itemText(0)
        w.position_frames.setCurrentIndex(2)
        assert w.frame_slider.value() == 3
        assert w.selected_spot_overlay.isVisible()
        w.threshold.setValue(6)
        assert sc.result is None
        assert w.position_details.isHidden()
        assert not w.export_button.isEnabled()
    finally:
        c.widget.close()


def test_selected_position_ring_follows_observations_and_clears(qapp, tmp_path):
    from qtpy import QtCore

    seed = make_run(tmp_path)
    for i in range(1, 4):
        image = np.full((48, 60), 5, np.uint16)
        image[20:23, 24 + i : 27 + i] += 100
        image[8:11, 40:43] += 100
        TifImage(data=image).write(str(tmp_path / f"sample_{i + 10:03d}.tif"))
    c = MainController(
        use_settings=False, run_async_processing=False, experimental_single_crystal=True
    )
    try:
        c.widget.single_crystal_mode_btn.click()
        sc, w = c.single_crystal_controller, c.widget.single_crystal_widget
        sc.load_series(import_series(seed))
        sc.detect()
        assert len(sc.result.table) == 2
        track = int(np.argmin(sc.result.table.column("x")))
        w.table_view.selectRow(track)
        assert w.frame_slider.value() == 2
        assert "magenta ring" in w.status_label.text()
        for frame in (1, 2, 3):
            w.frame_slider.setValue(frame)
            rows = sc.result.table.observations
            observed = rows[(rows[:, 0] == track) & (rows[:, 1] == frame)][0]
            for ring in (w.selected_spot_overlay, w.selected_spot_outline):
                assert ring.isVisible()
                np.testing.assert_allclose(
                    [ring.getData()[0][0], ring.getData()[1][0]],
                    observed[2:4] + 0.5,
                    atol=1e-12,
                    rtol=0,
                )
        # Selection on the same frame must move the ring immediately. Recenter
        # an off-screen selected spot without changing the zoom level.
        view = w.img_widget.img_view_box
        view.setRange(rect=QtCore.QRectF(0, 0, 5, 5), padding=0)
        w.table_view.selectRow(1 - track)
        assert w.frame_slider.value() == 2
        x, y = w.selected_spot_overlay.getData()
        assert x[0] == 41.5 and y[0] == 38.5
        assert view.viewRect().contains(QtCore.QPointF(x[0], y[0]))
        w.prediction_enabled.setChecked(False)
        assert w.selected_spot_overlay.isVisible()
        w.frame_slider.setValue(0)
        assert not w.selected_spot_overlay.isVisible()
        w.frame_slider.setValue(2)
        assert w.selected_spot_overlay.isVisible()
        w.table_view.clearSelection()
        assert not w.selected_spot_overlay.isVisible()
        assert not w.selected_spot_outline.isVisible()
        w.table_view.selectRow(track)
        assert w.selected_spot_overlay.isVisible()
        w.threshold.setValue(6)
        assert not w.selected_spot_overlay.isVisible()
        assert not w.selected_spot_outline.isVisible()
    finally:
        c.widget.close()


def test_image_click_selects_linked_row_without_changing_frame(qapp, qtbot, tmp_path):
    from qtpy import QtCore

    seed = make_run(tmp_path)
    # A spot in an earlier frame means the current frame's only detection is
    # not row zero in the final linked table.
    image = np.full((48, 60), 5, np.uint16)
    image[34:37, 8:11] += 100
    TifImage(data=image).write(str(tmp_path / "sample_010.tif"))
    c = MainController(
        use_settings=False, run_async_processing=False, experimental_single_crystal=True
    )
    try:
        c.widget.resize(1400, 950)
        c.show_window()
        c.widget.single_crystal_mode_btn.click()
        sc, w = c.single_crystal_controller, c.widget.single_crystal_widget
        sc.load_series(import_series(seed))
        sc.detect()
        assert len(sc.result.table) == 2
        w.frame_slider.setValue(1)
        qapp.processEvents()
        points = w.spot_overlay.points()
        assert len(points) == 1 and points[0].data() == 1

        def click_spot(button=QtCore.Qt.LeftButton):
            point = w.spot_overlay.points()[0]
            graphics = w.img_widget.pg_layout
            position = graphics.mapFromScene(w.spot_overlay.mapToScene(point.pos()))
            qtbot.mouseClick(graphics.viewport(), button, pos=position)

        click_spot()
        assert w.sections.currentWidget() is w.positions_section
        assert [i.row() for i in w.table_view.selectionModel().selectedRows()] == [1]
        assert w.table_view.visualRect(w.table_view.model().index(1, 0)).intersects(
            w.table_view.viewport().rect()
        )
        assert w.frame_slider.value() == 1
        assert w.selected_spot_overlay.isVisible()
        expected = points[0].pos()
        np.testing.assert_allclose(
            [
                w.selected_spot_overlay.getData()[0][0],
                w.selected_spot_overlay.getData()[1][0],
            ],
            [expected.x(), expected.y()],
            atol=1e-12,
            rtol=0,
        )
        click_spot()  # Already selected: retain frame and highlight.
        assert w.frame_slider.value() == 1
        w.frame_slider.setValue(3)
        click_spot()
        assert w.frame_slider.value() == 3
        w.table_view.clearSelection()
        click_spot(QtCore.Qt.RightButton)
        assert not w.table_view.selectionModel().selectedRows()
        # Table-driven selection still chooses the middle observed frame.
        w.table_view.selectRow(1)
        assert w.frame_slider.value() == 2
        w.table_view.clearSelection()
        w.show_spots([10.5], [10.5], [0])  # Unlinked live-preview detection.
        sc._spot_clicked(w.spot_overlay, w.spot_overlay.points())
        assert not w.table_view.selectionModel().selectedRows()
        w.threshold.setValue(6)
        sc._spot_clicked(w.spot_overlay, points)
        assert not w.table_view.selectionModel().selectedRows()
    finally:
        c.widget.close()


def test_background_series_browsing_and_stale_work(qapp, qtbot, tmp_path, monkeypatch):
    import importlib
    import threading

    module = importlib.import_module("dioptas.controller.SingleCrystalController")
    original = module.locate_positions
    started, release = threading.Event(), threading.Event()

    def delayed(task, progress=None, preview=None):
        started.set()
        assert release.wait(10)
        return original(task, progress=progress, preview=preview)

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


def test_isolated_launcher_registers_bundled_hdf5_filters(tmp_path):
    from pathlib import Path
    import subprocess
    import sys

    root = Path(__file__).parents[3]
    code = """
import run_experimental_single_crystal as launcher
launcher.disable_external_hdf5_plugins()
import h5py, hdf5plugin, numpy as np, tempfile
from pathlib import Path
with tempfile.TemporaryDirectory() as folder:
    path=Path(folder)/'counts.h5'
    data=np.arange(100).reshape(10,10)
    with h5py.File(path,'w') as f:
        f.create_dataset('counts',data=data,**hdf5plugin.Blosc())
    with h5py.File(path,'r') as f:
        np.testing.assert_array_equal(f['counts'][...],data)
print('bundled filter round trip passed')
"""
    completed = subprocess.run(
        [sys.executable, "-c", code],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "bundled filter round trip passed" in completed.stdout


def test_select_one_frame_discovers_only_its_run(qapp, tmp_path, monkeypatch):
    seed = make_run(tmp_path)
    # Nearby files, including sidecars and a different numeric run, stay separate.
    for name in ("other_012.tif", "sample_012.tif.bak", "sample_0120.png"):
        (tmp_path / name).write_text("unrelated")
    monkeypatch.setattr(
        QtWidgets.QFileDialog, "getOpenFileName", lambda *a, **k: (str(seed), "")
    )

    def confirm(dialog):
        dialog.confirm()
        return dialog.result()

    monkeypatch.setattr(RotationSeriesDialog, "exec_", confirm)
    c = MainController(
        use_settings=False, run_async_processing=False, experimental_single_crystal=True
    )
    try:
        sc, w = c.single_crystal_controller, c.widget.single_crystal_widget
        sc.open_series()
        assert len(sc.series.files) == 5
        assert w.frame_slider.value() == 2
        assert c.model.img_model.filename == str(seed)
        # Command-line and dialog paths may include a redundant ./ component.
        sc.load_series(sc.series, str(seed.parent) + "/./" + seed.name)
        assert w.frame_slider.value() == 2
        w.previous_frame_button.click()
        assert w.frame_slider.value() == 1
        w.next_frame_button.click()
        assert w.frame_slider.value() == 2
        w.frame_slider.setValue(0)
        assert not w.previous_frame_button.isEnabled()
        assert w.next_frame_button.isEnabled()
        w.frame_slider.setValue(4)
        assert w.previous_frame_button.isEnabled()
        assert not w.next_frame_button.isEnabled()
        assert w.sections.count() == 4
        for index in range(w.sections.count()):
            w.sections.setCurrentIndex(index)
            assert sc.series is not None
        # Changing to an unrelated image disables both navigation buttons.
        sc._image_changed()
        assert not w.previous_frame_button.isEnabled()
        assert not w.next_frame_button.isEnabled()
    finally:
        c.widget.close()


def test_preview_snapshots_preserve_position_results(tmp_path):
    task = SeriesTask(import_series(make_run(tmp_path)), np.zeros((48, 60), bool), {})
    frames = []
    result = locate_positions(task, preview=frames.append)
    original = locate_positions(task)
    assert [f.index for f in frames] == list(range(5))
    assert [len(f.table) for f in frames] == [0, 1, 1, 1, 0]
    for frame in frames:
        assert not frame.image.flags.writeable
        assert not frame.table.values.flags.writeable
        np.testing.assert_array_equal(
            frame.image, read_frame(task.series.files[frame.index])
        )
    np.testing.assert_array_equal(
        result.table.observations, original.table.observations
    )
    np.testing.assert_array_equal(result.table.values, original.table.values)
    assert result.table.frame_hashes == original.table.frame_hashes


@pytest.mark.parametrize("invalidate", [False, True])
def test_completed_frames_preview_async_pause_and_stale_discard(
    qapp, qtbot, tmp_path, monkeypatch, invalidate
):
    import importlib
    import threading
    from qtpy import QtCore

    module = importlib.import_module("dioptas.controller.SingleCrystalController")
    original = module.locate_positions
    first, second = threading.Event(), threading.Event()
    release_first, release_second = threading.Event(), threading.Event()

    def delayed(task, progress=None, preview=None):
        def frame_ready(frame):
            assert QtCore.QThread.currentThread() is not qapp.thread()
            preview(frame)
            if frame.index == 1:
                first.set()
                assert release_first.wait(10)
            if frame.index == 3:
                second.set()
                assert release_second.wait(10)

        return original(task, progress=progress, preview=frame_ready)

    monkeypatch.setattr(module, "locate_positions", delayed)
    c = MainController(
        use_settings=False, run_async_processing=True, experimental_single_crystal=True
    )
    try:
        c.widget.single_crystal_mode_btn.click()
        sc, w = c.single_crystal_controller, c.widget.single_crystal_widget
        sc.load_series(import_series(make_run(tmp_path)))
        model_file = c.model.img_model.filename
        render_threads = []
        plot = w.img_widget.plot_image

        def render(*args, **kwargs):
            render_threads.append(QtCore.QThread.currentThread())
            return plot(*args, **kwargs)

        monkeypatch.setattr(w.img_widget, "plot_image", render)
        w.detect_button.click()
        qtbot.waitUntil(
            lambda: first.is_set() and "completed frame 2/5" in w.frame_label.text(),
            timeout=5000,
        )
        assert sc._runner.is_busy and sc.result is None
        assert w.frame_slider.value() == 1
        assert "sample_011.tif" in w.source_label.text()
        assert "spots found: 1" in w.source_label.text()
        assert (
            c.model.img_model.filename == model_file
        )  # preview does not trigger model loading/integration
        np.testing.assert_array_equal(
            w.img_widget.img_data, read_frame(sc.series.files[1])
        )
        w.img_widget.mouse_moved.emit(26.5, 18.5)
        shown_count = w.img_widget.img_data[18, 26]
        assert f"I: {shown_count:.6g} counts" in w.mouse_pixel_label.text()
        np.testing.assert_allclose(w.spot_overlay.getData()[0], [26.5], atol=1e-12)
        assert all(thread is qapp.thread() for thread in render_threads)
        assert w.spot_overlay.opts["pen"].color().name() == "#000000"
        assert w.spot_overlay.opts["pen"].widthF() >= 2
        if invalidate:
            w.threshold.setValue(6)
            assert not sc._preview_timer.isActive()
            assert sc._pending_preview is None
            release_first.set()
            release_second.set()
            qtbot.waitUntil(lambda: not sc._runner.is_busy, timeout=5000)
            assert sc.result is None
            assert "Search preview" not in w.frame_label.text()
            assert w.frame_slider.value() == 0
            assert len(w.spot_overlay.getData()[0]) == 0
        else:
            w.follow_search.setChecked(False)
            assert c.model.img_model.filename == sc.series.files[1]
            release_first.set()
            qtbot.waitUntil(second.is_set, timeout=5000)
            assert w.frame_slider.value() == 1
            assert sc._pending_preview[1].index == 3
            w.follow_search.setChecked(True)
            assert "completed frame 4/5" in w.frame_label.text()
            assert w.frame_slider.value() == 3
            w.previous_frame_button.click()
            assert not w.follow_search.isChecked()
            assert w.frame_slider.value() == 2
            release_second.set()
            qtbot.waitUntil(lambda: sc.result is not None, timeout=5000)
            assert w.frame_slider.value() == 2
            assert c.model.img_model.filename == sc.series.files[2]
            assert not sc._preview_timer.isActive()
            assert sc._pending_preview is None
    finally:
        release_first.set()
        release_second.set()
        c.widget.close()
