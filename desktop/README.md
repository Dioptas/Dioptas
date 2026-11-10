# Dioptas Rust desktop development

An experimental React/Tauri desktop interface for Dioptas with Calibration,
Mask, Integration and Map modes, plus a linked Batch window. It lives beside the existing Qt application
and uses its scientific models and file formats. It is not a complete
replacement yet.

The consolidated development branch is `codex/rust-desktop`. New desktop work
uses this checkout; the single-crystal experiment stays separate. See the
[consolidation record](RUST_DESKTOP_CONSOLIDATION.md) for included branches and
verification.

The desktop uses Dioptrin **0.12.0** plus the Massif, cached compatibility
and resident-layout/dynamic-worker optimizations at revision `41174d8`, locked in `backend/Cargo.lock`. It includes native
pyFAI-compatible full pixel splitting for both 1D patterns and cakes. Massif
picking retains full-resolution samples and reuses preprocessing across clicks;
see [Massif performance and numerical checks](MASSIF_PERFORMANCE.md) and
[cached integration measurements](PYFAI_CACHED_PERFORMANCE.md).
Settings → Integration also exposes bin-oriented CSR (the default),
pixel-oriented CSC and optional automatic size-based selection for resident 1D patterns.
See the [detector/bin crossover study and predictor](INTEGRATION_LAYOUT_CROSSOVER.md).

The default [Rust backend](backend/README.md) runs the
image → peak picking/fitting or loaded/manual geometry → integration workflow without Python, using
`dioptrin-io` and Dioptrin. `npm run tauri:dev`, `desktop/launch.command` and
embedded Tauri builds select Rust without a Python environment. Build hooks
compile and stage the matching native processor automatically.
See the [Python-removal audit](PYTHON_REMOVAL_AUDIT.md) for remaining compatibility
and distribution work. `npm run tauri:native-dev` retains its isolated port 1428.
The native calibration stage retains the existing controls, automatic ring
refinement, live progress/cancellation and grouped edit/fit Undo/Redo for the
[qualified detector geometry](NATIVE_DETECTOR_PARITY.md).
All three bundled masking plugins also run natively, including their settings,
dynamic recomputation, imprint and Undo/Redo. The native integration stage adds
warm-plan reuse and combined HDF5 loading, corrections/backgrounds, pattern and
overlay I/O, phase/material editing, Batch and Map with the existing controls.
Admitted fixed-mask HDF5 Batch/Map series use concurrent frames with one shared
CSC plan and persistent worker scratch. Development builds also optimize the
separate Bitshuffle/LZ4 C dependency. See [series pipeline measurements](NATIVE_SERIES_PIPELINE.md).
Corrected images and dynamic masks use shared native `Dynamic1dPlan` snapshots
and private reusable frame workers, including propagated pixel variances; see
[processed-series qualification](NATIVE_PROCESSED_SERIES_PIPELINE.md).
Spot and Cosmic masks use compact row workspaces and shared Spot bin membership;
see the [full-series spatial-mask profile and benchmark](NATIVE_SPATIAL_MASK_PERFORMANCE.md).
The integration status line reports measured images/s during Batch/Map loading.
See [native GUI Eiger timings](NATIVE_GUI_SERIES_PERFORMANCE.md) for first/repeated
loads, bin counts and Poisson errors. pyFAI-compatible Batch/Map now also use
[shared plans and persistent frame workers](NATIVE_PYFAI_SERIES_PIPELINE.md).
See the [qualification ledger](NATIVE_INTEGRATION_PARITY.md) for measured parity,
benchmark scope and remaining detector work. Native format-2 `.dio` persistence
and configuration select/add/duplicate/rename/remove controls are now available;
see [project compatibility and verification](NATIVE_PROJECT_PARITY.md).
The configuration bar is hidden by default. Enable **Settings → Configurations → Enable configurations** to use it, or press **Shift+C** in the workspace to toggle configurations. The shortcut pauses in text fields, menus, dialogs and Settings. This preference is remembered across restarts. Switching it off hides the toolbar
and disables combined patterns/cakes while retaining all configurations and the
active selection. Opening a project with active combination enables the toolbar.
The next stage adds [native rotations/flips and geometric masks](NATIVE_GEOMETRY_MASK_PARITY.md)
through the existing controls, including per-configuration persistence and history.
The separate [LA Cosmic action](NATIVE_LACOSMIC_PARITY.md) is now native as well,
with Cosmic Removal in the Mask panel, two passes, Undo/Redo and cancellation.

HDF5 files expose an **Image source** selector in Calibration → Image and
Integration → Image. It lists supported scalar planes/stacks with frame counts
and dimensions. Switching retains the current frame, clamped to a shorter source,
and updates the image and integrated results together. Recognized Eiger/LImA/Lambda
formats retain their automatic series option. Selected sources belong to each
configuration and survive native project save/reopen. See [HDF5 source selection](HDF5_SOURCE_PARITY.md).

For multi-frame images, **Integration → Image** also offers previous/next frame
arrows, a separate **Frame step**, and direct one-based frame entry. Frame steps
stop at the first/last frame of the current file or selected HDF5 source;
rapid clicks are processed in order. The frame step is independent of File step.
File arrows beside Load image move directly between files using File step and Name/Time,
opening frame 1 of each destination even when the current file has more frames.
Page Up / Page Down (Fn+↑ / Fn+↓ on a Mac) perform the same file navigation
in Calibration and Integration, using File step in Integration. Shortcuts pause
in fields, menus, dialogs and Settings. Unmodified arrows retain plot navigation.
The Image tab uses aligned File, Source and Frame rows. **Folder…** beside the
filename selects the input folder without a permanent directory field.
Autoprocess shows **Watching:** with the processor's confirmed folder; opening a
reference image elsewhere keeps that watcher fixed until Folder… changes it.
Source selection uses short, distinct dataset labels; the full selected path is
available on hover and in **File Info**. A sole source is shown as passive text,
and the Frame row is hidden for single images. Folder status and dimensions share
one compact line. The splitter stays fixed across Integration tabs. File order
and Batch mode use compact dropdowns. File and frame arrows use 32 × 30 px targets
at both text sizes, with each step field directly beside its browsing controls.

Changing source image dimensions asks for **Cancel** or **Open and reset
calibration** before changing the session, including variable-size frames within
one file. Accepting clears detector geometry, orientation, masks, corrections,
picks and stale integration results while keeping the current workspace and tab. It retains
phase and overlay references. **Reset calibration** beside Load .poni performs
the same detector reset while keeping the current image. Same-size images retain
calibration; a physical detector change with identical dimensions still requires
an explicit reset. Manufacturer-supported binning can resolve the first image
against a named detector; later size changes always prompt. Autoprocess stops
on a mismatch so it cannot integrate using the wrong detector geometry.

With configuration controls enabled, the top bar provides detector factors,
**Combine patterns**, **Combined cake** (calibrated 2D cakes), and combined-pattern
export across modes. Configuration file/folder arrows always browse all
configurations; the Image panel's arrows browse the active detector. Configure
filename/folder number positions, step sizes and linked filename changes in **Settings → Configurations → Configuration browsing**. The MEC preset supplies the Qt convention;
all rules remain customizable and persist across restarts. See
[detector combination and browsing](DETECTOR_COMBINATION_PARITY.md).
Combined patterns and cakes run through
Dioptrin's native shared-grid integration, with independent images, masks and
display preferences for each configuration. Combination needs calibrated images
and solid-angle correction. Combined counting errors use independent pixel variances propagated through
backgrounds, detector factors and image corrections. See the
[correction and uncertainty ledger](NATIVE_CORRECTION_UNCERTAINTY_PARITY.md)
for transfer/plate/slab controls, project ownership, full data-flow tests and
statistical assumptions. Cylinder, sphere and optional capillary-wall absorption are
also native; see the [round-sample qualification](NATIVE_ROUND_SAMPLE_CORRECTION_PARITY.md)
for their footprint models and legacy-project recalculation notice.

Integration and Map use the same `RasterView` and `PatternView` renderers.
`diffractionPlotSetup.ts` prepares their common detector mask/click properties
and pattern colors, visibility, phase references, overlay legends, linked radial
position and click sampling. Each mode supplies its own display data and tools;
Map ROI editing, Integration background inspection, independent image levels
and per-mode plot preferences remain with their existing owners. Detector zoom
and pan are shared across Calibration, Mask, Integration and Map during the
session. Pattern ranges are shared across Calibration, Integration and Map,
converting radial units and intensity scales as needed. Resizing keeps detector
pixels square; F/right double-click still restore the fitted image view.

## Native regression tests and CI

The Rust desktop gate and the case-by-case inventory of all 82 legacy functional
definitions are documented in [Native functional coverage](NATIVE_FUNCTIONAL_COVERAGE.md).
Run `npm run test:ci-native` for processor and headless UI checks; independent
Python reference calculations are an explicitly separate gate.

## Shared UI controls

All views use the controls and surfaces in `src/ui`, including table fields,
popup menus and detached windows. The shared stylesheet owns their neutral
palette and interaction states. See [UI_COMPONENTS.md](UI_COMPONENTS.md) for
component usage and the checks that prevent new per-view control themes.

## Run this checkout

Install Node/npm, Rust, a C/C++ compiler, CMake and Git, then:

```sh
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
Development also tracks React hook signatures in `.ts` modules: changing their
hook layout safely remounts the affected interface, while ordinary edits retain
interface state. Run `npm run test:hook-refresh` for the headless Chromium/WebKit
regression check against a real native session.

Rust processor source/Cargo/data changes rebuild the worker in the background.
After a successful build, the host waits for the current operation, checkpoints
all configurations into a private owned-data project, restores the new worker,
and swaps the stdio connection. The window stays open: images, masks, corrections,
geometry, calibration drafts/picks, file settings, combined results, configuration
identities/selection, linked inspection and the current project save path survive.
The frontend refreshes results without resetting plot views or its unapplied drafts.
Build/start/restore failures keep the old worker and its session active. Progress
and cancellation remain available while a reload waits for an operation.
Mask, calibration and integration Undo/Redo stacks survive worker replacement,
including their chronological order and each configuration’s redo branches.
History data is held in a private binary sidecar with shared arrays stored once;
it is not added to ordinary saved projects. The first update from an older
worker that cannot export history initializes empty stacks once. Reload status and
build errors appear in the footer and launcher log. Set `DIOPTAS_DEV_RELOAD=0` to
disable the watcher. Generated build/staging files are excluded from UI and host
watchers, so a scientific rebuild does not reload the window.

This applies to the native **live development preview**. Host Rust changes still
restart the host/window; bundled snapshot apps do not watch source files. Python
is only needed for the explicit compatibility backend and independent references.

For phase-editor work in its assigned checkout, use `npm run tauri:phase-dev`.
This opens the raw-image example with live React/CSS updates on its dedicated
port 1426, including the detached phase-editor window. It leaves the primary
preview's port 1420 and existing bundled windows alone. Bundled `.app` previews
contain the UI from their build and do not receive live edits.

`src-tauri/` contains the Rust host. React calls one Tauri command, which sends
requests over stdin/stdout to a local `dioptas-processor` Rust process. Native
file dialogs belong to Tauri. There is no scientific HTTP/API server or remote
service. The bundled frontend uses the Tauri asset protocol, without Vite.
The command worker owns the mutable scientific session. Bulk Batch/Map execution
lends one immutable reader and Dioptrin plan to scoped frame workers; each owns
its decoder buffers and float64 accumulators. Ordered collection and publication
stay on the command worker. Progress and cancellation bypass that
worker without accessing native objects. Pipe responses carry request IDs so a
long fit does not block progress/cancel responses. Window closure drops the pipe,
cancels pending refinement and reaps the child, with a bounded kill fallback.

Native image transfer uses binary buffers through both the Python pipe and
Tauri IPC. Commands and metadata remain JSON. Detector, mask, cake and map
pixels never become base64 strings on this path. A response contains a
little-endian uint32 header length, the UTF-8 JSON header, then the raw buffers
listed in that header. Buffer IDs identify immutable content; the window
advertises the IDs it still retains so unchanged pixels need not be resent.

The compatibility Python display cache retains up to 128 MiB of pixel buffers and associated
statistics, keyed by the complete source content, shape, dtype and display
options. This detects in-place image/mask changes while retaining statistics
from the original scientific precision. The window retains up to 128 MiB of
binary buffers. Detector and cake views normally render with WebGL 2; the
Canvas fallback and PNG export share a 96 MiB colour-image cache. Both caches evict older
entries. Render keys include mask content, palette, linear/log scaling and
intensity limits. Pending requests keep their advertised buffers alive even if
another response evicts them. Ring contours are reused only while the angular
array and calibrant angles agree; integrations continue to use the current
scientific models. The legacy pywebview host and browser-test bridge keep their
compatible JSON/base64 path.

A [standalone macOS Rust application](NATIVE_STANDALONE_PARITY.md) is now available.
`npm run tauri:bundle` builds the complete `.app` with processor, resources,
examples, offline guide and dependency notices. Move the entire application;
it runs without Python or a source checkout. Local bundles are ad-hoc signed,
with no publication/notarization step. Windows/Linux and universal macOS
packaging remain unqualified. The local native artifact and relocation checks
are documented in that ledger.

Development still supports `DIOPTAS_SOURCE_ROOT` for the Python comparison
backend and `DIOPTAS_NATIVE_PROCESSOR` for an explicit Rust executable.
Release Rust startup uses installed resources and a sibling processor, with
no checkout fallback. A missing processor/resource manifest fails explicitly.

For explicit compatibility comparison, use `--backend=python` or
`DIOPTAS_BACKEND=python`; the command-line argument takes precedence. Set up that
backend with `uv sync --python 3.13` first. `DIOPTAS_PYTHON` overrides its interpreter.
No existing preview process is restarted when this source default changes.

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
2. In **Image**, check image orientation, detector and pixel sizes.
   Valid pixel-size edits apply when leaving the field or pressing Enter;
   there is no separate Apply button and the selected tab stays unchanged.
   Previous/next arrows sit beside **Open image**. Detector definitions and
   distortion files follow the transformation buttons, separated by a divider.
   **Load .poni** and **Enter manually** stay available as quiet footer actions;
   mask use, transparency and mask loading are directly below the detector
   tools. Processing uses the native Rust/Dioptrin backend.
3. The shared strip above the tabs shows **Ring**, **Auto advance** and **Pick peaks**.
   Previous/next buttons step through rings; the ring menu shows picked-point totals
   and supports number entry followed by Enter to jump to a ring. Clicking a
   peak-table row selects that group and updates the active ring. Auto advance
   increases the ring number after each selection. With Pick peaks enabled,
   stationary detector clicks pick peaks in any calibration tab; turn it off
   to navigate without adding peaks. **Peaks** holds automatic/single peak search,
   search size and the group table. Pick bright
   positions around the ring; use the group table to inspect or reassign picks.
4. Open **Fit**: distance, wavelength, PONI 1/2 and rotations 1/2/3
   each have a value and an independent fit checkbox. The defaults match Qt:
   geometry parameters free, wavelength fixed. The folder button beside the
   calibrant selector loads custom `.D` spacings. Wavelength/energy, starting
   distance, polarization and fit constraints live here, not on the Image step.
   Calibrate uses the current parameter values and fit checkboxes
   directly; there is no separate Apply step. The example supplies its own known
   fixture values. Select enough
   peaks for the free parameters and spread them across several rings.
5. In **Fit**, press the fixed **Calibrate** action at
   the bottom of the task panel. The **Refinement** controls below Parameters configure automatic
   ring searches using the selected Massif/Blob settings; its progress is shown and it can
   be cancelled. Numeric options apply on blur or Enter, without an Apply button.
   Disable it to fit only the manually selected points.
   **Calibrate** and **Refine** are available together on both
   Fit and Validate, with short explanatory tooltips. Calibrate starts a fresh
   geometry from the current peak selections, distance/wavelength start values
   and fixed parameters. Refine continues from the existing geometry and is
   enabled once a geometry has been fitted, loaded or entered manually.
6. Validate the ring overlays, cake, integrated pattern, and RMS residual.
   Linked click inspection is shared by Integration and Map. Change
   **Validation calibrant** to inspect a different reference without changing
   the geometry. Use the peak table to reassign groups, select/delete several
   groups, or undo/redo edits; refine again after editing selections.
7. Inspect or edit complete geometry through the visible **pyFAI / Fit2D** tabs,
   then save a `.poni` calibration with the general footer action, available on
   every tab. Geometry and fit drafts persist while switching tabs; apply
   geometry edits or refit changed selections before saving.
   Alternatively, use **Load .poni** or **Enter manually** from any tab, without
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
precision independently of the display buffers.

## Changing detector or image dimensions

Opening an image with different source dimensions first offers **Cancel** or
**Open and reset calibration**. Cancel preserves the current image, geometry,
mask, background, corrections and history. Accepting opens the new image without
calibration while retaining the current workspace and tab. It clears detector geometry,
pixel setup, distortion, picked peaks, masks (including enabled mask plugins),
image background/corrections and the previous integration/cake. Image orientation
returns to its original state. Load a matching `.poni` or check the detector/pixel
sizes and calibrate again. Wavelength/distance start values, integration
preferences, overlays and phases remain available; automatic saving and
Autoprocess turn off.

The small **Reset calibration** icon beside **Load .poni** offers the same reset
while retaining the current image. Use it when changing detectors even if the
new detector has the same dimensions. Ordinary same-size image loads preserve
the current calibration, mask and image processing. Rotation is accounted for
when comparing source dimensions.

Previous/next image and frame navigation use the same compatibility check.
Autoprocess stops with a message on a size change instead of silently applying
the old geometry. When a PONI declares detector dimensions, incompatible image
loads prompt even if no image was previously loaded; loading that PONI onto an
incompatible current image is refused. Legacy/custom PONIs without dimensions
cannot establish the expected image size, so their first image establishes it.
Equal dimensions alone cannot establish that a calibration belongs to a detector.

`desktop/tests/test_image_change.py` covers both scientific engines. Run
`node scripts/image_change_smoke.mjs` from `desktop/` for the real-model headless
workflow, or add `--webkit`. It checks confirmation, cancellation/Escape and
focus restoration, reset/reload, ordinary same-size switching and compact layout
at both text sizes. Evidence is written to `desktop/artifacts/image-change/`.

## Custom actions

Use **Settings → Custom actions → Add action** to create a named sidebar
button for a local program or beamline script. Open the compact icon selector
to search 57 symbols, including plain and diagonal arrows. Choose an icon and
press **Save action** to apply it together with the other form edits.
Enter the executable (for
example, an absolute Python interpreter path), then one argument per line.
For Python scripts, the first argument is the script's full path. Paths with
spaces need no quotes. Save the action to add its button above Undo and Redo;
actions can be edited, hidden or deleted from the same settings page.
Each saved action has a trash button in its row for deletion without opening
the editor. Running actions cannot be deleted.
Drag saved actions by their grip handles, or use the up/down controls, to set
their order. A line shows the insertion point and the list scrolls when dragging
near its edges. Focused handles also accept Up/Down keys. Order is
saved as an interface preference and applies to both sidebar buttons and the
action menu. Up to three actions appear directly in the sidebar; additional
actions are available through **More actions**, a searchable list of all
enabled actions. Smaller windows reserve fewer sidebar slots to keep Undo,
Redo and Settings accessible. The menu opens on click and supports keyboard
navigation and Escape to close.
Use a short button name, such as Move or Lookup. The compact name field includes
a live preview at the sidebar's width; longer names are shortened to two lines
there and remain available in full in the menu and tooltip.
No startup configuration file needs to be prepared.

While **Custom actions** is open, the existing sidebar **Undo/Redo** buttons
restore action creation, saved edits (including names, icons and visibility),
deletion, and ordering. Cmd/Ctrl+Z and Cmd/Ctrl+Shift+Z (or Ctrl+Y) work here too;
text fields retain their normal text-editing undo. Save or cancel unfinished
form edits before undoing saved actions. Restored action definitions and order
are saved immediately. The last 100 changes are retained for the current window
session, including when Settings is closed and reopened. Returning to another
workspace restores its scientific history. Running a script does not add an
undo entry or rerun during history restoration.

For a motor-position lookup, arguments might be:

```text
/beamline/tools/lookup_motors.py
--image={image_path}
--frame={frame_index}
```

The input buttons insert placeholders; **Current input values** shows what
they will receive. Available inputs are:

| Placeholder             | Value                                                          |
| ----------------------- | -------------------------------------------------------------- |
| `{image_path}`          | Current detector file's full path                              |
| `{frame_index}`         | Current frame, starting at 0                                   |
| `{frame_number}`        | Current frame, starting at 1 (Qt's series position convention) |
| `{dataset}`             | Selected HDF5 image source, when present                       |
| `{calibration_path}`    | Loaded or last saved `.poni` path                              |
| `{project_path}`        | Current saved `.dio` project path                              |
| `{wavelength_angstrom}` | Current calibrated wavelength in Å                             |
| `{image_name}`          | Detector filename including extension                          |
| `{image_directory}`     | Folder containing the detector file                            |

A button is disabled when an input it needs is unavailable. Manually entered
geometry has no calibration path until saved. A loaded or previously saved
calibration file contains that saved geometry; save subsequent edits before
passing it to another tool. Actions receive the current context when clicked.
They are explicit actions and are never triggered by image loading or project
loading. Each argument is passed directly, without shell evaluation. Shell
scripts can be run using their executable path or a shell executable with the
script path as its first argument.

Actions run in the background without occupying the scientific worker.
Settings shows their running/completed status, exit code and the last 16 KiB
of combined output. A running action cannot be launched again or deleted.
External programs may continue running after Dioptas closes.

Settings are stored automatically in
`~/.Dioptas/desktop-custom-commands.json`, separately from scientific projects
and Qt's startup action configuration. `DIOPTAS_CUSTOM_COMMANDS_FILE` overrides
this location for isolated testing. An already-running preview with an older
Python worker retains icon choices in local interface preferences until the
action is saved with an updated worker. No processing-session restart is
needed to change the icon. **Save action** applies the icon and the remaining
form edits.
`npm run build && npm run test:custom-commands`
runs the headless workflow against the real Python bridge using temporary
settings and a disposable script; it does not touch user actions.

## Map workspace

Map follows the Qt arrangement: scan map on the left, detector and task tabs
at upper right, and a wide pattern beneath them. When the analysis area is
narrow, the detector moves into an Image tab. Drag the dividers to adjust the
panels; double-click a divider to restore its default proportions.

Use **Detach map** (the outward-arrow button below the scan) to move just
the scan map into an independent window and return the main window to
Integration. Move that window to a second screen and click cells to update the
main detector, cake and pattern. The window keeps its layer selector, histogram,
Smooth/Contours and data/PNG exports. Map mode remains available in the main
window for Points, Layers and Grid. **Show map** brings the existing window
forward; the **Dock map** icon returns it to Map mode. Closing the separate window also
docks the panel, without changing the main mode or discarding the scan.
Palette, contrast for unchanged map pixels, smoothing and contours survive
docking. The native map window remembers its size, position and monitor across
docking and app restarts. If the display is rearranged or its scaling changes,
placement follows the saved monitor; if it is disconnected, the window opens
within the current display's usable area. Maximizing/minimizing preserves its
last normal bounds. Plot zoom is not restored after reopening.
While detached, Map mode retains the original left map column as a quiet
placeholder with Show/Dock icons; the detector, controls and pattern keep their
positions. There is no separate workspace header or in-window expansion button.
Selections and layer edits use the main command queue and the same Rust
session; the child reads scan pixels through binary IPC. In Integration, a raw
point is calculated with current settings to populate all integration plots;
stored and normalized map profiles are retained. A missing raw image still
allows inspection of the stored profile. The browser test preview uses a popup
with the same shared panel and ordered commands.

Load calibrated images, a scan folder or a saved project. Load, Folder and
Live/Follow are grouped in Points; calibration and full-map reintegration use
compact icon buttons with tooltips. Grid dimensions apply on Enter or blur.
Points, Layers and Grid show scrollbars as soon as content overflows. Points
keeps its action buttons in one row above the file list; only the list scrolls
when the pattern is enlarged. Point indices and filenames use separate aligned
columns.
Points contains the scan arrangement with drag/keyboard reordering, blanks,
filename-numbering checks and exclude/include. Selected raw images are
reintegrated automatically with current settings when possible; stored-only and
normalized patterns remain available. The Points gear opens Map settings with
an option to reintegrate selected images (on by default) and normalization in a
compact popup beside the gear. Click outside or press Escape to close it.
Normalize using a physical 2θ/Q/d range or an existing pattern window, choose a
reference file, and apply or restore the originals. Reference choices show the
same 1-based row number and filename as Points, including after reordering;
blank cells cannot be references. A window supplies its current
bounds when Normalize is pressed. Layers contains editable
window and expression tables. Window colors link the table and pattern; edits
apply on blur or Enter, keeping Tab navigation within the table. Its numeric ranges
follow the displayed 2θ/Q/d unit. Pattern windows can be dragged, resized,
selected or recentered by clicking. Turn Edit off to zoom inside them. Pattern
2θ/Q/d display and Log/√ scaling do not change stored map data. Each raster keeps its own histogram.
Map's pattern plot shows the visible overlays and phase reflections shared with
Integration, including colors, phase pressure/temperature, overlay scale/offset
and measured-pattern visibility. Manage those references in Integration; Map
retains its Points/Layers/Grid controls. Changing Map's 2θ/Q/d display converts
references along with the measured curve without changing the stored profiles.
Clicking Map's detector or pattern marks the same calibrated position with a
green detector ring/crosshair and pattern line. Integration uses the same
position, including after switching modes or detaching/docking the scan window.
Selecting another scan point keeps both the green position and the Click readout.
The line follows the active 2θ/Q/d display unit. Stationary pattern clicks also
inspect inside editable ROIs; ROI drags continue to edit only the window. The
shared footer reports the clicked 2θ, Q, d and azimuth when available.

Live watches the loaded scan folder for completed numbered continuation files.
Follow selects the latest point; turn it off to retain the selected image.
The reintegration icon applies changed integration settings to the full map.
Save map data writes text/TIFF, PNG saves the map viewport, and Save project
retains the scientific map, windows, colors and layout. See [Map parity](MAP_PARITY.md) for
validation and remaining limitations, including detached windows and growing
HDF5 datasets.

## Batch image series

Integration → Image offers Qt's Integrate, Add, Average and Save choices for
multiple images. Integrate opens a separate Batch window following Qt's Files/2D
dialog layout. Selecting a frame updates
Integration's detector, cake and stored pattern. Use **Dock batch** to place the
series below the image in the lower-left corner; its divider resizes the dock,
and the header can collapse it or detach it again. The compact **Batch…** button
beside **File Info** in the Image tab reopens the window or dock without discarding
data, and is orange while Batch is open. The dock's settings icon opens **Options**, which holds
normalization and range settings so the series keeps most of the space. Its
histogram defaults to vertical on the left, mirrored toward the plot.
Hover uses separate Frame, intensity and radial fields in the shared footer.
Clicking selects both a frame and the linked green radial marker. The Phases
toggle shows shared phase references with the cake view's colors and line strengths.
The floating window has pattern-style unit/scale buttons at the far right; the
dock follows the main pattern’s controls. The dock shows frame position in the header instead
of a bottom browsing slider; click rows or use the overview’s keyboard arrows.
Selecting a frame keeps controls active without a global loading flash.
Both Integration splitters and Batch’s height, collapsed, open and docked states
are remembered across restarts. Smaller windows clamp the visible layout without
erasing your preferred sizes. Closing Batch keeps it closed on restart; quitting
with Batch open restores it. Scientific data is restored by loading a project. Controls include frame range/step,
normalization, HDF5/CSV saving and processed-batch import. Save project retains the series.
See [Batch parity](BATCH_PARITY.md) for workflow, checks and scope.

## Requested display products

The Rust UI requests only the display products it uses. Image browsing, Batch
selection and Map selection do not calculate a hidden cake. Switching to Cake,
opening calibration Validation or explicitly exporting cake data calculates it
on demand through the same native cake kernel. Showing it again reuses the
current result; changing the frame, mask or integration settings invalidates it.
Requesting a cake does not replace a stored/normalized pattern or add history.
Calibration ring contours are requested only while their calibration overlay is
visible. Phase guides and linked inspection contours remain independent.
The common request policy applies to file opens, arrows, settings, Batch, Map,
configuration changes and project loading. Legacy/reference calls without a
product request retain their complete response for compatibility.

## WebGL pattern benchmark

The renderer comparison is described in
[PATTERN_WEBGL_BENCHMARK.md](PATTERN_WEBGL_BENCHMARK.md). It covers ordinary and
large-pattern navigation, CPU drawing cost, frame cadence, upload behavior and
curve geometry. WebGL is the default; `VITE_DIOPTAS_PATTERN_RENDERER=canvas2d`
selects the Canvas renderer for diagnostics and comparisons. The headless
`npm run benchmark:pattern` now also defaults to WebGL; pass `-- --canvas2d`
for an explicit fallback benchmark. Headless GPU timing is not a native GPU benchmark.

## Image and pattern rendering

New detector sources are published together with their source-precision Auto
limits, across Calibration, Mask, Integration (corrected/raw) and Map. The
command queue stays reserved through the source-precision intensity calculation. This
avoids first showing new pixels with the previous file's or temporary default
limits. Contrast and view resets happen before drawing; canvas layers update
before the browser paints. Each display retains its own Auto preferences.
`npm run test:detector-redraw -- --webkit` counts real draw/upload calls and
checks delayed Auto responses; add `--canvas` to check the software fallback.

Detector and cake images use WebGL 2 (`src/WebGLRaster.ts`). Each mounted view
retains one full-resolution R32F intensity texture, an R8 mask and the selected
colour lookup table. Intensity limits, linear/log mapping and mask transparency
are shader uniforms; navigation changes the image projection. These operations
do not re-upload unchanged source pixels or run a JavaScript colour loop.
Nearest-neighbour sampling preserves individual detector pixels and the existing
bottom-origin projection. Calibration guides, masks under construction, ROI
handles, selections and cake axes remain on a transparent Canvas 2D layer above
the image, using the same projection and clip.

WebGL support is optional: unavailable contexts, texture dimensions beyond the
GPU limit and upload failures use the existing Canvas renderer. Context loss
switches to Canvas; restoration rebuilds the textures. Unmounting releases GPU
resources. PNG export deliberately uses the software colour renderer, retaining
its existing 2048-pixel width, current view and annotations without reading back
the GPU. Display rendering does not change scientific arrays, integration,
calibration or original-pixel readouts.

Pattern curves use WebGL 2 (`src/WebGLPattern.ts`) by default, while axes,
reference lines, editable ranges and the cursor use layered Canvas 2D surfaces
(`src/PatternView.tsx`). GPU buffers retain the curve coordinates and change only
when source arrays or intensity scaling change. High/low coordinate pairs retain
precision when zooming around large offsets. Unsupported or lost contexts and
upload failures use the cached Canvas renderer; turning antialiasing off keeps
the established Canvas pixel-line appearance. Context restoration rebuilds GPU
resources. Data extents and application overlay props are memoized. For monotonic
ascending or descending coordinates, binary search finds visible samples
(including boundary neighbours) and the nearest readout sample. Unordered
coordinates retain the general path; displayed samples inside the view are not
decimated, and gaps remain gaps. `npm run test:pattern-quality` checks curve
geometry, default rendering, fallback and context recovery.

Run `npm run test:rendering` and `npm run test:rendering -- --webkit` for shader
pixel comparisons, texture reuse, square pixels, context recovery, unsupported
GPU/texture-limit fallback, export and 100,000-point pattern navigation checks.
The test serves an isolated component fixture on an automatically assigned port,
without using the primary preview's port 1420. Add `--baseline=44504cc2` to compare
the pattern against the pre-change component from that commit. Reports and
screenshots are written to `desktop/artifacts/`.

## Layout and plot interaction

Ctrl+left click and Command+left click provide the right-button gestures in
image, cake and pattern views: click to zoom out 2×, double-click to restore the
full view, and drag to pan. These gestures also work over editable ROIs and
while peak picking or mask painting is active.

Calibration peak lists, Integration Phase/Overlay tables and material/reflection
tables share `DataTable`, `TableScroll` and `TableActions` from
`src/DataTable.tsx`. Header colors, compact row and field sizing, numeric
alignment, color swatches, selection/focus states and persistent scrollbars live
in `src/dataTable.css`. Map file lists use the same scroll surface and typography.
The shared appearance follows the original Overlay table: panel-colored
backgrounds, dark bordered inputs, 17 px checkboxes and compact 26 px rows at
both text sizes. Each view retains its scientific columns, row actions and
selection behavior. Overlay retains its pinned Original pattern row at the
same height as the other rows.

The app has no top header or in-app logo. Mode navigation stays on the left,
with Undo/Redo side by side above Open/Save project and Settings at the bottom.
Mode selection uses a neutral charcoal fill, light text and an orange icon.
Open project, Save project and Settings use compact icon-only buttons with
tooltips; Settings retains the same size when selected. The current project
name appears above its actions, with the full name available on hover. Text size
and keyboard shortcuts are in Settings at the bottom of the sidebar.
Plots occupy the main workspace, and
one changing task panel stays on the right, following the existing Dioptas
arrangement. A shared Ring / Auto advance / Pick peaks strip sits above horizontal
Image / Peaks / Fit / Validate tabs in the right calibration panel; the active
section has an orange underline. Tabs provide navigation, without Back/Next
buttons. The detector image stays visible; cake and pattern also appear on
Validate. Image contains image/detector controls only.
Parameters and Refinement are stacked in the Fit pane and scroll together when
needed, with a visible scrollbar; the fit action stays fixed below them.
Fit drafts survive visits to Peaks.
Refinement help opens above and to the right of its help button. In Tauri it
uses a non-focusing native popup that can extend outside the application window;
it switches to the upper left only when the screen's available area requires it.
Escape, leaving the help button, changing focus or moving the window dismisses
the popup. Browser and legacy previews keep help inside their web view.
The peak table scrolls within the available height,
with pinned column headers and load/save/trash/clear-all icons beside Ring selections.
Load and Save use standalone `calibration-peaks.json` files. Save includes all
picked groups, their ring assignments and exact source coordinates. Load replaces
the table and supports Undo/Redo; it requires matching image dimensions,
rotations/flips and calibrant d spacings. The file is versioned JSON using
Dioptas bottom-left row/column coordinates and one-based ring numbers.
The header checkbox selects or deselects all groups. Clear all asks for
confirmation beside its icon, with Cancel focused by default; Escape or clicking
outside dismisses the confirmation. New or selected groups
scroll into view. Tab labels are flat, with a thin active underline.
Positions remain accessible at both text sizes. Long image/geometry forms use
visible scrollbars. Fit/apply actions stay in one fixed footer position;
Save .poni is available on every tab, with quieter load/manual controls below.
Mask controls are directly visible
in the Image sidebar. Validation keeps complete geometry visible in pyFAI / Fit2D tabs.
The selected validation tab is retained across steps, modes and app restarts.

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
not modify source arrays. Calibrant guides on the detector and cake use thin,
translucent solid lines without a halo and quiet, borderless numbered labels;
cake lines stay at their 2θ positions when the pattern's radial unit changes.
The current picking ring has a slightly stronger stroke and a yellow label.
Picked calibration peaks follow Qt: solid red dots, orange for the current
ring, with larger dots and an opaque white outline for selected groups. Marker
diameters stay at 7/9 screen pixels while zooming.
Mouse coordinates and source intensity update together during movement at roughly
10 Hz, with one pixel read in flight at most. The last completed reading remains
visible while a new source-pixel lookup is pending; the final cursor position is
sampled even when movement stops during a lookup.

The shared footer stays on one line, without source labels, with fixed coordinate
fields. Coordinate precision follows the visible axis range and plot size: broad
intensity ranges show whole numbers, and zooming reveals finer digits. Pattern
x/y follow the pointer; I reports the nearest curve
sample independently of the pointer's height, including log and square-root
display modes. Integration and Map share a compact **Click** position alongside the
live readout, with green text and the selected azimuth. Hover and clicked radial
positions always show **2θ**, **Q** and **d** together, independently of the plot's
selected unit. These are degrees, Å⁻¹ and Å respectively (also named in the field
tooltips). Conversions use the session wavelength, and carry the source coordinate's
resolution into each unit. Calibrated detector hover also includes all three
radial units at the sampled original pixel centre. Unavailable conversions use
an em dash. At compact window widths, the clicked azimuth is available in the
Click tooltip so that all three radial units stay visible on one line.
Stationary inspection clicks leave green radial guides and linked image/cake crosses;
pattern clicks retain the last selected azimuth. Selections survive
display refreshes and radial-unit changes, and clear when the image or geometry
changes. Calibration and Mask show only the live mouse readout.

`node scripts/position_readout.mjs` (optionally `--webkit`) checks footer alignment,
pointer coordinates, persistent click readings, painted linked crosses,
shifted-cake inspection and radial-unit changes against real Python models.

All current plots (detector, cake, integrated pattern) share these controls:

- **Wheel:** zoom the plot under the pointer; the event is captured so the
  surrounding workspace does not scroll or jump.
- **Left drag:** zoom in using the selected zoom mode.
- **Right drag:** pan both axes in Rectangle mode, or horizontally in X-range
  mode. Ctrl + left drag also pans.
- **Right click:** zoom out one step (2× range). X-range mode expands only
  the horizontal range, refitting both pattern intensity limits to visible data
  with a small margin and preserving the cake's current azimuth limits.
- **Right double-click:** completely restore the fitted view, including after
  deep zoom or resizing.

The detector image has no axes, ticks or surrounding card. Its pixels stay
square during zoom, pan, histogram resizing and window resizing. Cake and
pattern retain their scientific axes.

All plots default to Rectangle zoom and detector views preserve square pixels.
The cake and integrated patterns have two separate icon-only buttons in the empty
corner below the y-axis and left of the x-axis for Rectangle and X-range zoom.
Both buttons have transparent backgrounds and a subtle rectangular background only
on hover; the selected icon is orange and the other icon is neutral. X-range selection fits the pattern's
minimum and maximum intensity to the visible data instead of forcing a zero
baseline; the cake keeps its current azimuth range. Wheel zoom follows the selected
mode too. In X-range mode, the pattern intensity limits continuously follow the
visible data during panning and data updates; the cake's azimuth limits stay
fixed. Settings also offers the pattern choice, independently for the main
pattern and Map pattern. Rectangle/X-range choices are saved independently for
the cake, main pattern, Map pattern and Batch plot and restored after restarting
the app.

When Pick peaks is enabled, a stationary left click picks peaks in any
calibration tab. A left drag zooms
without adding peaks. In the Point mask/eraser tool, click to stamp, left drag
zooms to a rectangle, and Shift + left drag paints continuously; right-button
navigation remains available. `F` or right double-click restores the image.
Detector and cake images have no extra title/dimension header, Fit button or
Display mask toggle or tool-selection strip above the plots. Picking is
controlled by the shared right-panel switch. Drawing and erasing belong to the dedicated Mask workspace;
masks remain visible, with use and transparency controlled in task options.

Settings is anchored at the bottom of the left mode sidebar. It opens a full,
fixed-size workspace inside the main window, with a category column for General,
Integration and Keyboard shortcuts. General contains interface text size, the processing-engine selector and
pattern drag-zoom mode. Categories scroll independently of the header. Back, Escape or a mode button returns to the plots;
opening Settings retains the mounted plots and their zoom, layout and drafts.
Reopening Settings restores the last selected category in the current session.
Command+, or Ctrl+, toggles Settings, including from focused plots and fields.
Settings → Integration contains radial coordinates and binning, integration method,
1D/cake azimuth ranges, cake resolution, solid angle, Poisson errors,
polarization and zero trimming. These use the existing session/project settings
with automatic application: checkboxes and selectors take effect immediately;
valid numeric edits apply on blur or Enter, including when leaving Settings.
The native method selector offers fractional polygon splitting, pyFAI-compatible
full pixel splitting, and subpixel sampling for both 1D patterns and cakes; only subpixel sampling shows a subpixels-per-axis control,
limited to 2–20 per axis (4–400 sample positions per detector pixel). A shared
app footer starts beside the full-height left sidebar and shows the active plot's
coordinates/intensity on the left, with workflow, processing, selection, save
and error messages on the right. Detector,
cake, pattern and map readings update at about
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

New sessions trim contiguous leading and trailing exact-zero bins from 1D
integrated patterns by default, including combined-detector patterns and their
exports. **Settings → Integration → Trim leading and trailing zeros** can retain
the full radial grid; saved project choices are honored. Radial coordinates,
counting errors and azimuthal std are sliced together. Internal zeros, negative
intensities and entirely zero patterns are retained. Cakes and the shared stored
Batch/Map grids keep their full binning.

Integration follows Qt's pane arrangement: a full-height image/cake on the left,
with tabbed controls above the integrated pattern on the right. Drag either
divider to resize the panes; Image/Cake switches the left display and preserves
its independent intensity controls. The save icon at the far left of the lower
image toolbar saves the current Image/Cake view as PNG, scientific image/cake data
as TIFF, or cake data as TXT/CSV through the native file dialog. PNG preserves the
current view and colour settings and omits ROI/inspection markers, matching Qt's
2048-pixel export width. The Image, Pattern, Background, Corrections, Overlay and Phase groups connect to the existing local models. Native file
choosers cover pattern/background/phase files and output/input folders. See
[Integration parity and limitations](INTEGRATION_PARITY.md) for the implemented
controls, scientific qualifications, tests and shared contracts.

## Processing engine

The default Rust processor uses Dioptrin directly. It does not import pyFAI or
call Python bindings. Detector/spline support is described in the
[detector ledger](NATIVE_DETECTOR_PARITY.md). The manual form's “pyFAI” label
names the PONI parameter convention; it does not select a Python runtime.

The explicit Python compatibility backend retains its old engine selector and
optional Dioptrin bindings (`uv sync --python 3.13 --extra dioptrin`). Its
fallback rules and support boundary belong to that backend only.

Dioptrin uses full pixel splitting; the usual pyFAI `csr` path uses bounding-box
splitting. Their bin grids and peak heights can therefore differ. The measured
CeO2 fixture is checked against pyFAI `full_csr`, including Poisson std and mask
edits, with relative-L2 regression limits of 0.3% for patterns, 0.6% for Poisson
std and 0.5% for cakes. These are scoped fixture checks, not universal accuracy
claims or bitwise parity. Unsupported integration options (including disabled
solid-angle correction and 1D azimuth sectors) use pyFAI. Spline, nonuniform and
curved detectors also retain pyFAI integration.

For separate cold/repeated-image timings with no, static and changing masks:

```sh
.venv/bin/python desktop/scripts/dioptrin_benchmark.py
```

The report is written to `desktop/artifacts/dioptrin-benchmark.json`. It covers
model calls with each desktop engine's own splitting method, excluding file
IO, IPC and rendering. Native objects are created, used and explicitly released
on the processing thread, including when logs retain an old model.

Dioptrin uses full pixel splitting; the usual pyFAI `csr` path uses bounding-box
splitting. Their bin grids and peak heights can therefore differ. The measured
CeO2 fixture is checked against pyFAI `full_csr`, including Poisson std and mask
edits, with relative-L2 regression limits of 0.3% for patterns, 0.6% for Poisson
std and 0.5% for cakes. These are scoped fixture checks, not universal accuracy
claims or bitwise parity. Unsupported integration options (including disabled
solid-angle correction and 1D azimuth sectors) use pyFAI. Spline, nonuniform and
curved detectors also retain pyFAI integration.

For separate cold/repeated-image timings with no, static and changing masks:

```sh
.venv/bin/python desktop/scripts/dioptrin_benchmark.py
```

The report is written to `desktop/artifacts/dioptrin-benchmark.json`. It covers
model calls with each desktop engine's own splitting method, excluding file
IO, IPC and rendering. Native objects are created, used and explicitly released
on the processing thread, including when logs retain an old model.

## Development and verification

For the current default, use `npm run backend:test`, `npm run build`, `npm test`,
`npm run backend:prepare`, and `cargo test --manifest-path src-tauri/Cargo.toml`
from `desktop/`. `npm run test:backend-commands` audits the legacy command routes;
`npm run test:native-integration`, `test:native-calibration`, `test:native-project`
and the other native scripts use headless Chromium/WebKit. See the audit for
scope and the no-Python host-test invocation. Native window smokes below are
explicit checks for behavior that needs an actual window.

For independent Python references and the legacy comparison bridge:

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
node scripts/calibration_tooltip_native_smoke.mjs
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
Rust host tests exercise the default Rust pipe, full-resolution payloads,
concurrent progress, unexpected child termination, and cleanup. The Python
transport tests verify cancellation bypass even when every request worker is busy.

## Boundaries of this milestone

- Native Tauri macOS startup and the real-data calibration workflow are
  exercised; Windows/Linux packaging and behavior are not qualified yet.
  Linux requires Tauri's system WebKit/build dependencies. The legacy
  pywebview host also needs a supported renderer if used there.
- The frontend offers seeded calibration plus staged automatic ring refinement,
  not Dioptrin's full automatic calibration/ring-identification workflow.
- Full uncertainty diagnostics and explicit HDF5 dataset selection do not yet
  have frontend controls. The Python preview also lacks configuration controls.
  The native Rust preview has a configuration toolbar; its scope is described in
  [NATIVE_PROJECT_PARITY.md](NATIVE_PROJECT_PARITY.md). Integration's
  Image tab now offers editable filenames/directories, a native folder chooser
  and Autoprocess for incoming stable images while Integration is open.
  Integration also exposes backgrounds, selected corrections, phases/overlays
  and pattern saving/autocreate; its remaining Qt scope is
  listed in [INTEGRATION_PARITY.md](INTEGRATION_PARITY.md).
  The Python preview retains existing `.dio` configurations and displays the
  selected configuration.
- Native format-2 project saves retain standard `.dio` state alongside owned
  native resources and workflow metadata. See [project compatibility](NATIVE_PROJECT_PARITY.md);
  legacy formats 0/1 are not admitted, and Qt writers can discard native extensions.
- The cake retains its actual 2θ coordinate even when the 1D pattern uses Q or d,
  matching the existing synchronous Dioptas configuration API.
- The source example is a regression/interaction fixture. Agreement on it does
  not establish calibration quality for other detectors or experimental data.
- The React/Tauri default is Rust. The original Qt application and explicit
  Python compatibility backend remain in the repository for comparison.
  WASM/browser-only execution is not implemented.

The [Python-removal audit](PYTHON_REMOVAL_AUDIT.md) is the current remaining-work
list. Verification sections below record earlier Python-era checkpoints.

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
| ------------------------------------------- | -----: |
| Tauri, binary transfer and display caches   | 160 ms |
| Qt/Python, normal asynchronous processing   | 166 ms |
| Qt/Python, synchronous processing           | 172 ms |

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

## Shared interface and design audit

`TabList` owns task-tab keyboard navigation across the modes, settings and phase
editors. `Dialog` / `DialogHeader` own native modal focus, dismissal and headers;
nonmodal color and action menus retain their own list/menu interactions.
`ScientificNumberInput` formats a visual preview while keeping the exact input
value. `usePlotTypography` carries the Standard/Larger preference into canvas
labels and axes, and `GeometryProvenance`, `PatternFreshness` and
`StatusMessage` share scientific context and feedback. Chrome tokens live in
`uiTheme.css`; scientific palettes remain independent. Integration options are
kept as a session draft and applied together, including the radial coordinate.
The model's shared history action determines Undo/Redo routing and labels.
Manual geometry keeps full-precision drafts, allows convention comparisons and
requires applying/resetting a pending draft before editing the other convention.

From `desktop`, run `npm run test:ui-audit` for the real-model Chromium review,
or `node scripts/ui_audit.mjs --stage=webkit --webkit` for WebKit. The audit loads
CeO2, performs an independent peak-seeded fit, loads the reference PONI separately,
and exercises the measured map fixtures and a six-frame series derived from
CeO2. It captures modes, settings, editors, dialogs and compact/large-text layouts,
checks keyboard and error/draft behavior, canvas text scaling and anchored popup
bounds, and records axe violations separately
from checks requiring manual review. Results go to `artifacts/ui-audit`.
`npm run test:ui-audit:baseline` builds the historical frontend at `b418d66b`
without resetting this checkout; `-- --ref=REV` selects another baseline.
These are headless browser checks, not OS-dialog or formal accessibility certification.

`npm run report:ui-audit` assembles the dated rubric, raw reviews and matched
screenshots into `artifacts/ui-audit/index.html`. The audit alone opts into a
fixed peak-search random seed, so its measured-point fits match across the
before/after and browser comparisons.

The fixed 25-category definitions and equal weights are in `UI_DESIGN_RUBRIC.json`.
`UI_DESIGN_REVIEW.json` records separate Codex and Claude ratings, evidence,
source revisions and limits. `UI_PEER_REVIEW.txt` retains the independent review
and its follow-up addendum verbatim. The current Codex mean is 9.472/10 (9.5 to
one decimal); Claude's independent mean is 9.02/10. These are scoped design
judgments, not scientific accuracy, production readiness or accessibility
certification. Subsequent fixes do not imply a new peer score.

## Shared interface behavior

Resting text inputs use quiet recessed fills without pale outlines; focus and
invalid states stay visible. Focus outlines use neutral gray, including inputs and scientific plots. Selected
tabs, table rows, toggles and settings choices retain orange; focus and active
selection remain distinct. Text sizes and states share theme tokens.
`Dialog`, `TabList`, `HistoryControls`, `WorkspaceModeButtons`, `LayoutDivider`
and the scientific value/status/provenance components centralize common policy.

Pattern and phase legends stay inside the data viewport, with no reserved
header. `PlotLegend` provides bounded dragging and keyboard movement, a small
dark background behind names, a glyph halo and full names on focus/hover.
Placement samples bucket extrema and weights peaks above dense baseline samples;
it avoids existing cursor/ROI/phase labels when data or layout changes, then
stays stable during exploration. Explicit moves stay fixed through data changes.
A four-pixel drag threshold prevents focus clicks with hand jitter from pinning
a legend; arrow keys pin it and Home/Escape restores the default.

`geometryDraft` and `useCalibrationFitDraft` own exact session drafts. Modes,
Settings, dialog dismissal and Undo retain deliberate edits; untouched fields
rebase to the applied model. Apply consumes the geometry draft, and Calibrate
consumes the fit draft. `useDraftReplacement` names affected drafts and asks
before intentionally loading replacement settings. Projects and PONI exports
save applied values; pending option drafts remain in the session.

Fit starting values are explicitly separate from current geometry. Fit and
manual PONI display in mm; manual pyFAI commands still use SI meters. Exact
bounds govern shared validation, while concise error previews identify units
and mark approximate values. Frame positions are one-based, bounded integers;
Batch indices remain explicitly zero-based. Compact Batch toolbars wrap and
keep their window actions reachable. `PathInput` reveals long directory tails
with a clipping cue while retaining native editing.

A focused pattern supports Alt+Left/Right and Alt+Home/End to inspect actual
visible samples without panning or editing the model. The existing readout and
a polite accessible reading expose the values. Descending d spacing, invalid
coordinates and scaled overlays are covered. Documented app/plot/legend/divider
shortcuts have explicit scopes and are exercised against the actual handlers.

## Evidence and remaining limits

The current checks include 65 frontend unit tests, 17 Rust tests, and 58 captured
views plus 39 behavior checks in each of Chromium and WebKit. Batch and pattern controls are checked against clipping ancestors and pointer hit
targets, and their headers must fit one row. Each engine inspects 465 resting
field appearances across captured states, including scientific tables. ARIA snapshots and raw axe
violations/incomplete findings accompany screenshots. Explicit failures and
UI-build hashes prevent incomplete or stale runs being published as current.

Focused regressions are available with `node scripts/ui_audit.mjs --stage=polish
--focus=polish` and `node scripts/ui_audit.mjs --stage=peer-check --focus=peer`.
The full audit includes both. A synthetic three-frame HDF5 fixture verifies
frame navigation; TIFF fixtures follow the existing first-page PIL path. Gold
phase/editor fixtures are not specimen identifications. The original screenshot
baseline is `b418d66b`; the earlier 9.1 checkpoint is `876e0651`.

Native macOS qualification now passes: six Batch detach/dock cycles with changing
bounds; four application-launch stages for floating/closed/docked/collapsed state,
splitters and native bounds; Map docking and a full application restart; measured
CeO2 calibration, WebGL detector/cake/pattern rendering, masking, phase/database
editing, exports and project round trips. Native open, save and batch chooser
cancellation preserves scientific state. All four native help popups retain main
window focus, including screen-edge placement and Escape/blur dismissal.

The original failed runs remain in `artifacts/ui-audit/native/`; they are historical
failures, not rewritten passes. Current reports, commands and scope are described
in [Native verification](NATIVE_VERIFICATION.md). Native screenshots are actual
window captures, distinct from the browser screenshots. Native tests use private
WebKit stores and disposable preference files; restart stages intentionally share
their own store. Screen readers, colour-panel interaction, Windows/Linux packaging,
portable Python distribution and native display-latency measurement remain outside
this qualification.

Retina WebGL results in `artifacts/ui-audit/performance/` retain both WebKit's
reported Apple GPU result and Chromium's slower SwiftShader wide-pan result.
The provenance file identifies the measured source and its limits. These are
headless browser measurements, not native GPU/display-latency certification.

The scan map uses its existing histogram/settings and Layer/ROI controls for scale and calculation context. The redundant permanent summary/color-key block below the map is removed in both main and detached Map views; a concise accessible description retains context without taking plot space.

Batch follows the same layout as Map: the redundant permanent intensity/source-units/color-key row below the heatmap is removed in both docked and detached views. Its histogram and display settings own the scale controls, with accessible context on the series. The now-unused `ColorScaleLegend` component and styles have been removed.
