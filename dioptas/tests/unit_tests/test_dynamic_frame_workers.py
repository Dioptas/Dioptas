# SPDX-License-Identifier: MIT
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import threading
from unittest.mock import patch

import numpy as np
import pytest

from dioptas.model.Configuration import Configuration
from dioptas.model.util import dynamic_integration as dynamic

FIXTURE = Path(__file__).parents[1] / 'data/fast_hdf5/counts-bitshuffle-lz4.h5'


@pytest.fixture
def config(tmp_path, qapp):
    dioptrin = pytest.importorskip('dioptrin')
    if not hasattr(dioptrin.Integrator, 'prepare_dynamic1d'):
        pytest.skip('Shared dynamic plans require the unreleased native API')
    pytest.importorskip('bslz4_to_sparse')
    c = Configuration()
    c.auto_integrate_pattern = False
    c.auto_integrate_cake = False
    c.integration_rad_points = 16
    c.trim_trailing_zeros = False
    c.img_model.load(str(FIXTURE))
    c.update_mask_dimension()
    p = tmp_path / 'small.poni'
    p.write_text('poni_version: 1\nPixelSize1: 0.0001\nPixelSize2: 0.0001\n'
                 'Distance: 0.1\nPoni1: 0.0001\nPoni2: 0.0001\n'
                 'Rot1: 0\nRot2: 0\nRot3: 0\nWavelength: 1e-10\n')
    c.calibration_model.load(str(p))
    c.calibration_model.use_dioptrin = True
    c.calibration_model.dioptrin_num_workers = 4
    c.calibration_model._create_dioptrin_integrator()
    c.use_mask = True
    c.mask_plugin_manager.update_plugin_settings('Threshold Mask', {'above_value': 300})
    c.mask_plugin_manager.set_enabled('Threshold Mask', True)
    c.img_model.img_changed.blocked = True
    yield c
    dynamic.close_frame_pool(c)


@pytest.mark.parametrize('plugin', ['Threshold Mask', 'Cosmic Ray Mask', 'Spot Mask'])
@pytest.mark.parametrize('unit', ['2th_deg', 'q_A^-1', 'd_A'])
def test_parallel_matches_serial_and_keeps_order(config, plugin, unit):
    c = config
    c.integration_unit = unit
    c.mask_plugin_manager.set_enabled('Threshold Mask', False)
    c.mask_plugin_manager.set_enabled(plugin, True)
    indices = [1, 0, 1, 1, 0]
    with patch.object(dynamic, '_eligible', return_value=False):
        with dynamic.frame_integrations(c, indices) as results:
            expected = [(i, r.radial.copy(), r.intensity.copy()) for i, r in results]
    with dynamic.frame_integrations(c, indices) as results:
        actual = list(results)
    assert c._frame_pool.workers == 4
    assert [i for i, _ in actual] == indices
    for (_, x, y), (_, result) in zip(expected, actual):
        np.testing.assert_allclose(result.radial, x, rtol=1e-13, atol=1e-12)
        np.testing.assert_allclose(result.intensity, y, rtol=5e-12, atol=1e-9)


def test_corrections_mask_changes_and_pool_reuse(config):
    c = config
    img = c.img_model
    img.factor = 1.25
    img.rotate_img_p90()
    c.update_mask_dimension()
    img._background_data = np.full(img.raw_img_data.shape, 2.)
    img.background_scaling = .7
    img.background_offset = .5
    # Use the real correction manager with an already-calculated correction.
    from types import SimpleNamespace
    correction = SimpleNamespace(get_data=lambda: np.full(img.raw_img_data.shape, 1.2),
                                 shape=img.raw_img_data.shape)
    img._img_corrections = correction_manager = dynamic._Correction(correction.get_data())
    img._calculate_img_data()
    for threshold in [300, 18]:
        c.mask_plugin_manager.update_plugin_settings('Threshold Mask', {'above_value': threshold})
        c.calibration_model.polarization_factor = .8 if threshold == 18 else .965
        static = np.zeros(img.raw_img_data.shape, dtype=bool)
        static[0, 0] = True
        c.mask_model.set_mask_data(static)
        with patch.object(dynamic, '_eligible', return_value=False):
            with dynamic.frame_integrations(c, [0, 1]) as results:
                expected = [r.intensity.copy() for _, r in results]
        with dynamic.frame_integrations(c, [0, 1]) as results:
            actual = [r.intensity for _, r in results]
        np.testing.assert_allclose(actual, expected, rtol=5e-12, atol=1e-9)
        pool = c._frame_pool
        with dynamic.frame_integrations(c, [0, 1]) as results:
            list(results)
        assert c._frame_pool is pool
    assert img._img_corrections is correction_manager


def test_pool_overlaps_jobs_drops_on_owner_and_cancels():
    owners, drops = [], []
    barrier = threading.Barrier(4)
    class Worker:
        def __init__(self, snapshot):
            self.owner = threading.get_ident()
            owners.append(self.owner)
        def compute(self, read, index):
            assert threading.get_ident() == self.owner
            if index < 4:
                barrier.wait(timeout=5)
            return read(index)
        def __del__(self):
            drops.append((self.owner, threading.get_ident()))
    pool = dynamic.FramePool(None, 4, Worker)
    try:
        assert list(pool.map(lambda x: x * 2, range(12))) == [(i, i*2) for i in range(12)]
        iterator = pool.map(lambda x: x, range(4, 100))
        next(iterator)
        iterator.close()
        assert list(pool.map(lambda x: x, [12])) == [(12, 12)]
    finally:
        pool.close()
    assert len(set(owners)) == 4
    assert len(drops) == 4 and all(owner == drop for owner, drop in drops)
    assert not any(t.is_alive() for t in pool.threads)


def test_read_exception_and_early_exit_close_source(config, monkeypatch):
    readers = []
    original = dynamic.FastChunkReader
    class Reader(original):
        def __init__(self, *a):
            super().__init__(*a)
            readers.append(self)
        def read(self, index):
            if index == 1:
                raise OSError('injected source error')
            return super().read(index)
    monkeypatch.setattr(dynamic, 'FastChunkReader', Reader)
    with pytest.raises(OSError, match='injected'):
        with dynamic.frame_integrations(config, [0, 1, 0]) as results:
            list(results)
    assert readers[0].fd is None
    with dynamic.frame_integrations(config, [0]*20) as results:
        next(results)
    assert readers[1].fd is None
    with dynamic.frame_integrations(config, [0]) as results:
        assert len(list(results)) == 1


@pytest.mark.parametrize('median', [False, True])
def test_spot_native_parallel_matches_serial(median):
    from dioptas.model.util.mask_plugins.powder_outlier import _c_compute_binned
    if _c_compute_binned is None:
        pytest.skip('native Spot Mask extension unavailable')
    rng = np.random.default_rng(123)
    images = [rng.exponential(10, 8192).astype(np.float64) for _ in range(8)]
    bins = np.tile(np.arange(128, dtype=np.int32), 64)
    def compute(image):
        return _c_compute_binned(image, bins, 128, 3., median, 1)
    expected = [compute(x) for x in images]
    with ThreadPoolExecutor(4) as pool:
        actual = list(pool.map(compute, images))
    np.testing.assert_array_equal(actual, expected)
    assert np.count_nonzero(actual)


@pytest.mark.parametrize('errors,spread', [(False, False), (True, False),
                                         (False, True), (True, True)])
@pytest.mark.parametrize('supersampling', [1, 2])
def test_statistics_and_automatic_bins(config, errors, spread, supersampling):
    c = config
    c.calculate_poisson_errors = errors
    c.calculate_azimuthal_std = spread
    c.integration_rad_points = None
    c.trim_trailing_zeros = True
    c.calibration_model.supersampling_factor = supersampling
    with patch.object(dynamic, '_eligible', return_value=False):
        with dynamic.frame_integrations(c, [0, 1]) as results:
            expected = []
            for _, result in results:
                expected.append((result.radial.copy(), result.intensity.copy(),
                                 c.calibration_model.sigma,
                                 result.azimuthal_std))
    with dynamic.frame_integrations(c, [0, 1]) as results:
        actual = list(results)
    for (_, result), (x, y, sigma, std) in zip(actual, expected):
        np.testing.assert_allclose(result.radial, x, rtol=5e-12, atol=1e-9)
        np.testing.assert_allclose(result.intensity, y, rtol=5e-12, atol=1e-9)
        if errors:
            np.testing.assert_allclose(result.sigma, sigma, rtol=5e-12, atol=1e-9)
        if spread:
            np.testing.assert_allclose(result.azimuthal_std, std, rtol=5e-12, atol=1e-9)


def test_gc_state_restored_and_native_pool_owned(config, monkeypatch):
    import gc
    enabled = gc.isenabled()
    original = dynamic._FrameWorker.compute
    seen = []
    def compute(self, *args):
        seen.append(gc.isenabled())
        return original(self, *args)
    monkeypatch.setattr(dynamic._FrameWorker, 'compute', compute)
    for state in [False, True]:
        (gc.enable if state else gc.disable)()
        try:
            with dynamic.frame_integrations(config, [0, 1]) as results:
                list(results)
                assert not gc.isenabled()
            assert gc.isenabled() == state
        finally:
            (gc.enable if enabled else gc.disable)()
    assert seen and not any(seen)


@pytest.mark.parametrize('workflow', ['batch', 'map'])
def test_real_workflows_use_complete_frame_jobs(config, monkeypatch, workflow):
    c = config
    with patch.object(dynamic, '_eligible', return_value=False):
        with dynamic.frame_integrations(c, [0, 1]) as results:
            expected = [r.intensity.copy() for _, r in results]
    seen = []
    original = dynamic._FrameWorker.compute
    def compute(self, read, index):
        seen.append(index)
        return original(self, read, index)
    monkeypatch.setattr(dynamic._FrameWorker, 'compute', compute)
    c.img_model.img_changed.blocked = False
    if workflow == 'batch':
        model = c.batch_model
        model.set_image_files([str(FIXTURE)])
        model.integrate_raw_data(0, 2, 1, use_all=True)
        actual = model.data
        assert np.asarray(model.pos_map).tolist() == [[0, 0], [0, 1]]
    else:
        model = c.map_model
        model.load([str(FIXTURE)])
        actual = model.pattern_intensities
        assert [point.frame_index for point in model.point_infos] == [0, 1]
    assert sorted(seen) == [0, 1]
    assert c._frame_pool.shared_plan_id
    np.testing.assert_allclose(actual, expected, rtol=5e-12, atol=1e-9)
    assert not c.img_model.img_changed.blocked
    threads = list(c._frame_pool.threads)
    c.mask_plugin_manager.set_enabled('Threshold Mask', False)
    if workflow == 'batch':
        model.integrate_raw_data(0, 2, 1, use_all=True)
    else:
        model.load([str(FIXTURE)])
    assert c._frame_pool is None
    assert not any(thread.is_alive() for thread in threads)



def test_mask_and_image_setting_changes_reuse_geometry_plan(config):
    c = config
    with dynamic.frame_integrations(c, [0, 1]) as results:
        list(results)
    plan = c._frame_plan
    pool = c._frame_pool
    c.mask_plugin_manager.update_plugin_settings('Threshold Mask', {'above_value': 18})
    static = c.mask_model.get_img().copy()
    static[0, 1] = True
    c.mask_model.set_mask_data(static)
    c.img_model.factor = 1.1
    with dynamic.frame_integrations(c, [0, 1]) as results:
        list(results)
    assert c._frame_pool is not pool
    assert c._frame_plan is plan
    assert c._frame_pool.shared_plan_id == plan.shared_plan_id
    c.calibration_model.polarization_factor = .5
    with dynamic.frame_integrations(c, [0, 1]) as results:
        list(results)
    assert c._frame_plan is not plan


@pytest.mark.parametrize('workflow', ['batch', 'map'])
def test_repeated_fixed_dynamic_round_trips_reuse_plan_and_preserve_results(config, workflow):
    c = config
    c.img_model.img_changed.blocked = False
    if workflow == 'batch':
        model = c.batch_model
        model.set_image_files([str(FIXTURE)])
        def run():
            model.integrate_raw_data(0, 2, 1, use_all=True)
            return model.data.copy()
    else:
        model = c.map_model
        def run():
            model.load([str(FIXTURE)])
            return np.asarray(model.pattern_intensities).copy()
    old_plans = []  # retain objects so identity checks cannot reuse freed addresses
    for threshold in (300, 18, 300):
        c.mask_plugin_manager.update_plugin_settings('Threshold Mask', {'above_value': threshold})
        c.mask_plugin_manager.set_enabled('Threshold Mask', True)
        with patch.object(dynamic, '_eligible', return_value=False):
            expected_dynamic = run()
        actual_dynamic = run()
        np.testing.assert_allclose(actual_dynamic, expected_dynamic, rtol=5e-12, atol=1e-9)
        plan, pool = c._frame_plan, c._frame_pool
        assert all(plan is previous for previous in old_plans)
        old_plans.append(plan)
        np.testing.assert_allclose(run(), expected_dynamic, rtol=5e-12, atol=1e-9)
        assert c._frame_plan is plan and c._frame_pool is pool
        c.mask_plugin_manager.set_enabled('Threshold Mask', False)
        expected_fixed = []
        with dynamic.prefetch_series(c.img_model, workers=1):
            # Force the normal per-frame path as an independent dispatch reference.
            for i in (0, 1):
                c.img_model.load_series_img(i+1)
                _, y = c.integrate_image_1d(update_pattern_model=False)
                expected_fixed.append(y.copy())
        actual_fixed = run()
        np.testing.assert_allclose(actual_fixed, expected_fixed, rtol=5e-12, atol=1e-9)
        assert c._frame_pool is None and c._frame_plan is plan
        assert not any(thread.is_alive() for thread in pool.threads)
        static = c.mask_model.get_img().copy()
        static[-1, 0] = not static[-1, 0]
        c.mask_model.set_mask_data(static)
    assert len(old_plans) == 3


def test_layout_choice_reaches_native_and_replaces_plan(config):
    c = config
    outputs = []
    plans = []
    for layout in ('csc', 'csr', 'csc'):
        c.calibration_model.dioptrin_sparse_layout = layout
        assert c.calibration_model._dioptrin_integrator.sparse_layout == layout
        assert c.create_integration_task().dioptrin_sparse_layout == layout
        with dynamic.frame_integrations(c, [0,1]) as results:
            outputs.append([r.intensity for _,r in results])
        plans.append(c._frame_plan)
    assert all(a is not b for a,b in zip(plans,plans[1:]))
    np.testing.assert_allclose(outputs[0],outputs[1],rtol=5e-12,atol=1e-9)
    np.testing.assert_allclose(outputs[0],outputs[2],rtol=5e-12,atol=1e-9)
    with pytest.raises(ValueError):c.calibration_model.dioptrin_sparse_layout = 'invalid'
