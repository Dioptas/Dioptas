"""End-to-end Qt model benchmark on an exact compressed Eiger frame subset.

Run as a module from the checkout root with OMP_NUM_THREADS=1,
OPENBLAS_NUM_THREADS=1 and RAYON_NUM_THREADS=1. Uses real BatchModel/MapModel
entry points, a temporary HDF5 subset retaining original compressed chunks,
and independent native references. Does not render the GUI.
"""
import argparse
from contextlib import nullcontext
import ctypes
import gc
import hashlib
from importlib.metadata import version
import json
import logging
import os
from pathlib import Path
from statistics import median
import tempfile
import subprocess
import time
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import dioptrin
import h5py
import hdf5plugin  # noqa: F401
import numpy as np
import psutil
from qtpy.QtWidgets import QApplication

from dioptas.model.Configuration import Configuration
from dioptas.model.loader.hdf5Loader import Hdf5Image, HAS_BITSHUFFLE
from dioptas.model.util.mask_plugins import powder_outlier

DATASET = 'entry_0000/instrument/eiger/data'
CASES = [
    ('no_mask', None), ('static_mask', None),
    ('threshold_230', ('Threshold Mask', {'above_value': 230})),
    ('threshold_207', ('Threshold Mask', {'above_value': 207})),
    ('cosmic_default', ('Cosmic Ray Mask', {})),
    ('spot_mean', ('Spot Mask', {'method': 'mean'})),
    ('spot_median', ('Spot Mask', {'method': 'median'})),
]


def exact_subset(source_path, target, count):
    # APFS copy-on-write clone preserves the original dataset/filter metadata
    # without invoking the incompatible legacy filter's encoder callbacks.
    # Only the temporary clone is resized and overwritten with original chunks.
    assert source_path.resolve() != target.resolve() and not target.exists()
    subprocess.run(['cp', '-c', str(source_path), str(target)], check=True)
    chunks, frames = [], []
    with h5py.File(source_path, 'r') as source, h5py.File(target, 'r+') as output:
        data = source[DATASET]
        assert data.chunks == (1, *data.shape[1:])
        indices = np.linspace(0, len(data)-1, count, dtype=int).tolist()
        copied = output[DATASET]
        copied.resize((count, *data.shape[1:]))
        for local, index in enumerate(indices):
            filter_mask, raw = data.id.read_direct_chunk((index, 0, 0))
            copied.id.write_direct_chunk((local, 0, 0), raw, filter_mask=filter_mask)
            chunks.append(hashlib.sha256(raw).hexdigest())
            frame = data[index]
            np.testing.assert_array_equal(copied[local], frame)
            frames.append(np.ascontiguousarray(frame[::-1], dtype=np.float64))
    return indices, chunks, frames


def configure(args, subset, case, plugin_config):
    config = Configuration()
    config.auto_integrate_pattern = False
    config.auto_integrate_cake = False
    config.integration_rad_points = 2000
    config.trim_trailing_zeros = False
    config.use_mask = case != 'no_mask'
    config.img_model.img_changed.blocked = True
    config.img_model.load(str(subset))
    config.update_mask_dimension()
    if config.use_mask:
        config.mask_model.load_mask(str(args.mask))
    cal = config.calibration_model
    cal.load(str(args.poni))
    cal.use_dioptrin = True
    cal.dioptrin_num_workers = getattr(args, 'workers', 1)
    cal.polarization_factor = .965
    cal._create_dioptrin_integrator()
    if plugin_config:
        name, settings = plugin_config
        config.mask_plugin_manager.update_plugin_settings(name, settings)
        config.mask_plugin_manager.set_enabled(name, True)
    config.img_model.img_changed.blocked = False
    return config


def reference(args, subset, frames, case, plugin_config):
    config = configure(args, subset, case, plugin_config)
    cal = config.calibration_model
    native = dioptrin.Integrator.from_poni_dict(cal._get_poni_dict(),
        method='pixel_split', unit='2th_deg', polarization_factor=.965, mask_mode='fixed')
    outputs, mask_counts, mask_hashes = [], [], []
    plugin_settings = {name: entry.plugin.get_settings()
                       for name, entry in config.mask_plugin_manager.plugins.items() if entry.enabled}
    for frame in frames:
        # Independent reference: explicitly compute each frame's plugin mask,
        # then integrate directly, without batch/map dispatch or image loading.
        if config.use_mask:
            config._update_plugin_masks(frame)
            assert all(entry.enabled for name, entry in config.mask_plugin_manager.plugins.items()
                       if plugin_config and name == plugin_config[0])
            mask = config.mask_model.get_mask()
            mask = cal._prepare_integration_mask(mask)
            mask_counts.append(int(np.count_nonzero(mask)))
            mask_hashes.append(hashlib.sha256(mask).hexdigest())
            native.set_mask(mask.astype(np.uint8))
        else:
            mask_counts.append(0)
            mask_hashes.append(None)
            native.set_mask(None)
        outputs.append(np.asarray(native.integrate1d(frame, 2000).intensity))
    return np.array(outputs), mask_counts, mask_hashes, plugin_settings


def close_model(config):
    loader = config.img_model.loader
    if isinstance(loader, Hdf5Image):
        loader.f.close()
    from dioptas.model.util.dynamic_integration import close_frame_pool
    close_frame_pool(config)
    del config
    gc.collect()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--hdf5', type=Path, required=True)
    parser.add_argument('--poni', type=Path, required=True)
    parser.add_argument('--mask', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--serial-frame-jobs', action='store_true')
    parser.add_argument('--frames', type=int, default=4)
    parser.add_argument('--repeats', type=int, default=3)
    parser.add_argument('--workers', type=int, default=1)
    parser.add_argument('--decode-workers', type=int, default=1)
    parser.add_argument('--threads-per-worker', type=int, default=1)
    parser.add_argument('--workflows', nargs='+', choices=['batch','map'], default=['batch','map'])
    parser.add_argument('--cases', nargs='+', choices=[case[0] for case in CASES])
    args = parser.parse_args()
    if min(args.workers, args.decode_workers, args.threads_per_worker, args.frames, args.repeats) < 1:
        parser.error('Worker, thread, frame and repeat counts must be positive')
    app = QApplication.instance() or QApplication([])
    logging.getLogger().setLevel(logging.WARNING)
    if powder_outlier._cv2 is not None:
        powder_outlier._cv2.setNumThreads(1)
    original_gen = Hdf5Image.gen_frames

    def bounded_gen(self, n_frames=None, decomp_workers=1, **options):
        return original_gen(self, n_frames=n_frames, decomp_workers=args.decode_workers, **options)

    results = []
    with tempfile.TemporaryDirectory(prefix='dioptas-eiger-masking-') as directory:
        subset = Path(directory)/'eiger_subset.h5'
        indices, chunk_hashes, frames = exact_subset(args.hdf5, subset, args.frames)
        subset_bytes = subset.stat().st_size
        from dioptas.model.util import dynamic_integration
        serial_context = (patch.object(dynamic_integration, '_eligible', return_value=False)
                          if args.serial_frame_jobs else nullcontext())
        with patch.object(Hdf5Image, 'gen_frames', bounded_gen), serial_context:
            for case, plugin_config in CASES:
                if args.cases and case not in args.cases:
                    continue
                print(f'Reference: {case}', flush=True)
                expected, counts, mask_hashes, settings = reference(args, subset, frames, case, plugin_config)
                gc.collect()
                for workflow in args.workflows:
                    config = configure(args, subset, case, plugin_config)
                    if workflow == 'batch':
                        model = config.batch_model
                        model.set_image_files([str(subset)])
                        run = lambda model=model: model.integrate_raw_data(0, len(frames), 1, use_all=True)
                        output = lambda model=model: model.data
                    else:
                        model = config.map_model
                        run = lambda model=model: model.load([str(subset)])
                        output = lambda model=model: model.pattern_intensities
                    dispatch = {'batch_iterator': 0, 'per_frame': 0, 'frame_jobs': 0}
                    from dioptas.model.util.dynamic_integration import _FrameWorker
                    original_job = _FrameWorker.compute
                    def frame_job(*a, **kw):
                        dispatch['frame_jobs'] += 1
                        assert a[0].adapter.worker.shared_plan_id == config._frame_pool.shared_plan_id
                        return original_job(*a, **kw)
                    def original_batch(images, n_points, azimuthal_std=False, _config=config):
                        return _config.calibration_model._dioptrin_integrator.batch1d_iter(
                            images, n_points, num_workers=args.workers,
                            num_threads=args.threads_per_worker,
                            **({'azimuthal_std':True} if azimuthal_std else {}))
                    original_frame = config.calibration_model.integrate_1d

                    def batched(*a, _original=original_batch, **kw):
                        dispatch['batch_iterator'] += 1
                        return _original(*a, **kw)

                    def per_frame(*a, _original=original_frame, **kw):
                        dispatch['per_frame'] += 1
                        return _original(*a, **kw)

                    with patch.object(config.calibration_model, 'dioptrin_batch1d_iter', batched), \
                         patch.object(config.calibration_model, 'integrate_1d', per_frame), \
                         patch.object(_FrameWorker, 'compute', frame_job):
                        start = time.perf_counter()
                        run()
                        first_run = time.perf_counter()-start
                        samples = []
                        for _ in range(args.repeats):
                            dispatch.update(batch_iterator=0, per_frame=0, frame_jobs=0)
                            cpu = psutil.cpu_times()
                            own = psutil.Process().cpu_times()
                            start = time.perf_counter()
                            run()
                            elapsed = time.perf_counter()-start
                            cpu_after = psutil.cpu_times()
                            own_after = psutil.Process().cpu_times()
                            busy = ((cpu_after.user+cpu_after.system)-(cpu.user+cpu.system))
                            process_cpu = ((own_after.user+own_after.system)-(own.user+own.system))
                            samples.append({'seconds': elapsed, 'process_cpu_seconds': process_cpu,
                                            'other_busy_cores': max(0,(busy-process_cpu)/elapsed),
                                            'dispatch': dispatch.copy()})
                            actual = np.asarray(output())
                            np.testing.assert_allclose(actual, expected, rtol=5e-12, atol=1e-9)
                            assert actual.shape == (len(frames), 2000)
                            dynamic = plugin_config is not None
                            assert config.calibration_model._dioptrin_integrator.mask_mode == ('dynamic' if dynamic else 'fixed')
                            assert config.calibration_model.use_dioptrin
                            assert dispatch == (({'batch_iterator':0,'per_frame':len(frames),'frame_jobs':0}
                                                 if args.serial_frame_jobs else {'batch_iterator':0,'per_frame':0,'frame_jobs':len(frames)}) if dynamic
                                                 else {'batch_iterator':1,'per_frame':0,'frame_jobs':0})
                            if dynamic:
                                assert config.mask_plugin_manager.is_enabled(plugin_config[0])
                    relative = float(np.linalg.norm(actual-expected)/np.linalg.norm(expected))
                    item = {'case':case,'workflow':workflow, 'mask_mode':'dynamic' if plugin_config else 'fixed',
                            'first_run_seconds':first_run,'samples':samples,
                            'median_fps':len(frames)/median(s['seconds'] for s in samples),
                            'reference_relative_l2':relative, 'masked_pixels':counts,
                            'mask_hashes':mask_hashes,'plugin_settings':settings}
                    results.append(item)
                    print(f'{case:18s} {workflow:5s}: {item["median_fps"]:.2f} fps, L2={relative:.2g}',flush=True)
                    close_model(config)
                    del config, model, run, output, original_batch, original_frame
                    gc.collect()
    try:
        omp_threads = ctypes.CDLL('/opt/homebrew/opt/libomp/lib/libomp.dylib').omp_get_max_threads()
    except OSError:
        omp_threads = None
    source_paths = [Path('dioptas/model')/name for name in ['MaskPluginManager.py','Configuration.py','CalibrationModel.py','BatchModel.py','MapModel.py','ImgModel.py','loader/hdf5Loader.py','util/mask_plugins/threshold.py','util/mask_plugins/cosmic.py','util/mask_plugins/powder_outlier.py']]
    result = {'date':'2026-11-06','source':str(args.hdf5.resolve()),'source_bytes':args.hdf5.stat().st_size,
              'dataset':DATASET,'source_indices':indices,'shape':frames[0].shape,'subset_bytes':subset_bytes,
              'subset_creation':'APFS clone of original file; resize only the cloned dataset and overwrite four frames with exact original compressed chunks; no recompression; all decoded pixels independently compared. macOS cp -c is required for fixture preparation.',
              'compressed_chunk_sha256':chunk_hashes,'decoded_float64_sha256':[hashlib.sha256(f).hexdigest() for f in frames],
              'mask_source':str(args.mask.resolve()),'mask_sha256':hashlib.sha256(args.mask.read_bytes()).hexdigest(),
              'poni':str(args.poni.resolve()),'poni_sha256':hashlib.sha256(args.poni.read_bytes()).hexdigest(),
              'packages':{p:version(p) for p in ['dioptrin','numpy','h5py','hdf5plugin','scipy']},
              'backend':('Local unreleased Dioptrin shared-plan build; package version remains 0.8.0, not the published wheel.' if hasattr(dioptrin.Integrator, 'prepare_dynamic1d') else 'Published Dioptrin 0.8.0'),
              'features':{'bitshuffle_parallel_decoder':HAS_BITSHUFFLE,'shared_dynamic_plan':hasattr(dioptrin.Integrator,'prepare_dynamic1d'),'spot_native_extension':powder_outlier._c_compute_binned is not None,'opencv_smoothing':powder_outlier._cv2 is not None,'openmp_max_threads':omp_threads},
              'settings':{'bins':2000,'method':'pixel_split','unit':'2th_deg','polarization':.965,'solid_angle':True,'precision':'float64','poisson_errors':False,'factor':1,'background':None,'workers':args.workers,'threads_per_worker':args.threads_per_worker,'decompression_workers':args.decode_workers,'serial_frame_jobs':args.serial_frame_jobs},
              'source_hashes':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in source_paths},
              'thread_environment':{key:os.environ.get(key) for key in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','RAYON_NUM_THREADS']},
              'limits':'Production Qt reader and processing; warm-cache sampled subset of same Eiger file, concurrent user activity. Explicit fixed batch worker/thread counts; dynamic masking/integration uses independent whole-frame workers and one private native thread per worker. Timings include Qt model dispatch, file opening, read/decompression, image preparation, mask updates and integration, result collection and map reduction. Exclude GUI rendering, fixture preparation, initial Configuration setup and first-run LUT/plugin setup. Independent references excluded from clocks. This is not full 625-frame or cold-SSD throughput.',
              'results':results}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2)+'\n')
    print('Saved',args.output,flush=True)
    app.processEvents()


if __name__=='__main__':
    main()
