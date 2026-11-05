# SPDX-License-Identifier: MIT
"""Real-fixture regressions for the optional published backend.

Run with ``DIOPTAS_REQUIRE_DIOPTRIN=1`` to fail rather than skip without a
working backend. DIOPTAS_DIOPTRIN_RECORD optionally records numerical arrays
for comparison across installed releases (with identical arithmetic settings).
"""

import inspect
import os
from pathlib import Path
from types import SimpleNamespace

import fabio
import numpy as np
import pytest

from dioptas.model.Configuration import Configuration
from dioptas.model.integration_task import PersistentIntegrationEngine
from dioptas.model.util.integration import iter_frames_sequential


DATA = Path(__file__).parents[1] / "data"
NPOINTS = 256
NAZIMUTH = 36


def same(actual, expected):
    """Also check the bits: allclose can hide stale buffers and rounding drift."""
    actual, expected = np.asarray(actual), np.asarray(expected)
    np.testing.assert_array_equal(actual, expected)
    assert actual.dtype == expected.dtype
    assert actual.tobytes() == expected.tobytes()


def equivalent_cake(actual, expected):
    # Pixel-split 2D tables can change summation order when rebuilt, including
    # when the live integrator switches between q patterns and 2theta cakes.
    # Reproduced with 0.6.1 as well as 0.7.0; allow only float64 rounding noise.
    assert np.asarray(actual).dtype == np.asarray(expected).dtype
    np.testing.assert_allclose(actual, expected,
                               rtol=50 * np.finfo(np.float64).eps, atol=0)


def record(key, **arrays):
    destination = os.environ.get("DIOPTAS_DIOPTRIN_RECORD")
    if destination:
        destination = Path(destination)
        destination.mkdir(parents=True, exist_ok=True)
        np.savez(destination / f"{key}.npz", **arrays)


@pytest.fixture(params=[False, True], ids=["strict", "fast"])
def native(request, monkeypatch):
    try:
        import dioptrin
    except ImportError:
        if os.environ.get("DIOPTAS_REQUIRE_DIOPTRIN"):
            pytest.fail("A working Dioptrin install is required")
        pytest.skip("Optional Dioptrin is not installed")
    try:
        dioptrin.validate_license()
    except dioptrin.LicenseError as exc:
        if os.environ.get("DIOPTAS_REQUIRE_DIOPTRIN"):
            pytest.fail(f"A working Dioptrin install is required: {exc}")
        pytest.skip(f"Optional Dioptrin unavailable: {exc}")
    original = dioptrin.Integrator
    supports_fast = "fast_math" in inspect.signature(original.from_poni_dict).parameters
    if request.param and not supports_fast:
        pytest.skip("This older reference release has no fast arithmetic")
    created = []

    def factory(*args, **kwargs):
        if supports_fast:
            kwargs["fast_math"] = request.param
        integrator = original.from_poni_dict(*args, **kwargs)
        created.append(integrator)
        return integrator

    # Exercise the application's real constructor and native operations. Only
    # select arithmetic here; production keeps the published default.
    monkeypatch.setattr(dioptrin, "Integrator", SimpleNamespace(from_poni_dict=factory))
    return SimpleNamespace(factory=factory, created=created, fast=request.param)


@pytest.fixture(params=["pilatus", "marccd"])
def real_config(request, native):
    if request.param == "pilatus":
        poni = "CeO2_Pilatus1M.poni"
        files = ["map/Fe3O4C_M1_map_1_P1_E1_001.tif",
                 "map/Fe3O4C_M1_map_2_P1_E1_001.tif"]
    else:
        poni = "LaB6_40keV_MarCCD.poni"
        files = ["image_001.tif", "image_002.tif"]
    config = Configuration()
    config.auto_integrate_pattern = False
    config.calibration_model.load(str(DATA / poni))
    paths = [str(DATA / filename) for filename in files]
    config.img_model.load(paths[0])
    cal = config.calibration_model
    cal.use_dioptrin = True
    cal._create_dioptrin_integrator()
    assert cal._dioptrin_integrator is not None
    config.integration_rad_points = NPOINTS
    config.cake_azimuth_points = NAZIMUTH
    config.trim_trailing_zeros = False
    config.use_mask = True
    if request.param == "marccd":
        config.mask_model.load_mask(str(DATA / "test.mask"))
    else:
        mask = np.zeros(config.img_model.img_data.shape, dtype=bool)
        mask[200:260, 300:420] = True
        config.mask_model.set_mask_data(mask)
    return config, paths, request.param


@pytest.mark.parametrize("supersampling", [1, 2], ids=["pixel_split", "supersampled"])
@pytest.mark.parametrize("unit", ["2th_deg", "q_A^-1", "q_nm^-1", "d_A"])
def test_real_images_synchronous_and_persistent_abab(real_config, native, supersampling, unit):
    config, paths, detector = real_config
    cal = config.calibration_model
    cal.set_supersampling(supersampling)
    cal.polarization_factor = 0.93
    config.integration_unit = unit
    config.calculate_poisson_errors = True
    # A real background fixture and scalar image correction traverse ImgModel
    # before either integration backend sees an image.
    config.img_model.load_background(paths[0])
    config.img_model.params.background_scaling = 0.02
    config.img_model.factor = 1.25
    engine = PersistentIntegrationEngine()
    snapshots = []
    worker_snapshots = []
    held_workers = []
    for i, path in enumerate(paths * 2):
        config.img_model.load(path)
        mask = config.mask_model.get_mask()
        x, y = cal.integrate_1d(num_points=NPOINTS, unit=unit, mask=mask,
                                calculate_errors=True, trim_zeros=False)
        sigma = cal.sigma.copy()
        cake = cal.integrate_2d(mask=mask, rad_points=NPOINTS, azimuth_points=NAZIMUTH)
        task = config.create_integration_task(calculate_pattern=True, calculate_cake=True)
        result = engine.compute(task)
        assert engine.dioptrin_integrator is not None
        same(result.pattern.radial, x)
        same(result.pattern.intensity, y)
        same(result.pattern.sigma, sigma)
        equivalent_cake(result.cake.intensity, cake)
        same(result.cake.radial, cal.cake_tth)
        same(result.cake.azimuthal, cal.cake_azi)
        arrays = dict(radial=x, intensity=y, sigma=sigma, cake=cake,
                      cake_radial=cal.cake_tth, cake_azimuthal=cal.cake_azi)
        # Copies make a later mutation of an earlier returned buffer visible.
        snapshots.append({key: value.copy() for key, value in arrays.items()})
        worker = dict(radial=result.pattern.radial, intensity=result.pattern.intensity,
                      sigma=result.pattern.sigma, cake=result.cake.intensity,
                      cake_radial=result.cake.radial, cake_azimuthal=result.cake.azimuthal)
        worker_snapshots.append({key: value.copy() for key, value in worker.items()})
        held_workers.append(worker)
        if i >= 2:
            for key, value in arrays.items():
                compare = equivalent_cake if key == "cake" else same
                compare(value, snapshots[i - 2][key])
            # The persistent engine retains its tables: ABAB must be bitwise
            # identical, and later calls must not mutate earlier results.
            for key, value in worker.items():
                same(value, worker_snapshots[i - 2][key])
        record(f"model-{detector}-{native.fast}-{supersampling}-{unit}-{i}", **arrays)
    assert not np.array_equal(snapshots[0]["intensity"], snapshots[1]["intensity"])
    # One synchronous integrator and one persistent integrator per output unit.
    assert len(engine._dioptrin_backends) == (1 if unit in ("2th_deg", "d_A") else 2)
    engine.close()
    for worker, snapshot in zip(held_workers, worker_snapshots):
        for key, value in worker.items():
            same(value, snapshot[key])


@pytest.mark.parametrize("supersampling", [1, 2], ids=["pixel_split", "supersampled"])
@pytest.mark.parametrize("errors", [False, True], ids=["intensity", "poisson"])
def test_real_file_and_array_batches_abab(real_config, native, supersampling, errors):
    config, paths, detector = real_config
    cal = config.calibration_model
    cal.set_supersampling(supersampling)
    cal.polarization_factor = 0.93
    n = cal.sync_dioptrin_for_batch(config.mask_model.get_mask(), "2th_deg", NPOINTS,
                                   config.img_model.img_data.shape)
    integrator = cal._dioptrin_integrator
    # Native TIFF loading and ImgModel both flip the file's rows. Dioptas's
    # batch generator additionally applies its frame pipeline before yielding.
    assert not config.img_model.img_transformations
    images = []
    for path in paths:
        config.img_model.load(path)
        with fabio.open(path) as image:
            np.testing.assert_array_equal(config.img_model.img_data, image.data[::-1])
        images.append(config.img_model.get_img_data_float64())
    expected1 = [integrator.integrate1d(image, n, errors=errors) for image in images]
    expected2 = [integrator.integrate2d(image, n, NAZIMUTH, errors=errors) for image in images]
    held = []
    for repeat in range(3):
        generator = iter_frames_sequential(config.img_model, paths * 2, img_shape=images[0].shape)
        batches = [
            list(integrator.batch1d_iter(paths * 2, n, errors=errors, num_workers=2)),
            list(integrator.batch1d_iter(generator, n, errors=errors, num_workers=2)),
            list(integrator.batch2d_iter(paths * 2, n, NAZIMUTH, errors=errors, num_workers=2)),
        ]
        for kind, results in enumerate(batches):
            assert len(results) == 4
            for i, item in enumerate(results):
                assert item.is_ok(), item.error
                result = item.result
                reference = (expected2 if kind == 2 else expected1)[i % 2]
                arrays = {}
                for field in ["radial", "intensity", "errors"] + (["azimuthal"] if kind == 2 else []):
                    value = getattr(result, field)
                    expected = getattr(reference, field)
                    if expected is None:
                        assert value is None
                    else:
                        same(value, expected)
                        arrays[field] = np.asarray(value)
                held.append((result, {key: value.copy() for key, value in arrays.items()}))
                record(f"batch-{detector}-{native.fast}-{supersampling}-{errors}-{repeat}-{kind}-{i}", **arrays)
        if repeat == 1 and hasattr(integrator, "clear_file_workers"):
            integrator.clear_file_workers()
    for result, snapshot in held:
        for field, expected in snapshot.items():
            same(getattr(result, field), expected)
    assert not np.array_equal(expected1[0].intensity, expected1[1].intensity)


def test_model_batch_and_map_apply_image_corrections(real_config, native):
    config, paths, detector = real_config
    cal = config.calibration_model
    cal.dioptrin_num_workers = 2
    config.img_model.load_background(paths[0])
    config.img_model.params.background_scaling = 0.02
    config.img_model.factor = 1.25
    expected = []
    for path in paths * 2:
        config.img_model.load(path)
        _, y = cal.integrate_1d(num_points=NPOINTS, mask=config.mask_model.get_mask(), trim_zeros=False)
        expected.append(y.copy())
    expected = np.asarray(expected)
    batch = config.batch_model
    batch.set_image_files(paths * 2)
    assert cal.can_use_dioptrin_batch("2th_deg")
    batch.integrate_raw_data(0, 4, 1, use_all=True)
    same(batch.data, expected)
    config.map_model.load(paths * 2)
    same(config.map_model.pattern_intensities, expected)
    record(f"pipeline-{detector}-{native.fast}", batch=batch.data,
           map=config.map_model.pattern_intensities)
