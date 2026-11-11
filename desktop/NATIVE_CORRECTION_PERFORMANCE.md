# Correction calculation and Plot performance

All eight Integration correction previews now reuse their processing maps:
flat field, transfer, cBN seat, plate, slab, cylinder, sphere and detector
absorption. The native command and full-resolution scientific/display contracts
are unchanged. No processing server or production Python path is involved.

The latest update queues histogram, default levels and plot-buffer preparation
on one background display worker. Apply returns without waiting for preview
preparation or transfer. The frontend quietly preloads ready buffers; Plot then
uses the cached fast path. An early Plot joins the matching in-flight job.
Plot is now a compact icon/text action beside Apply rather than a separate
right-aligned row.

## Removed repeated work

- cBN/plate/slab kernels parse their numeric parameters and prepare constant
  geometry once, then evaluate independent pixels in the selected native worker
  pool. The former scalar formulas remain as independent test oracles.
- One shared angular workspace serves the remaining analytical corrections for
  a given physical geometry and image shape. Deterministic correction maps are
  shared across single-image processing, Batch/Map snapshots and previews.
  Snapshots can populate the shared cache, rather than losing newly built maps
  when a temporary Processing clone is dropped.
- Flat-field transformations and transfer gains are keyed by source-array
  identity, source shape and transformations. The transfer preview retains the
  established reciprocal-of-gain convention and its floating-point operation
  order. Replacing a reference invalidates it even if its filename is unchanged.
- Embedded attenuation data are decoded once per process; formula and energy
  evaluation still follows the current material and calibration wavelength.
- Plot retains the most recent full-resolution display buffer, histogram and
  levels. An unchanged replot returns that raster; the transport omits display
  bytes already advertised by the client. Changing Auto settings reuses the same
  pixels and histogram and updates only the levels.
- First Plot computes correction-specific levels directly. It no longer builds
  ordinary detector levels and then overwrites them. Exact percentile ranks are
  located with the histogram, followed by selection of the original float64
  samples in those buckets. This removes full-image percentile copies and
  selection without approximating the quantiles or subsampling pixels.

Each correction keeps at most one map. An additional 256 MiB LRU budget bounds
retained maps (a single oversized current map is permitted). The cache also
keeps one angular workspace and per-correction preview rasters with a separate
256 MiB LRU budget covering their pinned float64 maps and display bytes (one
oversized current preview is permitted). Processing snapshots retain their
required Arcs independently. Caches are disposable, excluded from saved
projects/checkpoints, and do not participate in scientific equality or Undo.
Geometry, shape, resolved attenuation, parameters and reference/transform changes
are checked before reuse; cancellation and invalid maps are never published.

## Native command measurements

November 11, 2026, development build on this Mac; synthetic full-resolution
1024 × 1024 image, the same calibration and integration settings on the saved
pre-change and updated processors. Times are individual command wall times,
including result preparation and stdio, excluding browser paint/physical scanout.
Ordinary development work was running; these are example runs, not statistical
latency guarantees. Flat-field loading/normalization was already inexpensive and
did not improve in this run; its Plot path did.

| Correction | Apply before → after (ms) | First Plot before → after (ms) | Cached Plot after (ms) |
| --- | ---: | ---: | ---: |
| Flat field | 18.3 → 20.5 | 17.9 → 6.9 | 0.2 |
| Transfer | 6.4 → 7.4 | 8.2 → 5.0 | 0.1 |
| cBN seat | 2925.7 → 34.2 | 3224.3 → 6.8 | 0.2 |
| Plate | 1423.0 → 17.2 | 1175.2 → 5.7 | 0.2 |
| Slab | 1373.5 → 16.2 | 1154.1 → 5.5 | 0.2 |
| Cylinder | 55.9 → 41.5 | 20.5 → 6.0 | 0.2 |
| Sphere | 35.2 → 20.5 | 19.5 → 5.9 | 0.2 |
| Detector absorption | 16.2 → 16.3 | 19.9 → 6.9 | 0.5 |

The detector kernel is distinct from Apply/Plot wall time. A fresh, isolated
3072 × 3072 (9,437,184-pixel) detector run measured:

| Stage/action | Time |
| --- | ---: |
| Geometry/scalar setup | < 0.001 ms |
| Full path/efficiency kernel | 5.891 ms |
| Apply, including corrected image/results | 131.3 ms |
| First Plot command | 52.3 ms |
| Display conversion and fingerprint within Plot | 5.194 ms |
| Full-resolution histogram within Plot | 20.331 ms |
| Exact source-precision levels within Plot | 8.345 ms |
| Reopen unchanged Plot command | 0.3 ms |

The remaining first-Plot time includes validation, metadata and transfer of the
37.75 MB float32 raster. The previous detector-specific optimization measured
186.7 ms for first Plot and 175.9 ms for another Plot; the new display cache and
level preparation improve that path further. The broader 9M sweep also completes
every correction, but accumulates large history states and is a separate receipt;
its timings should not be substituted for the fresh detector measurement.

Driver: `node desktop/scripts/corrections_benchmark.mjs [processor-path]`.
`DIOPTAS_BENCH_SIZE` selects the square detector size, `DIOPTAS_BENCH_KINDS`
selects comma-separated corrections, and `DIOPTAS_TRACE_FRAME=1` records native
stages. Receipts: `artifacts/corrections-before.json`, `corrections-after.json`,
`corrections-after-9m.json`, `detector-absorption-further-9m.json` and associated
trace logs. These measurements use the existing native stdio harness, not its
base64 browser-test adapter.

## Verification

Native tests cover bit-for-bit agreement of optimized cBN/plate/slab maps with
the previous scalar formulas; source-precision percentiles against full selection
for floating, narrow-range, repeated, constant and nonfinite data; shared map and
buffer identity across snapshots/Plot; Auto-level buffer reuse; new references
and transformations; cancellation; all existing correction preview, offline
project and functional workflows. Counting-variance operation order is retained.

Independent processing, uncertainty and round-sample reference scripts pass,
including capillary-wall materials, quadrature, supersampling weights and native/
legacy project interoperability. Headless Chromium and WebKit pass all correction
types, repeated Plot/Back, reference availability, independent levels/zoom,
unchanged image/pattern/cake ownership and stale/failing request cleanup.
Frontend build/tests and strict production Clippy pass. All-target Clippy passes
with only the existing unrelated `items_after_test_module` lint disabled.

No visible GUI test window was opened and no user process was terminated.

## Eager preparation and preload (superseded by background preparation)

The initial eager implementation prepared the full-resolution raster, histogram
and default percentile levels before correction calculation returned. Transfer prepares its
reciprocal divisor separately from the processing gain. Complete reference pairs
are prepared when loaded even if transfer application is disabled.

Successful responses include `preparedCorrections` raster metadata and the
corresponding binary buffers. The existing frontend raster transfer hydrates
these silently into its bounded byte cache. Preloaded buffers receive independent
storage so they remain cacheable when the surrounding source-image packet is
larger than that cache budget. They do not display a preview or change detector
contrast. The first Plot request advertises the preloaded buffer and receives
metadata only. Drawing/uploading that buffer to the GPU still occurs in the view.

Changed maps replace that correction's prepared preview. Failed/cancelled edits
do not publish pending data. Native worker handoff leaves new previews pending
for the frontend's subsequent refresh, rather than consuming their preload in
the host-only restore exchange. Caches remain disposable and bounded: evicted
previews or client buffers use the existing on-demand fallback.

Matched fresh 3072 × 3072 detector runs on this Mac:

| Native command | Before eager preparation | After |
| --- | ---: | ---: |
| Apply (including results and plot preload) | 113.7 ms | 187.0 ms |
| First Plot | 49.1 ms | 0.6 ms |
| Another Plot | 0.2 ms | 0.2 ms |
| First Plot pixel payload | 37.75 MB | 0 bytes |

This moves work and transfer to Apply; it does not eliminate them. The updated
9M path/efficiency kernel remains 5.686 ms. In the 1M sweep all eight first Plot
requests take 0.1–0.2 ms with zero pixel payload. Receipts are
`artifacts/corrections-eager-before.json`, `corrections-eager-after.json`,
`corrections-eager-all.json` and `corrections-eager-trace.log`.

Rust tests verify that each analytical correction's calculation response
contains the exact buffer Arc used on its first Plot, and that the first Plot
packet contains no pixel buffers when those IDs are advertised. Frontend tests
verify preload reuse even when the source packet exceeds the byte-cache budget.
Headless Chromium and WebKit assert zero first-Plot pixel bytes across all eight
corrections, alongside the existing ownership, invalidation and failure checks.


## Background preparation and compact Plot action

New map results now enqueue display work and return immediately. A single
reusable Rayon display worker evaluates only immutable correction arrays; on
macOS its thread uses Utility QoS. It does not own a Session or modify image,
pattern, cake, calibration, history or project data. The scientific worker budget
continues to govern scientific processing; this one additional thread is reserved
for optional display preparation.

The queue keeps the newest job per correction and bounds queued map storage.
Ticket checks discard results superseded by edits, removal or cancellation.
Preload queries filter completed rasters by the active configuration's exact
reference/parameter/geometry keys. Requests with an obsolete revision or
configuration are quietly discarded. An early Plot promotes its queued map and
waits for that job with cancellation checks rather than computing duplicate
histograms. Native on-demand preparation remains available if the display worker
cannot start or a prepared preview has been evicted.

`integration_correction_preload` is a read-only Rust/stdio route. The React hook
polls it while matching jobs are pending, without using the foreground run/busy
state. It stops on readiness, mode/context changes or unmount. Completed buffers
are hydrated into the existing bounded client byte cache. Ordinary Apply replies
no longer carry correction preview pixels, even if a small job has already
finished by the time Apply returns.

Fresh 3072 × 3072 detector runs, using the same native stdio harness:

| Measurement | Eager preparation | Background preparation |
| --- | ---: | ---: |
| Apply command | 168.0 ms | 115.7 ms |
| Ready Plot command | 0.5 ms | 0.2 ms |
| Additional time after Apply until preload completed | included in Apply | 15.3 ms |
| Ready Plot pixel payload | 0 bytes | 0 bytes |

The detector path/efficiency kernel remains 5.692 ms. Background conversion,
histogram and exact levels took about 99 ms on the one display worker, mostly
overlapping Apply. Timing excludes browser paint/GPU scanout. Receipts:
`artifacts/corrections-background-before.json`, `corrections-background-after.json`
and `corrections-background-trace.log`. Setting `DIOPTAS_BENCH_EARLY_PLOT=1`
exercises Plot immediately without waiting for the preload poll.

The correction form now places a quiet chart-icon **Plot** button directly
beside the compact **Apply** checkbox. The same button becomes **Back** with a
back arrow while its correction is visible. Full correction-specific accessible
checkbox names remain intact. This applies to flat field, transfer and every
analytical correction; there is no separate upper-right action row.

Native gated-worker tests verify nonblocking queueing, job coalescing, obsolete
and cancelled result rejection, restart without recalculating science, and reuse
by an early Plot. Full library, preview, functional and native-session checks pass.
Headless Chromium/WebKit additionally delay preload while applying another edit,
verify that controls remain usable, reject the obsolete response, and then require
zero pixel bytes for ready Plot. Compact row bounds and screenshots pass at
1000/1440 pixels with Standard and Larger text. Screenshots are under
`artifacts/correction-previews/*-actions-*.png`.
