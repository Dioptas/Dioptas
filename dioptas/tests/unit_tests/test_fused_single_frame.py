# SPDX-License-Identifier: MIT
"""Chooser, snapshot, fallback and numeric checks for the single-frame bridge."""
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
import shutil
import sys

import h5py
import numpy as np
import pytest

from dioptas.model.integration_task import PersistentIntegrationEngine
from dioptas.model.loader.fusedHdf5 import describe_fused_source, file_identity

FIXTURE = Path(__file__).parents[1] / "data/fast_hdf5/counts-bitshuffle-lz4.h5"


@pytest.fixture
def hdf_task(calibrated_config):
    config = calibrated_config
    config.auto_integrate_pattern = False
    config.auto_integrate_cake = False
    config.img_model.load(str(FIXTURE))
    task = config.create_integration_task()
    source = describe_fused_source(config.img_model)
    assert source is not None
    return config, replace(task, fused_hdf5_source=source, prefer_dioptrin=True, pattern_num_points=17,
                           trim_trailing_zeros=False, mask=None, calculate_pattern=True,
                           dioptrin_geometry_config=config.calibration_model._get_poni_dict(),
                           correct_solid_angle=True, pattern_azimuth_range=None)


@pytest.fixture
def fake_backends(monkeypatch):
    calls = SimpleNamespace(fused=[], ordinary=[], builds=[], behavior=None)

    def result(points, errors):
        return SimpleNamespace(radial=np.arange(points, dtype=float),
            intensity=np.ones(points), errors=np.ones(points) if errors else None)

    class Ordinary:
        @staticmethod
        def from_poni_dict(*args, **kwargs):
            return Ordinary()
        def set_sparse_layout(self, *args): pass
        def set_method(self, *args, **kwargs): pass
        def set_unit(self, *args): pass
        def set_mask(self, *args): pass
        def set_polarization_factor(self, *args): pass
        def integrate1d(self, image, points, **kwargs):
            calls.ordinary.append(image)
            return result(points, kwargs.get("errors", False))

    class Unsupported(ValueError): pass
    class Mismatch(ValueError): pass

    class Fused:
        def __init__(self, path, dataset, poni, points, **kwargs):
            self.points = points
            calls.builds.append((path, dataset, points, kwargs))
            if calls.behavior == "unsupported": raise Unsupported()
        def integrate1d(self, frame, **kwargs):
            calls.fused.append((frame, kwargs))
            if calls.behavior == "mismatch": raise Mismatch()
            if calls.behavior == "decode_error": raise OSError("invalid compressed block")
            return result(self.points, kwargs["errors"])

    monkeypatch.setitem(sys.modules, "dioptrin", SimpleNamespace(Integrator=Ordinary))
    monkeypatch.setitem(sys.modules, "dioptrin_io_fused", SimpleNamespace(
        FusedHdf5Integrator=Fused, UnsupportedFusedLayout=Unsupported,
        SourceImageMismatch=Mismatch))
    return calls


def test_selects_eight_core_fused_preview_and_reuses_plan(hdf_task, fake_backends):
    _, task = hdf_task
    engine = PersistentIntegrationEngine()
    engine.compute(task)
    engine.compute(replace(task, calculate_errors=True))
    assert not fake_backends.ordinary
    assert len(fake_backends.builds) == 1
    assert len(fake_backends.fused) == 2
    assert fake_backends.builds[0][3]["num_workers"] == 8
    assert fake_backends.fused[1][1]["errors"]
    np.testing.assert_array_equal(fake_backends.fused[0][1]["expected_image"], task.image)


def test_plan_invalidates_for_fixed_mask_bins_and_polarization(hdf_task, fake_backends):
    _, task = hdf_task
    engine = PersistentIntegrationEngine()
    engine.compute(task)
    mask = np.zeros(task.image.shape, bool); mask[0, 0] = True
    task = replace(task, mask=mask)
    engine.compute(task)
    engine.compute(task)
    task = replace(task, pattern_num_points=19)
    engine.compute(task)
    task = replace(task, polarization_factor=.7)
    engine.compute(task)
    assert len(fake_backends.builds) == 4


@pytest.mark.parametrize("change", [dict(fused_hdf5_source=None),
    dict(calculate_azimuthal_std=True), dict(dioptrin_sparse_layout="csr"),
    dict(dioptrin_geometry_config={"wavelength": 0})])
def test_excluded_tasks_keep_current_path(hdf_task, fake_backends, change):
    _, task = hdf_task
    PersistentIntegrationEngine().compute(replace(task, **change))
    assert not fake_backends.fused and not fake_backends.builds
    assert fake_backends.ordinary


def test_missing_bridge_keeps_ordinary_integration(hdf_task, fake_backends, monkeypatch):
    _, task = hdf_task
    monkeypatch.setitem(sys.modules, "dioptrin_io_fused", SimpleNamespace())
    PersistentIntegrationEngine().compute(task)
    assert len(fake_backends.ordinary) == 1


@pytest.mark.parametrize("behavior", ["unsupported", "mismatch"])
def test_admission_and_pixel_mismatch_fall_back(hdf_task, fake_backends, behavior):
    _, task = hdf_task
    fake_backends.behavior = behavior
    PersistentIntegrationEngine().compute(task)
    assert len(fake_backends.ordinary) == 1


def test_decoder_failure_is_not_silently_replayed(hdf_task, fake_backends):
    _, task = hdf_task
    fake_backends.behavior = "decode_error"
    with pytest.raises(OSError, match="compressed block"):
        PersistentIntegrationEngine().compute(task)
    assert not fake_backends.ordinary


def test_changed_source_fails_before_native_integration(hdf_task, fake_backends, tmp_path):
    _, task = hdf_task
    path = tmp_path / "source.h5"; shutil.copyfile(FIXTURE, path)
    source = replace(task.fused_hdf5_source, filename=str(path), identity=file_identity(path))
    with path.open("ab") as stream: stream.write(b"changed")
    with pytest.raises(OSError, match="changed"):
        PersistentIntegrationEngine().compute(replace(task, fused_hdf5_source=source))
    assert not fake_backends.fused and not fake_backends.ordinary


def test_dynamic_bulk_transformations_and_corrections_excluded(hdf_task, monkeypatch):
    config, _ = hdf_task
    assert config.create_integration_task(allow_fused=False).fused_hdf5_source is None
    monkeypatch.setattr(type(config), "has_dynamic_mask", property(lambda self: True))
    assert config.create_integration_task().fused_hdf5_source is None
    config.img_model.factor = 2
    assert describe_fused_source(config.img_model) is None
    config.img_model.factor = 1
    config.img_model.flip_img_horizontally()
    assert describe_fused_source(config.img_model) is None


def test_prefetch_callback_cannot_be_mistaken_for_a_preview(hdf_task):
    config, _ = hdf_task
    config.img_model.series_get_image = lambda i: np.zeros((3, 4))
    assert describe_fused_source(config.img_model) is None


@pytest.mark.parametrize("unit", ["2th_deg", "q_A^-1", "d_A"])
@pytest.mark.parametrize("errors", [False, True])
def test_real_native_bridge_matches_current_qt_pattern(hdf_task, unit, errors):
    bridge = pytest.importorskip("dioptrin_io_fused")
    assert hasattr(bridge, "FusedHdf5Integrator")
    _, task = hdf_task
    task = replace(task, unit=unit, calculate_errors=errors,
                   mask=np.arange(task.image.size).reshape(task.image.shape) % 7 == 0)
    engine = PersistentIntegrationEngine()
    actual = engine.compute(task).pattern
    expected = engine.compute(replace(task, fused_hdf5_source=None)).pattern
    np.testing.assert_allclose(actual.radial, expected.radial)
    np.testing.assert_allclose(actual.intensity, expected.intensity, rtol=2e-12, atol=1e-10)
    if errors: np.testing.assert_allclose(actual.sigma, expected.sigma, rtol=2e-12, atol=1e-10)
    assert any(backend.fused is not None for backend in engine._dioptrin_backends.values())


def test_real_coordinator_owns_fused_backend_on_worker(hdf_task, qtbot, monkeypatch):
    pytest.importorskip("dioptrin_io_fused")
    import threading
    from dioptas.model.DioptasModel import DioptasModel
    from dioptas.controller.integration_coordinator import AsyncIntegrationCoordinator
    config, _ = hdf_task
    config.calibration_model.use_dioptrin = True
    config.calibration_model.detector.mask = np.zeros(config.img_model.raw_img_data.shape, np.int8)
    config.mask_model.clear_mask()
    config.integration_rad_points = 17
    assert config.create_integration_task().calculate_pattern
    model = DioptasModel()
    model.configurations[0] = config
    coordinator = AsyncIntegrationCoordinator(model, debounce_ms=0)
    real = coordinator.integration_engine.compute
    seen = []
    def compute(task):
        result = real(task)
        seen.append((threading.get_ident(), any(b.fused is not None for b in
            coordinator.integration_engine._dioptrin_backends.values())))
        return result
    monkeypatch.setattr(coordinator.integration_engine, "compute", compute)
    failures = []
    coordinator.failed.connect(lambda *args: failures.append(args))
    try:
        for _ in range(2):
            coordinator.request(config, calculate_pattern=True, calculate_cake=False, immediate=True)
            qtbot.waitUntil(lambda: not coordinator.is_busy, timeout=10000)
        assert not failures
        assert len(seen) == 2 and all(thread != threading.get_ident() for thread, _ in seen)
        # This image was loaded before the coordinator was attached. It uses
        # its resident array, without an automatic fused reread.
        assert not any(native for _, native in seen)
    finally:
        coordinator.shutdown()


@pytest.fixture
def combined_config(hdf_task, monkeypatch):
    pytest.importorskip("dioptrin_io_fused")
    from dioptas.model.DioptasModel import DioptasModel
    from dioptas.controller.integration_coordinator import AsyncIntegrationCoordinator
    config, _ = hdf_task
    config.calibration_model.use_dioptrin = True
    config.calibration_model.detector.mask = np.zeros(config.img_model.raw_img_data.shape, np.int8)
    config.mask_model.clear_mask()
    config.use_mask = True
    config.integration_rad_points = 17
    model = DioptasModel(); model.configurations[0] = config
    coordinator = AsyncIntegrationCoordinator(model, debounce_ms=0)
    config.auto_integrate_pattern = True
    # Read every requested frame through the production hook, while preview
    # requests are explicitly driven by each test to avoid a timer race.
    config.pattern_integration.active = False
    yield config, coordinator
    coordinator.shutdown()


def test_combined_navigation_decodes_once_and_worker_uses_precomputed(combined_config, qtbot, monkeypatch):
    config, coordinator = combined_config
    original = config.img_model.loader.get_image
    ordinary = []
    def no_decode(index):
        ordinary.append(index)
        return original(index)
    monkeypatch.setattr(config.img_model.loader, "get_image", no_decode)
    # Preserve the authoritative series callback identity for ordinary loading.
    config.img_model.series_get_image = config.img_model.loader.get_image
    for index in [1, 0]:
        config.img_model.load_series_img(index+1, force=True)
        cached = config.img_model._combined_pattern
        assert cached is not None and not config.img_model.raw_img_data.flags.writeable
        task = config.create_integration_task()
        assert task.precomputed_pattern is not None and task.fused_hdf5_source is None
        def no_array(*args): raise AssertionError("precomputed pattern must not integrate pixels again")
        monkeypatch.setattr(coordinator.integration_engine, "_ensure_dioptrin", no_array)
        coordinator.request(config, calculate_pattern=True, calculate_cake=False, immediate=True)
        qtbot.waitUntil(lambda: not coordinator.is_busy, timeout=10000)
        np.testing.assert_allclose(config.pattern_model.pattern.y, cached.result.intensity)
    assert ordinary == []


def test_combined_settings_edits_use_resident_array_without_reread(combined_config, qtbot):
    config, coordinator = combined_config
    config.img_model.load_series_img(2, force=True)
    original = config.create_integration_task()
    assert original.precomputed_pattern is not None
    changed = replace(original, polarization_factor=.7)
    assert not changed.precomputed_pattern.matches(changed)
    custom = replace(original, image=np.array(original.image, copy=True)+1)
    assert not custom.precomputed_pattern.matches(custom)
    config.mask_model.set_mask_data(np.ones(config.img_model.raw_img_data.shape, bool))
    assert config.create_integration_task().precomputed_pattern is None
    config.mask_model.clear_mask()
    config.calculate_poisson_errors = True
    assert config.create_integration_task().precomputed_pattern is None


def test_combined_skips_dynamic_and_blocked_bulk_loads(combined_config, monkeypatch):
    config, coordinator = combined_config
    callback = config.img_model.combined_frame_loader
    monkeypatch.setattr(type(config), "has_dynamic_mask", property(lambda self: True))
    assert callback(config.img_model.filename, 0, existing_loader=config.img_model.loader) is None
    monkeypatch.setattr(type(config), "has_dynamic_mask", property(lambda self: False))
    config.img_model.img_changed.blocked = True
    assert callback(config.img_model.filename, 0, existing_loader=config.img_model.loader) is None
    config.img_model.img_changed.blocked = False


def test_combined_does_not_wait_behind_bulk_owner_job(combined_config):
    import threading
    config, coordinator = combined_config
    sibling = coordinator.create_processing_runner(None)
    release = threading.Event()
    sibling.submit(lambda: release.wait(5))
    sibling.shutdown(wait=False)  # its actual executor work is still active
    try:
        assert config.img_model.combined_frame_loader(config.img_model.filename, 0,
            existing_loader=config.img_model.loader) is None
    finally:
        release.set()
        sibling.shutdown(wait=False)


def _lima_file(tmp_path, name="lima.h5"):
    path = tmp_path / name
    shutil.copyfile(FIXTURE, path)
    with h5py.File(path, "a") as file:
        file.attrs["default"] = "entry"
        file.attrs["creator"] = "LIMA-1.10.6"
        entry = file.create_group("entry")
        entry.attrs["default"] = "instrument/eiger/data"
        entry.create_group("measurement")["data"] = file["detector/data"]
        entry.create_group("instrument/eiger")["data"] = file["detector/data"]
    return path


def test_initial_lima_load_uses_one_decode_preserves_header_and_reuses_plan(combined_config, tmp_path, monkeypatch):
    import fabio
    from dioptas.model.loader.FabioLoader import FabioLoader
    config, coordinator = combined_config
    path = _lima_file(tmp_path)
    def no_ordinary(*args, **kwargs): raise AssertionError("must not decode through FabIO")
    monkeypatch.setattr(FabioLoader, "__init__", no_ordinary)
    config.img_model.load(path, 1)
    assert config.img_model._combined_pattern is not None
    kept = config.img_model.raw_img_data
    native_id = coordinator._runner.call_when_idle(
        lambda: id(coordinator.integration_engine._combined_loader.backend))
    reference = fabio.open(path, frame=1)
    try:
        np.testing.assert_array_equal(kept, reference.data[::-1])
        assert kept.dtype == reference.data.dtype
        assert config.img_model._img_data_fabio.header == reference.header
        assert config.img_model.series_pos == 2 and config.img_model.series_max == 2
    finally:
        reference.close()
    other = _lima_file(tmp_path, "other.h5")
    config.img_model.load(other, 0)
    assert coordinator._runner.call_when_idle(
        lambda: id(coordinator.integration_engine._combined_loader.backend)) == native_id
    np.testing.assert_array_equal(kept, np.arange(12,24,dtype=np.uint32).reshape(3,4)[::-1])


def test_combined_failure_leaves_live_image_and_filename_unchanged(combined_config, tmp_path, monkeypatch):
    config, coordinator = combined_config
    path = _lima_file(tmp_path)
    filename, pixels = config.img_model.filename, config.img_model.raw_img_data
    real = coordinator.integration_engine.load_combined
    def change_source(request):
        result = real(request)
        with path.open("ab") as stream: stream.write(b"source changed")
        return result
    monkeypatch.setattr(coordinator.integration_engine, "load_combined", change_source)
    with pytest.raises(OSError, match="changed"):
        config.img_model.load(path)
    assert config.img_model.filename == filename
    assert config.img_model.raw_img_data is pixels


def test_changed_file_before_navigation_does_not_mix_cached_metadata_with_new_counts(combined_config, tmp_path):
    config, coordinator = combined_config
    path = _lima_file(tmp_path)
    config.img_model.load(path)
    with path.open("ab") as stream: stream.write(b"changed before navigation")
    assert config.img_model.combined_frame_loader(str(path), 1,
        existing_loader=config.img_model.loader) is None
