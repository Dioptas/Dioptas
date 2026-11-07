# Combined HDF5 loading and fixed-mask integration in Qt

The combined path decodes a supported frame **once** and returns both original
integer display pixels and a float64 1D pattern. Eight block workers share one
fixed lookup and own their histograms; raw histograms are merged and normalized
once. The Qt integration worker consumes the prepared result, rather than reading
or integrating the frame again. Display counts remain uint16/uint32; weights,
signal/variance sums, normalization and returned patterns remain float64.

## Matched full Qt comparison

These measurements use the real `ImageController`, `PatternController` and
`AsyncIntegrationCoordinator`, including image updates, snapshot creation,
owner-thread dispatch, pattern/plot model application and the default **25 ms
Qt debounce**. Qt is offscreen at 1200×900: CPU/event/paint preparation is measured,
while physical monitor presentation and actual GPU performance are not qualified.

| Median time (ms) | Intensity: existing | Intensity: combined | Poisson: existing | Poisson: combined |
| --- | ---: | ---: | ---: | ---: |
| Open → applied pattern | 180.41 | 143.33 | 182.16 | 144.54 |
| Open → subsequent Qt event flush | 184.98 | 148.50 | 186.96 | 149.09 |
| Load + image-controller update | 144.18 | 114.61 | 144.64 | 115.02 |
| Combined native decode + image + pattern | — | 6.68 | — | 7.37 |
| Task snapshot | 2.67 | 0.59 | 2.69 | 0.60 |
| Post-load integration worker | 6.17 | 0.13 | 6.89 | 0.19 |

Intensity: **20.6% lower open-to-pattern latency** (1.26× speed). The corresponding p95 values are 192.59 and 156.87 ms.

With Poisson errors: **20.6% lower open-to-pattern latency** (1.26× speed). The corresponding p95 values are 193.99 and 157.52 ms.

The combined worker's small post-load time is not the integration kernel time:
integration already happened during the combined native load. Image processing,
plot preparation and debounce now account for most of the full Qt latency.

The same 625-frame Eiger 9M source (3262×3108 uint32), 2000 bins, pixel splitting,
polarization 0.965, two-theta degrees, effective fixed mask and float64 arithmetic
were used in both cases. Twelve evenly spaced frames were tested in three passes
per error setting, rotating whole-pass mode order. There are 36 observations per
cell, 144 timed operations total. Each timed operation reopens its selected frame,
so neither path can reuse FabIO's decoded-currentframe cache. Compressed chunks
were warmed before timing; no decoded stack cache is retained. Other desktop
applications were active and CPUs were not isolated.

Correctness and pixel hashes were checked outside the timing interval. All sampled
combined display arrays matched the existing loader bit-for-bit, including dtype
and flipped display order; all intensity and Poisson outputs passed the float64
comparison tolerance. Every combined timed operation made exactly one native load
call and passed a prepared pattern to the coordinator, with no fused reread task.
The initial observed loads, including lookup construction, were 1.096 s for the
existing path and 0.873 s combined (one observation each, separate from warm results).

## All-frame precision and ownership validation

All **625** combined stored-order display arrays matched the independent h5py
SHA256 reference hashes exactly, including original reserved counts. Each pattern
and Poisson result was compared with the existing resident-array float64 kernel
using those returned pixels, so validation itself required no second file decode.
Maximum scaled intensity difference was **3.73e-15**, and Poisson difference
**1.71e-15**. Tolerance was absolute 1e-10 plus relative 2e-12. Reduction ordering
can change float64 rounding; no float32 geometry weights or sums are introduced.

The source adapter's arrays own their memory, retain their dtype and are read-only
through their NumPy base. Snapshots borrow those immutable pixels and matching mask
when consuming a prepared pattern. Pixel replacement, writable inputs, mask edits,
geometry/polarization/bin/unit changes or missing requested error terms invalidate
that prepared pattern and use the resident-image integration path, without rereading
the file. Compatible source files can reuse the lookup through `set_source`.

## Selection and unchanged paths

Qt installs the combined loader only on its live interactive configurations.
Automatic 1D integration, Dioptrin/CSC, valid calibration, fixed masks and an
uncorrected/untransformed image are required. Initial file opening preserves
FabIO's authoritative LImA default dataset and header facade without calling its
pixel decoder. Already selected HDF5 datasets retain their exact selection.
Full-frame Bitshuffle/LZ4 native uint16/uint32 chunks are required. Metadata,
shape/mask ambiguity or unsupported layout uses ordinary loading, once.

Dynamic masks, background subtraction, image corrections, transformations,
spread statistics, azimuthal restrictions, other backends and batch/map processing
retain their existing routes. A busy shared worker (including a bulk runner whose
Qt signals have been closed) is never waited on by a combined load; ordinary loading
is used instead. File mutation during a combined operation is an error and cannot
publish partial pixels or a partial pattern. Frozen source identity is retained
with loaded pixels to avoid mixing a replacement file with cached metadata.

Lookup setup runs on the existing native owner thread; its cost is included in a
cold load. Native objects are created/reused/closed on that thread. The synchronous
image-loading API still waits for its result. GUI generations/revisions continue
to reject stale integration deliveries. No 2D-cake algorithm is changed.

## Scope and reproduction

The earlier reread prototype's 6.5 ms array worker versus 10.5 ms fused worker
remains a valid record of that inefficient design. It loaded pixels for display
first, then decoded again. This combined path replaces that automatic reread.
The older Qt record measured models/worker only; its absolute 58/62 ms figures
must not be compared with this report's real-controller/plot/debounce scope.
Native compressed-input 5.38/6.09 ms kernel-pipeline measurements are also a
different scope from full Qt latency.

Run `scripts/benchmark_combined_hdf5.py` from the Qt checkout with the installed
source adapter, `QT_QPA_PLATFORM=offscreen RAYON_NUM_THREADS=8 OMP_NUM_THREADS=1
OPENBLAS_NUM_THREADS=1`, and the HDF5, PONI and raw calibrated uint8 mask paths.
The adapter build recipe is in `dioptrin-io/python-fused/README.md`.
`python-fused/validate_eiger.py` performs the complete count/pattern validation.
Large acquired data remain outside Git. No package publication or cross-platform
CI qualification is implied by this local macOS/M4 Pro run.
