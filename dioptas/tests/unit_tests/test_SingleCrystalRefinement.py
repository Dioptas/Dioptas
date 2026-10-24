"""Predictions, residuals and refinement use blind inputs and invalidate together."""

import json
import numpy as np
import pytest

from .test_SingleCrystalIndexing import synthetic_tracks
from dioptas.model.rotation_series import SeriesPositions
from dioptas.model.single_crystal_indexing import find_cells
from dioptas.model.single_crystal_refinement import (
    refine_positions,
    export_refinement,
    preferred_candidate,
)
from phasesmith.experimental.indexing import IndexingOptions


@pytest.fixture(scope="module")
def experiment():
    positions, geometry, _ = synthetic_tracks()
    table = positions.table
    table.values = np.c_[
        table.observations[:, 2:5], np.zeros(len(table)), np.ones(len(table))
    ]
    table.omega_bounds = np.c_[np.arange(-90, 90.0), np.arange(-89, 91.0)]
    snapshot = dict(
        vectors=geometry.vectors.tolist(),
        wavelength_angstrom=geometry.wavelength,
        axis_sign=1,
    )
    cells = find_cells(
        positions,
        [(1, geometry, snapshot)],
        options=IndexingOptions(max_length=15, grid_size=128),
    )
    result = refine_positions(positions, cells, (2048, 2048))
    return SeriesPositions(table, positions.metadata), cells, result


def test_refinement_export_and_fixed_geometry(experiment, tmp_path):
    _, _, result = experiment
    fit = result.refinement
    assert fit.metrics["validation"]["after"]["rms_xy"] < 1e-7
    assert fit.fit_mask.sum() >= 100
    assert len(result.refined_scan.values) > 100
    assert result.metadata["fixed_instrument"] is True
    assert result.metadata["material_or_cell_priors"] is False
    files = export_refinement(result, tmp_path / "refinement.json")
    record = json.loads(files[0].read_text())
    assert record["refined_reciprocal_basis"] == fit.reciprocal_basis.tolist()
    assert "domega_refined" in files[1].read_text().splitlines()[0]
    assert "intensity" not in files[2].read_text().splitlines()[0]


def test_missing_or_failed_candidate_cannot_refine():
    from types import SimpleNamespace

    with pytest.raises(ValueError, match="candidate"):
        preferred_candidate(SimpleNamespace(reports=[]))


def test_controller_overlay_model_toggle_plots_and_invalidation(
    qapp, tmp_path, experiment
):
    from fabio.tifimage import TifImage
    from dioptas.controller.MainController import MainController

    positions, cells, result = experiment
    c = MainController(
        use_settings=False, run_async_processing=False, experimental_single_crystal=True
    )
    try:
        image = np.full((2048, 2048), 100, dtype=np.uint16)
        path = tmp_path / "unknown.tif"
        TifImage(data=image).write(str(path))
        c.model.img_model.load(str(path))
        sc, w = c.single_crystal_controller, c.widget.single_crystal_widget
        sc.result = positions
        sc.cell_result = cells
        w.frame_slider.setRange(0, 179)
        sc._show_result(result, sc._generation)
        frame = int(
            result.initial_scan.frame_indices[
                len(result.initial_scan.frame_indices) // 2
            ]
        )
        w.frame_slider.setValue(frame)
        sc.plot_predictions()
        assert len(w.predicted_overlay.getData()[0]) > 0
        assert sc.result is positions
        assert w.residual_button.isEnabled() and w.refinement_export_button.isEnabled()
        w.prediction_model.setCurrentIndex(0)
        mask = result.initial_scan.frame_indices == frame
        np.testing.assert_allclose(
            w.predicted_overlay.getData()[0], result.initial_scan.values[mask, 0] + 0.5
        )
        w.prediction_enabled.setChecked(False)
        assert len(w.predicted_overlay.getData()[0]) == 0
        w.prediction_enabled.setChecked(True)
        sc.show_refinement_residuals()
        assert len(sc._residual_dialog.plots) == 6
        for plot in sc._residual_dialog.plots:
            assert len(plot.listDataItems()) == 3
        sc.invalidate()
        assert sc.refinement_result is None and sc._residual_dialog is None
        assert (
            not w.residual_button.isEnabled()
            and not w.refinement_export_button.isEnabled()
        )
        assert len(w.predicted_overlay.getData()[0]) == 0
    finally:
        c.widget.close()


def test_stale_refinement_is_discarded(qapp, qtbot, tmp_path, experiment, monkeypatch):
    import importlib
    import threading
    from fabio.tifimage import TifImage
    from dioptas.controller.MainController import MainController

    module = importlib.import_module("dioptas.controller.SingleCrystalController")
    started, release = threading.Event(), threading.Event()
    positions, cells, result = experiment

    def delayed(*args, **kwargs):
        started.set()
        assert release.wait(10)
        return result

    monkeypatch.setattr(module, "refine_positions", delayed)
    c = MainController(
        use_settings=False, run_async_processing=True, experimental_single_crystal=True
    )
    try:
        path = tmp_path / "unknown.tif"
        TifImage(data=np.full((64, 80), 100, np.uint16)).write(str(path))
        c.model.img_model.load(str(path))
        sc, w = c.single_crystal_controller, c.widget.single_crystal_widget
        sc.result, sc.cell_result = positions, cells
        sc.refine_positions()
        qtbot.waitUntil(started.is_set, timeout=5000)
        sc.invalidate()
        release.set()
        qtbot.waitUntil(lambda: not sc._runner.is_busy, timeout=5000)
        assert sc.refinement_result is None
        assert not w.residual_button.isEnabled()
        assert len(w.predicted_overlay.getData()[0]) == 0
    finally:
        release.set()
        c.widget.close()


def test_orthorhombic_metric_service_and_ui_action(qapp, experiment, tmp_path):
    from fabio.tifimage import TifImage
    from dioptas.controller.MainController import MainController

    positions, cells, _ = experiment
    result = refine_positions(positions, cells, (2048, 2048), symmetry="orthorhombic")
    np.testing.assert_allclose(result.refinement.cell[3:], 90, atol=3e-13)
    setting = result.metadata["orthorhombic_setting"]
    assert setting["centring"] == "P" and setting["lattice_index"] == 1
    assert result.metadata["material_or_cell_priors"] is False
    record = json.loads(
        export_refinement(result, tmp_path / "orthorhombic.json")[0].read_text()
    )
    assert record["metric_constraint"] == "orthorhombic"
    assert record["orthorhombic_setting"]["transform"] == setting["transform"]
    c = MainController(
        use_settings=False, run_async_processing=False, experimental_single_crystal=True
    )
    try:
        path = tmp_path / "unknown.tif"
        TifImage(data=np.full((2048, 2048), 100, np.uint16)).write(str(path))
        c.model.img_model.load(str(path))
        sc, w = c.single_crystal_controller, c.widget.single_crystal_widget
        sc._show_result(positions, sc._generation)
        sc._show_result(cells, sc._generation)
        assert w.orthorhombic_button.isEnabled()
        assert w.sections.currentIndex() == 2
        w.orthorhombic_button.click()
        assert sc.refinement_result.metadata["metric_constraint"] == "orthorhombic"
        assert w.prediction_model.itemText(1) == "Orthorhombic model"
        assert w.sections.currentIndex() == 3
        sc.invalidate()
        assert not w.orthorhombic_button.isEnabled()
    finally:
        c.widget.close()


def test_explicit_selected_candidate_drives_refinement(experiment):
    from dataclasses import replace

    positions, cells, _ = experiment
    sign, corrected, search = cells.reports[0]
    selected = replace(
        search,
        candidates=(
            replace(search.candidates[0], accepted=False),
            search.candidates[0],
        ),
    )
    cells = replace(cells, reports=((sign, corrected, selected),))
    result = refine_positions(positions, cells, (2048, 2048), selection=(sign, 1))
    assert result.metadata["candidate_index"] == 1
    assert "explicit candidate selection" in result.metadata["selection"]
    with pytest.raises(ValueError, match="held-out"):
        refine_positions(positions, cells, (2048, 2048), selection=(sign, 0))
