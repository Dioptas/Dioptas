# Batch processing in the React desktop

Batch starts from Qt's `dioptas/widgets/integration/BatchWidget.py` and its
controllers, and reuses `BatchModel` and the current Python integration pipeline.
It is a separate companion window linked to Integration. There is no Batch mode
in the left sidebar. Qt's Files and 2D views provide the layout baseline; 3D is
intentionally omitted. React's existing typography, plot gestures, image controls
and neutral charcoal/orange styling apply.

## Qt layout and docking

The top row follows Qt: Open raw/proc data, previous/next folder, Save, source
folder, and Files/2D tabs. Files shows Calibration File, Mask File, and the raw
filename/N images table. Selecting a file selects its first integrated frame.
2D shows the selectable intensity series with 2θ/Q/d and lin/√/log options at the
right in the separate window. Its independent histogram uses the existing React
image controls and defaults to vertical, leaving more height for the series.

Below the view, Files offers Integrate; 2D offers AutoScale and Normalize with a
separate normalization-settings popup. Previous/slider/next, Frame, and
Start/Stop/Step follow beneath. Displayed frame and bin indices start at zero,
as in Qt. Start/Stop are inclusive; the adapter translates them to the existing
one-based inclusive processing-command range.

**Dock batch** moves the same panel into Integration's lower-left corner below
the detector/cake and image toolbar. It shares the left column's width and leaves
the pattern and right-hand task controls in place. Drag the divider (or focus it
and use Up/Down) to resize; double-click resets the height. The header can collapse,
hide or detach the panel. **Batch view…** in Integration → Image reopens it.
Dock preference and height persist. Hiding or closing the window keeps the batch.
When docked, an **Options** tab beside Files/2D holds unit/scale controls,
AutoScale, normalization and Start/Stop/Step. The 2D tab keeps only the series,
histogram and frame navigation. Options edits survive tab changes, and returning
to 2D preserves zoom, contrast and selection. Files retains its integration range.
The full-width splitter between image and Batch has a visible grip, pointer
resizing, keyboard Up/Down and double-click reset; the dock can shrink to 220 px.
Overview contrast, palette, scaling and zoom survive docking and reopening.
The native window remembers its own size/monitor/position and uses Map's existing
monitor-aware placement logic, with separate saved placement. Removed displays
or changed screen scaling are handled by that shared implementation.

## Processing and linked selection

- Integration → Image **Load image…** and Cmd/Ctrl+O accept multiple files.
  Multiple selections integrate automatically and open Batch while the main
  window stays in Integration. One image retains ordinary image loading.
- Open raw/proc data accepts raw image series or one processed HDF5 batch.
  Previous/next folder uses Qt's neighboring numbered-folder lookup and matching
  file extension. Input order is preserved. A live calibration is required to
  integrate raw data; processed patterns can be opened without one.
- Integration captures the current mask, transformations, binning/unit, azimuth
  range, detector corrections and image background into an isolated configuration
  on the existing worker. Reintegration is explicit and uses current settings.
  Failed/cancelled processing retains the previous complete series and image.
- Click a 2D row, choose a file, use navigation, or enter a frame number. The
  selection loads the original detector frame and calculates the cake through
  Integration's normal processing path. The selected stored profile is then
  restored, including normalization. These calculations never replace the stored
  batch matrix. The linked green inspection position is retained.
- Missing raw files clear stale detector/cake pixels and show the stored profile
  with a message. Imported batches cannot be reintegrated until raw sources are
  loaded again. Raw source images remain external to saved projects.
- 2D uses one column per radial bin and one row per integrated frame. Physical
  tick labels follow the actual radial coordinates, including descending d axes.
  Display unit conversion retains the original axis and intensities; conversion
  to/from 2θ requires the recorded source wavelength. Q↔d needs no wavelength.
- Rectangle zoom, right-drag pan, right-click zoom out, right-double-click/F fit,
  wheel zoom and keyboard row selection use shared plot navigation. Dragging
  never selects a frame. Readouts report original intensities, including in √/log
  display. Detector pixels remain full resolution and square. Histograms for
  detector, cake and batch overview are independent.
- Normalize matches each frame's mean over the selected inclusive bin interval
  to a reference frame using Qt's model. Settings can be saved before enabling
  normalization. Turning Normalize off restores retained original arrays exactly.
  Invalid ranges and nonpositive means reject the operation.

The child uses the main window's ordered mutation queue and the same processing
session. Native child commands are restricted to read-only batch snapshots and
levels; mutations and file dialogs route through the main window. Snapshot pixels
use existing binary IPC. Browser tests use the same panel in a popup. Progress
and cancellation use the existing independent processing path. No scientific
HTTP server or Qt application is started, and Dioptrin remains optional.

## Persistence and remaining scope

Save writes Qt-compatible processed HDF5 or radial/frame/intensity CSV through
Qt's writers, publishing atomically. It saves current intensities, including
normalization. Optional HDF5 metadata records normalization and, for newly
integrated series, the actual integration wavelength. Saved processed files do
not retain unnormalized source intensities. Import uses an isolated configuration,
so embedded calibration/mask references cannot replace the live setup.

Save project retains the matrix, axis, raw-file/frame maps, selection and
normalization restore state in the optional `react_desktop_batch` HDF5 group.
Qt ignores this extension. The project does not embed raw images.

Qt's batch background extraction, waterfall, phase controls and image
sum/average/save modes are not implemented here. Multi-frame support follows the
existing loaders (tested with HDF5); the PIL TIFF loader exposes only its first
page. Explicit HDF5 dataset selection remains outside the desktop preview.

## Verification

`desktop/tests/test_batch_workflow.py` compares real Qt-model results for 2θ/Q/d,
mask/orientation, wrapped azimuth, background/flat-field corrections and HDF5
frames. It checks range/step, exact normalization restoration, independent cake
updates, read-only snapshots, raw/processed opening, wavelength-aware units,
neighboring folders, missing raw files, atomic failure/cancellation and
processed/project round trips.

`node scripts/batch_smoke.mjs` (also `--webkit`) checks the real Python-backed
companion and dock: automatic opening from Image, Qt Files/2D controls,
linked frame/cake selection, normalization, unit and intensity options,
reintegration, saving/reopening, gestures, contrast/zoom preservation,
collapse/resize/hide/detach, missing raw images, and 1000 × 700 layout at both
text sizes. Generated screenshots/reports are in ignored `desktop/artifacts/`.

`npm run tauri:smoke -- --batch` uses an isolated application identifier to check
native window open/dock/reopen, remembered placement, binary reads, rejection of
child mutations, linked cake/profile selection and processing-child cleanup.
This requires real native windows; routine layout checks remain headless.

Compact dock follow-up: Chromium and WebKit checks cover vertical histograms,
Options reachability at both text sizes, retained edits/view state between tabs,
and pointer/keyboard resizing of image, dock and overview. At 1000 × 700 with
large text and a 320 px dock, the 2D data area is at least 150 px tall.

The prior CIF assertion fix remains covered by the full desktop Python suite.

Verification on 2026-11-05: 283 desktop Python tests passed (5 skipped),
55 JavaScript tests and 17 Rust tests passed. Build, Chromium/WebKit Batch
companion/dock checks, the detached Map regression, the broader headless browser
workflow and the isolated native Batch smoke passed. The first native run found
an incorrect size/position argument in the test harness; the corrected harness
passed. These checks do not establish Windows/Linux native window behavior.
