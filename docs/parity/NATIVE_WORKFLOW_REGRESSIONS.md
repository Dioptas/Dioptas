# Native combined-workflow regression coverage

> Historical evidence: Python-era commands and source paths in this ledger refer to
> pre-cleanup revision `a39717a41458129ba9370c849a4121ecdbc6a444` (resolve the full revision in `../architecture/REFERENCE_DATA.md`).
> The active application and test suite are Rust/headless UI only. See
> [reference data policy](../architecture/REFERENCE_DATA.md) for retained fixtures and current checks.

Local verification on 2026-11-08. This supplements the stage-specific parity
ledgers; it is not a claim that every Qt functional test has a Rust equivalent.

## Regressions covered in this change

| Workflow | Executable evidence |
| --- | --- |
| Appended/case-insensitive PONI fields, last values used; malformed final values rejected | `geometry.rs` unit test using the existing two-record LaB6 fixture |
| Named Eiger calibration with matching dimensions; atomic rejection on Pilatus example | Geometry unit test and `scripts/native_file_errors_smoke.mjs` in headless Chromium/WebKit |
| Saved asymmetric TIFF `.mask` coordinates → frame navigation → native combined integration → Batch/Map → two configurations → `.dio` reopen with raw files removed | `backend/tests/integration/combined_workflows.rs`, frozen independent Bitshuffle-LZ4 and TIFF fixtures; 12 combinations of units, mask use and Poisson options |
| Existing Map regions, reductions, background flags, expressions and active layer survive new-file loading, reintegration and processed-batch loading | Same combined test, including Q to d conversion; new grids are still chosen for the incoming point count |
| Incremental Map values match finished values; unfinished cells are NaN; no duplicate integration | `batch_workflow.rs` unit matrix: all six reductions, both background choices, direct/expression layers |
| Partial maps and current patterns appear while busy, with matching finished cells; regions persist; detached Map also updates | `scripts/native_map_progress_smoke.mjs`, real Rust worker and 2048-frame generated input, headless Chromium/WebKit |
| Cancellation/source mutation publishes no incomplete series; cancelled Map preview clears and preceding state survives | `scripts/native_integration_transport.test.mjs`, generic gzip and combined Bitshuffle-LZ4 routes |
| Short detector mismatch dialog; copyable report for other failures; recent actions, selected paths, context and build; OK/Escape; JS errors and unhandled rejections | `scripts/native_file_errors_smoke.mjs` in Chromium/WebKit plus `scripts/error_reporting.test.mjs` |
| Native panic returns a fatal report and available native backtrace, and stops the worker instead of reusing its session | `transport.rs` panic-boundary unit test; ordinary Result errors retain existing rollback |

Command failures are captured at the shared frontend bridge, including detached
native windows. The root React boundary captures rendering failures, and window
handlers capture uncaught JS errors/rejections. Reports remain local until copied.
Native panics are reported at the worker boundary; this does not recover a crashed
session or promise recovery from process aborts, allocation failure or OS termination.
The Tauri pipe also rejects pending/future requests after a child exits.

## Performance and exact Eiger reproduction

`scripts/native_eiger_regression.py` is an optional read-only check against the
external Dioptrin test data, not a required CI input. Its Rust children run with
Python unavailable. The parent uses independent Pillow/NumPy/h5py inspection.

On this Apple M4 Pro, the matched warm-cache 64-frame/2000-bin comparison measured
27.85 → 89.88 images/s (three repetitions, eight decoder workers). All exported
64×2000 float64 samples were bit-for-bit identical. A complete 625-frame Map
command took 5.12 s, about 122 images/s, including series construction and final
selection, without frontend rendering/polling. Earlier repeats measured about
30 → 95 images/s. These measurements do not establish the desired 200 images/s,
or cold-storage throughput. The 4/12/16-worker sweep did not justify changing
the default of eight workers. Machine-readable receipts are under ignored
`artifacts/standalone/eiger-regression.json`.

Bulk processing now retains one immutable geometry/mask/plan context per admitted
single-dataset source and consumes combined decoder/integrator results directly.
It avoids per-frame full-image allocation, conversion, flipping and display/mask
refresh. Corrections, dynamic masks, transformed images, unsupported codecs and
multi-dataset series retain their ordinary processing route. Source identity,
axis agreement and cancellation checks remain active. Map previews reduce each
completed pattern using the same window algorithms as the final map; raster
publication is throttled to 150 ms and carries immutable binary buffers.

Exact `eiger_0000.mask` inspection on fresh TIFF and HDF5 frames 0 and 389 found
saved-coordinate agreement and all 887556 invalid pixels masked. Reversing that
mask vertically covered only 823786 invalid pixels. The reported visual reversal
has therefore not been reproduced; the image and default mask orientations were
left unchanged. The frozen asymmetric-mask regression guards against introducing
an extra flip.

## Remaining Qt replacement qualification

The native suite now has 52 Rust tests, numerical reference scripts, transport
checks and real-worker browser workflows. Existing independent integration and
series parity checks still pass. These cover substantial combinations, but do
not constitute a one-to-one port of Qt's functional suite.

Still needed is a maintained case-by-case mapping of Qt project/integration tests
to native tests, especially broad combinations of phase/EOS state and overlays,
all correction/background/absorption models, detector/distortion variants,
transforms, historical project versions, and missing/moved source data. Existing
stage tests cover examples of these individually; that is not proof of every
combination. Cross-platform packaged-app, real OS-dialog and long-running live
acquisition qualification remain separate from headless/scientific fixtures.
