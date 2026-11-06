# Lookup-table sharing retry, 2026-11-06

Repeated at the user's request with the same full 625-frame Eiger file, calibration, original static mask plus threshold >230, 2000 two-theta bins, pixel splitting, polarization 0.965, solid-angle correction, and float64 arithmetic. Five alternating paired passes per worker count. Same native binary and borrowed-array worker API for both variants; the only intended difference is one shared prepared plan versus one prepared plan per frame worker. Each frame job includes reading/decompression, image preparation, dynamic masking, normalization, integration and map assembly, with one native compute thread per job. GUI rendering and initial Configuration construction are excluded.

| Workers | Separate-table median fps | Shared-table median fps | Median other busy cores: separate / shared |
| --- | --- | --- | --- |
| 4 | 81.41 | 82.65 | 6.05 / 4.90 |
| 8 | 109.57 | 105.51 | 7.18 / 8.07 |

**This retry was not a quiet-machine experiment.** Before the first benchmark, four cores were already at 100%, with substantial activity on the other cores. The four-worker warm trials recorded approximately 4–7 other busy cores. The eight-worker trials recorded approximately 4–9 other busy cores, rising during the run: separate-table fps ranged from 94.27 to 149.50, and shared-table fps from 95.49 to 140.74. This changing load prevents attributing the small median difference to table sharing. No other process was stopped or modified.

All frame indices and worker counts were checked; all outputs matched exactly (relative L2 error 0.0). Plan identities remained stable across warm passes, with exactly one shared identity versus four/eight separate identities. The source file remained unchanged. Both pools remained resident for alternating warm trials, so process RSS is not a per-variant memory measurement. First-use times depend on setup order and are not isolated startup measurements.

Method and reproduction commands are unchanged from [the preceding controlled comparison](2026-11-06-quiet-lut-sharing.md). No production processing code was changed for this retry.

Raw results: [4 workers](2026-11-06-quiet-lut-sharing-retry-4.json), [8 workers](2026-11-06-quiet-lut-sharing-retry-8.json), [summary](2026-11-06-quiet-lut-sharing-retry-summary.json).
