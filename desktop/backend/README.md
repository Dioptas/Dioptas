# Native backend migration

The native migration runs the existing React interface against a Rust
processing executable. It does not start or import Python. Tauri still owns
native dialogs and the processor's stdio pipes; no scientific HTTP server is
introduced. The normal preview continues to use its Python backend until the
remaining workflows have been migrated and qualified.

## Build and try

From `desktop/`:

```sh
# File input, display and masks; no Dioptrin dependency is compiled.
npm run backend:build

# Opt-in native Dioptrin engine for the integration workflow below.
npm run backend:build:dioptrin

# Explicit experimental Rust selection, with its own Vite port (1428).
npm run tauri:native-dev
```

Open a detector image and use the existing Image → Peaks → Fit → Validate
workflow. Enter pixel sizes and fit start values, pick measured rings, and use
Calibrate for a fresh fit or Refine to continue an existing geometry. Automatic
refinement retains the existing Massif/Blob, angular-width, intensity, and ring
count controls. Alternatively, load a supported `.poni` or enter complete
pyFAI-convention geometry before Integration. The raw CeO2 example remains
uncalibrated; its reference PONI is not used by picking/fitting tests.

For an embedded frontend, first run `npm run build` and
`npm run tauri:build -- --debug`, then start the resulting host with
`--backend=rust`. `--backend=python` selects the existing backend. The environment
alternative is `DIOPTAS_BACKEND=rust`; an explicit argument takes precedence.
Invalid backend names fail without launching a substitute.

The host finds a native processor beside its executable, then this checkout's
`desktop/backend/target/debug/dioptas-processor` (release for release hosts).
`DIOPTAS_NATIVE_PROCESSOR` explicitly overrides the executable. Build the native
processor in the matching profile for a release host. A missing native executable
produces a build instruction; it does not launch Python. Installer bundling of
the processor and cross-platform distribution qualification are still pending.

HDF5 and its lossless codecs build from pinned native dependencies. Rust, a C
compiler, CMake, and Git are build prerequisites. There is no installed Python,
NumPy, h5py, FabIO, or pyFAI requirement for the Rust processor. The Python
reference environment is used only for migration tests.

## Implemented boundary

- Independent `dioptrin-io` input, pinned to source revision
  `cf33ecf89c1aaafa95982df491d90a38e15c2332`, including compressed TIFF/EDF/CBF,
  native formats, detector containers and HDF5. Only enabled reader features
  are admitted. JPEG/JPEG2000 and sparse reconstruction are not enabled in this
  initial consumer.
- Original typed samples and stored row order are retained separately from the
  f64 scientific view. Scientific rows flip exactly once to Dioptas's existing
  bottom-left convention. Full-resolution f32 display buffers never replace
  scientific samples. Complex/color data and integer values outside ±2^53
  require a future explicit scientific interpretation and currently fail.
- Single-source frame stepping, with immutable source checks. Shape changes reset
  incompatible masks and history, including equal-area shape changes.
- Explicit HDF5 dataset selection through `open_image.dataset`. Recognized
  Eiger/LImA/Lambda conventions use the native reader. External source graphs
  require explicit `follow_external_links: true`; no source search/relocation is
  inferred. CBF byte-offset dialect can be supplied explicitly as
  `cbf_dialect: "legacy32"` or `"extended64"`.
- The current binary packet contract: request IDs, content-addressed immutable
  buffers, deduplication, and omission only of buffers advertised by the window.
  No production pixel base64 encoding. One worker owns source and engine objects.
  Input size and pending work are bounded; progress bypasses the worker queue.
- Full-source asinh histograms; percentile, min/max, and mean ± 3 std Auto
  levels, with the existing repeated-gap rule. Scientific precision supplies
  detector and cake display statistics and pixel readouts. With the optional
  engine, calibrated detector readouts include native 2θ and pixel-scale angular
  resolution; the interface derives Q/d from the session wavelength as before.
- Brush/eraser, clear, mask Undo/Redo, use-mask and transparency. Mask history
  payloads are bounded to 128 MiB. Deferred mask operations clear stale products
  and calculate on the next explicit integration.
- All three bundled dynamic mask plugins run in Rust: Threshold Mask, Cosmic
  Ray Mask and Spot Mask. Their existing names, defaults, setting schemas and
  control order are retained. User/plugin masks remain separate and combine for
  display, peak picking and integration. Imprint bakes the current plugin mask
  into the user mask and disables the plugin in one Undo/Redo step. Invalid or
  cancelled changes preserve settings, masks, products and history.
- Flat uniform-pixel PONI loading/writing and complete manual pyFAI geometry.
  PONI and manual-command quantities use SI units and radians; the existing
  React form owns the display-unit conversions. Unsupported named detectors,
  orientations, spline corrections and PONI fields are rejected explicitly.
- With optional `dioptrin` feature: native PixelSplit 1D and cake integration,
  solid-angle and polarization corrections, 2θ/Q/d pattern coordinates, Poisson
  errors, and explicit radial/cake binning. Cake coordinates remain 2θ. Grid
  metadata follows pixel-corner extents and the engine's azimuth-bin-center
  convention. Native kernels are reused rather than copied or reimplemented.
- Atomic XY pattern and PONI exports. Other export formats are not migrated.
- Embedded native calibrant resources and session-owned custom `.D` references;
  wavelength-dependent ring availability and validation-only reference changes.
  Building the processor embeds the existing source calibrants without Python.
- Seeded native Massif or single-local-maximum peak picking, subpixel scientific
  coordinates, auto advance, grouped table edits/reassignment/multiple deletion,
  and compatible version-1 standalone peak files. Peak files retain the existing
  bottom-left row/column convention and validate dimensions, orientation,
  calibrant spacings, ring IDs and every coordinate before replacement.
- Seven independent fit checkboxes, fixed values, free wavelength, fresh-start
  versus continued fits, fitted residuals, and display ring contours. Native
  Dioptrin supplies the numerical fit and seeded Massif kernels; its fixed
  rotations retain the user's exact entered interval in the adapter.
- Staged automatic ring search/refit using the existing angular-band,
  mean-factor + population std threshold, upper-intensity ceiling and mask
  semantics. Massif uses Dioptrin's background/maximum extraction; Blob uses a
  native f64 difference-of-Gaussians scale space at 1/2/4/8 pixels. These native
  searches preserve the workflow and controls, not bit-identical pyFAI peak
  selections. The independent forward-model checks below qualify their outputs.
- Calibration snapshot Undo/Redo covers setup, constraints, picks/group edits,
  references, geometry load/manual edits, and complete fits. An automatic search
  is one history entry. No-op/failed commands retain Redo; new edits invalidate
  it. History is bounded by count and estimated payload; mask history retains
  the separate scope from the first native stage.
- Detached live progress previews contain candidate picks, active ring,
  fitted contours and RMS. Progress and cancellation bypass the scientific
  worker through stdio; queued cancellation is retained at worker start. A
  cancelled/failed fit restores geometry, picks, diagnostics, history and prior
  display products. Cancellation is checked between native calls/ring stages;
  a single library call is not interrupted internally. No Python fallback is
  used. A standalone non-calibration integration call remains noninterruptible.

The schema-only `src/correction_defaults.json` retains the existing React
controls' parameter definitions from `dioptas.desktop.integration.CORRECTIONS`
at migration base `b418d66b`. These corrections are disabled and their commands
remain unsupported; this file is not a scientific correction implementation.

## Remaining migration, in order

1. **Remaining calibration geometry:** Fit2D conversion, linked inspection,
   detector definitions, orientations, nonuniform pixel corners, distortion
   splines and their round trips. Detector rings use sampled display contours;
   fitting, integration and ring searches retain full-resolution samples.
2. **Image/mask/integration parity:** transformations, neighboring-file series,
   geometric masks and the separate LA Cosmic mask operation, background images, flat fields,
   absorption corrections, SmoothBruckner background, sectors/wrapped ranges,
   automatic bins, supersampling, statistics, other exports and autoprocessing.
3. **Phases and overlays:** native PhaseSmith and Peritheos APIs, material/CIF/
   JCPDS/EOSMAT adapters, search, editing, source provenance and legacy formats.
   Add dependencies only as each workflow is migrated.
4. **Persistence and multi-image work:** `.dio` read/write compatibility,
   configurations, Batch, Map, processed HDF5 and custom actions. Arbitrary
   third-party Python mask plugins need a native extension contract or individual
   ports; the bundled plugins are already native.
5. **Default transition and distribution:** cover the complete required command
   inventory and scientific reference corpus; build/test native libraries and
   installers on macOS, Windows and Linux; bundle the native executable and
   notices; then select Rust by default and remove the Python runtime from the
   new desktop's required distribution. The original Qt application can retain
   its Python source independently.

Dioptrin remains an optional Cargo feature. A complete native default must
resolve required numerical-engine availability while preserving that policy;
the existence of a native adapter does not establish detector-wide parity.
Unported commands and settings return explicit errors without Python fallback.
The existing UI still exposes unported controls in this development preview;
it is not yet a replacement for the everyday application.

## Native masking behavior

The implementation in `src/mask_plugins.rs` ports the bundled sources in
`dioptas/model/util/mask_plugins/`; `src/mask_plugins.json` is a static copy of
their names, descriptions, defaults and schemas at `a55e5bb1`. No Python or
SciPy executes at build time or runtime. Threshold and Cosmic do not require
Dioptrin. Spot uses its optional native full-resolution two-theta geometry;
without that feature, enabling Spot returns an explicit build instruction.
Without a calibration, an enabled Spot plugin returns an empty mask, matching
the existing plugin's behavior.

Cosmic retains the positive-neighbor mean/variance, reflected sliding windows
(including even sizes), intensity/z-score tests and iterative NaN removal.
Spot retains equal-width angular bins, user-mask exclusion, minimum bin size,
mean/std or median/MAD, and gap-aware Gaussian smoothing with cross dilation
and reach limits. Geometry/bin plans are cached separately from image results.
New frames, settings, geometry and user-mask changes invalidate the appropriate
results. Disabled caches cannot reappear on a different image. Automatic
calibration searches use detached plugin masks for the candidate geometry;
cancelled refinement cannot publish those candidates.

Spot statistics deliberately match the shipped **C accelerator**: one pass and
the upper middle element for even-sized median/MAD bins. Its `iterations` field
is retained for settings compatibility but has no effect, just as with that
accelerator. The older NumPy fallback averages the two middle values and can
iterate mean clipping, so it is not an interchangeable numerical reference.
Native smoothing follows the existing **SciPy** route: reflect boundaries,
truncate=4 and float32 intermediate mask fields; image statistics and geometry
remain f64. Optional OpenCV uses a different kernel extent/boundary convention
and is not claimed bit-identical. These choices remove runtime-dependent
selection between algorithms while retaining the current controls.

No extra user-directory or installed entry-point plugins were present in the
checked environment. Unknown plugin names fail explicitly; Python plugin files
are not imported by this backend. General mask shapes/morphology, mask file
import/export, and the separate LA Cosmic operation remain migration work.

## Qt integration changes to carry forward

Read-only source audit on 2026-11-07: the Qt checkout at
`/Users/clemens/Programming/Dioptas`, revision `2e34f09f`, includes shared
Dioptrin plans/selectable CSC (`62024fea`), warm Batch/Map startup reuse
(`81a23206`) and detector navigation/display improvements (`65c24a45`). The
separate Qt preview at `/Users/clemens/Programming/Dioptas-fused-preview`,
revision `d6d479dc`, adds combined fixed-mask HDF5 loading/integration. Neither
checkout was modified. Integration migration must retain these behaviors:

- Keep geometry/LUT/normalization state on one persistent owner worker, cache
  pattern/cake units with bounded memory, and only change native settings when
  they differ. Warm plans before admitting large Batch/Map queues; reuse those
  plans on the same worker and reconcile setters after bulk work.
- Distinguish fixed masks/ROI from dynamic masks and preserve CSC and
  supersampling selection. Bound input queues and decoder workspaces; queued
  frames must own their storage even when decoder buffers are reused.
- For eligible full-frame Bitshuffle/LZ4 native u16/u32 HDF5 inputs, decode once
  to original typed display pixels plus a prepared float64 pattern. Retain exact
  dataset/header selection, frozen file identity and the single row flip.
  Compatible sources can reuse the lookup through `set_source`.
- Reuse prepared results only for matching immutable pixels, effective mask,
  geometry, shape, bins, unit, polarization, supersampling and error terms.
  Pixel/correction/transform changes invalidate them. Unsupported layouts or
  settings use ordinary native loading/resident-array integration once; do not
  reread already decoded pixels to attempt an optimization. A changed source
  must fail atomically. Do not wait behind bulk work for an optional combined
  load; reject stale deliveries by image/settings revision.
- Retain float64 weights, sums, normalization and Poisson terms; compare original
  counts and results independently, and benchmark matched cold/warm workloads
  including load, display, task preparation, dispatch and product application.

The authoritative owners are Qt `model/integration_task.py`,
`model/loader/combinedHdf5.py`, `model/loader/fastHdf5.py`,
`model/Configuration.py` and `controller/async_job.py`. The combined API is newer
than this backend's pins: `dioptrin-io` preview `d91d567` (following `1fd538d`)
and Dioptrin fixed-plan revision `72e9b72` underlie that Qt benchmark. Its
`python-fused` bridge is reference adapter code, not a Python dependency to add
to this processor. Qualify and pin the corresponding Rust APIs before adoption.

The current native integration adapter still constructs a new integrator per
call and retains a separate f64 scientific image. It does **not** yet carry these
warm-plan/combined-load optimizations. The Qt report's roughly 20.6% lower warm
open-to-pattern latency is a source benchmark for one Eiger 9M fixture on macOS,
not a speed measurement of this native desktop. See the Qt preview's
`docs/benchmarks/2026-11-07-combined-hdf5.md` and provenance/validation receipts
for its exact scope and reproduction conditions.

## Verification

From the repository root:

```sh
cargo fmt --manifest-path desktop/backend/Cargo.toml --check
cargo clippy --locked --manifest-path desktop/backend/Cargo.toml --all-targets --all-features -- -D warnings
cargo test --locked --manifest-path desktop/backend/Cargo.toml --no-default-features
cargo test --locked --manifest-path desktop/backend/Cargo.toml --all-features
cargo build --locked --manifest-path desktop/backend/Cargo.toml --features dioptrin
cargo test --locked --manifest-path desktop/src-tauri/Cargo.toml
.venv/bin/python desktop/scripts/native_backend_parity.py
.venv/bin/python desktop/scripts/native_calibration_parity.py
.venv/bin/python desktop/scripts/native_mask_parity.py
cd desktop
npm test
npm run build
npm run test:native-backend
npm run test:native-calibration
npm run test:native-calibration-transport
npm run test:native-mask
npm run test:native-mask-transport
```

The native tests exercise original counts and orientation, TIFF/HDF5 source
input, frame navigation and shape changes, unchanged-state failures, scientific
precision, masks/history, PONI round trips, buffer replay, and a real stdio
processor with both Python and PATH unavailable. An independently constructed
constant corrected image establishes the expected 1D intensity and cake grid.
It is a scoped regression, not a broad detector/calibration accuracy study.

The separate Python comparison checks every display byte, histogram count,
histogram edges and all Auto-level modes against the existing implementation
for the real CeO2 TIFF and two gzip-HDF5 frames. It never supplies data or
computation to the native process. The headless Chromium/WebKit test opens the
real image and calibration through actual React controls and renders detector,
pattern and cake. Screenshots and its receipt are written under ignored
`desktop/artifacts/native-backend/`. No visible/native window is needed for
these checks.

Local checkpoint, 2026-11-07: native tests pass with and without the numerical
engine (26 and 20 tests respectively); all 19 Tauri host tests and 59 JavaScript
tests pass. At the input-stage checkpoint the existing Python desktop suite
passed with 294 tests and five optional skips; Python implementation files have
not changed in this calibration stage. Strict native Clippy, formatting and the
production frontend build pass.
The independent input/display comparisons and headless Chromium/WebKit workflow
checks pass within their scope above. Visible native dialogs/windows and
Windows/Linux execution have not been requalified for this backend.

The calibration-stage tests additionally cover exact synthetic geometry,
fixed distance/tilts, free wavelength, rotations outside the principal interval,
all-fixed fits, unavailable-ring rejection, Massif/Blob searches, peak-file
compatibility, atomic input validation, transaction-sized history and cancelled/
failed refinement restoration. The real stdio test runs with Python and PATH
unavailable and checks immediate queued cancellation and responsive abort.

Measured CeO2 fixture, five original seed locations: 174 picked points in five
groups produce RMS 0.008680343581089094°; four-ring automatic Massif refinement
produces 59 points in four groups with RMS 0.010147852936183156°. Independent
pyFAI evaluation of the exported PONI/points reproduces both residuals within
1e-9°, and the Python desktop reads the exported peak groups exactly. These
are regression residuals, not detector-wide accuracy or identifiability claims.
Both headless Chromium and WebKit exercise actual picks, Undo/Redo, fresh
Calibrate, continued automatic Refine, live previews and validation plots without
rendering/command errors. Receipts/screenshots are under ignored
`desktop/artifacts/native-calibration/`.

Masking comparisons cover the synthetic fixture and measured CeO2 image with
threshold combinations, Cosmic windows/passes, Spot mean/median, narrow detector
gaps, smoothing, empty user masks, geometry changes/undo and selected nonfinite
inputs. All 26 checks reproduce the chosen Python/C reference masks exactly;
this is fixture parity, not a universal numerical equivalence proof. The actual
Chromium/WebKit controls exercise all three plugins, settings, imprint and
Undo/Redo without rendering/command errors. A real stdio test checks prompt
cancellation, immediate queued cancellation and complete restoration. Receipts
and screenshots are under ignored `desktop/artifacts/native-mask/`.
