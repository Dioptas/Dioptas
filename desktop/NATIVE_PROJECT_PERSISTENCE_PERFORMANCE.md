# Large Batch/Map project persistence benchmark

On this Mac, large unchanged projects take about **5–10 seconds to save**, with no progressive file growth in eight fresh-process reopen/save cycles. The slow path is repeated full-array serialization and compression. The prior 3,000-group microbenchmark measured a different workload.

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

## Results

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

## Reproduce and inspect

From the repository root, with the reference CPython 3.13 environment:

```sh
cargo build --release --locked --manifest-path desktop/backend/Cargo.toml --all-features --bin dioptas-processor
.venv/bin/python desktop/scripts/benchmark_project_persistence.py --output desktop/artifacts/project-persistence-benchmark/large-release --cycles 8 --edit-cycles 4
```

The helper requires NumPy, h5py and fabio from the existing reference environment, and currently records hardware using macOS sysctl. Allow several GiB for disposable fixtures/projects and additional transient archive copies. It refuses to start a case below 8 GiB free.

- [Raw per-cycle receipt](artifacts/project-persistence-benchmark/large-release/results.json)
- [Summary and dataset storage breakdown](artifacts/project-persistence-benchmark/large-release/summary.json)
- [Five-second sampled call tree](artifacts/project-persistence-benchmark/large-release/save-sample.txt)
- [Native snapshot/packet traces](artifacts/project-persistence-benchmark/large-release/profile.stderr.log)
- [Generated-file checksums and cleanup receipt](artifacts/project-persistence-benchmark/large-release/disposable-files-receipt.json)

Large generated fixtures/projects were removed after verification to recover about 8.6 GB. Exact numeric manifests, file checksums, per-cycle measurements, logs and the regeneration helper remain.

No production scientific, UI or persistence implementation was changed for this benchmark. The reusable helper and this report are local repository additions.
