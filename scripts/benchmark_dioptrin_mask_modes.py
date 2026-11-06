"""Time Qt model mask policies on decoded Eiger frames, with bounded CPU use.

Example (from the checkout root)::

    OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 RAYON_NUM_THREADS=1 \
      .venv/bin/python -m scripts.benchmark_dioptrin_mask_modes \
      --hdf5 /path/to/eiger_0000.h5 --poni /path/to/calibration.poni \
      --output /tmp/dioptas-mask-mode-timing.json

This times Configuration.integrate_image_1d, including threshold-mask creation,
mask updates and normalization. Loading/decoding, initial geometry setup and
one warm frame per case are excluded. It is not a file-throughput benchmark.
"""
import argparse
import hashlib
from importlib.metadata import version
import json
import os
from pathlib import Path
import platform
from statistics import median
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import h5py
import hdf5plugin  # noqa: F401 - registers bitshuffle/LZ4 decoders
import numpy as np
from qtpy.QtWidgets import QApplication

from dioptas.model.Configuration import Configuration
from dioptas.model.util.MaskPlugin import MaskPluginBase


class Threshold(MaskPluginBase):
    name = "Benchmark threshold"
    is_dynamic = True

    def compute_mask(self, img_data, **kwargs):
        return img_data > 230


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hdf5", type=Path, required=True)
    parser.add_argument("--poni", type=Path, required=True)
    parser.add_argument("--dataset", default="entry_0000/instrument/eiger/data")
    parser.add_argument("--frames", type=int, default=4)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.frames < 2 or args.repeats < 1:
        parser.error("Use at least two frames and one repeat")
    app = QApplication.instance() or QApplication([])
    with h5py.File(args.hdf5) as handle:
        source = handle[args.dataset]
        indices = np.linspace(0, len(source) - 1, args.frames, dtype=int).tolist()
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
    cal.dioptrin_num_workers = 1
    cal.load(str(args.poni))
    cal.use_dioptrin = True
    cal._create_dioptrin_integrator()
    cal.polarization_factor = 0.965
    plugin = Threshold()
    config.mask_plugin_manager.register(plugin)
    original_set_mode = cal.set_dioptrin_mask_mode
    timings, outputs = {}, {}
    # Alternate cases on later repeats to reduce ordering bias. Force the
    # opposite policy as a control; both must give equivalent results.
    cases = [(False, "fixed"), (False, "dynamic"), (True, "fixed"), (True, "dynamic")]
    for repeat in range(args.repeats):
        for dynamic, policy in (cases if repeat % 2 == 0 else cases[::-1]):
            key = f"{'changing' if dynamic else 'static'}_mask_{policy}_policy"
            config.mask_plugin_manager.set_enabled(plugin.name, dynamic)
            cal.set_dioptrin_mask_mode = lambda requested, selected=policy: original_set_mode(selected)
            config.prepare_dioptrin_mask_mode()
            config.img_model._img_data = frames[0]
            config.integrate_image_1d(update_pattern_model=False)
            result = []
            start = time.perf_counter()
            for frame in frames:
                config.img_model._img_data = frame
                _, intensity = config.integrate_image_1d(update_pattern_model=False)
                result.append(intensity)
            elapsed = time.perf_counter() - start
            timings.setdefault(key, []).append(elapsed)
            outputs[key] = np.array(result)
    # The real fixed-mask map/batch path configures its mask once, then streams
    # frames. Compare that wrapper with the per-frame model controls above.
    cal.set_dioptrin_mask_mode = original_set_mode
    config.mask_plugin_manager.set_enabled(plugin.name, False)
    config.prepare_dioptrin_mask_mode()
    cal.sync_dioptrin_for_batch(config.mask_model.get_mask(), "2th_deg", 2000, frames[0].shape)
    list(cal.dioptrin_batch1d_iter(iter(frames), 2000))
    batch_seconds = []
    for _ in range(args.repeats):
        start = time.perf_counter()
        batch_results = list(cal.dioptrin_batch1d_iter(iter(frames), 2000))
        batch_seconds.append(time.perf_counter() - start)
    assert all(result.is_ok() for result in batch_results)
    batch_intensity = np.array([result.result.intensity for result in batch_results])
    np.testing.assert_allclose(batch_intensity, outputs["static_mask_fixed_policy"],
                               rtol=1e-11, atol=1e-10)
    timings["static_mask_fixed_batch_wrapper"] = batch_seconds
    errors = {}
    for prefix in ["static", "changing"]:
        a, b = [outputs[f"{prefix}_mask_{p}_policy"] for p in ["fixed", "dynamic"]]
        np.testing.assert_allclose(a, b, rtol=1e-11, atol=1e-10)
        errors[prefix] = float(np.linalg.norm(a-b)/np.linalg.norm(a))
    result = {
        "dioptrin": version("dioptrin"), "platform": platform.platform(),
        "source": str(args.hdf5.resolve()), "dataset": args.dataset,
        "frame_indices": indices, "shape": frames[0].shape,
        "decoded_sha256": [hashlib.sha256(f).hexdigest() for f in frames],
        "poni": str(args.poni.resolve()), "bins": 2000,
        "method": "pixel_split", "precision": "float64", "threshold": 230,
        "static_mask": "none; isolates execution-policy differences",
        "thread_environment": {k: os.environ.get(k) for k in ["OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "RAYON_NUM_THREADS"]},
        "limits": "Short single-thread warmed model-path timing during concurrent rsmith work; no I/O/decompression or initial LUT setup; not peak throughput or a 0.7-vs-0.8 comparison.",
        "relative_l2": errors,
        "results": {k: {"seconds": v, "median_fps": len(frames)/median(v)} for k,v in timings.items()},
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result["results"], indent=2))
    print("relative L2:", errors)
    app.processEvents()


if __name__ == "__main__":
    main()
