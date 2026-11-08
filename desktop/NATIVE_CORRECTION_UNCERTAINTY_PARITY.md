# Native correction and counting-uncertainty qualification

Transfer, plate absorption and slab self-absorption run in Dioptas's Rust
processing pipeline alongside flat field, cBN and detector absorption. The GUI,
processing settings and `.dio` persistence belong to Dioptas. Dioptrin supplies
generic integration of independent pixel variances, including shared-grid
multi-detector accumulation. Python is used only by the independent reference
gate; the processor and standalone application require no Python runtime.

## Scientific contract

For original sample counts `S`, background counts `B`, background scale `b`,
offset `o` and total deterministic multiplicative correction `g`:

```
I_pixel = (S - b B - o) g
V_pixel = [max(S, 0) + b² max(B, 0)] g²
I_bin   = sum(w I_pixel) / sum(w N)
std_bin = sqrt(sum(w² V_pixel)) / sum(w N)
```

`N` contains the selected solid-angle and polarization normalization. Pixel
splitting accumulates each pixel's contributions before squaring its bin
weight. Empty bins retain the established zero intensity/std convention.
Negative background-subtracted intensities retain their original counting
variance. Detector factors scale std by their absolute value, including
negative and zero factors. Combined detectors sum signal and independent
variances before the shared normalization; corrected detectors now support
counting errors. Combination still requires solid-angle correction.

**Include background counting noise** defaults on, is saved per configuration,
and can be turned off for a background treated as a fixed reference. Offset
does not add variance. The model assumes original inputs are Poisson counts
with unit counting gain; arbitrary rescaled/previously corrected input files
do not establish that assumption. Flat fields, transfer references, absorption
parameters, geometry, polarization and normalization factors are treated as
fixed calibrations. Their estimation uncertainties, sample/background
covariance, cross-detector covariance and covariance between split bins are
not propagated. Azimuthal std remains a separate measure of angular spread.
Fitted pattern-background uncertainty is also excluded. Series normalization
rescales stored std using the applied factor, treating that factor as fixed.

Add/average actions retain independent input counting variance: sums use the
sum of input variances; averages divide that variance by the number of inputs
squared. Source variances are owned by the session/project and follow image
transformations. External TIFF/NPY images cannot carry this native project
metadata; reloading an exported image starts a new input-count assumption.

## Corrections and controls

- **Transfer:** multiplies by `original / response`, without mean normalization.
  The two references must have the source detector dimensions and finite,
  strictly positive samples. Incomplete pairs remain disabled. Invalid/zero
  reference pixels are rejected explicitly rather than silently repaired.
- **Plate:** divides by `exp(-mu t / |n · d|)`, for a plate after the sample.
- **Slab:** divides by the depth integral of incident and outgoing transmission.
  With `mu_i = mu / |cos(tilt)|`, `mu_d = mu / |n · d|`, the factor is
  `(exp(-mu_i t) - exp(-mu_d t)) / (mu_d - mu_i)` with the continuous equal-path
  limit `t exp(-mu_i t)`. The Rust implementation uses `expm1` to avoid
  cancellation. This preserves the Python convention, including its thickness
  factor; it is not silently normalized to unit thickness.

The native GUI supports direct attenuation entry or formula/material and density
lookup using Rust `xraydb` 0.4.1. Formula-derived μ follows the calibration
wavelength and uses total Elam attenuation, matching Python XrayDB. Density 0
uses the material database. Energies outside 100–800,000 eV fail explicitly.
The correction-only plot view remains outside this step; no Python lookup is
invoked silently.

The full embedded database is disabled. The app embeds only 329,526 bytes
(about 322 KiB) of element properties and Elam photoabsorption/scattering data,
retaining all 98 Elam elements without Chantler, fluorescence, or duplicate
Waasmaier–Kirfel tables. The dataset is loaded once without file/network access.
[Subset provenance and regeneration](backend/data/README.md) record exact hashes,
versions, and source attribution; projects also record the data fingerprint.
Thickness is in mm, attenuation in mm⁻¹ and alignment in degrees. Tilt measures
the normal relative to the beam; rotation follows pyFAI azimuth. As in Python,
zero thickness or zero attenuation gives unity. Path cosines are bounded by
`1e-10`; nonpositive/nonfinite final transmission or overflow is rejected
atomically. cBN/detector absorption retain their established definitions.

The existing **Corrections** type list contains all six choices, with no new
toolbar. Image background owns its counting-noise control. Current-image
correction edits use the shared scientific Undo/Redo history. Reference planes
remain in source order and follow rotations/flips together with the image.

## Persistence and data flows

Native format-2 projects own both transfer reference planes, including disabled
and partially loaded pairs, analytical parameter drafts, background-noise
policy, formula/material/density/source selection and derived-image source variances. Reopening and recalculating works
after the source files have been deleted. Enabled transfer metadata retains
the scalar filename layout expected by the original Python reader; native
cached arrays are stored separately. A changed legacy reference filename takes
precedence over an older native cache. The original Python reader still needs
the transfer files; native offline ownership does not extend its capabilities.

Pattern error columns (`xye`, `fxye`) use propagated counting std. Batch and Map
retain per-profile std, including normalization, stored-only selection and
native project reopening. Processed HDF5 adds optional `counting_std` and
`desktop_original_counting_std` matrices; CSV adds `counting_std` when available.
Older files without these optional arrays continue to load without invented
errors. Cake intensity continues through the same correction pipeline;
individual cake-bin uncertainty maps are not exposed by the desktop interface.

## Reproducible evidence

All checks run through the existing native CI gate:

- `backend/tests/functional_flows.rs`: numerical gain/background laws across
  2θ/Q/d, sectors, ROI and supersampling; transfer/plate/slab with a rotated
  detector, export, Undo and owned offline projects; active/disabled/partial
  transfer pairs; invalid references and absorption rollback; corrected
  multi-detector sigma; derived-average variance; corrected Batch/Map std
  through normalization, HDF5 and project reopening without source files.
- `scripts/native_processing_parity.py`: original Python correction formulas,
  asymmetric transfer references and Python/Rust project cross-read/write.
- `scripts/native_uncertainty_parity.py`: independent NumPy weights for a
  supersampled sector, nonuniform flat/transfer maps, all four absorption
  corrections, negative corrected
  intensities, background noise on/off and solid angle on/off. The checked
  std differs by less than `4e-13` on this synthetic fixture. Independent
  Gauss–Legendre quadrature checks the slab depth integral near equal incident
  and outgoing paths, where the original subtraction formula loses precision.
- `scripts/native_material_parity.py`: 84 independent XrayDB comparisons across
  both correction types, six materials/formulas, seven energies, a near-edge
  pair, grouped/fractional formulas and named-material density. Formula mode is
  compared against explicit μ through intensities and propagated std. Invalid
  materials, density and out-of-range energy preserve the preceding state.
- `scripts/native_corrections_smoke.mjs`: headless Chromium/WebKit controls,
  transfer loading, draft commit/enable, formula/density lookup, project reopening and panel layouts at
  1440 and 1100 px. Receipts/screenshots are under `artifacts/native-corrections`.
- Dioptrin tests: explicit variance agrees with the independently implemented
  Poisson path for counting, polygon splitting and supersampling; a hand-built
  fractional LUT checks squared weights/masking; negative signals, detector
  gains and invalid variance rejection are covered.

Cylinder and sphere absorption remain unsupported and fail atomically.
