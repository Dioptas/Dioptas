# Native image orientation and geometric masks

The default Rust backend handles the existing React `image_transform` and
`mask_edit` commands. There is no scientific server or Python fallback. The
processor now uses Dioptrin by default; the Python launcher requires explicit selection.

Read-only references are this checkout's `dioptas/desktop/calibration.py`,
`dioptas/desktop/mask.py`, `ImgModel`, `CalibrationModel` and `MaskModel`. The
current Qt checkout at `2e34f09f` has identical mask and transformation methods;
its recent reader reuse/integration optimizations remain covered by the existing
warm-plan and combined-HDF5 regression checks.

## Implemented workflow

Image & detector retains Rotate −90°, Rotate +90°, Flip horizontal, Flip vertical
and Reset transformations. The existing Dioptas/NumPy operation names and array
conventions are retained: the UI's +90° command records `rotate_matrix_p90`
(`np.rot90`) on the bottom-up scientific view. Rendering still uses square source
pixels and the existing detector gestures. Rotations swap the two uniform pixel
pitches; flips retain them. PONI distance, offsets and rotations retain the
existing flat-detector convention. This does not add distorted/named detectors.

Transforms permute f64 scientific pixels without resampling. Original typed
samples and stored row order remain separately owned. The transformation log is
composed into one signed-stride permutation; processing cost does not grow with
every click. The log is bounded to 1024 operations. New source frames, incoming
images, image add/average/save, Batch integration and linked Map selection use
the same orientation. The combined HDF5 decode/integration shortcut remains for
untransformed inputs; transformed inputs use the resident native path and retain
warm integration plans. No transformed data is sent to a plan for source order.

User masks and their separate Undo/Redo snapshots stay attached to source pixels.
Dynamic plugins recompute using the new image/geometry. Background and flat-field
planes retain source coordinates and are permuted before processing. A transform
clears stale calibration picks/RMS and marks an existing calibration dirty.
Calibration Undo/Redo restores orientation, pixel pitches, picks and diagnostics;
ordinary mask history remains usable in either orientation. Drawing selections
are cancelled when image orientation or configuration context changes. Existing
ROI slices are clipped to a rotated detector's bounds, or cleared if empty;
transform Undo restores their previous bounds.

Mask mode supports the existing rectangle, circle, polygon, four-point arc,
threshold-above/below, radial range inside/outside, Grow, Shrink, Invert and Clear
controls, including Unmask. Point/brush drawing and all three dynamic plugins
remain available. Each edit is detached, validates all input and commits one mask
history entry. Failed/cancelled operations preserve data, products, mode and
history. Progress/cancel use the existing stdio side channel. Polygon loops check
cancellation within each row; individual reader/integration calls retain their
existing cancellation boundary.

Rectangle endpoints use NumPy ties-to-even rounding and half-open slices.
Circles truncate the clicked center and radius, with the existing strict ellipse
interior. Arcs use the existing circumcenter and 50 samples per boundary.
Polygon classification follows the reference's two-ray boundary rule and vertex
tolerance, including self-intersections; see the
[scikit-image source](https://github.com/scikit-image/scikit-image/blob/v0.26.0/skimage/_shared/geometry.pyx)
and [retained notice](backend/resources/skimage-polygon-NOTICE.txt).
Grow/Shrink retain the four ordered row/column assignments in `MaskModel`, rather
than substituting a different morphology kernel. Radial masks use original pixel
centers, inclusive/open-ended bounds in 2θ/Q/d, and ignore NaN coordinates. Only
radial masks require the optional Dioptrin geometry feature; transforms, shapes,
thresholds and morphology also work without it.

## Projects and reference boundaries

Format-2 `.dio` stores the original bottom-up raw/background/flat caches and the
transformation log separately, preventing a second application on load. User
masks remain in current scientific coordinates. Optional native metadata retains
original pixel pitches for exact Reset behavior. Transform state is independent
per configuration and persists without the source files. Peak files now record
and validate the transformation log as well as dimensions, so equal-shaped flips
cannot silently reuse incompatible picks. Stored project geometry is
canonical on load; the reader does not silently rotate saved PONI parameters.
Older writers lack reset-pitch metadata: Reset retains their saved pitches,
matching the existing reader, instead of inferring an earlier detector.

The current Python reference can drop backgrounds/flat fields during a
rectangular rotation's intermediate shape updates. Native transforms publish
atomically and preserve them. The independent processed-pixel check therefore
uses an explicit NumPy background/flat formula followed by the same permutations.
The reference's transformed `.dio` geometry can also differ from its live
non-square pixel pitches: the project adapter respects the geometry actually
written in the document. Native saves retain both current geometry and reset
pitches. These checks establish native round trips and scoped cross-reader
compatibility, not a repair of every older writer's state-loss behavior. The
original Qt/Python implementation is unchanged.

The separate LA Cosmic operation is now native in the
[following stage](NATIVE_LACOSMIC_PARITY.md). The Cosmic Ray Mask dynamic plugin
also remains native. Named/nonuniform
and spline detector geometry, Fit2D conversion, broader format qualification and
cross-platform native packaging remain migration work.

## Verification

From the repository root, using the test-only Python reference environment:

```sh
cargo fmt --manifest-path desktop/backend/Cargo.toml --check
cargo clippy --locked --manifest-path desktop/backend/Cargo.toml --all-targets --all-features -- -D warnings
cargo clippy --locked --manifest-path desktop/backend/Cargo.toml --all-targets --no-default-features -- -D warnings
cargo test --locked --manifest-path desktop/backend/Cargo.toml --all-features
cargo test --locked --manifest-path desktop/backend/Cargo.toml --no-default-features
cargo build --locked --manifest-path desktop/backend/Cargo.toml --all-features
.venv/bin/python desktop/scripts/native_geometry_mask_parity.py
.venv/bin/python desktop/scripts/native_project_parity.py
.venv/bin/python desktop/scripts/native_series_parity.py
cd desktop
npm test
npm run build
npm run test:native-geometry-mask
npm run test:native-geometry-mask-transport
```

Rebuild with all features after no-feature tests, which can replace the debug
processor executable. Reference Python/NumPy/skimage execute only in the test
process; the Rust child runs with Python and PATH unavailable.

Checks cover 46 exact full-resolution geometric-mask comparisons, subpixel and
reversed selections, degenerate/invalid inputs, random self-crossing polygons,
arc wrap directions and open radial bounds. Transform checks use a rectangular
source, unequal pixel pitches and nonconstant background/flat fields. Native
unit tests also check scientific counts beyond f32 integer precision, grouped
picks/history, offline configuration ownership and cancellation rollback.

Headless Chromium/WebKit exercise the actual orientation buttons, shape clicks,
polygon completion, morphology, thresholds, radial range and Undo/Redo. The real
stdio cancellation test observes a running polygon operation and verifies exact
session restoration, then checks queued transform cancellation. Receipts and
screenshots are under ignored `desktop/artifacts/native-geometry-mask/`.
These tests do not requalify visible native dialogs or Windows/Linux execution.

Checkpoint, 2026-11-07: all 35 native tests pass with Dioptrin and all 29 pass
without it; strict Clippy passes in both feature modes. All 19 Tauri host and 60
JavaScript tests pass, as does the production frontend build. The new reference,
Chromium/WebKit and cancellation checks pass. Existing detector/display,
calibration, plugin masking, integration/processing, series, I/O/history and
project checks also pass, including the prior warm-plan/combined-HDF5 fixture.
The WebKit mask screenshot was inspected; no visible user window was opened.
