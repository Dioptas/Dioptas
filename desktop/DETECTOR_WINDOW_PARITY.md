# Standalone detector image

November 10, 2026. This focused feature commit is based on the committed
correction-preview dependency `62473343`; integrate that dependency first.
The detector image can be undocked with the corner icon in
Calibration, Mask, Integration or Map. Show detector window raises/reuses the
same companion. Dock and the operating system's close button return the view.
The main workspace keeps its task controls and layout settings; its image slot
shows Show/Dock actions while detached. This preserves the desktop splitters
rather than reproducing Qt's temporary splitter collapse.

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
same ordered Rust commands as the docked view. Pattern and cake inspection stay
in the main window, with linked green markers on the detached detector.

The child uses the same square-pixel renderer, original image dimensions and
orientation, histogram, palettes, linear/log and Auto controls. It has one
readout footer. Standard navigation gestures and F stay local to the existing
renderer; mask Enter/Escape and q/w are forwarded to the original mask owner.
Saving a displayed detector PNG still uses the main Save image action: the
child supplies the existing renderer's PNG, then the main owner opens its dialog.
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
  main ROI controls and detached ROI drag, rectangle/polygon masks and Undo,
  detached calibration picking, main PNG export using the detached renderer,
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

Receipts and screenshots are in `artifacts/detector-window/`. The broad
`test:ui-components` run fails the unrelated Phase parameters scrollbar
assertion (12 px expected, 0 observed). The same failure reproduces with the
original `b31e7650` fixture dependencies
(the sole changed runtime import, ImageIntensity, was supplied from that commit
through a temporary Vite loader). `artifacts/detector-window/ui-baseline.log`
records the baseline failure. No shared scrollbar/phase implementation was
changed by this feature. Windows/Linux native window semantics and physical
display latency remain unqualified.

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
