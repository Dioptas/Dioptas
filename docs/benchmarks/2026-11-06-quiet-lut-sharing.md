# Controlled lookup-table sharing comparison, 2026-11-06

Sharing the lookup table shows no meaningful steady-state throughput change in this experiment. Four workers deliver approximately 90 fps and eight approximately 145 fps, either way. The median paired sharing effect is −0.28% and +0.55%, respectively, smaller than observed run-to-run variability. These measurements do not establish exact equivalence or a quiet-machine upper limit.

| Workers | Paired passes | Separate-plan median fps | Shared-plan median fps | Median paired shared/separate difference | Other busy cores: separate / shared |
| --- | --- | --- | --- | --- | --- |
| 4 | 5 | 87.95 | 89.52 | -0.28% | 2.29 / 2.22 |
| 8 | 10 | 145.22 | 145.08 | +0.55% | 2.71 / 3.50 |

The same full original Eiger file was used: `/Users/clemens/Programming/Dioptrin/test_data/eiger_0000.h5`, 625 uint32 frames of 3262×3108 pixels, dataset `/entry_0000/instrument/eiger/data`. Calibration and static mask are the same files as the preceding comparisons. Integration settings: 2000 two-theta bins, pixel splitting, solid angle, polarization 0.965, float64 weights/corrections/accumulators, static mask plus a threshold >230 mask recomputed every frame, no Poisson errors or azimuthal spread.

This comparison deliberately isolates ownership of prepared tables. Both variants use the **same locally built Dioptrin binary, the same borrowed-array worker API, and the same production Qt MapModel frame pipeline**. The shared variant uses one immutable plan. A benchmark-only factory gives every worker a separate immutable plan for the control variant. Both use one native compute thread per complete frame job, identical image processing and masks, independent frame normalization, the same reader, and ordered result collection. The older separate-integrator prototype also copied images through the streaming API, so it would not isolate sharing alone.

Warm trials alternate AB/BA order. Both pools stay prepared and resident, avoiding repeated setup between timed trials. Four workers received five paired passes; eight received two sets of five pairs, with the repeat announced because background load differed between variants in the first set. All samples from both eight-worker sets are retained and included above; none were discarded. Pairs follow adjacent recorded samples. Median paired percentage is calculated from each pair's shared/separate fps ratio; it can differ from the ratio of the two independent throughput medians when load drifts.

The heavy previous load had cleared, but the machine was not completely idle: one PhaseSmith solver was initially observed, and a later three-second check showed a `refit-bank-fast-` process using about 1.16 cores and total system activity about 1.79 cores. No user process was stopped or modified. Background bursts occurred during measurements: eight-worker shared trials had median other busy-core use 3.50 versus 2.71 for separate plans. Thus the conclusion is absence of a clear sharing-related speed penalty, not proof that every timing difference is noise. Observed ranges were 83.78–95.06 / 86.95–94.27 fps for four-worker shared/separate, and 134.41–157.09 / 125.40–156.50 for eight-worker shared/separate.

Every timed run checked all 625 frame indices, the requested number of actual frame-worker threads, one native compute thread per worker, and exactly one versus four/eight worker plan identities. Plan identities stayed unchanged across warm passes. Every pattern matched the reference exactly: relative L2 error **0.0**. Source-file size and modification time remained unchanged. Native binary, script, mask and calibration hashes are recorded in the raw JSON.

Times include opening the file, snapshotting, reading/decompression, image processing, dynamic masking, normalization, integration and map assembly. Configuration creation and GUI rendering are excluded. These are repeated-file/OS-cache measurements, not cold-SSD throughput. Warm process RSS includes both resident pools, so it is **not a per-variant memory comparison**. First-use timings also depend on setup order and the common prepared parent plan, so they are not isolated startup benchmarks. The architectural memory benefit is that shared workers reference one geometry/CSR/CSC/correction allocation rather than independently allocated copies.

Only the benchmark script and these results were added in this comparison; production processing code was not changed.

Reproduction: `scripts/benchmark_lut_sharing.py --workers 4 --repeats 5` or `--workers 8 --repeats 5`, with `OMP_NUM_THREADS=1`, `OPENBLAS_NUM_THREADS=1`, and `RAYON_NUM_THREADS` matching the worker count. Supply `--hdf5`, `--poni`, `--mask`, `--output` as recorded in the JSON. The script verifies the real numerical outputs during every run.

Raw records: [4 workers](2026-11-06-quiet-lut-sharing-4.json), [8 workers, first set](2026-11-06-quiet-lut-sharing-8.json), [8 workers, repeat](2026-11-06-quiet-lut-sharing-8-repeat.json), [combined summary](2026-11-06-quiet-lut-sharing-summary.json).
