# SPDX-License-Identifier: MIT
import numpy as np
import pytest
from dataclasses import replace

from ...model.util.mask_plugins.diamond import DiamondSpotMaskPlugin, diamond_d_spacings
from .test_PowderOutlierMaskPlugin import _make_geometry


def test_diamond_lines_against_independent_eight_atom_structure_factor():
    fcc = np.array([[0, 0, 0], [0, 0.5, 0.5], [0.5, 0, 0.5], [0.5, 0.5, 0]])
    atoms = np.vstack([fcc, fcc + 0.25])
    expected = set()
    for h in range(7):
        for k in range(7):
            for l in range(7):
                n = h * h + k * k + l * l
                if 0 < n <= 36:
                    f = np.exp(2j * np.pi * (atoms @ [h, k, l])).sum()
                    if abs(f) > 1e-8:
                        expected.add(n)
    spacings = diamond_d_spacings(3.567, 3.567 / 6)
    actual = set(np.rint((3.567 / spacings) ** 2).astype(int))
    assert actual == expected
    assert {3, 8, 11, 16, 19, 24, 27, 32} <= actual
    assert not {4, 12, 20} & actual  # 200, 222, 420


def scene():
    shape = (220, 280)
    y, x = np.indices(shape)
    wavelength = 0.31e-10
    center = 2 * np.arcsin(0.31 / (2 * (3.567 / 4)))
    geometry = replace(
        _make_geometry(shape),
        wavelength=wavelength,
        tth_array=center + (x - 70) * 0.0002,
    )
    first = 1000 * np.exp(-((x - 70) ** 2 + (y - 70) ** 2) / (2 * 8**2))
    second = 1000 * np.exp(-((x - 210) ** 2 + (y - 150) ** 2) / (2 * 8**2))
    image = 600 + np.random.default_rng(99).normal(0, 4, shape) + first + second
    p = DiamondSpotMaskPlugin()
    p.update_settings(
        dict(d_tolerance_percent=0.5, broad_background_radius=40, num_bins=100)
    )
    return p, image, geometry, first, second


def test_prior_selects_spots_not_complete_rings_and_allows_wings_outside_band():
    p, image, geometry, first, second = scene()
    mask = p.compute_mask(image, geometry)
    assert mask[first > 20].mean() > 0.95
    assert not mask[second > 20].any()
    assert not mask[180:200, 68:72].any()  # same d, no spot
    low, high = p._seed_ranges(geometry)[0]
    assert np.any(mask & ((geometry.tth_array < low) | (geometry.tth_array > high)))


@pytest.mark.parametrize("transform", [np.flipud, np.fliplr, np.rot90])
def test_diamond_prior_transforms_with_geometry(transform):
    p, image, geometry, _, _ = scene()
    expected = p.compute_mask(image, geometry)
    g = replace(
        geometry,
        tth_array=transform(geometry.tth_array),
        azi_array=transform(geometry.azi_array),
    )
    np.testing.assert_array_equal(
        p.compute_mask(transform(image), g), transform(expected)
    )


def test_settings_round_trip_and_missing_geometry():
    p, image, geometry, _, _ = scene()
    other = DiamondSpotMaskPlugin()
    other.update_settings(p.get_settings())
    assert other.get_settings() == p.get_settings()
    assert not p.compute_mask(image, None).any()
    other.lattice_a = 4.5
    assert not other.compute_mask(image, geometry).any()


def test_no_matching_diamond_line_or_invalid_wavelength():
    p, image, geometry, _, _ = scene()
    g = replace(geometry, tth_array=geometry.tth_array * 0.1)
    assert not p.compute_mask(image, g).any()
    with pytest.raises(ValueError, match="wavelength"):
        p.compute_mask(image, replace(geometry, wavelength=0))


def test_sample_spot_overlapping_diamond_is_excluded_but_same_ring_elsewhere_is_kept():
    p, image, geometry, _, _ = scene()
    y, x = np.indices(image.shape)
    overlapping_sample = 200 * np.exp(-((x - 72) ** 2 + (y - 75) ** 2) / 2)
    separate_sample = 200 * np.exp(-((x - 70) ** 2 + (y - 180) ** 2) / 2)
    mask = p.compute_mask(image + overlapping_sample + separate_sample, geometry)
    assert mask[75, 72]
    assert not mask[180, 70]
