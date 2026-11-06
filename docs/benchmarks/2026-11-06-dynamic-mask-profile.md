# Qt Dioptas dynamic-mask profile and copy removal

Measured 2026-11-06, using published Dioptrin 0.8.0. This profile follows the
[mask-mode dispatch work](2026-11-06-dioptrin-mask-modes.md). Its timings supersede
the earlier diagnostic for the optimized per-frame Qt path.

## Findings and changes

Mask creation was not the main cost in this threshold-mask case. The Qt model
reapplied the unchanged polarization factor every frame. Dioptrin recalculated
full-detector polarization and correction arrays on each setter call, costing
about 57 ms/frame. The model also evaluated `ImgModel.img_data` five times,
allocating five 81 MB processed-image arrays per frame.

- Reuse polarization state while the native integrator and factor are unchanged.
  Update it when either changes, including transitions between 1D, 2D and batch
  use. Release cached state if native integrator creation fails.
- Capture one processed image per Configuration integration call and pass that
  same image through plugin masking, shape checks, native integration or the
  pyFAI fallback (including supersampling). Direct CalibrationModel calls also
  capture only once for 1D integration.
- Preserve the independent processed snapshot. Raw ImgModel storage is not
  exposed for mutation; background correction, scaling and float64 arithmetic
  remain intact. No change to the global `img_data` getter or Rust kernels.

## Exclusive wall-time profile

Median stage milliseconds per frame; nested stages are subtracted so these
categories do not double-count work. Stage medians need not sum to the median
of complete runs. Polarization work is absent from warmed optimized frames.

| Stage | Before ms/frame | After ms/frame |
| --- | ---: | ---: |
| Reapply polarization correction | 56.59 | 0.00 |
| Processed-image creation/copies | 10.11 | 1.80 |
| Plugin geometry context | 3.94 | 3.59 |
| Threshold-mask creation | 2.22 | 2.06 |
| Combine plugin/user/ROI masks | 0.55 | 0.52 |
| Upload mask to native integrator | 0.21 | 0.19 |
| Native integration + normalization | 23.83 | 23.07 |
| Other model work | 2.71 | 2.52 |

The remaining small detector-mask merge/plugin bookkeeping stages are recorded
in the raw JSON. Native normalization is included in the integration timer:
the public native API does not expose a separate normalization-only timer.

Processed-image getter allocations fell from **405,531,840 to 81,106,368 bytes
per frame** (five getter calls to one). This counter measures image getter
allocations, not all native/NumPy allocations or total process memory traffic.

Separate uninstrumented runs measured **10.14 → 29.50 fps**,
a **2.91×** gain. The first optimized profile gave
28.4 fps; the final pass gave the value above, consistent with concurrent host
load. All four final intensity arrays were asserted byte-identical to saved
pre-optimization results.

## Protocol and limits

Same Eiger9M source and calibration as the earlier diagnostic: four decoded
float64 frames at indices 0, 208, 416 and 624; 3262 × 3108 pixels; 2000 bins;
full pixel splitting; solid-angle correction; polarization 0.965; dynamic
threshold above 230. No additional static mask. Five warmed four-frame passes
with instrumentation, followed by five without instrumentation, per version.
One Rayon/OpenMP/BLAS thread. The CPU ran concurrent rsmith work; no jobs were
stopped. File I/O, decompression and initial geometry/LUT setup are excluded.
These are short model-path measurements, not peak batch or full-file throughput.
Other dynamic plugins, such as cosmic/spot masking, have different mask costs.

## Validation

- 157 calibration, worker, batch, map and mask-mode tests passed in the first
  broad run after the production change.
- 45 configuration/mask tests passed, including new checks for one processed
  snapshot, background/scaling correctness, raw-storage independence and
  correction-state invalidation.
- The final 16 mask-mode tests additionally cover numerical polarization
  changes across 1D/2D/1D integrations in both policies, with Poisson errors
  checked for the 1D cases. These overlap the runs above.
- Eiger output comparison is byte-identical before/after; Ruff and whitespace
  checks pass.

## Reproduction and artifacts

Run `python -m scripts.profile_dioptrin_dynamic_mask --help` from the Qt
checkout. Set `OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 RAYON_NUM_THREADS=1`.
The `--save-reference` and `--reference` options write and check small numerical
reference arrays outside the repository. Each JSON includes source hashes,
decoded-frame hashes, raw samples, exclusive timings and environment details.

- [Before profile](2026-11-06-dynamic-mask-profile-before.json)
- [After profile](2026-11-06-dynamic-mask-profile-after.json)
- [Exact production optimization patch](2026-11-06-image-copy-optimization.patch)

The patch isolates this optimization from the earlier uncommitted 0.8.0 pin and
mask-policy changes. It can be reversed against the optimized tree to recreate
the profiled model code before this change. Benchmark data and numerical
references remain outside the source package.
