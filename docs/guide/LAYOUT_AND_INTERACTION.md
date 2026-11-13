# Layout and plot interaction

> Moved from the former desktop README (now `DEVELOPMENT.md`). Source paths and commands are relative to the repository root.

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
Color lookup tables are frozen assets; see `licenses/colormaps/` for source
attribution. Their historical generator is available in Git history.
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

Native headless backend and calibration checks cover footer alignment,
pointer coordinates, persistent click readings and linked plot inspection.

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
