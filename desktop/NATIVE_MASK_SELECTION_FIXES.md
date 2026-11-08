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

## Follow-up: fused pixel preparation and streaming transfer

Source decoding retains the existing Dioptrin-IO codec and original typed sample
storage. Numeric conversion now writes source rows directly to their final
bottom-up f64 positions, using up to eight workers for large planes. This removes
the separate full-plane row-swapping pass. All supported scalar types preserve
their previous conversion rules, including half floats, NaN payloads, signed
zero, and rejection of integers beyond the existing exact-f64 bound.

The processor emits a response header and immutable buffers using vectored
writes under the existing packet mutex, instead of allocating/copying a full
image-sized packet first. The protocol and caching rules are unchanged. Partial
writes, interruptions and empty buffers are handled explicitly. On Unix, a
duplicate of the stdout pipe is used through a binary File writer, avoiding the
text stdout line-writer layer; other platforms retain their existing stdout.

In a matched warm-cache release run against the previous standalone processor,
decode/pixel-preparation handoff decreased from 9.95 to 8.17 ms, and response
encoding plus write/flush from 9.07 to 8.03 ms. Stored Map selection decreased
from 34.91 to 32.98 ms; reintegration from 38.82 to 37.09 ms. These same-run
improvements are smaller than a comparison against the earlier 37/40-ms run;
the matched numbers are the performance claim. Timings exclude GUI painting.
The transmitted full-size float32 plane remains approximately 40.6 MB for this
3262 × 3108 image. No spatial sampling or change in numerical precision is used.

Patterns, every compared image/mask byte, histogram bins/edges, limits and linked
coordinates match the baseline. All 65 Rust tests and seven Tauri processor
tests passed, with Clippy warnings denied. Integration transport tests passed
for cancellation and source mutation, and headless Chromium/WebKit checks
passed for live Map results and detached previews. New regressions cover exact
orientation of every supported scalar type, odd-height parallel row partitions,
precision guards, and partial/interrupted vectored writes with cached buffers.

The final standalone repeat measured 36.47 → 34.85 ms for stored selection and
41.47 → 37.53 ms for reintegration. Decode/preparation was 9.77 → 8.14 ms;
packet encoding plus write/flush was 9.76 → 8.44 ms. Exact output comparisons
passed again. The bundle's manifest, signature integrity, macOS 14 deployment
targets and system-only dynamic dependencies passed inspection. The existing
user app and earlier artifacts were left unchanged.

## Follow-up: avoid discarded selection metadata

Map/Batch selection previously dispatched a complete open-image command and
discarded its UI response before constructing the final selection response.
The shared open-image model operation is now called directly inside the existing
rollback boundary. Public loading still uses that same model operation. Revision
increments, source validation, processing, masks and integration are preserved.

Map selection also omits calibration-ring display paths that its response already
cleared, and avoids attaching identical Map metadata twice. Calibration and
Integration responses retain their ring products. Angular reference data in
the calibration controls is retained in every mode.

The immutable mask display buffer now owns its masked-pixel count. Equal masks
share that owner with the effective mask, so normal UI snapshots do not recount
the full detector. Cached counts are used only for the identical Arc allocation;
temporary bulk masks with a different owner retain the exact counting fallback.
The count and buffer are replaced together on mask changes and restored together
through checkpoints. One duplicate retained mask allocation is also eliminated.

A first timing repeat was inconsistent while another CPU-intensive job was
running. That job was preserved. Normal and reversed benchmark order then both
showed a gain: stored selection medians were 32.79 → 29.10 ms and 34.24 → 28.09 ms;
reintegration was 36.30 → 32.00 ms and 36.78 → 31.75 ms. Pooling the same eight
frame samples per mode across both runs gives 33.62 → 28.28 ms for stored patterns
and 36.65 → 31.86 ms for reintegration. These are warm-cache backend/transfer
measurements under background load, excluding screen painting. Results are
reported as ranges rather than a precise idle-machine guarantee.

All 65 Rust tests passed and Clippy passed with warnings denied. Headless
Chromium/WebKit integration workflows, live Map/detached previews and native
transport cancellation/source-mutation checks passed. Image/mask bytes, patterns,
histograms, limits and linked coordinates remained exact in both benchmark
orders. The benchmark additionally checks complete UI state (apart from elapsed
time), Map metadata and ring products against the previous build.

The final packaged repeat measured 33.15 → 28.92 ms for stored selection and
37.75 → 33.59 ms for reintegration. Full workflow-state and Map-metadata
comparisons passed, excluding only elapsed time, as did all byte/numerical
comparisons. The new standalone bundle passed resource, signature-integrity,
deployment-target and native-dependency inspection. No user window was restarted.

## Correction: acquisition invalid pixels outside structural gap strips

The earlier structural-margin qualification did not establish complete automatic
acquisition masking. A user report reproduced a scientifically bad pattern even
though the displayed red mask was applied: 15,160 detector invalid-marker pixels
remained outside the structural mask. Their large values dominated integration.
The existing tests checked the displayed gap bands but missed this numerical case.

Automatic Eiger acquisition masks now corroborate nonzero dummy codes against
nearly uniform complete bands in the known detector gaps. Matching invalid values
are then included throughout the acquisition mask, including disconnected bad-pixel
regions. Zero is still extended only at structural boundaries; valid interior
zeros and ordinary large counts are retained. Recognized codes include minus one
and the supported integer-type maxima; f64 project caches retain recognition of
those original source markers. The inferred mask remains cached per detector,
shape and unchanged source file, as in the existing acquisition-mask workflow.

For the actual `eiger_0000.h5` fixture the marker is uint32 maximum (4,294,967,295),
whereas the adjacent TIFF uses int32 maximum. Automatic masking now includes all
887,556 marker pixels, compared with 872,396 previously. The median integrated
intensity changes from 9,429,614 to 228.846 counts. The automatic pattern and cake
exactly match an explicitly loaded mask with the same exclusions. The supplied
`eiger_0000.mask` has 32 additional custom exclusions; it remains a distinct mask,
and ordinary large measured counts are not automatically discarded.

New regression coverage explicitly compares automatic and manually selected
invalid-pixel exclusions in the pattern and cake, including Poisson errors and
the user-mask switch off. Synthetic max/minus-one/zero fills retain valid interior
zeros and large measured values, and persist through Map and project operations.
`scripts/native_detector_gap_integration_check.py` validates the real 9M data on
frames 0, 1, 7, 250 and 624 and compares stored/reintegrated Map profiles. This is
sampling of the real acquisition, not a universal claim about frame-varying dummy
locations. All 65 Rust tests, Clippy and native transport checks pass.

The histogram option was confirmed by the user to be correct after restarting.
Display preferences and histogram code were left unchanged for this correction.

## Correction: Map detector histogram defaults on restart

The Map detector used a separate display-preference hook that explicitly passed
`false` for gap filtering, unlike the Mask workspace. Its initial source-precision
contrast preparation also selected `false` based on Map mode. Both defaults now
enable gap filtering for detector images. The Map heatmap keeps its independent
unfiltered default, and an explicitly saved user choice is still remembered.

Fresh-profile headless Chromium/WebKit regressions check that the Map detector
checkbox starts checked, the map heatmap remains independent, and deliberate
off/on changes survive frontend reloads. Existing live Map and detached-preview
checks pass in the same run. Frontend unit tests and TypeScript/Vite build pass.
The complete Tauri host is rebuilt to embed the corrected frontend; copying only
the updated processor into an older app would retain the old histogram defaults.

The numerical regression was rerun against the processor and resources inside
`Dioptas Rust Map Contrast.app`. It integrates the complete 625-frame Eiger HDF5
acquisition and compares stored and click-to-reintegrate profiles at frames 0,
1, 7, 250 and 624. Both warm and cold bulk HDF5 paths pass; the cold path starts
without an open detector image or a loaded user mask. Toggling histogram gap
filtering leaves stored/reintegrated profiles unchanged. Disabling the user-mask
switch and reintegrating the Map still excludes detector-invalid pixels. These
checks complement the exact explicit-mask pattern/cake comparison above and
are recorded in `artifacts/native-mask/real-eiger-integration.json`.

## Batch and other integration routes

`scripts/native_detector_gap_workflows_check.py` compares the Eiger detector with
a Custom uniform detector having the same geometry and **no automatic mask**.
The reference uses an explicit mask of the 887,556 acquisition dummy pixels.
Its unmasked control produces a median intensity over 1,000 times larger, so
the comparison is sensitive to missing exclusions rather than merely matching
two automatic-mask paths.

The checks cover all 625 stored Batch profiles on warm and cold bulk HDF5 paths,
Batch reintegration and selected-frame cakes, folder/multiple-image integration,
ordinary TIFF and combined/pattern-only HDF5 loading, frame navigation, explicit
reintegration, CSC/CSR layouts, azimuth limits, detector ROI, background/flat-field/
absorption corrections, dynamic-mask fallback, the disabled user-mask switch,
automatic processing, live Map appends, Poisson-error export, derived images,
rotations, cached `.dio` pixels and duplicated configurations. Numerical receipts
record the exact processor hash in `artifacts/native-mask/real-eiger-workflows.json`.

The audit found an additional failure in Image → Add: arithmetic changed the
dummy codes before automatic-mask discovery, contaminating 1,957 of 2,000 profile
bins in the real TIFF pair. Corrected image export could similarly change or
overflow those codes. Add/Average now union the physical acquisition masks from
the original inputs before arithmetic, transforming that union back to the
source layout. Derived and saved invalid samples use the reserved int32 maximum
marker. Using minus one instead was rejected by the corrected-export comparison:
valid negative corrected counts could also equal minus one and become excluded.
Original source files and valid sample arithmetic are unchanged.

The mask-cache source key distinguishes derived/project-cache pixels from the
original disk samples, preventing a union from a derived image from leaking into
an original same-path F64 input. Image batch actions share the existing first-load
detector assignment rules. A synthetic Rust regression checks minus-one/int32-max/
uint32-max fills, isolated invalid pixels in different inputs, Add/Average,
rotation, project reload, return to original F64 sources and saved TIFFs. Valid
negative counts that become minus one remain unmasked. All 66 Rust tests and
Clippy pass; the optional external-data timing test remains ignored.

Code inspection confirms that ordinary/automatic/calibration validation and cake
integration use `calculate_products` with `integration_mask`. The Batch/Map/live
series owner builds the static physical mask before the combined HDF5 plan, or
refreshes masks before resident integration in the processing/plugin fallback.
Prepared results are validated against a key containing the scientific mask.
Histogram filtering does not select any of these masks. This qualifies the tested
fixed-mask Eiger acquisition and the listed routes, not every possible detector
or acquisitions whose invalid locations change frame by frame.
