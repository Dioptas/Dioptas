# Dioptas React / Tauri desktop preview

An experimental React/Tauri desktop interface for Dioptas with Calibration,
Mask, Integration and Map modes. It lives beside the existing Qt application
and uses its scientific models and file formats. It is not a complete
replacement yet.

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

Native image transfer uses binary buffers through both the Python pipe and
Tauri IPC. Commands and metadata remain JSON. Detector, mask, cake and map
pixels never become base64 strings on this path. A response contains a
little-endian uint32 header length, the UTF-8 JSON header, then the raw buffers
listed in that header. Buffer IDs identify immutable content; the window
advertises the IDs it still retains so unchanged pixels need not be resent.

The Python display cache retains up to 128 MiB of pixel buffers and associated
statistics, keyed by the complete source content, shape, dtype and display
options. This detects in-place image/mask changes while retaining statistics
from the original scientific precision. The window retains up to 128 MiB of
binary buffers and 96 MiB of colour-mapped canvases. Both caches evict older
entries. Render keys include mask content, palette, linear/log scaling and
intensity limits. Pending requests keep their advertised buffers alive even if
another response evicts them. Ring contours are reused only while the angular
array and calibrant angles agree; integrations continue to use the current
scientific models. The legacy pywebview host and browser-test bridge keep their
compatible JSON/base64 path.

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
2. In **Image & setup**, check image orientation, detector and pixel sizes.
   Press **Next: Pick rings** to apply the detector settings and continue.
   Previous/next arrows sit beside **Open image**. Detector definitions and
   distortion files follow the transformation buttons, separated by a divider.
   **Load .poni** and **Enter manually** stay available below the step actions;
   mask use, transparency and mask loading are directly below the detector
   tools. The processing engine lives in **Settings → General**.
3. Continue to **Pick rings**. The task panel follows Qt: **Current ring number**,
   **Automatic increase**, automatic/single peak search and search size. The
   step automatically enables picking; the right task panel identifies the
   current ring. Pick bright
   positions around the ring; use the group table to inspect or reassign picks.
4. Open Calibrate → **Parameters**: distance, wavelength, PONI 1/2 and rotations 1/2/3
   each have a value and an independent fit checkbox. The defaults match Qt:
   geometry parameters free, wavelength fixed. The folder button beside the
   calibrant selector loads custom `.D` spacings. Wavelength/energy, starting
   distance, polarization and fit constraints live here, not on the Image step.
   Apply complete fit parameters to confirm start values before a first fit;
   the example explicitly supplies its own known fixture values. Select enough
   peaks for the free parameters and spread them across several rings.
5. Continue to **Calibrate** and press the fixed **Calibrate detector** action at
   the bottom of the task panel. The **Refinement** tab configures automatic
   ring searches using the selected Massif/Blob settings; its progress is shown and it can
   be cancelled. Disable it to fit only the manually selected points.
6. Validate the ring overlays, cake, integrated pattern, and RMS residual.
   Click a plot to link its radial position across the other views. Change
   **Validation calibrant** to inspect a different reference without changing
   the geometry. Use the peak table to reassign groups, select/delete several
   groups, or undo/redo edits; refine again after editing selections.
7. Inspect or edit complete geometry through the visible **pyFAI / Fit2D** tabs,
   then save a `.poni` calibration with the fixed bottom action. Geometry drafts
   persist while switching tabs; apply changes before refining or saving.
   Alternatively, use **Load .poni** or **Enter manually** from any step, without
   picking peaks.
8. Switch to **Mask** for drawing, geometric selections, thresholds, automatic
   masks and mask files; see [Mask parity](MASK_PARITY.md). Switch to
   **Integration** for image/cake/pattern display, integration options, shared
   masks, backgrounds, corrections, overlays/phases and Qt-style pattern saving;
   see [Integration parity](INTEGRATION_PARITY.md). Calibration also offers mask load/use,
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

The app has no top header or in-app logo. Mode navigation stays on the left,
with Undo/Redo side by side above Open/Save project and Settings at the bottom.
Mode selection uses a neutral charcoal fill, light text and an orange icon.
Open project, Save project and Settings use compact icon-only buttons with
tooltips; Settings retains the same size when selected. The current project
name appears above its actions, with the full name available on hover. Text size
and keyboard shortcuts are in Settings at the bottom of the sidebar.
Plots occupy the main workspace, and
one changing task panel stays on the right, following the existing Dioptas
arrangement. The working calibration steps show the image alone; cake and
pattern appear on Validate. The calibration sidebar fits without scrolling:
The Image step contains image/detector controls only. Parameters / Refinement
split the Calibrate step, while the peak table pages its groups according to
available height. Tab labels are flat, with a thin active underline.
Positions remain visible at both text sizes. Back/Next, fit/apply, save and
load/manual actions stay fixed at the bottom. Mask controls are directly visible
in the Image sidebar. Validation keeps complete geometry visible in pyFAI / Fit2D tabs.

Each image (detector and cake) has an adjacent histogram, with independent
limits, colour map, linear/log mode and auto settings. Both start in linear
mode. Auto and a settings button stay visible; the adjacent colour bar opens
the colour-map picker. Auto is
highlighted after automatic levels are applied; manual range or linear/log scale
changes clear its selection. Click the
settings button or double-click the histogram to open its small settings
dialog: numeric limits, auto mode, clipping, gap filtering, linear/log, compact
or large size, and vertical (right of image) or horizontal (above image) layout. Single-image
calibration defaults to a right-hand bar; multi-image validation/integration
defaults to top bars for both detector and cake. Selection
shading and boundary handles stay inside the histogram graph, clear of the
colour bar. Drag either handle or the whole selected region beyond the data
range to extend its intensity limits; the histogram axis fits the extended
range when released. Arrow keys and numeric limits can also extend the range.
Auto modes match Qt: Percentile (configurable tail clipping),
Min/max and Mean ± 3 Std, with optional detector-gap filtering. The picker shows actual ramp images in one flat list of standard Dioptas/
pyqtgraph scales, with Grey as the default. Left or right click the colour bar to
open the colour-map picker. CET/PAL and custom preview palettes
are excluded.
Percentile clipping defaults to 2.5% per tail. Each image view saves its auto
mode, clipping percentage and gap-filter setting across app restarts, and applies
them when an image loads. Numeric clipping and intensity-limit edits apply on
Enter or when leaving the field, allowing complete numbers to be typed first.
Lookup tables are generated at build time; see `scripts/export_colormaps.py`
and `licenses/colormaps/` for source attribution.
Histogram counts include every finite source pixel, including zero and negative
values; its intensity axis is logarithmic away from zero. Display adjustments do
not modify source arrays. Calibrant rings use thin, translucent solid lines
without a halo and quiet, borderless numbered labels; the current picking ring
has a slightly stronger stroke and a yellow label.
Picked calibration peaks follow Qt: solid red dots, orange for the current
ring, with larger dots and an opaque white outline for selected groups. Marker
diameters stay at 7/9 screen pixels while zooming; table swatches match the image.
Mouse coordinates and source intensity update together during movement at roughly
10 Hz, with one pixel read in flight at most. The last completed reading remains
visible while a new source-pixel lookup is pending; the final cursor position is
sampled even when movement stops during a lookup.

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

Image plots use Rectangle zoom and detector views preserve square pixels.
The integrated pattern defaults to Horizontal, retaining automatic intensity
scaling. Settings offers Rectangle mode to select both radial and intensity
ranges, independently for the main pattern and Map pattern.

In the Pick rings step, a stationary left click picks peaks. A left drag zooms
without adding peaks. In a mask/eraser tool, left drag paints; right-button
navigation remains available. `F` or right double-click restores the image.
Detector and cake images have no extra title/dimension header, Fit button or
Display mask toggle or tool-selection strip. Picking follows the calibration
step automatically. Drawing and erasing belong to the dedicated Mask workspace;
masks remain visible, with use and transparency controlled in task options.

Settings is anchored at the bottom of the left mode sidebar. It opens a full,
fixed-size workspace inside the main window, with a category column for General,
Integration and Keyboard shortcuts. General contains interface text size, the processing-engine selector and
pattern drag-zoom mode. Categories scroll independently of the header and the
Integration Apply bar. Back, Escape or a mode button returns to the plots;
opening Settings retains the mounted plots and their zoom, layout and drafts.
Settings → Integration contains radial coordinates and binning, supersampling,
1D/cake azimuth ranges, cake resolution, solid angle, Poisson errors,
polarization and zero trimming. These use the existing session/project settings
and explicit Apply action. A shared
app footer starts beside the full-height left sidebar and shows the active plot's
coordinates/intensity on the left, with workflow, processing, selection, save
and error messages on the right. Detector,
cake, pattern and map readings identify their source and update at about
10 Hz; leaving a plot clears its reading. Plot-local status rows and floating
pattern readouts are removed. Calibrant display switches sit at the right end
of the calibration step toolbar above the image.

The interface uses the original Dioptas orange (`#ff9500`) for accents and primary actions,
with soft tonal buttons, compact groups for related tools, and a green hexagonal-prism
symbol elongated along its c direction. Its six-sided prism has an inclined
termination, dark glassy faces and narrow reflections inspired by the supplied
crystal photographs. The native app icon uses a rounded orange glass tile with soft
reflections; its artwork is exported from the React crystal component. Workspace, panels
and input backgrounds retain their neutral dark colours. The crystal symbol
keeps its own green identity. The normal interface uses
14–15 px control text; Settings → Interface text → Larger switches to
16–17 px text and wider options.
Secondary metadata remains smaller. Plot annotations are 13 px. Text-size
preferences are retained when local storage is available. The large calibration
title/header is removed; compact step buttons take its place. Advanced groups
fold away, while the existing left navigation / right controls arrangement stays.

## Integration workflow

Integration follows Qt's pane arrangement: a full-height image/cake on the left,
with tabbed controls above the integrated pattern on the right. Drag either
divider to resize the panes; Image/Cake switches the left display and preserves
its independent intensity controls. The Image, Pattern, Background, Corrections, Overlay and Phase groups connect to the existing local models. Native file
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

Then select **Dioptrin (optional)** under **Settings → General → Processing engine**. Selection
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
- Full uncertainty diagnostics, live acquisition watching, explicit HDF5 dataset
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

Combined-view verification: the main checkout includes the finished Mask,
Integration and Map branches. The combined desktop suite passed 90 tests with
four optional-engine skips. An additional cross-view test passes: masked
Integration results agree with stored Map patterns, and a project round trip
retains mask, map and integration settings. The three Rust tests pass.
Calibration/Integration, Mask and Map browser workflows pass. Both bundled
Tauri smoke checks pass, covering calibration, Mask/Integration controls and
Map loading/linked inspection/project persistence; both processing children
are reaped. The earlier Map-branch calibration-smoke timeout remains a
historical result in [Map parity](MAP_PARITY.md); it did not reproduce in
the combined native check.


On macOS with CPython 3.13.5, checks cover the real CeO2 image workflow,
individual fixed/free constraints, wavelength refinement, peak editing/history,
orientation, manual geometry and PONI output, custom calibrant ownership/project
reopening, detector/distortion files, linked coordinate conversions, automatic
ring searches and transactional cancellation. Earlier optional-engine checks
also covered fixed distance/rotation and free wavelength. Exact results are recorded in
[the calibration comparison](CALIBRATION_PARITY.md).

The browser checks use the real Python models and have exercised both engines,
peak clicks/edits, constraint controls, save/reopen/export, mask/undo, plot gestures,
linked validation, orange accents and both text sizes, and compact layout. Native startup
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

## Binary transfer verification (2026-11-01)

Started from UI checkpoint `3fda11a7`. Styles and layout components are unchanged;
the raw calibration browser screenshot is pixel-identical to that checkpoint.
Python coverage includes every full-resolution detector pixel, mask undo/redo,
in-place mutation, full-precision statistics, eviction and binary progress/cancel.
Frontend coverage includes malformed frames and concurrent eviction. Native
checks exercise calibration, masks, Integration, Map and project persistence.

In the local macOS debug build, calibrated switching between the 2048 × 2048
`image_001.tif` and `image_002.tif` fixtures took 140–160 ms after warming the
caches (click through two animation frames after display). Scientific-command
round trips were 92–97 ms. The first measured response was 21,604,769 bytes;
a warm response was 416,976 bytes of metadata with zero pixel bytes. Warm UI
switches performed no detector recolouring. These are local measurements,
not latency guarantees for other files, settings or machines.

Run `npm test` for frontend cache/framing tests and the normal Python/browser
suites above. The native smoke adds a `binaryTransfer` record with timings,
transferred pixel bytes and rendered-cache checks. Filename/title assertions
still require the existing window-title capability override when building the
native test window; the binary transport adds no permissions.

### Matched Qt/Python comparison

The native smoke now saves `artifacts/qt-comparison.dio` for the Qt timing
script. The measured comparison used the Qt checkout in
`/Users/clemens/Programming/Dioptas`, the same two source images, exact saved
geometry/mask/corrections, pyFAI, 600 radial bins and 90 cake azimuth bins.
Both clients were 1440 × 908 logical pixels at device pixel ratio 1. Eight
alternating switches were measured after warming each path. The final
image_001 integrated patterns agreed exactly.

| Complete switch, including repaint settling | Median |
| --- | ---: |
| Tauri, binary transfer and display caches | 160 ms |
| Qt/Python, normal asynchronous processing | 166 ms |
| Qt/Python, synchronous processing | 172 ms |

Qt's asynchronous detector plot finished painting at a median 73 ms, while
integration completed at 130 ms. The settled endpoint adds two 16-ms Qt waits;
Tauri uses two animation-frame callbacks after its state becomes ready.
These are approximate application comparisons with different event loops,
so the small differences above should not be read as a renderer ranking or
an isolated IPC measurement.

Run the Qt side from the repository root without reading or writing user
settings (only its own benchmark window is closed):

```sh
.venv/bin/python desktop/scripts/qt_image_benchmark.py \
  --project desktop/artifacts/qt-comparison.dio \
  --output desktop/artifacts/qt-image-benchmark-async.json
```

Add `--synchronous` for the synchronous Qt path, or `--qt-source PATH` to
measure another Qt checkout using the same Python environment. The script
uses the native report's client dimensions when
`artifacts/qt-comparison-native.json` is available (`--native-report` overrides
its path). Reports distinguish slot return, image-item paint, complete
viewport paint, integration completion and settling time.
