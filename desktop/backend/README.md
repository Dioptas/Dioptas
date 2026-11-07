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
- Atomic XY/XYE/CHI/DAT/FXYE pattern and PONI exports, mask files, image/cake exports, processed HDF5/CSV series and phase/material exports. See the integration-stage qualification below.
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
  used. Bulk integration checks cancellation between files, frames and processing stages; an individual numerical kernel is not interrupted internally.

## Integration, phases and Batch/Map

The integration stage now includes persistent pattern/cake plans, combined HDF5
loading, corrections and backgrounds, pattern/overlay editing and I/O, linked
inspection, automatic incoming-file processing, phase/material editing, Batch,
Map and explicit custom actions. It keeps the existing React command contract.
Integration and phase edits share chronological calibration Undo/Redo; raw source
files and authored catalog records remain unchanged. Failed or cancelled bulk
operations restore the complete preceding scientific state.

See [native integration qualification](../NATIVE_INTEGRATION_PARITY.md) for the
implemented controls, pinned Qt/API sources, independent numerical checks, real
Eiger timing scope and reproduction commands. `src/correction_defaults.json`
provides the existing cBN/OIADAC parameter metadata; `processing.rs` implements
those corrections in native f64, together with image backgrounds and flat fields.

## Projects and configurations

Current format-2 `.dio` persistence now runs in Rust, with project-owned image,
background and flat caches, shared phases/overlays and independent scientific
configurations. React exposes select/add/duplicate/rename/remove controls in the
native preview. Per-configuration Batch/Map state and calibration metadata use
optional extensions alongside the existing interoperable scientific groups.
See [project qualification](../NATIVE_PROJECT_PARITY.md) for cross-reader checks,
offline behavior, atomic save/load cancellation and explicit compatibility limits.

## Image orientation and geometric masks

The native backend now supports rotations/flips/reset and the existing geometric
mask controls: rectangle, circle, polygon, arc, thresholds, radial intervals and
Grow/Shrink/Invert/Clear, including Unmask and history. Transforms retain source
pixels, masks, backgrounds and flat fields, carry through Batch/Map and persist
per configuration. See [orientation/masking qualification](../NATIVE_GEOMETRY_MASK_PARITY.md)
for exact conventions, reference differences and reproduction commands.

## Remaining application migration

- Named/nonuniform detectors, orientation variants, distortion splines and
  Fit2D manual-geometry conversion need their own input/geometry qualification.
- The separate LA Cosmic operation remains migration work. The three bundled dynamic
  plugins and NPY/TIFF/EDF/text mask loading are implemented. Arbitrary third-party
  Python plugins need a native extension contract or individual ports.
- Broader detector/format/scientific reference coverage and native installer
  bundling/notices on macOS, Windows and Linux are required before switching the
  default launcher and removing the desktop's required Python distribution.

Dioptrin remains an optional Cargo feature. Native numerical operations report
that requirement explicitly when built without it. Unported commands return
errors without Python fallback. This opt-in backend is not yet a replacement
for every current application workflow.

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
are not imported by this backend. Geometric mask shapes/morphology and mask-file
I/O are now native. The separate LA Cosmic operation remains migration work.

## Qt integration changes carried forward

The native adapter owns persistent, bounded pattern/cake plans on the existing
processing worker. Batch/Map use that same owner; bulk work does not rebuild
unchanged plans or calculate cakes for every frame. Compatible fixed-mask
Bitshuffle/LZ4 u16/u32 HDF5 frames use one typed decode and an owned prepared f64
pattern, with source/dataset identities checked before publication. Corrections
and dynamic masks use the resident native path. All routes retain f64 science
and the same bottom-up detector convention.

Read-only references were Qt `2e34f09f`, combined Qt preview `9c73ffb3`,
`dioptrin-io` `3440119` and Dioptrin `5e245da`; exact pins and restrictions are
in [the qualification ledger](../NATIVE_INTEGRATION_PARITY.md). The Qt report's
20.6% timing is historical source evidence. The separately measured native
Eiger result is recorded in that ledger with its own matched workload.

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
engine (35 and 29 tests respectively); all 19 Tauri host tests and 60 JavaScript
tests pass. At the input-stage checkpoint the existing Python desktop suite
passed with 294 tests and five optional skips; Python implementation files have
not changed in these native migration stages. Strict native Clippy, formatting and the
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
