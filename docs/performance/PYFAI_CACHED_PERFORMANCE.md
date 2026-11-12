# Cached pyFAI-compatible integration

Measured on 2026-11-09 at Dioptrin `4e2cabb`, based on `88b88a1` (Massif) and the public 0.12.0 release. The additional APIs are committed and pushed; this measurement does not publish a new package release. Subsequent polygon execution-layout work and the current desktop pin are documented in the [detector/bin crossover study](INTEGRATION_LAYOUT_CROSSOVER.md).

## Changes

- 1D compatibility uses a strict fixed CSR plan: unchanged weights and summation order, a compacted mask and cached per-bin normalization.
- Fixed-mask cakes with solid-angle correction use an immutable shared-grid plan. Static geometry is validated once, and repeats produce intensity directly without coverage counts or raw output arrays. Input dimensions and unmasked finite pixels remain checked.
- Cake grid limits and coordinate metadata are cached with the geometry/options key, instead of calculating detector corners again on every request.
- Dynamic masks, 1D azimuthal spread/externally supplied variance, and cakes without solid-angle correction retain their existing general execution where needed. They share the cached cake grid and are included in the numerical regression checks.

## Matched timing comparison

Same CeO2_Pilatus1M.tif (1043 × 981), supplied reference PONI, 1,000 radial bins × 360 azimuthal bins, 73,560 negative gap pixels masked, polarization 0.99, relative solid-angle correction, and no error calculation in timing. Both methods use the exact same bin edges.

Release-profile Rust numerical paths, 8 Rayon threads; resident float64 image, no errors, fixed gap mask; excludes decoding, process startup, transport, raster conversion, UI. Three alternating paired runs; 15 fresh plans and 63 cached calls per method.

Times are milliseconds, first calculation / cached repeat. The unchanged polygon path is a control; small differences between runs reflect the active workstation and allocator/cache state.

| Method | 1D first / cached | Cake first / cached |
|---|---:|---:|
| Polygon (control, optimized-run context) | 64.826 / 0.538 | 59.324 / 0.681 |
| Compatibility before | 107.178 / 0.616 | 73.524 / 2.647 |
| Compatibility optimized | 116.888 / 0.277 | 74.224 / 0.658 |

Cached compatibility speedups: **2.22× for 1D** and **4.03× for cake**. Preparing the 1D cache adds roughly 9.7 ms to the first calculation on this fixture; cake preparation is similar to before. These figures qualify this image/profile, not all detector sizes or live-preview redraw latency.

## Numerical verification

- All 1,000 pattern values and 360,000 cake values are bitwise identical to the frozen previous float64 results in all three paired runs. The published-release baseline arrays also match bitwise.
- 68 old/new native command comparisons pass, including changed samples, masks, corrections, units, radial/azimuthal bin counts, sectors, Poisson errors, azimuthal spread, geometry changes, method switches, project restoration and combined detectors. Native pattern/sigma comparison is float64; transported cakes are float32, supplemented by the float64 Rust comparison above.
- Independent pyFAI reference checks pass for 21 matched 1D/cake cases, ROI, warm reuse, project restoration, Batch, combined errors and beam safety. Approximate pyFAI boundary conventions are unchanged.
- Dioptrin: 229 tests/doctests pass. Desktop Rust: 140 pass, 1 opt-in benchmark ignored. Both Clippy checks pass with warnings denied. Strict library documentation and Chromium/WebKit headless integration workflows pass.

## Evidence and reproduction

Raw measurements, input hashes, executable/source hashes and test logs: [summary](../../artifacts/integration-cache-optimization/summary.json), [native equality](../../artifacts/integration-cache-optimization/desktop-equality.json), and `artifacts/integration-cache-optimization/verification/`. The old and new Rust harnesses and lockfiles are retained with the input arrays. The original pattern/cake comparison is still valid because the optimized values are unchanged.

From `artifacts/integration-cache-optimization`:

```sh
cargo build --locked --release --manifest-path before/runner/Cargo.toml
cargo build --locked --release --manifest-path runner/Cargo.toml
../../../.venv/bin/python repeat.py
../../../.venv/bin/python desktop_parity.py
../../../.venv/bin/python summarize.py
```
