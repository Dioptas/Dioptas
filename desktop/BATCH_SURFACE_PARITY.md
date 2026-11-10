# Native Batch 3D surface display

The optional **3D** tab sits beside Files, 2D and Options, in both the dock
and detached Batch window. The renderer reads the current native Batch raster
through the existing binary transfer. It introduces no processing command,
scientific engine, integration, browser background fit or full-matrix transform.
The matrix remains owned by the Rust series. Normalization and background display
products supplied to 2D also supply 3D; display sampling never changes stored
values, errors, exports or source detector pixels.

## Reference and behavior

Read-only reference: `BatchWidget.activate_surface_view`,
`BatchController.plot_batch/update_3d_axis/process_step`,
`SurfaceWidget` and the Qt surface navigation controls, as recorded in the base
application commit `5aff6fdf`.

- Front: azimuth 0°, elevation 0°; Right: 90°, 0°; Top: 0°, 90°;
  Isometric: 45°, 30°. Qt's axes are frame/radial/intensity. Camera and axis
  proportions persist across tabs, docking and display-buffer replacement.
- Left drag rotates; right drag pans; wheel zooms without scrolling the shell.
  Rightward drag decreases azimuth, and downward drag increases elevation,
  following Qt's orbit direction.
  Right click zooms out; right double click or F fits. R/T/I select Right/Top/Iso.
  The Front button remains available because desktop F consistently means Fit.
  Axis proportions and physical radial bounds are available under the adjacent
  settings button. Contrast limits perform the high/low display clipping.
- Physical 2θ (°), Q (Å⁻¹) or d (Å) coordinates come from Batch's current axis,
  including descending/nonuniform d. Docked units and intensity scale follow the
  linked pattern, just as 2D does. Conversion retains all source columns and
  needs the recorded wavelength for angular conversions.
- Frame labels and selection use one-based acquired-series indices. Source
  filename and the native one-based source-frame number are available in the
  accessible description and hover hint. The orange selected frame is drawn
  from its actual profile even if it falls between displayed frame samples;
  the green radial marker follows the shared physical inspection position.
  Picking and Up/Down/Home/End use the existing ordered `batch_select` path.
  Left/Right move the radial marker. Hover reports the original current raster
  intensity, plus 2θ/Q/d in the common footer.
- Start/Stop in Options are inclusive; Step is a requested display stride and
  the existing frame-navigation step. The effective display stride is shown in
  the surface toolbar. Shared bin/frame viewport ranges also carry a 2D zoom
  into 3D. Surface radial bounds update that shared viewport. F clears ranges.
- Linear, log and square root share the 2D limits and palette. Negative values
  remain valid linearly; square root clamps at zero; nonfinite samples form
  holes. A single frame/bin displays a curve or point. An unavailable Canvas
  context reports a local error; empty finite data reports an empty range.

## Deliberate display differences from Qt

Qt raises frame stride using `max(1, floor(selected_rows * full_columns /
500000))`, then slices inclusive Start/Stop at that stride. The desktop retains
that minimum, adds a strict 8,192-vertex budget and at most 256 radial vertices,
and displays the effective frame/radial stride on hover. Selected rows retain
their original indices; the radial endpoint is included. These are unaveraged
display samples, so narrow peaks can be omitted at overview scale. Narrow the
radial/frame range to inspect more detail; scientific outputs remain complete.

The bounded Canvas triangle renderer uses orthographic projection and physical
radial spacing. Qt uses OpenGL/perspective and bin spacing, with its numeric 3D
axis labels currently disabled. Desktop labels include the actual units and
rounded major ticks, with exact integer frame range edges. Camera backing pixels are bounded to 2× device scale and 2,048
pixels per side. There is no browser GPU/context requirement.

The log transfer intentionally matches desktop 2D's `log1p(max(0, I-lower)) /
log1p(upper-lower)` rather than Qt's direct `log10` transform. Square root also
matches 2D's nonnegative clamp. Geometry height and color use the same transfer
and clipping. This is display qualification, not a new scientific calculation.
Phase overlays, waterfall generation and background extraction belong to their
existing/separate workflows. Phase controls are disabled while 3D is active.

## Readable axes and ticks

The axes now use rounded major values and corresponding grid lines. Frame
numbers remain integers and include the exact displayed range edges. Radial
labels retain physical positions on ascending and descending 2θ/Q/d axes.
Intensity labels show the original intensity: log uses compact decade labels,
and square root places rounded intensity values using the same transfer as the
surface. Shared powers of ten and offsets remove repeated digits; the intensity
factor stays visible in the caption even when its vertical axis collapses in Top.
Factors remain stable while changing tick density or rotating the view.

Axis edges are chosen from the projected box silhouette as the camera rotates.
Tick marks point outward; titles and numbers lie entirely outside the projected
data box. Adaptive margins retain space for the surface in compact panes.
Text is measured at the selected interface font size. Collision detection uses
oriented text rectangles for slanted titles, and chooses title placement to keep
as many readable numbers as possible. Crowded ticks are thinned; labels are never
clamped onto the image, hidden by the surface, or placed over one another.
The saved active-view PNG includes these same axes.

`npm run test:batch-surface-axes` checks 80 layouts in each of headless Chromium
and WebKit: all four orientations, 2θ/Q/d, descending coordinates, linear/log/√,
large offsets, small values, standard/larger text, and compact panes. It checks
text separation, bounds, unit titles, original-intensity positions and the
outward half-plane of every label against the entire projected data box.
Eight numerical tests cover rounded values, integer frame edges, stable factors,
nonlinear scale positions, collapsed axes and constant intensity. The frontend
suite passes 94 tests. Inspected screenshots and receipts are under
`desktop/artifacts/batch-surface-axes/`; both dedicated headless surface gates
are included in the native UI CI gate. This change has no scientific data or
native command changes.

## Shared export interface

`captureBatchSurface(root?: ParentNode): string | null` in
`src/batchSurfaceCapture.ts` returns base64 PNG bytes without a data-URL prefix,
matching the export chat's `BatchCapture`. It includes rendered axes, scale and
selection, and returns null for inactive, collapsed, empty or unavailable views.
`BatchSurfaceView` also accepts an optional structural `captureRef` compatible
with `BatchCaptureRef`; it registers on mount and unregisters on unmount.
The export workflow can pass its existing active-renderer ref directly. There is
no additional Save control, file dialog or scientific export in this feature.

## Verification

- `npm test`: existing frontend/model/architecture checks and six dedicated
  surface tests pass (85 total at feature qualification).
- `npm run build` passes.
- `cargo test --locked --manifest-path backend/Cargo.toml --all-features`
  passes; the external-image opt-in benchmark remains ignored.
- `npm run test:batch-surface`: headless Chromium and WebKit pass rendered
  orientation changes, source picking, PNG capture, physical descending axes,
  scale transfer, radial/frame ranges, requested/effective stride, gestures,
  single-frame and nonfinite data, unavailable context, compact controls,
  native linked selection, exact normalization-off matrix restoration and
  camera/stride persistence. Real Rust stdio sessions run with Python/PATH
  unavailable; no native windows are opened.

Receipts and inspected screenshots are in ignored
`desktop/artifacts/batch-surface/`. Native WKWebView/OS window behavior is covered
by the existing Batch window owner; this feature adds no new native-window API.
