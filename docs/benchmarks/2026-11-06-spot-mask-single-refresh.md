# Spot Mask: compute once per frame

## Thread-count correction (2026-11-06)

Fixed-mask controls used one integration worker with the native default of two threads per worker. Spot Mask and the other dynamic per-frame cases used one Rayon/OpenMP thread, so the Spot before/after comparison is unchanged. The newer scaling benchmark explicitly sets private batch thread counts.

2026-11-06. Qt Dioptas local source fix; published Dioptrin 0.8.0 runtime.

## Fix

A combined image/geometry refresh previously ran geometry-aware mask plugins
against the previous image during `update_geometry()`, then again against the
new image during `update_image()`. Configuration now defers geometry-triggered
mask computation until the immediately following image update. Geometry-aware
caches are invalidated so static plugins also see changed geometry. Standalone
geometry-only updates retain immediate recomputation.

## Matched end-to-end benchmark

Same Eiger9M frames 0, 208, 416 and 624; same calibration and 8.755% static mask;
2000 bins, full pixel splitting, solid-angle correction, polarization 0.965 and
float64 arithmetic. Same exact original bitshuffle/LZ4 chunks. Three warmed
four-frame runs per case. One integration worker and one decoder worker, with
one Rayon/OpenMP/BLAS thread. Includes Qt model dispatch, file opening, reading,
decompression, image preparation, mask generation, normalization, integration,
result collection and map reduction. GUI rendering and initial LUT/plugin setup
are excluded. Concurrent user work continued; normal OS file cache was warm.

| Spot method | Workflow | Before fps | After fps | Gain |
| --- | --- | ---: | ---: | ---: |
| Mean | Batch | 1.92 | 3.45 | 1.79× |
| Mean | Map | 1.96 | 3.42 | 1.75× |
| Median | Batch | 1.31 | 2.46 | 1.88× |
| Median | Map | 1.32 | 2.45 | 1.86× |

All seven masking cases were rerun in both batch and map workflows. All 42
timed runs passed their independent numerical reference checks. Compressed and
decoded frame hashes, mask hashes, masked-pixel counts, plugin settings, package
versions and numerical settings match the previous benchmark. The unchanged
control cases vary by roughly -1% to +7%, so small changes in their rates should
be treated as measurement/host-load variation. The Spot gains are much larger.

The two Spot methods retain sigma multiplier 3, 445 bins, one iteration and
smoothing sigma 1 / threshold 0.3. The native C mask extension was active;
OpenCV was absent, as in the baseline. A separate warm-frame call-count check
verifies **one Spot computation per frame**, compared with two previously.

## Tests

99 targeted tests passed across mask-plugin management, Spot Mask algorithms,
Configuration, and Dioptrin mask modes. New cases cover combined updates,
geometry-only updates, geometry removal, dimension changes, static and dynamic
geometry-aware plugins, notification counts, and real Spot Mask outputs matching
fresh plugin instances for both mean and median. Ruff and whitespace checks pass.

## Reproduce and inspect

Use the command in the [original benchmark report](2026-11-06-qt-eiger-masking.md)
with output `docs/benchmarks/2026-11-06-qt-eiger-masking-single-refresh.json`.
Fixture creation uses a temporary APFS clone; the original source is opened
read-only, and the temporary file is removed afterward.

- [Full new raw results and provenance](2026-11-06-qt-eiger-masking-single-refresh.json)
- [Original raw results](2026-11-06-qt-eiger-masking.json)
- [Before/after CSV for all masking cases](2026-11-06-spot-mask-single-refresh.csv)
- [New call-count diagnostic](2026-11-06-qt-plugin-single-refresh-diagnostic.json)
- [Previous call-count diagnostic](2026-11-06-qt-plugin-call-diagnostic.json)

These short subset measurements establish this change's observed gain in the
Qt processing path. They are not full 625-frame, cold-SSD or peak multiworker
rates. Production code and results remain local and uncommitted.
