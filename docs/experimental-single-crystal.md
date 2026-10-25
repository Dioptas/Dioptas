# Experimental single-crystal mode

Development lives on `codex/single-crystal-mode` and uses PhaseSmith's
`codex/experimental-spots` branch. It is outside the standard release path:
no tags, release version changes, default dependency changes or default mode
changes. The source checkout also requires an explicit opt-in switch. The
ordinary published PhaseSmith wheel does not contain the experimental engine.

## Local development

Build PhaseSmith in its own checkout with:

```sh
maturin build --release --features experimental-spots --out dist-experimental
```

Install that wheel into this Dioptas checkout's development environment after
installing Dioptas and its normal dependencies. Do not use `uv sync` again
without reinstalling the experimental wheel: the normal lock resolves the
published default PhaseSmith build. Launch with the opt-in variable set:

```sh
# Linux/macOS
DIOPTAS_EXPERIMENTAL_SINGLE_CRYSTAL=1 .venv/bin/python run.py
```

```powershell
# Windows PowerShell
$env:DIOPTAS_EXPERIMENTAL_SINGLE_CRYSTAL = '1'
.venv\Scripts\python.exe run.py
```

There are no external executables, system-specific scientific libraries,
process workers or DIALS dependencies. Each PhaseSmith detector runs one native
thread outside the interpreter lock; rotation scans use four concurrent frame
detectors by default. Dioptas queues one application job at a time and
discards results after changes to images, masks, configurations or settings.

## First milestone

Open an image in any mode and select **Single Crystal**, or open it directly
from the new panel. Configure detection/noise assumptions and select **Find
spots and extract counts**. No phase, composition, known cell, space group or
source structure is required. The panel shows centroids, signed aperture sums,
conditional standard errors, I/sigma, background and quality flags. Yellow
markers identify unflagged records; red markers identify records needing
inspection. Every retained record is exported, including flagged records.

Input is the original detector count array after Dioptas image orientation
transforms, with the enabled combined user/plugin/ROI mask. NaN/Inf detector
pixels are additionally excluded. Dioptas's display scale, background image
subtraction and intensity corrections do not enter this raw-count analysis.
This choice keeps the declared Poisson/read-noise approximation interpretable;
it does not imply that uncorrected counts are crystallographic intensities.

An explicit **Exclude zero-valued detector padding** option is off by default.
It helps with image-plate frames whose unused exterior is zero-filled. It also
excludes genuine zero-count pixels, so it must not be enabled indiscriminately
for photon-counting data. Its setting is retained with the exported mask policy.

Export writes a CSV and JSON sidecar, recording every default/selected
threshold, support/noise setting, image shape/dtype, orientation transforms,
source filename and image/mask checksums. The sidecar does not embed the raw
image or exact mask: retain those inputs with the exported observations.
Experimental results are session-local and are not silently inserted into the
ordinary `.dio` project persistence format.

The single-frame action has no profile fitting, deblending, indexing,
partiality correction, absorption correction, scaling or structure solution.
Rotation linking and experimental geometry/cell proposals are separate actions
described below. The background is a local constant mean.
Unresolved physical overlaps can form one detected component without an
OVERLAP flag; that flag checks intersection of measurement apertures only.
Uncertainties are conditional on independent pixels and declared noise. They
omit detection selection bias, background gradients and shared-background
cross-spot covariance. Follow PhaseSmith's `docs/experimental-spots.md` for
the exact numerical contract and quality flags.

The dedicated CI workflow builds the experimental backend and tests the
integration on Linux, macOS and Windows. Adding this matrix is not evidence
of a completed passing run; check its actual results before promotion.

## Rotation-series position hunt

The primary development workflow is now **Open rotation series → confirm angles
→ Find 3D positions**. Choose any numbered frame; the importer selects that run's
matching filename prefix and sorts by numeric suffix. It requires explicit omega
bounds: confirm the per-frame sidecar interpretation or enter first start, step
and exposure width separately. Missing frame numbers keep their angular gaps.
Source sidecars and any user override remain in exported provenance.

The slider browses the whole run with exposure start/end and midpoint readouts.
The position table lists x, y, omega, detected omega RMS, observation count and
quality. Selecting a row shows a frame from that candidate. Frame browsing preserves results; changing
mask, orientation, configuration or detection settings invalidates them. Work
runs in the existing background-job queue, reports frame progress and discards
stale results. Images are read serially; up to four frames can be detected concurrently.
The bounded pipeline consumes detections in source order before linking and
calculating position centroids. Preview images are retained by frame index so
read-ahead cannot mismatch an image and its detections. Export provenance records
the frame worker count; numerical records and source fingerprints are unchanged.

Position export writes a track CSV, an observations CSV with every source frame,
and a JSON provenance sidecar. It has no integrated-intensity column. Detector
sums are internal centroid weights only; exposure midpoints limit omega
resolution. Ambiguous many-to-one links and scan-boundary candidates are flagged.
The separate geometry/cell action below transforms these positions to reciprocal
space and proposes candidate HKLs/cells. Rocking-curve integration follows later.

The existing single-frame measurement action remains available separately.
No ordinary release switch or dependency was changed.

A separate development launcher opens a run directly without loading or saving
the regular Dioptas settings:

```sh
.venv/bin/python -m dioptas.experimental_single_crystal /path/to/sample_001.tif \
  --sidecar-angles --find-positions
```

For missing metadata, replace `--sidecar-angles` with
`--omega-start -38 --omega-step 0.5 --omega-width 0.5` (use the measured values).
`--exclude-zero-padding` is opt-in. Optional `--saturation N` flags pixels at N
counts; N must come from detector knowledge rather than an assumed full-well.

## CPU omega-background subtraction

After opening a rotation series, select **Omega background…**. This separate
operation estimates a baseline along omega at each detector pixel, using an
independent implementation of arPLS with native CPU/OpenMP acceleration and a
SciPy fallback. The omega-sequence application is credited to **Konstantin
Glazyrin's background-sc**; the arPLS method is credited to Baek et al. (2015).
No code from background-sc is reused and there is no GPU requirement.

The dialog can export every corrected frame as signed float32 TIFF with omega
bounds, source metadata and masks, plus summed images and convergence maps.
**Open corrected series** reopens those frames with their angles and exported
mask. Original detector files remain unchanged. The worker is cancellable;
partial results are removed and existing result directories are never replaced.

This requires uniformly spaced frame midpoints and one image file per exposure.
Broad or persistent scattering can enter the baseline; corrected counts alone
do not supply valid intensity uncertainties. Use this output for inspection and
position hunting until intensity preservation is validated for the experiment.

See [method, boundaries and export conventions](source/omega_background.rst)
and [measured CPU timings](omega-background-performance.md). On an M4 Pro with
eight workers, a 76-frame 2048 × 2048 Fe7C3 scan took 17.8 seconds including
individual-frame export, with zero-padding excluded. At the default iteration
cap, 7.6% of processed pixels were flagged as unconverged.

On a machine where automatic discovery of external HDF5 plugins stalls during
startup, the opt-in development wrapper configures HDF5 before importing Dioptas:

```sh
.venv/bin/python run_experimental_single_crystal.py --no-hdf5-plugin-autoload \
  /path/to/sample_001.tif --sidecar-angles --find-positions
```

This uses the bundled HDF5 library's public `H5PLset_loading_state(0)` API for
that process only. It leaves global plugin files and settings untouched.
`hdf5plugin` still explicitly registers its bundled compression filters; a
compressed Blosc HDF5 write/read test checks this path. Omit the flag when
external automatic plugin discovery is needed. The ordinary launcher and normal
Dioptas startup do not change. The observed local startup stall reproduced with
h5py alone, including a clean environment; dependency versions were restored
after diagnosis.

## Geometry and blind cell search

After finding series positions, select **Geometry and find unit cell…**. Choose
the detector PONI calibration for the scan, its row convention, and the vertical
rotation-axis sign. Use **Test both signs** when uncertain. The sign is defined
in pyFAI's right-handed (1=vertical,2=horizontal,3=beam) basis, rather than an
ambiguous clockwise label. The maximum cell edge is a generic search bound;
the dialog has no material, expected cell, crystal system, space group or UB input.

Legacy Dioptas calibrations describe displayed, vertically flipped rows; PONI
files calibrated against original array rows require the second coordinate
option. Additional Dioptas image flips/quarter turns are undone explicitly.
The adapter uses pyFAI's calibrated rays and rejects non-affine detector geometry.
Wavelength is required. Spatial distortion and parallax models are not supported.

Every frame observation is transformed into the reference sample frame before
one equal-observation mean is formed per track. The search uses each linked spot
once, excluding flagged tracks, tracks with more than eight observations and
reciprocal RMS spread above 0.03 Å^-1. It reserves five-frame blocks for checking
the result, excluding links crossing partition boundaries. Both signs use an
identical position selection. PhaseSmith evaluates fused Fourier values,
gradients and Hessians and runs a bounded native FFT (at most 256³).
The job uses the same single-worker queue and discards stale results.

Choose **FFT grain search** to discover competing lattice orientations from
unindexed positions, or **Compact FFT cell search (comparison)** for the earlier
method. No input HKLs, cell or material are required. The numerical engine is part
of PhaseSmith; no research checkout is needed at runtime. Grain search uses at
most four private native workers and a declared grain budget. Training-only
reassignment freezes the complete pool before rotated held-out controls are run;
rejected models remain in the result. There is no all-data polish after validation.

The candidate table lists every returned model within the search bounds, with
cell edges, angles, volume, training/held-out percentages, residual RMS, rotation
sign and pass/rejection status. Hover for match counts/control support. Sort
columns and use **Open candidate table…** for a wider view. Select a row for
subsequent prediction/refinement; changing selection clears the previous fit.
Several grain orientations can share the same cell. The compact method retains
up to 40 distinct cell proposals; the grain method retains the frozen model pool
and exports its complete per-round proposal/reassignment audit.

The panel lists size-reduced, unconstrained cell metrics and training/held-out
matching fractions. Passing these provisional checks does not prove a primitive
cell, a space group, a unique lattice or a material identity. A cell from diamond
or another phase is possible; the program does not identify chemistry. Multiple
lattices, missing reflection classes and geometry errors remain limitations.

**Export cell candidates…** writes JSON provenance and a CSV of selected track
IDs, corrected q, provisional HKL, residual and training/validation membership
for every returned candidate under each tested sign, including rejected ones. It records calibration hashes, exact
geometry vectors, source position metadata, algorithm hashes and search/filter
settings. Original frames and position results remain unchanged. Candidate HKLs
are diagnostic assignments, not integrated crystallographic intensities.

See PhaseSmith's `docs/experimental-reciprocal-indexing.md` for equations,
support conventions, search bounds, complexity and independent reference tests.

## Predicted spots and positional cell/orientation refinement

Selecting a ranked cell already selects its fitted cell and orientation. The
**Cell** section names that cell and offers **Show predicted positions (+)**
above its ranked table, with residual plots and prediction export below. The
visibility toggle's tooltip explains the overlay colours. There is no separate
Predictions tab. This section has no additional cell-search
or refinement buttons, initial/refined selector, or fitting summary. Browsing
frames or choosing a different cell updates positions automatically, without a
new fit. Instrument geometry remains fixed; no intensity model is supplied.

Cyan crosses overlay geometrically possible **Bragg centres** on each exposure
as the frame slider moves. The calculation solves both Ewald crossings and uses
the current panel orientation. Enabled masks/nonfinite pixels and optional zero
padding filter the displayed crosses. Click a cross for its provisional HKL and
omega. Weak or systematically absent reflections can still be predicted. The
overlay is not an intensity, rocking-width or completeness prediction: a real
spot can persist on adjacent frames around its calculated Bragg centre.

The image always uses the selected fitted setting, as do the selected-spot hkl
and residual readouts. Initial predictions remain in diagnostic plots and audit
exports. Neither overlay visibility nor frame browsing changes the fit or
selects an iteration using validation data.

**Residual plots…** opens six plots of calculated-minus-measured x, y and omega
against scan angle/detector position. Grey denotes the initial model, blue the
refined training points and orange the held-out points. Outliers are retained in
these comparisons; robust weighting affects fitting, not the plotted population.

**Export predicted positions…** writes JSON with both reciprocal bases,
orientation matrices, fixed geometry, loss settings, validation metrics and
source/code hashes. A centroid CSV retains every selected track, including
unmatched/excluded rows, with frozen HKLs, partition, predictions, residuals and
failure flags. Another CSV lists all possible integer-HKL panel crossings for
both models before display-mask exclusions. No integrated intensities are added.

The scan envelope is limited to 180°, 10,000 exposures, 250,000 raw enumerated
HKLs and one million frame-assigned predictions; exceeded budgets fail explicitly.
See PhaseSmith's `docs/experimental-spot-prediction.md` for equations, analytical
derivatives, half-open detector/exposure support and independent validation.

### Series navigation, plot gestures and metric settings

Use **Open series from one frame…** and select any numbered image. Dioptas finds
all files with the same filename prefix and extension, sorts their numeric frame
IDs and previews the range/missing numbers with the angle metadata. Confirm that
preview or enter explicit angles if metadata are absent. The selected frame opens
first; previous/next buttons to the right of the slider step through the discovered
files and stop at the ends. Numeric gaps remain angular gaps. Other run prefixes
are excluded. Browsing keeps the detected positions and cell results.

Hovering over the single-crystal image displays x/y pixel coordinates, raw
detector counts, 2θ (degrees), d-spacing (Å), Q = 2π/d (Å⁻¹), and azimuth χ
(degrees). Counts come from the displayed frame, including live search previews.
Scattering coordinates use the detector snapshot selected for cell finding,
including the original/displayed row convention and image transformations;
before cell finding they use the active Dioptas calibration. Without calibration,
only pixel coordinates and counts are shown. Values clear outside the detector.
Image coordinates refer to pixel edges (pixel centres are at index + 0.5).
The readout evaluates one detector ray per mouse event, without full image arrays.

Selecting a position row opens its middle observed frame and marks the spot with
a hollow magenta ring outlined in black, above the other overlays. The ring
follows the selected track's per-frame measured x/y positions while browsing,
and hides on frames without an observation. Selection clearing and invalidation
remove it. Selecting a spot outside the current view recentres without changing
the zoom. The same marker is available for single-frame spot measurements.
Clicking a detected spot in the image selects and scrolls to its linked row in
the Positions tab while retaining the current frame. Detected spots take click
priority over predictions. Unlinked live-search preview markers become selectable
after the final positions table is available.

The Positions tab shows a compact selected-spot panel: selected cell/model,
indexing status, assigned conventional hkl, and Δxy/Δx/Δy (pixels) plus Δω
(degrees). Residuals are calculated minus the signal-weighted linked-spot
centroid, matching positional refinement, not the current frame midpoint.
Changing the selected cell updates these diagnostics
even when prediction overlays are hidden. Inspection reads existing frozen
assignments and uses PhaseSmith's existing spot predictor; it performs no
refitting, reassignment, or ranking changes. “Indexed” means inclusion in that
cell snapshot's accepted indexed/fit population, not a fresh fit-quality test.
Tracks filtered out before cell searching show “Not assessed”, rather than “No”.
Unassigned tracks have no assigned hkl/residual; invalid predicted crossings
retain the assignment but explicitly lack a detector residual.
The observed-frame dropdown lists every actual observation with its series
frame, original file number and omega exposure bounds. Choosing an entry opens
that frame without changing the spot selection; missing observations are not
filled in from a first/last-frame range.

“Find lattices and rank cells” runs lattice discovery and then automatically
compares primitive/Bravais settings of the default passing lattice, opening the
ranked list and its selected preview. Selecting another passing lattice from the
candidate list automatically replaces the ranked list and predictions. Rapid
selection changes coalesce to the latest lattice while a comparison is running;
results belonging to previous selections are discarded. No separate comparison
button is required. A failed lattice search remains visible for diagnosis without automatic
cell comparison. These are two processing stages within one user action; the
ranked settings are not a list of independently detected grains.

The experimental sidebar has separate Series, Detection, Cell and
Positions tabs. All six residual plots share pattern-style
controls: left-drag rectangle zoom, right/Ctrl-left drag pan, right/Ctrl-left click
zoom out, double right/Ctrl-left click reset, and wheel zoom bounded by the data
extent. Bounds include all plotted populations, excluding reference lines.

The retained programmatic orthorhombic refinement API searches integer lattice
axes within 0.3° of perpendicular and performs a constrained three-length plus
three-orientation fit. Settings retain their integer change of basis, lattice
index and P/A/B/C/I/F translations; conventional-cell predictions retain the
original reciprocal-lattice selection. The training/held-out split, assignments
and instrument remain fixed. A metric candidate is not a proven primitive lattice,
intensity symmetry or space group. Exports preserve the transform, search bounds,
both models and held-out residuals. These legacy fitting APIs remain available
for numerical diagnostics; their controls are absent from the sidebar.


### macOS file-dialog fallback

The experimental mode uses Qt widget file dialogs on macOS for every open/save/
directory action, including actions outside its own tab. This process-local
application flag avoids a reproduced native AppKit open/save panel initialization
stall; a minimal native panel remained blocked in `NSSavePanel._initBridgeAndStuff`,
while a Qt panel opened the same measured-data folder in about 0.06 seconds.
Shared file helpers also disable custom directory-icon lookup. The behavior is
unchanged by default on Windows/Linux, and no system services or saved settings
are modified. `DIOPTAS_QT_FILE_DIALOGS=1` explicitly enables the same fallback for
ordinary mode in this checkout. See [Qt file-dialog options](https://doc.qt.io/qt-6/qfiledialog.html#Option-enum).


### Live peak-search preview

During series detection, **Follow search** displays the latest completed frame
with its spot candidates, filename, frame count and omega range. Marker centres
remain yellow (unflagged) or red (flagged), with a two-pixel black outline and a
fixed screen size so they remain visible over bright image features.

The worker supplies immutable images/detections after each frame. A GUI timer
updates at most ten times per second and retains only the newest pending frame;
fast searches may skip intermediate previews. Image data are not queued per frame,
re-read for preview, or loaded into the shared model while the search runs.
Preview uses the current contrast and image view. Uncheck Follow search or browse
manually to inspect a frame without stopping processing; recheck it to catch up.

These frame detections precede cross-frame linking. The status explains when all
frames are complete and linking begins. Final tracks replace the provisional
markers when the job finishes, and the shared model is synchronized to the shown
frame once. Source/settings changes and closing the window discard stale previews.
The observer does not change detection, track values, flags or source hashes.


See PhaseSmith's `docs/experimental-grain-search.md` for FFT grain search equations,
ambiguity rules, strict distance boundaries, reserved-data gates, computational
budgets and provenance. This remains in the experimental branch and opt-in native
feature; standard releases and dependencies are unchanged.

## Ranked cell settings and direct selection

**Find lattices and rank cells** automatically compares settings of the selected
passing lattice; choosing a different lattice repeats the comparison. PhaseSmith compares primitive hypotheses and
all 14 Bravais types using measured positions and the inferred lattice, with no
known material, cell, saved UB or reference indexing. This uses the
`f166525af743bcfa63c6e132101730d907b5927d` experimental backend or a compatible
newer build; the experimental CI pins this exact revision on Windows/macOS/Linux.

The **Cell** section shows **Lattice candidates** above **Ranked cell settings**
in a vertical splitter, with both selections visible and independent table
scrolling. Drag the divider to adjust their space. The lower table's heading
identifies its selected lattice/axis. The ranked view shows rank, Bravais
symbol, edges, α/β/γ angles and training-score difference. **Full ranked table** opens a
non-modal sortable table with angles, volume, training/held-out xy and omega
residuals, symmetry order and fit status. It shares the sidebar selection. Point
symmetry does not increase just because a conventional cell is centred.

Clicking a row immediately queues predictions for **that fitted setting**. It
performs no new refinement or ranking. The selected-cell overlays,
residual plots and exports use that row's stable PhaseSmith fit-pool index and
integer lattice transformation; centred conventional predictions retain the
primitive-lattice restriction. The selected fitted model stays visible even if
its held-out residual is worse; both metrics remain in the plots and exports.
Selecting an invalid fit explains the problem rather than substituting another cell.

Higher lattice symmetry comes first among finite fits within the declared
training-score window (default delta <=10 on one fixed reflection population).
Less comparable fits remain selectable for inspection. This is a provisional
proposal ranking, not a space-group probability or proof of physical primitivity.
Changing the selected lattice clears its ranked settings. Source/mask/parameter
changes invalidate ranks and overlays. Rapid row changes coalesce to the latest
selection; stale predictions cannot replace that cell's overlay. All numerical
work remains in the existing dedicated background worker.

**Export ranked cells** saves all ranks, fixed fits, geometry, comparison options
and the retained/excluded support of every primitive hypothesis, including rejected
ones. Predictions and residuals for the current row can be exported through
**Cell**. Existing plot mouse controls and frame buttons are unchanged.

## 3D reciprocal-space explorer

**Reciprocal space…** in Cell opens a non-modal, rotatable 3D point cloud for
the selected ranked cell. It follows cell/lattice selections and clears when
the source is invalidated. Drag left to rotate, wheel to zoom, right/Ctrl-drag
to pan, and double-click to reset. Buttons orient the camera along hk, hl or kl
planes. Markers grow gently with zoom (at most 1.8× their initial pixel diameter),
with a matching increase in click tolerance to keep magnified spots selectable.
The compact **Point size** slider adjusts their diameter from 50% to 250%
of the default, independently of camera position; it retains the zoom scaling.
These are camera presets in the same 3D viewer. The default Cartesian
q coordinates use equal physical units, in Å⁻¹ with `|q|=1/d`.
Markers are shaded spheres. **Perspective** is on by default: a camera three
cloud radii in front of the pivot projects both point positions and marker
diameters with the factor `3r / (3r - z)`. Nearer spheres appear larger; marker
size indicates camera depth, not measured intensity. Turning Perspective off
restores orthographic projection and equal marker diameters. Hit targets and
selection rings follow the projected sphere sizes in both modes.
Hovering a sphere shows a compact tooltip beside the cursor with its spot/frame,
indexing status and the selected cell's frozen integer hkl assignment. It hides
when leaving the ball/view, dragging, zooming or replacing the cell data. The
bottom readout also retains the plotted coordinates. Unindexed and
excluded/unassessed tracks have no displayed hkl assignment. Fractional plotted
coordinates remain unrounded and are labelled separately from assigned hkl.
Fractional-index mode shows unrounded h/k/l; its axis lengths and angles are
coordinate units rather than physical reciprocal distances.

PhaseSmith's native `reciprocal_vectors` owns detector/omega conversion.
The display adapter expresses q in the selected fitted reciprocal basis B using
`q = h B`, without rounding h or reassigning reflections. Linked-centre mode
uses original signal-weighted x/y/omega centres, matching cell comparison;
individual-observation mode converts every original frame observation separately.
Nonfinite centres are omitted and counted. Indexed (cyan), unassigned (orange)
and excluded/unassessed (grey) colours retain the same frozen assignment/eligible
population as selected-spot details. Each population can be hidden independently.
Reference lattice planes mark integer indices, not allowed/predicted reflections;
empty nodes do not establish systematic absences or a smaller cell.

Clicking a point selects its original track, scrolls to its Positions row and
highlights the detector spot. An individual observation also opens its exact
frame. When spheres overlap, clicking selects the frontmost sphere under the
cursor. In empty space the padded click targets prefer the nearest centre,
then frontmost for near ties. Table/image selections highlight the same track in magenta.
**Centre selected** moves the rotation pivot to that spot. **Slices…** opens an
optional three-panel hk/hl/kl inspection tool, with adjustable normal-coordinate
centres and full slab thickness. Both boundaries are included:
`abs(normal - centre) <= thickness / 2`. Slice mouse gestures match the pattern
plots, and grids are excluded from zoom bounds. This is a measured-position
viewer, not an intensity reconstruction or diffuse-scattering volume.

The 3D view uses Qt's CPU raster painter, without an
OpenGL requirement or additional GPU library. Cached sphere sprites are drawn
in exact back-to-front order (stable input order for equal depths). Coordinate
conversion, projection and picking are O(N); sorting for rendering is
O(N log N), and storage is O(N). Reference guide segments crossing the camera's
near plane are omitted.
The cloud (and each optional slice) displays at most 50,000 points with
deterministic evenly spaced sampling and reports shown/total counts. Large
clouds may lose small features when capped. The experimental CI runs on Windows,
macOS and Linux; local interactive review is on macOS.

Local P1 validation (2026-10-25) used its archived measured position table and
re-ran the blind FFT lattice search before ranking; no known cell/material was
supplied. All five settings were selected in an offscreen real-frame review and
matched their exact stored PhaseSmith fit matrices. At frame 39/76 their predicted
visible spots numbered 24/23/24/24/23 (ranks 1..5). The local review and captures
are under `PhaseSmith/runs/p1-dioptas-ranked-20261025/`; it leaves oP rank 1
selected. The larger-cell question and provisional symmetry limitations remain.
