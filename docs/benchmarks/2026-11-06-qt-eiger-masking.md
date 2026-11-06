# Qt Dioptas processing benchmark with different masks

## Thread-count correction (2026-11-06)

Fixed-mask batch/map paths used one integration worker with two threads per worker (the native API default), plus one decode worker. Dynamic per-frame paths used one Rayon/OpenMP thread. Global RAYON_NUM_THREADS=1 did not constrain private batch pools. The newer scaling benchmark explicitly sets num_threads=1 per batch worker.

Measured 2026-11-06 using the actual Qt application's BatchModel and MapModel
entry points. Includes file opening, HDF5 reading/decompression, orientation and
image preparation, mask computation and combination, normalization, integration,
result collection, and map reduction. It does not render the GUI.

## Results

Median frames/s over three warmed four-frame runs per case and workflow.
One integration worker, one decompression worker, and one Rayon/OpenMP/BLAS
thread. Fixed-mode streaming can overlap the decoder and integration workers;
this is a bounded-concurrency benchmark rather than a claim of exactly one CPU
core. No Poisson errors, image scaling factor 1, no background subtraction.

| Masking | Batch fps | Map fps |
| --- | ---: | ---: |
| No mask | 11.81 | 15.40 |
| Static mask | 11.97 | 15.70 |
| Static + threshold >230 | 12.78 | 12.99 |
| Static + threshold >207 | 12.51 | 12.65 |
| Static + cosmic rays (defaults) | 1.59 | 1.57 |
| Static + Spot Mask (mean) | 1.92 | 1.96 |
| Static + Spot Mask (median) | 1.31 | 1.32 |

Fixed/no-mask cases used the native streaming batch iterator. Dynamic cases
used the native per-frame path with a newly computed mask and normalization
for each frame. Every measured run asserted the selected mask mode and dispatch
counts. Every output was checked against independent direct-native integration
using explicitly recomputed masks. Fixed results matched exactly; dynamic
relative L2 differences were at most 3.8e-16.

## Mask settings

The supplied static mask excludes 8.755% of pixels. All dynamic cases include
that static mask. Thresholds 230 and 207 are diagnostic values chosen to exercise
different mask densities, not detector saturation recommendations. Their total
masked fractions across the four frames were 9.32–10.84% and 11.53–15.95%.

- Cosmic Ray Mask: sigma 5, window 5, two iterations, minimum intensity 100.
- Spot Mask: 445 radial bins, sigma multiplier 3, one iteration, smoothing sigma
  1 and smoothing threshold 0.3; mean and median variants measured separately.
- The native Spot Mask C extension was available. OpenCV was absent, so its
  optional smoothing implementation was not used. Exact settings are in JSON.

## Interpretation

For light masks, file loading and ordinary Qt processing substantially reduce
the rate compared with the earlier predecoded-array benchmarks. Heavy mask
algorithms dominate the cosmic/Spot cases. These results should not be compared
directly with the old eight-worker 625-frame throughput or with kernel-only fps.

A separate warm-frame diagnostic verified one cosmic mask computation per frame,
but **two Spot Mask computations per frame**. `_update_plugin_masks()` first
refreshes geometry, causing an enabled geometry-aware plugin to recompute on
the previous image, and then refreshes the image, causing another computation.
This is a further optimization opportunity; no production masking behavior was
changed during this benchmark. The diagnostic's individual timings are not the
multi-frame throughput medians above.

## Input and measurement boundaries

Four full Eiger9M uint32 frames at indices 0, 208, 416 and 624 from the original
625-frame file, shape 3262 × 3108. Full pixel splitting, 2000 uniform 2theta
bins, solid-angle correction, polarization 0.965, float64 integration weights,
corrections and sums. Same calibration and supplied static mask as the earlier
Dioptrin comparison.

To exercise actual file loading with bounded run time, fixture preparation made
an APFS copy-on-write clone of the original file, resized only its dataset, and
copied the selected original compressed chunks into positions 0–3. Compression
parameters and chunk bytes were preserved without recompression. Every decoded
pixel was compared against the original before measurement. Preparation and
independent reference calculations are excluded from timing. The original file
was opened read-only; the temporary clone was removed on completion. Fixture
preparation currently requires macOS `cp -c`.

A first full run warmed each case's LUT/geometry/plugin state; its elapsed time
is recorded separately. Each subsequent timed run included its file loading.
Normal OS cache was warm, with no cache purge. Concurrent user work continued;
per-pass other-process CPU activity is recorded. Four-frame runs include more
per-file setup overhead per frame than long scans. These results are not a
cold-SSD benchmark or a complete 625-frame scan benchmark.

Runtime: published Dioptrin 0.8.0 with the current local Qt image-copy and
polarization-state optimizations. The unreleased Rust setter no-op fix was not
installed; Qt already avoids those redundant calls. Native kernel comparisons
against a newly built patch wheel are outside this measurement.

## Reproduction and artifacts

Run from `/Users/clemens/Programming/Dioptas`:

```sh
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 RAYON_NUM_THREADS=1 \
  .venv/bin/python -m scripts.benchmark_qt_eiger_masking \
  --hdf5 /Users/clemens/Programming/Dioptrin/test_data/eiger_0000.h5 \
  --poni /Users/clemens/Programming/Dioptrin/docs/benchmarks/2026-11-05-bslz4/calibration.poni \
  --mask /Users/clemens/Programming/Dioptrin/test_data/eiger_0000.mask \
  --output docs/benchmarks/2026-11-06-qt-eiger-masking.json
```

- [Raw results, settings, source hashes and chunk/frame hashes](2026-11-06-qt-eiger-masking.json)
- [CSV summary](2026-11-06-qt-eiger-masking.csv)
- [Warm-frame plugin call diagnostic](2026-11-06-qt-plugin-call-diagnostic.json)
- [Earlier model-only profile and copy removal](2026-11-06-dynamic-mask-profile.md)
