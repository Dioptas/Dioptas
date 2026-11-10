# Application processing workers

Settings → General → Processing workers controls the native application's common
CPU budget. Automatic is the default; it reserves two performance cores on Macs
that report them, otherwise two available CPU cores, with at least one worker.
An M4 Pro with ten performance and four efficiency cores therefore defaults to
eight workers. Manual selection permits 1 through the available CPU count,
including all fourteen cores on that machine. Use default restores Automatic.

Changes apply to the next serialized operation without restarting the app or
refitting existing products. The preference is saved in application-local storage
and restored on startup even when Settings has never been opened. It is shared
across configurations and is not imported from normal scientific project files.
The private development-worker handoff retains it alongside the live session.

`worker_pool.rs` owns reusable Rayon pools and the current operation's selected
pool. The Session and its configuration/history owners remain on the command
thread; only Send-safe numerical inputs enter the pool. Background fitting,
resident integration/plan preparation, calibration fitting and Massif preparation,
mask plugins, sample-absorption tables, image orientation/conversion, detector-gap
marking, histograms/count tables and display fingerprints use this common pool.
The previous separate Background and display-hash pools have been removed.

Raw series use finite frame tasks in the same pool. Decoder/integration scratch
returns with each completed result and is reused when ordered consumption opens
another queue slot. No pool thread blocks waiting for future frame jobs. This
preserves the existing rolling pipeline, acquisition order and at-most-workers
reorder bound, instead of introducing batch barriers. Cancellation/failure
disconnects result receivers before joining pending tasks. The established 4 GiB
combined frame-worker payload budget and selected-frame limit can reduce the
effective count. The decoder's internal block executor receives the same worker
budget; deterministic per-frame integration retains its serial kernel context.

`processing_workers` accepts `{"workers":null}` for Automatic or a positive
integer no larger than available CPU capacity. Invalid requests retain the prior
choice and products. `state.processingWorkers` reports requested, effective,
available and automatic counts. Pools are resized only between operations. A
weak registry reuses a live pool of the same size; unused custom pools are freed.

For diagnostic command-line clients, `DIOPTAS_WORKERS` sets the initial common
count. Legacy `DIOPTAS_INTEGRATION_THREADS` and `DIOPTAS_BACKGROUND_WORKERS` are
accepted, in that order, when the general variable is absent; they no longer
create feature-specific budgets. Settings overrides this initial choice.

The full 625 × 1000 automatic-background scaling comparison is recorded in
`artifacts/batch-background-performance/scaling.json`: 3/8/10/14 workers measured
173/85/76/81 ms respectively before consolidation. Ten was fastest for that
workload; eight is the requested default that reserves two performance cores.
All nine tested counts produced background and source matrices identical, bit
for bit, to the original implementation. Use
`scripts/batch_background_scaling_benchmark.mjs` to reproduce the comparison via
the same native worker-setting command used by Settings.

Native regressions cover worker selection, invalid requests, nested work/pool
reuse, single-core/capacity limits, exact serial/parallel background output,
unmodified retained products, project independence, development handoff, and
bounded ordered integration with cancellation/failure. Headless Chromium and
WebKit exercise manual selection, startup persistence from Mask mode, Use default
and large text. The GUI check is registered in `test:ci-native`.


Qualification after reconciliation with the typed-integer integration update:
195 native tests passed (two opt-in performance tests ignored); 98 JavaScript
tests, frontend build and Clippy with warnings denied passed. Both headless
browsers passed worker Settings, native Integration and automatic Batch background
checks; native stdio cancellation passed. The shared pool was also checked on the
complete 625-frame Eiger source in Batch/Map, Poisson errors off/on, two before/
after repeats: all 16 runs had bitwise identical intensities, axes, counting std
where present, and Map values. The source file was unchanged. The aggregate
receipt is `artifacts/shared-processing-workers/validation.json`. Timing was not
isolated from concurrent work, so it is not a new throughput qualification.
The final API-based background sweep also retained exact original values at all
nine worker counts (`artifacts/batch-background-performance/shared-pool-scaling.json`).
