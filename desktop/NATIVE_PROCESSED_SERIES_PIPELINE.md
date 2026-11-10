# Corrected images and dynamic masks in native series

Batch and Map use Dioptrin's **`Dynamic1dPlan` and `Dynamic1dWorker`** for
corrected images and per-frame masks. The default polygon/subpixel path calls
`Integrator::prepare_dynamic1d` with dynamic masking and CSC execution. The
same dynamic-plan type can own the existing compatibility/sector LUT and custom
normalization, retaining those scientific settings. The desktop pins pushed
Dioptrin revision `41174d85ce0eca17ac3b61fa1eb19ad97bf0055a`.

One immutable plan is shared across the source's workers. Its float64 CSC
weights and per-pixel normalization are prepared once. Each worker retains its
own signal, normalization and variance histograms, decoded native frame buffer,
oriented float64 image, propagated variances and plugin caches. Masks and bin
denominators change for each frame; neither is baked into a fixed-mask table.
The fixed-mask, uncorrected route keeps its existing `Fixed1dPlan` pipeline.
Uncorrected pyFAI-compatible series also run in parallel using a shared
`FixedCsr1dPlan`, retaining their existing compatibility weights and arithmetic;
see the [full-file pyFAI series comparison](NATIVE_PYFAI_SERIES_PIPELINE.md).

## Corrections and uncertainty

Backgrounds, flat fields, transfer references, cBN/detector absorption and
plate/slab/cylinder/sphere absorption are supported. Geometry/material-dependent
maps are prepared once per source and shared; workers apply the existing
ordered operations to each exposure. Original counting variance and optional
background noise are propagated through every divide/multiply. Supplied pixel
variances go directly to `Dynamic1dWorker`, preserving uncertainty when the
background-subtracted intensity is negative.

The implementation deliberately retains division versus multiplication and the
original operation order. Combining all gains into one product can move a pixel
across an exact mask threshold by a rounding bit. A native unit test verifies
**bitwise identical corrected pixels and variances** against the established
pipeline for all absorption types, transfer/flat/background combinations,
background-noise choices and negative/zero/positive detector factors.

The existing [counting-uncertainty contract](NATIVE_CORRECTION_UNCERTAINTY_PARITY.md)
and its assumptions remain applicable. Integration can differ by float64
summation/FMA rounding; normalization and variance use the original division
and square-root order. Azimuthal spread retains the native plan's row-statistics
calculation.

## Per-frame masks and scheduling

Threshold, Cosmic Ray and Spot masks are computed from each frame's corrected
float64 values. User masks, detector acquisition masks and ROI restrictions
keep their existing combination semantics. Spot's geometry-dependent angular
bin indices are shared; plugin masks and caches remain private to workers.
Spot's user-mask-dependent bin membership is also shared. Spatial kernels reuse
private compact scratch and process contiguous rows; see the
[spatial-mask optimization and full-file measurements](NATIVE_SPATIAL_MASK_PERFORMANCE.md).
Threshold/Cosmic settings are extracted before pixel loops, avoiding repeated
JSON lookups without changing comparisons or statistics.

The source reader remains a frozen self-contained Bitshuffle/LZ4 HDF5 snapshot
with uint16/uint32 full-frame chunks. Transformations and unsupported source
layouts retain their existing native path. There is no Python fallback.
Start/stop/stride and file/frame order are preserved. Only the command worker
collects profiles, reduces Map windows and publishes progress/previews; silent
worker controls share cancellation without overwriting series totals.

The queue admits at most one outstanding result per requested worker slot.
Worker count is capped by selected frames and a conservative **4 GiB combined
worker payload** estimate covering decoder storage, float64 processing buffers
and plugin temporaries. Shared LUTs/correction maps, final series and allocator
overhead are separate. Eight workers fit the measured Threshold/correction
cases; heavier plugin scratch can reduce that number. Workers persist across
frames of a source and are joined before returning. Existing checkpoint/source
checks, cancellation and rollback preserve the preceding complete series.

## Tests and benchmark reproduction

Dioptrin's library tests cover concurrent masks, supplied variances, negative
signals, squared splitting weights, all-masked bins, invalid inputs, recovery
after failure, unchanged table ownership and histogram allocation reuse. The
desktop's numerical script compares both Batch and Map against the preserved
native executable across corrected/error-free data, all three plugins,
combined corrections/plugins, pyFAI/subpixel integration, sectors/spread,
disabled masks, multiple files and strided selection.

```sh
python desktop/scripts/native_processed_series_parity.py \
  --before /path/to/preserved/dioptas-processor \
  --after desktop/backend/target/debug/dioptas-processor

python desktop/scripts/native_processed_series_benchmark.py \
  --source /path/to/eiger_0000.h5 \
  --before desktop/backend/target/debug/dioptas-processor \
  --after desktop/backend/target/debug/dioptas-processor \
  --sequential-reference --repeats 1 \
  --output desktop/artifacts/native-series-pipeline/processed-eiger-results.json
```

The full-file comparison uses the **same optimized binary**, with
`DIOPTAS_SERIES_PARALLEL=0` for the sequential reference. Both variants therefore
include codec optimization and invariant mask-setting extraction; the measured
gain isolates series execution and correction-map preparation/reuse. The
preserved original executable is the separate numerical oracle.

All 625 Eiger frames use 2,000 bins, polygon splitting, polarization 0.965,
Poisson errors, named-detector geometry and the automatic acquisition mask.
The corrected case subtracts a 7-count background at scale 0.7 plus offset 1.2,
includes its counting noise and applies a nonuniform mean-normalized flat
field varying 0.8–1.2 across columns. Dynamic masking uses Threshold above
1,000; the combined case evaluates that threshold on corrected values.

Timing includes the complete native stdio command, per-command preparation,
worker creation, ordered collection, final selection and Map previews/reduction.
Initial geometry/plan warmup, process startup, exports/numerical checks and
Tauri rendering are excluded. File pages are warm and CPU resources are not
isolated. Results are processor command throughput, not screen presentation
rates. The receipt records binary hashes, worker/plan diagnostics and complete
float64 comparisons, and checks that the source size/mtime remain unchanged.

### Measured results — November 10, 2026

One paired full-file pass on the local M4 Pro, eight workers and Poisson errors:

| Case | Sequential Batch | Parallel Batch | Sequential Map | Parallel Map |
| --- | ---: | ---: | ---: | ---: |
| Background + flat field | 7.34 | 87.15 | 7.55 | 85.53 |
| Threshold Mask | 42.62 | 94.92 | 42.64 | 93.35 |
| Corrections + Threshold | 7.13 | 78.68 | 6.94 | 71.51 |

All rates are images/s. The corrected/combined cases improved approximately
10.3–11.9×; Threshold improved 2.2× against the sequential reference that already
has the invariant-setting optimization. Every parallel run used eight workers,
one source pipeline, all 625 profiles, and no additional dynamic-plan builds
after warmup.

All **12 full-file runs** passed comparisons of every stored float64 profile,
radial axis, counting std and Map window value. Maximum relative L2 differences
were **4.44e-15** for intensity, **1.43e-15** for counting std and **2.24e-15** for
Map values. Maximum absolute differences were 1.04e-8, 6.93e-14 and 7.96e-12,
respectively; comparisons use rtol 3e-12 and atol 1e-8. The source stayed unchanged.
[Full-file receipt](artifacts/native-series-pipeline/processed-eiger-results.json).

Before the subsequent [spatial-kernel optimization](NATIVE_SPATIAL_MASK_PERFORMANCE.md),
default spatial plugins were measured on **the first 16 original Eiger
frames**, in Batch with Poisson errors. These are sampled measurements, not
full-file or Map throughput claims. The payload budget admitted three workers:

| Default plugin | Sequential | Parallel |
| --- | ---: | ---: |
| Spot Mask, median + smoothing | 2.01 | 4.31 |
| Cosmic Ray Mask, two passes | 1.27 | 2.72 |

Both improved about 2.14× and matched the sequential profiles/counting std
within 3.88e-16/1.91e-16 relative L2. These heavier mask computations remain much
slower than Threshold. [Sampled spatial-plugin receipt](artifacts/native-series-pipeline/spatial-masks-eiger-results.json).

The full Rust desktop suite, strict Clippy, ten preserved-executable numerical
scenarios across Batch/Map, and five real-stdio cancellation/source-change
tests pass. Headless Chromium/WebKit Map progress checks pass, including
unfinished cells, retained regions/expressions and detached previews. Dioptrin
passes 214 Rust library tests and strict library Clippy. No visible test window
was opened.
