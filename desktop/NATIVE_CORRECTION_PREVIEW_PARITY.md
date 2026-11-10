# Native correction Plot / Back previews

Integration → Corrections now offers Qt's **Plot / Back** workflow for flat
field, transfer, cBN seat, detector absorption, plate, slab, cylinder and sphere.
The preview uses the existing full-resolution detector renderer with square
pixels, shared gestures, its own histogram, levels, scale, palette and zoom.
Back returns to the preceding detector or Cake view. The recent responsive
Integration layout is retained.

## Scientific display contract

Qt's `CorrectionController` plots each model's `get_data()`, rather than a
corrected source image. The native preview follows that divisor convention:

| Choice | Plotted values | Units |
| --- | --- | --- |
| Flat field | Mean-normalized response, including the existing zero-response replacement | dimensionless |
| Transfer | Response / original; processing multiplies by the reciprocal | dimensionless |
| cBN seat | Anvil and seat transmission | dimensionless |
| Detector absorption | Relative oblique-incidence absorption efficiency | dimensionless |
| Plate | Transmission | dimensionless |
| Slab | Existing depth integral | mm |
| Cylinder | Native mean transmission, including an enabled capillary wall | dimensionless |
| Sphere | Native mean transmission | dimensionless |

The existing slab zero-attenuation/zero-thickness identity convention is
retained. The validated native cylinder/sphere geometry and quadrature remain
as documented in [round-sample qualification](NATIVE_ROUND_SAMPLE_CORRECTION_PARITY.md);
previews do not reinstate the legacy ray-model defects.

`Processing::preview_map` isolates one actual native series operation. The
analytical maps reuse `absorption` or the existing sample transmission maps;
flat/transfer planes follow the source image's rotations and flips. Backgrounds,
detector factors, masks, ROI and other corrections never enter the plotted map.
Formula lookup and capillary materials use the current native scientific state.
No correction formulas or new models were introduced. Display buffers use the
same full-resolution float32 transfer as detector images; native levels and
histograms use the original float64 map. Gap filtering is unavailable for maps.

Loaded flat/transfer maps can be plotted while disabled. An incomplete transfer
pair is unavailable. Analytical Plot requires the committed correction to be
enabled, as its Qt correction object does. Failed/invalid previews return an
explicit error rather than a fabricated identity map.

## Ownership and restoration

`integration_correction_preview` returns a dedicated binary raster and metadata
without replacing the session image, raw pixels, processed values, pattern,
cake, geometry, masks, path, HDF5 dataset/frame, transforms, history or project
configuration. It does not save a preview into projects or create another
processing session. Optional revision/configuration guards reject outdated
requests. Calculation uses the existing controlled/cancelable stdio path.

The dedicated React adapter owns the selected map. The source renderer remains
mounted behind the preview; preview histograms and navigation never write source
preferences. Back restores the source view and clears preview readouts. Hover
shows map factors (or the slab integral in mm), and native geometry-only pixel
queries supply calibrated 2θ/Q/d without reading image intensity. Preview clicks
are local and do not replace the source's linked selected position.

Committed edits/removal, mode/Settings/configuration changes and source changes
dismiss the map. A failed edit also dismisses it. Superseded or late responses
cannot reopen a preview. Switching correction types can replace the displayed
map; its header always offers Back. Fresh previews auto-level, as in Qt; their
temporary display settings are discarded on Back. Source image saving is disabled
while a map is visible, preventing a preview PNG from being mislabeled as detector
counts or paired with source TIFF data. Pattern/cake processing and exports keep
their existing ownership. There is no separate correction-map data export.

## Verification

- `backend/tests/correction_previews.rs`: all analytical maps match the actual
  per-pixel pipeline divisor while other processing is active; native metadata,
  raw/processed/mask/cake buffer identities, complete patterns and source/history
  state remain unchanged. Disabled/reference/partial/removal/invalid request
  cases, every rotation/flip, HDF5 dataset and nonfirst frame, geometry-only
  readout, formula attenuation and offline project ownership are covered.
- `scripts/native_processing_parity.py`: pixel maps checked against the actual
  Qt cBN, oblique, plate and slab formulas, independent flat normalization and
  response/original arrays; unchanged pattern/cake/source products before/after.
- `scripts/native_round_absorption_parity.py`: preview samples checked against
  independent NumPy volume/ray quadrature for pencil, partial and full footprints,
  tilted cylinder and shell, including a formula-derived capillary wall with a
  nonabsorbing sample. Existing native/reference tolerances remain unchanged.
- `scripts/correction_previews_smoke.mjs`: real Rust-backed headless Chromium and
  WebKit controls; reference availability, map readouts/units, native Auto levels,
  independent levels/zoom, Back to detector/Cake, replacement/removal/disable,
  mode/configuration switching, late-response rejection, failure recovery and
  1440/1100-pixel layouts. Receipts/screenshots: `artifacts/correction-previews/`.
- Frontend build and 105 existing frontend tests, responsive Integration
  checks, the complete Rust test suite (including 63 library tests, three new
  preview tests and 31 native functional flows; two external-fixture benchmarks
  ignored), and strict Clippy.

The separately required `test:ui-components` check fails its unrelated existing
Phase parameters scrollbar assertion (`0` px versus expected `12` px). Rebuilding
the same fixture with the unchanged baseline `ImageIntensity.tsx` reproduces the
identical failure; all other imported fixture styles/components are unchanged.
This feature does not change global scrollbar styling or that fixture.

Routine checks are headless; no native preview windows or user processes were
opened, moved or terminated. Python is used only as an explicit independent
reference in this checkout's own environment, never as a production fallback.
