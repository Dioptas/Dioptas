# Native display preparation and transfer

November 10, 2026. This work changes Rust Dioptas (React/Tauri), using
`e9cddc17` as the preserved application baseline. It includes the preceding
single-image strict CSR optimization and shared processing-worker controls in
both variants. Dioptrin's numerical implementation and pin are unchanged.

## Changes and profile

Three costs were identified in real native GUI traces and separate macOS
sampling runs:

1. Repeated high detector sentinel values were hashed on every occurrence during
   integer count statistics. A pending sparse count now accumulates that value
   between dense counts and flushes it when the sparse value changes. The same
   4,096-value cache bound, fallback conditions, sorted distribution, gap rule,
   quantiles and histogram remain in force. In the paired GUI runs, this stage
   fell from **4.96 to 2.68 ms**; float32 conversion and display fingerprinting
   remain approximately 1.08 and 2.40 ms respectively.
2. The frontend copied a full 40,553,184-byte detector payload out of each IPC
   packet. Native JSON headers now end on a four-byte boundary using valid JSON
   whitespace. Large payloads become typed views of the received packet;
   aligned little-endian float32 data go directly to the renderer. Legacy or
   unaligned payloads retain a copying fallback. Small companions are copied
   independently so they cannot pin a large packet. The source cache accounts
   for the complete backing packet, shared once across its views, and preserves
   concurrent-request pinning and A/B/A identities. Payload bytes and content
   hashes are unchanged.
3. A per-upload `getError` query blocked WebKit's GPU queue by approximately
   **8 ms**. Detector textures now update existing storage with `texSubImage2D`.
   Pattern curves reuse equally sized superseded buffers with `bufferSubData`;
   buffers belonging to unchanged curves/overlays are reserved. GPU error checks
   remain on allocations, while updates validate dimensions/capacity and retain
   established formats. Context-loss recovery remains in place. Shaders,
   coordinate splitting, mask blending and color calculations are unchanged.

The paired GUI traces show detector submission after hydration falling from
approximately **12 ms to 4–5 ms**. Warm frames no longer perform the blocking
GPU error query. Native pipe writing remains approximately **6.7 ms** for a new
40.6 MB image; the optimization does not claim a faster operating-system pipe.

[GUI timings and stage profiles](artifacts/display-transfer-throughput/gui.json)
and [separate sampling receipt](artifacts/display-transfer-throughput/profile.json)
retain measurements and raw-source paths/SHA256 identities. Sample counts are
hotspot attribution, not normalized CPU percentages. Both sampled backend
process footprints were approximately 3.0G.

## Actual GUI measurement

Apple M4 Pro, 3262 × 3108 Eiger images, 2,000 bins, pyFAI-compatible full splitting,
CSR, named-detector PONI, automatic acquisition mask, Poisson errors off/on,
no corrections or dynamic masks, normal automatic processing-worker setting.
Both variants use the real App command queue, Rust processor, Tauri binary IPC,
WebKit, and shared detector/pattern GPU renderers. Detector pixels remain at
full resolution. Cake and rings are hidden as in the normal Integration image
view. Viewport is 1440 × 908 CSS pixels with device pixel ratio 1.

Three fresh private-window runs per variant reverse before/after ordering on the
second pair. Each traverses 24 new frames per Poisson setting and performs 25
cached forward/backward selections. This gives **588 timed GUI selections**:
72 new-frame and 75 cached selections per variant/error setting. Source-frame
changes and visible WebGL rendering are checked for every selection. Cached
means frontend detector bytes are reused; the backend still loads and integrates
the selected frame. Timed file opens select frames 1, 313 and 625. Opens are
classified from actual native packet byte counts, not assumed cache state.

Median milliseconds, click to completed detector **and** pattern GPU work:

| Navigation | Poisson errors | Before | After |
| --- | --- | ---: | ---: |
| New frame | Off | 54.5 | **43.0** |
| New frame | On | 52.0 | **42.0** |
| Cached selection | Off | 39.0 | **29.0** |
| Cached selection | On | 39.0 | **29.0** |

New-frame render readiness improves **19–21%**, and cached readiness improves
approximately **26%**. The additional two-animation-frame presentation bound
measures 79 → 58 ms for new frames without errors and 78 → 59 ms with errors.
Cached presentation bounds remain approximately 58–59 ms despite earlier GPU
completion. Paint opportunities are quantized by the display/WebKit cadence;
they are not physical-display scanout measurements.

Calibrated file opens transferring new detector bytes remain a median **80 ms
in both variants**, for both error settings, with six observations per
variant/setting. File discovery, command handling and presentation opportunities
remain material. These results do not establish a substantial file-opening
speedup. OS file dialogs, initial geometry/plan construction and cold-disk I/O
are excluded from the warm comparison.

The workstation was not CPU-isolated. Before/after CPU snapshots and all runs
are retained. Test windows used private WebKit stores without requesting focus;
the test processes closed at completion. Other previews were not terminated.

Both versions also traverse **all 625 frames through the actual GUI**, with each
Poisson setting, followed by 625 cached selections per setting: **4,996 additional
GUI selections** in total. Display scaling changed from 1 to 2 during the long
baseline run. Consequently these traversals are retained as stress checks and
are **excluded from matched timing conclusions**. Detector and pattern readbacks
match the repeated-run references exactly when grouped by canvas dimensions and
source frame. [Full GUI traversal receipt](artifacts/display-transfer-throughput/gui-full.json).
An additional short check also encountered different display scaling between
windows and is excluded from performance comparisons; its matching-size pixel
readbacks agree with the same references. [Additional display check](artifacts/display-transfer-throughput/additional-display-check.json).

## Unchanged results and regression checks

- All **625 frames** in each Poisson setting match the preserved backend's
  float64 radial coordinates, intensities and errors bit for bit. Transported
  detector/mask bytes, histograms, auto levels and coordinate metadata also
  match. Source size and modification time are unchanged. The additional cached
  integration and load-only controls pass the same checks.
- All **24 actual GUI detector/pattern RGBA readbacks** in the paired runs match
  exactly across variants and repetitions. Readback and SHA256 computation
  happen outside timed intervals, immediately after the actual GPU draw and
  before presentation clears the drawing buffer.
- Headless Chromium and WebKit compare reused GPU storage with fresh allocations
  byte for byte for six detector frames and six pattern frames per browser.
  They cover changing data, masks, shapes, palettes, linear/log/sqrt display,
  retained/reordered overlays, changed curve sizes and invalid dimensions.
  Existing pixel-rendering, gestures, zoom persistence, slice navigation and
  context-loss/recovery checks also pass.
- **81 preserved-executable cases** pass across integer/float images, corrections,
  masks/ROI, navigation, changed bins/units/sectors, errors/spread, transforms and
  cakes. There are **196 passing backend tests**, two existing opt-in tests
  ignored, **27 host tests**, **103 JavaScript tests**, and **nine native stdio
  cancellation/source-change tests**. All-target backend Clippy and the
  TypeScript/Vite build pass. Headless native Integration/Map workflows pass in
  Chromium and WebKit.
  After merging with the current primary checkout's independent coordinate-change
  work, all **202 backend tests** and its TypeScript/Vite build also pass.
  The normal native debug build and all-target Clippy pass there as well. Its
  fresh processor reproduces the measured optimized executable bit for bit at
  Eiger frames 1, 313 and 625 in both error settings and cached reintegration.

[Full-series numerical receipt](artifacts/display-transfer-throughput/full-bitwise.json),
[broader numerical comparisons](artifacts/display-transfer-throughput/parity.json),
and [verification receipt](artifacts/display-transfer-throughput/validation.json).
The merged-executable comparison has a separate
[correctness receipt](artifacts/display-transfer-throughput/main-bitwise.json).

## Reproduction

Preserve the before and after application bundles and processor executables.
Build the frontend with `VITE_DIOPTAS_NAVIGATION_BENCHMARK=1` and the normal debug
Tauri build using an isolated configuration from `nativeTestProfile`. Then run
each application/processor pair with:

```sh
node desktop/scripts/image_navigation_native.mjs --no-build \
  --app /path/to/variant.app/Contents/MacOS/dioptas-desktop \
  --processor /path/to/variant-processor \
  --eiger /path/to/eiger_0000.h5 --eiger-only \
  --single-method pyfai_full --single-bins 2000 --single-steps 24 \
  --keep-visible --no-capture --output /path/to/receipt-directory
```

Use `--single-steps 624` to traverse the complete 625-frame source before the
cached navigation checks. The driver clicks the actual frame arrows and checks
`integration_navigation` responses; file arrows remain a separate action.
GPU completion includes both detector and pattern contexts. Hash validation is
untimed. The private test profile disables worker hot reload and leaves other
previews and their processing intact.
