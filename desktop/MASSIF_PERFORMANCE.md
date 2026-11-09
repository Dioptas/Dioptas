# Massif peak-picking performance

Measured November 9, 2026, on the development Mac. This is the native Rust
processor, with Python unavailable to the child process. Timings cover the
stdio command and returned snapshot; they exclude final GUI presentation.

## Implementation

Dioptrin revision `88b88a1b15e8831ffa1a2e65dea6838b24769bd2` (based on 0.12.0)
reorders the full-resolution separable Gaussian convolution for contiguous
access and SIMD across independent output pixels, and processes rows through
Rayon. Each output pixel accumulates the same kernel coefficients in the same
order as before. Reflection, component connectivity, seed and candidate order,
uphill walks, subpixel localization, thresholds and deduplication are retained.
The shared Gaussian filter also accelerates image-wide Massif candidates used
by automatic calibration refinement.

The new `PreparedMassif` owns the cleaned image and its component labels.
The desktop retains one disposable prepared image per processing session.
The cache key includes shape and the immutable owners of scientific samples
and the active effective mask. Image/frame replacement, transformations,
corrections and effective-mask changes force fresh preprocessing. Holding those
owners also makes copy-on-write edits change identity. Calibration group edits,
ring selection and repeated seeds can reuse the preparation. A disabled mask
does not participate in the key. The nearby-maximum retry after a background
click shares the same prepared image.

The cache is absent from project files, history and development handoffs. It
can be discarded without changing scientific state. It retains one f64 image
and one u32 label per pixel (about 12 MB per million pixels), plus references
to its source owners. These owners can keep one previous source alive until
the cache is replaced. No downsampling, float-precision reduction, Python
fallback or alternate scientific implementation was added to the desktop.

## Timings

Final repeated measurements, with identical optimized development build
settings before and after (three CeO2 runs and two LaB6 runs):

| Fixture | Previous picks | First optimized pick | Subsequent optimized picks |
| --- | ---: | ---: | ---: |
| CeO2 Pilatus, 1043 × 981 | 314–357 ms | 9.9–11.5 ms | 1.3–2.1 ms |
| LaB6 MarCCD, 2048 × 2048 | 3062–3897 ms | 70–74 ms | 4.4–4.6 ms |

Exact timings vary with machine load. Raw repeated measurements and complete
coordinate/fit comparisons are written to the ignored
`artifacts/massif-performance/results.json`. These measurements do not establish
OS scanout latency or performance on every detector size.

## Numerical and workflow checks

- Dioptrin's frozen pre-change convolution is compared bit for bit with the
  optimized convolution, including one-pixel dimensions, non-square images,
  edges and kernels wider than the image. Prepared and one-shot searches are
  compared with the pre-change seeded search for exact peak order and positions.
- The saved pre-change processor and optimized processor return exactly the
  same picked groups on both measured fixtures. CeO2 manual and automatic
  refinement also return exactly the same geometry, RMS and refined groups.
- Manual CeO2 RMS is **0.008680343581089094°** and automatic RMS is
  **0.010147852936183156°**. Independent pyFAI forward calculations give
  0.008680343581089150° and 0.010147852936183322°, respectively. Existing
  synthetic calibration tests independently recover known subpixel positions
  and geometry, including fixed rotations and free wavelength.
- Cache tests cover reuse across seeds and calibration undo/redo, mask edits
  and mask undo/redo, mask enable/disable, image backgrounds and reset, flips,
  rotations, image replacement, same-file frame changes, immutable-source
  copy-on-write and masked-seed rejection. Cached results equal fresh searches
  after invalidation.
- All 204 Dioptrin library tests pass. Desktop library, calibration,
  geometry/mask and development-reload checks pass. The headless Chromium and
  WebKit calibration workflows and stdio progress/cancellation check pass.
  The frontend production build passes. No visible test window is required.

These checks establish preservation of the existing native results. They do
not make the native and pyFAI Massif algorithms identical: their existing
differences in selected peak sets remain.

## Reproduce

Save the old executable before rebuilding the processor, then run from
`desktop/`:

```sh
cargo build --locked --manifest-path backend/Cargo.toml
DIOPTAS_MASSIF_BASELINE=/absolute/path/to/old/dioptas-processor node scripts/massif_performance.mjs
cargo test --locked --manifest-path backend/Cargo.toml --lib --test calibration --test geometry_masks --test development_reload
node scripts/native_calibration_smoke.mjs
node --test scripts/native_calibration_transport.test.mjs
PYTHONPATH=.. ../.venv/bin/python scripts/native_calibration_parity.py
```

The baseline environment variable is optional for timing, but required for
the exact pre/post processor comparison. The Python command is an independent
reference check only. The Rust processor does not call Python.

In the Dioptrin source checkout, run `cargo test --lib` to include the frozen
Massif reference comparisons and the rest of the library checks.
