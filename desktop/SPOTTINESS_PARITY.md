# Native Spottiness diagnostic

Integration → Pattern provides **Show Spottiness**, **Relative spread
(std / mean)** and **Save Spottiness…**, matching the Qt Options control group.
Enabling Show Spottiness requests `integration_settings.azimuthal_std` from the
existing worker. No second image processing session or alternative spread
estimator is created. The two preferences belong to each configuration and
survive format-2 project save/reopen and development checkpoints.

The companion reuses PatternView, its shared gestures and linear y axis. Its
radial range follows the main pattern in both directions; y navigation remains
independent. Radial units, click markers, phase positions and the shared footer
follow the main plot. The diagnostic has its own std or std/mean labels; Poisson
counting errors remain separate `sigma` values. Phase positions are mirrored as
full-height lines without duplicating the phase legend.

## Scientific ownership

The worker publishes a `pattern.spottiness` product containing the original
integrated x, mean, population std and relative spread. Background subtraction,
overlay interpolation and fitted-background clipping of the displayed pattern
do not change this product. Its x grid can consequently extend beyond a
background-clipped main pattern; the visible radial range remains linked.
Native integration's leading/trailing exact-zero trimming applies to all
integrated arrays together. Disable Trim zeros to retain these edge bins.

Relative spread uses Qt's exact convention: the threshold is 1e-12 times the
largest finite absolute original mean, with a unit floor. A ratio is undefined
for nonfinite std/mean, nonpositive means, means at/below the threshold or an
overflowing division. Undefined values are null in JSON, gaps in the plot and
NaN in CSV. The threshold uses the entire original integrated curve, independent
of plot zoom, clipping and background subtraction.

Single-pattern CSV is a native `integration_save_spottiness` command with radial,
mean, std and relative columns in float64 round-trip precision, a radial-unit
header and an explicit population/counting-error distinction. It always exports
all available original diagnostic samples. A temporary file in the destination
directory is synced and atomically published; failed/cancelled writes preserve
the previous destination. Tauri owns the save dialog; cancelling it does not
send a scientific command. Missing statistics are rejected. Existing Batch
exports and pattern figure rendering are unchanged.

The implementation also fixes an existing background/d-spacing alignment bug:
Patterns::ingest reversed descending x, intensity and counting errors for
background processing, but previously omitted the spread array.

## Supported modes and limits

Polygon, subpixel and pyFAI-compatible full splitting reuse their existing
Dioptrin spread calculation and selected mask, ROI, azimuth sector, solid-angle
and polarization normalization. Admitted image backgrounds, flat fields,
transfer and absorption corrections run through the existing native processed
image path before integration. The spread therefore describes those processed
pixel values. Stored normalized Batch rows retain the corresponding mean/std
pair when selected into Integration; relative spread is invariant to positive
common scaling.

Combined patterns have no native population-spread product. The controls state
this explicitly, hide the diagnostic and disable save; direct export also
rejects the combination. Plain imported pattern files have no azimuthal std and
are treated similarly. Counting errors never substitute for unavailable spread.

Qt's pyFAI spottiness helper selects bbox CSR overlaps. The desktop retains the
selected integration method, including full polygon overlaps for pyFAI-compatible
mode. Consequently universal bitwise Qt agreement is not claimed. Direct-beam
polygon behavior remains an existing approximation; the independent measured
image oracle excludes pixels within 1 degree of the beam. No new detector or
correction compatibility is claimed beyond the native integration/correction
ledgers.

## Validation (November 10, 2026)

- Frontend build and 105 unit/architecture tests pass.
- The backend library suite passes 65 tests (two external-data checks ignored);
  native Clippy and formatting pass. The Tauri CSV dialog contract test passes.
- Native focused tests cover three splitting methods × three radial units,
  mean/std/counting-error separation, full CSV readback, fitted background
  clipping, loaded partial-overlap background, warm d-spacing reintegration,
  mask/ROI, configuration and project restore, normalized stored Batch rows,
  unavailable imported/combined results and export rejection.
- Rust helper tests cover zero, tiny, negative and nonfinite means, strict cutoff,
  overflowing ratios and cancellation both before and during staged CSV writing.
- `native_spottiness_parity.py` uses Qt's independent `weighted_spread` helper
  with independently built pyFAI full CSR overlaps on CeO2/Pilatus data, solid
  angle on/off, 2θ/Q, an azimuth sector and a beam mask. Maximum mean differences
  are 0.00252 and 0.00190; maximum std differences are 0.04341 and 0.01063, within
  rtol 2e-4 / atol 0.01 for std. Four synthetic zero/negative/tiny/heterogeneous
  frames also check Qt relative-spread conventions. Image background plus
  normalized flat-field correction is checked against independently calculated
  processed pixels and pyFAI full CSR weights. Receipt:
  `artifacts/spottiness-reference.json`.
- `spottiness_smoke.mjs`: headless Chromium and WebKit at 1000 × 668 in Standard
  and Larger text, show/hide, relative mode, zoom in either plot/reset, radial
  units, shared click markers/footer, CSV save, dialog cancellation and native
  publication errors. Screenshots: `artifacts/spottiness/`.
- Existing Integration responsive smoke passes Chromium/WebKit, including
  phase controls, Batch selection and renderer preservation.

Run from desktop with `npm run build`, `npm test`, `npm run test:spottiness`,
`npm run test:spottiness-reference` (explicit independent Python environment),
and from the repository root with `cargo test --locked --manifest-path
 desktop/backend/Cargo.toml --test spottiness --test zero_trimming`.
No visible/native application window was opened. No release or publishing work
is included; this feature is committed on its assigned isolated branch for
coordinated integration with the other parity features.
