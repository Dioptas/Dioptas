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
