# SPDX-License-Identifier: MIT
"""Native experiment: spatial selectivity, missing data and buffer lifetime."""
from dataclasses import replace

import numpy as np
import pytest

from ...model.util.mask_plugins import diamond_roi
from .test_DiamondSpotMask import scene


@pytest.fixture
def detector_scene():
    if diamond_roi.native is None:
        pytest.fail("Build the native ROI extension before running these tests")
    _, image, geometry, first, second = scene()
    detector = diamond_roi.DiamondROIDetector(
        geometry, background_radius=40, d_tolerance_percent=0.5
    )
    return detector, image, geometry, first, second


def test_spatial_prior_and_overlapping_reflection(detector_scene):
    detector, image, _, first, second = detector_scene
    y, x = np.indices(image.shape)
    overlap = 500 * np.exp(-((x - 72)**2 + (y - 75)**2) / 2)
    separate = 500 * np.exp(-((x - 70)**2 + (y - 180)**2) / 2)
    mask = detector.compute_mask(image + overlap + separate)
    assert mask[first > 20].mean() > 0.95
    assert not mask[second > 20].any()
    assert mask[75, 72]
    assert not mask[180, 70]
    assert not mask[180:200, 68:72].any()


def test_owned_output_fresh_discovery_and_input_unchanged(detector_scene):
    detector, image, _, _, _ = detector_scene
    original = image.copy()
    mask = detector.compute_mask(image)
    saved = mask.copy()
    assert mask.flags.owndata
    assert not detector.compute_mask(np.zeros_like(image)).any()
    np.testing.assert_array_equal(mask, saved)
    np.testing.assert_array_equal(image, original)
    np.testing.assert_array_equal(detector.compute_mask(image), mask)


def test_invalid_pixels_and_user_mask_are_excluded(detector_scene):
    detector, image, _, _, _ = detector_scene
    image[68:72, 88:105] = np.nan
    image[76:80, 88:105] = 0
    existing = np.zeros(image.shape, bool)
    existing[60:65, 88:105] = True
    mask = detector.compute_mask(image, existing)
    assert mask.any()
    assert not mask[~np.isfinite(image) | (image == 0) | existing].any()
    for value in [0, np.nan, np.inf, 600]:
        assert not detector.compute_mask(np.full_like(image, value)).any()


@pytest.mark.parametrize("dtype", [np.uint16, np.uint32, np.int32, np.float32, np.float64])
def test_supported_types_and_negative_strides(detector_scene, dtype):
    detector, image, _, _, _ = detector_scene
    image = np.rint(image).astype(dtype)
    expected = detector.compute_mask(image)
    # Identical logical image in a view with two negative strides.
    view = image[::-1, ::-1].copy()[::-1, ::-1]
    mask = np.zeros(image.shape, bool)[::-1, ::-1]
    np.testing.assert_array_equal(detector.compute_mask(view, mask), expected)
    mask[60:65, 88:105] = True
    expected_masked = detector.compute_mask(image, mask.copy())
    np.testing.assert_array_equal(detector.compute_mask(view, mask), expected_masked)


@pytest.mark.parametrize("shape", [(1, 1), (7, 9), (17, 25), (79, 133), (129, 97)])
def test_partial_tiles_agree_with_generic_stride_path(detector_scene, shape):
    _, _, geometry, _, _ = detector_scene
    y, x = np.indices(shape)
    image = np.random.default_rng(345).integers(100, 120, shape, dtype=np.uint16)
    image = image + (5000*np.exp(-((x-shape[1]/2)**2+(y-shape[0]/2)**2)/200)).astype(np.uint16)
    geometry = replace(geometry, tth_array=np.full(shape, geometry.tth_array[70,70]))
    detector = diamond_roi.DiamondROIDetector(geometry, background_radius=40, min_seed_radius=2)
    expected = detector.compute_mask(image)
    view = image[:, ::-1].copy()[:, ::-1]
    np.testing.assert_array_equal(detector.compute_mask(view), expected)


@pytest.mark.parametrize("transform", [np.flipud, np.fliplr, np.rot90])
def test_array_transforms_with_geometry(detector_scene, transform):
    _, image, geometry, _, _ = detector_scene
    # A whole number of coarse blocks gives symmetric discovery under transforms.
    image = image[:216]
    geometry = replace(geometry, tth_array=geometry.tth_array[:216])
    expected = diamond_roi.DiamondROIDetector(
        geometry, background_radius=40, d_tolerance_percent=0.5
    ).compute_mask(image)
    transformed = replace(geometry, tth_array=transform(geometry.tth_array))
    result = diamond_roi.DiamondROIDetector(
        transformed, background_radius=40, d_tolerance_percent=0.5
    ).compute_mask(transform(image))
    np.testing.assert_array_equal(result, transform(expected))


def test_saturated_clipped_spot_and_illumination_step(detector_scene):
    _, image, geometry, _, _ = detector_scene
    y, x = np.indices(image.shape)
    # Make the prior uniform to ensure the spatial test rejects the step itself.
    geometry = replace(geometry, tth_array=np.full(image.shape, geometry.tth_array[70,70]))
    detector = diamond_roi.DiamondROIDetector(geometry, background_radius=40)
    rng = np.random.default_rng(10)
    step = 100 + 200 * (x > 140) + rng.normal(0, 2, image.shape)
    assert not detector.compute_mask(step).any()
    peak = np.minimum(100000 * np.exp(-((x - 5)**2 + (y - 75)**2)/(2*12**2)), 65535)
    mask = detector.compute_mask(step + peak)
    assert mask[peak > 1000].mean() > 0.95
    assert not mask[:, 135:150].any()


def test_work_limit_raises_instead_of_returning_partial_mask(detector_scene):
    _, image, geometry, _, _ = detector_scene
    detector = diamond_roi.DiamondROIDetector(
        geometry, background_radius=40, d_tolerance_percent=0.5,
        max_window_pixels=100,
    )
    with pytest.raises(RuntimeError, match="no complete mask"):
        detector.compute_mask(image)
    assert not detector.compute_mask(np.zeros_like(image)).any()


def test_invalid_input_and_settings(detector_scene):
    detector, image, geometry, _, _ = detector_scene
    for bad in [image[0], image[:-1], image.astype(np.uint8), image.astype('>f8')]:
        with pytest.raises(ValueError, match="Expected aligned"):
            detector.compute_mask(bad)
    with pytest.raises(ValueError, match="Mask shape"):
        detector.compute_mask(image, np.zeros((1, 1), bool))
    for settings in [dict(block=0), dict(max_growth=255), dict(max_window_pixels=0),
                     dict(wing_contrast=6), dict(seed_contrast=np.nan)]:
        with pytest.raises(ValueError):
            diamond_roi.DiamondROIDetector(geometry, **settings)


def test_native_unavailable_is_explicit(monkeypatch, detector_scene):
    _, _, geometry, _, _ = detector_scene
    monkeypatch.setattr(diamond_roi, "native", None)
    with pytest.raises(RuntimeError, match="unavailable"):
        diamond_roi.DiamondROIDetector(geometry)


def test_over_budget_result_is_not_returned(monkeypatch, detector_scene):
    detector, image, _, _, _ = detector_scene
    times = iter([0, 10_000_000])
    monkeypatch.setattr(diamond_roi, "perf_counter_ns", lambda: next(times))
    with pytest.raises(RuntimeError, match="exceeded 10 ms.*no mask returned"):
        detector.compute_mask(image)


def test_bright_narrow_peak_does_not_become_broad_after_pooling(detector_scene):
    detector, image, _, first, second = detector_scene
    y, x = np.indices(image.shape)
    background = image - first - second
    narrow = 60000 * np.exp(-((x-70)**2+(y-70)**2)/(2*2**2))
    assert not detector.compute_mask(background + narrow).any()


def test_gap_through_entire_core_can_prevent_width_confirmation(detector_scene):
    detector, image, _, _, _ = detector_scene
    image[68:72,60:80] = np.nan
    image[76:80,60:80] = 0
    existing = np.zeros(image.shape, bool)
    existing[60:65,60:80] = True
    # Intentionally conservative: no unbroken broad interior remains. No filling
    # of missing detector counts or invented width evidence is allowed.
    assert not detector.compute_mask(image, existing).any()
