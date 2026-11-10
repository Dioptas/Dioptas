//! Bounded row parallelism for background operations. Arithmetic inside a row
//! remains ordered; workers only write disjoint scratch rows, never live state.
use crate::control::Control;
use rayon::prelude::*;
use serde_json::json;
use std::sync::{
    Mutex, OnceLock,
    atomic::{AtomicBool, Ordering},
};
use std::time::{Duration, Instant};

pub(crate) fn rows<S, I, F>(
    output: &mut [f64],
    bins: usize,
    start: usize,
    control: &Control,
    label: &str,
    initialize: I,
    work: F,
) -> Result<(), String>
where
    I: Fn() -> S + Sync,
    F: Fn(usize, &mut [f64], &mut S) -> Result<(), String> + Sync,
{
    if output.is_empty() {
        return control.check();
    }
    static POOL: OnceLock<Option<rayon::ThreadPool>> = OnceLock::new();
    let pool = POOL.get_or_init(|| {
        let threads = std::thread::available_parallelism()
            .map_or(1, usize::from)
            .min(3);
        rayon::ThreadPoolBuilder::new()
            .num_threads(threads)
            .thread_name(|i| format!("background-{i}"))
            .build()
            .ok()
    });
    let count = output.len() / bins;
    let workers = pool
        .as_ref()
        .map_or(1, |p| p.current_num_threads())
        .min(count);
    let chunk_rows = count.div_ceil(workers);
    let progress = Mutex::new((start, Instant::now()));
    let failed = AtomicBool::new(false);
    control.publish(json!({"running":true,"current":start,"total":start+count,"label":label}));
    let chunk = |(index, data): (usize, &mut [f64])| -> Result<(), String> {
        // Exactly one state per chunk, sharing the prepared SVD through Arc.
        let mut state = initialize();
        for (local, row) in data.chunks_exact_mut(bins).enumerate() {
            if failed.load(Ordering::Relaxed) {
                return Ok(());
            }
            control.check()?;
            if let Err(error) = work(start + index * chunk_rows + local, row, &mut state) {
                failed.store(true, Ordering::Relaxed);
                return Err(error);
            }
            let mut progress = progress.lock().unwrap();
            progress.0 += 1;
            if progress.0 == start + count || progress.1.elapsed() >= Duration::from_millis(40) {
                control.publish(
                    json!({"running":true,"current":progress.0,"total":start+count,"label":label}),
                );
                progress.1 = Instant::now();
            }
        }
        Ok(())
    };
    if let Some(pool) = pool.as_ref().filter(|_| workers > 1) {
        pool.install(|| {
            output
                .par_chunks_mut(chunk_rows * bins)
                .enumerate()
                .try_for_each(chunk)
        })?;
    } else {
        output
            .chunks_mut(chunk_rows * bins)
            .enumerate()
            .try_for_each(chunk)?;
    }
    control.check()
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::{background_fit::ChebyshevFit, batch_background::smooth_cancellable};

    #[test]
    fn uneven_parallel_rows_match_independent_serial_fits_bit_for_bit() {
        let x: Vec<_> = (0..97).map(|i| 1.0 + i as f64 * 0.1).collect();
        let data: Vec<_> = (0..37 * x.len())
            .map(|i| 100.0 + (i % 97) as f64 + 70.0 * (i as f64 * 0.13).sin().abs())
            .collect();
        let control = Control::default();
        let mut expected = Vec::new();
        for row in data.chunks_exact(x.len()) {
            let smoothed = smooth_cancellable(row, 3, 11, &control).unwrap();
            expected.extend(crate::pattern::chebyshev(&x, &smoothed, 8).unwrap());
        }
        let fit = ChebyshevFit::new(&x, 8).unwrap();
        let mut output = vec![0.0; data.len()];
        rows(
            &mut output,
            x.len(),
            0,
            &control,
            "Test",
            || (),
            |index, out, _| {
                let row = &data[index * x.len()..(index + 1) * x.len()];
                let smoothed = smooth_cancellable(row, 3, 11, &control)?;
                out.copy_from_slice(&fit.fit(&smoothed)?);
                Ok(())
            },
        )
        .unwrap();
        assert!(
            output
                .iter()
                .zip(expected)
                .all(|(a, b)| a.to_bits() == b.to_bits())
        );
        assert_eq!(control.progress()["current"], 37);
        assert_eq!(control.progress()["total"], 37);
    }
}
