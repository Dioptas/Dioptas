# Single Crystal XRD

SCXRD sits below Map in the left mode bar. Its frames, geometry, processing and
history are independent of powder Integration/Calibration/Map. The production
worker is Rust over Tauri-owned stdio; no interpreter or scientific server is
required. Task controls stay on the right; detector navigation uses the shared
Dioptas gestures and square, full-resolution detector pixels.

## Starting a protocol

1. **Frames:** load a contiguous numbered image sequence or a supported
   multi-frame detector file. Review order with the frame arrows, direct entry
   and scan-order disclosure. Page Up/Down steps outside text fields. Angles
   are declared, not inferred from file names. Reverse/nonuniform scans require
   preparation with a supported acquisition model.
2. Select **PhaseSmith protocol** (the default). **Load protocol…** accepts a
   supported PhaseSmith JSON document; **Use bundled v29** loads the unchanged
   supplied-symmetry example. Inspect the full document. Review first/last
   frames (one-based in the UI), exposure start/step/width, spindle axis,
   overload threshold and cell-shadow assumptions. Example angles and the 35°
   DAC opening are declared assumptions, not detector metadata.
3. Load an affine `.poni` calibration, or copy the current powder calibration.
   Check pixel size, wavelength and geometry for this detector. Unsupported
   distortion/spline/orientation overrides are rejected. The SC copy remains
   independent of subsequent powder edits.
4. The **Sample setup** block in Frames links to every required prior editor.
   Before processing, supply the orthorhombic cell in **Geometry**, the supplied
   space-group number in **Scaling**, and element symbols in **Structure**.
   These lengths are editable before indexing; incompatible angles carried from
   exploration have an explicit clear/re-enter action.
   Atom counts, atomic coordinates and reference intensities are not required.
   Review seat/illumination and DAC-axis/opening controls in **Background**.
   Return to Frames, confirm acquisition/shadow assumptions and Apply settings.
5. Run one stage at a time, or **Run to next decision** for dependent processing
   and the optional bounded structure search. The native coordinator owns all
   checkpoints: moving masks; original-count detection/linking; indexing and
   pose/orientation refinement with family holdout; predicted-crossing profile
   integration and family scaling. Indexing/geometry complete together, as do
   integration/scaling. A checkpoint can therefore complete the next tab.
6. Inspect observed/predicted positions, signed intensities, quality flags,
   eligibility and merging statistics. The observation table filters all,
   usable or excluded observations across the whole reduction and paginates that
   selection. This changes only the view. Expand a quality summary for every
   decoded reason and its raw flags. Native support/correction settings are in
   the collapsible details above the table. The native policy retains MISMATCH
   warnings where upstream permits them; nonzero flags do not all mean excluded.
   Detected-track and predicted-crossing identities are distinct. Rint measures
   repeated-family agreement; structural R1 is a different statistic.
7. **Export:** save the recipe, full-precision observation table, usable HKLF4
   intensities and, when available, candidate CIF. Native candidate CIFs include
   available anisotropic tensors. A recovered candidate is not a final validated
   crystallographic refinement.

Protocol numerical controls are checked against the versioned native
implementation. Frozen fields are read-only. Unsupported changes, unknown
controls and automatic-symmetry protocols fail explicitly. Current support is
the supplied-symmetry orthorhombic v1 family, including v29, for 5–225 contiguous
selected frames and original uint32-compatible counts. The profile recipe uses
both moving mask providers, original-count guarded-plane background, independent
3D profile learning, shape fitting, physical corrections, robust
frame/detector/ray family scaling and its equivalent-error model. It performs no
absorption correction. The upstream geometry, teacher and usable-observation
gates are enforced. Reference-coordinate/count grading in the example document
requires an independent reference and is not run by Dioptas.

## Repeating, inspecting and correcting work

**Save effective protocol…** records acquisition/shadow overrides, execution
controls and search budgets. **Inspect protocol** shows this backend-generated,
applied effective document. Unapplied drafts are labelled; apply them to refresh
inspection. Default protocol sessions expose the same first/last-frame controls
without requiring an explicit template import. Entering protocol mode applies
its declared interval; inconsistent selections are rejected. It refuses exclusions or selections the protocol
cannot represent. A **Dioptas recipe** additionally records source paths/hashes,
calibration, sample priors, masks, choices, settings and engine/adapter identity.
Open recipe verifies decoded counts and rebuilds results from retained inputs.
Absolute source paths must still exist. Protocol recipes rebuild native stages;
legacy v1 recipes with no workflow field retain exploratory-summation semantics.
**Apply recipe settings…** transfers parameters to another measurement while
retaining its frames, calibration, masks and frame exclusions; review and confirm
the new acquisition before processing.

Enable **Keep lossless intermediate stage outputs** before running to retain an
exportable NPZ audit of masks, positions, indices, geometry, original shoebox
samples/backgrounds/variances, teacher membership, profile bank, physical and
empirical factors, intensities and eligibility. This costs memory and temporary
storage. Export saves a durable copy; a recipe alone does not contain these
arrays. Host-owned decoding/cache execution is separate from the frozen
scientific protocol. Earlier stages are rebuilt at checkpoints because the
public coordinator does not expose resumable internal workspaces.

Numbers commit on Enter or blur. Invalid/unapplied drafts block processing;
Reset draft restores applied values. Mode switches preserve drafts and viewport.
SC Undo/Redo (Ctrl/Cmd Z, Shift Z or Y) retains three scientific edit snapshots,
independent of powder history. Undoing a clear/settings edit can restore its
previous reduction and candidate after Stop. Running a processing stage itself
does not create an undo entry. Settings and
stage clearing invalidate dependent products. Stop keeps completed checkpoints
and settings; an interrupted native checkpoint commits no partial results. Stop
is cooperative and may wait for a bounded tile/frame/kernel. Rerun to resume.

The protocol currently rejects manual detector rectangles, track exclusions and
interior omitted frames rather than silently ignoring them. Inspect a problem,
correct acquisition/calibration/shadow settings or use a contiguous frame range,
then rerun. Native exclusion flags are decoded to readable reasons; their raw
bits remain in tooltips and exports. A Stop control is available inside the task
panel as well as in the global status bar. Use the exploratory path when manual exclusions are needed. Source
files, HDF5 companions and loaded calibration files are protected from export
overwrites. Output writes are atomic. HKLF4 uses a common scale where needed;
use the full-precision table if its field widths cannot preserve nonzero sigma.

## Exploratory summation

Select **Exploratory measured-track summation** for flexible peak/background
controls, optional omega arPLS baseline, blind primitive-cell exploration, manual
frame/track/rectangle exclusions, fixed or refined geometry and measured-track
summation. Background-subtracted images assist spotting; integration and
counting variance use original counts. Each image has its own histogram.
Optional robust log-linear omega scaling requires repeated families. Explicit
isotropic/anisotropic candidate search and export remain available. Its candidate
CIF exports Ueq only. This path does not implement native profile/family scaling
and must not be described as the complete PhaseSmith protocol.

## Validation boundary

The matched MgSiO3 replay reproduces standalone masks through reduction; see the
[comparison](SCXRD_RINT_COMPARISON.md) and [validation record](SCXRD_VALIDATION.md).
This exposed dataset does not establish general instrument accuracy, automatic
Bravais/space-group identification, completeness, multi-lattice separation,
absorption correction or final structure-refinement support. The exploratory
path has a 10,000-frame and 16 GiB scratch admission cap; blind indexing samples
at most 10,000 positions deterministically. Hashes establish decoded-count
identity, not calibration validity. Time-limited searches can stop at different
iterations across builds/hardware/load: retain actual results and termination.
