//! Bounded, ordered frame execution over one immutable reader and CSC plan.
//! Shared-pool tasks reuse decoder/integration scratch for the entire source.
use crate::{control::Control, gpu::plans::Gpu1dPlan};
use dioptrin::integration::{Fixed1dPlan, Fixed1dResult, InputOrder};
use dioptrin_io::{
    PixelBuffer, PixelType,
    hdf5::raw::{FrameBuffer, RawReader},
};
use rayon::prelude::*;
use std::sync::{
    atomic::{AtomicBool, Ordering},
    mpsc,
};

pub(super) struct Stats {
    pub workers: usize,
    pub frames: usize,
    pub pending_peak: usize,
}

/// The decoder's conservative full-frame payload estimate also bounds the
/// worker storage. Plans and the caller's final series are separate.
const WORKER_BUDGET: usize = 4 * 1024 * 1024 * 1024;

pub(super) fn run(
    reader: &RawReader,
    plan: &Fixed1dPlan,
    errors: bool,
    frames: &[usize],
    control: &Control,
    mut consume: impl FnMut(usize, Fixed1dResult) -> Result<(), String>,
) -> Result<Stats, String> {
    execute(
        reader,
        frames,
        control,
        0,
        || Ok(plan.worker(errors, InputOrder::FlipVertical)),
        |integrator, pixels, _, _| {
            integrator.begin_frame();
            match pixels {
                PixelBuffer::U16(v) => integrator.push_u16_block(0, v),
                PixelBuffer::U32(v) => integrator.push_u32_block(0, v),
                _ => return Err("Unexpected series pixel type.".into()),
            }?;
            integrator.finish_frame()
        },
        &mut consume,
    )
}

const GPU_SERIES_BATCH: usize = 16;

/// Distinguishes recoverable GPU execution errors from fatal I/O, cancellation,
/// or consumer errors so callers never re-consume frames or mask fatal errors.
pub(super) enum GpuRunError {
    Gpu { consumed: usize },
    Fatal(String),
}

/// Decodes frames in parallel into reusable buffers and submits 16-frame
/// batches to the GPU plan (using `InputOrder::FlipVertical` to avoid host
/// vertical flips).
pub(super) fn run_gpu(
    reader: &RawReader,
    plan: &Gpu1dPlan,
    errors: bool,
    frames: &[usize],
    control: &Control,
    mut consume: impl FnMut(usize, Fixed1dResult) -> Result<(), String>,
) -> Result<Stats, GpuRunError> {
    if frames.is_empty() {
        return Ok(Stats {
            workers: 0,
            frames: 0,
            pending_peak: 0,
        });
    }
    let pool = crate::worker_pool::current();
    let max_batch = GPU_SERIES_BATCH
        .min(frames.len())
        .min((WORKER_BUDGET / reader.worker_payload_bytes().max(1)).max(1));
    let mut buffers: Vec<FrameBuffer> = (0..max_batch).map(|_| FrameBuffer::default()).collect();
    let kind = reader.pixel_type();
    let mut consumed = 0usize;

    for chunk in frames.chunks(max_batch) {
        control.check().map_err(GpuRunError::Fatal)?;
        let n = chunk.len();
        pool.install(|| {
            buffers[..n]
                .par_iter_mut()
                .zip(chunk.par_iter())
                .try_for_each(|(buf, &frame)| {
                    control.check()?;
                    reader
                        .read_frame_into(frame, buf)
                        .map_err(|e| e.to_string())
                })
        })
        .map_err(GpuRunError::Fatal)?;
        control.check().map_err(GpuRunError::Fatal)?;
        let results = match kind {
            PixelType::U16 => {
                let mut slices = Vec::with_capacity(n);
                for buf in &buffers[..n] {
                    match buf.pixels() {
                        Some(PixelBuffer::U16(v)) => slices.push(v.as_slice()),
                        _ => {
                            return Err(GpuRunError::Fatal("Unexpected series pixel type.".into()));
                        }
                    }
                }
                plan.integrate_batch_u16(&slices, errors)
                    .map_err(|_| GpuRunError::Gpu { consumed })?
            }
            PixelType::U32 => {
                let mut slices = Vec::with_capacity(n);
                for buf in &buffers[..n] {
                    match buf.pixels() {
                        Some(PixelBuffer::U32(v)) => slices.push(v.as_slice()),
                        _ => {
                            return Err(GpuRunError::Fatal("Unexpected series pixel type.".into()));
                        }
                    }
                }
                plan.integrate_batch_u32(&slices, errors)
                    .map_err(|_| GpuRunError::Gpu { consumed })?
            }
            _ => return Err(GpuRunError::Fatal("Unexpected series pixel type.".into())),
        };
        for (&frame, result) in chunk.iter().zip(results) {
            control.check().map_err(GpuRunError::Fatal)?;
            consume(frame, result).map_err(GpuRunError::Fatal)?;
            consumed += 1;
        }
    }

    Ok(Stats {
        workers: pool.current_num_threads().min(max_batch),
        frames: frames.len(),
        pending_peak: max_batch,
    })
}

pub(super) fn execute<S: Send, R: Send>(
    reader: &RawReader,
    frames: &[usize],
    control: &Control,
    extra_worker_bytes: usize,
    create: impl Fn() -> Result<S, String> + Sync,
    process: impl Fn(&mut S, &PixelBuffer, usize, &Control) -> Result<R, String> + Sync,
    mut consume: impl FnMut(usize, R) -> Result<(), String>,
) -> Result<Stats, String> {
    let pool = crate::worker_pool::current();
    let requested = pool.current_num_threads();
    let workers = requested.min(frames.len()).min(
        WORKER_BUDGET
            / reader
                .worker_payload_bytes()
                .saturating_add(extra_worker_bytes)
                .max(1),
    );
    if frames.is_empty() {
        return Ok(Stats {
            workers: 0,
            frames: 0,
            pending_peak: 0,
        });
    }
    if workers == 0 {
        return Err("A series worker exceeds the 4 GiB worker payload budget.".into());
    }
    control.check()?;
    let stop = AtomicBool::new(false);
    let create = &create;
    let process = &process;
    pool.in_place_scope(|scope| {
        // Each submitted frame is a finite task: no pool thread waits for more
        // jobs. Scratch ownership returns with its result and is reused when an
        // ordered queue slot opens, retaining the existing bounded pipeline.
        let (results, completed) = mpsc::sync_channel(workers);
        let dispatch = |ordinal, frame, scratch: Option<(FrameBuffer, S)>| {
            let results = results.clone();
            let stop = &stop;
            scope.spawn(move |_| {
                let outcome = std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| {
                    if stop.load(Ordering::Acquire) {
                        return Ok(None);
                    }
                    control.check()?;
                    let (mut decoder, mut state) = match scratch {
                        Some(scratch) => scratch,
                        None => (FrameBuffer::default(), create()?),
                    };
                    reader
                        .read_frame_into(frame, &mut decoder)
                        .map_err(|e| e.to_string())?;
                    control.check()?;
                    let result = process(
                        &mut state,
                        decoder.pixels().ok_or("Incomplete series frame.")?,
                        frame,
                        &control.silent_child(),
                    )?;
                    Ok::<_, String>(Some((ordinal, result, (decoder, state))))
                }))
                .unwrap_or_else(|_| Err("Series frame worker panicked.".into()));
                match outcome {
                    Ok(Some(value)) => {
                        let _ = results.send(Ok(value));
                    }
                    Ok(None) => {}
                    Err(error) => {
                        stop.store(true, Ordering::Release);
                        let _ = results.send(Err(error));
                    }
                }
            });
        };
        let outcome = (|| {
            let mut dispatched = workers;
            for (ordinal, &frame) in frames.iter().take(workers).enumerate() {
                dispatch(ordinal, frame, None);
            }
            let mut pending = std::collections::BTreeMap::new();
            let mut next = 0;
            let mut pending_peak = 0;
            while next < frames.len() {
                control.check()?;
                let (ordinal, result, scratch) = completed
                    .recv()
                    .map_err(|_| "Series workers stopped before completing the source.")??;
                pending.insert(ordinal, (result, scratch));
                pending_peak = pending_peak.max(pending.len());
                while let Some((result, scratch)) = pending.remove(&next) {
                    control.check()?;
                    consume(frames[next], result)?;
                    next += 1;
                    if dispatched < frames.len() {
                        dispatch(dispatched, frames[dispatched], Some(scratch));
                        dispatched += 1;
                    }
                }
            }
            Ok(Stats {
                workers,
                frames: next,
                pending_peak,
            })
        })();
        stop.store(true, Ordering::Release);
        // Disconnect before the scope joins, releasing senders on cancellation.
        drop(completed);
        outcome
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use dioptrin::{geometry::Geometry, integration::Integrator, poni::Poni};
    use dioptrin_io::hdf5::Limits;
    use std::io::Write;

    fn fixture(u16_samples: bool) -> (tempfile::TempDir, RawReader, Fixed1dPlan) {
        let temp = tempfile::tempdir().unwrap();
        let path = temp.path().join("frames.h5");
        let file = hdf5::File::create(&path).unwrap();
        let samples: Vec<u32> = (0..40 * 17 * 23)
            .map(|i| (i % 997 + 11 * (i / (17 * 23))) as u32)
            .collect();
        if u16_samples {
            file.new_dataset::<u16>()
                .shape([40, 17, 23])
                .chunk([1, 17, 23])
                .create("frames")
                .unwrap()
                .write_raw(&samples.iter().map(|&v| v as u16).collect::<Vec<_>>())
                .unwrap();
        } else {
            file.new_dataset::<u32>()
                .shape([40, 17, 23])
                .chunk([1, 17, 23])
                .create("frames")
                .unwrap()
                .write_raw(&samples)
                .unwrap();
        }
        drop(file);
        let reader = RawReader::open_snapshot(&path, "/frames", Limits::default()).unwrap();
        let mut poni = Poni::new();
        poni.pixel1 = 1e-4;
        poni.pixel2 = 1e-4;
        poni.distance = 0.15;
        poni.poni1 = 0.0007;
        poni.poni2 = 0.0012;
        let plan = Integrator::new(Geometry::new(17, 23, poni))
            .with_fast_math(true)
            .prepare_fixed1d((17, 23), 32)
            .unwrap()
            .with_csc_layout();
        (temp, reader, plan)
    }

    #[test]
    fn ordered_strided_u16_u32_and_poisson_share_one_plan() {
        for u16_samples in [false, true] {
            let (_temp, reader, plan) = fixture(u16_samples);
            for errors in [false, true] {
                let frames: Vec<_> = (1..40).step_by(2).collect();
                let mut observed = vec![];
                let stats = run(
                    &reader,
                    &plan,
                    errors,
                    &frames,
                    &Control::default(),
                    |frame, result| {
                        let values: Vec<_> = (0..17)
                            .rev()
                            .flat_map(|r| {
                                (0..23).map(move |c| {
                                    let i = frame * 17 * 23 + r * 23 + c;
                                    (i % 997 + 11 * frame) as f64
                                })
                            })
                            .collect();
                        let expected = plan.integrate_frame(&values, errors)?;
                        assert_eq!(result.radial, expected.radial);
                        for (actual, reference) in result.intensity.iter().zip(expected.intensity) {
                            assert!((actual - reference).abs() <= 2e-12 * reference.abs().max(1.));
                        }
                        assert_eq!(result.errors.is_some(), errors);
                        if let Some(sigma) = result.errors {
                            for (actual, reference) in sigma.iter().zip(expected.errors.unwrap()) {
                                assert!(
                                    (actual - reference).abs() <= 2e-12 * reference.abs().max(1.)
                                );
                            }
                        }
                        observed.push(frame);
                        Ok(())
                    },
                )
                .unwrap();
                assert_eq!(observed, frames);
                assert_eq!(stats.frames, frames.len());
                assert!(stats.workers <= stats.frames);
                assert!(stats.pending_peak <= stats.workers);
            }
        }
    }

    #[test]
    fn errors_cancel_and_consumer_failure_join_workers_and_allow_reuse() {
        let (_temp, reader, plan) = fixture(false);
        let frames: Vec<_> = (0..40).collect();
        let control = Control::default();
        let error = run(&reader, &plan, false, &frames, &control, |_, _| {
            control.cancel();
            Ok(())
        })
        .err()
        .unwrap();
        assert!(error.contains("cancelled"), "{error}");
        let error = run(
            &reader,
            &plan,
            false,
            &frames,
            &Control::default(),
            |_, _| Err("preview failed".into()),
        )
        .err()
        .unwrap();
        assert_eq!(error, "preview failed");
        assert!(
            run(
                &reader,
                &plan,
                false,
                &[0, usize::MAX, 2],
                &Control::default(),
                |_, _| Ok(())
            )
            .is_err()
        );
        assert_eq!(
            run(
                &reader,
                &plan,
                false,
                &frames,
                &Control::default(),
                |_, _| Ok(())
            )
            .unwrap()
            .frames,
            40
        );
    }

    #[test]
    fn integration_uses_the_shared_selected_pool_without_exceeding_its_budget() {
        let (_temp, reader, plan) = fixture(true);
        for workers in [1, crate::worker_pool::available().min(4)] {
            let pool = crate::worker_pool::pool(Some(workers)).unwrap();
            crate::worker_pool::enter(pool, || {
                let stats = run(
                    &reader,
                    &plan,
                    true,
                    &(0..19).collect::<Vec<_>>(),
                    &Control::default(),
                    |_, _| Ok(()),
                )
                .unwrap();
                assert_eq!(stats.workers, workers);
                assert_eq!(stats.frames, 19);
                assert!(stats.pending_peak <= workers);
            });
        }
    }
    #[test]
    fn source_mutation_discards_provisional_frames() {
        let (temp, reader, plan) = fixture(false);
        let mut changed = false;
        let result = run(
            &reader,
            &plan,
            false,
            &(0..40).collect::<Vec<_>>(),
            &Control::default(),
            |_, _| {
                if !changed {
                    std::fs::OpenOptions::new()
                        .append(true)
                        .open(temp.path().join("frames.h5"))
                        .unwrap()
                        .write_all(b"changed source")
                        .unwrap();
                    changed = true;
                }
                Ok(())
            },
        );
        assert!(result.is_err());
    }
}
