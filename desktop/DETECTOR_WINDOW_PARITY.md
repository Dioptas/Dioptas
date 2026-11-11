# Standalone detector image

November 10, 2026. This focused feature commit is based on the committed
correction-preview dependency `62473343`; integrate that dependency first.
The detector image can be undocked in Calibration, Mask, Integration or Map.
Integration places Undock at the lower right of the image toolbar, with the other
controls aligned left. Its two nonwrapping groups use at most two rows at compact
widths. The complete
Save, ROI, Image/Cake, Profile, Mask, transparency, background and Phases toolbar
moves beneath the detached view, including the cake azimuth shift when applicable.
Show detector window raises/reuses the same companion. Dock and the operating
system's close button return the view.

Integration removes the image pane and its divider while detached, giving its
width to the pattern and task controls. Docking restores the saved split without
overwriting it. A docked Batch fills the freed image column in the main workspace.
If Batch is also detached or hidden, only the full-width task tabs and pattern
remain. Docking the image restores the saved Batch height and collapsed state.
Other modes retain their Show/Dock placeholder and existing layouts.

## Reference and ownership

The Qt reference is `IntegrationWidget.dock_img` in
`dioptas/widgets/integration/__init__.py`: it reparents the image frame,
changes the local readout visibility, remembers normal bounds and restores the
splitters on docking. Its image controls and scientific controller are retained.
The legacy functional undocking test checks the Undock/Dock round trip.

`DetectorSurface` transports the existing `RasterView` and `ImageIntensity`
props. Their callbacks, scientific drafts, mask selections, per-configuration
contrast and shared viewport remain with their existing main-window owners.
The child cannot call `desktop_invoke`, open a file dialog or create a processor.
Picks, mask strokes/shapes, ROI edits and linked inspection therefore use the
same ordered Rust commands as the docked view. Integration can switch between
image and cake inside the companion, including Q display, azimuth shifting and
an optional azimuthal profile to the left of the cake, sharing its vertical
azimuth axis. The profile is hidden in Image mode and correction previews.
The pattern stays in the main window;
linked inspection and markers connect the views. The detached profile reads and
exports through the main command queue. Its result contains profile samples,
not another scientific session or a detector raster copy.

The child uses the same square-pixel renderer, original image dimensions and
orientation, histogram, palettes, linear/log and Auto controls. It has one
readout footer. Standard navigation gestures and F stay local to the existing
renderer; mask Enter/Escape and q/w are forwarded to the original mask owner.
Save image beneath the detached image/cake supplies the existing renderer's PNG,
then the main owner opens its dialog. Image and cake retain independent contrast,
Auto state, histograms and viewports through switching and docking.
In narrow Map layouts the detector owner remains mounted while detached even
when the main Map task tab changes. Correction Plot/Back uses a higher-priority
surface with its own viewport, histogram and units; returning or docking restores
the original source view. The child never requests a second preview calculation.
A new main frontend handshake reconnects an existing native companion after a
frontend reload.

## Transport and invalidation

Live detector events carry metadata/actions; raster arrays never become base64.
An explicit PNG save returns the renderer's existing PNG data URL to the main
Save image action. The main webview publishes immutable raster bytes using raw
binary Tauri IPC. The
host retains only the current snapshot's image/mask buffers, sharing an ID when
the histogram and renderer refer to the same pixels. Metadata-only updates
reuse these bytes; the child advertises its cached IDs through `RasterTransfer`.
Uploads and reads each coalesce to one active request and one newest pending
view. No decoding, histogram scan, integration or correction calculation is
added by detaching. The renderer is mounted in one window at a time.

The host bounds each snapshot to four distinct buffers totaling 256 MiB and an
8 MiB JSON header. Invalid, missing, conflicting or oversized buffers cannot
replace the last valid snapshot. Old sources are released on publication of a
new source and the current snapshot is cleared on native child destruction.
The frontend uses its existing bounded 128 MiB raster cache. Browser test
popups use structured clone and the opener's bridge as an explicit test adapter.

Callback identity includes mode, stable configuration context, scientific
revision, selected HDF5 source, dimensions/orientation, displayed immutable
pixels and active picking/mask tool. Actions captured before a source, geometry,
configuration or tool replacement are rejected instead of being applied to the
new image. Display changes remain independent from scientific pixels.

Window placement reuses the existing companion placement implementation with a
separate `detector-window-v1.json`. Normal size/position are retained through
dock/reopen; minimized/maximized bounds do not replace normal placement. The
existing monitor/DPI/work-area checks apply, including disconnected displays.
Detaching does not modify Batch, Map or phase-editor window ownership.

## Evidence

- `npm test`: 107 passing frontend/transport tests, including binary detector
  round trips, exact float32 samples and ID reuse without pixel retransmission.
- Tauri host: 29 passing tests, including immutable shared snapshots,
  replacement/eviction, invalid/truncated data rollback and generic window
  placement tests. Strict host Clippy passes.
- `scripts/detector_window_smoke.mjs`: headless Chromium and WebKit with a real
  Rust processor, full-resolution CeO2 image, repeated open/close/dock, no extra
  Auto calculation on undock, square pixels, zoom/pan/readout, linked clicks,
  detached ROI controls and drag, rectangle/polygon masks and Undo,
  detached calibration picking, detached Save using the original main owner,
  complete lower-right toolbar at 420/520 px with both text sizes, independent
  image/cake contrast, freed pattern width and restoration on docking,
  narrow Map, independent configuration contrast and rejection of an explicitly delayed old-configuration action.
- `scripts/detector_source_smoke.mjs`: both browsers, real HDF5 source/frame
  clamping, transformed full-resolution dimensions, canceled calibrated source
  replacement, accepted detector/calibration reset and compact Standard/Larger
  layouts with square pixels and the Dock action in the actual viewport. Loaded,
  disabled flat-field previews are checked through detached Plot/Back,
  close/redock and reopen, with preserved source/preview zoom and unchanged
  science. Preview command counts exclude duplicate calculations on movement.
- The original correction-preview Chromium/WebKit workflow passes after its
  detector-selector adjustment; all three native correction-preview tests pass.
- `scripts/detector_window_native.mjs`: one disposable macOS test application
  campaign with private WebKit storage and preferences. Actual native open,
  minimize/reopen/reuse, independent move/resize, dock/reopen placement, OS close,
  binary/cached snapshot IPC, child command rejection, main-frontend reload
  reconnection and a stable processor PID pass. The test's processor is reaped
  on final exit. The campaign's first wrapper report used the wrong PID field;
  the corrected run passes that check.

Receipts and screenshots are in `artifacts/detector-window/`. The earlier
Phase parameters scrollbar fixture failure was corrected in the consolidated
checkout; the full shared-controls suite passes in Chromium and WebKit at both
text sizes. Windows/Linux native window semantics and physical display latency
remain unqualified.

## Consolidated desktop integration

The detector window and correction-preview dependency are now integrated with
consolidated base `53fe41b2`, preserving cake Q display and azimuthal profiles.
The joint source check additionally exercises an open detached correction map
with Q selected and a native azimuthal profile visible. Changing profile width
keeps that map open, preserves science and avoids duplicate preview work.
Profile reads and exports now retain correction previews, matching the other
read-only inspection commands. The merged tree passes 212 native processor
checks (two existing ignored), 112 frontend tests, 29 host tests, strict Clippy,
frontend build and the headless/native workflows described in the
[consolidation record](RUST_DESKTOP_CONSOLIDATION.md).

## Complete detached Integration workspace follow-up

Implemented directly in the consolidated Tauri checkout. The compact detached
profile exposed a tick-density/annotation-margin feedback loop in `PatternView`.
Tick density now uses a stable reserved annotation height, so rendering no longer
changes the tick count by changing its own gutter. The source regression covers
this constant-intensity profile, width changes and profile export in the child.
The source toolbar remains visible with processing/export actions disabled while
a correction map is shown; the redundant preview-corner Undock icon is removed.

Headless Chromium and WebKit pass `test:detector-window`,
`test:correction-previews`, `test:cake-profile`, `test:cake-q-axis`,
`test:integration-responsive`, `test:integration-panel` and `test:ui-components`.
The responsive check also preserves the same Batch heatmap instance and usable
main dock while the image is detached. All 112 frontend tests and the production
build pass. No scientific Rust code or native window-management code changed in
this follow-up; the earlier isolated native lifecycle campaign is historical
qualification, not a newly repeated visible-window check.

## Rust-only audit and local readouts (2026-11-11)

`npm run test:detector-window` uses only the Rust stdio processor in both browser
engines. Its source-selector fixture is generated by a Rust Cargo example; the
flat field is written directly by Node. Both detector scripts assert the Rust
runtime, and the shared client disables Python/PATH fallback. The separate
visible native detector script explicitly requests `--backend=rust`.

While the image/cake/profile is detached, its live mouse coordinates appear
only in that companion's footer. The last-click position remains visible in both
windows so users can compare the selected point with the current mouse position.
The main footer retains the filename and readouts from its own pattern. Docking
restores live image/cake readouts in the main footer. Linked inspection and
scientific state remain shared.

Both headless Chromium/WebKit detector workflows pass, including detached cake
hover, hidden duplicate live coordinates, matching last-click positions in both
windows, a retained main-pattern readout and restored detector readouts on docking. Production build and all 113 frontend
tests pass. No visible native window campaign was run for this UI change.

The detector regression also explicitly clicks image → pattern → image with the
companion open. Each gesture must change the shared Rust selection, update the
other plot's linked marker (including the projected detector point and contour),
and produce matching click fields in both footers. Chromium and WebKit pass
this round trip against Rust; no application correction was needed.

The same round-trip check now covers detached cake → pattern → detached cake
in both 2θ and Q display modes. Cake clicks update the pattern's linked marker;
pattern clicks update the cake's radial marker and click point while retaining
the selected azimuth. Both footer readouts must match after every click. The
source grid remains in 2θ while Q labels are displayed. Chromium and WebKit pass
against Rust with no application change needed.
