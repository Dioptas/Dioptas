# Map workflow parity (2026-11-01)

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
  panel; detector and pattern occupy the right column, with Files/Layers/Grid
  task controls on the far right. Drag or use arrow keys on the dividers to
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
  radial unit. Detector/pattern inspection links only compatible radial units;
  a different displayed integration unit cannot silently move an ROI.
- Window add/remove/rename, numeric range editing, and opt-in draggable pattern
  regions/edges. Sum, Sum minus background, Mean, Maximum, Peak area, Peak
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

- PatternView has optional `regions`, `editRegions`, and `onRegionChange` props.
  Calibration defaults remain unchanged. Normal shared navigation is active
  until **Edit windows** is enabled; right-button navigation remains available
  during window editing. Updates are committed on release, not on every move.
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

- Qt's directory watcher / **Live** acquisition, follow-newest behavior and
  detached native map window are not implemented. The in-window resizable and
  expandable map is supported; no nonfunctional Live/Undock buttons are shown.
- Overlay loading/editing remains part of the shared integration work; Map can
  evaluate references to overlays already present in a project. It does not
  implement the full integration, mask or batch workspaces (batch background
  extraction, frame-stack visualization and batch pattern export).
- The stored map unit is used for the map pattern and its ROI controls. Qt can
  display this pattern in the integration view's independently selected unit.
  Pattern square-root scaling is not added to the shared linear/log renderer.
- Explicit HDF5 dataset selection follows the existing desktop boundary's
  limitation; supported ImgModel default datasets and processed batch formats
  work. There is no arbitrary beamline motor-coordinate importer.
- Display preferences and panel sizes are local to the mounted Map view; map
  scientific state is persisted. No portable Python runtime or Windows/Linux
  qualification is claimed.

## Validation

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
