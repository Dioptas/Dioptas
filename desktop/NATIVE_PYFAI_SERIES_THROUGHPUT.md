# pyFAI-compatible throughput: direct decoder input

> Historical evidence: Python-era commands and source paths in this ledger refer to
> pre-cleanup revision `a39717a41458129ba9370c849a4121ecdbc6a444` (resolve the full revision in `REFERENCE_DATA.md`).
> The active application and test suite are Rust/headless UI only. See
> [reference data policy](REFERENCE_DATA.md) for retained fixtures and current checks.

November 10, 2026. Raw, fixed-mask pyFAI-compatible Batch and Map integration
now uses Dioptrin's `FixedCsr1dInputPlan`, pinned at public revision `a10f3d6`.
It retains the previous compatibility weights and strict arithmetic while
reading uint16/uint32 decoder buffers directly. Corrected pixels, dynamic masks
and azimuthal-spread requests retain their established dynamic-plan path.

## Why the preceding path was slower than polygon

Both paths already processed frames concurrently. Polygon's pixel-oriented
kernel consumed the decoder's native integer pixels. The compatibility path
first expanded and vertically flipped each frame into float64, then handed
CSR integration to a second worker thread in a private Rayon pool.

For each 3262 × 3108 Eiger frame, the expansion materialized **81,106,368 bytes**
of float64 values from 40,553,184 bytes of uint32 counts. Over 625 frames, that
means approximately **50.7 GB of expanded values written**, followed by CSR
reads from the larger input representation. These are logical data volumes,
not a measurement of physical DRAM traffic.

The two methods also have different lookup weights and execution policies.
Compatibility uses the strict CSR row order; polygon uses its streamed
pixel-oriented kernel. The splitting geometry is prepared once in both paths,
so repeated polygon clipping is not the per-frame bottleneck here.

macOS process sampling confirmed the strict CSR reductions as the dominant
active stack (6,038 collapsed leaf samples), followed by float64 expansion
(2,066) and the main Bitshuffle decoding stacks (1,502). The optimized sample
contains no expansion stack; strict typed CSR and decoding remain the main
work. Reported process footprint fell from approximately 3.7G to 3.2G.
These samples attribute hotspots; their counts are not normalized percentages
or throughput measurements. [Profile summary](artifacts/native-pyfai-throughput/profile.json).

## Optimization and unchanged results

The new immutable input plan shares the original `Arc<FixedCsr1dPlan>`, including
its coefficients, fixed mask and cached normalization. It maps CSR column
addresses to the decoder's row order **once per scientific key**. Per-frame
loads convert each integer to float64 at the original arithmetic operation.
The eight persistent frame workers perform the strict kernel directly, removing
the expanded image buffer, flip pass and second-thread handoff.

For a calibrated pixel `j = row × width + column`, the source address is
`(height - 1 - row) × width + column`. This reads exactly the value previously
stored at `expanded[j]`. Coefficients and entries within each bin stay in their
original order. The implementation reuses the original strict scalar row kernel:
no FMA, reassociation, coefficient regrouping, reciprocal normalization or
changed variance/square-root order was introduced. Resident float64 integration
and the corrected/dynamic-mask paths remain available with their existing behavior.

## Full original Eiger series

All **625 frames**, 2,000 bins, named-detector PONI, automatic acquisition mask,
polarization 0.965, CSR resident setting, no image corrections or dynamic masks.
Both compatibility variants already use eight frame workers. Medians are taken
from two full-file passes per variant with order reversed for the second pass.
The polygon control uses the same flags and two full-file passes per case.

| View / Poisson errors | Previous compatibility, images/s | Optimized compatibility, images/s | Polygon control, images/s | Compatibility speedup |
| --- | ---: | ---: | ---: | ---: |
| Batch / off | 129.27 | **202.07** | 199.75 | 1.56× |
| Batch / on | 125.57 | **199.45** | 185.22 | 1.59× |
| Map / off | 126.67 | **198.20** | 211.62 | 1.56× |
| Map / on | 127.52 | **202.93** | 185.23 | 1.59× |

Compatibility now runs in the same throughput range as polygon on this workload.
The control does not imply that their different splitting methods produce
identical profiles.

Every float64 **bit** of every stored compatibility intensity, radial coordinate,
counting std and Map value matches the preserved preceding executable across
all 16 accepted before/after commands. Maximum absolute difference is zero.
All eight polygon-control commands likewise reproduce their own reference bits.
Each parallel command processes 625 frames with eight worker starts, one source
pipeline and zero additional pattern/dynamic plan builds after warmup. Source
size and modification time remain unchanged.

Initial exploratory timing overlapped unrelated builds/processing. The final
experiment waits for quiet CPU snapshots before each command and retries detected
overlaps, retaining their timing and process metadata in `contendedAttempts`.
The compatibility receipt records nine rejected timing attempts; the polygon
receipt records seven. The acceptance rule uses unrelated process CPU before/after
the command, not its measured speed. This is a contention check, not hardware
CPU isolation. Raw exploratory runs remain available locally.

Timings include the full native command, worker startup, ordered collection,
final selection and Map previews/reduction. They exclude initial geometry/plan
warmup, process startup, exports/parity checks and GUI rendering. Cake and rings
are hidden, as in the ordinary Integration image view. OS file pages are warm.
These are native-command images/s, not display-refresh rates.

[Paired compatibility receipt](artifacts/native-pyfai-throughput/paired.json) ·
[Polygon control](artifacts/native-pyfai-throughput/polygon.json).

## GUI observations and main-checkout integration

A fresh main-checkout build also passes four full-file bitwise comparisons
against the preserved preceding reference, after integrating other concurrent
desktop changes. Its 188 Rust tests and strict Clippy pass. This validation ran
under background CPU activity; its timings are not used in the quiet-CPU table.
[Main-checkout validation](artifacts/native-pyfai-throughput/main-bitwise-validation.json).

An isolated Tauri/WKWebView run of the normal Batch load action uses the current
main checkout, production binary IPC and GPU rendering for all 625 frames:

| Poisson errors | First load, seconds | First load, images/s | Repeated load, seconds | Repeated load, images/s |
| --- | ---: | ---: | ---: | ---: |
| Off | 5.984 | 104.45 | 3.905 | 160.05 |
| On | 3.280 | 190.55 | 3.240 | 192.90 |

These are unisolated GUI observations while background indexing and other
checks were active, rather than a controlled Poisson-error cost comparison.
The repeated Poisson run reaches about 193 images/s, versus approximately 115
in the previous GUI measurement. Use the paired quiet-CPU commands above to
assess the core optimization. GUI rates include native execution, normal React
processing, GPU completion and paint opportunities; initial image/calibration
setup and the OS picker are excluded. Physical LCD scanout is not measured.
[GUI receipt](artifacts/native-pyfai-throughput/gui.json).

All four GUI commands report 625 parallel frames, eight workers and visible
live rates. The private test window requested no keyboard focus and was closed
with only its own processing child; a user preview is still running.
Headless Chromium/WebKit Map checks also pass, including detached previews,
unfinished cells, retained regions/expressions and live rate arithmetic. The
synthetic progress fixture now has 8,192 frames so the faster kernels leave a
reliably observable interval for polling. [Headless receipt](artifacts/native-pyfai-throughput/headless-map.json).

## Validation and reproduction

All **215 Dioptrin library tests** and strict library/test Clippy pass, including
bitwise typed-versus-float64 tests for both integer types and input orders,
ragged/empty rows, duplicate/unsorted indices, fractional/subnormal weights,
partial/all masks, large counts, errors on/off, invalid-input recovery and
concurrent plan use. A pre-existing dynamic-plan test needed a missing borrow
to compile; production dynamic behavior was unchanged.

The desktop's **182 Rust tests**, strict all-target Clippy, 18 preserved-binary
numerical scenarios across Batch/Map, and nine cancellation/source-mutation
transport scenarios pass with the pinned public dependency. Numerical scenarios
include corrections, dynamic/disabled masks, sectors, spread, Q/d units,
solid-angle correction disabled, multiple sources and strided selection.
[Validation summary](artifacts/native-pyfai-throughput/validation.json).

```sh
python desktop/scripts/native_pyfai_series_benchmark.py \
  --source /path/to/eiger_0000.h5 --parallel-before --bitwise --wait-idle \
  --before /path/to/preceding-parallel/dioptas-processor \
  --after desktop/backend/target/debug/dioptas-processor \
  --output /tmp/pyfai-throughput/paired.json
python desktop/scripts/native_pyfai_series_benchmark.py \
  --source /path/to/eiger_0000.h5 --method polygon --variants after \
  --bitwise --wait-idle \
  --before /path/to/preceding-parallel/dioptas-processor \
  --after desktop/backend/target/debug/dioptas-processor \
  --output /tmp/polygon-control/results.json
```

Full profiling samples, raw logs, receipts and reference matrices are retained
under `/Users/clemens/Codex/dioptas-pyfai-throughput-20261110`.
