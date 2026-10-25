# SPDX-License-Identifier: MIT
from dataclasses import replace

import numpy as np
import pytest

from ...model.util.mask_plugins import powder_outlier as po
from ...model.util.mask_plugins.broad_spots import broad_spot_mask
from .test_PowderOutlierMaskPlugin import _make_geometry


def scene():
    shape = (240, 280)
    y, x = np.indices(shape)
    radius = np.hypot(y - 120, x - 140)
    geometry = _make_geometry(shape)
    geometry.tth_array = radius / 300
    rng = np.random.default_rng(867)
    # A radial powder ring plus a slow azimuth-dependent illumination gradient.
    image = 600 + 150 * np.exp(-(((radius - 70) / 3) ** 2)) + x * 0.3
    image += rng.normal(0, 4, shape)
    broad = 500 * np.exp(-((x - 70) ** 2 + (y - 70) ** 2) / (2 * 10**2))
    narrow = 300 * np.exp(-((x - 210) ** 2 + (y - 170) ** 2) / (2 * 1**2))
    image += broad + narrow
    return image, geometry, broad, narrow


def plugin():
    p = po.PowderDiffSpotMaskPlugin()
    p.update_settings(dict(algorithm="broad", num_bins=100, broad_background_radius=45))
    return p


def test_broad_wings_and_narrow_sample_candidate():
    image, geometry, broad, narrow = scene()
    p = plugin()
    mask = p.compute_mask(image, geometry)
    # Known injected signal, independently defined from the detection score.
    wings = (broad > 12) & (broad < 40)
    assert mask[wings].mean() > 0.8
    assert not mask[narrow > 50].any()
    assert mask[broad < 1].mean() < 0.01
    p.broad_grow_sigma = p.broad_seed_sigma
    seed_only = p.compute_mask(image, geometry)
    assert mask[wings].sum() > seed_only[wings].sum()


@pytest.mark.parametrize(
    "transform",
    [np.flipud, np.fliplr, lambda a: np.rot90(a, 1), lambda a: np.rot90(a, -1)],
)
def test_pixel_transform_equivariance_with_missing_data(transform):
    image, geometry, _, _ = scene()
    image[:10] = 0
    image[30:35, 60:65] = np.nan
    gap = np.zeros(image.shape, bool)
    gap[20:23] = True
    reference = plugin().compute_mask(image, geometry, gap)
    transformed_geometry = replace(
        geometry,
        tth_array=transform(geometry.tth_array),
        azi_array=transform(geometry.azi_array),
    )
    actual = plugin().compute_mask(
        transform(image), transformed_geometry, transform(gap)
    )
    np.testing.assert_array_equal(actual, transform(reference))


def test_large_saturated_component_has_no_upper_size_rejection():
    image, geometry, broad, _ = scene()
    image[broad > 20] = 65535
    mask = plugin().compute_mask(image, geometry)
    assert (broad > 20).sum() > 1500
    assert mask[broad > 20].all()


def test_missing_and_masked_pixels_are_never_output_or_used_as_signal():
    image, geometry, _, _ = scene()
    image[65:75, 65:75] = np.nan
    image[70, 60] = np.inf
    image[:10] = 0
    gap = np.zeros(image.shape, bool)
    gap[40:50] = True
    image[gap] = 1e10
    geometry.tth_array[100, 100] = np.nan
    mask = plugin().compute_mask(image, geometry, gap)
    assert not mask[gap].any()
    assert not mask[~np.isfinite(image)].any()
    assert not mask[:10].any()
    assert not mask[100, 100]
    assert mask[80, 70]


@pytest.mark.parametrize("value", [0, 100, np.nan, np.inf])
def test_missing_components_and_constant_frames(value):
    image = np.full((50, 50), value)
    assert not plugin().compute_mask(image, _make_geometry(image.shape)).any()


def test_mask_gap_cannot_join_seeds_to_disconnected_wings():
    image, geometry, broad, _ = scene()
    gap = np.zeros(image.shape, bool)
    gap[:, 84:89] = True
    mask = plugin().compute_mask(image, geometry, gap)
    assert mask[70, 70]
    assert not mask[70, 95]
    assert not mask[gap].any()


def test_broad_path_independent_of_optional_native_backends(monkeypatch):
    image, geometry, _, _ = scene()
    expected = plugin().compute_mask(image, geometry)
    monkeypatch.setattr(po, "_c_compute_binned", None)
    monkeypatch.setattr(po, "_cv2", None)
    np.testing.assert_array_equal(plugin().compute_mask(image, geometry), expected)


def test_settings_round_trip_and_legacy_defaults():
    p = plugin()
    copy = po.PowderDiffSpotMaskPlugin()
    copy.update_settings(p.get_settings())
    assert copy.get_settings() == p.get_settings()
    legacy = po.PowderDiffSpotMaskPlugin()
    legacy.update_settings({"esdmul": 4.0})
    assert legacy.algorithm == "powder"
    assert legacy.esdmul == 4.0
    # Live changes may temporarily put the growth threshold above the seed.
    p.update_settings({"broad_seed_sigma": 0.5})
    image, geometry, _, _ = scene()
    assert p.compute_mask(image, geometry).dtype == bool


def test_degenerate_and_nonfinite_geometry_bins():
    geometry = np.array([[0, 0], [np.nan, np.inf]])
    np.testing.assert_array_equal(po._compute_bin_indices(geometry, 10), [0, 0, -1, -1])
    assert not broad_spot_mask(np.ones((2, 2)), np.full(4, -1), 10).any()


def test_invalid_growth_settings():
    with pytest.raises(ValueError):
        broad_spot_mask(np.ones((2, 2)), np.zeros(4, int), 1, grow_sigma=-1)


def test_width_filter_rejects_unrelated_powder_arcs_at_shadow_and_padding():
    image, geometry, broad, _ = scene()
    y, x = np.indices(image.shape)
    image[x > 140] *= 0.02
    image[np.hypot(x - 140, y - 120) > 115] = 0
    mask = plugin().compute_mask(image, geometry)
    assert mask[broad > 50].mean() > 0.95
    # A powder arc touches the broad reflection. Its overlapping/connected
    # portion may be removed too; unrelated arcs must not seed their own masks.
    far_from_peak = np.hypot(x - 70, y - 70) > 65
    assert not mask[far_from_peak].any()


def test_zero_max_growth_keeps_seeds_and_reach_is_bounded():
    from scipy.ndimage import distance_transform_edt

    image, geometry, _, _ = scene()
    p = plugin()
    p.broad_max_growth = 0
    seeds = p.compute_mask(image, geometry)
    p.broad_max_growth = 7
    grown = p.compute_mask(image, geometry)
    assert grown.sum() > seeds.sum()
    assert (distance_transform_edt(~seeds)[grown] <= 7).all()
