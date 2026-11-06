# Whole-frame dynamic masking with one shared Dioptrin plan

Measured 2026-11-06 on Apple M4 Pro, 14 CPU cores, 48 GiB RAM. Changes are local and unreleased in Dioptrin and Qt Dioptas. No dioptrin-io changes or GUI rendering are included.

Dioptrin now owns an immutable `Dynamic1dPlan`: detector geometry, float64 CSR/CSC weights and correction arrays are prepared once. Each application worker holds a lightweight handle sharing that same plan. Each call borrows its float64 image and complete uint8 mask without copying, releases the GIL, and computes independent normalization and accumulation results. No frame updates a shared mask. Geometry, shape, integration method, units, bins or polarization changes replace the plan; user masks, plugin settings and image-processing settings can replace worker contexts while retaining the plan. Fixed-mode runs release cached dynamic workers and plans.

Qt Dioptas owns the outer frame pool: read/decompress, apply the normal image pipeline, create dynamic masks, integrate, return the result. Each worker has independent plugin/cache/image state and one native compute thread. The caller collects results in input order and handles model updates, progress and cancellation. Queues contain bounded frame descriptors; files remain open until active jobs finish. Spot Mask's C numerical loops now release the GIL, with one OpenMP thread per frame worker.

The fast path currently covers the supported bitshuffle/LZ4 HDF5 layouts and the built-in Threshold, Cosmic Ray and Spot plugins. Other formats/layouts, third-party dynamic plugins, custom transformations and unsupported integration settings retain the previous processing path and its reader prefetch. Errors on the parallel path propagate rather than silently dropping a frame's mask.

All full-file measurements use the original 625-frame uint32 Eiger file, 3262×3108 pixels, `/entry_0000/instrument/eiger/data`, file SHA256 `2b749693d7a942b35d89806d99b9a1025ee119850be0ade27428f1dc11d0a1f3`. Settings: 2000 two-theta bins, full pixel splitting, solid-angle correction, polarization 0.965, original static mask plus threshold >230, float64 integration weights/corrections/accumulators, no Poisson errors or azimuthal spread for timings.

| Frame/decoder workers | Serial-mask fps | Shared whole-frame fps | Observed gain | Whole-frame fps range | First whole-file run, s | First-run peak RSS, GiB | Warm median peak RSS, GiB |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 4 | 47.42 | 71.94 | 1.52x | 69.13–72.22 | 10.727 | 4.35 | 3.46 |
| 8 | 51.46 | 113.52 | 2.21x | 98.06–120.39 | 5.795 | 5.91 | 3.98 |

These are three alternating paired passes with a warm OS cache. The baseline retains the fast parallel reader and uses 4 or 8 global Rayon threads for each serial frame; the new path uses 4 or 8 complete frame jobs with one native thread each. Times include file opening, snapshots, reads/decompression, image preparation, changing masks, normalization, integration, ordering and map assembly. Initial Configuration construction/reference generation and GUI rendering are excluded. The first-run column includes actual frame processing plus plan/plugin setup; it is not an isolated LUT-build duration. All calls in each parallel run reported exactly one shared plan identity, unchanged across warm runs.

The host remained busy with other user work. Median other busy cores in the 4-worker serial/parallel samples were 10.20/9.68, and in the 8-worker samples 9.94/7.11. Thus these are observed throughput gains under contention, not isolated hardware scaling limits. Earlier separate-integrator prototype results were obtained under lighter load and must not be directly used as a speed comparison. Its first-run peak RSS was about 10.8–10.9 GiB; that historical comparison is indicative rather than a controlled allocator experiment.

For heavier masks, the same exact 16 frames sampled across the original file were used in both workflows. Original compressed chunks and decoded pixels were verified, with hashes retained in the raw records. Median fps over three warm runs:

| Mask | Batch, 4 | Map, 4 | Batch, 8 | Map, 8 |
| --- | --- | --- | --- | --- |
| Threshold >230 | 46.61 | 47.13 | 64.41 | 62.93 |
| Cosmic Ray Mask, defaults | 5.13 | 5.32 | 7.19 | 7.17 |
| Spot Mask, mean | 11.91 | 11.99 | 19.31 | 19.67 |
| Spot Mask, median | 8.18 | 8.26 | 14.23 | 14.39 |

These short-file timings include per-file overhead and should not be compared directly with the full-file threshold row. Independent references recompute each frame's mask and integrate directly with float64 CSR weights. Maximum relative L2 error was below 1.2e-15. Tests also cover Poisson errors, azimuthal spread, strict arithmetic, counting/pixel-split/supersampled methods, units, background/correction/factor processing, mask/settings changes, plan invalidation/reuse, source/worker lifetime, ordering, cancellation and read failures. The native concurrency test checks that CSR storage and correction-array addresses remain shared and unchanged under concurrent changing masks.

Final checks passed: **283 Qt tests**, **170 Rust unit tests**, and **20 Python API regression tests**. Rust formatting, Ruff and whitespace checks passed.

The runtime is a locally built, unreleased Dioptrin wheel installed only in Qt Dioptas's `.venv`; metadata remains 0.8.0, but it is **not the published 0.8.0 wheel**. Binary/wheel/source hashes are in [provenance](2026-11-06-shared-frame-workers-provenance.json). Published 0.8.0 lacks this API and safely uses the serial-mask fallback; a Dioptrin release and dependency update are still required to ship the shared-plan path. No release, commit or push was performed.

Reproduce full-file runs with `scripts/benchmark_dynamic_frame_pool.py --workers 4` or `--workers 8`, `OMP_NUM_THREADS=1`, `OPENBLAS_NUM_THREADS=1`, and matching `RAYON_NUM_THREADS=4` or `8`. Supply `--hdf5`, `--poni`, `--mask`, `--output` as recorded in the raw JSON. For sampled batch/map masks use `scripts/benchmark_qt_eiger_masking.py --frames 16 --repeats 3 --workers N --decode-workers N --workflows batch map --cases threshold_230 cosmic_default spot_mean spot_median`, with `RAYON_NUM_THREADS=1`.

Raw results: [full 4](2026-11-06-shared-frame-workers-full-4.json), [full 8](2026-11-06-shared-frame-workers-full-8.json), [mask sample 4](2026-11-06-shared-frame-workers-4.json), [mask sample 8](2026-11-06-shared-frame-workers-8.json). The final mask-only cache-lifetime refinement does not alter the measured steady-state numerical path and is covered by the final regression suite.
