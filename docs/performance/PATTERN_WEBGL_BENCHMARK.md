# Pattern WebGL rendering and benchmark

> Historical evidence: Python-era commands and source paths in this ledger refer to
> pre-cleanup revision `a39717a41458129ba9370c849a4121ecdbc6a444` (resolve the full revision in `../architecture/REFERENCE_DATA.md`).
> The active application and test suite are Rust/headless UI only. See
> [reference data policy](../architecture/REFERENCE_DATA.md) for retained fixtures and current checks.

WebGL is the default pattern renderer, with automatic Canvas fallback for
unavailable/lost contexts, upload failures, and the existing antialias-off pixel
mode. `VITE_DIOPTAS_PATTERN_RENDERER=canvas2d` forces Canvas for diagnostics.
The implementation was evaluated on `codex/webgl-pattern-benchmark` against the
merged Canvas implementation at `d4efd68a` before promotion to the desktop branch.

## What a useful comparison measures

The same `PatternView` navigation handlers receive 90 input updates for each of:

- Continuous right-drag panning across a wide view.
- Panning after zooming approximately 10× into the data.
- Continuous wheel zoom, inward and outward.

The first ten updates are excluded from warm timing summaries. Each run fixes
the plot at 1000 × 600 CSS pixels, uses the same immutable source arrays and
styles, and records device pixel ratio and the observed animation-frame cadence.
Renderers run sequentially in the same native Tauri/WKWebView window. No
`gl.finish`, framebuffer readback, screenshots, or GPU-buffer instrumentation
queries run inside the timed interactions.

The test includes a measured CeO2 pattern integrated to 2,000 bins from the
repository detector image and its reference PONI. The other cases are explicitly
synthetic stress patterns: 2,000 points; twenty 4,000-point curves; 100,000
points; eight 100,000-point curves; and one million points. Synthetic peaks,
background variations and overlays test renderer load, not scientific accuracy.

Three implementations are compared: the original Canvas component, Canvas with
the prototype's layer arrangement, and WebGL curves. The original component is
reconstructed from `d4efd68a` into an ignored temporary source file, with timing
hooks and guards that skip unchanged gutter-state updates. Those guards avoid
unnecessary React effect updates under the synthetic event loop; its drawing
algorithm is unchanged. The intermediate Canvas run checks whether the layer
refactor itself changes performance.

CPU drawing time measures the plotting effect, including any buffer upload.
Input-to-submission time includes React processing before that effect finishes.
Animation-frame intervals measure scheduling cadence and expose stalls. They
are not measurements of physical display latency or isolated GPU execution time.
A “long frame” is an interval exceeding 1.5× the idle median in that same run.

## First native result, 2026-11-03

The native window reported **Apple GPU / WebGL 2.0**, DPR 1. Its idle animation
cadence was approximately 20 ms. CPU timings have roughly 1 ms resolution, so
sub-millisecond differences should not be interpreted precisely.

Full-range pan, p95 across warm updates:

| Workload | Original Canvas drawing | WebGL drawing | Canvas frame interval | WebGL frame interval |
| --- | ---: | ---: | ---: | ---: |
| Measured CeO2, 2,000 bins | 2 ms | ≤1 ms | 22 ms | 21 ms |
| Synthetic 2,000 points | 2 ms | ≤1 ms | 22 ms | 21 ms |
| Twenty × 4,000 points | 7 ms | ≤1 ms | 20 ms | 21 ms |
| 100,000 points | 8 ms | ≤1 ms | 20 ms | 22 ms |
| Eight × 100,000 points | 53 ms | ≤1 ms | 54 ms | 22 ms |
| 1,000,000 points | 64 ms | ≤1 ms | 64 ms | 22 ms |

A second sequential native run reproduced the conclusion: p95 wide-pan drawing
was 55 ms for eight dense curves and 70 ms for a million points, versus about
1 ms with WebGL. Their p95 animation-frame intervals were 55/71 ms with Canvas
and 21 ms with WebGL. Ordinary patterns again maintained the same cadence.
The original run is retained as `artifacts/pattern-native-run1.json`, and the
repeat is `artifacts/pattern-native.json`.

The two heaviest Canvas cases had long intervals in every measured wide-pan
frame; WebGL had none. The intermediate Canvas layer arrangement produced
essentially the same result as the original: approximately 54/63 ms p95 drawing
for those two cases. This supports attributing the gain to GPU curve rendering.

Wheel zoom also improved for the heavy cases: p95 frame intervals changed from
48 to 21 ms for eight dense curves and from 76 to 21 ms for one million points.
When already zoomed in, visible-range culling made Canvas fast enough to sustain
the observed cadence. There is little visible frame-rate benefit for ordinary
patterns; the useful gain is smoother navigation and CPU headroom for large
patterns and many overlays.

No vertex buffers were uploaded during navigation. The million-point curve used
16 MB of vertex data; eight dense curves used 12.8 MB. These figures cover the
vertex buffers, not total GPU/driver memory. Initial preparation and upload are
measured separately from warm navigation in the JSON report.

Headless Chromium was deliberately excluded from the performance conclusion:
its command line selected `swiftshader-webgl`, a software renderer. It remains
useful for functional checks, but does not measure native GPU performance.

## Rendering quality and verification

Fourteen WebKit geometry comparisons cover DPR 1/2, narrow peaks, missing samples,
descending coordinates, unordered samples, log/nonpositive values, square-root
scaling, and deep zoom near large coordinate offsets. Geometry masks matched
within two CSS pixels, allowing at most two or 0.1% unmatched pixels per mask.
There were 20 outlying mask pixels among 105,108 compared curve pixels in total.
These checks catch misplaced curves and connections across gaps; they do not
establish identical antialiasing.

The renderer uses instanced round-ended segments with shader edge smoothing.
Its line weight and joins differ slightly from Canvas. The narrow-peak images
in `artifacts/pattern-quality-{canvas,gpu}.png` make that visible. The retained Canvas option supports direct visual comparison when adjusting
line appearance. GPU context loss/restoration is checked. Turning
antialiasing off uses the existing Canvas pixel renderer.

The complete browser calibration/integration workflow and WebKit position/readout
checks pass with the WebGL curve option enabled. The native Tauri application
workflow smoke also passes and reaps its processing child. The 37 JS tests pass. This
experiment does not establish Windows/Linux performance or improve integration
and fitting times; the scientific processing boundary is unchanged.

## Reproduce

From this worktree's root directory, after the normal independent checkout
setup (`npm ci`, and `uv sync --python 3.13 --extra test` at the repository root):

```sh
npm run benchmark:pattern:native
npm run test:pattern-quality
```

The native runner reconstructs its Canvas reference, builds a dedicated benchmark
bundle, launches only its own test window and closes it on completion. It writes
`artifacts/pattern-native.json`, progress/log files and removes the generated
reference source. No primary-preview port is used. Keep other heavy workloads
idle while timing. The benchmark binary is a test harness; rebuild normally to
return it to the application:

```sh
npm run tauri:build -- --debug
src-tauri/target/debug/dioptas-desktop --example
```

Browser diagnostics are available through `npm run benchmark:pattern -- --webgl
--webkit` and `--original`; `--case=dense-overlays` selects a single workload.
Their GPU/engine and timing context must be inspected before comparing results.
