# Batch processing in the React desktop

The opt-in Rust implementation has a separate [native qualification ledger](NATIVE_INTEGRATION_PARITY.md), including the integration, phase and Batch/Map migration. The Python/Qt behavior and historical checks below remain reference evidence.

Batch starts from Qt's `dioptas/widgets/integration/BatchWidget.py` and its
controllers, and reuses `BatchModel` and the current Python integration pipeline.
It is a separate companion window linked to Integration. There is no Batch mode
in the left sidebar. Qt's Files and 2D views provide the layout baseline; 3D is
intentionally omitted. React's existing typography, plot gestures, image controls
and neutral charcoal/orange styling apply.

## Qt layout and docking

The top row follows Qt: Open raw/proc data, previous/next folder, Save, source
folder, and Files/2D tabs. Files shows Calibration File, Mask File, and the raw
filename/N images table. Selecting a file selects its first integrated frame.
2D shows the selectable intensity series, a vertical histogram on the left, and
2θ/Q/d plus Log/√ controls at the far right in the floating window. Those buttons
reuse the pattern view’s PlotToggle and styling. When docked, Batch follows the
main pattern’s units and Log/√ controls; duplicate buttons are removed. Axis
conversion uses the batch’s recorded wavelength and never drops matrix columns;
if a requested angular conversion is unavailable, the valid stored axis remains.
The independent histogram is mirrored horizontally on the left, including its
handle hit areas. Expanded labels remain upright; horizontal orientation keeps
the existing unmirrored behavior.

In the separate window, Files offers Integrate. Histogram Auto owns intensity
autoscaling; there is no duplicate AutoScale action. A compact Normalize toggle
sits in the existing bottom-right axis margin in both docked and separate views.
Options contains the normalization region directly, plus Start/Stop/Step.
Previous/slider/next and Frame remain below the separate plot. Displayed frame
numbers start at 1; stored indices remain zero-based. Start/Stop are inclusive;
the adapter translates them to the existing processing-command range.
The 2D series grows bottom to top: frame 1 is the lowest row. Selection,
hover readouts and frame labels follow that orientation; Up moves to the next
frame and Down to the previous one. Stored data stays in acquisition order.
The selected frame uses an orange horizontal line and a small marker at the left
edge. Focusing the canvas does not add a border around the whole Batch plot.
The lower-left plot controls select rectangle or X-range (slice) zoom, using
the shared blue drag selection. X-range zoom preserves the frame range. The
chosen mode survives tab changes, docking and reopening.
The frame axis keeps its numeric labels without a title, with a narrow margin
that grows only when larger frame numbers need it.
Axis numbers, unit labels and border use the pattern plot's muted colors.
Axis labels also match its 13 px monospace font in both interface text sizes.

**Dock batch** moves the same panel into Integration's lower-left corner below
the detector/cake and image toolbar. It shares the left column's width and leaves
the pattern and right-hand task controls in place. Drag the divider (or focus it
and use Up/Down) to resize; double-click resets the height. The header can collapse,
hide or detach the panel. The compact **Batch…** button beside **File Info** in
Integration → Image reopens it. It is orange while either the dock or detached
window is open, and neutral after closing/hiding it.
Clicking it while docked hides the panel without discarding data; clicking it
while detached raises and restores the existing window, including if minimized.
Automatic opening after integration and layout restoration always show Batch.
The detached toolbar has no duplicate close button; use the native window close
control. The dock retains its Hide button.
Dock preference, open/closed state, height and collapsed state persist.
Both Integration splitters retain their preferred percentages. A smaller window
clamps the displayed sizes without overwriting preferences, so expanding it
restores the preferred layout. Hiding or closing Batch keeps the data but saves
its closed state; quitting the app with Batch open preserves the open state.
Startup restores the layout once the main window is ready, including an empty
Batch panel before a scientific project is loaded. Project data still comes from
the normal Load/Save project workflow.
The settings icon (accessible as **Options**) beside Files/2D holds normalization
limits and Start/Stop/Step in both layouts. The docked 2D tab has no bottom browsing row or slider: the header
shows the selected frame number and total frame count (n/N in narrow panes).
The header stays on one row; secondary captions become tooltip-labelled icons
when space is tight. Heatmap ticks, hover
readout, navigation and Start/Stop use frame numbers
starting at 1; stored model indices and radial bin indices remain zero-based.
The heatmap has no vertical axis title. Click rows or use
Up/Down and Home/End on the overview to browse. Open, previous/next-folder and
Save remain visible at upper left in all tabs and both window states.
Options edits survive tab changes, and returning to 2D preserves zoom, contrast
and selection. Files retains its integration range.
The splitter shares Integration’s thin grip and hover styling, with pointer
resizing, keyboard Up/Down and double-click reset; the dock can shrink to 220 px.
The dock has no outer frame. The header shows the last three folder names,
centered when they fit and clipped from the left when space is tight, keeping
the final folder visible, with the full path in its tooltip. Files shows
basenames with full paths in tooltips. Header actions are borderless icons with
hover/focus feedback; tabs use the shared underline style. The hidden cake-shift
control no longer reserves a blank row above Batch
when displaying the detector.
Overview contrast, palette, scaling and zoom survive docking and reopening.
The native window remembers its own size/monitor/position and uses Map's existing
monitor-aware placement logic, with separate saved placement. Removed displays
or changed screen scaling are handled by that shared implementation.

## Processing and linked selection

- Integration → Image **Load image…** and Cmd/Ctrl+O accept multiple files.
  Qt's **Integrate / Add / Average / Save** radio choices control multiple
  selections. Integrate (the default) opens Batch while staying in Integration.
  Add and Average use the existing image model and current transformations and
  corrections. Save writes corrected, int32, top-origin TIFF copies prefixed
  `batch_` into a chosen output folder; existing files are never overwritten.
  Combining/exporting uses an isolated model and cancellation or failure keeps
  the current image and complete batch. A single file retains ordinary loading.
- Open raw/proc data accepts raw image series or one processed HDF5 batch.
  Previous/next folder uses Qt's neighboring numbered-folder lookup and matching
  file extension. Input order is preserved. A live calibration is required to
  integrate raw data; processed patterns can be opened without one.
- Integration captures the current mask, transformations, binning/unit, azimuth
  range, detector corrections and image background into an isolated configuration
  on the existing worker. Reintegration is explicit and uses current settings.
  Failed/cancelled processing retains the previous complete series and image.
- Click a 2D row, choose a file, use navigation, or enter a frame number. The
  selection loads the original detector frame and calculates the cake through
  Integration's normal processing path. The selected stored profile is then
  restored, including normalization. These calculations never replace the stored
  batch matrix. The linked green inspection position is retained.
  Clicking the overview also sets its radial position, showing the shared green
  marker on Batch, pattern, cake and detector. Stored-only batches retain a local
  marker without inventing detector geometry. Hover uses the shared footer fields
  for Frame, I, 2θ, Q and d, with zoom-dependent precision and recorded wavelength.
  Selection uses the same quiet, serialized command path as Map, keeping controls
  and plots mounted without global busy-state dimming. Further clicks queue while
  a frame loads rather than being dropped.
- Missing raw files clear stale detector/cake pixels and show the stored profile
  with a message. Imported batches cannot be reintegrated until raw sources are
  loaded again. Raw source images remain external to saved projects.
- **Phases** overlays shared visible phase references on the overview. Colors,
  per-phase intensity-scaled widths and opacity match the cake view. Phase
  coordinates are d spacings, converted with the batch's recorded wavelength;
  pressure/temperature/visibility edits in Integration update the same references.
- 2D uses one column per radial bin and one row per integrated frame. Physical
  tick labels follow the actual radial coordinates, including descending d axes.
  Display unit conversion retains the original axis and intensities; conversion
  to/from 2θ requires the recorded source wavelength. Q↔d needs no wavelength.
- Rectangle zoom, right-drag pan, right-click zoom out, right-double-click/F fit,
  wheel zoom and keyboard row selection use shared plot navigation. Dragging
  never selects a frame. Like Cake, rectangle/X-range selections may start in
  the canvas axis margins; gutter-only gestures stay inert. Readouts report original intensities, including in √/log
  display. Detector pixels remain full resolution and square. Histograms for
  detector, cake and batch overview are independent.
- Normalize matches each frame's mean over the selected physical interval to the
  existing reference pattern using Qt's model. Limits follow the current Batch
  axis (2θ in degrees, Q in Å⁻¹ or d in Å), including the linked pattern axis
  while docked. The desktop adapter selects inclusive stored sample centres and
  supplies a half-open bin interval to the unchanged scientific model; no
  interpolation or resampling is introduced. Conversions use the batch's recorded
  wavelength; Q↔d also works without one. The reference is identified by filename,
  without an index field. Settings can be applied before enabling normalization
  and are retained in .dio projects and optional processed-HDF5 metadata.
  Turning Normalize off restores retained original arrays exactly. Invalid
  regions and nonpositive means reject the operation without replacing data.

The child uses the main window's ordered mutation queue and the same processing
session. Native child commands are restricted to read-only batch snapshots and
levels; mutations and file dialogs route through the main window. Snapshot pixels
use existing binary IPC. Browser tests use the same panel in a popup. Progress
and cancellation use the existing independent processing path. No scientific
HTTP server or Qt application is started, and Dioptrin remains optional.

## Persistence and remaining scope

Save writes Qt-compatible processed HDF5 or radial/frame/intensity CSV through
Qt's writers, publishing atomically. It saves current intensities, including
normalization. Optional HDF5 metadata records normalization and, for newly
integrated series, the actual integration wavelength. Saved processed files do
not retain unnormalized source intensities. Import uses an isolated configuration,
so embedded calibration/mask references cannot replace the live setup.

Save project retains the matrix, axis, raw-file/frame maps, selection and
normalization restore state in the optional `react_desktop_batch` HDF5 group.
Qt ignores this extension. The project does not embed raw images.

Qt's batch background extraction, waterfall, phase controls and image
sum/average/save modes are not implemented here. Multi-frame support follows the
existing loaders (tested with HDF5); the PIL TIFF loader exposes only its first
page. Explicit HDF5 dataset selection remains outside the desktop preview.

## Verification

`desktop/tests/test_batch_workflow.py` compares real Qt-model results for 2θ/Q/d,
mask/orientation, wrapped azimuth, background/flat-field corrections and HDF5
frames. It checks range/step, exact normalization restoration, independent cake
updates, read-only snapshots, raw/processed opening, wavelength-aware units,
neighboring folders, missing raw files, atomic failure/cancellation and
processed/project round trips.

`node scripts/batch_smoke.mjs` (also `--webkit`) checks the real Python-backed
companion and dock: automatic opening from Image, Qt Files/2D controls,
linked frame/cake selection, normalization, unit and intensity options,
reintegration, saving/reopening, gestures, contrast/zoom preservation,
collapse/resize/hide/detach, missing raw images, and 1000 × 700 layout at both
text sizes. Generated screenshots/reports are in ignored `desktop/artifacts/`.

`npm run tauri:smoke -- --batch` uses an isolated application identifier to check
native window open/dock/reopen, remembered placement, binary reads, rejection of
child mutations, linked cake/profile selection and processing-child cleanup.
This requires real native windows; routine layout checks remain headless.

Compact dock follow-up: Chromium and WebKit checks cover vertical histograms,
Options reachability at both text sizes, retained edits/view state between tabs,
and pointer/keyboard resizing of image, dock and overview. They also hold a real
frame load to verify that controls stay enabled and subsequent selections queue;
check mirrored histogram geometry and pointer dragging, linked units/scales,
layout and popup restoration across frontend reloads, invalid preference fallback; and
cover frameless docking, trailing paths and removal of the hidden toolbar row.
At 1000 × 700 with
large text and a 320 px dock, the 2D data area is at least 150 px tall.

The prior CIF assertion fix remains covered by the full desktop Python suite.

Verification on 2026-11-05: 283 desktop Python tests passed (5 skipped),
55 JavaScript tests and 17 Rust tests passed. Build, Chromium/WebKit Batch
companion/dock checks, the detached Map regression, the broader headless browser
workflow and the isolated native Batch smoke passed. The first native run found
an incorrect size/position argument in the test harness; the corrected harness
passed. These checks do not establish Windows/Linux native window behavior.

`node scripts/tauri_batch_layout.mjs` builds an isolated, named native app and
checks floating restore after app exit, native child close, closed-state restore,
docking/collapse and splitter restoration across fresh processing sessions.
Its test profile and window placement are separate from the user preview.

Layout/linked-controls verification (2026-11-05): 58 JavaScript tests and
17 Rust tests pass, as do Chromium/WebKit Batch checks, detached Map checks,
and the broader browser workflow. The bundled native restart campaign passes
all four stages and reaps each processing child. It distinguishes an explicit
child close from app shutdown, and checks docking before the original open
command finishes. Routine layout and histogram checks remain headless.


## Native requalification (2026-11-06)

The current native check passes six detach/dock cycles with different native
sizes/positions and linked selection. The four-stage app-restart campaign also
compares saved native bounds, besides floating/closed/docked/collapsed layout and
splitter state. Private WebKit stores isolate test preferences; each processing
child is reaped. The old failures remain archived. See
[NATIVE_VERIFICATION.md](NATIVE_VERIFICATION.md) for current scope and commands.
