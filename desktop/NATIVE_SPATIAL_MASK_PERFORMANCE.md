# Spot and Cosmic mask performance

November 10, 2026. The native Rust mask kernels used by interactive images,
Batch and Map now use contiguous row operations and reusable private scratch.
Batch/Map retain the existing shared Dioptrin `Dynamic1dPlan`, persistent
workers, ordered collection, cancellation and source-snapshot checks.

## Profile and implementation

macOS `sample` profiles of the old processor (`3333736d`) showed Spot spending
most samples in the Gaussian convolution and its repeated reflected-boundary
calculation. Cosmic's hot stacks were the repeated `uniform_axis` filters and
reflection, including strided column traversal. The masks were already inside
the parallel pipeline; the mask kernels and their large scratch requirements
were limiting throughput.

Cosmic now computes count, positive intensity and squared positive intensity
together with rolling local sums. Two row-sized moment buffers replace the
separate full-image filter intermediates. Boundary indices are calculated
once per axis, and row updates read contiguous pixels. The working image is
still rejected only after each complete pass, preserving the original two-pass
algorithm and comparisons.

Spot prepares compact pixel membership once per geometry, bin count and user
mask. Workers share that immutable membership and reuse private value/MAD
scratch. User-mask edits, geometry edits and bin changes invalidate membership.
Gaussian convolution uses contiguous rows vertically and padded rows
horizontally. It preserves reflected edges, kernel tap order, float64 sums,
the float32 cast after each axis, and the existing gap-dilation/reach rules.
The mean/std reductions run in original pixel order before median selection.

Scratch is private to each worker and omitted from checkpoint clones. The
existing 4 GiB worker-payload budget uses the actual compact workspace estimate,
including the largest statistical bin. For this Eiger dataset it admits eight
workers instead of the previous three. Shared geometry/membership, final
results and allocator overhead remain outside that payload estimate.

Post-change profiles show the fused Cosmic calculation and Spot statistics/
convolution in their worker stacks; repeated per-pixel reflection and the old
full-image uniform filters are removed from the hot loops. Raw before/after
profiles and baseline float64 matrices are retained locally in
`/Users/clemens/Codex/dioptas-spatial-masks-20261110`.

## Full Eiger benchmark

Source: `/Users/clemens/Programming/Dioptrin/test_data/eiger_0000.h5`,
5,687,072,680 bytes, **all 625 frames, each 3262 × 3108 pixels**. Local Apple M4
Pro, macOS 26.6.2, optimized development processor. Both executables use the
same optimized codec and dynamic integration plan. Settings: polygon splitting,
2,000 radial bins, Poisson errors, polarization 0.965, adjacent named-detector
PONI geometry and automatic acquisition mask. Each plugin uses its unchanged
defaults: Spot median/MAD, 445 bins, sigma 1 smoothing, threshold 0.3; Cosmic
5-pixel window, two passes, sigma 5, minimum intensity 100. No image corrections
are enabled in these timings.

| View / mask | Before, images/s | After, images/s | Before, seconds | After, seconds | Speedup |
| --- | ---: | ---: | ---: | ---: | ---: |
| Batch / Spot | 5.68 | 41.64 | 110.08 | 15.01 | 7.33× |
| Map / Spot | 5.60 | 39.74 | 111.69 | 15.73 | 7.10× |
| Batch / Cosmic | 3.50 | 38.53 | 178.59 | 16.22 | 11.01× |
| Map / Cosmic | 3.49 | 36.08 | 179.17 | 17.33 | 10.34× |

Before uses three workers; after uses eight, both requested eight under the
same payload cap. Each measured command processes all 625 frames with one
source pipeline and **zero additional dynamic-plan builds after warmup**.
Timings include mask generation, frame decode/integration, worker startup,
ordered collection, final selection and Map preview/reduction. Initial
setup/two-frame plan warmup, process startup, exports/comparisons and Tauri
rendering are excluded. OS file pages are warm; CPU resources are not isolated.
These are native command throughput measurements, not display frame rates.
Sampling briefly overlapped the optimized Batch Spot and Map Cosmic commands.

With concurrency held at the original **three workers**, optimized full-file
Batch reaches **17.04 images/s for Spot** (36.68 s) and **15.83 images/s for
Cosmic** (39.49 s), respectively **3.00× and 4.52×** the original rates. This
separates the faster kernels from the additional concurrency made possible by
their smaller workspace. All 625 profiles and counting std remain identical.

Receipts: [before](artifacts/native-spatial-masks/before.json),
[after](artifacts/native-spatial-masks/after.json),
[controlled three-worker run](artifacts/native-spatial-masks/after-3-workers.json).

## Numerical and workflow checks

Every exported float64 intensity, radial coordinate and counting std across all
625 profiles is **identical** before/after in all four runs (maximum absolute
difference zero). Every Map window value is also identical. The controlled
three-worker comparisons use the same full-file reference. The source's size
and modification time remain unchanged.

Frozen pre-change kernels are compiled only in tests. Regression cases cover
small/asymmetric images, reflected boundaries, even and oversized windows,
multiple Cosmic passes, negative values/NaNs, mean/median Spot statistics,
Gaussian widths and thresholds, and user-mask gap reach. A separate measured
Eiger oracle checks byte-for-byte Spot and Cosmic masks at full resolution on
frames 0, 1, 312 and 624. Independent Python/C/SciPy comparisons report **26
comparisons, zero different mask pixels**. These checks preserve the established
mask algorithms and numerical behavior.

Validation also passes **182 Rust tests** (two data-dependent tests skipped in
the default suite; the Eiger oracle above was run explicitly), strict Clippy
for all targets, ten corrected/plugin integration scenarios across Batch/Map
against the preserved executable, and seven real-stdio cancellation/source
mutation cases, including Spot and Cosmic. Headless Chromium and WebKit Map
checks pass for partial/unfinished cells, retained regions/expressions and
detached previews. No visible test window was opened.

## Reproduction

Build the processor with `cargo build --locked --manifest-path
desktop/backend/Cargo.toml`. Preserve the old executable before rebuilding.
Run once for each executable; the first invocation stores reference matrices:

```sh
python desktop/scripts/native_spatial_mask_benchmark.py \
  --source /path/to/eiger_0000.h5 --processor /path/to/old/dioptas-processor \
  --label before --directory /tmp/spatial-before
python desktop/scripts/native_spatial_mask_benchmark.py \
  --source /path/to/eiger_0000.h5 --processor /path/to/new/dioptas-processor \
  --label after --directory /tmp/spatial-after --reference /tmp/spatial-before
# Isolate kernel improvements with the old worker count:
python desktop/scripts/native_spatial_mask_benchmark.py \
  --source /path/to/eiger_0000.h5 --processor /path/to/new/dioptas-processor \
  --label after-3-workers --threads 3 --views batch \
  --directory /tmp/spatial-three --reference /tmp/spatial-before
DIOPTAS_EIGER_FILE=/path/to/eiger_0000.h5 \
  cargo test --locked --manifest-path desktop/backend/Cargo.toml --lib \
  measured_eiger_mask_bits_match_frozen_kernels -- --ignored --nocapture
```

The Python scripts are explicit benchmark/reference clients. Production mask
generation, decoding and integration remain entirely Rust over native stdio.
