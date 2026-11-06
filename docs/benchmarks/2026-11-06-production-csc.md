# Production CSC release verification

Dioptrin 0.9.0 promotes CSC to fast 1D for fixed and dynamic masks. Fixed masks retain the geometry CSC, cache a valid-pixel list and normalization; dynamic masks accumulate normalization per frame. `sparse_layout="csr"` provides the alternative without reducing precision. Strict arithmetic, azimuthal spread and 2D keep compatible paths. Fixed-mode tiles have deterministic boundaries independent of execution pool, preserving exact direct/file/array batch equality across worker counts.

Actual Qt MapModel entry points, same complete 625-frame Eiger file and static mask, float64 pixel splitting, 2000 two-theta bins, solid angle, polarization 0.965. Three alternating warm-cache paired passes per worker count, including file opening, reading/decompression, mask preparation, normalization, integration and map assembly:

| Workers | CSR fps | CSC fps | Observed CSC gain |
| --- | --- | --- | --- |
| 4 | 164.78 | 168.70 | 2.4% |
| 8 | 202.24 | 219.70 | 8.6% |

These are production timings, not just standalone kernel measurements. Python/library startup and GUI rendering are excluded. First-use timings are retained in the raw JSON but are not isolated geometry setup comparisons because the second layout reuses the geometry created by the first. Background CPU activity is recorded per sample; these are observed gains under the recorded load, not ideal hardware limits. Outputs are checked at rtol 5e-12 and atol 1e-9.

Qt Integration Options exposes CSC (default) and CSR on the same row as Use Dioptrin. The choice propagates through synchronous, asynchronous, fixed-batch and dynamic shared-plan paths and is retained in configuration/project state. Dynamic workers are closed on fixed-mode runs while the valid shared plan remains cached; returning to dynamic mode reuses it. Geometry/method/bin/unit/polarization/layout changes replace the plan as needed. Mask and threshold changes only refresh dependent selection/normalization.

Local release qualification: 173 Rust unit tests, 21 Python API regressions, 52 real-fixture release tests with exact direct/file/array parity, and 392 Qt model/state/controller regressions passed. Missing/invalid activation-state wheel probes and package-content checks passed. Each release wheel also runs the shared-plan/layout API tests in CI. New selector, mode-switch and retained-cache cases are included.

Raw records: [4 workers](2026-11-06-production-csc-4.json), [8 workers](2026-11-06-production-csc-8.json). Driver: `scripts/benchmark_production_sparse_layout.py`. Historical candidate/small-image probes remain separate from this production verification.
