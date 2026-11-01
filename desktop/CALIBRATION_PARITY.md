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
| Load image; previous/next image | Source card and previous/next buttons, using the existing file iterator |
| ±90° rotation; horizontal/vertical flip; reset | Image & detector section; detector and image transformations stay aligned; stale peaks are cleared |
| Custom/predefined detector; detector file/reset | Experiment setup and Image & detector; loaded detector pixel pitches cannot be edited as custom pixels |
| Distortion spline load/reset | Image & detector |
| Calibrant selection | Bundled references plus custom `.D` import; custom content is owned by the session and embedded in project metadata |
| Wavelength / energy; distance; pixel sizes | Unit-labelled fields with linked wavelength/energy conversion and explicit Apply setup |
| Confirmation of experiment defaults | Required before fitting; the example explicitly supplies its known fixture inputs |
| Individual distance/wavelength/PONI/rotation fit checkboxes | Fit parameters; all six geometry parameters free and wavelength fixed by default, matching Qt |
| Polarization factor | Fit parameters and both manual geometry conventions |
| Seeded automatic peak search / single local maximum | Qt-style automatic/single search radio buttons and search-size field, default 10 source pixels |
| Ring number and automatic increment | Qt-style current-ring spinbox, automatic-increase checkbox, image-side picking badge and highlighted fitted ring |
| Group positions and ring reassignment | Peak table with mean source pixel coordinates and editable ring assignment |
| Multiple selection, delete, clear | Group checkboxes, select all, delete selected, individual removal, clear all; selected groups highlighted on the image |
| Peak edit history | Undo / redo buttons; Cmd/Ctrl+Z and Shift+Cmd/Ctrl+Z in calibration |
| Initial fit / subsequent refinement | Same pyFAI model entry points; optional separately installed Dioptrin adapter |
| Automatic refinement | Staged ring search/refit; enabled by default; Massif/Blob, Δ2θ, mean factor, intensity ceiling, ring count; Qt default values retained |
| Refinement progress / abort | Progress and cancel command remain responsive while the scientific session is busy; failure/cancel restores the pre-command geometry and picks |
| Mask use and transparency | Load/save mask, use-mask switch, transparent display; brush/erase and stroke undo in Integration |
| Calibrant lines and numbers | Independent display switches; reference lines also appear in the integrated pattern in its actual radial unit |
| Validation reference selection without changing geometry | Dedicated Validation calibrant selector uses the loaded/fitted geometry wavelength; changing reference clears the old RMS diagnostic |
| Linked detector/cake/pattern validation | Stationary validation click propagates the matching 2θ contour, cake line and pattern position; Q/d conversion uses the actual wavelength |
| pyFAI and Fit2D geometry inspection/input | Collapsible manual editor with complete unit-labelled fields; can create a geometry without peaks |
| Load/save calibration | Existing PONI reader/writer, plus standard `.dio` project save/reopen |
| Image intensity/log/colormap | Each image has its own histogram, Auto and colour picker; small settings dialog for limits, auto modes, linear/log, size and horizontal/vertical layout; counts use every finite source pixel |
| Moving mouse readout | Coordinates and original-pixel intensity sampled during continuous movement at about 10 Hz |
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
  actions. Fitting is disabled while their drafts differ from the applied state.
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

Control text defaults to 14–15 px, with an Aa option for 16–17 px; secondary
metadata is 13/14 px and plot annotations are 13 px. Warm orange is the default accent; optional dioptase green remains selectable.
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
  peak edits, constraint controls, reference changes, both accents and text sizes,
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
