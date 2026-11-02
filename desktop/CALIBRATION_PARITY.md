# Calibration workflow comparison

Compared on 2026-11-01 against this checkout's Qt
`dioptas/widgets/CalibrationWidget.py`,
`dioptas/controller/CalibrationController.py`, and the shared
`dioptas/model/CalibrationModel.py`. The Qt controller also matches the current
original checkout in `/Users/clemens/Programming/Dioptas`.

This is coverage of the calibration workflow, not a claim that the React
preview replaces the complete application. The original Qt interface is unchanged.

| Qt calibration option / interaction | React preview |
| --- | --- |
| Image → Pick rings → Calibrate → Validate | Compact step toolbar with Back/Next, one changing task panel and fixed fit action; image alone until Validate |
| Load image; previous/next image | Compact Open image button with adjacent previous/next arrows, using the existing file iterator |
| ±90° rotation; horizontal/vertical flip; reset | Visible labelled buttons in Image & detector; detector and image transformations stay aligned; stale peaks are cleared |
| Custom/predefined detector; detector file/reset | Experiment setup and Image & detector; loaded detector pixel pitches cannot be edited as custom pixels |
| Distortion spline load/reset | Image & detector |
| Calibrant selection | Bundled references plus custom `.D` import; custom content is owned by the session and embedded in project metadata |
| Wavelength / energy; distance; pixel sizes | Pixel sizes on Image; start values and linked wavelength/energy conversion in Calibrate → Parameters |
| Confirmation of experiment defaults | Image applies detector pixels on Next; applying the complete fit-parameter set confirms start values in Calibrate. The example supplies known fixture values |
| Individual distance/wavelength/PONI/rotation fit checkboxes | Fit parameters; all six geometry parameters free and wavelength fixed by default, matching Qt |
| Polarization factor | Fit parameters and both manual geometry conventions |
| Seeded automatic peak search / single local maximum | Qt-style automatic/single search radio buttons and search-size field, default 10 source pixels |
| Ring number and automatic increment | Qt-style current-ring spinbox, automatic-increase checkbox, image-side picking badge and highlighted fitted ring |
| Group positions and ring reassignment | Height-adaptive paged table with mean source pixel coordinates and editable ring assignment; positions remain visible at both text sizes |
| Multiple selection, delete, clear | Group checkboxes, select all, delete selected, individual removal, clear all; selected groups highlighted on the image |
| Peak edit history | Undo / redo buttons; Cmd/Ctrl+Z and Shift+Cmd/Ctrl+Z in calibration |
| Initial fit / subsequent refinement | Same pyFAI model entry points; optional separately installed Dioptrin adapter |
| Automatic refinement | Staged ring search/refit; enabled by default; Massif/Blob, Δ2θ, mean factor, intensity ceiling, ring count; Qt default values retained |
| Refinement progress / abort | Progress and cancel command remain responsive while the scientific session is busy; failure/cancel restores the pre-command geometry and picks |
| Mask use and transparency | Load mask, use-mask switch, transparent display; saving, drawing/erasing/history in the dedicated Mask mode |
| Calibrant lines and numbers | Independent display switches; reference lines also appear in the integrated pattern in its actual radial unit |
| Validation reference selection without changing geometry | Dedicated Validation calibrant selector uses the loaded/fitted geometry wavelength; changing reference clears the old RMS diagnostic |
| Linked detector/cake/pattern validation | Stationary validation click propagates the matching 2θ contour, cake line and pattern position; Q/d conversion uses the actual wavelength |
| pyFAI and Fit2D geometry inspection/input | Visible validation tabs with complete unit-labelled fields; Enter manually opens the same editor in a dialog from any step |
| Load/save calibration | Fixed Load .poni / Enter manually entry actions on every step; fixed Refine / Save actions on validation; existing PONI reader/writer and `.dio` project persistence |
| Image intensity/log/colormap | Each image has its own histogram, Auto and colour picker; small settings dialog for limits, auto modes, linear/log, size and horizontal/vertical layout; counts use every finite source pixel |
| Moving mouse readout | Coordinates and original-pixel intensity sampled during continuous movement at about 10 Hz; one app footer also reports cake/pattern/map values and workflow messages |
| Wheel zoom | Non-passive native wheel listener captures the event in each plot; the workspace does not also scroll |
| Plot rectangle zoom, pan, zoom out | Shared implementation for detector, cake and pattern; per-plot horizontal/rectangle choice |

## Deliberate differences

- Right click expands a plot range 2×; right double-click restores the complete
  fitted view, matching Qt. Square detector pixels are retained while resizing
  an already zoomed view. The detector's axes, ticks and outer card are removed;
  its readout and peak table use top-origin display rows without flipping data.
- The integrated pattern defaults to horizontal zoom with automatic intensity
  scaling. Detector and cake default to rectangle zoom. Both modes are selectable.
- Clicking the image picks only in Pick rings. Validation clicks inspect a radial
  position, avoiding accidental changes to calibration points.
- Fit input validation counts the actual free parameters. This is only a minimum
  equation count, not a claim of identifiability or a well-constrained geometry;
  users should distribute peaks across rings and azimuths.
- Numeric setup, fit constraints and refinement options have explicit Apply
  actions. Image applies detector settings and continues with Next; complete
  start values are confirmed on Calibrate. Mask controls stay directly visible in Image. Fitting is disabled while drafts differ from the applied state.
- The native adapter corrects the existing Fit2D model path's pixel-X/pixel-Y
  swap for non-square pixels. This is local to the new adapter; the original
  model and Qt application were not modified.
- Cake coordinates remain actual 2θ even when the pattern uses Q or d, following
  the existing synchronous configuration API.
- PyFAI is the default, including when Dioptrin is installed. No server is started
  by the desktop host. The optional native adapter currently requires a flat,
  uniformly sampled detector without a distortion spline.

The Export pattern button has been removed as requested; the underlying export
command and numerical round-trip tests remain.

## Sidebar layout recheck (2026-11-01)

Rechecked the original Qt checkout's `CalibrationControlWidget`,
`CalibrationParameterWidget`, `StartValuesGroupBox`, `PeakSelectionWidget`,
`RefinementOptionsGroupBox`, and geometry widgets. An isolated offscreen Qt
widget capture confirmed the form grouping and persistent alternative-entry
buttons without loading or writing user settings.

The React sidebar now exposes image transformations and detector files directly,
uses aligned value/unit/fit columns and compact refinement rows, and keeps one
set of fit inputs on Calibrate. Validation starts with its reference selector
and visible pyFAI/Fit2D tabs rather than a collapsed editor and a partial geometry
summary. The sidebar requires no scrolling: Image contains only image/detector
controls; Parameters / Refinement tabs divide Calibrate, and the peak table pages its
rows to match the available height. All controls, group positions and actions
remain visible with normal or larger text. Refine/apply, save and load/manual
entry actions are fixed below the content. Mask use, transparency and the mask-load
button sit directly below the detector tools; no extra setup menu is needed.
Manual entry uses a modal dialog with Escape/focus handling. Geometry drafts
survive tab changes; unapplied changes disable refine/save, and Apply geometry submits the
active convention from the fixed action bar. Cancelling Load .poni retains the
current step.

The processing-engine selector is available only under Settings → General;
custom calibrant loading sits beside the Calibrate → Parameters calibrant
selector, and mask controls sit directly in the Image sidebar.

Start values now live only in Calibrate, following Qt's grouping. Applying the
complete, validated fit-parameter set confirms those values; partial parameter
updates do not confirm an otherwise unconfirmed session. The Image step only
applies detector pixels. A divider separates Reset transformations from the
detector-file tools. Fit/geometry tabs use flat labels with a thin underline.
Geometry calculations, units and the processing runtime are unchanged. This is
layout reconciliation rather than exact widget-for-widget parity.

Browser layout checks cover 1000 × 668 CSS pixels with both text sizes,
including clean and edited geometry, image controls and every fit/geometry tab, and access
to all picked groups through pagination. They assert that controls fit within
the sidebar and table bounds, rather than merely hiding scrollbar tracks.
The real-image workflow also covers geometry application and restoration.
The embedded WKWebView smoke passes calibration, validation and return from
Mask/Integration, and confirms that its processing child exits. Its test build
uses temporary window-title read/set capabilities because the normal capability
file lacks those permissions; this change does not alter that file.

## Remaining scope

Map-branch recheck (2026-11-01): Python/browser calibration regressions pass, but
this branch's bundled native calibration smoke timed out. The timeout was also
reproduced with baseline UI components and the Python session restored. Native
Map workflow and chooser checks pass; see [Map parity](MAP_PARITY.md). The native
calibration timeout remains a qualification gap alongside the earlier evidence
below.


Tauri host verification (2026-11-01): embedded-asset and live native windows both
complete measured-image peak picking, fitting and detector/cake validation.
The live window applies a disposable CSS edit without a document reload.
The Rust/stdio transport has real-session tests for concurrent responses and
child failure/cleanup; Python checks that cancel/progress bypass occupied
command workers. Native open-file/cancel dialogs were checked in the macOS app.
The existing browser interaction checks still pass. Scientific Python and
optional-engine boundaries are unchanged; a portable Python bundle is pending.

Mask, Integration and Map have scoped implementations; see
[MASK_PARITY.md](MASK_PARITY.md), [INTEGRATION_PARITY.md](INTEGRATION_PARITY.md)
and [MAP_PARITY.md](MAP_PARITY.md) for their coverage and limitations.
Configuration switching, live acquisition and explicit HDF5 dataset-selection
interfaces remain outside the preview. Project configurations are preserved,
but only the selected one is
displayed. There is no new uncertainty estimator or geometry-identifiability
diagnostic. The native host now supports Tauri/WKWebView, with a local stdio
process using the existing Python scientific runtime. The earlier pywebview host
remains for comparison. There is no WASM implementation or portable bundled
Python runtime/installer yet.

Control text defaults to 14–15 px, with a Settings option for 16–17 px; secondary
metadata is 13/14 px and plot annotations are 13 px. Original Dioptas orange (`#ff9500`) is the fixed interface accent; buttons use soft tonal fills and compact tool groups.
The green crystal symbol has a six-sided prism, an inclined termination and
long reflective faces along c, independent of the control accent.
Scientific color maps are independent of the accent. Accessibility is improved,
but this is not a formal accessibility conformance audit.

## Verification

- `desktop/tests/test_calibration_workflow.py` exercises fixed distance/rotation,
  free wavelength, group reassignment/multiple deletion/undo/redo, orientation,
  manual geometry, PONI output, independent Q conversion, detector/spline files,
  invalid-mask rejection, real-ring automatic refinement, failed/cancelled
  command restoration, custom references, file stepping and validation references.
- `desktop/tests/test_session.py` covers engine independence, no-Qt imports,
  real-image calibration/residuals, full-resolution masking, exports and project
  round trips.
- `desktop/tests/test_bridge.py` checks that native processing objects are
  constructed, used and released on one thread, even when callers use different
  threads; cancellation bypasses an occupied processing worker. The native host
  and browser harness both use this dispatcher.
- Desktop tests without Dioptrin installed: **32 passed, 4 skipped**. With
  Dioptrin installed, the scientific session/workflow checks: **26 passed**;
  the dispatcher lifetime check passed separately. Dioptrin was subsequently
  removed from the preview environment.
- `desktop/scripts/smoke.mjs` exercises those central operations through the
  built React UI against real Python models, including gestures in every plot,
  peak edits, constraint controls, reference changes, orange accents and both text sizes,
  independent detector/cake controls with linear defaults and a settings dialog
  for compact/large and horizontal/vertical layouts, full-resolution auto levels
  checked against Qt, visual standard colour choices (no CET/PAL) and full-resolution image/mask transfer, histogram dragging/keyboard
  control, continuous-moving readouts,
  wheel capture without transient parent scrolling, refinement drafts, and
  1000 × 760 layout. Generated screenshots/reports are in ignored artifacts.
- Existing Pipeline, MainController and CalibrationController regression checks:
  **90 passed, 1 skipped**. No original Qt workflow changes were required.
- Native smoke: WKWebView; measured image and calibration workspace visible;
  bridge connected; image histogram visible; synthetic wheel event prevented;
  full-resolution detector data confirmed; no Qt application; zero TCP listeners in the Python process. Live-mode native
  smoke additionally changes a disposable CSS module and verifies that WKWebView
  applies the update in place, without reloading the document.

The CeO2 fixture and these checks establish scoped regression evidence. They do
not establish calibration accuracy across all detectors or experimental setups,
nor Windows/Linux packaging or full application parity.
