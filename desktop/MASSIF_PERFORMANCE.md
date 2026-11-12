# Massif peak-picking performance

> Historical evidence: Python-era commands and source paths in this ledger refer to
> pre-cleanup revision `a39717a41458129ba9370c849a4121ecdbc6a444` (resolve the full revision in `REFERENCE_DATA.md`).
> The active application and test suite are Rust/headless UI only. See
> [reference data policy](REFERENCE_DATA.md) for retained fixtures and current checks.

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


## Event-to-render and full-calibration follow-up

The November 9 follow-up measures actual React input handling, Tauri binary
IPC, the Rust processor, and the detector canvas in an isolated WKWebView
host. The timer starts at synthetic pointer-up/button activation and stops
when the final marker strokes have been issued to the detector canvas.
Additional animation-frame timestamps bound the next presentation
opportunities. OS input queues and physical monitor scanout are not measured.

The headless Chromium/WebKit comparison uses the same UI and Rust processor
but substitutes a test bridge for Tauri IPC. Its transport overhead is
measurably larger, particularly on the 4-megapixel image, so the table below
uses the native host measurements. Each native run includes one cold pick and
seven warm picks per image, and three repeats of each CeO2 calibration case.
Before and after use the same frozen frontend bundle, image data and fit inputs.

| Native operation | Before follow-up, median to drawn markers | After follow-up, median to drawn markers | After, next frame opportunity |
| --- | ---: | ---: | ---: |
| CeO2 cold pick | 19 ms | 17 ms | 18 ms |
| CeO2 cached pick | 9 ms | 9 ms | 19 ms |
| LaB6 cold pick, 2048 × 2048 | 73 ms | 69 ms | 69 ms |
| LaB6 cached pick | 11 ms | 11 ms | 19 ms |
| CeO2 initial fit, automatic search disabled | 77 ms | 49 ms | 64 ms |
| CeO2 automatic refinement, 4 rings | 321 ms | 139 ms | 154 ms |
| CeO2 automatic refinement, 15 rings | 986 ms | 394 ms | 411 ms |

The first calibration also prepares integration products and can be slower:
post-change fifteen-ring samples ranged from 394 to 513 ms. A conservative
second-frame bound for that case was 439 ms at the median. These are local
optimized-development timings, not a guarantee for other detectors or loads.

### Additional changes

An opt-in `DIOPTAS_TRACE_FRAME=1` profile identified preview construction as
about 795 ms of a 1.15-second fifteen-ring calibration. The image-wide Massif
candidate search was about 10 ms and the geometry fits about 33 ms. The
follow-up therefore changes display-contour work and field reuse:

- Contour extraction computes conservative angle bounds on the existing sample
  grid and skips strips that cannot cross a target. Sampling, interpolation,
  path traversal and output coordinates are unchanged. Existing full-resolution
  indexed contours retain their existing strip index.
- Automatic ring-band searches reuse the exact full-resolution angle field
  already evaluated for the current preview geometry, rather than evaluating
  it a second time. The cache validates geometry and shape. This retains one
  additional f64 angle field (8 MB per million pixels), shared by ownership.
- Calibration fit, ring-search and preview stage timings are available through
  the existing opt-in stderr tracing. Ordinary command responses are unchanged.

The before/after native receipts compare all 25 measured operations for exact
peak coordinates, fitted geometry and RMS. A separate processor comparison
also checks the complete final ring paths and integrated pattern for manual,
four-ring and fifteen-ring fits. New contour tests compare exact paths against
the unpruned traversal at several sampling steps, boundaries, non-square
shapes, saddles, nonfinite values and exact-level values. Desktop library,
calibration and requested-product tests, independent pyFAI RMS checks, and the
stdio cancellation/rollback test pass.

The initial fit uses the selected groups. With automatic refinement enabled,
an image-wide Massif candidate search then supplies successive angular ring
bands and repeated fits. It is not a repeated click-based seed search.

Further numerical optimization of ordinary warm picks would save only a small
part of the current event-to-render latency. Background preparation could hide
cold-pick latency, but would add work after loading every image and needs a
separate scheduling and cancellation design. No speculative background work or
change to peak selection has been added.

### Follow-up benchmark tools

- `scripts/calibration_latency_benchmark.mjs`: headless pointer-to-canvas
  measurements in Chromium and WebKit, with source-buffer identity retained.
  Build an instrumented UI first with
  `VITE_DIOPTAS_NAVIGATION_BENCHMARK=1 npx vite build --outDir artifacts/calibration-latency/baseline-ui`.
  The runner accepts `--processor`, `--ui`, `--label` and `--repetitions`.
- `scripts/calibration_latency_native.js`: native browser driver, substituted
  for `scripts/image_navigation_native.js` only in an isolated test checkout.
  The test host embeds that same instrumented UI and is launched with
  `--navigation-benchmark`; the regular preview host is not modified.
- `scripts/calibration_latency_native.mjs`: runs the prepared isolated host with
  private WebKit storage and an explicit processor. Use `--app`, `--processor`
  and `--label` to compare saved binaries. The native test bundle needs the
  ordinary staged Dioptas resources and a macOS application bundle structure.

Receipts are in ignored `artifacts/calibration-latency/`: `baseline.json`,
`optimized.json`, `native-before.json`, `native-optimized.json`, `science.json`
and opt-in stage logs. The temporary native host exits after each report and
does not share the running preview's scientific session.
