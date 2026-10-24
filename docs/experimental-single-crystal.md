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
process workers or DIALS dependencies. PhaseSmith runs one native numerical
thread outside the interpreter lock. Dioptas queues one job at a time and
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

No profile fitting, deblending, frame linking, lattice/grain indexing,
partiality correction, absorption/geometry correction, scaling, merging or
structure solution is implemented. The background is a local constant mean.
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
quality. Selecting a row plots its detected x/y trajectory against omega and
shows a frame from that candidate. Frame browsing preserves results; changing
mask, orientation, configuration or detection settings invalidates them. Work
runs in the existing single-worker queue, reports frame progress and discards
stale results. Only one detector image is read at a time.

Position export writes a track CSV, an observations CSV with every source frame,
and a JSON provenance sidecar. It has no integrated-intensity column. Detector
sums are internal centroid weights only; exposure midpoints limit omega
resolution. Ambiguous many-to-one links and scan-boundary candidates are flagged.
This mode does not yet transform positions to reciprocal space, find a unit cell
or assign symmetry/HKL. Rocking-curve integration follows indexing later.

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
