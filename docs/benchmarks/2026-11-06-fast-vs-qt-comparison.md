# Old fast pipeline versus current Qt Dioptas

2026-11-06. Actual same-machine comparison, not a comparison between unmatched
historical benchmark numbers. No production code was changed for this study.

## Main result

The earlier high speed is reproducible. The archived reusable-buffer recipe
measured **177.9 fps median**, with individual passes
from 164.6 to 192.7 fps. That overlaps the older roughly 193 fps result under
normal concurrent host-load variation. The current Qt Map path measured
**114.4 fps** once it was given the same eight decoding and
eight single-thread integration workers. The recent roughly 19 fps fixed-mask
measurement used only one decoder and a short sampled file.

This full-file comparison uses all **625 original Eiger9M frames**, the supplied
static mask, the same installed Dioptrin 0.8.0 kernel, float64 arithmetic and
matched numerical geometry/corrections. The old path uses Jon's decompressor
only; it does not use his float32 integration weights or integration kernel.

## Fixed mask: full-file throughput

Three paired/reordered full-file passes per pipeline; medians below. Eight
decoder workers, eight integration workers with one thread each. The synchronous
NumPy batch API uses global Rayon, while streaming uses private worker pools;
both were explicitly configured for eight-way integration. Initial trial data
with an unmatched global pool were discarded and are not in these artifacts.

| Pipeline | fps | Seconds / 625 frames |
| --- | ---: | ---: |
| Archived recipe: mmap + fast decoder + reused buffers | 177.88 | 3.51 |
| Same fast decoder, allocated float64 frames | 185.72 | 3.37 |
| Qt decoder + HDF5 chunks, grouped integration | 103.19 | 6.06 |
| Qt reader streamed directly to Dioptrin | 118.25 | 5.29 |
| Current Qt MapModel | 114.43 | 5.46 |
| Fast decoder streamed directly to Dioptrin | 164.45 | 3.80 |
| Qt MapModel + fast-decoder adapter | 160.07 | 3.90 |
| Qt decoder + mmap chunks, grouped integration | 112.95 | 5.53 |
| Fast decoder + HDF5 chunks, grouped integration | 180.54 | 3.46 |

## Where the time goes

With identical grouped scheduling and native integration:

| Stage, full 625-frame file | Fast decoder recipe | Qt decoder recipe |
| --- | ---: | ---: |
| Read compressed data + decode + flip + float64 preparation | 1.83 s | 4.42 s |
| Native integration + result collection | 1.68 s | 1.65 s |

These grouped stages run consecutively, so their wall times can be interpreted
separately. Stage medians need not add exactly to median total time. Summed
worker timings overlap and are not added to wall-clock totals.

The native integration time is essentially unchanged. The main difference is
the decode implementation and its buffer/data path. The crossover tests isolate
it further: the fast decoder still delivers **180.5 fps**
when compressed chunks are read through the same HDF5 `read_direct_chunk` API.
Conversely, moving the Qt decoder to mmap yields only
**113.0 fps**. HDF5 chunk reading alone therefore
does not explain the gap. This experiment groups decoder implementation and
its internal allocations; it does not claim an instruction-level decomposition
of that decoder's cost.

The Qt model layer itself is a comparatively small cost: with the same Qt
reader, direct streaming measured 118.2 fps versus
114.4 fps through MapModel. With the fast decoder, the
corresponding rates were 164.4 and
160.1 fps. MapModel evaluated `img_data`
only once per full static-mask file, allocating about 81 MB total through that
getter, rather than once per frame. Getter copies are not the remaining main
bottleneck on this fixed-mask path.

Reusing float64 frame buffers was not independently faster in this run: the
allocation control's range overlapped the reused-buffer recipe. The data do not
support attributing the principal speed gap to those allocations alone.

## Dynamic threshold mask: matched processing and reader adapters

A separate 16-frame sample spans the original scan, retaining exact compressed
chunks and checked decoded pixels. All paths apply the **same static mask OR
built-in threshold >230**, using the same Configuration image preparation,
plugin computation, normalization and integration. Within-frame Rayon is eight
threads; threshold NumPy operations remain serial. Three warmed passes per path.

| Pipeline | fps |
| --- | ---: |
| Old fast grouped decode + Qt per-frame processing | 65.84 |
| Qt grouped decode + same Qt per-frame processing | 49.14 |
| Current Qt dynamic Map path (serial frame reader) | 18.12 |
| Qt Map + serial HDF5-reader adapter | 19.54 |
| Qt Map + parallel HDF5-reader adapter | 57.76 |

The two grouped variants have **eight actual decoder workers** and identical
per-frame Qt masking/integration work, isolating their decoder stages. Current
Qt's dynamic Map path is included as the real baseline, but cannot be called a
matched-eight-decoder path: it switches to sequential frame loading. The default
loader for this file is `FabioLoader` wrapping `fabio.limaimage.LimaImage`.
Switching only to serial HDF5 has a small effect. The benchmark adapter that
selects the existing HDF5 reader and enables eight-worker prefetch reaches
**57.8 fps** versus
**18.1 fps** currently, a
**3.19×** gain.

The adapter retains the actual MapModel loop; it only changes reader selection
and prefetch. Frames remain independently owned while prefetched/native work is
in flight. Dynamic masks and integration are still processed one frame at a
time. They have not been parallelized across frames in this benchmark.

This identifies two practical improvements: keep parallel prefetch available
when dynamic masking is enabled, and improve/replace the current decode path.
It does not require rewriting the Qt model or reducing integration precision.
Neither adapter has been installed into production code by this study.

## Validation and measurement boundaries

- All 27 measured full-file passes checked all 625 patterns against a common
  native reference, including the decoder/I/O crossovers. Largest relative L2
  difference was 0.
- All 15 dynamic sample passes matched the same reference, with actual dynamic
  mask mode and threshold plugin verified. Raw results retain per-pass errors.
- Eight decoder workers and eight one-thread batch workers were matched in the
  fixed-path cases. Fixed streaming may overlap both pools; grouped variants
  run consecutive stages. Process CPU usage and concurrent host load are in JSON.
- All use 2000 2theta bins, full pixel splitting, solid-angle correction,
  polarization .965, float64 weights/corrections/sums, no Poisson errors, factor
  1 and no background. The user mask and calibration hashes are recorded.
- One file's real compressed frame accesses, decoding, orientation conversion,
  integration and results are timed. Qt also opens metadata/loads its initial
  image each run. LUT/mask setup, initial chunk indexing/mmap opening and warmup
  are excluded. OS cache was warm; these are not cold SSD bandwidth results.
- The 625-frame fixed-mask comparison reads the original file directly. Dynamic
  sampling uses a temporary APFS clone with exact chunks; original input is
  read-only. GUI rendering is excluded. Concurrent user jobs were not stopped.
- Old codec is the pinned 0.0.22a3 build at `94264db`, loaded by explicit package
  path without changing Qt dependencies. Source/build hashes and package
  versions are retained. Published Dioptrin 0.8.0 is used throughout; the local
  unreleased setter guard is not needed because Qt already avoids redundant
  polarization updates.

## Artifacts and reproduction

Run from the Qt checkout, with `OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
RAYON_NUM_THREADS=8`:

- `python -m scripts.compare_fast_and_qt_eiger --help`: full-file comparison;
  use `--workers 8 --repeats 3`, same source/calibration/mask paths as previous
  reports, and the pinned `--old-package` directory recorded in JSON. To isolate
  the I/O crossovers, use `--only qt_mmap_decoder_grouped old_hdf_decoder_grouped`.
- `python -m scripts.compare_qt_dynamic_readers --help`: the dynamic sample;
  use `--workers 8 --frames 16 --repeats 3` and the same input/package paths.

[Full-file raw data](2026-11-06-fast-vs-qt-full-file.json),
[I/O crossover raw data](2026-11-06-fast-vs-qt-io-crossover.json),
[dynamic-reader raw data](2026-11-06-fast-vs-qt-dynamic-readers.json),
[CSV summary](2026-11-06-fast-vs-qt-comparison.csv).

Scripts, measurements and previous Qt changes remain local and uncommitted.
