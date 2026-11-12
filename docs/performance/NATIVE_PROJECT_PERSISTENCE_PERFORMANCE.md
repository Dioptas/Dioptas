# Large Batch/Map project persistence benchmark

After dataset reuse and shared compatibility storage, repeated saves of these large projects take **0.81–1.38 seconds median**, improved from **4.96–10.23 seconds**. All five cases have zero file growth across eight reopen/save cycles. Every logical numeric dataset, including compatibility aliases, matches the pre-optimization baseline bit-for-bit. The earlier 3,000-group microbenchmark measures a different workload.

## Workloads and method

- Date: November 12, 2026; source `7b7081f722a675c3fe17a75cda4a5eba84d96f4b`.
- Apple M4 Pro, 14 cores, 48 GiB RAM, macOS 26.6.2, local APFS storage.
- Real release Rust processor built with `--release --locked --all-features`. The exact binary SHA-256 and environment are in the raw receipt.
- Measured CeO₂/Pilatus1M diffraction data seeds varied synthetic profiles with small peak shifts, changing scale, noise, and positive counting std. These are representative project volumes, not a real 10,000/20,000-frame experimental acquisition.
- Each project has normalized profiles with original data/std retained. Map has six ROI reductions, an expression layer, snake arrangement and a selected point. Every configuration also has a full-resolution measured detector cache. The combined case duplicates both views into two configurations.
- Source metadata models 500-frame HDF5 stacks or one file per frame. Raw source paths are deliberately offline; the actual series data and detector cache are embedded in the project.
- Initial creation is followed by eight cycles. Every reopen uses a fresh Rust process. Filesystem caches remain warm; no OS cache purge or visible application window is used.
- Timings cover the public Rust stdio command, including response receipt/JSON decode/cache processing. Saves include the real HDF5 writer, compaction, file sync and atomic publication. Process startup, fixture generation and verification are outside the timer. React rendering and Tauri IPC overhead are outside this benchmark.
- Every numeric dataset is streamed and checked by exact byte hashes after every cycle. Source matrices and counting std are checked against the generated input. Restored selection, normalization, axes, Batch entries, Map values, ROI/expression state and grid settings are also compared.

## Baseline results

GB means 1,000,000,000 bytes. Repeated-save and reopen figures are medians of eight independent cycles; the initial save is separate.

| Project | Archive GB | Initial save s | Repeat save s (range) | Reopen s (range) | Size change after eight cycles |
| --- | ---: | ---: | ---: | ---: | ---: |
| Batch, 10,000 × 2,048; 20 stack paths | 1.165 | 11.02 | 9.41 (8.70–10.47) | 1.60 (1.27–2.36) | 0 B |
| Batch, 10,000 × 2,048; 10,000 file paths | 1.167 | 9.03 | 9.56 (9.14–10.82) | 1.68 (1.26–2.59) | 0 B |
| Map, 20,000 × 1,024; 100 × 200 grid | 0.915 | 4.86 | 5.02 (4.82–5.39) | 1.34 (1.13–1.49) | 0 B |
| Map, 10,000 × 2,048; 100 × 100 grid | 0.915 | 4.69 | 4.96 (4.74–5.33) | 1.17 (0.99–1.35) | 0 B |
| Batch + Map, 5,000 × 2,048 each, two configurations | 1.759 | 8.54 | 10.23 (9.33–12.74) | 2.59 (1.97–3.16) | -2,197 B |

The two-configuration archive shrank by 2,197 bytes on its first reopen/save, then remained exactly the same length for cycles 2–8. The other four archives stayed exactly the same length for all cycles. Filesystem allocated-block counts also stayed constant within each case after that initial transition. All numeric-content and restored-state comparisons passed.

## Replacing cached detector images

Four additional edits replace the active detector image in the combined project while preserving the large Batch/Map matrices. Each edit is saved, reopened in a new worker, saved again and verified.

| Edit | Save s | Reopen s | Verification resave s | Archive bytes | Live image caches |
| --- | ---: | ---: | ---: | ---: | ---: |
| 1 | 11.37 | 2.46 | 9.45 | 1,763,373,623 | 2 |
| 2 | 8.59 | 2.55 | 8.72 | 1,763,371,196 | 2 |
| 3 | 9.17 | 2.35 | 9.85 | 1,763,374,911 | 2 |
| 4 | 9.66 | 1.99 | 8.60 | 1,763,351,668 | 2 |

The first edit adds one distinct cached image because the inactive configuration still references the original. Later edits retain exactly two caches: the inactive original and the current active image. Replaced active images do not accumulate. Small size fluctuations reflect compression of changed image values; all Batch/Map numeric datasets remain exact.

## Why saves remain slow

The writer copies the retained archive into a private working file, serializes configuration series, writes selected-view compatibility data, prunes obsolete native arrays, copies reachable objects into a fresh compact archive, then syncs and publishes it. This bounds growth but still processes large unchanged matrices.

For the 10,000 × 2,048 Batch case, stored dataset payloads include **656.3 MB of native series data** and **507.5 MB of Batch compatibility data**, plus approximately 1.1 MB of image/small-array pools. Normalization legitimately retains originals and counting std; the compatibility representation additionally duplicates those matrices. Exact hashes confirm that all four large native matrices (normalized intensity/std and original intensity/std) each have a byte-identical compatibility counterpart.

A separate sampled save, excluded from the timing distribution above, took **9.195 s wall time and 8.20 CPU-seconds**. In its five-second middle window, all 449 save-worker samples were under `save_active_extensions`; 431 (96.0%) were under the HDF5 deflate filter/zlib. This is a sampled-window result, not a claim that exactly 96% of the entire save is compression.

The same run's final response snapshot took 176.1 ms; response encoding and writing took 4.8 ms. The profile supports prioritizing reuse of unchanged matrices and avoiding duplicate compression of compatibility representations. A full incremental-save design must also preserve atomicity, cancellation, unknown extensions and existing readers.

## Optimized results

Optimized implementation benchmark source: `7096247783fbf19006031d3fdffd2a1a9979c14c`; baseline science source: `7b7081f722a675c3fe17a75cda4a5eba84d96f4b`. Same release build profile, machine, fixture generator, dimensions, source metadata, normalization and eight fresh-process cycles. Timings are medians; filesystem caches remain warm.

| Case | Save before → after s | Speedup | Reopen before → after s | Archive before → after GB | Growth over eight cycles |
| --- | ---: | ---: | ---: | ---: | ---: |
| batch-stack | 9.41 → 1.38 | 6.8× | 1.60 → 0.98 | 1.165 → 0.658 | 0 B |
| batch-tiffs | 9.56 → 1.24 | 7.7× | 1.68 → 1.03 | 1.167 → 0.659 | 0 B |
| map-stack | 5.02 → 0.87 | 5.8× | 1.34 → 0.84 | 0.915 → 0.660 | 0 B |
| map-tiffs | 4.96 → 0.81 | 6.1× | 1.17 → 0.80 | 0.915 → 0.660 | 0 B |
| combined-two-config | 10.23 → 0.94 | 10.9× | 2.59 → 1.39 | 1.759 → 0.659 | 0 B |

Per-case save ranges are retained in the JSON receipt; the Map-stack run includes one 3.84 s outlier. No samples are discarded. Each first save and all repeated saves are separately recorded.

Native series now read/write directly within project groups. Compatibility matrices are hard links to the corresponding native f64 datasets, avoiding duplicate serialization/compression. Same-allocation arrays can share storage across views/configurations within a save. An archive-scoped weak allocation proof also reuses unchanged loaded arrays, including their attributes, after configuration staging/reindexing. Shape, canonical dtype, axis unit, file ownership and internal storage must match. External, virtual, converted and transformed legacy data are written from the current owned Vec.

Atomic saves still copy and compact the archive. This is not a fully incremental file format. The retained source archive is the one opened by the session: newly computed/replaced arrays share within a save, but gain cross-save archive provenance after reopening. This preserves existing unknown-extension and rollback behavior while removing the measured compression bottleneck.

All 142 logical numeric datasets across the five final archives match the baseline byte hashes, despite having fewer physical dataset objects. Original input/std hashes and the per-cycle restored-state assertions also pass. Four image replacements retain exactly two live image caches, with exact Batch/Map matrices and exact edited reopen/resave checks.

Additional regressions cover immutable-read reuse, metadata-only changes, sub-f32 scientific changes, normalization toggle/restoration, counting std/spread/background roles, converted dtype promotion, external raw/VDS/foreign-link changes after load, staging-name collisions, and the existing atomic cancellation/opaque-reference boundaries. The extended independent Python project qualification checks native ↔ Qt/Python reader/writer behavior and configuration independence.

- [Optimized per-cycle results](../../artifacts/project-persistence-benchmark/optimized-release/results.json)
- [Baseline comparison and all-case logical-data verification](../../artifacts/project-persistence-benchmark/optimized-release/comparison.json)

## Reproduce and inspect

From the repository root, with the reference CPython 3.13 environment:

```sh
cargo build --release --locked --manifest-path backend/Cargo.toml --all-features --bin dioptas-processor
.venv/bin/python scripts/benchmark_project_persistence.py --output artifacts/project-persistence-benchmark/large-release --cycles 8 --edit-cycles 4
```

The helper requires NumPy, h5py and fabio from the existing reference environment, and currently records hardware using macOS sysctl. Allow several GiB for disposable fixtures/projects and additional transient archive copies. It refuses to start a case below 8 GiB free.

- [Raw per-cycle receipt](../../artifacts/project-persistence-benchmark/large-release/results.json)
- [Summary and dataset storage breakdown](../../artifacts/project-persistence-benchmark/large-release/summary.json)
- [Five-second sampled call tree](../../artifacts/project-persistence-benchmark/large-release/save-sample.txt)
- [Native snapshot/packet traces](../../artifacts/project-persistence-benchmark/large-release/profile.stderr.log)
- [Generated-file checksums and cleanup receipt](../../artifacts/project-persistence-benchmark/large-release/disposable-files-receipt.json)

Large generated fixtures/projects were removed after verification to recover about 8.6 GB. Exact numeric manifests, file checksums, per-cycle measurements, logs and the regeneration helper remain.

The baseline measurement itself changed no processing code. The optimized writer changes storage ownership and serialization, retaining scientific values and existing paths; no UI controls or scientific algorithms were changed.
