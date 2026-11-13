# Native feature status

> Moved from the former desktop README (now `DEVELOPMENT.md`). Source paths and commands are relative to the repository root.

The image dialogs in Calibration, Integration, Map, Batch and Single Crystal XRD,
including image background, flat-field and transfer correction selection, show
the same supported image extensions. These include NumPy `.npy`, TIFF/MAR,
EDF/CBF, HDF5, Oxford/R-AXIS/HiPiC/ADSC `.img`, Bruker, KCD/MPA/SPE,
Esperanto `.esperanto`/`.esper`, MRC/DM3, FIT2D `.f2d`, grayscale PNM and XSD XML.
Gzip (`.gz`) and bzip2 (`.bz2`) files are also visible. Folder scanning requires a
known image extension before the compression suffix, such as `.edf.gz` or
`.esper.bz2`, and skips hidden files. File contents still determine the reader;
an extension does not override format, shape or data validation. Select **All
files** for supported detector files with other names. JPEG, JPEG 2000 and NumPy
`.npz` archives are not enabled in this application.

The development branch is `develop`, promoted from `codex/rust-desktop` on
November 11, 2026. The former Qt `develop` is preserved on `legacy/qt`, and
existing stable releases remain Qt applications. New desktop work targets
`develop`; the former single-crystal experiment stays separate. The new native
[SCXRD workflow](../architecture/SCXRD_WORKFLOW.md) provides guided frame-to-export processing;
see its [validation and limitations](../parity/SCXRD_VALIDATION.md). Versioned PhaseSmith
protocols support inspection, effective-settings export, native checkpoints and
lossless stage audits; the [matched MgSiO3 comparison](../history/SCXRD_RINT_COMPARISON.md)
documents the corrected profile/scaling reduction and its supported scope. See the
[consolidation record](../history/RUST_DESKTOP_CONSOLIDATION.md) for branch history and
verification.

The desktop uses Dioptrin **0.12.0** plus the Massif, cached compatibility
and resident-layout/dynamic-worker/typed-CSR optimizations at revision `0c0d4fc`, locked in `Cargo.lock`. It includes native
pyFAI-compatible full pixel splitting for both 1D patterns and cakes. Massif
picking retains full-resolution samples and reuses preprocessing across clicks;
see [Massif performance and numerical checks](../performance/MASSIF_PERFORMANCE.md) and
[cached integration measurements](../performance/PYFAI_CACHED_PERFORMANCE.md).
Settings → Integration also exposes bin-oriented CSR (the default),
pixel-oriented CSC and optional automatic size-based selection for resident 1D patterns.
See the [detector/bin crossover study and predictor](../performance/INTEGRATION_LAYOUT_CROSSOVER.md).

The default [Rust backend](../../backend/README.md) runs the
image → peak picking/fitting or loaded/manual geometry → integration workflow without Python, using
`dioptrin-io` and Dioptrin. `npm run tauri:dev`, `launch.command` and
embedded Tauri builds select Rust without a Python environment. Build hooks
compile and stage the matching native processor automatically.
See [reference data and cleanup](../architecture/REFERENCE_DATA.md) for the Python-free test
policy and retained fixtures. `npm run tauri:native-dev` retains its isolated port 1428.
The native calibration stage retains the existing controls, automatic ring
refinement, live progress/cancellation and grouped edit/fit Undo/Redo for the
[qualified detector geometry](../parity/NATIVE_DETECTOR_PARITY.md).
All three bundled masking plugins also run natively, including their settings,
dynamic recomputation, imprint and Undo/Redo. The native integration stage adds
warm-plan reuse and combined HDF5 loading, corrections/backgrounds, pattern and
overlay I/O, phase/material editing, Batch and Map with the existing controls.
Admitted fixed-mask HDF5 Batch/Map series use concurrent frames with one shared
CSC plan and persistent worker scratch. Development builds also optimize the
separate Bitshuffle/LZ4 C dependency. See [series pipeline measurements](../performance/NATIVE_SERIES_PIPELINE.md).
Corrected images and dynamic masks use shared native `Dynamic1dPlan` snapshots
and private reusable frame workers, including propagated pixel variances; see
[processed-series qualification](../performance/NATIVE_PROCESSED_SERIES_PIPELINE.md).
Spot and Cosmic masks use compact row workspaces and shared Spot bin membership;
see the [full-series spatial-mask profile and benchmark](../performance/NATIVE_SPATIAL_MASK_PERFORMANCE.md).
The integration status line reports measured images/s during Batch/Map loading.
See [native GUI Eiger timings](../performance/NATIVE_GUI_SERIES_PERFORMANCE.md) for first/repeated
loads, bin counts and Poisson errors. pyFAI-compatible Batch/Map now also use
[shared plans and persistent frame workers](../performance/NATIVE_PYFAI_SERIES_PIPELINE.md).
Raw fixed-mask compatibility integration reads decoder pixels directly while
preserving float64 result bits; see the [profile and matched polygon comparison](../performance/NATIVE_PYFAI_SERIES_THROUGHPUT.md).
Single-image compatibility integration also reads integer pixels directly,
parallelizing independent radial bins with identical results; see the
[single-image loading and integration comparison](../performance/NATIVE_PYFAI_SINGLE_IMAGE_PERFORMANCE.md).
Display preparation now batches repeated detector sentinel counts, and aligned
binary rasters reach the GPU through packet views. Detector textures and pattern
buffers reuse storage between frames. See the [actual native GUI profile and
loading/navigation comparison](../performance/NATIVE_DISPLAY_TRANSFER_PERFORMANCE.md).
See the [qualification ledger](../parity/NATIVE_INTEGRATION_PARITY.md) for measured parity,
benchmark scope and remaining detector work. Native format-2 `.dio` persistence
and configuration select/add/duplicate/rename/remove controls are now available;
see [project compatibility and verification](../parity/NATIVE_PROJECT_PARITY.md).
On ordinary native startup, Dioptas offers **Restore** or **Start fresh** when
an automatic session checkpoint exists. Normal close saves a separate atomic
checkpoint, and a changed session is backed up every ten minutes. Explicit
startup files take priority. See [session recovery](../architecture/SESSION_RECOVERY.md) for
storage, preserved state, failure behavior and verification.
Recovery includes bounded undo/redo history in a separate companion file;
ordinary saved `.dio` projects remain history-free.
The configuration bar is hidden by default. Enable **Settings → Configurations → Enable configurations** to use it, or press **Shift+C** in the workspace to toggle configurations. The shortcut pauses in text fields, menus, dialogs and Settings. This preference is remembered across restarts. Switching it off hides the toolbar
and disables combined patterns/cakes while retaining all configurations and the
active selection. Opening a project with active combination enables the toolbar.
The next stage adds [native rotations/flips and geometric masks](../parity/NATIVE_GEOMETRY_MASK_PARITY.md)
through the existing controls, including per-configuration persistence and history.
The separate [LA Cosmic action](../parity/NATIVE_LACOSMIC_PARITY.md) is now native as well,
with Cosmic Removal in the Mask panel, two passes, Undo/Redo and cancellation.

HDF5 files expose an **Image source** selector in Calibration → Image and
Integration → Image. It lists supported scalar planes/stacks with frame counts
and dimensions. Switching retains the current frame, clamped to a shorter source,
and updates the image and integrated results together. Recognized Eiger/LImA/Lambda
formats retain their automatic series option. Selected sources belong to each
configuration and survive native project save/reopen. See [HDF5 source selection](../parity/HDF5_SOURCE_PARITY.md).

For multi-frame images, **Integration → Image** also offers previous/next frame
arrows, a separate **Frame step**, and direct one-based frame entry. Frame steps
stop at the first/last frame of the current file or selected HDF5 source;
rapid clicks are processed in order. The frame step is independent of File step.
File arrows beside Load image move directly between files using File step and Name/Time,
opening frame 1 of each destination even when the current file has more frames.
Page Up / Page Down (Fn+↑ / Fn+↓ on a Mac) perform the same file navigation
in Calibration and Integration, using File step in Integration. Shortcuts pause
in fields, menus, dialogs and Settings. Unmodified arrows retain plot navigation.
Image and Pattern share the same neutral Load/Folder buttons and aligned file
browser: Load, arrows, Step and Browse by above the filename and Folder action.
Pattern retains its editable input/autocreate output folder, with Autocreate and
format choices grouped below the browser. Long filenames retain their useful
counter and extension while remaining fully editable.
The Image tab uses aligned File, Source and Frame rows. **Folder…** beside the
filename selects the input folder without a permanent directory field.
Autoprocess shows **Watching:** with the processor's confirmed folder; opening a
reference image elsewhere keeps that watcher fixed until Folder… changes it.
Source selection uses short, distinct dataset labels; the full selected path is
available on hover and in **File Info**. A sole source is shown as passive text,
and the Frame row is hidden for single images. Folder status and dimensions share
one compact line. The splitter stays fixed across Integration tabs. The chevron at the right of the
tab strip temporarily collapses or restores the task panel. Narrow task panels use
one tab group, arranged in one row or two balanced rows without a horizontal
scrollbar. At 900 px of task-panel width, Image/Pattern/Background/Corrections
remain on the left and Overlay/Phase form an independent tab group on the right.
Above 1400 px, Overlay and Phase each have their own column. These Qt thresholds
scale with the interface text size. Each group retains its selection; resizing
preserves control drafts and mounted plots. Selecting any tab,
including the selected tab, opens its controls at the previous panel height.
Collapse does not change the image/pattern split or the expanded default on a
fresh app session. File order
and Batch mode use compact dropdowns. File and frame arrows use 32 × 30 px targets
at both text sizes, with each step field directly beside its browsing controls.

Changing source dimensions **without a calibration** shows the old/new sizes
and asks before opening. **Open image** resets orientation, mask, picked coordinates
and ROI; it does not reset a calibration. Experiment/fit
preferences, integration settings and correction drafts remain available.
An incompatible remembered detector is replaced by image detection; background,
flat and transfer references with incompatible dimensions are discarded.

With a calibration loaded, a size change asks before replacing the image.
**Open and reset calibration** clears detector geometry and image-dependent
processing, keeping the current workspace/tab, phases and overlays. When the
geometry accepts the new dimensions, **Open with current calibration** keeps
that calibration and resets image coordinates. This explicit choice also
supports legacy PONIs without dimensions and manufacturer-supported binning.
Same-size images retain their calibration; changing physical detectors with
identical dimensions still needs an explicit calibration change or reset.

Either loading order works when switching detectors. Loading an incompatible
PONI offers **Load calibration and clear image**: the new calibration stays
loaded while the old image and its products are removed. Then open the matching
image. A project can save/reopen this calibration-only state without the old
source files. Cancel/Escape preserve the preceding session. **Reset calibration**
beside Load .poni still resets the detector while retaining the current image.
Autoprocess stops on an unresolved calibrated size mismatch.

With configuration controls enabled, the top bar provides detector factors,
**Combine patterns**, **Combined cake** (calibrated 2D cakes), and combined-pattern
export across modes. Configuration file/folder arrows always browse all
configurations; the Image panel's arrows browse the active detector. Configure
filename/folder number positions, step sizes and linked filename changes in **Settings → Configurations → Configuration browsing**. The MEC preset supplies the Qt convention;
all rules remain customizable and persist across restarts. See
[detector combination and browsing](../parity/DETECTOR_COMBINATION_PARITY.md).
Combined patterns and cakes run through
Dioptrin's native shared-grid integration, with independent images, masks and
display preferences for each configuration. Combination needs calibrated images
and solid-angle correction. Combined counting errors use independent pixel variances propagated through
backgrounds, detector factors and image corrections. See the
[correction and uncertainty ledger](../parity/NATIVE_CORRECTION_UNCERTAINTY_PARITY.md)
for transfer/plate/slab controls, project ownership, full data-flow tests and
statistical assumptions. Cylinder, sphere and optional capillary-wall absorption are
also native; see the [round-sample qualification](../parity/NATIVE_ROUND_SAMPLE_CORRECTION_PARITY.md)
for their footprint models and legacy-project recalculation notice.
Correction [Plot / Back previews](../parity/NATIVE_CORRECTION_PREVIEW_PARITY.md) show the actual
native divisor map with independent display controls and restore the preceding
image or Cake view.

The pattern **2θ** and **Q** buttons also select the cake radial display axis,
without rebinning its scientific pixels or changing the zoomed interval. A cake
retains its own source unit, including combined Q cakes. Selecting d leaves the
last cake axis selected; missing wavelength uses an explicit source-unit fallback.
See [cake axis qualification](../parity/CAKE_Q_AXIS_PARITY.md) for coordinate and export semantics.

Integration's **Profile** toggle shows the native azimuthal profile to the left
of the cake, with intensity horizontally and a shared vertical azimuth axis.
It appears only in Cake view at the linked detector/cake/pattern radial position.
**Width (bins)** controls the
fractional radial average; its save icon exports azimuth in degrees and intensity
through the native chooser. Turning Profile on from Image switches to Cake;
Image mode hides the profile.
Drag the small divider to change the profile width (double-click resets it).
The shared azimuth labels are on the far left; an axis-started left drag can
select a zoom region in the profile or continue into the cake.
See [azimuthal-profile semantics and checks](../parity/CAKE_PROFILE_PARITY.md).

Integration and Map use the same `RasterView` and `PatternView` renderers.
`diffractionPlotSetup.ts` prepares their common detector mask/click properties
and pattern colors, visibility, phase references, overlay legends, linked radial
position and click sampling. Each mode supplies its own display data and tools;
Map ROI editing, Integration background inspection, independent image levels
and per-mode plot preferences remain with their existing owners. The detector's corner Undock icon opens a standalone image window while the
main task controls and plots keep working. Show detector window reuses it;
Dock or its close button returns the view with images, calibration, contrast
and zoom retained. See [detector-window behavior and evidence](../parity/DETECTOR_WINDOW_PARITY.md).
Detector zoom
and pan are shared across Calibration, Mask, Integration and Map during the
session. Pattern ranges are shared across Calibration, Integration and Map,
converting radial units and intensity scales as needed. Resizing keeps detector
pixels square; F/right double-click still restore the fitted image view.
