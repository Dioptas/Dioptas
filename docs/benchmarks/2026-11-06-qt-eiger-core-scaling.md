# Qt Eiger masking: scaling to 4 and 8 threads

Measured 2026-11-06. Actual MapModel processing, with the Spot Mask double-refresh
fix and Qt image/correction-state reuse. Published Dioptrin 0.8.0. No production
parallel-frame masking implementation was added for this benchmark.

## Matched results

Median frames/s, three warmed runs per case and budget:

| Masking | 1 thread | 4 threads | 8 threads | 8 vs 1 |
| --- | ---: | ---: | ---: | ---: |
| Fixed mask | 18.68 | 18.68 | 18.63 | 1.00× |
| Threshold >230 | 13.75 | 17.27 | 17.89 | 1.30× |
| Cosmic rays | 1.53 | 1.56 | 1.72 | 1.12× |
| Spot Mask, mean | 3.49 | 3.70 | 3.75 | 1.08× |
| Spot Mask, median | 2.42 | 3.27 | 3.34 | 1.38× |

All 45 timed runs (360 patterns) passed independent direct-native reference
checks. All decoded-frame hashes and exact masks match across budgets. Largest
relative L2 difference against the independent references was below 1.2e-15;
float64 weights, corrections and sums were used throughout.

## What the thread budgets mean

- Dynamic masks: frames remain sequential in the current Qt path. Fresh worker
  processes were launched with `RAYON_NUM_THREADS=1/4/8` for within-frame native
  integration and `OMP_NUM_THREADS=1/4/8` for Spot Mask's native per-bin work.
  BLAS was limited to one thread. These are available thread counts, not CPU
  affinity or a guarantee that all threads remain busy. OpenMP reports 4/8 in
  the corresponding process results; a separate runtime probe confirmed the
  baseline limit of 1.
- Fixed-mask control: `num_workers=1/4/8`, explicitly **one native thread per
  worker**. One decoder worker throughout. Decoder and integration may overlap,
  so this configuration can use one additional decoder core. Actual average
  process CPU use is recorded separately.
- Cosmic-ray masking and most NumPy/SciPy/image preparation remain sequential.
  The Spot C extension parallelizes bin statistics, while packing pixels,
  allocating/copying arrays and the SciPy smoothing path retain serial work.
  OpenCV was absent. Dioptrin's integration can parallelize a frame, but does
  not parallelize the plugin computation around it.

## Interpretation

Four threads capture most of the gains seen here; moving to eight adds little.
Measured average process CPU use at the eight-thread budget was only about
1.0–1.5 cores across these cases, despite availability of more worker threads.
That is evidence that the full current processing path does not expose enough
parallel work to use eight cores continuously.

The fixed-mask control is already capped by its single-decoder/model pipeline
in this configuration: adding integration workers does not improve its rate.
Threshold masking gains about 30%, while the heavy mostly serial cosmic-ray
path changes little. Spot median benefits more from parallel bin statistics,
but serial stages limit the full-pipeline gain to about 38% at eight threads.
This is not evidence that Dioptrin's integration kernel itself cannot scale.

For substantially better throughput with expensive dynamic masks, the next
architectural step is multiple independent frame workers, each owning its mask
plugin state and integration context. This benchmark measures existing
within-frame parallelism; it does not prototype or claim multi-frame masking
throughput.

## Inputs and limits

Eight full Eiger9M frames at indices 0, 89, 178, 267, 356, 445, 534, 624 from
the same original bitshuffle/LZ4 file; 3262 × 3108 pixels. Temporary APFS clones
preserved original compressed chunks and filter metadata, and all decoded
pixels were checked. Source input was read-only; temporary clones were removed.

Same supplied 8.755% static mask for all cases. Dynamic cases add threshold >230,
cosmic defaults (sigma 5, window 5, two iterations, minimum 100), or Spot mean /
median (445 bins, sigma multiplier 3, one iteration, smoothing 1 / threshold .3).
2000 bins, full pixel splitting, solid-angle correction, polarization .965,
no Poisson errors, scaling factor 1, no background subtraction.

Timings include file opening, HDF5 reads/decompression, image processing,
masking, normalization/integration, result collection and map reduction. They
exclude GUI rendering, fixture/reference preparation, configuration construction
and a first warm run's LUT/plugin setup. The OS file cache was warm. Concurrent
user work was not stopped; other-process CPU load varied and is recorded. Small
changes, especially cosmic's roughly 12%, should not be read as precise causal
scaling gains. This is an eight-frame sample rather than full-scan/cold-SSD
throughput. A fresh 1-thread baseline was rerun, rather than reusing four-frame
results with different per-file overhead.

## Correction to previous fixed-path labels

Earlier fixed-mask reports set global `RAYON_NUM_THREADS=1`, but did not pass
`num_threads` to the batch API. Its private worker pools default to two threads
per worker. Their timing values remain unchanged and have been annotated. The
previous dynamic-mask measurements were correctly limited to one Rayon/OpenMP
thread. All fixed-path runs in this scaling comparison explicitly specify one
thread per worker.

## Reproduction

Use `scripts/benchmark_qt_eiger_masking.py` with `--frames 8 --repeats 3
--workflows map --cases static_mask threshold_230 cosmic_default spot_mean
spot_median --workers N --threads-per-worker 1`, for N=1,4,8 in **separate
processes**, setting `RAYON_NUM_THREADS=N OMP_NUM_THREADS=N OPENBLAS_NUM_THREADS=1`.
Use the same source, calibration and mask paths as the previous benchmark.

- [1-thread raw results](2026-11-06-qt-eiger-scaling-1.json)
- [4-thread raw results](2026-11-06-qt-eiger-scaling-4.json)
- [8-thread raw results](2026-11-06-qt-eiger-scaling-8.json)
- [CSV with speedups and CPU utilization](2026-11-06-qt-eiger-core-scaling.csv)

No production code changed for this measurement. Ruff, whitespace checks and
all numerical/dispatch checks passed. Benchmark scripts and results are local
and uncommitted.
