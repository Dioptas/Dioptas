# Dioptas React / Tauri desktop preview

An experimental React desktop interface for Dioptas, starting with detector
calibration. It lives beside the existing Qt application and uses its scientific
models and file formats. It is not a complete replacement yet.

## Run this checkout

Use standard CPython 3.13 (not a free-threaded interpreter):

```sh
uv sync --python 3.13
cd desktop
npm ci
npm run tauri:dev -- -- -- --example
```

The example opens the **raw** `CeO2_Pilatus1M.tif` fixture, without loading its
reference PONI. The explicit example setup is CeO2, wavelength 0.406626 Å,
172 × 172 µm pixels, and a starting distance of 200 mm. These are starting
inputs, not a previously fitted geometry.

For an empty workspace, use `npm run tauri:dev`. On macOS, after setup, double-click
`desktop/launch.command` to reopen the raw-image example in **Live preview**.
The launcher now opens **Tauri**, using WKWebView on macOS. Its first run compiles
the Rust host and requires the Rust toolchain and platform build prerequisites.
The Tauri CLI owns a loopback Vite frontend on port 1420; React/CSS edits appear
in the running native window. If that port is occupied, it fails rather than
opening a different project's server. Closing the window also stops Vite.
Rust changes rebuild/restart the host. Python processing changes require a restart.

`src-tauri/` contains the Rust host. React calls one Tauri command, which sends
requests over stdin/stdout to a local `dioptas.desktop.stdio` process. Native
file dialogs belong to Tauri. There is no scientific HTTP/API server or remote
service. The bundled frontend uses the Tauri asset protocol, without Vite.
Scientific objects are constructed, used and released on one processing thread,
including the optional native integrator. Progress and cancellation bypass that
worker without accessing native objects. Pipe responses carry request IDs so a
long fit does not block progress/cancel responses. Window closure drops the pipe,
cancels pending refinement and reaps the child, with a bounded kill fallback.

This is still a **source-checkout preview**, not a portable installer or a
Rust-only scientific implementation. The host finds this checkout's `.venv`;
`DIOPTAS_SOURCE_ROOT` and `DIOPTAS_PYTHON` can override those paths explicitly.
The Python runtime and dependencies have not yet been bundled for distribution.
Dioptrin remains optional. No Qt application is created by this host.

To build a local executable with embedded UI (no development server):

```sh
cd desktop
npm run tauri:build -- --debug
src-tauri/target/debug/dioptas-desktop --example
```

The earlier pywebview host remains available for comparison:
`uv sync --python 3.13 --extra desktop`, `cd desktop && npm run build`, then
`.venv/bin/python -m dioptas.desktop --example` from the checkout root.
Its `--dev` option still supports live frontend updates independently of Tauri.

## Calibrate first

1. Open a calibrant image, or explore the raw CeO2 example.
2. Choose the calibrant and detector. Check pixel sizes, wavelength or energy,
   and starting distance; press **Apply setup** after editing numbers.
3. Continue to **Pick rings**. The task panel follows Qt: **Current ring number**,
   **Automatic increase**, automatic/single peak search and search size. The
   image toolbar always shows which ring will be picked next. Pick bright
   positions around the ring; use the group table to inspect or reassign picks.
4. Check **Fit parameters**: distance, wavelength, PONI 1/2 and rotations 1/2/3
   each have a value and an independent fit checkbox. The defaults match Qt:
   geometry parameters free, wavelength fixed. Select enough peaks for the
   free parameters and spread them across several rings.
5. Continue to **Calibrate** and press the fixed **Calibrate detector** action at
   the bottom of the task panel. Automatic refinement searches further rings
   using the selected Massif/Blob settings; its progress is shown and it can
   be cancelled. Disable it to fit only the manually selected points.
6. Validate the ring overlays, cake, integrated pattern, and RMS residual.
   Click a plot to link its radial position across the other views. Change
   **Validation calibrant** to inspect a different reference without changing
   the geometry. Use the peak table to reassign groups, select/delete several
   groups, or undo/redo edits; refine again after editing selections.
7. Save a `.poni` calibration. Alternatively, load an existing PONI or enter
   complete geometry using the pyFAI or Fit2D editor, without picking peaks.
8. Switch to **Integration** for image/cake/pattern display, integration options,
   shared masks, backgrounds, corrections, overlays/phases and Qt-style pattern
   save/autocreate controls. See INTEGRATION_PARITY.md for coverage and limits.
   Calibration also offers mask load/save/use,
   image transformations, detector definitions, distortion splines, and custom
   calibrant `.D` files.

The image readout and peak-table positions count rows downward from the top.
The detector picture keeps its existing orientation. Scientific geometry and
stored control points retain the existing Dioptas bottom-left convention; the
UI converts row labels without flipping the data. See
[the calibration comparison](CALIBRATION_PARITY.md) for coverage and differences.

Display intensity limits, linear/logarithmic scaling, and color maps do not
change scientific arrays. Detector images, masks and cake arrays are transferred at their complete spatial
resolution (no display decimation). Zoom therefore resolves the original
detector pixels; calculations, brush edits and pixel readouts also use original
resolution. Display payloads use float32; scientific arrays retain their source
precision in Python.

## Layout and plot interaction

Mode navigation stays on the left, plots occupy the main workspace, and
one changing task panel stays on the right, following the existing Dioptas
arrangement. The working calibration steps show the image alone; cake and
pattern appear on Validate. Back/Next actions guide the sequence, and the fit
action stays visible at the bottom of the task panel.

Each image (detector and cake) has an adjacent histogram, with independent
limits, colour map, linear/log mode and auto settings. Both start in linear
mode. Only Auto and the colour-map selector stay visible. Click the colour
bar, double-click or right-click the histogram to open its small settings
dialog: numeric limits, auto mode, clipping, gap filtering, linear/log, compact
or large size, and vertical (right of image) or horizontal (above image) layout. Single-image
calibration defaults to a right-hand bar; multi-image validation/integration
defaults to top bars for both detector and cake. Selection
shading and boundary handles stay inside the histogram graph, clear of the
colour bar. Auto modes match Qt: Percentile (configurable tail clipping),
Min/max and Mean ± 3 Std, with optional detector-gap filtering. The picker shows actual ramp images in one flat list of standard Dioptas/
pyqtgraph scales, with Grey as the default. CET/PAL and custom preview palettes
are excluded.
Lookup tables are generated at build time; see `scripts/export_colormaps.py`
and `licenses/colormaps/` for source attribution.
Histogram counts include every finite source pixel, including zero and negative
values; its intensity axis is logarithmic away from zero. Display adjustments do
not modify source arrays. Ring overlays use a dark halo and numbered labels;
the current picking ring has a brighter stroke and label. Mouse coordinates and
source intensity update during movement at roughly 10 Hz, with one pixel read
in flight at most.

All current plots (detector, cake, integrated pattern) share these controls:

- **Wheel:** zoom the plot under the pointer; the event is captured so the
  surrounding workspace does not scroll or jump.
- **Left drag:** zoom in using the selected zoom mode.
- **Right drag:** pan both axes. Ctrl + left drag also pans.
- **Right click:** zoom out one step (2× range).
- **Right double-click:** completely restore the fitted view, including after
  deep zoom or resizing.

The detector image has no axes, ticks or surrounding card. Its pixels stay
square during zoom, pan, histogram resizing and window resizing. Cake and
pattern retain their scientific axes.

Each plot header offers **Horizontal** and **Rectangle** modes. The integrated
pattern defaults to Horizontal, retaining its automatic intensity scaling.
Rectangle mode selects both radial and intensity ranges. Detector and cake
plots default to Rectangle; detector views preserve square pixels.

In the Pick rings step, a stationary left click picks peaks. A left drag zooms
without adding peaks. In a mask/eraser tool, left drag paints; right-button
navigation remains available. `F` or the detector fit button restores the image.

The interface defaults to warm orange accents, with a green hexagonal-prism
symbol elongated along its c direction. Its six-sided prism has an inclined
termination, dark glassy faces and narrow reflections inspired by the supplied
crystal photographs. Workspace, panels
and input backgrounds retain their neutral dark colours. **Accent color** also
offers dioptase green; the crystal symbol keeps its own green identity. The normal interface uses
14–15 px control text; **Aa** switches to 16–17 px text and wider options.
Secondary metadata remains smaller. Plot annotations are 13 px. Color and text
preferences are retained when local storage is available. The large calibration
title/header is removed; compact step buttons take its place. Advanced groups
fold away, while the existing left navigation / right controls arrangement stays.

## Integration workflow

Integration now has Qt-style Image, Pattern, Options, Background, Corrections,
Overlay and Phase groups, connected to the existing local models. Native file
choosers cover pattern/background/phase files and output/input folders. See
[Integration parity and limitations](INTEGRATION_PARITY.md) for the implemented
controls, scientific qualifications, tests and shared contracts.

## Optional processing engine

**pyFAI is the default and provides the complete implemented workflow without
Dioptrin installed.** Tauri uses the normal Dioptas scientific dependencies.
The `desktop` extra adds pywebview only for the earlier comparison host.

To install the optional Dioptrin engine:

```sh
uv sync --python 3.13 --extra dioptrin
```

Then select **Dioptrin (optional)** in the Processing engine selector. Selection
checks its calibration API and normal license validation before changing the
session. Installing the package does not select it automatically. The engine
choice is local to the session, not restored from another computer's project.
The new interface does not change either project's licensing.

`dioptas/desktop/engines.py` defines the narrow calibration adapter: seeded peak
finding and geometry fitting. The Dioptrin adapter calls its existing Python
bindings; pyFAI uses the same calibration entry points as Qt Dioptas. Session
storage, detector definitions, PONI conventions, and integration remain in the
existing Dioptas models. Their existing pyFAI fallback rules still apply for
native integration options that are unsupported. The native calibration adapter
currently accepts only flat detectors with uniform pixels and no distortion
spline; use pyFAI otherwise.

## Development and verification

```sh
uv sync --python 3.13 --extra desktop --extra test
.venv/bin/python -m pytest -n 0 desktop/tests \
  dioptas/tests/unit_tests/test_pipeline.py \
  dioptas/tests/controller_tests/test_MainController.py \
  dioptas/tests/controller_tests/test_CalibrationController.py
cd desktop
npm run build
npx playwright install chromium
npm run smoke
npm run tauri:smoke
npm run tauri:smoke -- --live
cargo test --manifest-path src-tauri/Cargo.toml
cd ..
.venv/bin/python -m dioptas.desktop --example --smoke
```

Native-engine tests run when Dioptrin is separately installed, otherwise they
skip. With that extra installed, `npm run smoke -- --dioptrin` also exercises
engine selection and the native calibration workflow through the interface.
The browser smoke test uses a test-only JSON-lines process to connect
Playwright to real Dioptas models. It exercises measured-image clicks, fitting,
PONI save, integration units/bins, mask painting and undo, export, and project
save/reopen. This browser-test process is distinct from Tauri's production stdio
transport. Screenshots
and reports are written to ignored `desktop/artifacts/`.

`npm run tauri:dev` provides frontend hot reload in the Tauri window. A plain browser
has no native bridge: it displays an explanatory error rather than
inventing a dataset or simulated processing. `npm run format` formats the
frontend source. The Live preview launcher updates without rebuilding;
rebuild only when using the bundled mode. In the legacy Python host, `--debug`
enables webview developer tools.

`npm run tauri:smoke` builds a debug executable with embedded assets, opens its
own native test window, picks measured CeO2 peaks, calibrates, verifies both
validation images and wheel capture, then closes only that window. The `--live`
variant runs through the Tauri/Vite development launcher and changes a disposable
CSS module to check hot reload without a document reload. Both verify that the
processing child has exited. Reports go to `artifacts/tauri-*-smoke.json`.
Rust tests also exercise the real Python pipe, full-resolution payloads,
concurrent progress, unexpected child termination, and cleanup. The Python
transport tests verify cancellation bypass even when every request worker is busy.

## Boundaries of this milestone

- Native Tauri macOS startup and the real-data calibration workflow are
  exercised; Windows/Linux packaging and behavior are not qualified yet.
  Linux requires Tauri's system WebKit/build dependencies. The legacy
  pywebview host also needs a supported renderer if used there.
- The frontend offers seeded calibration plus staged automatic ring refinement,
  not Dioptrin's full automatic calibration/ring-identification workflow.
- Full uncertainty diagnostics, Map/acquisition workflows, explicit HDF5 dataset
  selection, and configuration switching do not yet have frontend controls.
  Integration now exposes backgrounds, selected corrections, phases/overlays,
  pattern saving/autocreate and folder integration; its remaining Qt scope is
  listed in [INTEGRATION_PARITY.md](INTEGRATION_PARITY.md).
  Existing `.dio` configurations are retained;
  only the selected configuration is displayed.
- Project saves use standard `.dio` data and an optional `react_desktop` HDF5
  attribute for workflow options, selected calibrant (including custom d-spacing
  text), setup confirmation and fit diagnostics. Qt Dioptas can
  read the normal state; a subsequent Qt save does not retain this UI attribute.
- The cake retains its actual 2θ coordinate even when the 1D pattern uses Q or d,
  matching the existing synchronous Dioptas configuration API.
- The source example is a regression/interaction fixture. Agreement on it does
  not establish calibration quality for other detectors or experimental data.
- This keeps the existing Python scientific runtime. Qt remains a dependency
  of the original application; the React host does not instantiate a Qt app.
  pyFAI may probe optional Qt modules when they are installed. A subprocess test
  verifies that the new session also runs when Qt imports are unavailable.

The interface/engine boundary permits native Rust bindings later. The new host
is Tauri; the scientific implementation still uses Python. WASM/browser-only
execution is not implemented.

## Verification on 2026-11-01

On macOS with CPython 3.13.5, checks cover the real CeO2 image workflow,
individual fixed/free constraints, wavelength refinement, peak editing/history,
orientation, manual geometry and PONI output, custom calibrant ownership/project
reopening, detector/distortion files, linked coordinate conversions, automatic
ring searches and transactional cancellation. Earlier optional-engine checks
also covered fixed distance/rotation and free wavelength. Exact results are recorded in
[the calibration comparison](CALIBRATION_PARITY.md).

The browser checks use the real Python models and have exercised both engines,
peak clicks/edits, constraint controls, save/reopen/export, mask/undo, plot gestures,
linked validation, both accents and text sizes, and compact layout. Native startup
reports WKWebView, a working bridge, no Qt application and zero TCP listeners.

These are scoped regression and interaction checks, not full application or
cross-platform qualification. Generated evidence is in `desktop/artifacts/`.

The Tauri migration adds three Rust tests and two Python transport tests.
The Python desktop suite reports 34 passed / 4 skipped (optional Dioptrin absent).
The current real-model browser and Tauri checks use pyFAI. Tauri's embedded-asset and live native
smoke checks both pick five measured groups, fit geometry and display detector
and cake at full resolution. The live check confirms CSS HMR without losing the
document. Closing either test window reaps its processing child. Native open
dialog cancellation and opening the CeO2 TIFF were also checked interactively
in the locally built `.app`. The processing runtime is still checkout-local.
