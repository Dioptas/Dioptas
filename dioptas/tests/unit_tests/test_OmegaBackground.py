# SPDX-License-Identifier: MIT
"""Numerical, intensity-preservation and signed frame-export checks."""

import json
from types import SimpleNamespace

import numpy as np
from PIL import Image
import pytest
from scipy.special import expit

from dioptas.model.omega_background import (
    BackgroundCancelled,
    OmegaBackgroundTask,
    native_detector_mask,
    subtract_omega_background,
)
from dioptas.model.util import omega_background as numerical
from dioptas.model.util.omega_background import ArPLSParameters, arpls_rows


def dense_reference(y, p):
    """Literal matrix equations; no band storage or native solver calls."""
    offset = y[0]
    scale = np.max(np.abs(y - offset))
    if scale == 0:
        return y.copy()
    y = (y - offset) / scale
    d = np.diff(np.eye(len(y)), n=2, axis=0)
    penalty = p.smoothness * d.T @ d
    weights = np.ones(len(y))
    for _ in range(p.max_iterations):
        z = np.linalg.solve(np.diag(weights) + penalty, weights * y)
        residual = y - z
        negative = residual[residual < 0]
        if len(negative) < 2 or np.max(np.abs(residual)) < 1e-10:
            break
        sigma = max(float(negative.std()), 1e-8)
        new_weights = np.maximum(
            expit(
                -np.clip(
                    2 * (residual - (2 * sigma - negative.mean())) / sigma, -40, 40
                )
            ),
            1e-8,
        )
        if (
            np.linalg.norm(new_weights - weights) / np.linalg.norm(weights)
            < p.tolerance
        ):
            break
        weights = new_weights
    return z * scale + offset


@pytest.mark.parametrize("frames", [3, 5, 37, 180])
@pytest.mark.parametrize("smoothness", [0.1, 300.0, 1e4, 1e6])
def test_native_and_scipy_agree_with_dense_equations(frames, smoothness):
    rng = np.random.default_rng(640)
    rows = rng.normal(200, 3, (4, frames))
    rows[:, frames // 2] += 100
    p = ArPLSParameters(smoothness, 1e-3, 15)
    dense = np.array([dense_reference(row, p) for row in rows])
    for backend in (
        ["scipy", "native"] if numerical._omega_arpls is not None else ["scipy"]
    ):
        baseline, counts, converged = arpls_rows(rows, p, workers=2, backend=backend)
        np.testing.assert_allclose(baseline, dense, rtol=2e-7, atol=2e-5)
        assert np.all(counts <= 15)
        assert converged.dtype == bool


@pytest.mark.parametrize("backend", ["auto", "scipy"])
def test_flat_linear_negative_and_empty_traces(backend):
    rows = np.vstack([np.zeros(76), np.full(76, -15), np.linspace(-500, 1000, 76)])
    before = rows.copy()
    baseline, _, converged = arpls_rows(rows, backend=backend)
    np.testing.assert_allclose(baseline, rows, atol=2e-7)
    np.testing.assert_array_equal(before, rows)
    assert converged.all()
    assert arpls_rows(np.empty((0, 76)), backend=backend)[0].shape == (0, 76)


def test_narrow_peak_integrals_and_centroids_on_known_background():
    rng = np.random.default_rng(140250)
    x = np.arange(180)
    background = 200 + 0.15 * x
    centers = [35.0, 80.0, 145.0]
    peaks = np.array([1000 * np.exp(-0.5 * ((x - c) / 1.2) ** 2) for c in centers])
    raw = peaks + background + rng.normal(0, 1, peaks.shape)
    baseline, _, _ = arpls_rows(raw)
    corrected = raw - baseline
    for row, center in enumerate(centers):
        selection = np.abs(x - center) < 6
        np.testing.assert_allclose(
            corrected[row, selection].sum(), peaks[row, selection].sum(), rtol=0.01
        )
        centroid = (corrected[row, selection] * x[selection]).sum() / corrected[
            row, selection
        ].sum()
        assert abs(centroid - center) < 0.02
    assert np.any(corrected < 0)


def test_deterministic_workers_and_iteration_limit():
    rows = np.random.default_rng(876).normal(size=(97, 76))
    a = arpls_rows(rows, workers=1)
    b = arpls_rows(rows, workers=4)
    for left, right in zip(a, b):
        np.testing.assert_array_equal(left, right)
    _, counts, converged = arpls_rows(rows, ArPLSParameters(max_iterations=1))
    assert np.all(counts == 1)
    assert np.count_nonzero(~converged) > 0


@pytest.mark.parametrize(
    "rows",
    [
        np.zeros(3),
        np.zeros((2, 2)),
        np.array([[0, 1, np.nan]]),
        np.array([[0, 1, np.inf]]),
        np.ones((2, 5), complex),
    ],
)
def test_bad_array_rejected(rows):
    with pytest.raises(ValueError):
        arpls_rows(rows)


@pytest.mark.parametrize(
    "kwargs",
    [
        dict(smoothness=0),
        dict(smoothness=np.nan),
        dict(tolerance=1),
        dict(max_iterations=0),
        dict(max_iterations=2.5),
    ],
)
def test_bad_parameters_rejected(kwargs):
    with pytest.raises(ValueError):
        ArPLSParameters(**kwargs)


def test_fallback_and_native_boundary_validation(monkeypatch):
    extension = numerical._omega_arpls
    monkeypatch.setattr(numerical, "_omega_arpls", None)
    assert "SciPy" in numerical.backend_name()
    assert np.isfinite(arpls_rows(np.ones((2, 10)))[0]).all()
    with pytest.raises(RuntimeError):
        arpls_rows(np.ones((2, 10)), backend="native")
    if extension is not None:
        for data in (np.ones(4), np.ones((2, 2)), np.array([[1, 2, np.nan]])):
            with pytest.raises(ValueError):
                extension.baselines(data, 300.0, 0.001, 10, 1)


def make_series(tmp_path, n=12):
    rng = np.random.default_rng(55)
    stack = rng.normal(100, 1, (n, 7, 9)).astype(np.float32)
    stack[4:7, 2, 3] += 50
    files = []
    for i, frame in enumerate(stack):
        path = tmp_path / f"sample_{i + 3:03d}.tif"
        Image.fromarray(frame).save(path)
        files.append(str(path))
    bounds = np.column_stack([np.arange(n) * 0.5, np.arange(n) * 0.5 + 0.5])
    series = SimpleNamespace(
        files=tuple(files),
        frame_numbers=tuple(range(3, n + 3)),
        omega_bounds=bounds,
        angle_source="test explicit angles",
        source_records=tuple({"values": {"chi": 15.0}} for _ in files),
    )
    return series, stack


def test_export_roundtrip_signed_counts_metadata_masks_and_orientation(tmp_path):
    series, stack = make_series(tmp_path)
    mask = np.zeros(stack.shape[1:], bool)
    mask[1, 4] = True
    task = OmegaBackgroundTask(series, mask=mask, tile_pixels=13, workers=2)
    result = subtract_omega_background(task, tmp_path / "result")
    m = json.loads((result.directory / "manifest.json").read_text())
    assert "Konstantin Glazyrin" in m["credit"]
    assert m["masked_pixels"] == 1
    np.testing.assert_array_equal(m["omega_bounds"], series.omega_bounds)
    saved = []
    for i, record in enumerate(m["source_records"]):
        with Image.open(result.directory / record["corrected_file"]) as image:
            assert image.mode == "F"
            saved.append(np.array(image))
            header = json.loads(image.tag_v2[270])
            assert header["source_file"] == series.files[i]
            assert header["source_record"]["values"]["chi"] == 15.0
        text = (result.directory / (record["corrected_file"] + ".txt")).read_text()
        assert "omega0 =" in text and "omegaR =" in text
    saved = np.array(saved)
    assert np.any(saved < 0)
    np.testing.assert_array_equal(saved[:, 1, 4], stack[:, 1, 4])
    reference = arpls_rows(stack.reshape(len(stack), -1).T, task.parameters)[0]
    reference = stack - reference.T.reshape(stack.shape)
    reference[:, mask] = stack[:, mask]
    np.testing.assert_allclose(saved, reference, atol=2e-6)
    with Image.open(result.directory / "signal_sum.tif") as image:
        np.testing.assert_allclose(
            np.array(image), saved.sum(axis=0, dtype=np.float64), atol=3e-5
        )
    with Image.open(result.directory / "background_sum.tif") as image:
        background = np.array(image)
    np.testing.assert_allclose(
        background + saved.sum(axis=0), stack.sum(axis=0), atol=2e-4
    )
    assert not list(result.directory.glob("*.work"))
    from dioptas.model.rotation_series import import_series

    reopened = import_series(
        result.directory / m["source_records"][0]["corrected_file"]
    )
    np.testing.assert_array_equal(reopened.omega_bounds, series.omega_bounds)
    assert reopened.frame_numbers == series.frame_numbers
    with pytest.raises(FileExistsError):
        subtract_omega_background(task, result.directory)


def test_summary_only_and_tile_independence(tmp_path):
    series, _ = make_series(tmp_path)
    a = subtract_omega_background(
        OmegaBackgroundTask(series, tile_pixels=1), tmp_path / "a"
    )
    b = subtract_omega_background(
        OmegaBackgroundTask(series, tile_pixels=32, export_frames=False), tmp_path / "b"
    )
    assert not (b.directory / "frames").exists()
    for name in ("signal_sum.tif", "background_sum.tif"):
        with (
            Image.open(a.directory / name) as left,
            Image.open(b.directory / name) as right,
        ):
            np.testing.assert_array_equal(np.array(left), np.array(right))


@pytest.mark.parametrize(
    "cancel_stage",
    [
        "Reading frames",
        "Estimating background",
        "Exporting corrected frames",
        "Complete",
    ],
)
def test_cancellation_removes_all_partial_outputs(tmp_path, cancel_stage):
    series, _ = make_series(tmp_path)
    task = OmegaBackgroundTask(series, tile_pixels=10)
    with pytest.raises(BackgroundCancelled):
        subtract_omega_background(
            task,
            tmp_path / "cancelled",
            progress=lambda stage, done, total: stage != cancel_stage,
        )
    assert not (tmp_path / "cancelled").exists()
    assert not list(tmp_path.glob(".omega-background-*"))


def test_reject_missing_angle_step_and_mismatched_shapes(tmp_path):
    series, _ = make_series(tmp_path)
    series.omega_bounds[5:] += 0.5
    with pytest.raises(ValueError, match="uniformly spaced"):
        subtract_omega_background(OmegaBackgroundTask(series), tmp_path / "bad")
    series.omega_bounds[5:] -= 0.5
    with pytest.raises(ValueError, match="mask"):
        subtract_omega_background(
            OmegaBackgroundTask(series, mask=np.zeros((3, 4), bool)), tmp_path / "bad"
        )
    assert not list(tmp_path.glob(".omega-background-*"))


def test_mask_inverse_matches_all_display_transformations():
    from dioptas.model.ImgModel import TRANSFORMATION_FUNCTIONS
    from dioptas.model.omega_background import display_detector_mask

    raw = np.zeros((7, 9), bool)
    raw[1, 4] = True
    transforms = ("rotate_matrix_p90", "fliplr", "rotate_matrix_m90", "flipud")
    display = raw[::-1]
    for name in transforms:
        display = TRANSFORMATION_FUNCTIONS[name](display)
    np.testing.assert_array_equal(native_detector_mask(display, transforms), raw)
    np.testing.assert_array_equal(display_detector_mask(raw, transforms), display)


def test_nonfinite_pixels_are_excluded_not_used_in_baseline(tmp_path):
    series, stack = make_series(tmp_path)
    stack[4, 2, 3] = np.nan
    Image.fromarray(stack[4]).save(series.files[4])
    result = subtract_omega_background(
        OmegaBackgroundTask(series), tmp_path / "nonfinite"
    )
    assert result.metadata["masked_pixels"] == 1
    with Image.open(result.directory / "mask.tif") as image:
        assert np.array(image)[2, 3] == 1


def test_descending_angles_are_supported(tmp_path):
    series, _ = make_series(tmp_path)
    series.omega_bounds *= -1
    result = subtract_omega_background(
        OmegaBackgroundTask(series, export_frames=False), tmp_path / "descending"
    )
    assert result.metadata["omega_bounds"] == series.omega_bounds.tolist()
