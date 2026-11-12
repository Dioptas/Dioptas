# Native Batch/Map frame pipeline

> Historical evidence: Python-era commands and source paths in this ledger refer to
> pre-cleanup revision `a39717a41458129ba9370c849a4121ecdbc6a444` (resolve the full revision in `REFERENCE_DATA.md`).
> The active application and test suite are Rust/headless UI only. See
> [reference data policy](REFERENCE_DATA.md) for retained fixtures and current checks.

Batch and Map share `Session::integrate_series`. Admitted uncorrected, fixed-mask HDF5 series
now run concurrent complete frames against one cached, immutable CSC plan and
one raw-chunk reader. Each scoped worker retains its native uint16/uint32 frame
buffer, compressed input, codec scratch and float64 integration accumulators
throughout the source. Workers do not spawn another set of block threads for
each frame. No full-frame float64 conversion or per-worker LUT copy is needed.

The default is eight workers, controlled by `DIOPTAS_INTEGRATION_THREADS`.
Admission caps the worker count by the selected frame count and a conservative
4 GiB combined worker payload budget. For corrected/dynamic processing it also
accounts for float64 buffers and plugin temporaries. Shared plans/correction
maps, final scientific series and allocator overhead are separate.
At most as many outstanding frames as there are workers are admitted; only
ordered consumption releases another queue slot. The result reorder queue is bounded by
the worker count even if an early frame is slow.

The command worker collects profiles in source/frame order and owns Map
reduction, preview publication and the final series. Source fingerprints are
checked before and after processing; raw reads also check their frozen file
identity. Cancellation, a reader error, a worker panic or a collector error
stops admission, releases blocked channels and joins every worker. Existing
transactional rollback retains the preceding complete Batch/Map; partial Map
previews remain provisional and are cleared when the operation ends.
Cancellation is checked around decode/integration and ordered publication;
an individual decoder or integration kernel is allowed to finish.

## Admission and layout

The existing combined-source admission is retained: a single self-contained
HDF5 dataset with supported full-frame Bitshuffle/LZ4 uint16/uint32 chunks,
fixed established masks, polygon/subpixel integration, solid-angle correction,
no image transformations, image corrections/background processing, dynamic
mask, azimuth-limited pattern or azimuthal spread. Poisson errors are supported.
Other cases retain their existing native integration path and scientific
settings. There is no Python fallback or automatic change of integration method.

Corrected images and changing masks now have a separate
[native dynamic-plan pipeline](NATIVE_PROCESSED_SERIES_PIPELINE.md), using
Dioptrin's `Dynamic1dPlan`/`Dynamic1dWorker` with supplied pixel variances.

The resident CSR/CSC setting does not change this pipeline's CSC block plan.
Geometry, masks, normalization and lookup tables are built once and shared;
complete frame workers retain independent float64 sums and error propagation.
Start/stop/stride selection is applied across the ordered input files before
dispatch. Worker threads persist across frames of a source and are joined at
its end; no background pool survives the completed command.

## Development codec optimization

`hdf5-bitshuffle` is a separate C dependency of `dioptrin-io`. Optimizing the
Rust I/O package alone leaves its Bitshuffle/LZ4 and NEON/AVX2 C kernels at
development optimization level zero. The desktop now sets
`profile.dev.package.hdf5-bitshuffle.opt-level = 2`, matching its other hot
scientific dependencies. This also benefits single-frame decoding. Release
builds already optimize this dependency.

Profiling the earlier live-development binary found most decoder samples in
unoptimized NEON unshuffle routines. The benchmark separates that build issue
from the benefit of concurrent complete frames by comparing the preserved old
binary, the new optimized binary with frame parallelism disabled, and the same
optimized binary with frame parallelism enabled.

## Earlier desktop implementations

The preserved `codex/react-desktop` worktree at
`/Users/clemens/.codex/worktrees/dioptas-react-desktop/Dioptas` has React and a
Rust/Tauri host but runs the Python desktop processor and native Dioptrin behind
it. Its Batch/Map workflow reuses the Qt models and processing infrastructure.
Thus the earlier fast pipeline was also available behind a React interface;
describing it as available only in the Qt interface was too narrow.

The fully Rust scientific port introduced in `53b06ada` processes series frames
sequentially and uses parallel blocks within an admitted Eiger frame. Inspection
of the preserved branches/worktrees found no earlier Rust Batch/Map frame pool.
The development codec slowdown is independently reproducible without changing
that processing structure. These findings do not identify which exact earlier
preview/build the user observed.

## Verification and reproduction

Measured November 10, 2026 on the local M4 Pro, all **625 × 3262 × 3108**
Eiger uint32 frames, 2,000 radial bins, eight workers, polygon splitting,
polarization 0.965 and the PONI's named-detector geometry/automatic gap mask.
The following rates convert the median complete-command time from two passes
to images/s; the second pass reverses variant order.

| Workflow | Earlier dev build | Codec optimized, existing pipeline | Codec optimized, frame workers |
| --- | ---: | ---: | ---: |
| Batch, intensity | 20.9 | 154.6 | 207.0 |
| Batch, Poisson | 22.6 | 144.1 | 183.8 |
| Map, intensity | 22.5 | 108.2 | 201.4 |
| Map, Poisson | 23.0 | 134.9 | 186.4 |

The combined improvement is about 8.1–9.9×. Codec optimization accounts for
most of it. CPU resources were not isolated; in particular, the two codec-only
Map/intensity times were 7.59 and 3.97 seconds, so its two-pass median should
not be treated as a precise pipeline speedup. These are processor command
throughputs, not screen presentation rates or cold-start measurements.

All **24 full-file runs** passed float64 comparisons against the preserved
binary. The largest intensity relative L2 difference was **2.28e-15**
(maximum absolute difference **8.61e-9**); the largest counting-std relative L2
difference was **1.95e-16**. Map window values agreed within **4.04e-16** relative
L2. Every parallel run integrated all 625 frames using exactly eight worker
starts, one pipeline invocation and zero additional pattern-plan builds.
The maximum observed reorder queue contained seven results.

Raw times, diagnostics, binary hashes and numerical comparisons:
[benchmark receipt](artifacts/native-series-pipeline/eiger-results.json).

`integration_diagnostics` reports `frameParallelIntegrations`,
`seriesWorkerStarts`, `seriesPipelineRuns` and `seriesPendingPeak`. The normal
plan-build and pattern-only-decode counters remain available. Set
`DIOPTAS_SERIES_PARALLEL=0` to compare the existing sequential-frame/fused-block
route in the same binary; it is a benchmark/debug override.

```sh
python desktop/scripts/native_series_pipeline_benchmark.py \
  --source /path/to/eiger_0000.h5 \
  --before /path/to/preserved/dioptas-processor-before \
  --after desktop/backend/target/debug/dioptas-processor \
  --output desktop/artifacts/native-series-pipeline/eiger-results.json \
  --repeats 2
```

The harness checks all 625 stored float64 profiles, radial axes, Poisson errors
and Map window values against the preserved binary. Timings include the complete
native stdio command, worker startup, final frame selection/image/pattern/cake
response and Map previews/reduction. Initial geometry/plan setup, process
startup, numerical export checks and Tauri/rendering are excluded. Repetition
order is reversed on the second pass; file pages are warm after the first pass
and the machine's CPU is not isolated. The receipt records executable SHA-256
identities and confirms the source's size and modification time stayed unchanged.

Unit tests cover typed samples, ordered striding, Poisson equivalence, bounded
reordering, failed reads, cancellation, source mutation, collector failure and
worker reuse after a failed operation. Existing real-stdio transport tests cover
Batch/Map cancellation and source-change rollback on compressed sources.
Headless Chromium/WebKit checks cover partial Map previews, unfinished cells,
detached previews, and retention of regions/expressions.
