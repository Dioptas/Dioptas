# Production fast HDF5 reading in Qt Dioptas

Implemented and measured 2026-11-06. Local source changes; not a published Qt
release. Installed environment: Dioptrin 0.8.0 and the pinned PyPI decoder
`bslz4-to-sparse==0.0.22a3`.

## What changed

- Qualifying bitshuffle/LZ4 HDF5 data now use the benchmark-proven decoder in
  `loader/fastHdf5.py`. HDF5 supplies discovery and a once-per-stream chunk
  index. Workers use indexed positional reads, reusable native u16/u32
  workspace, then one flip/float64 conversion to independently owned frames.
  There is no mmap lifetime or mutable-buffer reuse across queued consumers.
- Fixed-mask batch/map streams use that reader automatically. Native batch
  worker threads are explicitly one per worker, avoiding the prior hidden
  two-thread default.
- Dynamic mask and pyFAI-compatible per-frame loops in batch, map and live-map
  append now use `prefetch_series`. It temporarily replaces only the series
  frame callback. ImgModel still applies transformations, corrections,
  background and scaling; Configuration recomputes each frame's mask on the
  caller thread. It restores the callback and closes owned readers/pools on
  completion, early cancellation and exceptions.
- Dataset selection honors the selected HDF5 dataset or the actual dataset
  selected by the established FabIO loader. Multiple hard-link aliases are
  compared by HDF5 object identity. Equal shape/type alone is insufficient;
  ambiguous channels retain the original reader.
- The Dioptrin extra installs the codec on supported wheel platforms. macOS
  Intel retains the existing decoder. Missing/unsupported fast backends or
  layouts retain the stock bitshuffle/HDF5 paths. Source/decode failures after
  reading begins propagate rather than silently replaying data.
- The standalone PyInstaller spec explicitly collects the c2py native library
  and package/license metadata. Library discovery was checked locally; a
  complete standalone application bundle was not rebuilt for this change.

The fast path is deliberately scoped to native u16/u32, one full image per
chunk, and a single bitshuffle/LZ4 filter. It preserves count values, including
reserved/high uint32 samples, while the consumer owns mask/correction policy.
The index checks source/storage identity, size and mtime. It treats one run as
an immutable snapshot, not live/SWMR refresh. Fast decoder workers are capped
at eight with 2 GiB decoder-payload admission; integration queues/geometry/masks
are additional allocations. Queued arrays remain independent and bounded in
number.

`dioptrin-io` was inspected and remains an unpublished Rust-only package with
no Python binding. This implementation uses the MIT-licensed decompressor from
the already measured pipeline, not a new numerical kernel. The interface can
adopt the shared Rust backend when its Python bridge is available.

## Paired before/after benchmark

Same file, calibration, static mask, 2000 bins, full pixel splitting,
solid-angle correction, polarization .965 and float64 arithmetic. Eight decode
and integration workers, one thread per fixed-mode native worker. Dynamic
within-frame Rayon and OpenMP environment limits are eight. No Poisson errors.

Three alternating paired runs after warmup, including file loading, decode,
image processing, masks, normalization, integration and map reduction. The
"before" control disables the new optional decoder and per-frame prefetch to
reproduce the prior behavior. Fixed controls retain their previous parallel
stock reader; dynamic controls retain the sequential established loader.
The "after" path is the production implementation, without decoder adapters.

| Case | Before fps | After fps | Gain |
| --- | ---: | ---: | ---: |
| Fixed mask, full 625 frames | 99.12 | 161.22 | 1.63× |
| Dynamic threshold >230, 16 frames | 14.95 | 39.74 | 2.66× |

Instrumentation confirmed 625 fast decoded frames per full-file after pass,
and 15 fast frames after the initial metadata/image load in each dynamic sample
pass. All outputs matched the common reference. The first image/metadata still
uses the established image-loader behavior; this per-file overhead matters more
for short sampled files.

An independent three-pass full-file run measured
**161.09 fps** for the production Map
path and **169.74 fps** for
the reader streamed directly into Dioptrin. The archived grouped-buffer recipe,
replayed with the same installed codec/kernel, measured
154.65 fps in that run.
These are different scheduling/overlap choices; they are not a claim that one
kernel became faster. Earlier ~193 fps measurements were taken under different
host load; the raw ranges should accompany comparisons.

## Different masking, production batch and map

Eight sampled frames spanning the same source scan, three warm repetitions per
workflow. Eight decoder workers, eight fixed-mode workers with one thread each,
and eight within-frame Rayon/OpenMP threads for dynamic processing. Same mask
settings as the previous scaling benchmark. These short-file rates include
initial file/image loading overhead and should not be compared directly with
the 625-frame rate above.

| Mask case | Batch fps | Map fps |
| --- | ---: | ---: |
| static_mask | 25.31 | 37.77 |
| threshold_230 | 36.91 | 32.43 |
| cosmic_default | 1.39 | 1.40 |
| spot_mean | 3.57 | 3.58 |
| spot_median | 3.35 | 3.30 |

All 30 timed masking runs passed independent direct-native output checks and
mask-mode/dispatch checks. Expensive cosmic/Spot mask algorithms remain the
main cost in their cases. Concurrent host CPU load was especially high during
parts of this run (recorded per pass); small differences from older masking
measurements are not reliable isolated speed changes. The paired fixed and
threshold experiment is the stronger estimate of the reader improvement.

## Validation

**222 targeted tests passed** across fast-reader counts/ownership/lifetimes,
Configuration, CalibrationModel, integration workers, batch/map paths, backend
availability and mask modes. New tests cover:

- independently encoded u16/u32 bitshuffle data and original high/reserved counts;
- owned contiguous arrays, start offsets and retained earlier frames;
- missing-codec and non-LZ4/endian fallback;
- changed sources, cancellation, callback restoration and closed readers;
- frame skips/repeats/reverse access and transformations/background/scaling;
- real dynamic HDF5 batch/map results against a fresh native reference;
- hard-link aliases versus genuinely different same-shaped image channels.

Ruff, Python syntax and whitespace checks passed. All pinned wheel/sdist hashes
were verified against PyPI and the frozen dependency graph resolves without
changing unrelated package resolutions. Native-library collection finds the
packaged c2py library; distribution metadata retains upstream license notices.

No source detector data or running user jobs were modified. The full benchmark
reads the original file read-only. Short samples use a temporary APFS clone with
exact original compressed chunks and independently checked decoded pixels; the
clone is removed afterward. OS cache was warm, no physical cold-SSD bandwidth
claim is made. Benchmark/reference preparation, LUT/plugin warmup and GUI
rendering are excluded from timing.

## Artifacts

- [Alternating paired before/after data](2026-11-06-production-fast-reader-paired.json)
- [Full-file production/reference data](2026-11-06-production-fast-reader-full-file.json)
- [All masking batch/map data](2026-11-06-production-fast-reader-masks.json)
- [CSV summary](2026-11-06-production-fast-reader-summary.csv)

Reproduction helpers are `scripts/benchmark_production_reader_pair.py`,
`scripts/compare_fast_and_qt_eiger.py` and `scripts/benchmark_qt_eiger_masking.py`.
Each provides `--help`; use the same input/PONI/mask paths recorded in JSON.
For the full-file replay select the installed codec package path so the
reference and production use the same library build. For masking use
`--workers 8 --decode-workers 8 --threads-per-worker 1 --frames 8 --repeats 3`.

Changes are local and uncommitted. Restart an already running Qt Dioptas process
to load the new source/backend. No Qt release or unrelated Rust repository was
changed or published by this task.
