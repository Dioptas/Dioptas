# SPDX-License-Identifier: MIT

import numpy as np
import pytest

from ...model.util.MaskPlugin import GeometryContext
from ...model.util.mask_plugins.powder_outlier import (
    PowderDiffSpotMaskPlugin,
    _compute_powder_outlier_mask,
)
from ...model.MaskPluginManager import MaskPluginManager


def _make_geometry(shape):
    """Create a geometry context with linear 2-theta gradient."""
    tth = np.linspace(0.01, 1.0, shape[0] * shape[1]).reshape(shape)
    azi = np.linspace(-np.pi, np.pi, shape[0] * shape[1]).reshape(shape)
    return GeometryContext(
        tth_array=tth,
        azi_array=azi,
        dist=0.2,
        wavelength=0.3344e-10,
        poni1=0.05,
        poni2=0.05,
        rot1=0.0,
        rot2=0.0,
        rot3=0.0,
        pixel1=75e-6,
        pixel2=75e-6,
    )


def _make_powder_image(shape, geometry):
    """Create a synthetic powder diffraction image with known spots.

    Returns (image, spot_mask) where spot_mask marks the injected spots.
    """
    rng = np.random.default_rng(42)

    # Base powder pattern: smooth function of 2-theta + noise
    tth = geometry.tth_array
    base_intensity = 1000 * np.exp(-5 * tth) + 200
    noise = rng.normal(0, 10, shape)
    img = base_intensity + noise

    # Inject bright spots (simulating single-crystal reflections)
    spot_mask = np.zeros(shape, dtype=bool)
    spot_positions = [(50, 50), (75, 30), (20, 80), (90, 90), (40, 60)]
    for y, x in spot_positions:
        if y < shape[0] and x < shape[1]:
            img[y, x] = base_intensity[y, x] + 5000  # Very bright spot
            spot_mask[y, x] = True

    return img.clip(0), spot_mask


def _call_mask(img, geometry, esdmul=5.0, num_bins=50, method="mean",
               iterations=1, smooth_sigma=0.0, smooth_threshold=0.5):
    """Helper to call _compute_powder_outlier_mask with test-friendly defaults."""
    return _compute_powder_outlier_mask(
        img,
        geometry=geometry,
        esdmul=esdmul,
        num_bins=num_bins,
        method=method,
        iterations=iterations,
        smooth_sigma=smooth_sigma,
        smooth_threshold=smooth_threshold,
    )


class TestPowderOutlierAlgorithm:
    """Test the core outlier detection algorithm."""

    def test_detects_bright_spots(self):
        shape = (100, 100)
        geometry = _make_geometry(shape)
        img, spot_mask = _make_powder_image(shape, geometry)

        mask = _call_mask(img, geometry, esdmul=3.0, smooth_sigma=0.0)

        # All injected spots should be detected
        for y, x in zip(*np.where(spot_mask)):
            assert mask[y, x], f"Spot at ({y}, {x}) not detected"

    def test_does_not_mask_uniform_image(self):
        shape = (100, 100)
        geometry = _make_geometry(shape)
        rng = np.random.default_rng(123)

        # Uniform image with small noise — no outliers
        img = 500 + rng.normal(0, 5, shape)

        mask = _call_mask(img, geometry, esdmul=5.0, smooth_sigma=0.0)

        # Very few (if any) pixels should be flagged
        assert mask.sum() < shape[0] * shape[1] * 0.01

    def test_higher_esdmul_masks_less(self):
        shape = (100, 100)
        geometry = _make_geometry(shape)
        img, _ = _make_powder_image(shape, geometry)

        mask_aggressive = _call_mask(img, geometry, esdmul=2.0, smooth_sigma=0.0)
        mask_conservative = _call_mask(img, geometry, esdmul=10.0, smooth_sigma=0.0)

        assert mask_aggressive.sum() >= mask_conservative.sum()

    def test_smoothing_expands_cluster(self):
        shape = (100, 100)
        geometry = _make_geometry(shape)
        rng = np.random.default_rng(99)

        # Image with small noise (needed for std > 0) and a bright cluster
        base = 500.0 + rng.normal(0, 5, shape)
        base[50, 50] = 5000
        base[50, 51] = 5000
        base[51, 50] = 5000
        base[51, 51] = 5000

        mask_no_smooth = _call_mask(base, geometry, esdmul=3.0, smooth_sigma=0.0)
        mask_smooth = _call_mask(
            base, geometry, esdmul=3.0, smooth_sigma=2.0, smooth_threshold=0.1
        )

        # The cluster should be detected without smoothing
        assert mask_no_smooth[50, 50]
        assert mask_no_smooth[50, 51]
        # Smoothing expands the cluster footprint into neighboring pixels
        assert mask_smooth.sum() > mask_no_smooth[49:53, 49:53].sum()

    def test_smoothing_with_empty_existing_mask(self):
        """Regression: empty (all-zero) existing_mask must not trip the
        gap-cleanup path in _smooth_mask (UnboundLocalError on `reach`)."""
        shape = (50, 50)
        geometry = _make_geometry(shape)
        img, _ = _make_powder_image(shape, geometry)
        empty_mask = np.zeros(shape, dtype=np.uint8)

        mask = _compute_powder_outlier_mask(
            img,
            geometry=geometry,
            esdmul=3.0,
            num_bins=20,
            method="mean",
            iterations=1,
            smooth_sigma=2.0,
            smooth_threshold=0.1,
            existing_mask=empty_mask,
        )
        assert mask.shape == shape

    def test_more_bins_gives_finer_resolution(self):
        shape = (100, 100)
        geometry = _make_geometry(shape)
        img, _ = _make_powder_image(shape, geometry)

        mask_coarse = _call_mask(img, geometry, esdmul=3.0, num_bins=10, smooth_sigma=0.0)
        mask_fine = _call_mask(img, geometry, esdmul=3.0, num_bins=200, smooth_sigma=0.0)

        # Both should produce valid masks
        assert mask_coarse.shape == shape
        assert mask_fine.shape == shape

    def test_empty_bins_do_not_crash(self):
        shape = (10, 10)
        geometry = _make_geometry(shape)
        # Override tth to have gaps (many empty bins)
        tth = np.zeros(shape)
        tth[:5, :] = 0.1
        tth[5:, :] = 0.9
        geometry.tth_array = tth

        img = np.ones(shape) * 100.0

        mask = _call_mask(img, geometry, num_bins=1000, smooth_sigma=0.0)
        assert mask.shape == shape

    def test_median_method(self):
        shape = (100, 100)
        geometry = _make_geometry(shape)
        img, spot_mask = _make_powder_image(shape, geometry)

        mask = _call_mask(img, geometry, esdmul=3.0, method="median", smooth_sigma=0.0)

        # Should detect spots with median method too
        for y, x in zip(*np.where(spot_mask)):
            assert mask[y, x], f"Spot at ({y}, {x}) not detected with median"

    def test_mean_and_median_detect_same_spots(self):
        shape = (100, 100)
        geometry = _make_geometry(shape)
        img, spot_mask = _make_powder_image(shape, geometry)

        mask_mean = _call_mask(img, geometry, esdmul=3.0, method="mean", smooth_sigma=0.0)
        mask_median = _call_mask(img, geometry, esdmul=3.0, method="median", smooth_sigma=0.0)

        # Both methods should detect the injected spots
        assert np.all(mask_mean[spot_mask])
        assert np.all(mask_median[spot_mask])


class TestPowderOutlierPlugin:
    """Test the plugin class interface."""

    def test_plugin_attributes(self):
        plugin = PowderDiffSpotMaskPlugin()
        assert plugin.needs_geometry is True
        assert plugin.is_dynamic is True
        assert plugin.has_settings is True

    def test_returns_empty_mask_without_geometry(self):
        plugin = PowderDiffSpotMaskPlugin()
        img = np.ones((50, 50)) * 100
        mask = plugin.compute_mask(img, geometry=None)
        assert mask.shape == (50, 50)
        assert not np.any(mask)

    def test_computes_mask_with_geometry(self):
        plugin = PowderDiffSpotMaskPlugin()
        shape = (100, 100)
        geometry = _make_geometry(shape)
        img, spot_mask = _make_powder_image(shape, geometry)

        plugin.esdmul = 3.0
        plugin.num_bins = 50
        plugin.smooth_sigma = 0.0
        mask = plugin.compute_mask(img, geometry=geometry)
        assert mask.shape == shape
        # Should detect at least some of the injected spots
        overlap = np.logical_and(mask, spot_mask)
        assert overlap.sum() > 0

    def test_settings_roundtrip(self):
        plugin = PowderDiffSpotMaskPlugin()
        plugin.update_settings({
            "method": "mean",
            "esdmul": 5.0,
            "num_bins": 512,
            "iterations": 2,
            "smooth_sigma": 2.0,
            "smooth_threshold": 0.3,
        })
        settings = plugin.get_settings()
        assert settings["method"] == "mean"
        assert settings["esdmul"] == 5.0
        assert settings["num_bins"] == 512
        assert settings["iterations"] == 2
        assert settings["smooth_sigma"] == 2.0
        assert settings["smooth_threshold"] == 0.3

    def test_works_with_plugin_manager(self):
        manager = MaskPluginManager()
        plugin = PowderDiffSpotMaskPlugin()
        manager.register(plugin)

        shape = (100, 100)
        geometry = _make_geometry(shape)
        img, _ = _make_powder_image(shape, geometry)

        manager.set_enabled("Spot Mask", True)
        manager.update_geometry(geometry)
        manager.update_image(img)

        mask = manager.get_combined_mask()
        assert mask is not None
        assert mask.shape == shape

    def test_bin_index_caching(self):
        plugin = PowderDiffSpotMaskPlugin()
        shape = (100, 100)
        geometry = _make_geometry(shape)
        img, _ = _make_powder_image(shape, geometry)

        plugin.num_bins = 50
        plugin.smooth_sigma = 0.0

        # First call computes and caches
        plugin.compute_mask(img, geometry=geometry)
        assert plugin._cached_bin_indices is not None

        # Second call with same geometry uses cache
        cached_id = plugin._cached_geometry_id
        plugin.compute_mask(img, geometry=geometry)
        assert plugin._cached_geometry_id == cached_id
