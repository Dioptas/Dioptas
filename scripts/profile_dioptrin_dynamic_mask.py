"""Profile Qt's changing-mask path on decoded Eiger frames, with exclusive timers.

Use OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 RAYON_NUM_THREADS=1 and run as
``python -m scripts.profile_dioptrin_dynamic_mask --help``. Native integration
includes normalization; the public API does not expose a separate timer for it.
"""
import argparse
from collections import defaultdict
from contextlib import ExitStack
import hashlib
from importlib.metadata import version
import json
import os
from pathlib import Path
from statistics import median
import time
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import h5py
import hdf5plugin  # noqa: F401
import numpy as np
from qtpy.QtWidgets import QApplication

from dioptas.model.Configuration import Configuration
from dioptas.model.ImgModel import ImgModel
from scripts.benchmark_dioptrin_mask_modes import Threshold


class Timers:
    def __init__(self):
        self.reset()
        self.stack = []

    def reset(self):
        self.seconds = defaultdict(float)
        self.calls = defaultdict(int)
        self.image_copy_bytes = 0

    def wrap(self, name, fn):
        def measured(*args, **kwargs):
            entry = [time.perf_counter(), 0.0]
            self.stack.append(entry)
            try:
                return fn(*args, **kwargs)
            finally:
                duration = time.perf_counter() - entry[0]
                self.stack.pop()
                self.seconds[name] += duration - entry[1]
                self.calls[name] += 1
                if self.stack:
                    self.stack[-1][1] += duration
        return measured


class NativeProxy:
    def __init__(self, native, timers):
        self.native = native
        self.integrate1d = timers.wrap("native_integration_and_normalization", native.integrate1d)
        self.set_mask = timers.wrap("native_mask_upload", native.set_mask)
        self.set_polarization_factor = timers.wrap(
            "polarization_reconfiguration", native.set_polarization_factor
        )

    def __getattr__(self, name):
        return getattr(self.native, name)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--hdf5", type=Path, required=True)
    p.add_argument("--poni", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--save-reference", type=Path)
    p.add_argument("--reference", type=Path)
    p.add_argument("--frames", type=int, default=4)
    p.add_argument("--repeats", type=int, default=5)
    args = p.parse_args()
    app = QApplication.instance() or QApplication([])
    dataset = "entry_0000/instrument/eiger/data"
    with h5py.File(args.hdf5) as f:
        source = f[dataset]
        indices = np.linspace(0, len(source)-1, args.frames, dtype=int).tolist()
        frames = [np.ascontiguousarray(source[i][::-1], dtype=np.float64) for i in indices]
    config = Configuration()
    config.auto_integrate_pattern = False
    config.auto_integrate_cake = False
    config.integration_rad_points = 2000
    config.trim_trailing_zeros = False
    config.use_mask = True
    config.img_model.img_changed.blocked = True
    config.img_model._img_data = frames[0]
    config.update_mask_dimension()
    cal = config.calibration_model
    cal.load(str(args.poni))
    cal.use_dioptrin = True
    cal.dioptrin_num_workers = 1
    cal.polarization_factor = 0.965
    cal._create_dioptrin_integrator()
    plugin = Threshold()
    config.mask_plugin_manager.register(plugin)
    config.mask_plugin_manager.set_enabled(plugin.name, True)
    config.integrate_image_1d(update_pattern_model=False)
    timers = Timers()
    raw_getter = ImgModel.img_data.fget

    def image_getter(model):
        value = raw_getter(model)
        if value is not None and not np.shares_memory(value, model.raw_img_data):
            timers.image_copy_bytes += value.nbytes
        return value

    original = cal._dioptrin_integrator
    cal._dioptrin_integrator = NativeProxy(original, timers)
    # Instrumentation preserves the native instance; preserve the correction
    # identity cache too, so installing a timer does not cause a cold update.
    state = getattr(cal, "_dioptrin_polarization_state", None)
    if state is not None and state[0] is original:
        cal._dioptrin_polarization_state = (cal._dioptrin_integrator, state[1])
    samples = []
    with ExitStack() as stack:
        stack.enter_context(patch.object(ImgModel, "img_data", property(timers.wrap("image_preparation_and_copies", image_getter))))
        for obj, attribute, category in [
            (plugin, "compute_mask", "threshold_mask_creation"),
            (config, "_update_plugin_geometry", "plugin_geometry_context"),
            (config.mask_plugin_manager, "update_image", "plugin_refresh_overhead"),
            (config.mask_model, "get_mask", "combine_plugin_user_roi_masks"),
            (cal, "_prepare_integration_mask", "combine_detector_mask"),
        ]:
            stack.enter_context(patch.object(obj, attribute, timers.wrap(category, getattr(obj, attribute))))
        for _ in range(args.repeats):
            timers.reset()
            patterns = []
            start = time.perf_counter()
            for frame in frames:
                config.img_model._img_data = frame
                _, y = config.integrate_image_1d(update_pattern_model=False)
                patterns.append(y.copy())
            total = time.perf_counter() - start
            exclusive = dict(timers.seconds)
            exclusive["other_model_work"] = total - sum(exclusive.values())
            samples.append({"seconds": total, "exclusive_seconds": exclusive,
                            "calls": dict(timers.calls), "image_copy_bytes": timers.image_copy_bytes})
    # A separate uninstrumented pass estimates profiler overhead.
    state = getattr(cal, "_dioptrin_polarization_state", None)
    if state is not None and state[0] is cal._dioptrin_integrator:
        cal._dioptrin_polarization_state = (original, state[1])
    cal._dioptrin_integrator = original
    uninstrumented = []
    for _ in range(args.repeats):
        start = time.perf_counter()
        for frame in frames:
            config.img_model._img_data = frame
            config.integrate_image_1d(update_pattern_model=False)
        uninstrumented.append(time.perf_counter()-start)
    patterns = np.array(patterns)
    numeric = None
    if args.reference:
        with np.load(args.reference) as f:
            expected = f['intensity']
        np.testing.assert_array_equal(patterns, expected)
        numeric = "byte-identical intensity vs pre-optimization reference"
    if args.save_reference:
        np.savez(args.save_reference, intensity=patterns)
    categories = samples[0]['exclusive_seconds']
    result = {
        "dioptrin": version("dioptrin"), "numpy": np.__version__,
        "source": str(args.hdf5.resolve()), "dataset": dataset, "indices": indices,
        "decoded_sha256": [hashlib.sha256(f).hexdigest() for f in frames],
        "settings": {"bins": 2000, "method": "pixel_split", "mask_mode": "dynamic", "threshold": 230, "polarization": .965, "float_precision": "float64", "errors": False},
        "thread_environment": {key: os.environ.get(key) for key in ['OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'RAYON_NUM_THREADS']},
        "source_hashes": {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in [Path('dioptas/model/Configuration.py'), Path('dioptas/model/CalibrationModel.py'), Path('dioptas/model/ImgModel.py')]},
        "samples": samples, "uninstrumented_seconds": uninstrumented,
        "median_fps": args.frames/median(uninstrumented),
        "median_profiled_ms_per_frame": {key: median(s['exclusive_seconds'][key] for s in samples)*1000/args.frames for key in categories},
        "image_getter_calls_per_frame": samples[0]['calls']['image_preparation_and_copies']/args.frames,
        "image_copy_bytes_per_frame": samples[0]['image_copy_bytes']/args.frames,
        "numerical_check": numeric,
        "limits": "One thread, four warmed decoded Eiger9M frames, concurrent rsmith work; setup/decode/file I/O excluded. Exclusive wall timers; native integration includes normalization. Image bytes count getter allocations, not all process allocations.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({key: result[key] for key in ['median_fps','median_profiled_ms_per_frame','image_getter_calls_per_frame','image_copy_bytes_per_frame','numerical_check']},indent=2))
    app.processEvents()


if __name__ == '__main__':
    main()
