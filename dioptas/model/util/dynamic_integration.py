# SPDX-License-Identifier: MIT
"""Bounded, ordered whole-frame jobs with worker-owned scientific state.

Only the caller touches live models. One immutable native plan is shared by all workers. Each frame passes its
mask explicitly and owns its image and accumulation results.
"""
from __future__ import annotations

from collections import deque
from concurrent.futures import Future
from contextlib import contextmanager
from copy import copy, deepcopy
from dataclasses import fields, replace
import hashlib
import gc
from queue import Queue
import threading
from types import SimpleNamespace
import weakref

import numpy as np

from dioptas.model.integration_task import (
    _freeze_geometry, _integrate_pattern_dioptrin, _calculate_num_points,
)
from .integration import _selected_reader, prefetch_series
from ..loader.fastHdf5 import FastChunkReader, UnsupportedFastLayout


def _frozen_array(value):
    if value is None:
        return None
    result = np.array(value, copy=True, order='C')
    result.flags.writeable = False
    return result


def _array_key(value):
    return None if value is None else (value.shape, value.dtype.str,
                                      hashlib.sha256(value).digest())


class _Correction:
    def __init__(self, data):
        self.data = data
        self.shape = None if data is None else data.shape

    def has_items(self):
        return self.data is not None

    def get_data(self):
        return self.data


class _MaskedFrameNative:
    """A lightweight worker sharing one immutable native plan."""
    def __init__(self, plan):
        self.worker = plan.worker(num_threads=1)
        self.points = plan.n_points
        self.mask = None

    def integrate1d(self, image, points, **options):
        if points != self.points:
            raise ValueError('Bin count changed during integration')
        return self.worker.integrate1d(image, mask=self.mask, **options)


class _FrameWorker:
    def __init__(self, snapshot):
        self.snapshot = snapshot
        task, image, self.user_mask, self.base_mask, self.geometry, specs, plan = snapshot
        self.image = copy(image)
        self.plugins = []
        for cls, settings in specs:
            plugin = cls()
            plugin.update_settings(deepcopy(settings))
            if hasattr(plugin, '_num_threads'):
                plugin._num_threads = 1
            self.plugins.append(plugin)
        self.adapter = _MaskedFrameNative(plan)

    def compute(self, read, index):
        raw = read(index)
        image = self.image._apply_frame_pipeline(raw)
        task = self.snapshot[0]
        if image.shape != task.image.shape:
            raise ValueError('Frame shape changed during dynamic integration')
        mask = np.array(self.base_mask, dtype=bool, copy=True)
        for plugin in self.plugins:
            options = {'existing_mask': self.user_mask}
            if plugin.needs_geometry:
                options['geometry'] = self.geometry
            dynamic_mask = plugin.compute_mask(image, **options)
            if dynamic_mask.shape != image.shape:
                raise ValueError(f"Plugin '{plugin.name}' returned an incompatible mask")
            mask |= dynamic_mask
        self.adapter.mask = mask.astype(np.uint8)
        return _integrate_pattern_dioptrin(
            self.adapter, None, replace(task, image=image, mask=mask))


class FramePool:
    """Reusable contexts; at most two job descriptors per worker in flight."""
    def __init__(self, snapshot, workers, factory=_FrameWorker):
        self.queue = Queue(maxsize=2 * workers)
        self.workers = workers
        self.closed = False
        self.threads = [threading.Thread(target=self._run, args=(snapshot, factory),
                                        daemon=True, name=f'dioptas-frame-{i}')
                        for i in range(workers)]
        for thread in self.threads:
            thread.start()

    def _run(self, snapshot, factory):
        worker = None
        try:
            while True:
                job = self.queue.get()
                if job is None:
                    self.queue.task_done()
                    return
                future, read, index = job
                try:
                    if future.set_running_or_notify_cancel():
                        if worker is None:
                            worker = factory(snapshot)
                        future.set_result(worker.compute(read, index))
                except BaseException as error:
                    # Do not retain the worker/native context via a traceback
                    # that could later be destroyed on the caller's thread.
                    future.set_exception(error.with_traceback(None))
                finally:
                    self.queue.task_done()
                    job = future = read = None
        finally:
            # Release worker state before shutting down its owner thread.
            worker = None

    def map(self, read, indices):
        pending = deque()
        indices = iter(indices)
        exhausted = False
        try:
            while pending or not exhausted:
                while len(pending) < 2 * self.workers and not exhausted:
                    try:
                        index = next(indices)
                    except StopIteration:
                        exhausted = True
                        break
                    future = Future()
                    self.queue.put((future, read, index))
                    pending.append((index, future))
                if pending:
                    index, future = pending.popleft()
                    yield index, future.result()
        finally:
            for _, future in pending:
                future.cancel()
            # Reads must finish before the caller closes the file descriptor.
            self.queue.join()

    def close(self):
        if self.closed:
            return
        self.closed = True
        for _ in self.threads:
            self.queue.put(None)
        for thread in self.threads:
            thread.join()


def close_frame_pool(config, *, clear_plan=True):
    finalizer = getattr(config, '_frame_pool_finalizer', None)
    if finalizer is not None:
        finalizer()
    config._frame_pool = None
    config._frame_pool_key = None
    if clear_plan:
        config._frame_plan = None
        config._frame_plan_key = None


def _shared_plan(config, task):
    key = (task.image.shape, task.pattern_num_points,
           _freeze_geometry(task.dioptrin_geometry_config),
           '2th_deg' if task.unit == 'd_A' else task.unit,
           task.supersampling_factor, task.polarization_factor, task.dioptrin_sparse_layout)
    if getattr(config, '_frame_plan_key', None) != key:
        import dioptrin
        native = dioptrin.Integrator.from_poni_dict(
            task.dioptrin_geometry_config, method='pixel_split',
            polarization_factor=task.polarization_factor,
            unit=key[3], mask_mode='dynamic')
        if hasattr(native, "set_sparse_layout"):
            native.set_sparse_layout(task.dioptrin_sparse_layout)
        if task.supersampling_factor > 1:
            native.set_method('supersampled', n_ss=task.supersampling_factor)
        config._frame_plan = native.prepare_dynamic1d(task.image.shape, task.pattern_num_points)
        config._frame_plan_key = key
    return config._frame_plan


def _snapshot(config):
    cal, source = config.calibration_model, config.img_model
    task = config.create_integration_task()
    # Keep a tiny shape carrier; workers never integrate the snapshot image.
    shape = task.image.shape
    carrier = np.broadcast_to(np.float64(0), shape)
    task = replace(task, image=carrier, mask=None, filename='', revision=0,
                   pattern_num_points=task.pattern_num_points or
                   _calculate_num_points(cal.pattern_geometry, shape))
    user_mask = _frozen_array(config.mask_model.get_img())
    base = np.array(user_mask, dtype=bool, copy=True)
    roi = config.mask_model.roi_mask
    if roi is not None:
        base |= roi.astype(bool)
    specs = []
    needs_geometry = False
    for entry in config.mask_plugin_manager.plugins.values():
        if not entry.enabled:
            continue
        if entry.plugin.is_dynamic:
            specs.append((type(entry.plugin), deepcopy(entry.plugin.get_settings())))
            needs_geometry |= entry.plugin.needs_geometry
        elif entry.cached_mask is not None:
            base |= entry.cached_mask
    base = _frozen_array(cal._prepare_integration_mask(base))
    geometry = None
    if needs_geometry:
        from .MaskPlugin import GeometryContext
        geo = cal.pattern_geometry
        geometry = GeometryContext(
            tth_array=_frozen_array(geo.center_array(shape, unit='2th_rad')),
            azi_array=_frozen_array(geo.center_array(shape, unit='chi_rad')),
            **{name: getattr(geo, name) for name in
               ('dist', 'wavelength', 'poni1', 'poni2', 'rot1', 'rot2', 'rot3')},
            pixel1=geo.detector.pixel1, pixel2=geo.detector.pixel2)
    # A detached ImgModel uses precisely the normal transformation/correction
    # pipeline, with independent storage and frozen scientific inputs.
    image = object.__new__(type(source))
    image.params = SimpleNamespace(factor=source.factor,
                                  background_scaling=source.background_scaling,
                                  background_offset=source.background_offset)
    image.img_transformations = list(source.img_transformations)
    image._background_data = _frozen_array(source._background_data)
    correction = source._img_corrections.get_data() if source._img_corrections.has_items() else None
    image._img_corrections = _Correction(_frozen_array(correction))
    for array in (image._background_data, image._img_corrections.data):
        if array is not None and array.shape != shape:
            raise ValueError('Correction/background shape does not match frame')
    task_key = tuple((f.name, _freeze_geometry(getattr(task, f.name)))
                     for f in fields(task) if f.name not in ('image', 'mask'))
    key = (shape, task_key, _array_key(user_mask), _array_key(base),
           tuple((cls, _freeze_geometry(settings)) for cls, settings in specs),
           tuple(image.img_transformations), tuple(vars(image.params).items()),
           _array_key(image._background_data), _array_key(image._img_corrections.data))
    return (task, image, user_mask, base, geometry, specs), key


def _eligible(config):
    cal = config.calibration_model
    if not hasattr(cal._dioptrin_integrator, 'prepare_dynamic1d'):
        return False
    if not (config.has_dynamic_mask and cal.can_use_dioptrin_batch(
            config.integration_unit, config.oned_azimuth_range)):
        return False
    from .HelperModule import rotate_matrix_p90, rotate_matrix_m90
    if any(transform not in (np.fliplr, np.flipud, rotate_matrix_p90, rotate_matrix_m90)
           for transform in config.img_model.img_transformations):
        return False
    shape = config.img_model.raw_img_data.shape
    if any(e.enabled and not e.plugin.is_dynamic and
           (e.cached_mask is None or e.cached_mask.shape != shape)
           for e in config.mask_plugin_manager.plugins.values()):
        # The serial manager refreshes shape-dependent third-party masks.
        return False
    # Third-party plugins can keep the serial contract until a worker-cloning
    # API exists. Built-ins use settings-only instances and independent caches.
    from .mask_plugins.threshold import ThresholdMaskPlugin
    from .mask_plugins.cosmic import CosmicRayMaskPlugin
    from .mask_plugins.powder_outlier import PowderDiffSpotMaskPlugin
    supported = (ThresholdMaskPlugin, CosmicRayMaskPlugin, PowderDiffSpotMaskPlugin)
    return all(type(e.plugin) in supported for e in config.mask_plugin_manager.plugins.values()
               if e.enabled and e.plugin.is_dynamic)


@contextmanager
def frame_integrations(config, indices):
    """Yield ordered (frame_index, pattern) results for the currently loaded file.

    Safe fallback retains existing readers/backends for unsupported formats,
    third-party plugins, azimuth ranges, and correction modes.
    """
    reader = fast = None
    if _eligible(config):
        reader = _selected_reader(config.img_model.filename, config.img_model)
        if reader is not None:
            try:
                fast = FastChunkReader(reader.dataset, config.img_model.filename)
            except UnsupportedFastLayout:
                reader.f.close()
                reader = None
            except BaseException:
                reader.f.close()
                raise
    if fast is None:
        with prefetch_series(config.img_model, workers=config.calibration_model.dioptrin_num_workers):
            def serial():
                for index in indices:
                    config.img_model.load_series_img(index + 1)
                    x, y = config.integrate_image_1d(update_pattern_model=False)
                    yield index, SimpleNamespace(radial=x, intensity=y,
                        azimuthal_std=config.calibration_model.azimuthal_std)
            yield serial()
        return
    iterator = None
    # CPython's cyclic collector can run on any allocating thread. Defer it
    # while jobs run so unrelated GUI-owned PyO3 objects are not finalized on
    # a frame worker. All worker state is acyclic and explicitly owned.
    gc_enabled = gc.isenabled()
    gc.disable()
    try:
        snapshot, key = _snapshot(config)
        workers = max(1, min(config.calibration_model.dioptrin_num_workers or 1, 8))
        key = (workers, key)
        if getattr(config, '_frame_pool_key', None) != key:
            close_frame_pool(config, clear_plan=False)
            plan = _shared_plan(config, snapshot[0])
            pool = FramePool((*snapshot, plan), workers)
            pool.shared_plan_id = plan.shared_plan_id
            config._frame_pool = pool
            config._frame_pool_key = key
            config._frame_pool_finalizer = weakref.finalize(config, pool.close)
        iterator = config._frame_pool.map(fast.read, indices)
        yield iterator
    finally:
        try:
            if iterator is not None:
                iterator.close()
        finally:
            fast.close()
            reader.f.close()
            if gc_enabled:
                gc.enable()
