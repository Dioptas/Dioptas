# Native backend migration

The first migration stage runs the existing React interface against a Rust
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

Open a detector image, load a supported `.poni` calibration (or enter complete
pyFAI-convention geometry), then use Integration. The raw CeO2 example remains
uncalibrated; its reference PONI is
`dioptas/tests/data/CeO2_Pilatus1M.poni`. Ring picking and calibration fitting
are not part of this first stage.

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

The schema-only `src/correction_defaults.json` retains the existing React
controls' parameter definitions from `dioptas.desktop.integration.CORRECTIONS`
at migration base `b418d66b`. These corrections are disabled and their commands
remain unsupported; this file is not a scientific correction implementation.

## Remaining migration, in order

1. **Calibration and geometry:** native peak selections, calibrant resources,
   group/history files, fixed/free parameter fitting, automatic ring refinement,
   cancellation/rollback, Fit2D conversion, and full-resolution linked/ring
   contours. Then complete detector definitions, orientations, pixel corners,
   distortion splines and round trips. The current native integration call is
   not interruptible; a busy cancel request reports this rather than falsely
   claiming cancellation.
2. **Image/mask/integration parity:** transformations, neighboring-file series,
   geometric and automatic masks, plugins, background images, flat fields,
   absorption corrections, SmoothBruckner background, sectors/wrapped ranges,
   automatic bins, supersampling, statistics, other exports and autoprocessing.
3. **Phases and overlays:** native PhaseSmith and Peritheos APIs, material/CIF/
   JCPDS/EOSMAT adapters, search, editing, source provenance and legacy formats.
   Add dependencies only as each workflow is migrated.
4. **Persistence and multi-image work:** `.dio` read/write compatibility,
   configurations, Batch, Map, processed HDF5 and custom actions. Python mask
   plugins need an explicit replacement/optional external-runtime contract.
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
cd desktop
npm test
npm run build
npm run test:native-backend
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
engine (12 tests in each build); all 19 Tauri host tests and 59 JavaScript tests
pass. The existing Python desktop suite passes with 294 tests and five optional
skips. Strict native Clippy, formatting and the production frontend build pass.
The independent input/display comparisons and headless Chromium/WebKit workflow
checks pass within their scope above. Visible native dialogs/windows and
Windows/Linux execution have not been requalified for this backend.
