# Parallel pyFAI-compatible Batch and Map integration

The native Rust desktop now admits uncorrected pyFAI-compatible image series
to the same bounded, ordered frame pipeline as corrected and dynamically masked
series. Supported self-contained Bitshuffle/LZ4 uint16/uint32 HDF5 sources use
persistent workers for the entire source. Other source layouts retain the
existing native path. `DIOPTAS_SERIES_PARALLEL=0` retains the serial reference.

## Shared plans and scientific behavior

For raw images with a fixed mask and no azimuthal-spread request, workers borrow
one shared **Dioptrin `FixedCsr1dPlan`**. This is the same cached plan used for
resident pyFAI-compatible integration, now held in an `Arc`. Its immutable
compatibility LUT, fixed mask and precomputed normalization are prepared once;
the resident and series paths do not clone or rebuild them per exposure.
Each persistent worker owns a reusable decoder buffer, oriented float64 input
buffer and a one-thread Rayon pool. This avoids nested CPU oversubscription
while retaining the existing CSR reduction and uncertainty arithmetic.

Corrected images and dynamic masks continue using shared `Dynamic1dPlan`
snapshots and private `Dynamic1dWorker` scratch. Raw pyFAI-compatible integration
with an azimuthal-spread request uses that same dynamic-plan route because it
also returns row statistics. Supplied correction variances, sectors, solid-angle
settings, polarization, units and mask semantics remain unchanged. Fixed-mask
CSR workers compute the established Poisson variance directly, so they need
no separate full-image variance buffer.

The existing four-GiB worker-payload budget, source identity checks, ordered
collection, frame selection, Map preview/reduction, cancellation and rollback
remain in force. Only the collector updates progress and the measured images/s
status. This change retains Dioptrin revision `41174d8`; it adds no Python
fallback or scientific HTTP service.

## Full Eiger benchmark — November 10, 2026

All **625 frames of `eiger_0000.h5`, 3262 × 3108 pixels each**, 2,000 radial
bins, pyFAI-compatible full splitting, CSR resident layout, polarization 0.965,
adjacent named-detector PONI and automatic acquisition mask. No background,
flat field or dynamic mask is enabled. Local Apple M4 Pro; optimized development
processor. The preserved executable is from desktop baseline `767953d7`.

Each figure uses median elapsed time from two full-file passes per variant,
with before/after order reversed in the second pass:

| View / Poisson errors | Before, images/s | Parallel, images/s | Before, seconds | Parallel, seconds | Speedup |
| --- | ---: | ---: | ---: | ---: | ---: |
| Batch / off | 108.29 | 128.41 | 5.772 | 4.867 | 1.19× |
| Batch / on | 104.13 | 129.38 | 6.002 | 4.831 | 1.24× |
| Map / off | 105.98 | 127.08 | 5.897 | 4.918 | 1.20× |
| Map / on | 101.40 | 128.95 | 6.164 | 4.847 | 1.27× |

All eight parallel measurements report **625 frame-parallel integrations,
eight worker starts, one source pipeline and zero additional pattern or dynamic
plan builds after warmup**. The old variant reports no frame pipeline. Its CSR
kernel already parallelizes bins within an exposure; eight frame workers do not
imply an eightfold speedup. The measured improvement is 18–27% while retaining
the strict CSR arithmetic and compatibility weights.

Timings include the complete native command, worker startup, ordered collection,
final selection and Map previews/reduction. Cake and calibration rings are not
requested, matching ordinary Integration image/Batch use. Initial image and
geometry setup, two-frame plan warmup, process startup, export/parity checks and
GUI rendering are excluded. OS file pages are warm and CPU resources are not
isolated. These rates are processor-command throughput, not screen refresh.

Every stored float64 intensity, radial coordinate and counting std, and every
Map value, is **identical** across all 16 full-file runs: maximum absolute
difference zero. All frames and their order are checked. The source size and
modification time remain unchanged. [Full receipt](artifacts/native-pyfai-series/results.json).

## Regression checks and reproduction

All 182 Rust tests and strict all-target Clippy pass. Eighteen preserved-binary
numerical scenarios cover both Batch and Map, multiple files, strided selection,
static/dynamic/disabled masks, errors on/off, corrected data, Q/d units,
sectors, azimuthal spread and solid-angle correction disabled. Nine real-stdio
transport scenarios verify cancellation and changed-source rollback, including
raw pyFAI-compatible integration and its spread path.

```sh
python desktop/scripts/native_pyfai_series_benchmark.py \
  --source /path/to/eiger_0000.h5 \
  --before /path/to/preserved/dioptas-processor \
  --after desktop/backend/target/debug/dioptas-processor \
  --output /tmp/pyfai-series/results.json
python desktop/scripts/native_processed_series_parity.py \
  --before /path/to/preserved/dioptas-processor \
  --after desktop/backend/target/debug/dioptas-processor
```

The first command writes the compact timing/parity receipt and uncompressed
float64 reference matrices to a sibling `oracles` directory. Initial image/
calibration preparation and GUI paint latency are separate from these timings.
