# Native integration qualification — 2026-11-07

This ledger covers the default Rust processing executable on `codex/native-backend`.
The Rust child does not import or execute
Python; independent comparison programs use Python only to calculate references.
The existing React controls, binary raster contract and local stdio owner remain.
There is no scientific HTTP service. Dioptrin is now the default native engine.

## Implemented boundary

- Image → corrected f64 detector → 1D pattern/2D cake, automatic/fixed bins,
  2θ/Q/d axes, polarization/solid-angle controls, Poisson errors, azimuthal spread,
  supersampling, CSC selection, finite and wrapped angular sectors, fixed ROI and
  dynamic plugins. A finite-sector adapter clips native radial/azimuth polygons;
  it avoids the library's periodic wrapping of all pixels into a narrow sector.
- Independent raw/processed images and histograms; image background scale/offset,
  mean-normalized flat response and cBN/OIADAC absorption corrections.
  Transfer, plate/slab absorption and corrected-count errors are qualified in the
  [correction and uncertainty ledger](NATIVE_CORRECTION_UNCERTAINTY_PARITY.md). Scientific
  buffers remain f64; display conversion to f32 does not change original counts.
- Imported patterns, SmoothBruckner/Chebyshev backgrounds and ROI; overlays with
  capture/update, scale/offset, colors/visibility, ordering, matching and waterfall;
  XY/XYE/CHI/DAT/FXYE pattern export and background/image/cake output.
  [Batch Save](NATIVE_BATCH_EXPORT.md) adds transactional per-frame formats,
  stored statistics/background copies and active-view PNG.
- Linked detector/pattern/cake inspection uses subpixel coordinates and shared
  geometry; navigation retains reader options and dataset selection. Incoming-file
  polling waits for two stable observations, preserves the preceding state on a
  corrupt input and supports automatic pattern output. Multi-image add/average
  and staged TIFF output retain source data and reject existing output targets.
- Phase/material catalog, JCPDS/EOSMAT/CIF input, legacy peak tables and native
  PhaseSmith powder reflections. Peritheos supplies pressure/thermal calculation.
  The editor retains lattice/symmetry, EoS/thermal constructors and parameters,
  records/defaults/validity, atomic sites/space groups, Wyckoff/composition display,
  explicit documented tetragonal-perovskite assumptions and material export.
  Catalog records stay read-only; editing a copy retains source provenance and
  marks edited records deferred. The 234 authored core material documents and
  685 record annotations retain their source qualifications; optional numerical
  dataset packages are not bundled. Record documentation opens only after the
  explicit user action in the Tauri host.
- Batch [rectangle-to-waterfall overlays](BATCH_WATERFALL_PARITY.md) use exact Rust
  series slices and the shared overlay owner, with headless drag/cancel checks.
- Batch raw-file/range/stride loading, warm integration, stored selection,
  physical units, reversible normalization, processed HDF5/CSV save/load and
  neighboring folders. Map shares the same integration owner and immutable series:
  six ROI reductions, straight-edge background, bounded expressions, layout/
  snake/transpose/flips, blanks/exclusions, normalization, cubic display previews,
  contours, export, selected raw images and numbered incoming-file append.
  Admitted fixed-mask HDF5 series now use a shared CSC plan and persistent
  concurrent frame workers; see [pipeline scope, codec fix and measured throughput](NATIVE_SERIES_PIPELINE.md).
  Corrected/dynamic-mask series use the dedicated Dioptrin dynamic-plan/worker
  types with supplied variances; see [processed-series evidence](NATIVE_PROCESSED_SERIES_PIPELINE.md).
- Grouped integration/phase changes join chronological calibration Undo/Redo;
  mask history remains separate. No-op saves preserve Redo. Stable phase/overlay
  IDs reject stale editor operations. Settings and bulk operations publish
  transactionally. Progress/cancel bypass the worker queue; cancellation checks
  occur between stages and frames, not inside an individual library kernel.
- Explicit configured custom actions retain the existing settings/placeholder
  contract and execute direct argv, with bounded asynchronous output capture.

## Qt optimization sources and native implementation

Read-only Qt source: `2e34f09f` (`codex/batch-map-startup-reuse`) and combined
preview `9c73ffb3` (including `d6d479dc`). No reference checkout was modified.
Pinned native dependencies:

| Library | Revision | Role |
| --- | --- | --- |
| dioptrin-io | `344011962df431a6a47e3a3fb727aa9c65df3131` | Typed readers, bounded combined raw-HDF5 fold |
| Dioptrin | `5e245da8c3df4735f2d0d28933c22fe16ac70c1f` | Shared fixed plans, integration, geometry/calibration |
| PhaseSmith | `f0925305c70fc8ea5965d14f03aa51b8399621d8` | Powder, crystallography, CIF, Bruckner |
| Peritheos | `3c79b1aedf28c348a49cc22d9f24d92895546283` | EoS/thermal evaluation and authored core documents |

The owner retains at most one pattern plan, cake plan and combined raw source.
Unchanged source/settings reuse the warm state. Eligible native-endian, full-frame
u16/u32 Bitshuffle/LZ4 HDF5 inputs decode once to typed display pixels plus a
prepared f64 pattern; preparation keys include geometry, source shape, dataset,
mask, unit, binning and error/correction settings. Requested/resolved source
identities are frozen and checked before publishing. External/VDS layouts,
other codecs, corrections and dynamic plugins use ordinary native resident
integration without retrying a second file read. `DIOPTAS_COMBINED_HDF5=0` selects
that native baseline for diagnostics. Decoder workspace is bounded to 256 MiB;
default workers are eight (`DIOPTAS_INTEGRATION_THREADS`, bounded 1–256).

Bulk discovery reads metadata, releases each reader, then opens one file at a
time. It checks frozen identities and uniform shapes, reuses the same warm 1D
owner and restores the selected session before publishing the complete matrix.
It does not compute an unused cake for every bulk frame. Source mutation or
cancellation cannot publish a partial Batch/Map. Live display buffers use
parallel BLAKE3 identities; owned project data retain SHA-256 identities.

## Shared interactive loading and navigation (2026-11-08)

File opens and in-file Next/Previous now call the same `Engine::load_frame`.
Batch selection and Map selection reach that loader through
`select_series_mode` → `open_image_model`. Configuration browsing and incoming
file processing also use `open_image_model`. The loader selects combined HDF5
decode/integration when admitted, parallel native pixels otherwise when
supported, and the ordinary native reader exactly once for other inputs.
Corrections, dynamic masks, source validation and detector-size confirmation
retain their existing admission and rollback behavior. Bulk Batch/Map work
retains its shared numerical kernels and avoids unused detector/cake display work.

All modes use the same `Raster::image`, `Buffer` fingerprints and binary packet
writer. Integration/Map retain their shared raster/pattern renderers. The
development profile now optimizes BLAKE3 and the JSON float formatter (`zmij`),
which were missing from the existing numerical-library optimization list.
Packet serialization borrows the response metadata instead of constructing an
intermediate JSON tree. Time-order browsing resolves the source directory once,
with per-file resolution only for symlinks; each click still rescans for new
arrivals. Image arrows and direct frame selection use the same quiet ordered
selection queue as Batch/Map, retaining every rapid click without disabling the
whole interface.

Matched local development-build medians, 12 alternating selections after warmup,
1,000 radial × 360 cake bins, baseline `032771df` versus the shared changes:

| Path | Before | After |
| --- | ---: | ---: |
| 4 MP TIFF, Next/Previous with integration/cake | 66.77 ms | 21.70 ms |
| 4 MP TIFF, By Time in a 2,002-file folder | 75.73 ms | 25.95 ms |
| 4 MP TIFF, Batch selection | 67.69 ms | 23.02 ms |
| 4 MP TIFF, stored Map selection | 40.49 ms | 11.24 ms |
| Eiger 9M, Next/Previous with integration/cake | 162.84 ms | 72.32 ms |
| Eiger 9M, stored Map selection | 118.88 ms | 54.98 ms |

These intervals cover real Rust stdio through the complete requested response,
with warm local filesystem pages and no CPU isolation; they exclude Tauri IPC,
GPU and physical-display latency. The Eiger frame is 3,262 × 3,108 pixels.
The comparison checks all 13 image/Batch/Map entry-point scenarios: detector,
mask and cake bytes, patterns and histograms match exactly. Only display Auto
limit metadata permits four machine epsilons of relative rounding (observed
differences below 4e-12); source/calibration metadata and scientific outputs
remain exact. Plans are reused: this improvement does not skip integration or
reduce detector resolution. Remaining Eiger time is principally decoding and
the requested integration/display preparation.

To reproduce from `desktop/`, build the baseline and current processor in
separate worktrees, then run:

```sh
node scripts/image_navigation_benchmark.mjs --all-paths --baseline /absolute/path/to/baseline-processor --eiger /absolute/path/to/eiger_0000.h5
node scripts/image_navigation_ui_benchmark.mjs --baseline /absolute/path/to/baseline-processor --compare-busy-ui
```

Receipts are under ignored `desktop/artifacts/image-navigation/`. The headless
UI probe preserves binary-buffer identity and separates response-to-paint time;
its Playwright bridge replaces Tauri IPC, so its absolute click-to-paint totals
are not native-application latency measurements. Rust checks cover file-order
filtering, late arrivals, symlinked files/folders and byte-identical packet
framing. Headless Chromium/WebKit cover stable controls, boundary notices,
rapid Next/Previous order and later arrivals.

## Native button-to-display timing (2026-11-08)

The native navigation benchmark runs the actual React App in a private Tauri
WKWebView, with the Rust worker, binary IPC and shared GPU renderers. It activates
the real Integration Next/Previous buttons and records response receipt,
hydration, React publication, detector/cake submission and pattern rendering.
After the new frame has rendered, it waits for GPU completion and two animation
frames. The reported display interval includes a WebKit presentation opportunity;
it does not measure OS input dispatch or physical LCD scanout. The extra animation
frame makes it a conservative presentation estimate.

Matched local debug builds, warm filesystem pages, 1,000 radial × 360 cake bins,
1440 × 908 CSS pixels at device-pixel ratio 1, visible foreground windows:

| Integration browsing | Before host changes | After host changes |
| --- | ---: | ---: |
| 4 MP TIFF, first Next (one sample) | 140 ms | 79 ms |
| 4 MP TIFF, cached Next/Previous (13 samples) | 79 ms | 59 ms |
| Eiger 9M, 12 successive new frames | 339 ms | 139 ms |
| Eiger 9M, cached Next/Previous (13 samples) | 138 ms | 117 ms |

Values are medians, with no CPU isolation. All final samples were visible and
focused; screenshots confirm the detector and pattern were displayed. These
before values already include the shared loader optimizations above. They are
not timings for the earlier unoptimized worker or predictions for release builds.

The largest additional bottleneck was the native host's packet allocation:
extending a nonempty `Vec` with `resize` initialized a 42 MB payload byte by byte
in the debug host. Direct zeroed allocation reduces initialization from roughly
140 ms to 0.23 ms; payload reading itself takes about 5.5 ms. The host also used
to construct and discard a complete duplicate JSON metadata tree. It now
deserializes only routing fields, validates/skips the remaining JSON and forwards
the original metadata and binary bytes unchanged. Optimizing the host's
`serde_json` development dependency further reduces header parsing. Eiger header
parsing falls from about 31 ms to 12 ms overall. Bounds, truncation checks,
response routing and scientific precision remain intact.

Remaining time is mostly worker preparation and transfer: final native IPC is
about 94 ms for a new Eiger frame and 80 ms for a cached one. JavaScript hydration
takes 4–6 ms, response-to-detector submission about 12 ms, and the final paint
wait about 18–22 ms. Texture uploads total about 2 ms, and pattern drawing is
typically below 1 ms. Thus these samples do not identify GPU rendering as the
dominant remaining delay. The shared host fix applies to every mode using binary
responses, including image opens, Integration, Batch and Map selections.

To reproduce from `desktop/` after preparing the debug worker:

```sh
npm run backend:prepare -- --debug
node scripts/image_navigation_native.mjs --foreground --eiger /absolute/path/to/eiger_0000.h5 --output artifacts/native-navigation/current
```

Keep the explicitly printed private benchmark window visible and focused; on
macOS it may need to be raised after launch. The runner uses private WebKit
storage, never substitutes the bridge, and closes only its own process and
worker. `--no-build --app /absolute/path/to/baseline-host` can measure a saved
host built with the same benchmark hooks and resource layout. Hooks are enabled
only by `VITE_DIOPTAS_NAVIGATION_BENCHMARK=1`; normal builds expose no benchmark
control API. Optional host timings use `DIOPTAS_TRACE_NATIVE_NAV=1`.

Local receipts, stage traces and screenshots are under ignored
`desktop/artifacts/native-navigation/before-focused/` and
`desktop/artifacts/native-navigation/optimized-final/`. Malformed headers,
byte-identical forwarding, cached-buffer omission, child cleanup and existing
transport behavior pass the 25 native host tests; all 71 frontend unit tests pass.

## Independent checks and limits

- Core synthetic u32 Bitshuffle fixture: exact original display counts, frame and
  dataset changes, gzip fallback, fixed ROI and dynamic-mask admission; combined
  and resident f64 intensities/Poisson terms agree at rtol 2e-12. Unchanged frames
  build one pattern and one cake plan. Analytically normalized images establish
  expected 700 intensity in populated bins, including wrapped sectors and
  supersampling. An opposite-sector fixture excludes distant high counts. An
  independent NumPy point-to-bin matrix built with pyFAI geometry checks a
  supersampled sector's weighted intensity and merged-pixel Poisson propagation
  at rtol 3e-12, atol 1e-9.
- Corrections: exact f32 display and f64 readouts against the Python formulas;
  Bruckner and NumPy-scaled Chebyshev comparisons. Pattern exports are read back
  independently; masks are decoded by NumPy/Pillow/FabIO, including stored rows,
  explicit flip and Undo. Linked subpixel angles are checked with pyFAI.
- Series: six-frame batch against individual integrations, f64 processed-HDF5
  readback and bidirectional loading through the actual Qt BatchModel, normalization restore, 12 Map reduction/background combinations
  against Qt NumPy models, expressions/layout/exclusions and SciPy order-3 cubic
  interpolation. Selection retains the Map's stored unit independently of global
  Integration settings and fresh reintegration is not replaced by stored data.
  Live append checks stable numbered continuations, corrupt-file isolation and
  successful retry after repair, including files below the new highest number.
- Phases: JCPDS Au/Mo at four conditions including negative pressure; fcc CIF
  reflections/intensities and Moyo site metadata against the existing adapter;
  Gold pressure/thermal conditions, all 11 editable room-temperature EoS
  constructors, four thermal constructors, three ranked formula searches and
  both explicit tetragonal-perovskite assumptions. Read-only/copy/deferred
  provenance, record editing and EOSMAT round trips are checked independently.
  These fixtures qualify the tested conditions,
  not every catalog record, detector geometry or pressure/temperature range.
- Real stdio tests remove Python and PATH from the child, exercise intermediate
  bulk progress, queued/in-flight cancellation and changed-source rollback.
  Headless Chromium and WebKit exercise the assembled detector/pattern/cake,
  phase catalog/editor and Map UI. No visible/native window is opened.

Local gates: 27 native tests with Dioptrin and 21 without it, strict Clippy in
both feature modes, 19 Tauri host tests, 59 JavaScript tests and the production
frontend build pass. The five independent numerical/workflow scripts and real
stdio cancellation tests pass. Chromium/WebKit calibration, masking and assembled
integration/phase/Map checks report no command or rendering errors.

### Matched Eiger measurement

Read-only source: `Dioptrin/test_data/eiger_0000.h5`, 5,687,072,680 bytes,
625 × 3262 × 3108 u32, dataset `entry_0000/instrument/eiger/data`, full-frame
Bitshuffle/LZ4 chunks. Sampled frames: 0, 312 and 624, two repeats per mode,
2,000 radial/90 cake bins, eight workers, optimized development packages.
Compressed chunks were OS-page-cache warm; mode passes were sequential and CPU
resources were not isolated. Timing includes native stdio open through the
complete image/pattern/cake response; it excludes Tauri rendering/GPU time.

| Mode | Resident median | Combined median | Lower elapsed time |
| --- | ---: | ---: | ---: |
| Intensity | 0.6743 s | 0.4221 s | 37.4% |
| Poisson | 0.6947 s | 0.4407 s | 36.6% |

Both routes built one pattern and one cake plan. Independent Bitshuffle decoding
verified every sampled stored display pixel after orientation/f32 conversion and
selected scientific f64 readouts exactly. Resident/combined intensity and Poisson
outputs agree at rtol 2e-12, atol 1e-9. The benchmark uses an explicit 75 µm flat
uniform manual geometry with the adjacent PONI's numeric values and TIFF mask;
it does **not** qualify that PONI's named Eiger detector/orientation. Three sampled
frames do not qualify all 625 frames. This native result is separate from the
Qt preview's historical 20.6% result.

## Reproduce

From the repository root, with the test-only Python environment installed:

```sh
cargo test --locked --manifest-path desktop/backend/Cargo.toml --all-features
cargo test --locked --manifest-path desktop/backend/Cargo.toml --no-default-features
cargo clippy --locked --manifest-path desktop/backend/Cargo.toml --all-features --all-targets -- -D warnings
cargo clippy --locked --manifest-path desktop/backend/Cargo.toml --no-default-features --all-targets -- -D warnings
# Build last: no-feature integration tests also build the processor executable.
cargo build --locked --manifest-path desktop/backend/Cargo.toml --all-features
.venv/bin/python desktop/scripts/native_integration_core_parity.py
.venv/bin/python desktop/scripts/native_processing_parity.py
.venv/bin/python desktop/scripts/native_series_parity.py
.venv/bin/python desktop/scripts/native_phase_parity.py
.venv/bin/python desktop/scripts/native_io_history_parity.py
.venv/bin/python desktop/scripts/generate_native_resources.py --peritheos /path/to/pinned/peritheos
cd desktop
npm run build
npm test
npm run test:native-integration
npm run test:native-integration-transport
npm run test:native-calibration
npm run test:native-calibration-transport
npm run test:native-mask
npm run test:native-mask-transport
```

Receipts and headless screenshots are written under ignored
`desktop/artifacts/native-integration/`. `native_eiger_benchmark.py --help` lists
required read-only source/PONI/mask inputs for the large benchmark. Resource
regeneration is explicit (`generate_native_resources.py --write`); the default
mode compares JSON and verifies authored hashes/helper provenance.

## Remaining whole-application gates

Project `.dio` persistence and multiple configurations are now implemented in
the [project migration stage](NATIVE_PROJECT_PARITY.md). Image transforms and
geometric masks are implemented in the [following stage](NATIVE_GEOMETRY_MASK_PARITY.md).
Named/distorted detector geometry is now implemented within the
[detector qualification boundary](NATIVE_DETECTOR_PARITY.md). Full reader-semantic
coverage and cross-platform native installer qualification remain.
Batch HDF5 preserves processed series; `.dio` retains supported project state. Numerical
fixture agreement is not a universal scientific equivalence proof. These gaps
are explicit native errors; the backend never silently switches to Python.

Cylinder and sphere sample absorption, including optional capillary walls, are
qualified separately in the [round-sample ledger](NATIVE_ROUND_SAMPLE_CORRECTION_PARITY.md).
They use corrected physical ray paths and uniform footprints in Rust, with
project ownership, propagated counting std and independent numerical checks.

## pyFAI-compatible full pixel splitting — 2026-11-08

Settings → Integration offers **Pixel splitting (pyFAI-compatible)** alongside
the existing polygon and subpixel methods. The mode is owned by each detector
configuration, survives `.dio` projects and development handoffs, and applies to
1D patterns, cakes, combined detectors and fresh Batch/Map integration.
Both algorithms execute in Rust/Dioptrin. The 1D kernel is Dioptrin's
`IntegrationMethod::PyfaiFull` / `lut::build_lut1d_pyfai_csr`; 2D reuses its
shared-grid full-histogram compatibility rasterizer. Corrections and supplied
count variances retain their existing normalization and squared-weight propagation.

Compatibility is approximate: singular direct-beam pixels use nonnegative
detector-plane sampling; negative numerical fractions are discarded. 1D azimuth
selection follows pyFAI's intersecting-pixel convention; ordinary polygon sectors
retain their fractional clipping behavior. Fused compressed-input integration is
not selected for this desktop mode; resident processing remains entirely Rust.

`desktop/scripts/native_pyfai_splitting_parity.py` compares matched effective
edges against independent pyFAI `fullSplit1D_engine` and `fullSplit2D_engine`
references (2θ/Q/d, correction on/off, full/finite/wrapped azimuth), plus masks,
warm reuse, project restoration, Batch and combined-detector errors. The library
has its own Python oracle and Rust golden/plan tests. Headless Chromium/WebKit
checks verify that selecting the mode recalculates both products.

The full-splitting kernel is included in the public [Dioptrin 0.12.0 release](https://github.com/CPrescher/Dioptrin/releases/tag/v0.12.0).
The desktop's current pin, `41174d8`, includes Massif preprocessing, immutable
fixed-mask execution plans, opt-in resident layout selection and native dynamic
CSC workers with supplied variances on top of that release. The splitting weights and
compatibility arithmetic are unchanged; see the
[cached-path verification](PYFAI_CACHED_PERFORMANCE.md). It has no local-path dependency. The centered-detector
full-azimuth cake case differs in two bins whose pyFAI reference weights are
−5.55e-9 and 3.75e-8. Bins with absolute reference weight ≥1e-6 agree within
the cake tolerance; the receipt retains every difference. No bitwise boundary
compatibility is claimed. Dioptrin 0.12.0 publishes this method in the Rust and Python APIs.

Settings → Integration now offers CSR (default), CSC and optional Automatic for the
polygon/subpixel 1D execution layout. Forced CSC retains its original arithmetic;
ordinary CSR can differ by floating-point reduction order. Automatic uses a broad size/bin estimate for
resident frames, leaving streamed/parallel workers on
CSC. See [the matched detector/bin study](INTEGRATION_LAYOUT_CROSSOVER.md).

## Batch backgrounds (November 10, 2026)

Native per-series Smooth Bruckner/Chebyshev extraction, original/subtracted
overview display and source-axis range cutting are now qualified independently
against Qt. Source intensities, normalization, counting std, Map ownership and
project/configuration state remain separate. See [native Batch backgrounds](BATCH_BACKGROUND_NATIVE.md)
for the numerical references, progress/cancellation, headless checks and bounds.

Batch pattern-background inheritance: new raw integrations now use the active
Integration pattern background, including its ROI and loaded background, and
start subtracted. Existing batches now update automatically on background edits and Undo/Redo,
with serialized live edits and shared progress/cancellation.
The same per-pattern calculation is reused; sources, counting std, Map ownership
and reversible originals remain intact. See [the background qualification](BATCH_BACKGROUND_NATIVE.md).

## Single-image compatibility input (2026-11-10)

Fixed-mask, uncorrected uint16/uint32 single-image pyFAI-compatible patterns now
read decoder pixels directly and schedule independent strict CSR bins in
parallel. This applies to file opens, frame navigation and explicit/setting-driven
recalculation in Rust Dioptas. Corrected/transformed/derived inputs, dynamic masks
and azimuthal spread retain their existing resident route. Full Eiger before/after
results are bitwise identical: the integration stage improves by approximately
12%, while complete detector-loading latency remains near 29–30 ms. First-use
source-address preparation adds work. See the [full single-image profile,
benchmarks and verification](NATIVE_PYFAI_SINGLE_IMAGE_PERFORMANCE.md).

## Native display and transfer profile (2026-11-10)

Display statistics batch repeated integer sentinels without changing their
counts or retained-cache bounds. Aligned binary rasters use packet views;
source-cache accounting includes shared backing storage. Detector and pattern
renderers reuse allocated GPU storage and retain allocation/error validation.
Matched native GUI navigation is approximately 19–26% faster to completed GPU
work on the Eiger qualification; calibrated file-opening latency remains near
80 ms. Float64 outputs, display metadata and transported pixels remain bitwise
identical, and actual detector/pattern GPU readbacks match at the same display
resolution. See the [native GUI profile and verification](NATIVE_DISPLAY_TRANSFER_PERFORMANCE.md).
