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
from dioptas.model.single_crystal_inspection import spot_cell_details


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


def test_spot_details_match_selected_setting_hkl_and_centroid_residual(
    ranked_experiment,
):
    positions, cells, ranked = ranked_experiment
    for row in ranked.comparison.ranking:
        setting = ranked.comparison.settings[row.setting_index]
        i = int(np.flatnonzero(setting.eligible)[0])
        track = int(ranked.track_ids[i])
        preview = preview_ranked_cell(
            ranked, positions, (2048, 2048), row.setting_index
        )
        for refined in (False, True):
            detail = spot_cell_details(
                positions,
                track,
                ranked=ranked,
                setting_index=row.setting_index,
                refined=refined,
            )
            assert detail.indexed is True
            assert detail.hkl == tuple(setting.hkl[i])
            assert detail.model.startswith(
                f"Rank {row.rank} · {setting.setting.symbol}"
            )
            predicted = (
                preview.refinement.predictions
                if refined
                else preview.refinement.initial_predictions
            )
            np.testing.assert_allclose(
                detail.residual,
                predicted.values[i] - ranked.observed[i],
                atol=1e-12,
                rtol=0,
            )
    sign, number = ranked.selection
    candidate = next(r[2] for r in cells.reports if r[0] == sign).candidates[number]
    i = int(np.flatnonzero(candidate.indexed)[0])
    detail = spot_cell_details(
        positions, int(cells.track_ids[i]), cells=cells, selection=ranked.selection
    )
    assert detail.indexed is True and detail.hkl == tuple(candidate.hkl[i])
    assert detail.residual is not None


def test_spot_details_distinguish_missing_assignment_and_invalid_prediction():
    from types import SimpleNamespace as Record

    # Stable track IDs need not equal row numbers in the filtered cell snapshot.
    fit = Record(
        hkl=np.array([[1, -2, 3], [4, 0, 1]]),
        eligible=np.array([True, False]),
        observed=np.array([[10.0, 20.0, -5.0], [30.0, 40.0, -4.0]]),
        predictions=Record(
            values=np.array([[10.25, 19.5, -4.9], [31.0, 42.0, -3.0]]),
            flags=np.array([0, 0]),
        ),
    )
    result = Record(
        refinement=fit, track_ids=np.array([7, 2]), metadata={"candidate_index": 0}
    )
    detail = spot_cell_details(None, 7, refinement=result)
    assert detail.hkl == (1, -2, 3) and detail.indexed is True
    np.testing.assert_allclose(detail.residual, [0.25, -0.5, 0.1], atol=1e-12, rtol=0)
    rejected = spot_cell_details(None, 2, refinement=result)
    assert (
        rejected.indexed is False and rejected.hkl is None and rejected.residual is None
    )
    excluded = spot_cell_details(None, 3, refinement=result)
    assert excluded.indexed is None and "Excluded" in excluded.note
    fit.predictions.flags[0] = 1
    invalid = spot_cell_details(None, 7, refinement=result)
    assert invalid.indexed is True and invalid.hkl == (1, -2, 3)
    assert invalid.residual is None and "No valid" in invalid.note
    assert spot_cell_details(None, 7).indexed is None


def test_position_details_refresh_when_cell_or_prediction_model_changes(
    qapp, tmp_path, ranked_experiment
):
    positions, cells, ranked = ranked_experiment
    c, sc, w = controller_scene(tmp_path, positions, cells)
    try:
        sc._show_result(ranked, sc._generation)
        eligible = np.logical_and.reduce(
            [f.eligible for f in ranked.comparison.settings]
        )
        i = int(np.flatnonzero(eligible)[0])
        track = int(ranked.track_ids[i])
        w.table_view.selectRow(track)
        assert not w.position_details.isHidden()
        assert w.position_indexing_label.text() == "Yes"
        for row in range(w.rank_table_model.rowCount()):
            w.rank_table.selectRow(row)
            fit = ranked.comparison.settings[sc.ranked_selection]
            assert w.position_hkl_label.text() == " ".join(map(str, fit.hkl[i]))
            assert "fitted" in w.position_cell_label.text()
            assert w.position_residual_label.text().startswith("Δxy ")
        w.prediction_enabled.setChecked(False)
        assert w.position_indexing_label.text() == "Yes"
        w.prediction_model.setCurrentIndex(0)
        assert "initial" in w.position_cell_label.text()
        w.table_view.clearSelection()
        assert w.position_details.isHidden()
        w.table_view.selectRow(track)
        sc.invalidate()
        assert w.position_details.isHidden()
    finally:
        c.widget.close()


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


@pytest.mark.parametrize("asynchronous", [False, True])
def test_find_cells_automatically_opens_ranked_settings(
    qapp, qtbot, tmp_path, ranked_experiment, monkeypatch, asynchronous
):
    from qtpy import QtWidgets
    from dioptas.widgets.CellSearchDialog import CellSearchDialog

    positions, cells, _ = ranked_experiment
    c, sc, w = controller_scene(tmp_path, positions, cells, asynchronous=asynchronous)
    module = importlib.import_module("dioptas.controller.SingleCrystalController")
    dialog = CellSearchDialog(w, filename="detector.poni")
    monkeypatch.setattr(dialog, "exec", lambda: QtWidgets.QDialog.Accepted)
    monkeypatch.setattr(module, "CellSearchDialog", lambda *a, **kw: dialog)
    monkeypatch.setattr(
        module,
        "geometry_from_poni",
        lambda *a, **kw: (None, cells.metadata["geometry"][0]),
    )
    monkeypatch.setattr(module, "find_cells", lambda *a, **kw: cells)
    try:
        w.cell_button.click()
        qtbot.waitUntil(
            lambda: sc.ranked_result is not None and sc.refinement_result is not None,
            timeout=15000,
        )
        assert w.cell_view.currentIndex() == 1
        assert sc.ranked_result.comparison.recommended.setting.symbol == "oP"
        assert sc._rank_after_search_generation is None
        assert sc.cell_result is cells
        sc.invalidate()
        assert sc._rank_after_search_generation is None
    finally:
        dialog.close()
        c.widget.close()


def test_failed_lattice_search_stays_visible_without_auto_ranking(
    qapp, tmp_path, ranked_experiment, monkeypatch
):
    from dataclasses import replace

    positions, cells, _ = ranked_experiment
    failed = replace(
        cells,
        reports=tuple(
            (
                sign,
                q,
                replace(
                    search,
                    candidates=tuple(
                        replace(candidate, accepted=False)
                        for candidate in search.candidates
                    ),
                ),
            )
            for sign, q, search in cells.reports
        ),
    )
    c, sc, w = controller_scene(tmp_path, positions, cells)

    def unexpected():
        pytest.fail("Failed lattices must not be automatically ranked")

    monkeypatch.setattr(sc, "compare_ranked_cells", unexpected)
    try:
        sc._rank_after_search_generation = sc._generation
        sc._show_result(failed, sc._generation)
        assert sc.ranked_result is None
        assert sc._rank_after_search_generation is None
        assert w.cell_table_model.rowCount() > 0
        assert "No passing lattice" in w.status_label.text()
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
