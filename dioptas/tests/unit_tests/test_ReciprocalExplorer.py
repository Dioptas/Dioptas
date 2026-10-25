"""Reciprocal display preserves geometry, frozen membership and linked selection."""

from dataclasses import replace
from types import SimpleNamespace

import numpy as np
import pytest
from qtpy import QtCore

from .test_SingleCrystalCells import controller_scene
from .test_SingleCrystalRefinement import experiment
from dioptas.model.single_crystal_cells import rank_cells
from dioptas.model.reciprocal_explorer import reciprocal_snapshot
from phasesmith.experimental.reciprocal import reciprocal_vectors


@pytest.fixture(scope="module")
def reciprocal_experiment(request):
    positions, cells, _ = request.getfixturevalue("experiment")
    return positions, cells, rank_cells(positions, cells)


def test_snapshot_uses_phasesmith_vectors_and_unrounded_display_coordinates(
    reciprocal_experiment,
):
    positions, _, ranked = reciprocal_experiment
    index = ranked.comparison.recommended_setting_index
    fit = ranked.comparison.settings[index]
    snapshot = reciprocal_snapshot(positions, ranked, index)
    expected = reciprocal_vectors(
        positions.table.values[snapshot.track_ids, :3], ranked.geometry
    )
    np.testing.assert_array_equal(snapshot.track_q, expected)
    np.testing.assert_allclose(
        snapshot.track_hkl @ fit.reciprocal_basis, expected, atol=2e-13, rtol=2e-13
    )
    np.testing.assert_array_equal(
        snapshot.observation_q,
        reciprocal_vectors(positions.table.observations[:, 2:5], ranked.geometry),
    )
    np.testing.assert_array_equal(
        snapshot.status[ranked.track_ids], fit.eligible.astype(np.uint8)
    )
    assert snapshot.track_q.flags.writeable is False
    assert snapshot.observation_hkl.flags.writeable is False
    assert len(snapshot.points()[0]) == len(positions.table)
    assert (snapshot.points()[2] == -1).all()
    np.testing.assert_array_equal(
        snapshot.points(True, False)[0], snapshot.observation_q
    )


def test_snapshot_keeps_excluded_tracks_and_individual_exposures(reciprocal_experiment):
    positions, _, ranked = reciprocal_experiment
    index = ranked.comparison.recommended_setting_index
    values = np.array(positions.table.values, copy=True)
    observations = np.array(positions.table.observations, copy=True)
    values = np.vstack([values, values[-1]])
    extra = observations[-1].copy()
    extra[0] = len(values) - 1
    extra[4] += 0.1
    observations = np.vstack([observations, extra])
    values[0, 0] = np.nan
    modified = SimpleNamespace(
        table=SimpleNamespace(values=values, observations=observations)
    )
    snapshot = reciprocal_snapshot(modified, ranked, index)
    assert snapshot.omitted_tracks == 1 and 0 not in snapshot.track_ids
    assert snapshot.track_ids[-1] == len(values) - 1
    assert snapshot.status[-1] == 2
    assert len(snapshot.observation_q) == len(observations)
    assert not np.array_equal(snapshot.observation_q[-1], snapshot.observation_q[-2])
    settings = list(ranked.comparison.settings)
    settings[index] = replace(settings[index], training_score=np.inf)
    with pytest.raises(ValueError, match="valid fitted"):
        reciprocal_snapshot(
            positions,
            replace(
                ranked, comparison=replace(ranked.comparison, settings=tuple(settings))
            ),
            index,
        )


def test_reciprocal_slices_clicks_selection_modes_and_invalidation(
    qapp, qtbot, tmp_path, reciprocal_experiment
):
    positions, cells, ranked = reciprocal_experiment
    c, sc, w = controller_scene(tmp_path, positions, cells)
    try:
        sc._show_result(ranked, sc._generation)
        assert w.reciprocal_button.isEnabled()
        w.reciprocal_button.click()
        explorer = sc._reciprocal_dialog
        explorer.slice_button.click()
        dialog = explorer._slices
        assert dialog is not None and dialog.snapshot is not None
        qapp.processEvents()
        # Exercise actual graph hit testing, rather than invoking the slot.
        item = next(
            item
            for group in dialog.populations
            for item in group
            if len(item.scatter.points())
        )
        point = item.scatter.points()[0]
        track, frame = point.data()
        assert frame == -1
        pixel = dialog.graphics.mapFromScene(item.scatter.mapToScene(point.pos()))
        qtbot.mouseClick(dialog.graphics.viewport(), QtCore.Qt.LeftButton, pos=pixel)
        assert [i.row() for i in w.table_view.selectionModel().selectedRows()] == [
            track
        ]
        assert w.sections.currentWidget() is w.positions_section
        assert dialog.selected_track == track
        assert w.selected_spot_overlay.isVisible()
        w.table_view.clearSelection()
        qtbot.mouseClick(
            dialog.graphics.viewport(),
            QtCore.Qt.LeftButton,
            modifier=QtCore.Qt.ControlModifier,
            pos=pixel,
        )
        assert not w.table_view.selectionModel().selectedRows()
        pixel = dialog.graphics.mapFromScene(item.scatter.mapToScene(point.pos()))
        qtbot.mouseClick(dialog.graphics.viewport(), QtCore.Qt.LeftButton, pos=pixel)
        dialog.centre_selected.click()
        assert all(len(item.getData()[0]) for item in dialog.highlights)
        dialog.observations.setChecked(True)
        assert len(dialog._points()[0]) == len(positions.table.observations)
        point = next(
            item.scatter.points()[0]
            for group in dialog.populations
            for item in group
            if len(item.scatter.points())
        )
        track, frame = point.data()
        dialog._clicked(None, [point])
        assert w.frame_slider.value() == frame
        assert dialog.selected_track == track
        dialog.mode.setCurrentIndex(1)
        assert not dialog.grid_enabled.isEnabled()
        assert all(len(grid.getData()[0]) == 0 for grid in dialog.grids)
        dialog.centre_selected.click()
        assert all(len(item.getData()[0]) for item in dialog.highlights)
        # A different ranked setting replaces the display basis and assignments.
        w.rank_table.selectRow(1)
        assert dialog.snapshot.name.startswith("Rank 2")
        assert dialog.snapshot is not None
        sc.invalidate()
        assert dialog.snapshot is None
        assert not w.reciprocal_button.isEnabled()
        assert all(
            len(item.scatter.points()) == 0
            for group in dialog.populations
            for item in group
        )
        explorer.close()
        qtbot.waitUntil(lambda: sc._reciprocal_dialog is None, timeout=5000)
    finally:
        c.widget.close()


def test_slice_edges_are_inclusive_and_grid_is_not_reflection_data(qapp):
    from dioptas.model.reciprocal_explorer import ReciprocalSnapshot
    from dioptas.widgets.ReciprocalSliceDialog import ReciprocalSliceDialog

    coords = np.array([[0.0, 0.0, 0.125], [0.0, 1.0, -0.125], [0.0, 2.0, 0.126]])
    snapshot = ReciprocalSnapshot(
        "Boundary fixture",
        np.arange(3),
        coords,
        coords,
        np.empty(0, dtype=int),
        np.empty(0, dtype=int),
        np.empty((0, 3)),
        np.empty((0, 3)),
        np.ones(3, dtype=np.uint8),
        0,
        np.eye(3),
    )
    dialog = ReciprocalSliceDialog()
    try:
        dialog.thickness.setValue(0.25)
        dialog.set_snapshot(snapshot)
        points = dialog.populations[0][1].scatter.points()
        assert [p.data()[0] for p in points] == [0, 1]
        assert len(dialog.grids[0].getData()[0]) > 0
        bounds = dialog.plots[0].getViewBox()._data_bounds()
        np.testing.assert_array_equal(bounds, [[0.0, 0.0], [0.0, 1.0]])
        dialog.select_track(2)
        assert len(dialog.highlights[0].scatter.points()) == 0
    finally:
        dialog.close()


def test_3d_cloud_rotation_depth_picking_and_linked_observations(
    qapp, qtbot, tmp_path, reciprocal_experiment
):
    positions, cells, ranked = reciprocal_experiment
    c, sc, w = controller_scene(tmp_path, positions, cells)
    try:
        sc._show_result(ranked, sc._generation)
        w.reciprocal_button.click()
        dialog = sc._reciprocal_dialog
        cloud = dialog.canvas
        qapp.processEvents()
        assert len(cloud.coords) == len(positions.table)
        np.testing.assert_array_equal(cloud.coords, dialog.snapshot.track_q)
        before = cloud.rotation.copy()
        centre = cloud.rect().center()
        qtbot.mousePress(cloud, QtCore.Qt.LeftButton, pos=centre)
        qtbot.mouseMove(cloud, centre + QtCore.QPoint(60, 25))
        qtbot.mouseRelease(
            cloud, QtCore.Qt.LeftButton, pos=centre + QtCore.QPoint(60, 25)
        )
        assert not np.allclose(cloud.rotation, before)
        before = cloud.pan.copy()
        qtbot.mousePress(cloud, QtCore.Qt.RightButton, pos=centre)
        qtbot.mouseMove(cloud, centre + QtCore.QPoint(25, 20))
        qtbot.mouseRelease(
            cloud, QtCore.Qt.RightButton, pos=centre + QtCore.QPoint(25, 20)
        )
        np.testing.assert_allclose(cloud.pan - before, [25, 20])
        dialog.observations.setChecked(True)
        xy, _ = cloud.project(cloud.coords)
        # Pick the frontmost point under the actual raster hit position.
        pixel = QtCore.QPoint(*map(int, xy[len(xy) // 2]))
        row = cloud._pick(np.array([pixel.x(), pixel.y()]))
        track, frame = int(cloud.tracks[row]), int(cloud.frames[row])
        qtbot.mouseClick(cloud, QtCore.Qt.LeftButton, pos=pixel)
        assert [i.row() for i in w.table_view.selectionModel().selectedRows()] == [
            track
        ]
        assert w.frame_slider.value() == frame
        assert cloud.selected_track == track
        assert not dialog.grab().isNull()
        dialog.mode.setCurrentIndex(1)
        np.testing.assert_array_equal(cloud.coords, dialog.snapshot.observation_hkl)
        dialog.layers[1].setChecked(False)
        assert not (cloud.status == 1).any()
        w.rank_table.selectRow(1)
        assert dialog.snapshot.name.startswith("Rank 2")
        sc.invalidate()
        assert dialog.snapshot is None and len(cloud.coords) == 0
        dialog.close()
        qtbot.waitUntil(lambda: sc._reciprocal_dialog is None)
    finally:
        c.widget.close()


def test_3d_picking_prefers_frontmost_overlapping_point(qapp):
    from dioptas.widgets.Reciprocal3DWidget import Reciprocal3DWidget

    cloud = Reciprocal3DWidget()
    cloud.set_points(
        np.array([[0.0, 0.0, -1.0], [0.0, 0.0, 1.0]]),
        np.array([0, 1]),
        np.array([-1, -1]),
        np.array([0, 1]),
        np.eye(3),
        ("q1", "q2", "q3"),
    )
    cloud.rotation = np.eye(3)
    assert cloud._pick(np.array([cloud.width() / 2, cloud.height() / 2])) == 1
    assert cloud._pick(np.array([0.0, 0.0])) is None
    cloud.close()
