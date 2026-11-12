# Single Crystal XRD

SCXRD sits below Map in the left mode bar. Its detector, frame series, geometry,
processing products, contrast settings and edit history are separate from powder
Integration. The right panel follows nine stages; the action at its bottom stays
reachable while controls scroll. All processing uses the Rust stdio worker and
pinned native PhaseSmith kernels. No Python environment or server is required.

## First measurement

1. **Frames:** load a contiguous numbered image sequence or a supported
   multi-frame detector file. Check the order using the frame arrows, direct
   frame entry and spot-count plot. Page Up/Down steps through frames outside
   text fields. Supply the first exposure start, positive step, exposure width,
   spindle axis, photons/count gain, read noise and overload threshold. Confirm
   the acquisition checkbox and Apply settings. Angles are declared by the user,
   not inferred from file names. Reverse/nonuniform scans must be reordered or
   prepared with their correct acquisition model before admission.
2. Load an affine `.poni` calibration, or copy the current powder calibration.
   Verify its pixel size, wavelength and geometry against this detector. Shape
   and binning are checked; unsupported distortion/spline/orientation overrides
   are rejected. The SC copy is independent of subsequent powder edits.
3. **Background:** optionally prepare an omega arPLS baseline. This supports
   spotting and centroids. Measured intensities and counting variance always
   come from original detector counts. Compare Original, Background and
   Subtracted images using their separate histogram settings.
4. **Peaks:** detect and link spots across exposures. Select a track to inspect
   its frame; show observed/predicted/flagged markers. Exclude a bad track with
   its explicit checkbox, exclude a frame, or draw rectangular detector masks.
   Mask picking shows a preview; Escape cancels an unfinished rectangle.
5. **Cell:** blind search ranks reduced primitive lattices. Inspect support and
   withheld residuals; select the sample cell when choices are ambiguous.
   Diamond-like lattices require a decision. Candidates are not automatic
   Bravais-lattice or space-group determinations.
6. **Geometry:** keep calibration fixed, or explicitly request detector-pose and
   crystal-orientation refinement. A supplied metric must use the selected row
   setting. Acceptance checks convergence, parameter identifiability/bounds and
   improvement on withheld spots. Cell lengths and wavelength are fixed in this
   fit. Review observed/predicted positions before integrating.
7. **Intensities:** choose spatial and rocking apertures; integrate original
   counts with a local background, counting uncertainty, Lorentz and
   polarization corrections. The polarization vector follows lab fast/y.
   Signed intensities and flagged observations remain visible. Partial,
   overloaded, overlapping or poorly predicted observations are not silently
   promoted to usable reflections.
8. **Scaling:** supply a space-group number, inspect equivalent-family merging,
   Rint, available CC½ and systematic-absence evidence. An optional robust omega
   scale requires repeated families. Its conditional intensity sigmas and scale
   variance are distinct. This is not an absorption correction.
9. **Structure:** optionally enter element symbols and a supplied space group
   for a bounded native candidate search. Select isotropic or anisotropic ADPs
   explicitly. R1, parameter count, termination and candidate assessment are
   diagnostic; this is not a final validated refinement. **Export:** save the
   recipe, full-precision signed observation table, usable HKLF4 intensities,
   and an available candidate CIF.

**Run to next decision** performs the dependent stages, pausing at failed checks
or ambiguous cell choices. Without element symbols it stops after scaling and
offers Review and export. With elements it also runs the optional search. Every
stage can be visited and rerun. Applying changed settings invalidates dependent
products; a rerun never silently reuses stale intensities. Stop processing keeps
completed stages and current settings; rerun the interrupted stage to continue.
Large scans may stop between bounded tiles/frames rather than instantaneously.

## Repeating and correcting work

Numbers commit on Enter or blur. Invalid or unapplied drafts block processing
with an explanation; Reset draft restores applied settings. Mode switches keep
drafts and detector viewport. SC Undo/Redo (also Ctrl/Cmd Z, Shift Z or Y) keeps
three scientific edit snapshots independently of powder history. Processing is
not an undoable edit; rerun from retained inputs instead.

Save recipe writes `.scxrd.json`, including source hashes, acquisition,
calibration, masks, exclusions, choices, applied parameters and engine/adapter
identity. It does not save unapplied drafts or every intermediate array.
**Open recipe** verifies the original decoded counts and rebuilds peaks/cell
choices; run remaining stages again. Absolute source paths must still exist. The search seed and budget are recorded,
but a wall-clock-limited structure search can stop at different iterations on
different hardware or system load; retain its actual output and termination.
**Apply recipe settings** transfers processing parameters to the currently
loaded measurement while retaining its frames, calibration, masks and excluded
frames. Computed choices are cleared and acquisition must be confirmed again.
This is the starting point for a reproducible series of different measurements.

Source detector files, HDF5 companions and loaded calibration files are protected
from export overwrites. Recipe and table writes are atomic. HKLF4 has a common
scale when necessary and rejects values that cannot retain nonzero sigma within
its field widths; use the full-precision table in that case. The candidate CIF
contains P1 full-cell coordinates and per-atom Ueq, **not anisotropic tensors**.
It does not reproduce an anisotropic candidate's complete refinement model.

## Supported scope

This first native adapter provides a complete operable path from admitted frames
through summation intensities, supplied-symmetry assessment, optional candidate
search and export. It does not yet provide profile fitting, automatic Bravais or
space-group selection, completeness, absorption/DAC corrections, multi-lattice
separation, recipe source relinking or a final crystallographic refinement UI.
A 10,000-frame and 16 GiB raw-plus-baseline scratch admission cap prevents
unbounded work. Blind indexing samples at most 10,000 positions deterministically.
Source hashes identify decoded counts, not instrument calibration validity.

See [validation](SCXRD_VALIDATION.md) for measured limitations and reproducible
checks. In development only, hot worker replacement refuses to discard a loaded
SC session: save its recipe, restart and reopen. The production worker does not
use that development handoff.
