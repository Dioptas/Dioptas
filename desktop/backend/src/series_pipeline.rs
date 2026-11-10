//! Bounded, ordered frame execution over one immutable reader and CSC plan.
//! Threads and decoder/integration scratch live for the entire source, not a frame.
use crate::control::Control;
use dioptrin::integration::{Fixed1dPlan, Fixed1dResult, InputOrder};
use dioptrin_io::{
    PixelBuffer,
    hdf5::raw::{FrameBuffer, RawReader},
};
use std::sync::{
    Arc, Mutex,
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

pub(super) fn execute<S: Send, R: Send>(
    reader: &RawReader,
    frames: &[usize],
    control: &Control,
    extra_worker_bytes: usize,
    create: impl Fn() -> Result<S, String> + Sync,
    process: impl Fn(&mut S, &PixelBuffer, usize, &Control) -> Result<R, String> + Sync,
    mut consume: impl FnMut(usize, R) -> Result<(), String>,
) -> Result<Stats, String> {
    let requested = std::env::var("DIOPTAS_INTEGRATION_THREADS")
        .ok()
        .and_then(|v| v.parse::<usize>().ok())
        .unwrap_or(8)
        .clamp(1, 256);
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
    std::thread::scope(|scope| {
        let (jobs, incoming) = mpsc::channel::<(usize, usize)>();
        let incoming = Arc::new(Mutex::new(incoming));
        let (results, completed) = mpsc::sync_channel(workers);
        let mut handles = Vec::with_capacity(workers);
        for _ in 0..workers {
            let incoming = incoming.clone();
            let results = results.clone();
            let stop = &stop;
            let (create, process) = (&create, &process);
            handles.push(scope.spawn(move || {
                // Convert a worker panic to a failed operation, so an ordered
                // collector never waits forever for the missing frame.
                let outcome = std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| {
                    let mut decoder = FrameBuffer::default();
                    let mut state = create()?;
                    let child_control = control.silent_child();
                    while !stop.load(Ordering::Acquire) {
                        let Ok((ordinal, frame)) = incoming.lock().unwrap().recv() else {
                            break;
                        };
                        control.check()?;
                        if stop.load(Ordering::Acquire) {
                            break;
                        }
                        reader
                            .read_frame_into(frame, &mut decoder)
                            .map_err(|e| e.to_string())?;
                        control.check()?;
                        let result = process(
                            &mut state,
                            decoder.pixels().ok_or("Incomplete series frame.")?,
                            frame,
                            &child_control,
                        )?;
                        if results.send(Ok((ordinal, result))).is_err() {
                            break;
                        }
                    }
                    Ok::<_, String>(())
                }))
                .unwrap_or_else(|_| Err("Series frame worker panicked.".into()));
                if let Err(error) = outcome {
                    stop.store(true, Ordering::Release);
                    let _ = results.send(Err(error));
                }
            }));
        }
        drop(results);
        let outcome = (|| {
            let mut dispatched = workers;
            for (ordinal, &frame) in frames.iter().take(workers).enumerate() {
                jobs.send((ordinal, frame)).map_err(|e| e.to_string())?;
            }
            let mut pending = std::collections::BTreeMap::new();
            let mut next = 0;
            let mut pending_peak = 0;
            while next < frames.len() {
                control.check()?;
                let (ordinal, result) = completed
                    .recv()
                    .map_err(|_| "Series workers stopped before completing the source.")??;
                pending.insert(ordinal, result);
                pending_peak = pending_peak.max(pending.len());
                while let Some(result) = pending.remove(&next) {
                    control.check()?;
                    consume(frames[next], result)?;
                    next += 1;
                    // Only ordered consumption releases a queue slot. Even a
                    // slow first frame cannot create an unbounded reorder queue.
                    if dispatched < frames.len() {
                        jobs.send((dispatched, frames[dispatched]))
                            .map_err(|e| e.to_string())?;
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
        drop(jobs);
        // Release blocked senders before joining on cancellation/consumer error.
        drop(completed);
        for handle in handles {
            handle
                .join()
                .map_err(|_| "Series worker failed to shut down.")?;
        }
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
