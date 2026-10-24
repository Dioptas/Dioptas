"""Geometry matches pyFAI and image transformations; blind search UI stays opt-in."""

import json
from types import SimpleNamespace

import numpy as np
import pytest
import pyFAI

from phasesmith.experimental.reciprocal import reciprocal_vectors
from phasesmith.experimental.indexing import IndexingOptions
from dioptas.model.ImgModel import TRANSFORMATION_FUNCTIONS
from dioptas.model.single_crystal_indexing import (
    geometry_from_poni,
    find_cells,
    export_cells,
    cell_summary,
)


def calibration(tmp_path):
    path = tmp_path / "detector.poni"
    path.write_text(
        "PixelSize1: 0.00008\nPixelSize2: 0.00009\n"
        "Distance: 0.2\nPoni1: 0.0012\nPoni2: 0.0020\nRot1: 0.02\n"
        "Rot2: -0.01\nRot3: 0.04\nWavelength: 4e-11\nSplineFile: None\n"
    )
    return path


@pytest.mark.parametrize(
    "transforms",
    [
        (),
        ("flipud",),
        ("fliplr",),
        ("rotate_matrix_p90",),
        ("rotate_matrix_m90",),
        ("flipud", "rotate_matrix_m90", "fliplr"),
    ],
)
@pytest.mark.parametrize("original_rows", [False, True])
def test_geometry_matches_pyfai_after_actual_image_transforms(
    tmp_path, transforms, original_rows
):
    path = calibration(tmp_path)
    yy, xx = np.indices((31, 45))
    # These coordinate images express the original calibration pixel indices.
    if original_rows:
        yy, xx = yy[::-1], xx[::-1]
    for name in transforms:
        yy, xx = TRANSFORMATION_FUNCTIONS[name](yy), TRANSFORMATION_FUNCTIONS[name](xx)
    g, meta = geometry_from_poni(
        path,
        axis_sign=-1,
        shape=yy.shape,
        original_rows=original_rows,
        transformations=transforms,
    )
    points = np.array([[0, 0, 0], [7, 9, 0], [yy.shape[1] - 1, yy.shape[0] - 1, 0.0]])
    raw_x = xx[points[:, 1].astype(int), points[:, 0].astype(int)]
    raw_y = yy[points[:, 1].astype(int), points[:, 0].astype(int)]
    ai = pyFAI.load(str(path))
    z, p1, p2 = ai.calc_pos_zyx(d1=raw_y, d2=raw_x, use_cython=False)
    ray = np.column_stack([p1, p2, z])
    expected = (ray / np.linalg.norm(ray, axis=1)[:, None] - [0, 0, 1]) / 0.4
    np.testing.assert_allclose(
        reciprocal_vectors(points, g), expected, atol=3e-14, rtol=2e-12
    )
    assert meta["calibration_sha256"] and meta["original_rows"] == original_rows


def test_poni_constructor_matches_pyfai(tmp_path):
    from phasesmith.experimental.reciprocal import PanelGeometry

    g, _ = geometry_from_poni(calibration(tmp_path), axis_sign=1, shape=(31, 45))
    independent = PanelGeometry.from_poni(
        distance=0.2,
        poni1=0.0012,
        poni2=0.0020,
        pixel1=0.00008,
        pixel2=0.00009,
        rot1=0.02,
        rot2=-0.01,
        rot3=0.04,
        wavelength=0.4,
        axis=[1, 0, 0],
    )
    np.testing.assert_allclose(g.vectors, independent.vectors, atol=3e-17, rtol=3e-12)


def test_invalid_axis_and_transform(tmp_path):
    path = calibration(tmp_path)
    with pytest.raises(ValueError, match="Axis sign"):
        geometry_from_poni(path, axis_sign=0, shape=(31, 45))
    with pytest.raises(ValueError, match="Unsupported image"):
        geometry_from_poni(
            path, axis_sign=1, shape=(31, 45), transformations=("unknown",)
        )


def synthetic_tracks():
    """Forward simulated rotating crystal spots, using independently solved Ewald crossings."""
    from phasesmith.experimental.reciprocal import PanelGeometry

    rng = np.random.default_rng(8512)
    g = PanelGeometry.from_poni(
        distance=0.2,
        poni1=0.08,
        poni2=0.08,
        pixel1=8e-5,
        pixel2=8e-5,
        wavelength=0.4,
        axis=[1, 0, 0],
    )
    basis = np.diag([4.7, 6.3, 8.1])
    rot, _ = np.linalg.qr(rng.normal(size=(3, 3)))
    q = np.array(list(np.ndindex(13, 13, 13)), float) - 6
    q = q[np.any(q, axis=1)] @ np.linalg.inv(basis @ rot).T
    samples, frames = [], []
    for vector in q:
        radius = np.hypot(vector[1], vector[2])
        target = -0.4 * np.dot(vector, vector) / 2
        if radius <= abs(target):
            continue
        phase = np.arctan2(vector[2], vector[1])
        omega = np.arcsin(target / radius) - phase
        omega = (omega + np.pi) % (2 * np.pi) - np.pi
        if not -np.pi / 2 < omega < np.pi / 2:
            continue
        c, s = np.cos(omega), np.sin(omega)
        lab = np.array(
            [vector[0], c * vector[1] - s * vector[2], s * vector[1] + c * vector[2]]
        )
        ray = np.array([0, 0, 1]) + 0.4 * lab
        x, y = (ray[[1, 0]] * 0.2 / ray[2] + 0.08) / 8e-5 - 0.5
        if 15 < x < 2030 and 15 < y < 2030:
            samples.append([x, y, np.rad2deg(omega)])
            frames.append(int(np.rad2deg(omega) + 90))
    samples, frames = np.array(samples), np.array(frames)
    order = np.argsort(frames, kind="stable")
    samples, frames = samples[order], frames[order]

    class Table(SimpleNamespace):
        def __len__(self):
            return len(samples)

        def column(self, name):
            assert name == "n_observations"
            return np.ones(len(self))

    table = Table(
        observations=np.c_[np.arange(len(samples)), frames, samples],
        flags=np.zeros(len(samples), dtype=np.uint32),
        frame_ranges=np.c_[frames, frames + 1],
    )
    return (
        SimpleNamespace(table=table, metadata={"synthetic": True}),
        g,
        np.linalg.det(basis),
    )


def test_forward_geometry_blind_cell_and_exports(tmp_path):
    positions, g, volume = synthetic_tracks()
    result = find_cells(
        positions,
        [(1, g, {"synthetic": True})],
        options=IndexingOptions(max_length=15, grid_size=128),
    )
    best = result.reports[0][2].candidates[0]
    assert best.accepted and best.validation_fraction > 0.9
    assert best.volume == pytest.approx(volume, rel=0.001)
    files = export_cells(result, tmp_path / "cells.json")
    meta = json.loads(files[0].read_text())
    assert meta["material_or_cell_priors"] is False
    assert meta["reports"][0]["candidates"][0]["accepted"]
    assert "intensity" not in files[1].read_text().splitlines()[0]
    assert "chemical identification" in cell_summary(result)
    assert not result.track_ids.flags.writeable


def test_controller_search_result_keeps_positions_and_invalidates(qapp, tmp_path):
    from dioptas.controller.MainController import MainController

    positions, g, _ = synthetic_tracks()
    result = find_cells(
        positions, [(1, g, {})], options=IndexingOptions(max_length=15, grid_size=64)
    )
    controller = MainController(
        use_settings=False, run_async_processing=False, experimental_single_crystal=True
    )
    try:
        sc = controller.single_crystal_controller
        sc.result = positions
        sc._show_result(result, sc._generation)
        assert sc.result is positions and sc.cell_result is result
        assert sc.widget.cell_export_button.isEnabled()
        sc.invalidate()
        assert sc.cell_result is None and not sc.widget.cell_export_button.isEnabled()
    finally:
        controller.widget.close()
