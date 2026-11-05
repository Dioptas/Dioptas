# Batch processing in the React desktop

Batch reuses Qt's `BatchModel` and the current configuration's Python integration
pipeline. It is a dedicated workspace in the existing window, with navigation on
the left and task controls on the right. Qt's separate batch window, waterfall
and 3D surface are replaced by a selectable 2D intensity overview, a square-pixel
detector image and the selected stored pattern.

## Workflow

- In Integration → Image, **Load image…** accepts multiple files. One selection
  keeps ordinary image loading; multiple selections integrate automatically and
  open Batch. **Batch processing…** and the left-hand **Batch** button open the
  workspace without replacing the series. Cmd/Ctrl+O accepts multiple images in
  Integration and Batch.
- **Load images…** preserves the picker order. **Load folder…** uses natural
  filename order. A calibration is required; the current mask, transformations,
  radial binning/unit, azimuth range, detector corrections and image background
  are captured into an isolated configuration on the existing processing worker.
  No scientific server or Qt application is started. Dioptrin stays optional.
- The overview shows one row per integrated frame, first at the top. Click a row,
  choose a file, use previous/next, or enter a pattern number to load its original
  detector frame and stored integrated pattern. Arrow Up/Down and Home/End also
  select rows when the overview has focus. The orange outline marks the selection.
- The horizontal axis labels use the actual stored 2θ, Q or d coordinates.
  The heatmap uses one column per radial bin, including nonuniform radial axes;
  tick positions interpolate those coordinates. It does not resample the pattern
  matrix or substitute the current single-image integration for a stored pattern.
- Detector and overview histograms are independent and start linear/Grey. Each
  uses the existing intensity, Auto, palette and display-settings controls.
  Detector images retain full resolution, orientation and square pixels. Batch
  uses the shared detector/pattern setup: mask opacity follows the transparency
  setting, and compatible detector/pattern zoom ranges carry between workspaces.
- Plot gestures follow the shared implementation: rectangle zoom, right-drag
  pan, right-click zoom out, right-double-click fit and wheel zoom. F restores the
  overview. Dragging never also selects a row. Readouts use the app footer.
- **Integration range** uses one-based inclusive first/last source frames and a
  positive stride. **Reintegrate range** always uses the original loaded source
  series and the current settings. Stored results remain unchanged until that
  explicit action. Progress and cancellation use the existing independent path.
  Failed/cancelled work retains the preceding complete batch and live image.
- **Normalization** matches the mean intensity in a one-based inclusive bin
  interval to a selected reference pattern, using Qt's normalization model.
  **Restore original** restores the retained source arrays without inverse-scaling
  loss. Invalid or nonpositive means reject the operation.
- **Save batch…** writes Qt-compatible processed HDF5 or radial/frame/intensity
  CSV through Qt's writers. It saves the current intensities, including applied
  normalization. Output is published atomically. HDF5 adds an optional
  `desktop_normalized` result attribute and, for newly integrated batches,
  the actual integration wavelength in `desktop_wavelength_m`. Reimported
  intensities are the saved values. Pattern coordinate readouts use only a
  recorded source wavelength; unrecorded conversions remain unavailable. The
  exported file does not retain the unnormalized source intensities.
- **Open processed batch…** supports stored 2θ/Q/d matrices without requiring a
  live calibration. Import runs Qt's reader in an isolated configuration, so its
  optional calibration/mask loads cannot change the live setup. Missing raw files
  show the stored pattern and an explicit footer message. Reload original images
  to enable reintegration of an imported batch.
- Ordinary **Save project** retains the matrix, radial axis, raw-file/frame maps,
  selection and normalization restore state in an optional `react_desktop_batch`
  HDF5 group. Qt readers ignore this desktop extension. Source images stay external.

## Scope and verification

The implementation covers selecting and integrating image series, frame browsing,
2D overview, range/stride, normalization, processed import/export and project
persistence. It does not add Qt's image sum/average/save modes, batch background
extraction, phase fitting, folder-to-folder stepping, a detached native window,
or a 3D view. Multi-frame support follows the existing image loaders (tested with
HDF5); the PIL TIFF loader currently exposes only its first page. Explicit HDF5
dataset selection remains outside the desktop preview.

`desktop/tests/test_batch_workflow.py` checks direct Qt BatchModel parity for
2θ/Q/d, mask/orientation and wrapped azimuth, live-pipeline background/flat-field
parity, HDF5 frames, range/stride, exact normalization restoration, missing raw
files, atomic failure/cancellation and processed/project round trips.

`node scripts/batch_smoke.mjs` (also `--webkit`) checks the real Python-backed UI,
automatic entry from Image, linked row/list/keyboard selection, filtering,
gestures, normalization, reintegration, saving/reopening and 1000 × 700 layout
at both text sizes. `npm run tauri:smoke -- --batch` checks bundled WKWebView,
binary transfer, linked selection, independent histograms, HDF5 round trip and
processing-child cleanup. Existing desktop, JavaScript and native calibration
regressions remain applicable. Generated screenshots/reports live in ignored
`desktop/artifacts/`.

Verification in this worktree: 199 desktop Python tests passed (5 skipped),
37 JavaScript tests and 11 Rust tests passed. Build, Chromium/WebKit batch
smokes, the broader calibration/browser smoke, bundled native calibration
smoke and dedicated native batch smoke passed.

Merge verification on 2026-11-05: the main React checkout builds; 55 JavaScript
and 16 Rust tests pass, as do Chromium/WebKit Batch checks (including shared
zoom across Integration/Batch) and the broader headless calibration/browser
workflow. The full desktop Python suite reports 277 passed, 5 skipped and one
pre-existing failure in
`test_prepare_cif_and_import_use_experimental_cutoff_and_wavelength`: its exact
Q-cutoff expectation predates automatic structure-reflection coverage expansion.
The same result was reproduced using the pre-merge `DesktopSession` from
`bfe27394`. All ten Batch model tests pass.

CIF assertion follow-up (2026-11-05): the regression now verifies the requested
import settings and final experimental coverage, including retention of a wider
requested range. The focused phase/model tests pass (53 tests), and the full
desktop Python suite passes with 279 passed and 5 skipped.
