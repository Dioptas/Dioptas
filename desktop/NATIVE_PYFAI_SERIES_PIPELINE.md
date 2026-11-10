# Parallel pyFAI-compatible Batch and Map integration

This document records the initial frame-parallel implementation. The subsequent
[direct decoder-input optimization](NATIVE_PYFAI_SERIES_THROUGHPUT.md) removes its
float64 expansion and extra worker handoff, while retaining identical result bits.

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

## Native GUI follow-up

An isolated Tauri WKWebView run of the normal Batch load action confirms the
new processor route through production binary IPC, normal React processing,
GPU completion and paint opportunities. All commands process the full 625
frames at 2,000 bins, with no corrections or dynamic masks:

| Poisson errors | First load, seconds | First load, images/s | Repeated load, seconds | Repeated load, images/s |
| --- | ---: | ---: | ---: | ---: |
| Off | 5.563 | 112.35 | 5.214 | 119.87 |
| On | 5.005 | 124.88 | 5.423 | 115.25 |

Each run reports 625 frame-parallel integrations, eight workers and visible
live images/s in the status line. The previous full-file native GUI baseline
was approximately 100 images/s. These are single GUI passes without CPU
isolation; differences between first and repeated loads are not a scaling law.
Initial image/calibration setup and the OS picker are excluded. Physical LCD
scanout is not measured. [GUI receipt](artifacts/native-pyfai-series/gui.json).

The test reused the existing GUI harness with the newly built processor and
a private WebKit store, kept its own window visible without requesting keyboard
focus, and closed only that test's app/processing child. The existing user
preview remained running. Detailed native traces and captures are retained at
`/Users/clemens/Codex/dioptas-pyfai-series-20261110/gui`.

## Regression checks and reproduction

All 182 Rust tests and strict all-target Clippy pass. Eighteen preserved-binary
numerical scenarios cover both Batch and Map, multiple files, strided selection,
static/dynamic/disabled masks, errors on/off, corrected data, Q/d units,
sectors, azimuthal spread and solid-angle correction disabled. Nine real-stdio
transport scenarios verify cancellation and changed-source rollback, including
raw pyFAI-compatible integration and its spread path.
Headless Chromium/WebKit checks with `DIOPTAS_MAP_TEST_METHOD=pyfai_full` also
pass, including partial/unfinished Map cells, retained regions/expressions,
detached previews and measured progress rates. [Validation summary](artifacts/native-pyfai-series/validation.json),
[headless receipt](artifacts/native-pyfai-series/headless-map.json).

```sh
python desktop/scripts/native_pyfai_series_benchmark.py \
  --source /path/to/eiger_0000.h5 \
  --before /path/to/preserved/dioptas-processor \
  --after desktop/backend/target/debug/dioptas-processor \
  --output /tmp/pyfai-series/results.json
python desktop/scripts/native_processed_series_parity.py \
  --before /path/to/preserved/dioptas-processor \
  --after desktop/backend/target/debug/dioptas-processor
DIOPTAS_MAP_TEST_METHOD=pyfai_full node desktop/scripts/native_map_progress_smoke.mjs
# Explicit isolated native GUI benchmark (opens a test window):
node desktop/scripts/image_navigation_native.mjs \
  --eiger /path/to/eiger_0000.h5 --series --series-method pyfai_full \
  --keep-visible --output /tmp/pyfai-gui
```

The first command writes the compact timing/parity receipt and uncompressed
float64 reference matrices to a sibling `oracles` directory. Initial image/
calibration preparation and GUI paint latency are separate from these timings.
