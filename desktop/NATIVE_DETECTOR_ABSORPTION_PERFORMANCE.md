# Calibrated detector absorption and map reuse

Integration → Corrections → Detector absorption now takes only sensor thickness
and absorption length. Pixel positions and surface normals come from the active
calibration and its physical detector, including orientation, binning, distortion
and image transformations. There are no independent detector-angle overrides.

The divisor is `(1 − exp(−depth / cos(incidence))) / (1 − exp(−depth))`, where
`depth = thickness / absorption_length`. The implementation uses `expm1` for
stability with thin sensors. This follows the
[pyFAI calibrated transmission definition](https://pyfai.readthedocs.io/en/latest/api/geometry/index.html#pyFAI.geometry.core.Geometry.calc_transmission).
For a planar detector the cosine is distance / distance-to-pixel in the detector
frame; rigid calibration rotations act on both ray and normal and cancel in
their dot product. Mapped surfaces use their own physical pixel-corner normals.
This replaces the old small-angle approximation with separately editable angles.

The old loop built complete two-theta and azimuth arrays and performed JSON
parameter lookups and trigonometry for every pixel. Plot built the arrays and
evaluated the correction again. The new parallel kernel reads scalar inputs
once, needs no angular arrays and retains one full-resolution float64 map shared
by single-image processing, Batch/Map snapshots and Plot. Geometry, shape or
sensor optical-depth changes invalidate that map; source counts, frame changes,
backgrounds and display preferences do not. Variance still divides by the
square of the same divisor. Preview pixels, histograms and levels retain the
existing full-resolution display contract.

## Measured native stdio timings

November 11, 2026, development build on this Mac. Synthetic 3072 × 3072 image
(9,437,184 pixels), nonzero calibrated rotations, 512 radial / 72 cake bins,
one-sample integration. Same driver/settings with a saved pre-change processor
and the updated processor. These are individual command wall times including
native raster preparation and stdio transport, excluding browser paint or physical
display scanout. Ordinary background development work was running.

| Operation | Before | After |
| --- | ---: | ---: |
| Enable correction and update results | 13,603.9 ms | 123.8 ms |
| Plot the calculated correction | 12,653.2 ms | 186.7 ms |
| Plot again | 12,178.6 ms | 175.9 ms |
| Change sensor thickness and update results | 12,317.4 ms | 127.2 ms |

Driver: `node desktop/scripts/detector_absorption_benchmark.mjs [processor-path]`.
Receipts: `artifacts/detector-absorption/timings.json`.

## Persistence and qualification

Legacy project angle overrides are discarded and an active legacy detector
correction produces a recalculation notice. New projects record the native model
version. Development checkpoints and their Undo states migrate the older field
schema as well, so live worker replacement removes the obsolete controls.
The legacy Qt project section still receives required angle keys derived from
calibration; the Qt reader retains its historical approximation and loader angle
convention, so exact detector-correction parity with that reader is not claimed.
Native project save/reopen preserves the calibrated result.

Verification includes thin/opaque limits, known mapped-surface normals across
all four detector orientations and image transforms, shared-map identity and
invalidation, cancellation, legacy project import and subsequent save/reopen,
and existing correction-preview/pixel/variance/Batch/Map regressions. Independent
NumPy/pyFAI comparisons cover full-precision corrected pixels and propagated std,
plus spline, nonuniform and curved detectors in all four orientations. The
float64 oracle uses pyFAI's NumPy incidence path; `calc_transmission` itself
constructs positions from float32 indices, which is also compared at its source
precision. Existing tight pixel/variance tolerances are retained.

Headless Chromium and WebKit check the two remaining sensor fields, absence of
angle controls, Plot/Back, unchanged science, independent preview navigation and
histograms, and the established reference/failure/configuration workflows.
No visible test window was needed.

Frontend build and 113 frontend tests pass. Native checks passed 75 library tests
(two external-fixture tests ignored), the added checkpoint-migration test, four
correction-preview tests, 31 functional flows and 15 native-session tests. Strict
Clippy passes for the production library and processor. All-target strict Clippy
is blocked by the pre-existing `items_after_test_module` finding in the unchanged
`phases.rs` color-test placement; this change does not modify that file.
The updated development processor was built and staged for Tauri.

## Further correction/Plot optimization

The subsequent [shared correction optimization](NATIVE_CORRECTION_PERFORMANCE.md)
also caches the prepared raster and accelerates exact percentile preparation.
On the same fresh 9.4M detector fixture, first Plot is now 52.3 ms and an unchanged
replot 0.3 ms. Stage profiling measures the path/efficiency kernel itself at
5.891 ms; Apply/Plot wall times include the other scientific/display work.
