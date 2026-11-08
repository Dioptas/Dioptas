# Dioptas React / Tauri desktop preview

An experimental React/Tauri desktop interface for Dioptas with Calibration,
Mask, Integration and Map modes, plus a linked Batch window. It lives beside the existing Qt application
and uses its scientific models and file formats. It is not a complete
replacement yet.

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

## Shared UI controls

All views use the controls and surfaces in `src/ui`, including table fields,
popup menus and detached windows. The shared stylesheet owns their neutral
palette and interaction states. See [UI_COMPONENTS.md](UI_COMPONENTS.md) for
component usage and the checks that prevent new per-view control themes.

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

For phase-editor work in its assigned checkout, use `npm run tauri:phase-dev`.
This opens the raw-image example with live React/CSS updates on its dedicated
port 1426, including the detached phase-editor window. It leaves the primary
preview's port 1420 and existing bundled windows alone. Bundled `.app` previews
contain the UI from their build and do not receive live edits.

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
binary buffers. Detector and cake views normally render with WebGL 2; the
Canvas fallback and PNG export share a 96 MiB colour-image cache. Both caches evict older
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
2. In **Image**, check image orientation, detector and pixel sizes.
   Valid pixel-size edits apply when leaving the field or pressing Enter;
   there is no separate Apply button and the selected tab stays unchanged.
   Previous/next arrows sit beside **Open image**. Detector definitions and
   distortion files follow the transformation buttons, separated by a divider.
   **Load .poni** and **Enter manually** stay available as quiet footer actions;
   mask use, transparency and mask loading are directly below the detector
   tools. The processing engine lives in **Settings → General**.
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
precision in Python.

## Changing detector or image dimensions

Opening an image with different source dimensions first offers **Cancel** or
**Open and reset calibration**. Cancel preserves the current image, geometry,
mask, background, corrections and history. Accepting opens the new image without
calibration and returns to Calibration → Image. It clears detector geometry,
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

| Placeholder | Value |
| --- | --- |
| `{image_path}` | Current detector file's full path |
| `{frame_index}` | Current frame, starting at 0 |
| `{frame_number}` | Current frame, starting at 1 (Qt's series position convention) |
| `{dataset}` | Selected HDF5 image source, when present |
| `{calibration_path}` | Loaded or last saved `.poni` path |
| `{project_path}` | Current saved `.dio` project path |
| `{wavelength_angstrom}` | Current calibrated wavelength in Å |
| `{image_name}` | Detector filename including extension |
| `{image_directory}` | Folder containing the detector file |

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
Selections and layer edits use the main command queue and the same Python
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

## WebGL pattern benchmark

The renderer comparison is described in
[PATTERN_WEBGL_BENCHMARK.md](PATTERN_WEBGL_BENCHMARK.md). It covers ordinary and
large-pattern navigation, CPU drawing cost, frame cadence, upload behavior and
curve geometry. WebGL is the default; `VITE_DIOPTAS_PATTERN_RENDERER=canvas2d`
selects the Canvas renderer for diagnostics and comparisons.

## Image and pattern rendering

New detector sources are published together with their source-precision Auto
limits, across Calibration, Mask, Integration (corrected/raw) and Map. The
command queue stays reserved through the Python intensity calculation. This
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

## Optional processing engine

**The desktop prefers Dioptrin when installed and compatible, and otherwise
starts with pyFAI.** Dioptrin remains optional. Tauri uses the normal Dioptas scientific dependencies.
The `desktop` extra adds pywebview only for the earlier comparison host.

To install the optional Dioptrin engine:

```sh
uv sync --python 3.13 --extra dioptrin
```

Restart the processing session after installation. This checkout pins Dioptrin
0.9.0 and selects it automatically at startup. **Settings → General → Processing
engine** switches between Dioptrin and pyFAI. Selection checks the required API
before changing the session. Dioptrin 0.9.0 requires no license activation.
The engine choice is local to the session, not restored from another computer's
project; new sessions prefer the installed native engine again.

`dioptas/desktop/engines.py` defines the narrow calibration adapter: seeded peak
finding and geometry fitting. The Dioptrin adapter calls its existing Python
bindings; pyFAI uses the same calibration entry points as Qt Dioptas. Session
storage, detector definitions, PONI conventions, and integration remain in the
existing Dioptas models. Their existing pyFAI fallback rules still apply for
native integration options that are unsupported. The native calibration adapter
currently accepts only flat detectors with uniform pixels and no distortion
spline; use pyFAI otherwise.

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

Dioptrin 0.9.0 update (2026-11-06): the desktop suite passes **309 tests**
with the native engine installed, including missing/incompatible-engine fallback,
full-split numerical comparisons, mask edits, cancellation and native-resource
release. Shared CalibrationModel/Pipeline/integration-task checks pass **111
tests**. The headless browser workflow covers automatic native startup, explicit
engine switching, calibration and integration. No visible test window is required
for this backend change.

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
- Full uncertainty diagnostics, explicit HDF5 dataset selection, and
  configuration switching do not yet have frontend controls. Integration's
  Image tab now offers editable filenames/directories, a native folder chooser
  and Autoprocess for incoming stable images while Integration is open.
  Integration also exposes backgrounds, selected corrections, phases/overlays
  and pattern saving/autocreate; its remaining Qt scope is
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
