# SPDX-License-Identifier: MIT
"""Real backend checks for fixed/dynamic batch and map mask policies."""
from unittest.mock import Mock

import fabio
import numpy as np
import pytest

from dioptas.model.Configuration import Configuration
from dioptas.model.util.MaskPlugin import MaskPluginBase


class MovingThreshold(MaskPluginBase):
    name = "Test moving threshold"
    is_dynamic = True

    def __init__(self):
        self.masks = []

    def compute_mask(self, img_data, **kwargs):
        mask = img_data > 1000
        self.masks.append(mask.copy())
        return mask


@pytest.fixture
def mask_run(tmp_path, qapp):
    pytest.importorskip("dioptrin")
    config = Configuration()
    config.auto_integrate_pattern = False
    config.integration_rad_points = 64
    config.trim_trailing_zeros = False
    config.use_mask = True
    cal = config.calibration_model
    cal.use_dioptrin = True
    cal.dioptrin_num_workers = 1
    poni = tmp_path / "test.poni"
    poni.write_text(
        "poni_version: 1\nPixelSize1: 0.0001\nPixelSize2: 0.0001\n"
        "Distance: 0.1\nPoni1: 0.0032\nPoni2: 0.0032\n"
        "Rot1: 0\nRot2: 0\nRot3: 0\nWavelength: 1e-10\n"
    )
    cal.load(str(poni))
    paths = []
    for i in range(4):
        image = np.full((64, 64), 10 + i, dtype=np.uint16)
        image[10 + i * 8:14 + i * 8, 18:24] = 5000
        path = tmp_path / f"image{i}.tif"
        fabio.tifimage.TifImage(data=image).write(str(path))
        paths.append(str(path))
    config.img_model.load(paths[0])
    static = np.zeros((64, 64), dtype=bool)
    static[:, :3] = True
    config.mask_model.set_mask_data(static)
    plugin = MovingThreshold()
    config.mask_plugin_manager.register(plugin)
    return config, paths, plugin, static


@pytest.mark.parametrize("enabled,use_mask,static_plugin,expected", [
    (False, True, False, "fixed"),
    (True, True, False, "dynamic"),
    (True, False, False, "fixed"),
    (True, True, True, "fixed"),
])
def test_policy_uses_enabled_dynamic_plugins(mask_run, enabled, use_mask, static_plugin, expected):
    config, _, plugin, _ = mask_run
    plugin.is_dynamic = not static_plugin
    config.mask_plugin_manager.set_enabled(plugin.name, enabled)
    config.use_mask = use_mask
    config.prepare_dioptrin_mask_mode()
    assert config.calibration_model._dioptrin_integrator.mask_mode == expected
    # Geometry recreation must retain the selected policy.
    config.calibration_model._dioptrin_integrator_key = None
    config.calibration_model._create_dioptrin_integrator()
    assert config.calibration_model._dioptrin_integrator.mask_mode == expected


def reference_patterns(config, paths, static, dynamic):
    import dioptrin
    cal = config.calibration_model
    integrator = dioptrin.Integrator.from_poni_dict(
        cal._get_poni_dict(), method="pixel_split", unit="2th_deg",
        polarization_factor=cal.polarization_factor, mask_mode="fixed",
    )
    expected = []
    for path in paths:
        with fabio.open(path) as source:
            image = np.ascontiguousarray(source.data[::-1], dtype=np.float64)
        mask = static | (image > 1000) if dynamic else static
        integrator.set_mask(mask.astype(np.uint8))
        expected.append(integrator.integrate1d(image, 64).intensity)
    return np.array(expected)


@pytest.mark.parametrize("kind", ["batch", "map"])
@pytest.mark.parametrize("dynamic", [False, True])
def test_real_runs_refresh_masks_and_restore_fixed_path(mask_run, monkeypatch, kind, dynamic):
    config, paths, plugin, static = mask_run
    config.mask_plugin_manager.set_enabled(plugin.name, dynamic)
    cal = config.calibration_model
    expected = reference_patterns(config, paths, static, dynamic)
    if kind == "batch":
        model = config.batch_model
        model.set_image_files(paths)
        original = model._integrate_raw_data_dioptrin_batch
        spy = Mock(wraps=original)
        monkeypatch.setattr(model, "_integrate_raw_data_dioptrin_batch", spy)
        run = lambda: model.integrate_raw_data(0, len(paths), 1, use_all=True)
        output = lambda: model.data
    else:
        model = config.map_model
        original = model._integrate_dioptrin_batch
        spy = Mock(wraps=original)
        monkeypatch.setattr(model, "_integrate_dioptrin_batch", spy)
        run = lambda: model.load(paths)
        output = lambda: model.pattern_intensities
    plugin.masks.clear()
    plugin_notifications = Mock()
    config.mask_plugin_manager.mask_changed.connect(plugin_notifications)
    run()
    assert cal._dioptrin_integrator.mask_mode == ("dynamic" if dynamic else "fixed")
    assert spy.call_count == (0 if dynamic else 1)
    np.testing.assert_allclose(output(), expected, rtol=2e-13, atol=1e-12)
    assert not config.img_model.img_changed.blocked
    if dynamic:
        # Every frame's moving hot region must be recomputed, even while image
        # signals are blocked; stale masks would leave 5000-count pixels in.
        assert len(plugin.masks) >= len(paths)
        assert len({mask.tobytes() for mask in plugin.masks}) == len(paths)
        plugin_notifications.assert_not_called()
        assert not config.mask_plugin_manager.mask_changed.blocked
        config.mask_plugin_manager.set_enabled(plugin.name, False)
        run()
        assert cal._dioptrin_integrator.mask_mode == "fixed"
        assert spy.call_count == 1
        np.testing.assert_allclose(output(), reference_patterns(config, paths, static, False),
                                   rtol=2e-13, atol=1e-12)


def test_live_map_append_updates_dynamic_masks(mask_run):
    config, paths, plugin, static = mask_run
    config.mask_plugin_manager.set_enabled(plugin.name, True)
    model = config.map_model
    model.load(paths[:2])
    assert model.append_files(paths[2:]) == []
    np.testing.assert_allclose(model.pattern_intensities,
                               reference_patterns(config, paths, static, True),
                               rtol=2e-13, atol=1e-12)
    assert config.calibration_model._dioptrin_integrator.mask_mode == "dynamic"


@pytest.mark.parametrize("native", [False, True], ids=["pyfai", "dioptrin"])
@pytest.mark.parametrize("background", [False, True])
def test_dynamic_run_processes_image_once_and_preserves_storage(mask_run, monkeypatch, native, background):
    from dioptas.model.ImgModel import ImgModel
    config, _, plugin, _ = mask_run
    config.calibration_model.use_dioptrin = native
    config.img_model.factor = 2.5
    if background:
        config.img_model._background_data = np.full((64, 64), 3.0)
        config.img_model._calculate_img_data()
    config.mask_plugin_manager.set_enabled(plugin.name, True)
    config.img_model.img_changed.blocked = True
    config.integrate_image_1d(update_pattern_model=False)  # warm geometry
    raw = config.img_model.raw_img_data
    original = raw.copy()
    getter = ImgModel.img_data.fget
    processed = []

    def counted(model):
        image = getter(model)
        processed.append(image)
        return image

    monkeypatch.setattr(ImgModel, "img_data", property(counted))
    plugin_compute = Mock(wraps=plugin.compute_mask)
    monkeypatch.setattr(plugin, "compute_mask", plugin_compute)
    config.integrate_image_1d(update_pattern_model=False)
    assert len(processed) == 1
    assert plugin_compute.call_args.args[0] is processed[0]
    assert not np.shares_memory(raw, processed[0])
    np.testing.assert_array_equal(raw, original)
    expected = (original.astype(float) - (3 if background else 0)) * 2.5
    np.testing.assert_array_equal(processed[0], expected)


def test_polarization_cache_tracks_factor_and_native_instance(mask_run):
    config, _, _, _ = mask_run
    cal = config.calibration_model
    first = Mock()
    cal._dioptrin_integrator = first
    for factor in [.965, .965, None, None, .5]:
        cal._sync_dioptrin_polarization(factor)
    assert [call.args for call in first.set_polarization_factor.call_args_list] == [(.965,), (None,), (.5,)]
    second = Mock()
    cal._dioptrin_integrator = second
    cal._sync_dioptrin_polarization(.5)
    second.set_polarization_factor.assert_called_once_with(.5)


@pytest.mark.parametrize("mode", ["fixed", "dynamic"])
def test_cached_polarization_updates_match_fresh_native_integrators(mask_run, mode):
    import dioptrin
    config, _, _, static = mask_run
    cal = config.calibration_model
    cal.set_dioptrin_mask_mode(mode)
    image = config.img_model.get_img_data_float64()
    for factor, cake in [(.965, False), (.4, False), (.2, True), (.965, False)]:
        reference = dioptrin.Integrator.from_poni_dict(
            cal._get_poni_dict(), polarization_factor=factor, unit="2th_deg",
            method="pixel_split", mask_mode=mode,
        )
        reference.set_mask(static.astype(np.uint8))
        if cake:
            expected = reference.integrate2d(image, 64, 16, errors=True)
            cal.integrate_2d(rad_points=64, azimuth_points=16, mask=static,
                             polarization_factor=factor)
            # CalibrationModel stores the cake; its return value is not the
            # native result object.
            np.testing.assert_allclose(cal.cake_img, np.asarray(expected.intensity).reshape(16, 64),
                                       rtol=2e-13, atol=1e-12)
        else:
            expected = reference.integrate1d(image, 64, errors=True)
            _, actual = cal.integrate_1d(num_points=64, mask=static, trim_zeros=False,
                                          polarization_factor=factor, calculate_errors=True)
            np.testing.assert_allclose(actual, expected.intensity, rtol=2e-13, atol=1e-12)
            np.testing.assert_allclose(cal.sigma, expected.errors, rtol=2e-13, atol=1e-12)


@pytest.mark.parametrize("method", ["mean", "median"])
def test_spot_mask_computes_once_per_refresh_and_updates_geometry(mask_run, monkeypatch, method):
    from dioptas.model.util.mask_plugins.powder_outlier import PowderDiffSpotMaskPlugin
    config, _, _, static = mask_run
    manager = config.mask_plugin_manager
    plugin = manager.get_plugin('Spot Mask')
    plugin.update_settings({'method': method})
    manager.set_enabled(plugin.name, True)
    compute = Mock(wraps=plugin.compute_mask)
    monkeypatch.setattr(plugin, 'compute_mask', compute)
    image = np.arange(64*64, dtype=float).reshape(64, 64)
    for frame in [image, image[::-1].copy()]:
        compute.reset_mock()
        config._update_plugin_masks(frame)
        compute.assert_called_once()
        assert compute.call_args.args[0] is frame
        fresh = PowderDiffSpotMaskPlugin()
        fresh.update_settings(plugin.get_settings())
        expected = fresh.compute_mask(frame, geometry=manager._geometry, existing_mask=static)
        np.testing.assert_array_equal(manager.plugins[plugin.name].cached_mask, expected)

    # A geometry-only refresh still immediately recomputes on the latest image.
    compute.reset_mock()
    config.calibration_model.pattern_geometry.dist *= 1.2
    config._update_plugin_geometry(image.shape)
    compute.assert_called_once()
    assert compute.call_args.args[0] is frame
    assert compute.call_args.kwargs['geometry'].dist == config.calibration_model.pattern_geometry.dist
    fresh = PowderDiffSpotMaskPlugin()
    fresh.update_settings(plugin.get_settings())
    np.testing.assert_array_equal(manager.plugins[plugin.name].cached_mask,
        fresh.compute_mask(frame, geometry=manager._geometry, existing_mask=static))


@pytest.mark.parametrize('workflow', ['batch', 'map'])
def test_dynamic_hdf_runs_use_fast_prefetch_and_keep_fresh_masks(mask_run, monkeypatch, workflow):
    import h5py
    import dioptrin
    from dioptas.model.loader.fastHdf5 import FastChunkReader
    pytest.importorskip('bslz4_to_sparse')
    config, _, plugin, _ = mask_run
    path = str(__import__('pathlib').Path(__file__).parents[1] / 'data/fast_hdf5/counts-bitshuffle-lz4.h5')
    config.img_model.load(path)
    static = np.zeros((3, 4), bool); static[:, 0] = True
    config.mask_model.set_mask_data(static)
    config.calibration_model.dioptrin_num_workers = 2
    config.mask_plugin_manager.set_enabled(plugin.name, True)
    with h5py.File(path) as f:
        frames = np.ascontiguousarray(f['detector/data'][:][:, ::-1], dtype=float)
    reference = dioptrin.Integrator.from_poni_dict(config.calibration_model._get_poni_dict(),
        method='pixel_split', unit='2th_deg', polarization_factor=config.calibration_model.polarization_factor)
    expected=[]
    for frame in frames:
        reference.set_mask((static | (frame > 1000)).astype(np.uint8))
        expected.append(reference.integrate1d(frame, 64).intensity)
    calls=[];original=FastChunkReader.read
    def tracked(self,index):
        calls.append(index);return original(self,index)
    monkeypatch.setattr(FastChunkReader,'read',tracked)
    if workflow == 'batch':
        model=config.batch_model;model.set_image_files([path])
        model.integrate_raw_data(0,2,1,use_all=True);actual=model.data
    else:
        model=config.map_model;model.load([path]);actual=model.pattern_intensities
    assert 1 in calls
    np.testing.assert_allclose(actual,expected,rtol=2e-13,atol=1e-12)
    assert config.calibration_model._dioptrin_integrator.mask_mode == 'dynamic'
    assert not config.img_model.img_changed.blocked
