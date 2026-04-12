# SPDX-License-Identifier: MIT

import numpy as np
import pytest

from ...model.util.mask_plugins.threshold import ThresholdMaskPlugin
from ...model.util.mask_plugins.cosmic import CosmicRayMaskPlugin


# -- Threshold plugin tests --


class TestThresholdMaskPlugin:
    def test_mask_above(self):
        plugin = ThresholdMaskPlugin()
        plugin.above_enabled = True
        plugin.above_value = 100
        plugin.below_enabled = False

        img = np.zeros((50, 50))
        img[0, 0] = 200
        img[1, 1] = 50

        mask = plugin.compute_mask(img)
        assert mask[0, 0] == True
        assert mask[1, 1] == False

    def test_mask_below(self):
        plugin = ThresholdMaskPlugin()
        plugin.above_enabled = False
        plugin.below_enabled = True
        plugin.below_value = 10

        img = np.ones((50, 50)) * 50
        img[0, 0] = 5

        mask = plugin.compute_mask(img)
        assert mask[0, 0] == True
        assert mask[1, 1] == False

    def test_mask_both(self):
        plugin = ThresholdMaskPlugin()
        plugin.above_enabled = True
        plugin.above_value = 100
        plugin.below_enabled = True
        plugin.below_value = 10

        img = np.ones((50, 50)) * 50
        img[0, 0] = 200  # above
        img[1, 1] = 5  # below
        img[2, 2] = 50  # in range

        mask = plugin.compute_mask(img)
        assert mask[0, 0] == True
        assert mask[1, 1] == True
        assert mask[2, 2] == False

    def test_neither_enabled(self):
        plugin = ThresholdMaskPlugin()
        plugin.above_enabled = False
        plugin.below_enabled = False

        img = np.random.rand(50, 50) * 1000
        mask = plugin.compute_mask(img)
        assert not np.any(mask)

    def test_settings_roundtrip(self):
        plugin = ThresholdMaskPlugin()
        plugin.update_settings({
            "above_enabled": False,
            "above_value": 500,
            "below_enabled": True,
            "below_value": -10,
        })
        settings = plugin.get_settings()
        assert settings["above_enabled"] is False
        assert settings["above_value"] == 500
        assert settings["below_enabled"] is True
        assert settings["below_value"] == -10

    def test_has_settings(self):
        plugin = ThresholdMaskPlugin()
        assert plugin.has_settings
        assert plugin.is_dynamic


# -- Cosmic ray plugin tests --


class TestCosmicRayMaskPlugin:
    def test_detects_bright_outlier(self):
        plugin = CosmicRayMaskPlugin()
        plugin.sigma = 3.0
        plugin.min_intensity = 10.0

        # Uniform background with a single hot pixel
        img = np.ones((100, 100)) * 50.0
        img[50, 50] = 50000.0

        mask = plugin.compute_mask(img)
        assert mask[50, 50] == True
        # Most of the image should not be masked
        assert mask.sum() < 100

    def test_no_false_positives_on_uniform(self):
        plugin = CosmicRayMaskPlugin()
        plugin.sigma = 5.0
        plugin.min_intensity = 100.0

        img = np.ones((100, 100)) * 50.0
        mask = plugin.compute_mask(img)
        assert not np.any(mask)

    def test_respects_min_intensity(self):
        plugin = CosmicRayMaskPlugin()
        plugin.sigma = 3.0
        plugin.min_intensity = 1000.0

        # Hot pixel but below min_intensity threshold
        img = np.ones((100, 100)) * 50.0
        img[50, 50] = 500.0

        mask = plugin.compute_mask(img)
        assert mask[50, 50] == False

    def test_iterative_detection(self):
        plugin = CosmicRayMaskPlugin()
        plugin.sigma = 3.0
        plugin.iterations = 3
        plugin.min_intensity = 10.0

        img = np.ones((100, 100)) * 50.0
        # cluster of hot pixels
        img[50, 50] = 50000.0
        img[50, 51] = 40000.0
        img[51, 50] = 30000.0

        mask = plugin.compute_mask(img)
        assert mask[50, 50] == True
        assert mask[50, 51] == True
        assert mask[51, 50] == True

    def test_settings_roundtrip(self):
        plugin = CosmicRayMaskPlugin()
        plugin.update_settings({
            "sigma": 7.0,
            "window_size": 11,
            "iterations": 5,
            "min_intensity": 200.0,
        })
        settings = plugin.get_settings()
        assert settings["sigma"] == 7.0
        assert settings["window_size"] == 11
        assert settings["iterations"] == 5
        assert settings["min_intensity"] == 200.0

    def test_has_settings(self):
        plugin = CosmicRayMaskPlugin()
        assert plugin.has_settings
        assert plugin.is_dynamic
