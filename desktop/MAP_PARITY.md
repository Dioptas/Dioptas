# Map workflow parity (2026-11-04)

The GUI follow-up was developed in the assigned `codex/desktop-map` worktree
from `codex/react-desktop` at `dd9795d3`. Integration into the primary
`codex/react-desktop` checkout on 2026-11-04 includes its subsequent phase-editor
and database changes through `9777d23e`.
Qt references were read from `/Users/clemens/Programming/Dioptas`, particularly
MapWidget, MapPanelWidget, MapLayerWidget, MapGridPopup, MapPanelController,
MapController and MapRoiInPatternController. Scientific integration, reduction,
layout and expression calculations continue to use the existing Python models.

## GUI follow-up

The point-count/pattern/unit summary and standalone normalization button are
removed. A compact gear button in Points opens Map settings next to the trigger, with
inline labels and controls. It remains within the viewport on resize, and
clicking outside dismisses it. It contains
Reintegrate selected image (on by default, remembered in frontend preferences)
and normalization. Available raw images are reintegrated on selection when
this option is enabled and calibration is present. Normalized patterns retain
their stored scaling; stored-only projects fall back to their saved pattern
when raw reintegration is unavailable. Full-map reintegration remains separate.

The selected raw image and loaded geometry are shared with Calibration and
Integration. Map selection clears the previous cake and validation overlays and
marks them for calculation on entry to either view. It also publishes the selected
raw detector pixels for Integration's raw/corrected switch. Map navigation itself
does not calculate a cake or modify the stored scan patterns. Missing raw files
and blank cells retain their stored-pattern/empty behavior without requesting a
cake. Python regression checks compare the deferred result with opening the same
image directly; the headless Map check loads calibration in Map and visits both
Integration's cake display and Calibration's Validate view.

Point and file selection keep the controls enabled while loading the detector
and pattern. Rapid selections use the command queue in click order. Selection
metadata alone no longer clears or recomputes the scan's smoothing/contour
preview; changes to scan pixels, dimensions or display options still refresh it.
Headless checks hold a selection request in flight and verify stable controls,
retained scan canvas, no redundant map-display/levels requests, and the final
selection after several rapid file clicks.

Normalization accepts a physical 2θ/Q/d range or the current bounds of an
existing pattern window, plus a reference file. The reference selector shows
the same 1-based arrangement row and filename as Points; blank cells are
disabled, and rearranged rows resolve to their original stored pattern index. Unit switches convert both
bounds. Angular conversion requires a loaded calibration; Q/d conversion does
not. Applying a window reads its bounds at that time; editing it later does
not silently renormalize patterns. Normalize and Restore, Escape/Close and
focus restoration are available in the dialog.

Points now owns Load, Folder, Live/Follow and Check filename numbering. The
numbering check sits with insert/remove blank in the point-arrangement toolbar;
Grid contains dimensions and scan orientation. The redundant map-footer open
button and processed-batch shortcut were removed on request. Calibration and
full-map reintegration use compact icon buttons with descriptive tooltips.

Grid dimensions keep text drafts, allowing selection, deletion and replacement
without inserting a zero. Valid complete dimensions apply on Enter or blur;
there is no Apply grid button. Incomplete, undersized or oversized grids are
not sent to the processing model. All task tabs use the shared visible scrollbar
surface and reserve its gutter. The point list adapts to the available height.

Window fields remain editable during their own saves. Edits are serialized,
using the latest source range, so Tab and Enter preserve focus and a later
field edit cannot overwrite an earlier one. The table follows the pattern's
2θ/Q/d unit and converts edited bounds back to the stored scientific unit,
including the reversed From/To correspondence in d spacing. An unfinished
From/To pair stays editable locally until both bounds are valid; Escape restores
the stored range. Untouched fields retain the original precision.


- Qt-like split layout: map on the left; detector and Points/Layers/Grid task
  tabs at upper right; pattern spanning the right side below them. Dividers
  support dragging, arrow keys, Home and double-click reset. Below 740 px of
  available analysis width, the detector moves into an Image tab. Below 850 px
  window width the panels stack. The scan can be detached to a separate native
  window. Task controls stay on the right.
- Compact shared DataTable window editor, with exclusive map-layer radios,
  editable color swatches, names, From/To limits and all seven Qt value choices.
  Changes commit on blur or Enter; Escape reverts a draft. Display rounding does
  not write rounded ranges back to the model. Rows use the window color for
  selection and hover, matching the pattern regions. Expressions have their
  own editable table, add/update form and selected-row removal.
- Map tools use the Integration view's flat rectangular button styling.
  Pattern 2θ/Q/d, ROI editing, Log/√, AA and auto-range occupy a vertical strip
  on its right, freeing the bottom of the pattern. Layers keeps its tables and
  editor without explanatory paragraphs.
- Pattern ranges use the shared two-line boundary and top-handle renderer,
  without a surrounding rectangle. They are visible and editable by default.
  Drag the nearest edge to resize, drag the body to translate, click a region
  to select its map layer, or click outside regions to recenter the active
  window. When an
  expression is displayed, the first ROI supplies the active pattern window,
  as in Qt. Dragging source windows preserves the displayed expression layer.
  Turn Edit off to rectangle-zoom inside windows; other shared gestures remain
  available. The ROI toggle hides the ranges and their interaction together.
- Pattern 2θ/Q/d display uses the shared wavelength conversion helper without
  modifying stored map coordinates or intensities. ROI changes convert back to
  the stored unit, sorting reversed d edges. Unit changes reset the plot view
  so a manual range in d cannot be reused as an angular range. Conversions
  requiring a wavelength are disabled without a calibrated geometry; Q/d
  conversion remains available for stored batches.
- Pattern Log and square-root scales are exclusive. Antialias and auto-range
  controls reuse the shared renderer. Pattern scale, antialias, auto-range,
  split proportions, smoothing and contour preferences are saved locally.
  Plot readouts remain in the single app footer. There are no extra image
  titles or plot-specific coordinate footers.
- Points support drag reordering, arrow-key selection, Alt+arrow reordering,
  move buttons, inserted/removable blanks and exclude/include. Selection follows
  the detector, pattern, map cell and list; keyboard focus follows arrow
  selection. Trailing structural blanks are changed by resizing the grid.
  The list is paged in groups of 100 for large scans.
- Detector Mask and Transparent controls match the other desktop views. Mask
  display changes reintegrate the selected raw image automatically when
  possible. Stored-only and normalized patterns remain intact. Full-map
  reintegration is a separate action; deferred main integration stays outside
  Map mode.
- Live appends numbered continuations in the loaded scan folder, using the
  loaded files' common nonnumeric prefix and extensions. Files must have the
  same nonzero size and mtime in consecutive polls. A lightweight pending-file
  check precedes the normal serialized mutation command, which appends at most
  two files per tick using `MapModel.append_files`. Layout, windows and
  expressions survive append; Follow selects the latest point, or the selected
  image is restored. Read failures remain eligible for retry. Live stops on
  mode exit, source replacement, normalization or an error. Normalized maps
  must be restored before Live. It watches new files, not growing datasets
  inside an already-loaded HDF5 file.
- PNG uses the shared raster export path, including the current viewport and
  annotations, instead of copying an overlay-only canvas. Text/TIFF map export
  and lossless `.dio` project persistence remain available.

The earlier backend implementation and historical qualification follow below.

Combined-app recheck: this view is now merged with Mask and Integration on
`codex/react-desktop`. The combined Python/browser checks and both native
Tauri checks pass, including the calibration smoke that timed out during the
isolated Map-branch run recorded below. A new cross-view test confirms that
Map patterns use the same mask/integration settings and that all three views'
scientific state survives a project round trip. This does not extend the
feature coverage or platform qualification stated below.

Implemented in the assigned `codex/desktop-map` worktree. Compared directly with
current read-only Qt sources in `/Users/clemens/Programming/Dioptas`: MapWidget,
MapPanelWidget, MapLayerWidget, MapGridPopup, MapController, MapPanelController,
MapRoiInPatternController, MapModel, BatchModel, map_layout, map_reduction,
map_expression and map_task. The relevant scientific model files match this
branch's baseline; no original Qt or shared scientific implementation was edited.

## Implemented

- Dedicated **Map** mode in left navigation. The scan map occupies the left
  panel; detector and Points/Layers/Grid task controls occupy the upper right,
  with the pattern below them. Drag or use arrow keys on the dividers to
  resize the map/detector/pattern. Detach map opens an independent native
  window. Narrow layouts stack the plots in a
  scrolling workspace. Task controls remain on the right.
- Native multi-file image and folder selection. Explicit path lists retain
  supplied order; folder selection uses natural filename order. All frames
  in each file remain in frame order. Existing detector orientation, image
  transformations, mask, geometry and integration configuration are captured by
  Qt's `compute_map_integration` task. There is no scientific HTTP service.
- Loading/rebuilding integrates into an isolated candidate on DesktopBridge's
  single owning processing thread. Progress/cancel bypass that worker through
  the existing transport. Failed and cancelled loads retain the previous map.
  The current image is changed only after successful integration.
- The processing adapter retains processed HDF5/NeXus batch import through
  BatchModel; its Points shortcut was removed on request. This includes radial
  units and file/frame provenance. Import does not replace live calibration or
  mask. Missing raw sources show the stored pattern and an explicit message;
  no detector image is invented.
- Exact-factor grid presets or a larger custom grid, serpentine scan, axis swap,
  both mirrors, filename numbering checks, arrangement moves, inserted/removed
  blanks, point exclusion/inclusion. MapModel owns all coordinate and slot
  translations. Exclusion follows current Qt: remove the cell and close up
  subsequent points, while retaining the excluded point in the arrangement.
  Missing/nonfinite cells remain blank. Row 0 is the top display row.
- Pixel selection and arrangement selection link to the original detector image
  and frame, plus its stored integrated pattern. Optional reintegration uses the
  current scientific settings and converts the result into the map's stored
  radial unit. Display-coordinate conversion never rewrites stored ROI units.
  Only Integration shows linked detector/pattern click markers; Map keeps the
  shared live mouse readout and map-cell selection.
- Window add/remove/rename, numeric range editing, and draggable pattern
  regions/edges enabled by default. Sum, Sum minus background, Mean, Maximum, Peak area, Peak
  position and FWHM use the existing map reductions. Peak-shape reductions have
  the model's straight-edge background handling. Expressions use the existing
  safe grammar, including existing project overlay references via `ovl()`.
- Reversible mean-intensity normalization to a selected reference point over a
  physical radial interval or pattern window, using a dedicated BatchModel instance.
  Range selection uses the shared strict-endpoint window rule on stored samples,
  including descending axes. The internal bin interval remains supported for
  older callers/projects. The independent batch
  workspace keeps its own data and normalization history. Repeated application starts from originals;
  invalid/nonpositive ranges are rejected. The `.dio` project retains normalized
  map patterns; a separate optional `react_map_normalization` group retains
  originals/range/reference/physical coordinates for Restore after reopening in this frontend. Qt
  reads the normal map and ignores this extra group; a subsequent Qt save does
  not preserve this frontend-only restore history.
- Independent top histograms, intensity limits, Auto settings, linear/log mode
  and visual palettes for scan map and detector. Detector data remain at full
  resolution with square pixels. Histogram statistics use the original scalar
  map, including when the display is interpolated. Map hover resolves the
  already-transferred scalar/index grid locally; it does not send detector
  arrays or request full map snapshots. Detector readout is throttled.
- Optional cubic smoothing (2–10×) and contours (1–20 levels), computed on the
  processing thread with the same cubic upsampling family as Qt. Smoothing
  preserves the blank-cell footprint instead of allowing NaNs to contaminate
  the whole interpolated image. Display interpolation is bounded to four million
  cells; original scalar values and selection coordinates never change.
- Save map as tabular text (`%g`, with NaN blanks), Qt-style normalized uint32
  TIFF (blanks zero), or PNG of the current map viewport. `.dio` is the lossless
  map/pattern/layout/layer save/reopen path. Stored-only maps can be saved even
  without a detector image. All file actions have native Tauri dialog routing.

## Shared interfaces for integration

Mode code lives in MapView, MapControls, mapDomain, map.css, and the Python
`desktop/map.py` and `desktop/map_display.py` adapters. App.tsx has only mode
routing, map response state, and composition; session.py adds the mixin command
registry, snapshot hook and optional normalization persistence hooks.

- PatternView has optional `regions`, `editRegions`, `onRegionChange` and
  `onRegionSelect` props. Calibration defaults remain unchanged. Map enables
  **Edit windows** initially; disabling it restores normal left-drag navigation
  inside regions. Right-button navigation remains available during editing.
  Map uses `onRegionInput`, `onRegionDragStart` and `onRegionCancel` for live
  updates while dragging either boundary or the body. One reduction runs at a
  time; pending pointer positions are replaced by the newest position. Release
  flushes the final bounds, and Escape restores the bounds from before the drag.
  Live responses keep the plot viewport and controls available and preserve an
  active expression layer. Other PatternView callers retain their own update
  behavior.
- RasterView has an optional `contours` prop (arrays of x/y paths); no new gesture
  or detector-orientation implementation. Map selection uses its existing marker
  overlay. All renderers and navigation hooks are reused.
- ImageIntensity accepts `display="map"` for distinct accessible labels. Its
  previous detector/cake defaults and controls are unchanged.
- Response adds map-specific optional fields; shared State is unchanged.
- Tauri routes `map_load` to multi-file selection, `map_folder` to folder
  selection, `map_batch` to an HDF5 chooser and `map_export` to a save chooser.
  Explicit paths and reintegration bypass dialogs. Cancellation returns the
  existing `{ok: true, cancelled: true}` response.

## Remaining differences

- A detached native scan-map window is supported alongside the in-window
  resizable and expandable map. Detach returns the main workspace to Integration;
  cells drive its detector, cake and pattern through the existing command queue.
  Dock or window close restores the panel without clearing scan data. The child
  shares the scan component and uses read-only binary map snapshots; no second
  processing session is created. Window placement is retained; plot zoom is not restored
  on reopening. Live/follow-newest is implemented as
  described above; it does not monitor new frames inside existing HDF5 files.
- Overlay loading/editing remains in Integration. Map's pattern plot renders
  the same visible overlays and phases, with shared colors, conditions and
  scale/offset. Map can also evaluate overlay references in expressions. It does not
  implement the full integration, mask or batch workspaces (batch background
  extraction, frame-stack visualization and batch pattern export).
- Scientific map coordinates retain their stored radial unit. The table and
  pattern display 2θ, Q or d together, converting edits back to that stored
  unit. Pattern intensity uses the shared linear/log/square-root scales.
- Explicit HDF5 dataset selection follows the existing desktop boundary's
  limitation; supported ImgModel default datasets and processed batch formats
  work. There is no arbitrary beamline motor-coordinate importer.
- Several display preferences and panel proportions are saved locally; the
  selected task tab and displayed radial unit are local to the mounted view.
  Map scientific state is persisted. No portable Python runtime or Windows/Linux
  qualification is claimed.

## Points layout and scrolling (2026-11-04)

Point arrangement actions sit in one horizontal toolbar above the list, keeping
all actions visible when the pattern is enlarged. The Points tab has no outer
scroll surface; the file list fills its remaining height and is the only
scrolling region. Indices share a right-aligned column sized for the total slot
count; filenames share a left-aligned column and truncate with a tooltip.
Headless Chromium/WebKit checks exercise short panels at normal and large text,
number/filename alignment across one- and two-digit indices, and wheel scrolling
inside the list and over the fixed toolbar.

## Map settings and physical normalization verification (2026-11-04)

The production build, all 44 JavaScript checks, and the Python desktop suite
(253 passed, 5 skipped) pass. Headless Chromium/WebKit workflows cover the compact settings dialog, changing
reintegration preference, automatic selection with changed radial bin settings,
manual range unit conversion, pattern-window normalization, restore, Close/Escape
and focus return. They also cover normalized-pattern preservation and stored
fallback when a raw file disappears. Analytic Python tests compare physical
Q/d/2θ intervals to independently computed scale factors, verify descending
axes and atomic failure, and save/reopen/restore the physical definition.
A nearly constant map histogram also remains usable after normalization; all
finite source samples are retained and scientific values are unchanged.
Python processing changes require restarting an existing preview; frontend-only
settings changes update through HMR. No visible native window is opened for
routine verification.

## Numeric editing and control cleanup verification (2026-11-04)

Build and all 44 JavaScript checks pass. Expanded headless Chromium/WebKit
workflows verify clearing and replacing both grid dimensions, automatic commit
on Enter and blur, visible scrollbars and unobscured controls in all three tabs,
Live/Follow in Points, range-cell Tab/Enter focus during deliberately delayed
saves, completing a range whose new From initially exceeds the old To, and
numeric Q/d table edits against independent inverse conversions.
No native test window or preview restart is required for this frontend update.

## Merge verification (2026-11-04)

Live window dragging follow-up: headless Chromium/WebKit checks verify changed
scan pixels before pointer release for boundary resizing and body translation,
continued dragging across responses, preserved expression selection and viewport,
one in-flight reduction with a coalesced final position, and Escape restoration
both before and after an update. The TypeScript/Vite build and 44 JavaScript
checks pass. Scientific reductions were unchanged by that UI update. Before the
prefix-cache optimization below, a synthetic 10,000-point ×
1,000-bin map measured 16.3 ms median for a sum-window command plus JSON encoding
over 24 warmed updates; this excludes IPC and browser rendering and is not a
frame-rate guarantee.

Sum and Mean now share a lazy float64 cumulative-sum cache in MapModel. Window,
expression, color, active-layer and layout edits retain it. Loading, reintegration,
project restoration, normalization/restore, live append and reset discard it
through the data publication paths, including when the same array is republished
after an in-place change. The cache is derived in memory and is not saved in
projects; its storage is eight bytes per point per bin plus one leading column.
Background-subtracted and peak-shape reductions retain the existing direct path.
Strict endpoints, descending axes and empty-window NaNs are preserved. Disjoint
sample selections use direct reduction; rows with nonfinite/overflowed prefixes
or a numerically unstable subtraction use direct sums over the selected samples.

The cache follow-up passes 158 focused Python model/desktop checks and 13
offscreen Qt controller checks, the TypeScript/Vite build, and the complete
headless Map workflow in Chromium and WebKit. Coverage includes real reintegration
with changed bin counts, same-array data replacement, live append, normalization,
project reopen/restore, shared cache reuse, and numerical edge cases. In a seeded
10,000-point × 1,000-bin float64 benchmark over 25 windows of about 200 bins,
warmed median reductions changed from 4.37 to 0.166 ms for Sum and 4.40 to
0.142 ms for Mean. Cache construction took 27.4 ms and used 80,080,000 bytes.
Including map layout/snapshot and JSON encoding changed the median from 19.08 to
14.95 ms; these measurements exclude IPC and browser rendering. The local report
is `desktop/artifacts/map-sum-cache-benchmark.json`.

The combined Map and current React desktop tree passes the TypeScript/Vite
build, all 44 JavaScript checks, 28 focused Python tests (Map, combined-view
persistence and phase controls), and the complete headless Map workflow in
Chromium and WebKit. Existing previews were not closed or restarted; the Python
command additions require restarting the preview once.

## Current validation (2026-11-03)

- Desktop Python suite: **192 passed, 5 skipped**. Map-specific coverage includes
  analytic reductions, layout repair, file/frame provenance, color/active-layer
  project persistence, rejected edits, atomic expression rename, retained stored
  patterns on mask changes, and stable-file Live append/follow behavior.
- JavaScript unit checks: **37 passed**. Production TypeScript/Vite build passes.
- Expanded real-model Map browser workflow passes in Chromium and WebKit:
  inline editing, colors/reductions, forward Q conversion and reversed d-edge
  conversion, region dragging/recentering, Log/√, hidden windows, point dragging,
  keyboard focus, blanks/exclusion, actual Live file arrival/append/follow,
  normalization, export and
  project reopening, independent histograms, large text and compact Image tab.
- Bundled Tauri/WKWebView Map smoke passes: actual stdio processing, linked
  selection, full-resolution detector, independent histograms, window table,
  converted regions, square-root scale, wheel capture, export and `.dio`
  reopening. The full browser calibration/Integration regression and the
  bundled native calibration/Integration/Mask smoke also pass. Only test
  windows close and their processing children are reaped.
- The final focused Map + combined-view Python rerun passes **19 tests** after
  separating pending-file detection from the serialized Live append command.

Generated reports and screenshots are in ignored `desktop/artifacts/`.
These checks establish the tested workflows, not complete Qt feature parity or
Windows/Linux qualification.

## Historical validation (2026-11-01)

Results on this checkout: `desktop/tests` **49 passed / 4 skipped** (optional
Dioptrin absent); combined map/model/layout/reduction/expression/pipeline and
Qt Main/Calibration regressions **204 passed / 1 skipped** (includes the first
13 Map adapter tests); two further Map tests for multi-frame folder loading and
display interpolation passed in the final 15-test Map suite. Rust **3 passed**.
Browser calibration and Map checks and the bundled native Map check passed.
The separate bundled calibration smoke timed out; see the qualification below.


- Desktop Python tests cover measured-image map integration, analytic independent
  ROI expectations for all seven value choices, expression rename/validation,
  grid transforms, blanks/exclusion, linked stored selection, batch radial units,
  normalization/save/reopen/restore, text/TIFF exports, real load failure and
  concurrent real integration cancellation, folder order/multi-frame identity,
  and display interpolation without data mutation.
- Existing desktop calibration/transport tests and Qt map/layout/reduction/
  expression/pipeline/MainController/CalibrationController regressions pass.
- `node desktop/scripts/map_smoke.mjs`: real nine-image map through React,
  top histograms, linked selection, snake/grid/blank selection, ROI edge dragging,
  expression, normalization, export/project reopening, plot wheel gestures and
  local hover, large text, wide/compact screenshots and no browser errors.
- `npm run tauri:smoke -- --map`: bundled WKWebView, six measured-image points,
  native stdio linked selection, window creation, full detector resolution,
  independent histograms, wheel capture, export and project reopening; no Qt
  application or TCP listener; only the test window is closed, and its processing
  child is reaped. This harness uses explicit paths; chooser routing also has
  Rust coverage. Native macOS chooser interactions were also checked in an
  isolated test app: image-picker cancellation, nine-image folder import,
  two-file multi-selection, and PNG save into ignored artifacts all completed.
  That test app was closed without touching the primary preview.
- `npm run smoke` retains the existing measured calibration, mask, project,
  independent intensity, square-pixel/orientation and shared gesture checks.
  `npm run tauri:smoke` retains the bundled native calibration check, but that
  check timed out in this session after peak picking. Scientific commands were
  observed completing while its UI wait stopped advancing. The same timeout
  was reproduced with the baseline App, RasterView, PatternView,
  ImageIntensity and Python session temporarily restored in this worktree;
  all implementation files were then restored. This remains an unresolved
  native calibration-harness qualification gap, not a passing native
  calibration result. Python and browser calibration regressions pass.

Generated reports and screenshots are under ignored `desktop/artifacts/`.
These are scoped regression checks, not full Qt/cross-platform qualification.


## Separate map window (2026-11-04)

The map toolbar offers a Detach map icon. Only the scan panel
moves; its histogram, active layer, smoothing, contours and exports stay with
it. The main window returns to Integration and remains navigable. Map mode's
Points/Layers/Grid controls remain available while detached. Show map reuses the
existing child; Dock map returns to Map mode, while closing the child leaves
the current main mode intact. The main window owns the processor and closes its
child on exit. Child closure never shuts down the processor.

The native child may read only map_snapshot/map_display/map_levels. Mutations
are forwarded to the main window's existing ordered queue, including rapid
cell selections. Read-only map_snapshot returns no detector/cake buffers and
does not increment the scientific revision. A cell selected while Integration
is active calculates the full current image/pattern/cake display. Stored map
profiles and normalized map values are untouched. Docked Map selections retain
the stored-profile behavior and mark Integration for calculation when entered.
Shared scan preferences retain palette, log/linear, smoothing, contours and
manual limits for unchanged raster contents. Native window geometry is persisted across reopening; plot zoom is not. Live polling retains its existing
mode-exit behavior.

Verification commands: `node desktop/scripts/map_window.mjs` (add `--webkit`
for WebKit), `node desktop/scripts/map_smoke.mjs`,
`.venv/bin/python -m pytest desktop/tests/test_map_workflow.py`,
`npm --prefix desktop run build`, `npm --prefix desktop test`,
`cargo test --manifest-path desktop/src-tauri/Cargo.toml`, and the isolated
`npm --prefix desktop run tauri:smoke -- --map`. The native Map smoke includes
child movement/resizing, binary snapshots, linked selection/cake, docking,
reopening/closing and continued main-session access.

Verified during this follow-up: 25 Map Python tests passed; calibration/session/
bridge regressions passed (39 passed, 5 skipped); 48 frontend unit tests and
10 Rust tests passed. Chromium and WebKit checks cover detach/select/dock,
rapid selection order, shared layers and PNG output. Additional checks cover
palette, manual contrast/log retention and the 460 × 360 child with larger
text. The isolated WKWebView Map smoke passed independent child movement and
resize, binary map reads, complete linked Integration displays, docking and
child closure without stopping the processor. Window-manager checks used only
the test process; the existing preview was not restarted.


Primary-preview integration (2026-11-04): combined the detached map with the
newer shared cake recalculation fix. Map selection retains raw/corrected detector
responses and clears stale rings/timing; detached selections in Integration
calculate the full current pattern/cake. Both regression cases remain covered;
all 27 Map Python tests and the detached-window browser workflow pass in the
primary checkout.


## Remembered placement and detached placeholder (2026-11-04)

Native Map saves logical inner size, normal frame dimensions, monitor identity
and the logical offset within its work area. Docking, closing the map, closing
the main window and quitting flush the last normal geometry to an atomic,
versioned JSON file in the application configuration directory. Reopening uses
the same monitor and relative position even after monitor rearrangement or DPI
changes; size and position are clamped to the available work area. If the saved
monitor is absent, the main window's current screen (or primary screen) is used.
Minimized/maximized bounds do not replace the last normal bounds. Missing or
malformed settings fall back to the normal window defaults.

The in-window Expand map control is removed. Dock map is an icon with an
accessible name and tooltip in the child and the main Map placeholder. Detaching
retains the original map column and dividers: a quiet message and Show/Dock
icons replace only the scan panel. There is no header above the Map workspace,
and the detector, controls and pattern retain their original layout.

`node desktop/scripts/map_window_geometry.mjs` uses disposable settings and
isolated native windows to verify docking/reopening and persistence through a
complete application restart. Rust tests cover negative monitor origins,
disconnected screens, duplicate monitor names, scaling/rearrangement and invalid
saved data. Headless Chromium/WebKit checks cover the retained column bounds,
icon-only docking, removed expansion control and existing linked selection.


## Shared Map phase and overlay display (2026-11-04)

Map and Integration use the same overlay/phase serialization and pattern
renderer. Point selections retain shared visible reference curves and phase
reflections, including legend names/colors and pressure/temperature. Overlay
scale/offset and measured-pattern visibility/color follow the shared Integration
settings; management controls remain in Integration. Both legends are displayed
in Map. ROI windows and their editing retain the existing behavior.

Map's local radial-unit display converts measured points, overlay coordinates
and phase reflections together. When stored map units differ from the shared
Integration unit, overlay coordinates are first converted into the stored map
unit using the session wavelength. Stored and normalized map profiles are never
modified by reference display. Structure-based phases extend their reflection
coverage to the selected pattern's actual radial range/unit, matching Qt.

Verification: `node desktop/scripts/map_references.mjs` (also `--webkit`)
covers loaded references, map point changes, all radial units and intensity
scales, shared visibility/pressure/temperature/scale/offset, and detach/dock.
`npm --prefix desktop test` includes independent unit-conversion checks.
Python Map/Integration tests cover shared reference values with mismatched
stored/display units, normalized/stored-only profiles and extended CIF coverage.
