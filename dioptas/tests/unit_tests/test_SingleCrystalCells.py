"""Ranked settings select frozen PhaseSmith fits and never reuse stale previews."""

import importlib
import json
import threading

import numpy as np
import pytest
from qtpy import QtCore

from .test_SingleCrystalRefinement import (
    experiment,
)  # Shared synthetic rotating-crystal fixture.
from dioptas.model.single_crystal_cells import (
    rank_cells,
    preview_ranked_cell,
    export_ranked_cells,
)


@pytest.fixture(scope="module")
def ranked_experiment(request):
    positions, cells, _ = request.getfixturevalue("experiment")
    return positions, cells, rank_cells(positions, cells)


def test_adapter_rank_support_export_and_no_refitting(ranked_experiment, tmp_path):
    positions, _, ranked = ranked_experiment
    comp = ranked.comparison
    assert comp.recommended.setting.symbol == "oP"
    matrices = np.array([f.reciprocal_basis for f in comp.settings])
    for row in comp.ranking:
        preview = preview_ranked_cell(
            ranked, positions, (2048, 2048), row.setting_index
        )
        np.testing.assert_array_equal(
            preview.refinement.reciprocal_basis, matrices[row.setting_index]
        )
        assert preview.metadata["ranked_setting"]["rank"] == row.rank
        assert preview.metadata["material_or_cell_priors"] is False
        assert len(preview.refined_scan.values) > 100
        np.testing.assert_array_equal(preview.refinement.training, comp.training)
    np.testing.assert_array_equal(matrices, [f.reciprocal_basis for f in comp.settings])
    path = export_ranked_cells(ranked, tmp_path / "ranked.json")
    data = json.loads(path.read_text())
    assert [r["rank"] for r in data["ranking"]] == list(
        range(1, len(comp.settings) + 1)
    )
    assert len(data["primitive_hypotheses"]) == 390
    assert any(not p["supported"] for p in data["primitive_hypotheses"])
    with pytest.raises(ValueError):
        preview_ranked_cell(ranked, positions, (2048, 2048), -1)


def controller_scene(tmp_path, positions, cells, *, asynchronous=False):
    from fabio.tifimage import TifImage
    from dioptas.controller.MainController import MainController

    c = MainController(
        use_settings=False,
        run_async_processing=asynchronous,
        experimental_single_crystal=True,
    )
    path = tmp_path / "unknown.tif"
    TifImage(data=np.full((2048, 2048), 100, np.uint16)).write(str(path))
    c.model.img_model.load(str(path))
    sc, w = c.single_crystal_controller, c.widget.single_crystal_widget
    sc._show_result(positions, sc._generation)
    sc._show_result(cells, sc._generation)
    w.frame_slider.setRange(0, 179)
    return c, sc, w


def test_sorted_row_selection_previews_actual_fit_and_invalidates(
    qapp, tmp_path, ranked_experiment
):
    positions, cells, ranked = ranked_experiment
    c, sc, w = controller_scene(tmp_path, positions, cells)
    try:
        sc._show_result(ranked, sc._generation)
        assert w.rank_table_model.rowCount() == len(ranked.comparison.settings)
        assert w.cell_view.currentIndex() == 1
        assert not w.rank_table.isColumnHidden(3)
        assert w.rank_table_model.headerData(3, QtCore.Qt.Horizontal) == "α, β, γ (°)"
        assert w.rank_table_model.data(w.rank_table_model.index(0, 3)) == "90, 90, 90"
        assert w.sections.currentIndex() == 2
        assert w.prediction_model.currentIndex() == 1
        assert sc.ranked_selection == ranked.comparison.recommended_setting_index
        w.rank_table.sortByColumn(0, QtCore.Qt.DescendingOrder)
        w.rank_table.selectRow(0)
        selected = w.rank_table.currentIndex().data(QtCore.Qt.UserRole)
        assert sc.ranked_selection == selected
        assert sc.refinement_result.metadata["setting_index"] == selected
        np.testing.assert_array_equal(
            sc.refinement_result.refinement.reciprocal_basis,
            ranked.comparison.settings[selected].reciprocal_basis,
        )
        preview = sc.refinement_result
        frame = int(
            preview.refined_scan.frame_indices[
                len(preview.refined_scan.frame_indices) // 2
            ]
        )
        w.frame_slider.setValue(frame)
        sc.plot_predictions()
        mask = preview.refined_scan.frame_indices == frame
        np.testing.assert_allclose(
            w.predicted_overlay.getData()[0], preview.refined_scan.values[mask, 0] + 0.5
        )
        # A non-improving held-out metric must not silently substitute another cell.
        preview.refinement.metrics["validation_improved"] = False
        sc._show_result(preview, sc._generation)
        assert w.prediction_model.currentIndex() == 1
        sc.show_refinement_residuals()
        assert len(sc._residual_dialog.plots) == 6
        sc.invalidate()
        assert sc.ranked_result is None and sc.ranked_selection is None
        assert w.rank_table_model.rowCount() == 0
        assert sc.refinement_result is None and not w.rank_button.isEnabled()
        assert not w.rank_export_button.isEnabled()
    finally:
        c.widget.close()


def test_rapid_selection_discards_old_preview_and_keeps_latest(
    qapp, qtbot, tmp_path, ranked_experiment, monkeypatch
):
    positions, cells, ranked = ranked_experiment
    module = importlib.import_module("dioptas.controller.SingleCrystalController")
    original = module.preview_ranked_cell
    started, release = threading.Event(), threading.Event()
    calls = []

    def delayed(*args):
        calls.append(args[-1])
        if len(calls) == 1:
            started.set()
            assert release.wait(10)
        return original(*args)

    monkeypatch.setattr(module, "preview_ranked_cell", delayed)
    c, sc, w = controller_scene(tmp_path, positions, cells, asynchronous=True)
    try:
        sc._show_result(ranked, sc._generation)
        qtbot.waitUntil(started.is_set, timeout=5000)
        w.prediction_enabled.setChecked(False)
        w.rank_table.selectRow(1)
        w.rank_table.selectRow(w.rank_table_model.rowCount() - 1)
        selected = sc.ranked_selection
        assert sc.refinement_result is None
        release.set()
        qtbot.waitUntil(lambda: not sc._runner.is_busy, timeout=10000)
        assert len(calls) == 2
        assert calls[-1] == selected
        assert sc.refinement_result.metadata["setting_index"] == selected
        assert sc.ranked_selection == selected
        assert not w.predicted_overlay.isVisible()
        assert len(w.predicted_overlay.getData()[0]) == 0
    finally:
        release.set()
        c.widget.close()


def test_stale_preview_after_source_change_is_rejected(
    qapp, tmp_path, ranked_experiment
):
    positions, cells, ranked = ranked_experiment
    c, sc, w = controller_scene(tmp_path, positions, cells)
    try:
        sc._show_result(ranked, sc._generation)
        old = sc.refinement_result
        generation = sc._generation
        sc.invalidate()
        sc._show_result(old, generation)
        assert sc.refinement_result is None
        assert w.rank_table_model.rowCount() == 0
    finally:
        c.widget.close()


def test_prediction_checkbox_hides_graphics_across_cell_and_frame_changes(
    qapp, tmp_path, ranked_experiment
):
    positions, cells, ranked = ranked_experiment
    c, sc, w = controller_scene(tmp_path, positions, cells)
    try:
        sc._show_result(ranked, sc._generation)
        scan = sc.refinement_result.refined_scan
        frame = int(scan.frame_indices[len(scan.frame_indices) // 2])
        w.frame_slider.setValue(frame)
        sc.plot_predictions()
        assert w.predicted_overlay.isVisible()
        assert len(w.predicted_overlay.getData()[0]) > 0
        w.prediction_enabled.setChecked(False)
        # Clearing data alone can leave cached crosses in a QGraphicsView.
        assert not w.predicted_overlay.isVisible()
        assert len(w.predicted_overlay.getData()[0]) == 0
        w.rank_table.selectRow(1)
        w.frame_slider.setValue((frame + 1) % 180)
        sc.plot_predictions()
        assert not w.predicted_overlay.isVisible()
        assert len(w.predicted_overlay.getData()[0]) == 0
        scan = sc.refinement_result.refined_scan
        w.frame_slider.setValue(int(scan.frame_indices[len(scan.frame_indices) // 2]))
        w.prediction_enabled.setChecked(True)
        assert w.predicted_overlay.isVisible()
        assert len(w.predicted_overlay.getData()[0]) > 0
        sc.invalidate()
        assert not w.predicted_overlay.isVisible()
    finally:
        c.widget.close()
