# Eiger Batch throughput in the native GUI

> Historical evidence: Python-era commands and source paths in this ledger refer to
> pre-cleanup revision `a39717a41458129ba9370c849a4121ecdbc6a444` (resolve the full revision in `../architecture/REFERENCE_DATA.md`).
> The active application and test suite are Rust/headless UI only. See
> [reference data policy](../architecture/REFERENCE_DATA.md) for retained fixtures and current checks.

Measured November 10, 2026 on the local Apple M4 Pro. All full-file runs below
load **625 original 3262 × 3108 Eiger frames** from
`/Users/clemens/Programming/Dioptrin/test_data/eiger_0000.h5` using the normal
**Batch `batch_load_data` action** in the actual React App and Tauri WKWebView.
No dynamic masks, background or flat-field corrections are enabled. The
adjacent named-detector PONI and its automatic acquisition mask remain enabled.
Resident layout is CSR; polygon integration uses eight persistent frame workers.

The measurement includes the full native command, Tauri binary IPC, normal
React response processing, Batch display, GPU completion and paint
opportunities. It excludes the OS file picker and initial image/calibration
setup. It does not measure physical LCD scanout. Sources are OS-cache warm and
CPU resources are not isolated. Each table entry is one pass; between-run
variation is visible in the receipts and should not be treated as a regression.

## Controlled bin comparison

Both cases disable Poisson errors and use polygon integration. Each processes
all 625 frames, once with an unprepared series plan and once with it reused:

| Radial bins | First load, seconds | First load, images/s | Repeated load, seconds | Repeated load, images/s |
| --- | ---: | ---: | ---: | ---: |
| 1,000 | 3.307 | 188.99 | 2.759 | 226.53 |
| 2,000 | 3.560 | 175.56 | 3.058 | 204.38 |

Doubling the bin count reduces repeated-load throughput by about **9.8%** in
this paired pass. It still exceeds 200 images/s at 2,000 bins without errors.
The first load includes preparation of the shared series plan. A separate
initial GUI pass measured 180.95/203.92 images/s at 1,000 bins, illustrating
the variation between passes.

## Poisson errors and integration method

These cases also cover all 625 frames:

| Method / errors | Bins | First load, seconds | First load, images/s | Repeated load, seconds | Repeated load, images/s |
| --- | ---: | ---: | ---: | ---: | ---: |
| Polygon / Poisson | 2,000 | 4.187 | 149.27 | 3.546 | 176.25 |
| pyFAI-compatible full / no errors | 2,000 | 6.334 | 98.67 | 6.120 | 102.12 |
| pyFAI-compatible full / Poisson | 2,000 | 6.228 | 100.35 | 6.280 | 99.52 |

These measurements describe the baseline before the subsequent
[parallel pyFAI-compatible series implementation](NATIVE_PYFAI_SERIES_PIPELINE.md).

The original 1,000/no-errors versus 2,000/Poisson comparison changes **two
settings**, so it does not isolate bin count. Polygon's full-frame pipeline
reports 625 frame-parallel integrations, eight workers and one pipeline per
command. At this baseline, the uncorrected, fixed-mask pyFAI-compatible case bypassed
that pipeline: it reports zero worker starts/pipeline runs and 626 resident
integrations (625 series profiles plus final selected-frame integration).
Its existing serial route is a separate throughput limitation, not a bin-count
effect. This follow-up measures that route; it does not change its scientific
implementation or claim that the user's current session uses this method.
The linked follow-up now shares the same CSR plan across persistent frame workers.

Initial Eiger image opening took 0.315–0.357 s through paint, followed by
1.453–1.454 s for calibration loading and preparation. That approximately
1.8 s precedes the series measurements above. Polygon's native IPC portion
typically finishes 48–113 ms before the complete GUI measurement. The measured
GUI overhead does not explain a large drop from approximately 200 images/s in
this setup.

## Live progress rate

The existing status line now shows, for example:

`Integrating series 416 / 625 · 185.1 images/s`

The native ordered collector reports **completed frames / elapsed seconds**.
Timing starts before metadata discovery, checkpointing and plan preparation;
it uses elapsed wall time for the whole operation rather than summed worker
CPU time or a requested target rate. It is a running integration average,
not an instantaneous display-refresh measurement. Final response transfer and
rendering occur after the last integration progress update and are included
only in the GUI command benchmarks above.

Main, detached Batch and detached Map footers use the same formatter. Only
metadata crosses the detached-window status channel. Calibration/plugin
progress without a frame rate keeps its existing text. Headless Chromium and
WebKit checks verify the rate arithmetic and its presence in the main and
detached Map footers. Native full-series runs observe positive live rates in
the actual GUI. All 182 Rust tests, 94 frontend tests, strict Clippy, TypeScript
checking and the frontend build pass. No scientific algorithm changed.

The native benchmark windows use private WebKit stores and initially receive
no keyboard focus. The final compatibility run keeps its test window on top
to prevent WebKit occlusion throttling; an obscured-window attempt was rejected
when animation-frame presentation stopped. Each test's app and processing child
were closed. The user's existing live preview remained running.

## Receipts and reproduction

- [Initial native GUI pass](../../artifacts/native-gui-series/baseline.json)
- [Controlled bins and a separately labeled 32-frame method diagnostic](../../artifacts/native-gui-series/bin-control.json)
- [Full-file pyFAI-compatible cases](../../artifacts/native-gui-series/compatibility.json)
- [Headless progress checks](../../artifacts/native-gui-series/headless-progress.json)

The 32-frame diagnostic is not used for the full-file method rates above.
Receipts retain every progress string, worker/plan diagnostics, transport
timing summaries and the raw-receipt SHA-256. Full traces, logs and private-profile captures remain under
`/Users/clemens/Codex/dioptas-eiger-gui*-20261110`.

```sh
node scripts/image_navigation_native.mjs \
  --eiger /path/to/eiger_0000.h5 --series --output /tmp/gui-series
node scripts/image_navigation_native.mjs \
  --eiger /path/to/eiger_0000.h5 --series --series-extra --output /tmp/gui-bins
node scripts/image_navigation_native.mjs \
  --eiger /path/to/eiger_0000.h5 --series --series-method pyfai_full \
  --keep-visible --output /tmp/gui-compatibility
```

These explicit native benchmark commands open an isolated test window. Routine
GUI progress checks remain headless:
`node scripts/native_map_progress_smoke.mjs`.
