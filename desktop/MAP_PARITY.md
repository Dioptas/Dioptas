# Map workflow parity (2026-11-03)

The GUI follow-up is in the assigned `codex/desktop-map` worktree, updated from
`codex/react-desktop` at `dd9795d3`. The primary preview checkout is unchanged.
Qt references were read from `/Users/clemens/Programming/Dioptas`, particularly
MapWidget, MapPanelWidget, MapLayerWidget, MapGridPopup, MapPanelController,
MapController and MapRoiInPatternController. Scientific integration, reduction,
layout and expression calculations continue to use the existing Python models.

## GUI follow-up

- Qt-like split layout: map on the left; detector and Points/Layers/Grid task
  tabs at upper right; pattern spanning the right side below them. Dividers
  support dragging, arrow keys, Home and double-click reset. Below 740 px of
  available analysis width, the detector moves into an Image tab. Below 850 px
  window width the panels stack. Expand map restores the full-width in-window
  map; it can be docked again. Task controls stay on the right.
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
  display changes retain the selected stored pattern. Reintegration is explicit
  through Reintegrate selected image or Rebuild; normal integration is deferred
  while Map is active if its shared mask settings have changed.
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
  resize the map/detector/pattern. Expand map and Dock detector / pattern
  provide a larger map in the same window. Narrow layouts stack the plots in a
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
- Processed HDF5/NeXus batch import through BatchModel, including stored radial
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
  bin interval, using a dedicated BatchModel instance. The independent batch
  workspace keeps its own data and normalization history. Repeated application starts from originals;
  invalid/nonpositive ranges are rejected. The `.dio` project retains normalized
  map patterns; a separate optional `react_map_normalization` group retains
  originals/range/reference for Restore after reopening in this frontend. Qt
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
  inside regions. Right-button navigation remains available during editing. Updates are committed on release, not on every move.
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

- A detached native map window remains unimplemented. The in-window resizable
  and expandable map is supported. Live/follow-newest is now implemented as
  described above; it does not monitor new frames inside existing HDF5 files.
- Overlay loading/editing remains part of the shared integration work; Map can
  evaluate references to overlays already present in a project. It does not
  implement the full integration, mask or batch workspaces (batch background
  extraction, frame-stack visualization and batch pattern export).
- The map and its table retain their stored radial unit. The pattern can now
  display 2θ, Q or d independently, with converted ROI interaction and the
  existing renderer's linear/log/square-root intensity scales.
- Explicit HDF5 dataset selection follows the existing desktop boundary's
  limitation; supported ImgModel default datasets and processed batch formats
  work. There is no arbitrary beamline motor-coordinate importer.
- Several display preferences and panel proportions are saved locally; the
  selected task tab and displayed radial unit are local to the mounted view.
  Map scientific state is persisted. No portable Python runtime or Windows/Linux
  qualification is claimed.

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
