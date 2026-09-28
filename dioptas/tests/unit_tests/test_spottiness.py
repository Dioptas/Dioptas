# SPDX-License-Identifier: MIT
"""Population spread must not be confused with propagated intensity errors."""

from dataclasses import replace
from types import SimpleNamespace

import numpy as np
import pytest
from pyFAI.integrator.azimuthal import AzimuthalIntegrator

from dioptas.model.integration_task import IntegrationTask, PersistentIntegrationEngine
from dioptas.model.util.spottiness import (
    weighted_spread,
    integrate_spottiness,
    relative_spread,
    trim_spread,
)


@pytest.fixture
def spread_task():
    ai = AzimuthalIntegrator(
        dist=0.03,
        poni1=0.0015,
        poni2=0.0015,
        pixel1=0.0001,
        pixel2=0.0001,
        wavelength=1e-10,
    )
    image = np.random.default_rng(12).uniform(10, 100, (32, 32))
    return IntegrationTask(
        image=image,
        revision=0,
        mask=None,
        geometry_config=ai.get_config(),
        filename="frame.tif",
        unit="2th_deg",
        polarization_factor=0.8,
        correct_solid_angle=True,
        supersampling_factor=1,
        pattern_num_points=25,
        pattern_azimuth_range=None,
        trim_trailing_zeros=False,
        calculate_errors=False,
        calculate_pattern=True,
        cake_radial_points=None,
        cake_azimuth_points=36,
        cake_azimuth_range=None,
        calculate_cake=False,
        calculate_azimuthal_std=True,
        dioptrin_geometry_config=dict(
            distance=0.03,
            poni1=0.0015,
            poni2=0.0015,
            rot1=0.0,
            rot2=0.0,
            rot3=0.0,
            pixel1=0.0001,
            pixel2=0.0001,
            wavelength=1e-10,
        ),
    )


def test_population_weights_fractional_overlap_invalid_and_high_offset():
    # Bin 0 overlaps two pixels unequally; bins 1/2 have one/no valid pixel.
    lut = (
        np.array([0.5, 1.0, 1.0, 1.0, 1.0, 1.0]),
        np.array([0, 1, 2, 3, 4, 5]),
        np.array([0, 2, 3, 6]),
    )
    norm = np.array([2.0, 4.0, 1.0, 0.0, np.nan, 1.0])
    signal = np.array([(1e12 + 2) * 2, (1e12 + 7) * 4, 1e12, 50.0, 10.0, np.inf])
    mean, std = weighted_spread(lut, signal, norm)
    # w=(1,4), weighted mean offset=6, variance=(16+4)/5=4.
    np.testing.assert_allclose(mean, [1e12 + 6, 1e12, 0], rtol=0, atol=0)
    np.testing.assert_allclose(std, [2.0, 0.0, np.nan], equal_nan=True)


@pytest.mark.parametrize("sector", [None, (-70.0, 80.0)])
@pytest.mark.parametrize("solid_angle", [False, True])
def test_pyfai_spread_matches_explicit_weighted_reference(
    spread_task, sector, solid_angle
):
    task = replace(
        spread_task,
        pattern_azimuth_range=sector,
        correct_solid_angle=solid_angle,
        calculate_errors=True,
    )
    mask = np.zeros(task.image.shape, bool)
    mask[5:14, 2:17] = True
    task = replace(task, mask=mask)
    engine = PersistentIntegrationEngine()
    actual = engine.compute(task).pattern
    ai = engine.pyfai_integrator
    result = ai.integrate1d(
        task.image,
        task.pattern_num_points,
        method=("bbox", "csr", "cython"),
        unit=task.unit,
        mask=mask,
        polarization_factor=0.8,
        correctSolidAngle=solid_angle,
        azimuth_range=sector,
        error_model="poisson",
    )
    coefficients, indices, indptr = ai.engines[result.method].engine.lut
    norm = ai.polarization(task.image.shape, factor=0.8).astype(float)
    if solid_angle:
        norm *= ai.solidAngleArray(task.image.shape)
    values = (task.image / norm).ravel()
    for row in range(len(actual.intensity)):
        sl = slice(indptr[row], indptr[row + 1])
        pixels = indices[sl]
        weights = coefficients[sl] * norm.ravel()[pixels]
        if weights.sum() == 0:
            assert np.isnan(actual.azimuthal_std[row])
        else:
            mean = np.average(values[pixels], weights=weights)
            std = np.sqrt(np.average((values[pixels] - mean) ** 2, weights=weights))
            assert actual.intensity[row] == pytest.approx(mean, rel=1e-12)
            assert actual.azimuthal_std[row] == pytest.approx(std, rel=1e-12)
    np.testing.assert_allclose(actual.sigma, result.sigma)
    # Enabling spread cannot replace Poisson SEM with the much larger std.
    assert np.nanmax(actual.azimuthal_std) > np.max(actual.sigma)


def test_uniform_corrected_signal_detector_corrections_and_empty_bins():
    ai = AzimuthalIntegrator(
        dist=0.01, poni1=0.003, poni2=0.003, pixel1=0.001, pixel2=0.001
    )
    shape = (12, 12)
    ai.detector.flatfield = np.linspace(0.5, 2.0, 144).reshape(shape)
    ai.detector.darkcurrent = np.full(shape, 7.0)
    norm = (
        ai.solidAngleArray(shape)
        * ai.polarization(shape, factor=0.8)
        * ai.detector.flatfield
    )
    image = 45 * norm + ai.detector.darkcurrent
    image[0, 0] = np.nan
    kwargs = dict(unit="2th_deg", polarization_factor=0.8, correctSolidAngle=True)
    _, mean, std = integrate_spottiness(ai, image, 20, kwargs)
    np.testing.assert_allclose(mean[np.isfinite(std)], 45.0, rtol=1e-12)
    np.testing.assert_allclose(std[np.isfinite(std)], 0.0, atol=2e-14)
    _, mean, std = integrate_spottiness(
        ai, image, 20, dict(kwargs, mask=np.ones(shape, bool))
    )
    assert np.all(mean == 0)
    assert np.all(np.isnan(std))


@pytest.mark.parametrize("errors", [False, True])
def test_native_053_and_old_backend_fallback(spread_task, errors):
    dioptrin = pytest.importorskip("dioptrin")
    import inspect

    if (
        "azimuthal_std"
        not in inspect.signature(dioptrin.Integrator.integrate1d).parameters
    ):
        pytest.skip("native azimuthal spread requires Dioptrin 0.5.3")
    task = replace(
        spread_task, prefer_dioptrin=True, calculate_errors=errors, unit="d_A"
    )
    engine = PersistentIntegrationEngine()
    actual = engine.compute(task).pattern
    if engine.dioptrin_integrator is None:
        pytest.skip("Dioptrin unavailable (e.g. license)")
    direct = engine.dioptrin_integrator.integrate1d(
        task.image, 25, errors=errors, azimuthal_std=True
    )
    np.testing.assert_allclose(actual.azimuthal_std, direct.azimuthal_std)
    np.testing.assert_allclose(actual.intensity, direct.intensity)
    np.testing.assert_allclose(
        actual.radial, 1 / (2 * np.sin(np.radians(direct.radial) / 2))
    )
    assert (actual.sigma is not None) == errors

    # Old backend accepts errors but cannot calculate the independent spread.
    class Older:
        def integrate1d(self, image, n, errors=False):
            raise AssertionError("The unsupported keyword should raise TypeError first")

    for backend in engine._dioptrin_backends.values():
        backend.integrator = Older()
    fallback = engine.compute(task).pattern
    expected = (
        PersistentIntegrationEngine()
        .compute(replace(task, prefer_dioptrin=False))
        .pattern
    )
    np.testing.assert_allclose(fallback.azimuthal_std, expected.azimuthal_std)
    np.testing.assert_allclose(fallback.intensity, expected.intensity)
    if errors:
        np.testing.assert_allclose(fallback.sigma, expected.sigma)


def test_relative_and_trim_preserve_zero_means_and_missing_bins():
    mean = np.array([10.0, 0.0, -1.0, 1e-14, np.nan, np.inf])
    std = np.ones(6)
    np.testing.assert_allclose(
        relative_spread(mean, std),
        [0.1, np.nan, np.nan, np.nan, np.nan, np.nan],
        equal_nan=True,
    )
    assert relative_spread(np.empty(0), np.empty(0)).size == 0
    result = trim_spread(
        np.arange(4),
        np.array([1.0, 0.0, 0.0, 0.0]),
        np.ones(4),
        np.array([2.0, 0.0, 3.0, np.nan]),
    )
    assert len(result[0]) == 3  # final populated zero-mean bin is real data


@pytest.mark.parametrize("supersampling", [1, 2])
def test_synchronous_worker_state_export_and_mask(
    calibrated_config, tmp_path, supersampling
):
    config = calibrated_config
    config.auto_integrate_pattern = False
    config.calibration_model.use_dioptrin = False
    config.integration_rad_points = 80
    config.calibration_model.set_supersampling(supersampling)
    config.calculate_azimuthal_std = True
    config.calculate_poisson_errors = True
    config.integrate_image_1d()
    expected = config.pattern_model.azimuthal_std.copy()
    task = config.create_integration_task()
    engine = PersistentIntegrationEngine()
    result = engine.compute(task)
    np.testing.assert_allclose(result.pattern.azimuthal_std, expected, equal_nan=True)
    config.apply_integration_result(result)
    config.save_spottiness(str(tmp_path / "spread.csv"))
    config.save_pattern(str(tmp_path / "pattern.xye"))
    spread = np.loadtxt(tmp_path / "spread.csv", delimiter=",")
    xye = np.loadtxt(tmp_path / "pattern.xye")
    np.testing.assert_allclose(spread[:, 2], expected)
    np.testing.assert_allclose(xye[:, 2], config.pattern_model.errors, rtol=1e-5)
    config.calculate_azimuthal_std = False
    assert not config.apply_integration_result(
        result
    )  # stale result cannot restore disabled spread
    config.integrate_image_1d()
    assert config.pattern_model.azimuthal_std is None
    config.calculate_azimuthal_std = True
    config.use_mask = True
    config.mask_model.set_mask_data(np.ones(config.img_model.img_data.shape, bool))
    task = config.create_integration_task()
    result = engine.compute(task)
    config.apply_integration_result(result)
    assert np.all(np.isnan(config.pattern_model.azimuthal_std))
    assert np.all(config.pattern_model.pattern.y == 0)


def test_project_round_trip_and_legacy_defaults(tmp_path):
    from dioptas.model.DioptasModel import DioptasModel
    from dioptas.model.state import ConfigurationParams, params_from_dict

    model = DioptasModel()
    config = model.current_configuration
    config.auto_integrate_pattern = False
    config.calculate_azimuthal_std = True
    config.spottiness_relative = True
    config.pattern_model.set_pattern(
        np.arange(3.0),
        np.array([4.0, 0.0, 8.0]),
        unit="2th_deg",
        errors=np.ones(3),
        azimuthal_std=np.array([2.0, np.nan, 3.0]),
    )
    model.save(str(tmp_path / "spread.dio"))
    restored = DioptasModel()
    restored.load(str(tmp_path / "spread.dio"))
    assert restored.current_configuration.calculate_azimuthal_std
    assert restored.current_configuration.spottiness_relative
    np.testing.assert_allclose(
        restored.pattern_model.azimuthal_std, [2.0, np.nan, 3.0], equal_nan=True
    )
    np.testing.assert_allclose(restored.pattern_model.errors, 1.0)
    assert not params_from_dict(ConfigurationParams, {}).calculate_azimuthal_std


@pytest.mark.parametrize("backend", ["pyfai", "native", "old"])
def test_batch_worker_and_exports_use_independent_spread(
    spread_task, tmp_path, backend
):
    from PIL import Image
    from dioptas.model.Configuration import Configuration
    from dioptas.model.batch_task import (
        BatchIntegrationTask,
        compute_batch_integration,
        apply_batch_integration,
    )
    from dioptas.model.worker_configuration import capture_worker_configuration

    config = Configuration()
    config.auto_integrate_pattern = False
    ai = AzimuthalIntegrator()
    ai.set_config(spread_task.geometry_config)
    ai.save(str(tmp_path / "geometry.poni"))
    config.calibration_model.load(str(tmp_path / "geometry.poni"))
    config.calibration_model.use_dioptrin = backend != "pyfai"
    if backend != "pyfai":
        pytest.importorskip("dioptrin")
        config.calibration_model._create_dioptrin_integrator()
        if not config.calibration_model.supports_dioptrin_spottiness():
            pytest.skip("Dioptrin 0.5.3 unavailable")
    config.calculate_azimuthal_std = True
    config.integration_rad_points = 25
    config.trim_trailing_zeros = False
    config.integration_unit = "q_A^-1"
    filenames = []
    for i in range(3):
        filename = str(tmp_path / f"frame{i}.tif")
        Image.fromarray((spread_task.image * (i + 1)).astype(np.float32)).save(filename)
        filenames.append(filename)
    batch = config.batch_model
    batch.set_image_files(filenames)
    if backend == "old":
        # Only the old API is exposed; native streaming must be bypassed.
        native = config.calibration_model._dioptrin_integrator

        class Older:
            def __getattr__(self, name):
                return getattr(native, name)

            def batch1d_iter(self, images, n_points, errors=False, num_workers=None):
                raise AssertionError("Old backend must fall back")

            def integrate1d(self, image, n_points, errors=False):
                return native.integrate1d(image, n_points, errors=errors)

        config.calibration_model._dioptrin_integrator = Older()
    batch.integrate_raw_data(0, 3, 1, use_all=True)
    assert batch.azimuthal_std.shape == batch.data.shape == (3, 25)
    assert batch.integration_unit == "q_A^-1"
    np.testing.assert_allclose(
        batch.azimuthal_std[1], batch.azimuthal_std[0] * 2, rtol=1e-6
    )
    for i, filename in enumerate(filenames):
        config.img_model.load(filename)
        config.integrate_image_1d()
        np.testing.assert_allclose(
            batch.data[i], config.pattern_model.pattern.y, rtol=1e-6
        )
        np.testing.assert_allclose(
            batch.azimuthal_std[i], config.pattern_model.azimuthal_std, rtol=1e-6
        )
    batch.save_as_csv(str(tmp_path / "batch.csv"))
    table = np.loadtxt(tmp_path / "batch.csv", delimiter=",")
    assert table.shape == (75, 5)
    np.testing.assert_allclose(table[:, 3], batch.azimuthal_std.T.flatten())
    batch.save_proc_data(str(tmp_path / "batch.nxs"))
    expected = batch.azimuthal_std.copy()
    batch.reset_data()
    batch.load_proc_data(str(tmp_path / "batch.nxs"))
    np.testing.assert_allclose(batch.azimuthal_std, expected)
    assert batch.integration_unit == "q_A^-1"
    if backend == "pyfai":
        task = BatchIntegrationTask(
            capture_worker_configuration(config),
            tuple(filenames),
            batch.pos_map,
            batch.pos_map,
            0,
            3,
            1,
            True,
        )
        result = compute_batch_integration(task)
        apply_batch_integration(batch, result)
        np.testing.assert_allclose(batch.azimuthal_std, expected)
        assert batch.integration_unit == "q_A^-1"
    # Reintegrating with the option off must not retain a stale spread matrix.
    config.calculate_azimuthal_std = False
    batch.integrate_raw_data(0, 3, 1, use_all=False)
    assert batch.azimuthal_std is None


def test_each_bin_uses_its_own_origin_and_ignores_masked_outlier():
    # First image pixel is masked (absent from LUT), then bright and faint bins.
    signal = np.array([1e30, 1e20, 1e20, 1.0, 1.000002])
    lut = (np.ones(4), np.array([1, 2, 3, 4]), np.array([0, 2, 4]))
    mean, std = weighted_spread(lut, signal, np.ones(5))
    np.testing.assert_allclose(mean, [1e20, 1.000001], rtol=1e-15)
    np.testing.assert_allclose(std, [0.0, 1e-6], rtol=1e-9)


@pytest.mark.parametrize("size", [0, 1])
def test_unit_change_updates_short_patterns(size):
    from dioptas.model.Configuration import Configuration
    from dioptas.model.util.calc import convert_units

    config = Configuration()
    config.auto_integrate_pattern = False
    x = np.full(size, 10.0)
    config.pattern_model.set_pattern(x, np.ones(size), unit="2th_deg",
                                     azimuthal_std=np.ones(size))
    config.integration_unit = "q_A^-1"
    assert config.pattern_model.unit == "q_A^-1"
    np.testing.assert_allclose(config.pattern_model.pattern.original_data[0],
                              convert_units(x, config.calibration_model.wavelength,
                                            "2th_deg", "q_A^-1"))


def test_spread_supersamples_detector_corrections_and_csr_fallback(monkeypatch):
    ai = AzimuthalIntegrator(dist=.1, pixel1=.001, pixel2=.001)
    dark = np.full((4, 4), 7.)
    flat = np.arange(1., 17.).reshape(4, 4)
    mask = np.zeros((4, 4), dtype=bool)
    mask[0, 0] = True
    ai.detector.darkcurrent = dark
    ai.detector.flatfield = flat
    ai.detector.mask = mask
    image = np.repeat(np.repeat(45 * flat + dark, 2, axis=0), 2, axis=1)
    image[:2, :2] = 1e8  # masked detector pixel remains masked after expansion
    original = ai.integrate1d
    methods = []

    def unavailable_engine(*args, **kwargs):
        methods.append(kwargs["method"])
        if len(methods) == 1:
            raise NameError("configured engine unavailable")
        return original(*args, **kwargs)

    monkeypatch.setattr(ai, "integrate1d", unavailable_engine)
    result, mean, std = integrate_spottiness(
        ai, image, 8, dict(unit="2th_deg", correctSolidAngle=False))
    assert methods == [("bbox", "csr", "cython"), "csr"]
    populated = np.isfinite(std)
    np.testing.assert_allclose(mean[populated], 45.)
    np.testing.assert_allclose(std[populated], 0., atol=1e-12)
    np.testing.assert_allclose(result.intensity[populated], mean[populated], rtol=1e-6)
    np.testing.assert_array_equal(ai.detector.darkcurrent, dark)
    np.testing.assert_array_equal(ai.detector.flatfield, flat)
    np.testing.assert_array_equal(ai.detector.mask, mask)
