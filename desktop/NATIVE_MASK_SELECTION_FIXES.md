# Eiger gap margins and Map selection qualification

Validated locally on 2026-11-08 in `codex/native-backend`. These results apply
to the tested fixtures and workflows, not complete Qt parity or release qualification.

## Acquisition-specific gap margins

The generic Eiger2 CdTe 9M model mask agrees with pyFAI, but does not include
all module-border fill strips in `Dioptrin/test_data/eiger_0000.h5` (3262 × 3108,
625 frames). This is separate from image/mask orientation.

The Rust session supplements known Eiger gaps with nearly uniform fill strips
at module boundaries. Recognized values are zero, minus one, datatype maximum,
and the signed-int32 maximum used in this unsigned acquisition. Only marker
pixels in admitted boundary strips are added; interior zeros and large measured
counts are preserved. Evidence from illuminated module interiors is required.
A dark first frame is retried on subsequent frames. Successful inference is
cached by detector, shape, source identity, datatype, and reader options.

For the full-resolution fixture, the generic mask contains 682,680 pixels;
the extended mask contains 872,396. The image has 887,556 dummy pixels. No
valid pixels were newly masked in this comparison; 15,160 separate dummy
defects remain outside the structural strips and need an acquisition mask.
The supplied mask contains 887,588 pixels, including additional defects.

The extension check alone takes a median 0.43–0.46 ms over 30 release runs,
excluding decoding and allocation. It is reused across frames of one source.
Synthetic combined workflows cover max/zero/minus-one fills, valid interior
zeros, multiple sources, Map reintegration and project restoration without
the original image files. Unit checks also cover dark-frame retry and cache reuse.

## Preserve Qt AutoLevel filtering

The original Qt gap/dummy filter remains the reference. `Filter gaps` controls
automatic contrast estimation; it does not delete every large measured count
or replace the scientific detector mask. The fixture's dummy marker is
2,147,483,647; its largest retained non-dummy value is 6,383,154.

`scripts/native_autolevel_parity.py` compares the actual Qt `AutoLevel` class
against the Rust processor: 30 comparisons pass for min/max, mean ± 3 SD and
percentiles, with gap filtering on/off, synthetic fills, floating data and the
real 9M image. Relative tolerance is 2e-12, absolute tolerance 1e-9. The existing
React percentile setting is preserved. Compensated variance accumulation
improves mean/SD numerical accuracy without changing the rule.

Integer percentile computation uses a bounded exact histogram, counts larger
values in the sample population, and falls back to selection when requested
ranks cannot be resolved exactly. No high-count clipping is introduced.

## Map selection performance

The admitted parallel HDF5 decoder now also serves image-only loading and
stored-pattern selection. Current admission covers compatible little-endian
U16/U32 Bitshuffle-LZ4 inputs; other layouts/codecs retain the native reader
fallback. Map reintegration computes the pattern without an unused cake;
Integration and Batch retain their products. Linked contours are reused when
geometry, shape and physical two-theta agree. Display statistics avoid duplicate
scans, use parallel full-pixel histogram counting, and reuse matching Auto levels
in the frontend. ARM SHA instructions accelerate existing buffer hashes.

The binary-protocol benchmark client was also corrected to avoid repeatedly
copying its growing input packet. Its earlier 1.5-second result was a test-client
artifact and is not a production baseline.

Using that corrected client, warm-cache selection plus restoration of the same
linked guide decreased from approximately 480–500 ms in the previous standalone
processor to 110 ms: median 109.5 ms for stored patterns and 111.7 ms for
reintegration. Eight distinct frame selections were compared. Full patterns,
image/mask buffer hashes, histograms, contrast limits and linked positions agree
exactly with the baseline. This measures backend work and binary transfer,
excluding WebKit/GPU painting. It uses the full 9M fixture, 2,000 radial bins
and 90 cake bins.

Approximate stage medians (display subparts are included in its total):

| Stage | ms |
| --- | ---: |
| Metadata and decoder/plan handoff | 10.0 |
| Display preparation total | 75.2 |
| — float conversion and buffer hashing | 17.3 |
| — exact Auto percentiles | 37.1 |
| — full-pixel histogram | 16.8 |
| Masks and pattern integration | 4.8 |
| Response encoding and pipe flush | 9.0 |
| Linked guide restore | about 2.2 |

Medians of separate stages do not sum exactly to the total; snapshot/state and
other overhead account for the remainder. The optional `DIOPTAS_TRACE_FRAME`
environment variable emits stage timings to stderr without pixel data.

## Verification

- 58 Rust tests passed; one opt-in real-image timing benchmark is ignored by default.
- Rust Clippy passed with warnings denied.
- 63 frontend unit tests passed; TypeScript/Vite build passed.
- Headless Chromium and WebKit checks passed for error dialogs, live Map previews
  and detached previews; native integration transport/cancellation checks passed.
- Independent integration-core and series numerical parity checks passed.
- Actual Qt AutoLevel comparison passed all 30 cases described above.

Reproduction tools: `scripts/native_map_selection_benchmark.mjs`,
`scripts/native_autolevel_parity.py`, and the opt-in
`time_full_resolution_gap_extension` Rust test. Benchmark receipts are generated
under ignored `artifacts/native-map-selection/`.

## Follow-up: shared parallel display counts

The next optimization replaces the separate integer Auto/histogram scans with
one lossless count distribution. Images with at least 4,096 samples are eligible;
images with at least one million samples use up to eight workers with private
tables, followed by an exact integer reduction. Counts from -1 to 65,535 use a
dense table; other integer values use a bounded sparse table. No values are
clipped. Fractional data, signed zero, or excessive sparse cardinality retain
the general implementation. NaN and infinities retain their previous exclusion.

Exact percentiles, min/max and the existing asinh histogram are derived from
the same counts. The asinh operation runs once per distinct intensity instead
of once per pixel. The distribution and detected gap value stay with the raster,
so changing percentile/minmax settings can reuse them. Mean ± 3 SD keeps the
existing source-precision calculation. Detector modes share the same raster;
raw/corrected/cake datasets retain independent display statistics.

In a final matched run of the packaged processors on the same full 9M
acquisition, shared statistics took 4.25 ms, exact percentile extraction 0.007 ms
and histogram projection 0.020 ms, replacing 54.6 ms of separate work. Selection
plus linked-guide restoration decreased from 110.0 to 60.0 ms for stored
patterns and from 114.1 to 65.8 ms for reintegration. Eight frame selections
again produced exactly matching patterns, image/mask identities, histograms,
contrast limits and linked positions. These remain warm-cache backend/transfer
measurements, excluding GUI paint. An earlier isolated source-build run measured
60.1/63.9 ms. A preliminary run overlapped an independent Qt check; it is not
used as the performance baseline.

All 60 Rust tests passed (one optional benchmark ignored), Clippy passed, and
the 30 comparisons against the actual Qt AutoLevel implementation still pass.
Additional regression cases compare full histogram bins/edges and multiple
filtered/unfiltered percentiles with the original source-precision path,
including negative values, high outliers, NaN, infinity, constant images,
parallel reduction and bounded fallbacks. Frontend and native host code are
unchanged in this follow-up.

## Follow-up: display copies and linked geometry

A split trace isolated roughly 15 ms in the live buffer SHA256 fingerprint,
even after parallel pixel conversion. Display buffers now use namespaced BLAKE3
IDs with a private pool of at most eight workers, and retain their existing Vec
allocation through Arc rather than copying it into an Arc slice. Project blob
SHA256 identities and format-2 project compatibility are unchanged. BLAKE3's
parallel API is documented at <https://docs.rs/blake3/latest/blake3/struct.Hasher.html#method.update_rayon>.
The wire contract treats buffer IDs as opaque strings and still identifies the
complete immutable byte content. Full-resolution float32 conversion is also
parallel; source scientific values remain f64 and unchanged.

Frame loading no longer builds/hashes a temporary user-only mask before replacing
it with the effective mask. Equal effective mask bytes and dimensions retain the
existing display buffer; changed masks share their immutable allocation with the
effective scientific mask. Pixel-by-pixel comparisons, rather than assumptions
about frame number or detector identity, determine whether masks can be reused.

An inspection now survives image/frame changes when calibration geometry and
shape agree. Map replies retain this inspection, allowing the existing frontend
to skip its restore request. Reintegration does not recalculate a stationary
click. Calibration/detector/shape/orientation changes still invalidate the result.

For a newly selected angle, one full-resolution angle field and conservative
64-cell row-strip bounds are cached per geometry and shape. Strips that cannot
cross the target are skipped; cell order, saddle rules, interpolation and final
coordinates are unchanged. This is an exact search reduction, unlike the existing
coarse display sampling of phase rings. Azimuth projections can also be reused.
The cache holds one geometry field, approximately 81 MB plus 2.6 MB of bounds on
the tested Eiger; it does not retain fields for every loaded frame or angle.

In an isolated matched source-build benchmark, stored Map selection decreased
from 60.4 to 37.1 ms, and reintegration from 64.4 to 39.4 ms. Frame changes needed
zero additional inspection requests. Median new-angle inspection decreased from
163.9 to 4.17 ms with a warm geometry cache. The first inspection still builds
the cache: 87.3 ms in that run, versus 161.2 ms before. Results exclude GUI paint.

The benchmark now follows the frontend's actual restore policy and compares
image/mask wire bytes using an independent SHA256 digest, because cache IDs
intentionally differ across hash algorithms. Patterns, every tested image/mask
byte, histogram bins/edges, limits, and all new/repeated linked coordinates match
the prior build. Source-build stage medians were 9.82 ms for decode/plan handoff,
0.86 ms for display conversion, 2.38 ms for the buffer fingerprint, 4.60 ms for
shared statistics, 1.11 ms for mask/processing, and 9.26 ms for packet encode/write.
Stages are measured separately; their medians need not sum exactly to the total.

All 62 Rust tests and 63 frontend tests passed, as did Clippy and integration
transport cancellation/source-mutation tests. Headless Chromium/WebKit Map and
detached-preview checks passed. Regression checks cover exact indexed contours
on partial strips, saddles and nonfinite holes, byte-exact parallel display
conversion (including signed zero and NaN), retained inspection during Map
selection/reintegration and geometry-dependent invalidation.

The final standalone processor repeat confirmed 61.4 → 37.3 ms for stored
selection, 64.5 → 39.8 ms for reintegration, and 161.2 → 4.26 ms for new guide
positions. First-guide cache construction took 88.5 ms. Exact byte/numerical
comparisons passed again. All seven Tauri processor tests passed, including
round-trip buffers and cached-buffer omission with the new opaque IDs. The new
bundle's resource manifest, ad-hoc signature, macOS 14 deployment targets and
system-only dynamic dependencies passed inspection; no visible app was launched.
