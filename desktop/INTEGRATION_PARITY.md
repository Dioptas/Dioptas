# Integration workflow comparison

Implemented on `codex/desktop-integration` from checkpoint `4ef2ca3d`, using
current read-only Qt source at `/Users/clemens/Programming/Dioptas` and the
corresponding scientific models in this checkout. Comparison date: 2026-11-01.

The reference includes `widgets/integration/control/{ImageWidget,PatternWidget,
OptionsWidget,BackgroundWidget,CorrectionsWidget,OverlayWidget,PhaseWidget}.py`,
`widgets/integration/display/`, and `controller/integration/` (including the
nested overlay/phase controllers). The Qt view places its image/cake on the
left and control groups above the pattern on the right. The desktop now uses
that arrangement: the image/cake occupies the full-height left half, with the
controls in the upper-right pane and integrated pattern below them. Image/Cake
buttons switch the left display, retaining independent histograms. Both Qt-style
dividers support dragging, arrow keys and Home/double-click reset. The control
groups use the width of the upper-right pane rather than a tall sidebar. Left
mode navigation remains unchanged. This is a working, scoped workflow, not full
Qt replacement.

The former Options tab now lives in Settings → Integration: radial units,
automatic/manual binning, supersampling, 1D/cake azimuth ranges, cake bins,
solid angle, polarization, Poisson errors and zero trimming. The command and
project storage are unchanged; task controls stay in the Integration workspace.

| Qt workflow | Desktop implementation |
| --- | --- |
| Load image, previous/next, file step, number/time order | Existing ImgModel/FileNameIterator; file step and order controls; multiframe index shown when available; File Info exposes actual metadata |
| Load calibration | Native PONI chooser, existing CalibrationModel, shared calibration workflow retained |
| Image / cake switching and pattern inspection | Shared RasterView, PatternView and plot navigation; Qt Image/Cake switching, full-height image pane and controls-over-pattern split; linked clicks in all three views |
| Image intensity controls | Independent ImageIntensity for detector and cake, both default above the images; full-resolution arrays, original orientation, top-origin display rows, square detector pixels and existing gestures |
| Radial units and automatic/manual binning | Existing Configuration integration for 2θ, Q, d; Auto passes None to model; actual count displayed; manual counts 1–100000 |
| Supersampling | Existing CalibrationModel.set_supersampling, with fresh cake geometry to invalidate old pyFAI array caches; original image is still displayed at source resolution |
| 1D / cake azimuth options | Independent full/custom ranges, including sectors crossing ±180°; cake azimuth bin count; cake radial axis stays 2θ as in the synchronous Qt configuration model |
| Integration corrections | Solid angle, polarization and Poisson errors; XYE/FXYE require calculated errors; trim trailing zeros |
| Shared mask | Apply, transparency, native load/save; existing brush/eraser and stroke undo preserved; full dedicated Mask workspace belongs to the separate branch |
| Image background | Native load/remove and scale/offset, using ImgModel's subtraction pipeline; wrong-shape files are rejected before replacing the active background |
| Pattern background | Existing SmoothBruckner/PatternModel, smoothing, iterations, polynomial order and optional radial range; displayed data uses PatternModel.data; background range converts with radial unit changes; save fitted background |
| Corrections | Mean-normalized flat field with load/remove/use; cBN seat and oblique detector absorption with existing model parameters; active corrections rebuild on geometry changes |
| Pattern load / previous / next / save | Existing PatternModel iterators and Configuration writers; XY, XYE, CHI, DAT, FXYE; raw or background-subtracted save; background-only XY/CHI/DAT; no top-level Export pattern button |
| Autocreate | Existing Configuration._auto_save_patterns on explicit successful image load/navigation; output-folder chooser, selected formats and explicit Apply; normal and bkg_subtracted folders follow Qt; off after project reopen |
| Folder integration | Existing configuration.batch_model discovers same-extension files and their frames, integrates with current geometry/mask/corrections, reports progress and permits cancellation between frames; complete batch saves to model HDF5 or CSV; no duplicated Map workspace |
| Overlays | Native file import/current-pattern capture, visibility/color/scale/offset, delete, waterfall/reset, assign/remove pattern background; measured curves render on shared axes and participate in auto scaling |
| Phases | JCPDS/CIF/EOSMAT import, real PhaseModel pressure/temperature, apply-to-all, literature-reference selection when available, visibility/color/delete; computed reference sticks render in actual pattern units |
| Project persistence | Standard .dio models retain settings, backgrounds, corrections, overlays and phases. Autocreate is a session opt-in, never silently restored from a project. |

## Deliberate boundary handling

- Scientific ownership remains on DesktopBridge's single processing worker.
  Progress and the existing cancel event bypass it. A single pyFAI call is not
  interruptible; folder cancellation is observed between completed frames.
  Cancelled/failed batches restore the preceding complete batch, and the
  previously viewed file/frame is restored. Partial batches are not published.
- All new file/folder commands have Tauri native chooser routes, including
  cancellation. Updates, frame stepping, correction toggles and reference edits
  do not open dialogs. The browser chooser is only a test harness.
- Wrapped sectors explicitly select pyFAI's zero discontinuity while the
  calculation runs, then restore its normal ±π convention. Otherwise current
  pyFAI warns that a sector such as [150, -150] gives partial results. The
  numerical reference test uses the same explicit discontinuity with the Qt
  Configuration model. Cached angular-width arrays are cleared when switching
  discontinuities; the ordinary and wrapped cake comparisons pass at 1e-6 relative
  tolerance.
- Qt passes degrees to cBN but radians to oblique detector absorption. Its
  project correction reconstruction currently passes degrees to both. The
  desktop adapter normalizes these inputs, including after project load, so
  applied OIADAC corrections round-trip consistently. Original Qt/model files
  are unchanged.
- Overlay files keep their numerical x coordinates, matching Qt. They are not
  silently converted or assigned an inferred wavelength/unit. The UI asks for
  matching coordinates. Phase positions use PhaseModel conversion instead.
- Phase sticks show relative source reflection intensities (normalized to 30%
  of plot height); they are reference marks, not predicted measured counts.
- Numerical controls use explicit Apply actions. These do not launch model
  signal-driven background processing, a scientific HTTP service or Qt app.

## Integration contracts for merging the view branches

- `dioptas/desktop/integration.py` owns the IntegrationWorkflow mixin and all
  `integration_*` commands. Session only inherits/routes it, adds
  `state.integration`, refreshes PatternModel display data, invokes the scoped
  1D/2D adapters, and triggers autocreate after image loads.
- `desktop/src/integration.ts` owns IntegrationState and its command callback.
  `IntegrationView.tsx` contains the task tabs; `IntegrationPlotControls.tsx`
  contains the image toolbar and pattern tools;
  `integration.css` scopes its layout. `IntegrationWorkspace.tsx` owns the two
  resizable Qt-style dividers. App continues composing the existing
  detector/cake/pattern renderers. No renderer or gestures were copied. Identical
  cake payloads from overlay/phase-only changes preserve manual intensity limits.
- `State.bins` now accepts `null` for Qt automatic binning. `State.integration`
  is additive. Pattern responses optionally carry measured `curves` and
  `phaseLines`. PatternView's additive `curves`/`referenceLines` props default
  to empty and preserve calibration behavior; all modes share axes/gestures.
- `_next_image` accepts optional step=1. Linked detector inspection and ring
  contours use original-pixel geometry when supersampling is active. Default
  calibration behavior stays unchanged. PONI save temporarily restores physical
  detector pixel pitches so computational supersampling is never exported as
  changed detector hardware. Shared mask commands/contracts stay
  unchanged for the Mask branch to extend.
- Folder operations use the selected configuration's existing BatchModel, so
  the Map branch can consume the same results; no Map controls are added.
  A separate stdio progress/cancel protocol is unnecessary.

## Remaining Qt scope

- No new-file watcher / continuous beamline acquisition, image sum/average/save
  batch modes or stage/EPICS controls. Explicit loads and
  folder integration work; automatic unattended acquisition is not claimed.
- No transfer-function correction editor or formula/density-driven sample
  slab/cylinder/sphere/plate editor. Existing project data for these remain
  owned by the original models; this UI edits flat field, cBN and OIADAC only.
- No spottiness display/export, cake integral, image/cake export or detachable
  plot windows. Detector ROI limits can be edited numerically; graphical
  resize handles are not implemented.
- Phase database browsing, material/reflection/EOS editing and phase-list
  save/load are not implemented. File loading and existing reference choices
  work. CIF conversion currently uses model defaults for cutoff/minimum d.
- No overlay drag/reorder or intensity matching; scale/offset and waterfall work.
- No configuration switching, explicit HDF5 source/dataset chooser, portable
  Python bundle or Windows/Linux qualification. Background unit conversion and
  overlay input units follow the qualifications above.

## Validation

- Own CPython 3.13.7 environment: `uv sync --python 3.13 --extra test`;
  own desktop dependencies: `npm ci`.
- `desktop/tests/test_integration_workflow.py`: 20 passed. Independent
  Configuration comparisons cover 2θ/Q/d, radial/cake binning, sectors, solid
  angle/polarization/errors; tests also cover automatic bins/supersampling,
  original-pixel linked inspection/PONI after supersampling, image subtraction/flat
  field, invalid-file/detector-shape preservation, absorption/project
  round trips, pattern background/range conversion, all five pattern formats,
  overlays/phases, autocreate, model HDF5/CSV and real-worker cancellation.
- Full desktop plus Pipeline/MainController/CalibrationController suite:
  144 passed, 5 skipped (optional Dioptrin and existing skip).
- `npm run build` and expanded real-model `npm run smoke` pass. Browser checks
  exercise calibration, histograms, gestures, compact/large-text layout, then
  Integration options, visibility choices, overlays, phases, backgrounds, saving,
  file order, mask and detector correction; no browser errors.
- `cargo test`: 3 passed, including new chooser-routing assertions.
- `npm run tauri:smoke`: bundled native WKWebView passes measured-image
  calibration and Integration settings (600 radial / 90 azimuth bins), overlay
  rendering, phase reflections and pattern save through stdio. Both histograms
  remain visible. No Qt application or scientific TCP listener; its own
  processing child is reaped. No primary-preview port is used. The final native
  rerun passed after macOS was unlocked, including the completed geometry/cache
  guards and original-pixel PONI save handling.

Evidence lives under ignored `desktop/artifacts/`, including
`integration-pytest.log`, `integration-regressions.log`, `browser-smoke.json`,
`integration-controls.png` and `tauri-native-smoke.json`. These are scoped
workflow checks, not detector-wide scientific accuracy qualification.

## Qt layout revision (2026-11-01)

The image spans the left column; controls and pattern share the right column,
with controls above the pattern. The initial image/analysis split is 50/50, with
38% of the right column assigned to controls. Splitters preserve usable minimum
pane sizes. Image/Cake selection does not integrate or recreate scientific
models. Both shared image instances retain their display preferences.

`integration_layout.mjs` checks pane alignment and proportions, pointer/keyboard
resizing, Image/Cake switching, 1000 × 760 layout and larger text. The expanded
browser suite also exercises calibration, all three plot gestures and the
scientific Integration controls in this arrangement. Native smoke checks the
same pane geometry before exercising the existing real-model workflow. Build,
expanded browser smoke and bundled WKWebView smoke pass for this revision.
Screenshots are `artifacts/integration-qt-layout.png`, `integration-qt-cake.png`
and `integration-qt-compact-large.png`; native evidence includes
`qtIntegrationLayout: true` and processing-child cleanup. Scientific model code
is unchanged by the layout revision.


## Qt controls revision (2026-11-02)

The detector/cake toolbar sits below the left plot, as in Qt. It exposes Image /
Cake, mask use and transparency, raw/corrected image display, ROI use and numeric
limits, phase guides and continuous intensity autoscale. Full-circle cakes have
an azimuth-shift slider; it rolls complete display rows and adjusts axis/readout
coordinates without changing the scientific cake. Detector and cake histograms
remain independent. ROI uses Configuration.roi and its existing integration mask;
the display shades the excluded area. Raw display/readout does not disable
background subtraction or absorption corrections in the integration model.

Pattern controls are grouped down the right edge: 2θ / Q / d, Log / √,
background subtraction / inspection, AA and automatic axis range. Manual plot
navigation clears automatic range; enabling it refits the axes. Square-root
scaling clips negative display intensities to zero as Qt does. Background
inspection draws the original measured curve and model-extracted background
alongside the subtracted pattern. The top pattern row provides save, capture as
overlay/background and calibration loading. No inactive placeholder buttons were
added for undocking or image export.

The task tabs use one flat tab strip, compact aligned forms and fixed relevant
Apply actions. Background and Corrections have Qt-style category menus; overlays
and phases use rows with visibility, color and editable values instead of tall
per-item forms. The image tab focuses on files/navigation, mask files and folder
integration. Calibration loading and quick mask controls live beside their plots.

Quick unit switching exposed xypattern background extraction during an
intermediate descending d-spacing conversion. The desktop adapter suspends
extraction during conversion, restores the same background parameters after the
new radial samples exist, and preserves enabled state. Regression checks cover
2θ → Q → d → 2θ with full and restricted background ranges.

Validation for this revision: build and JS tests pass; desktop Python tests have
128 passed and 4 optional skips, including 27 integration workflow checks. The
browser checks exercise the new plot tools, ROI editing, azimuth shift, unit
switching with fitted backgrounds, frozen/automatic ranges and compact/larger-text
layout. Bundled Tauri/WKWebView smoke passes the existing calibration, Integration,
Mask and binary-transfer workflows. The main window now has explicit read/set
title permissions, which were required by the existing title behavior and native
smoke. Screenshots remain under ignored desktop/artifacts/.


The Integration tab strip shares Calibration's flat tab styling and keyboard
navigation (arrows, Home and End). Its order is Image, Pattern, Overlay, Phase,
Background, Corrections. There is no manual Integrate image button; image loads
and integration-setting changes calculate automatically. Only relevant background
and correction Apply actions occupy the fixed task footer.


## Overlay Qt recheck (2026-11-02)

Compared directly with `OverlayWidget`, `OverlayController`,
`OverlayInPatternController`, `PatternWidget` and its `ExLegendItem`. An isolated
offscreen capture of the original widget is in
`artifacts/overlay-qt-reference.png`; no user Qt window/settings were used.

The Overlay pane retains Qt's left icon rail (load, delete, clear, up/down),
central selected-row table (show, color, Name, Scale, Offset), and right parameter
rail (Scale Step, Offset Step, Waterfall/separation/Reset and As Bkg). Names edit
on double click or F2/Enter. New rows select and scroll into view; selection
follows the same overlay through reordering. The selected overlay curve draws
slightly thicker and above the other curves, including without antialiasing;
selection changes no scientific data. Table checkboxes remain vertically
centered, and As Bkg matches Waterfall's button height and padding. The active tab, selected row and
local step sizes survive visits to other modes. Following the 2026-11-03 interface
correction, numeric fields use standard native spin boxes, while Scale Step,
Offset Step and waterfall separation retain Qt's 1–2–5 progression for both
mouse arrows, keyboard stepping and mouse-wheel input. Row Scale/Offset wheel
steps use their respective step-size fields, and numeric-field wheel events
do not scroll the parameter rail. Waterfall has a compact Reset icon beside it;
As Bkg is pinned below the scrolling options so it remains visible at the
minimum pane height. Table rows and options use the same explicitly sized
visible scrollbars as calibration, including a horizontal scrollbar when columns
exceed the available width. The table header sits above the scrolling items and
follows their horizontal position. The left action rail retains spacing within Open/Delete and Up/Down pairs;
only the Clear-all group and its divider spacing collapse when the pane shrinks.
Every icon fits at the minimum pane height without a scrollbar. Scientific numeric
limits remain enforced, including the model's clamping of negative scaling to zero. The show-column header toggles all overlays. Clear all uses the same red ListX
icon and anchored confirmation dialog as calibration peaks, with Cancel focused
and Escape/outside-click dismissal. Right click or
Shift+F10 opens Match intensity, using the same overlap/interpolation and
least-squares factor as the original Qt controller.

Load selects multiple files and remembers the overlay directory. All numerical
work uses the existing OverlayModel. Waterfall keeps Qt's bottom-up negative
offsets and stores separation in the existing project view state. As Bkg toggles
the selected overlay, hides it while assigned, and restores visibility when
unassigned/replaced. Assignment uses the stable overlay UID, surviving reorder
and project round trips; removing/clearing an assigned overlay clears its
background reference. The pattern plot shows Qt-style borderless, colored,
right-aligned names, which can be dragged. Files can be displayed before a
current pattern or calibration exists. The desktop starts with empty pattern
data so xypattern's default demonstration curve cannot appear in this case.

Remaining interface differences are the native browser color picker rather
than QColorDialog, numeric text edits committing on Enter/blur (spin buttons
and arrow keys apply immediately), and scrolling inside table/parameter rails
at compact pane sizes. Overlay file x coordinates retain Qt's numerical-unit
semantics; no automatic unit reinterpretation was introduced. The native
multi-file dialog route is covered by Rust tests and the real-model chooser
harness; the modal OS picker was not manually exercised in this recheck.

Verification in the assigned `codex/overlay-qt-controls` checkout:

- Build and 20 existing JavaScript tests pass; eight Rust tests pass.
- Desktop Python suite: 162 passed, five skipped, including seven focused
  Overlay cases for Qt intensity-match parity, visibility, order, waterfall,
  background subtraction/persistence/removal, multi-file load and empty startup.
- `scripts/overlay_controls.mjs` passes Chromium and WebKit at 1440 × 1000 and
  1000 × 668, with both text sizes, exercising real-model controls, overlay-only
  plotting, selected-row/step retention across modes, legend dragging and table
  scrolling. Reports/screenshots: `artifacts/overlay-*`.
- The complete browser smoke passes calibration and existing Integration
  regressions. Bundled Tauri/WKWebView smoke passes, including overlay capture,
  selected-row reorder, As Bkg toggle, waterfall/reset/delete and processing-child
  cleanup. No development server or port 1420 was used.

Implementation is isolated in `src/IntegrationOverlayControls.tsx`,
`src/integrationOverlayControls.css`, `src/OverlayPlotLegend.tsx`,
`src/overlayPlotLegend.css` and `dioptas/desktop/overlay.py`, with narrow state,
view, dialog and session initialization hooks. Existing snapshotted changes
were preserved; this work was not committed, pushed or merged.



## Overlay import into the main preview (2026-11-03)

The Overlay changes were applied to `codex/react-desktop`, preserving the newer
Image/Pattern file controls and adaptive readout work. The live Tauri development
preview rebuilt and restarted its Python worker with the imported boundary.
Build, 43 focused Overlay/Pattern/Integration Python tests, Chromium/WebKit Overlay
checks and bundled native smoke pass in the primary checkout. The native binary
benchmark now waits for the calibration controls to become ready before stepping
images; its first import check clicked a still-disabled Next image button.
Changes remain uncommitted.


### Original-pattern visibility for waterfall figures (2026-11-03)

The table has a pinned **Original · filename** row with a visibility checkbox,
a white color swatch and read-only Scale 1 / Offset 0. It stays above the scrolling
overlay items and cannot be renamed, reordered, deleted or assigned as its own
background. Selecting it emphasizes the measured curve. Arrow-key navigation
includes this fixed row; ordinary overlays retain their stable-UID selection.
Clear all removes only actual overlays and leaves the Original row in place.

The checkbox is checked by default and replaces the separate checkbox beside
Waterfall. Unchecking hides the measured curve and its legend entry while
preserving overlays. Auto range and X-range fitting use the visible curves;
manually held ranges are preserved. Clearing all overlays restores the original,
and its checkbox remains usable even without overlays. Visibility affects
only display: scientific arrays, background subtraction and numerical pattern
saves are unchanged. It is stored in `PatternParams.visible`, saved in `.dio`
projects and included in the shared Undo/Redo history. No placeholder overlay
is added to the scientific model.



## Overlay display refinements (2026-11-03)

The pinned Original row has the same square native color well as other rows.
Its color and visibility affect only the displayed measured pattern. The color
is stored in `PatternParams.color`, saved in `.dio` projects, and participates
in the same chronological Undo/Redo history as overlay edits. Original
visibility follows the same history and persistence rules, including when no
overlays exist. Restoring Original color or visibility uses the pattern-only
update path and leaves unchanged mask pixels alone. Clearing all overlays or
removing the final overlay restores Original visibility as part of that same
undoable operation. Signed waterfall separation follows the 1–2–5 stepping sequence through zero, including
mouse-wheel and native spin-button interactions.

The Color header offers Viridis, Plasma, Magma, Inferno, Cividis and Turbo with
reversal. Dark endpoints are trimmed against the charcoal background; previews
use the same sampled range. Applying a scale affects actual overlays in table
order and is one undoable transaction, retaining the Original color.

Overlay edits return a pattern-only response. They neither disable the task
controls nor resend mask, image, cake, rings or linked-selection payloads.
Overlay Undo/Redo preserves calibration diagnostics and skips calibration,
detector, mask and cake recomputation. Unchanged configurations are left alone
during shared model history restoration. Detector/cake draw callbacks depend
on actual view coordinates and stable guide inputs, avoiding redraws from
unrelated React renders. Consecutive scale edits to one overlay form one Undo
step; offset edits form a separate step. Another changed field/overlay or
history navigation ends the group, including when edits are separated by pauses.

Table rows use 23px native numeric fields and minimal vertical padding (about
26px total), with centered checkboxes and unchanged 20px square color wells.
The larger macOS native color panel is anchored to the initiating color well
and constrained to that display's visible work area. Its command is explicitly
registered in the Tauri manifest and main-window capability. Window-update
notifications cover floating panels that open without becoming key.

Validation: Chromium and WebKit overlay interaction checks include full
command completion, grouped Undo/Redo, stable table enabled states, and no
detector/cake canvas redraws during overlay color, scale, offset, visibility
or history changes. Python checks guard against calibration/image/mask/raster
work on those paths. Native picker tracing confirmed a visible 250×397-point
panel directly below the initiating 20×20-point swatch. The primary preview was
saved and restored across its normal native-host rebuild; backups are in
`desktop/artifacts/main-preview-overlay-final-20261103*.dio`.


Original-color history checks cover mixed Original/overlay color ordering,
Undo and Redo, invalid-color rejection, `.dio` round trips, unchanged detector
and cake canvases, and stable table enabled states in Chromium and WebKit.
The direct native smoke runner timed out without a report in this session;
the same built application passed the smoke check when launched as the
registered macOS test bundle. Desktop/Pattern/History Python checks passed
226 tests (5 skipped); model-state/project regressions passed 63 (1 skipped).


Original-visibility history checks cover mixed visibility/color/overlay edit
ordering, Undo/Redo, hidden-state `.dio` round trips with and without overlays,
unchanged numerical pattern data, and invalid boolean rejection. Chromium and
WebKit checks include checkbox/plot synchronization and stable detector/cake
canvases and table fields across visibility Undo/Redo.


## Image file browser and autoprocess (2026-11-02)

The Image tab follows Qt's BrowseFileWidget: Load image and Autoprocess beside
previous/next, a real native step spinbox and By Name / By Time choices. Step
sits directly beside its value. Filename and directory are editable; Enter in
the filename loads it relative to the entered directory, and Load image also
loads an edited filename. With an unchanged filename, Load image opens the
native chooser in that directory. Enter in the directory changes the working
folder; its ellipsis button opens the native folder chooser. File Info expands
actual metadata. Mask-file and folder-integration controls are removed from
this tab. Frame selection remains available for multiframe images, and file
step survives tab switches.

Autoprocess can be enabled after selecting a folder, even before loading the
first image. While Integration is open (and Settings closed), commands poll the
existing NewFileInDirectoryWatcher once per second on the scientific worker.
The watcher does not start another thread: its file notifications only enqueue
paths. It baselines existing files and accepts new supported detector files once
they are nonempty and have stable size/modification time across two scans.
Every ready file is loaded and integrated in queue order using the current
geometry, mask and corrections. Autocreate also saves these patterns when
separately enabled. An unreadable image is reported in the shared footer and
does not block subsequent files. Foreground actions wait for an in-flight
automatic load instead of being dropped. Disabling clears the queue; changing
folders starts a new baseline. Autoprocess is off after opening a project or
the example. It does not integrate files already present when enabled, and
arbitrary multi-image selection and the remaining Qt batch modes are separate.

Focused Chromium/WebKit checks cover the spinbox, label alignment, folder
chooser, typed directory/filename, Enter/Load, real incoming-file integration,
disable and Escape, plus normal/large-text layout and existing splitters and
Image/Cake behavior. The controls occupy 174–175 px without scrolling at
1440 × 1000 and 1000 × 760. Seven new Python tests cover stable/empty/growing
files, every queued image, failed-file recovery, folder changes, real numerical
integration, autocreate and session reset. Screenshots and the focused runner
are under ignored `artifacts/integration-image-*`; reusable browser assertions
live in `scripts/integration_image_files.mjs`.

Validation for this revision: build, 20 JavaScript tests, eight Rust tests,
167 Python tests (five skips), focused Chromium/WebKit file-browser checks and
bundled Tauri/WKWebView smoke pass. The native smoke confirms the existing
calibration/Integration/Mask workflows, binary transfer and processing-child
cleanup; incoming-file behavior is covered by the focused real-model browser
checks and Python tests.




## Qt Pattern file controls (2026-11-02)

The Pattern tab follows Qt PatternWidget/BrowseFileWidget: Load pattern above
Autocreate, previous/next above a real step spinbox, By Name / By Time choices,
editable filename and directory rows, a native directory chooser and one row
of Pattern types (.xy, .xye, .chi, .dat, .fxye). Image and Pattern share
IntegrationFileNavigator and integrationFileControls.css so their spacing,
alignment and native steppers stay consistent. Each tab retains its own step
across tab switches; file order is owned independently by its existing model.

Enter or Load loads an edited filename relative to the selected directory.
The native load chooser starts in that directory. Loaded patterns display their
actual filename, including extension. Browsing uses PatternModel's existing
number/creation-time iterator with the selected step. The directory is also
the autocreate output folder, matching Qt. Autocreate and format selections
apply immediately, without Apply autocreate or a separate tall form. Existing
format validation and Poisson-error prerequisites are preserved. The save icon
beside the pattern remains the manual save action and saves the displayed
background-subtracted pattern, as Qt does; the duplicate save controls are
removed from the tab. Changing file order, formats or Autocreate preserves the
loaded curve and existing scientific corrections/backgrounds.

Seven new Python checks cover filename/folder entry, number/time browsing and
custom steps, invalid-entry preservation, chooser cancellation and immediate
autocreate with actual output files. The focused Chromium/WebKit runner checks
both Image and Pattern controls against real models, spinbox behavior and
retained values, independent file orders, and actual autocreated XY/CHI files.
It also checks both tabs at 1440 × 1000 and 1000 × 760 with both text sizes;
Pattern controls fit without scrolling. Screenshots are under ignored
artifacts/integration-pattern-*.png, and reusable browser checks are in
scripts/integration_pattern_files.mjs.

Validation: build, 174 Python tests (five skips), 24 JavaScript tests, focused
Chromium/WebKit Image-and-Pattern checks and bundled Tauri/WKWebView smoke pass.


## Scientific image and cake export

The image toolbar save icon exports the current view to PNG at Qt's 2048-pixel
width, retaining the plot range, palette and phase guides while omitting ROI and
inspection markers. TIFF saves scientific detector/cake arrays with Qt's flipped
rows and int32 convention. Cake TXT/CSV includes radial/azimuth coordinates;
scientific exports retain the original array independently of display shifts.
The native dialog offers only formats valid for the current source. Python tests
cover real image/cake data, orientation, coordinates, PNG decoding and validation.


## Pattern phase-line scaling (2026-11-02)

Pattern phase sticks now follow Qt `PhaseModel.get_phase_line_intensities`:
each phase's strongest reflection within the visible x-range reaches the
measured pattern maximum in that range, capped at the upper y-limit, with
the lower y-limit as its baseline. Relative intensities are preserved without
the former fixed 30% height or minimum-height floor. Overlay and background
inspection curves do not set the phase height. Zoom, pan and new pattern data
recalculate the scaling locally; phase indices keep normalization independent
even when phase names and colors coincide. Log and square-root modes use the
transformed measured maximum and preserve relative stick heights on screen.

`scripts/phase_line_scaling.test.mjs` covers numerical scaling, zoom limits,
independent phases, overlays, descending d-spacing, display transforms and
empty/invalid data. Its linear reference cases were also checked directly
against the Qt model method. `node scripts/phase_line_scaling.mjs` checks actual
canvas strokes through rectangle/X-range zoom, pan, wheel, reset and both
nonlinear intensity scales in an isolated browser fixture.

Validation: build, 20 JavaScript tests, 28 integration workflow tests, the
dedicated phase-line browser checks and bundled Tauri/WKWebView smoke pass.
The broader browser smoke timed out at its calibration active-ring pixel-color
assertion; it did not complete on this run.


## Live pattern-background editing

Background parameters and range edits refit automatically through PatternModel;
there is no separate pattern-background Apply action. A bounded queue retains
only the latest waiting settings, while optimistic edge positions remain visible
until their fit returns. Inspect shows the original measured curve, fitted
background and draggable range edges; dragging inside still zooms. Escape
restores the pre-drag range. Disabled settings persist for the next enable, and
range bounds follow the measurement and radial unit. Focused browser helpers
cover numeric validation, edge dragging, cancellation and serialized live fits.
