# Qt Dioptas: Dioptrin 0.8.0 mask modes

## Thread-count correction (2026-11-06)

The fixed-mask batch-wrapper diagnostic used one batch worker with the native API default of two threads per worker. Global RAYON_NUM_THREADS=1 did not override this private pool. Per-frame model controls used one Rayon thread. The newer scaling benchmark explicitly sets worker thread counts.

Measured 2026-11-06 using the published Dioptrin 0.8.0 wheel in the Qt checkout.

## Behavior

Before batch, map and live-map append integration, select dynamic mode when
masking is in use and any enabled mask plugin declares `is_dynamic=True`.
Otherwise select fixed mode. Static plugins, user-drawn masks and ROI masks do
not require dynamic mode. Disabling masking or the dynamic plugins restores
the fixed path at the next run.

Fixed masks use the existing parallel batch iterator, configured once per run.
The iterator supports one mask per run, so dynamic masks use the existing
per-frame model path with the Dioptrin backend. This path explicitly refreshes
plugin masks while image signals are blocked. Intermediate plugin notifications
are suppressed to avoid GUI updates or automatic integrations during a run.
Each frame updates its mask and normalization; geometry remains reusable.

## Checks

- 155 existing targeted calibration, integration-worker, availability, batch and
  map tests passed, including a rerun of the availability suite after updating
  its version expectations.
- Nine new tests passed against the real backend: enabled/disabled/static
  plugins, masking disabled, geometry recreation, file-based batch and map
  numerical references, switching back to fixed mode, suppressed intermediate
  notifications and dynamic live-map appends.
- Ruff and `git diff --check` passed.
- `uv tree --frozen --package dioptrin` resolves 0.8.0. All 25 wheel hashes and
  the source archive hash in the lockfile were checked against PyPI. Existing
  NumPy resolutions and unrelated package records were preserved.

## Short Eiger timing

Four Eiger9M frames (indices 0, 208, 416, 624) from the original 625-frame
bitshuffle/LZ4 HDF5 input, decoded before timing. Same full pixel splitting,
2000 bins, calibration and polarization 0.965. Float64 frames, weights and
arithmetic. The dynamic plugin masks values above 230. No static mask was used
in this diagnostic, to isolate execution-policy differences.

Three passes per case, medians below. One worker and one Rayon/OpenMP/BLAS
thread to limit interference with ongoing rsmith calculations. One warm frame
per case and initial LUT/geometry setup are excluded. Per-frame model timings
include image access, mask computation/update, normalization and integration.
The batch-wrapper timing configures its mask once, then streams the same
predecoded frames through CalibrationModel's real batch wrapper.

| Path | fps |
| --- | ---: |
| Fixed mask, fixed-mode batch wrapper | 86.13 |
| Fixed mask, per-frame model calls forced to fixed mode | 10.10 |
| Fixed mask, per-frame model calls forced to dynamic mode | 13.08 |
| Changing mask, per-frame calls forced to fixed mode | 6.75 |
| Changing mask, per-frame calls using dynamic mode | 11.91 |

Dynamic mode improves the changing-mask case by **1.77×** over forcing fixed
mode on the same 0.8.0 backend. Fixed-mode per-frame calls reapply the mask on
each call, losing the reuse provided by the batch path; their rates are not a
benchmark of fixed-mask batch throughput. The dispatch therefore retains the
batch path whenever a single mask can be reused.

All compared intensity outputs agree within float64 rounding noise: relative
L2 differences are 3.08e-16 for static masks and 3.63e-16 for changing masks.
The fixed-mode batch wrapper also matches the per-frame reference.

These short measurements were taken during concurrent work and exclude file
reading/decompression. They establish correct dispatch and a measured policy
gain on these inputs, not peak throughput, a full-file rate, or a comparison
against Dioptrin 0.7.0.

Raw measurements and input hashes: [JSON](2026-11-06-dioptrin-mask-modes.json).
Reproduction script: `scripts/benchmark_dioptrin_mask_modes.py` (run as a module
from the checkout root; see its docstring).
