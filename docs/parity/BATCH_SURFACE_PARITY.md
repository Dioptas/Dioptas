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
that minimum and bounds the mesh according to the selected resolution:

| Resolution | Mesh points | Radial samples |
| --- | ---: | ---: |
| Fast | 8,192 | 256 |
| High (default) | 65,536 | 2,048 |
| Very high | 262,144 | 8,192 |

Resolution is under the surface settings button and persists across tabs,
docking and restart. These are unaveraged source samples; arrays within both
limits retain all requested samples. Larger arrays raise the effective
frame/radial strides, shown on hover. Selecting a narrower range increases its
display detail. The original native arrays and scientific exports are untouched.
During rotation, pan and wheel zoom the renderer temporarily uses Fast detail,
then restores the requested mesh on pointer release or after wheel motion ends.
The requested Step and stored frame identities are retained throughout.

The surface now draws with **WebGL 2**, using indexed triangles, a depth buffer,
antialiasing, and a palette texture interpolated from the shared color map. It
uses orthographic projection and physical radial spacing. The readable axes,
grid and selected/linked profiles remain Canvas overlays; the GPU image is
composited into the same capture canvas, so existing PNG exports include all
of them. Qt uses OpenGL/perspective and bin spacing, with its numeric 3D axis
labels currently disabled. Desktop labels include actual units, rounded major
ticks and exact integer frame range edges. Backing pixels remain bounded to
2× device scale and 2,048 pixels per side.

A missing/lost WebGL 2 context falls back to the Canvas renderer. Surface settings
report **GPU drawing** or **Canvas fallback** explicitly. Contexts and graphics
buffers are released when the view unmounts. GPU picking resolves the nearest
projected triangle by depth instead of relying on array order. Hover picking is
limited to approximately 13 Hz, while drag gestures use the lighter mesh.

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
`artifacts/batch-surface-axes/`; both dedicated headless surface gates
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
`artifacts/batch-surface/`. Native WKWebView/OS window behavior is covered
by the existing Batch window owner; this feature adds no new native-window API.

## GPU and resolution qualification

`npm run test:batch-surface-gpu` passes in headless Chromium and WebKit, with
WebGL 2 actually active in both. A generated 64 × 2,048 fixture contains a narrow
radial peak between the old overview samples. Fast shows 7,328 mesh points and
misses that peak (sampled maximum approximately 0.0021); High retains all 2,048
radial bins with 65,536 points and a sampled maximum of 139.98. Very high retains
the complete 131,072-point source grid. Source-buffer SHA-256 is identical after
quality changes and rotation. This is an intentionally generated display fixture,
not an experimental measurement or scientific interpolation.

The check also covers detail restoration after motion, preference persistence,
depth-aware selection, PNG capture, forced context loss, unavailable-GPU fallback,
and context release on remount. The full frontend suite passes 95 tests, and
the existing surface and 160 axis-layout checks still pass. Its receipt records per-pass timings, including
CPU mesh/axis preparation and GPU image compositing. The captured headless WebKit
passes were approximately 14 ms for High, 20 ms for Very high and 4 ms while moving;
Chromium was slower. These are local headless measurements, not a native-display
frame-rate or scanout guarantee. Receipts and inspected images are under
`artifacts/batch-surface-gpu/`. The GPU check is part of the native UI gate.

## Navigation and toolbar follow-up

Right double-click restores the complete radial/frame view, camera fit and
proportions, matching F. It is detected from two secondary pointer clicks within
450 ms and 6 px (the same contract as the shared plot navigator); browser
`dblclick` events do not reliably cover secondary buttons. A single right click
zooms out 2×, right drag pans, and Control/Command + primary gestures provide
the secondary-button equivalent. Drag, wheel, cancellation and primary clicks
clear a pending secondary click so they cannot accidentally trigger a reset.

Surface orientation/normalization/settings controls now share the same quiet,
transparent style as the 2θ/Q/d controls, including selected and hover states.
The surface settings gear sits immediately after Normalize; Batch
Options sits just before Collapse in the window-action group and toggles back to the previous
Files/2D/3D view. The Phases icon has no visible caption at any width, while
retaining its accessible name and tooltip. Header controls remain inline.

The headless surface check in Chromium and WebKit covers physical right-button
double-click and Control-double-click after zoom/pan/radial cropping, full-range
restoration without selection changes, both gear positions, icon-only Phases,
settings toggle/return, and style equality against active/inactive 2θ/Q buttons.
The shared UI component checks also pass.
