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
- Batch raw-file/range/stride loading, warm integration, stored selection,
  physical units, reversible normalization, processed HDF5/CSV save/load and
  neighboring folders. Map shares the same integration owner and immutable series:
  six ROI reductions, straight-edge background, bounded expressions, layout/
  snake/transpose/flips, blanks/exclusions, normalization, cubic display previews,
  contours, export, selected raw images and numbered incoming-file append.
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
