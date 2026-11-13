# Single-image pyFAI-compatible integration

> Historical evidence: Python-era commands and source paths in this ledger refer to
> pre-cleanup revision `a39717a41458129ba9370c849a4121ecdbc6a444` (resolve the full revision in `../architecture/REFERENCE_DATA.md`).
> The active application and test suite are Rust/headless UI only. See
> [reference data policy](../architecture/REFERENCE_DATA.md) for retained fixtures and current checks.

November 10, 2026. This change is in the Rust/React/Tauri desktop. Qt Dioptas
and the Python bindings are unchanged.

## Implementation and numerical contract

Interactive fixed-mask uint16/uint32 images now use Dioptrin's explicit
`FixedCsr1dInputPlan::integrate_u16_parallel` / `integrate_u32_parallel` entry
points, pinned at `0c0d4fc`. The immutable plan and source-row address mapping
are shared with Batch/Map. A single image schedules independent radial bins
on the current Rayon pool; Batch/Map retain their serial-bin entry points
inside persistent frame workers.

Each bin uses the original strict scalar row kernel, coefficient order,
normalization, variance division and square root. Parallel collection preserves
the bin order. There is no FMA, coefficient regrouping or approximate arithmetic.
Integer inputs are finite and are converted to float64 at the original load
operation, avoiding the resident float64 input scan and reading the smaller
original pixel buffer instead. The oriented float64 image remains available
for display statistics, pixel inspection and the established scientific models.

The shared interactive product calculation applies this path to file opens,
frame navigation, explicit integration and integration-setting/mask changes.
Its existing scientific key invalidates geometry, units, bins, sectors and
fixed masks together. Redundant predecode masks are no longer constructed for
pyFAI requests, since the streamed Polygon decoder cannot consume them.

Corrected, transformed, derived and noninteger inputs, dynamic masks, and
azimuthal spread retain the established native resident path. Cakes still use
their existing implementation. Source-identity and cancellation checks occur
before returning the typed result, and the usual prepared-result key check
remains in place.

## Full Eiger comparison

The preserved before executable is from desktop `24883b49`. Both executables
use the same optimized development profile, eight integration/Rayon threads,
all 625 original 3262 × 3108 frames of `eiger_0000.h5`, the adjacent named-detector
PONI, 2,000 radial bins, CSR, polarization 0.965, and the automatic acquisition
mask. No corrections or dynamic masks are enabled. Cake and rings are hidden,
matching the normal Integration image view.

Two complete passes per error setting alternate old/new executions at every
frame and reverse the leading variant on successive frames and passes. There
are 5,000 timed frame-load/integration commands, 800 additional cached
integration commands, and 200 load-only controls. The test client honors the
GUI's binary-buffer cache and keeps only current-frame buffers. Hashing and
numerical comparison run outside the timed command intervals.

The workstation remained in use, including macOS indexing and other chats.
CPU snapshots are retained; these are interleaved comparisons under background
load, not isolated maximum-throughput measurements. An initial quiet-CPU gate
timed out; no user processes or previews were stopped.

Median times in milliseconds across the two complete passes:

| Poisson errors | Pattern/product calculation before → after | Complete load + integration before → after |
| --- | ---: | ---: |
| Off | 5.130 → **4.512** | 29.232 → **28.774** |
| On | 5.244 → **4.635** | 30.071 → **29.815** |

The integration stage takes **11.6–12.1% less time**. The approximately 0.3–0.5 ms
complete-command difference is small relative to the load-only control's
variation: load-only medians were 22.94–23.84 ms, with no consistent improvement.
There is no claim of a substantial improvement in overall image-loading latency.

Repeated integration of an already loaded image, with its display buffers cached:

| Poisson errors | Pattern/product calculation before → after | Complete `integrate` command before → after |
| --- | ---: | ---: |
| Off | 5.094 → **4.453** | 8.611 → **7.943** |
| On | 5.129 → **4.499** | 9.040 → **8.421** |

Initial file opening and plan construction took a median **1.427 s before** and
**1.520 s after** over four opens per executable. The new source-address mapping
adds first-use work; these shared-workstation measurements show approximately
93 ms additional startup time. It is cached for subsequent frames/settings that
retain the same scientific key. This is warm filesystem data, not cold-disk I/O.

A shorter 31-frame check spread across the entire source waited for quiet CPU
snapshots before each measurement block. The pattern stage again improved from
5.04–5.11 ms to 4.41–4.48 ms. Complete load/integration remained approximately
28–29 ms. Twenty of its 24 variant/measurement blocks had no detected heavy
external CPU work at either boundary; four overlapping background work are
retained and flagged. This corroborates the integration gain without changing
the full-series headline or implying complete workstation isolation.

[Full-series receipt](../../artifacts/native-pyfai-single-image/full.json) ·
[shorter check](../../artifacts/native-pyfai-single-image/quiet-sample.json).
Receipts retain every timed command, diagnostic deltas, executable hashes,
per-frame numerical/display signatures, raw-receipt paths and SHA256 identities.

`elapsedMs` measures the native pattern/product calculation, including mask-key
construction, the strict integration and pattern rebuilding. The complete
command additionally includes decoding, source orientation, full-resolution
display conversion/statistics, snapshot construction, binary transfer and
client receipt. These timings exclude React/GPU rendering and physical display
scanout. Initial plan construction is recorded separately from warm commands.

## Why the single-image gain is smaller than Batch/Map

Single-image CSR already parallelized bins. It also needs the oriented image
and a full-resolution display, whereas bulk workers can avoid those per-frame
products. Reading integer counts directly saves integration work, but it does
not remove the remaining decode/display/transport cost. Consequently the
roughly 200 images/s bulk measurement must not be interpreted as an interactive
image-display frame rate. The address mapping also requires additional first-use
preparation; the initial-load measurements include that cost.

macOS `sample` profiles cover separate 300-frame navigation runs, sampled for
two seconds at 1 ms intervals. They identify strict CSR, display fingerprinting,
count statistics, decoding and packet writes as active work. The optimized
trace's median strict typed kernel is **3.42 ms**. Oriented float64 preparation
still takes approximately 1.14 ms; display float32 conversion 1.16 ms,
fingerprinting 2.56 ms, count statistics 5.92 ms, and packet writing 7.40 ms.
These are stage durations from sampled runs, not additional paired benchmark
results or normalized CPU percentages. Process footprint remains approximately
3.0G in both samples. [Profile receipt](../../artifacts/native-pyfai-single-image/profile.json).

## Verification

- All 625 frames in both Poisson settings, across both full-file passes, match
  the preceding executable bit for bit in every float64 radial/intensity/error
  array and transported detector/mask pixels. Display histograms, auto levels
  and coordinate metadata also match. The source size and modification time
  remain unchanged.
- The frozen-executable regression checks pass **81 cases** across uint16,
  uint32 and float64 input. They include navigation, repeated integration,
  Poisson toggles, masks/ROI, changed bins, Q/d, wrapped sectors, solid-angle
  toggles, azimuthal spread, dynamic masks, background/flat-field corrections,
  re-enabling raw processing, transformations, and unchanged cakes.
- Dioptrin's **215 library tests** pass. The strict integer-input test now also
  compares parallel results with the float64 reference across 1/2/4-thread pools,
  both row orders/types, large counts, fractional/subnormal weights, duplicate
  indices, ragged/empty rows and partial/all masks. Both serial and parallel APIs
  reject invalid lengths. Library/tests Clippy passes with warnings denied.
- Desktop **190 Rust tests** pass, with two existing opt-in tests ignored. A new
  interactive regression compares integer and float64 reference patterns at
  the bit level and checks warm navigation/key invalidation and fallback paths.
  All-target Clippy, TypeScript/Vite build, **nine real-stdio transport tests**
  and the headless Chromium/WebKit native integration workflows pass. The merged
  primary checkout also passes the new interactive regression. Its fresh executable
  reproduces the measured optimized executable bit for bit at Eiger frames
  0, 312 and 624 with both Poisson settings and cached reintegration; these
  correctness-only timings are not used in the performance table.

[Frozen-executable comparisons](../../artifacts/native-pyfai-single-image/parity.json) ·
[verification receipt](../../artifacts/native-pyfai-single-image/validation.json) ·
[fresh primary executable](../../artifacts/native-pyfai-single-image/main-validation.json).

## Reproduction

From the desktop checkout, using the preserved executables:

```sh
python scripts/native_pyfai_single_benchmark.py \
  --source /path/to/eiger_0000.h5 \
  --before /path/to/dioptas-processor-before \
  --after /path/to/dioptas-processor-after \
  --output /path/to/results --frames 625 --repeats 2
python scripts/native_pyfai_single_parity.py \
  --before /path/to/dioptas-processor-before \
  --after /path/to/dioptas-processor-after \
  --output /path/to/parity.json
```

The scripts are test clients only. Production loading and integration remain
Rust/Dioptrin over Tauri-owned stdio.
