"""Measure first-result latency after a single-image integration, without GUI rendering.

Original HDF5 input is opened read-only. Batch selects a short prefix; Map
requests cancellation after that prefix and drains already admitted work.
"""
import argparse
from importlib.metadata import version
import json
from pathlib import Path
import time
from unittest.mock import patch

import dioptrin
import numpy as np

from dioptas.model.Configuration import Configuration
from dioptas.model.CalibrationModel import CalibrationModel
from dioptas.model.batch_task import BatchIntegrationTask, compute_batch_integration
from dioptas.model.integration_task import PersistentIntegrationEngine
from dioptas.model.map_task import compute_map_integration
from dioptas.model.worker_configuration import capture_worker_configuration


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hdf5", type=Path, required=True)
    parser.add_argument("--poni", type=Path, required=True)
    parser.add_argument("--mask", type=Path, required=True)
    parser.add_argument("--frames", type=int, default=4)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    dioptrin.validate_license()
    config = Configuration()
    config.auto_integrate_pattern = False
    config.auto_integrate_cake = False
    config.img_model.load(str(args.hdf5))
    if not 0 < args.frames <= config.img_model.series_max or args.workers < 1:
        parser.error("invalid frame/worker count")
    config.calibration_model.use_dioptrin = True
    config.calibration_model.load(str(args.poni))
    config.calibration_model.dioptrin_num_workers = args.workers
    config.integration_rad_points = 2000
    config.trim_trailing_zeros = False
    config.mask_model.load_mask(str(args.mask))
    config.use_mask = True
    engine = PersistentIntegrationEngine()
    try:
        started = time.perf_counter()
        preview = engine.compute(config.create_integration_task()).pattern
        preview_seconds = time.perf_counter() - started
        native = engine.dioptrin_integrator
        positions = np.column_stack((np.zeros(config.img_model.series_max, int),
                                     np.arange(config.img_model.series_max)))
        state = capture_worker_configuration(config)
        task = BatchIntegrationTask(state, (str(args.hdf5),), positions, positions,
                                    0, args.frames, 1, True)
        original = CalibrationModel.dioptrin_batch1d_iter
        measurements = []
        reference = None
        for label, shared, workflow in [
            ("fresh_batch", None, "batch"),
            ("shared_batch", engine, "batch"),
            ("shared_batch_repeat", engine, "batch"),
            ("shared_map", engine, "map"),
        ]:
            record = {"case": label}
            started = time.perf_counter()

            def timed(calibration, *a, **kw):
                record["reused_preview_backend"] = calibration._dioptrin_integrator is native
                for index, result in enumerate(original(calibration, *a, **kw)):
                    if index == 0:
                        record["first_result_seconds"] = time.perf_counter() - started
                    yield result

            with patch.object(CalibrationModel, "dioptrin_batch1d_iter", timed):
                if workflow == "batch":
                    result = compute_batch_integration(task, engine=shared)
                    data = result.data
                else:
                    result = compute_map_integration(
                        state, [str(args.hdf5)], lambda n, total: n < args.frames,
                        engine=shared)
                    data = result.pattern_intensities
            record["total_seconds"] = time.perf_counter() - started
            record["output_frames"] = len(data)
            if reference is None:
                reference = data.copy()
            np.testing.assert_allclose(data[:args.frames], reference, rtol=1e-12, atol=1e-12)
            np.testing.assert_allclose(data[0], preview.intensity, rtol=1e-12, atol=1e-12)
            assert record["reused_preview_backend"] == (shared is not None)
            record["max_abs_difference"] = float(np.max(np.abs(data[:args.frames] - reference)))
            measurements.append(record)
            print(json.dumps(record), flush=True)
        output = {
            "dioptrin_version": version("dioptrin"),
            "input": str(args.hdf5), "poni": str(args.poni), "mask": str(args.mask),
            "shape": list(config.img_model.img_data.shape),
            "source_frames": config.img_model.series_max,
            "selected_batch_frames": args.frames, "workers": args.workers,
            "preview_cold_seconds": preview_seconds, "measurements": measurements,
            "limits": "Warm OS cache; concurrent user work; no GUI rendering. "
                      "Map cancellation is throttled, so its output can exceed the requested prefix.",
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(output, indent=2) + "\n")
    finally:
        engine.close()


if __name__ == "__main__":
    main()
