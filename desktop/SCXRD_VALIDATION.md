# SCXRD validation and boundaries

Branch `codex/scxrd-native` starts at develop `70962477`. Native PhaseSmith
kernels are pinned at `e47507f4adf32ea2a137ddf6b735db88f8a67537` (single-crystal
and workflows 0.8.1). This is the installed source identity; historical references
to a different product/release name are not treated as numerical compatibility.

## Independent synthetic scan

`backend/examples/scxrd_fixture.rs` generates 161 256×256 TIFF exposures using an
analytic Ewald crossing and perspective projection, independently of the
PhaseSmith indexer/predictor. It has a rotated 7×9×11 Å orthorhombic cell, 333
crossings, Gaussian spots, flat background and no random counting noise. The
fixture is a geometry/photon-budget test, not a structure or realistic detector
benchmark.

Blind indexing recovered 7.0000019×9.0000097×10.9998957 Å with angles
90.000774, 90.000020 and 90.000285°. Of 333 integrated observations, 258 passed
quality flags. For these, original-count photon-budget relative error had median
0, 95th percentile 1.43e-16 and maximum 1.44e-16 using a 6-pixel spatial and
1.5° rocking half-aperture. Background on/off gave identical original-count
intensity and counting sigma for matched tracks/support after removing the
physical correction. Recipe reopening and rerunning reproduced every reflection
exactly in the same executable. A bounded candidate-search/CIF smoke also
exercises the optional search/export path; the photon fixture does not encode an atomic structure, so its R1 is not
a correctness metric. The powder image, geometry and pattern were
unchanged. This does not establish cross-platform bitwise reproducibility.

## Measured MgSiO3 diagnostic

The optional private-data probe admits the 144-frame Eiger example, 2162×2068
pixels, with its CeO2 PONI. It explicitly declares omega start -36°, step/exposure
0.5°, axis (-1,0,0), excludes the first two seat frames, and disables the omega
baseline for this diagnostic. These are declared settings, not metadata discovery.

The blind rank-one cell was 8.81318×5.18233×18.23665 Å with angles
90.0141,89.9922,90.0608°. There were 4,483 observations, 3,364 tracks and 3,010
unflagged indexing positions. Because 12 candidates remained, automatic mode
paused; the diagnostic script explicitly selected rank one. This is not proof
of automatic sample-lattice selection on arbitrary scans.

With supplied metric 8.8101×5.1824×18.2288 Å/90° and explicit geometry refinement,
1,781 training and 447 withheld spots gave withheld detector RMS
0.7565→0.3168 pixels, omega RMS 0.1575→0.1369°. The nine-parameter fit converged
without bound contact (condition 15.50; maximum correlation 0.9885).

Summation yielded 2,306 rows, 2,131 usable observations, 757 Pbca families and
530 repeated families. **Rint was 59.0%, CC½ 0.9021.** No absorption correction or
scan scaling was applied. Thus measured geometry and end-to-end operability are
demonstrated; intensity accuracy and parity with the former profile/scaling
workflow are **not qualified**. No measured structure-solution claim follows
from this probe. Historical 4.1% versus 5.14% R1 results used a different reduction
and ADP model; they are not benchmarks for these new summation intensities.

## Reproducing the checks

From the worktree root, first build the native processor and frontend, then:

```sh
CARGO_PROFILE_DEV_DEBUG=0 CARGO_INCREMENTAL=0 cargo run --locked --manifest-path desktop/backend/Cargo.toml --example scxrd_fixture -- desktop/artifacts/scxrd-fixture
npm --prefix desktop run test:scxrd
# Optional local measured data; not required for the synthetic suite:
DIOPTAS_SCXRD_MEASURED_DIR='/path/to/MgSiO3 example' npm --prefix desktop run test:scxrd-measured
npm --prefix desktop run test:scxrd-measured-gui
```

Artifacts under ignored `desktop/artifacts/scxrd-*` retain observations, recipes,
receipts, full-precision photon-budget comparisons, screenshots and accessibility
results. GUI probes use the real Rust processor with Python unavailable and
headless Chromium/WebKit. Nine tabs at 1500×1000, 1050×760 and larger-text
1100×850 give 54 layout captures; tests check panel overflow and primary-action
reachability. They exercise actual number typing, cell decisions, track
exclusion/Undo, masks/Escape, frame keys, own-image hover, contrast, mode-switch
drafts, recipe export and WCAG A/AA Axe checks. A separate measured GUI check
covers real-scan display and cancellation. Headless evidence does not qualify
native OS dialogs or every Tauri/WebKit platform.

Rust regressions cover validation/invalidation, source and calibration write
protection, recipe verification/preset transfer, detector overload resets,
independent image previews, symmetry scoring, export precision and atomic edits.
Frontend model/build checks and existing powder/Map workflows guard integration.
See [review record](SCXRD_REVIEW.md) for reviewer findings and final ratings.

Final automated checks: 383 native backend tests passed (two existing tests
ignored), 175 frontend tests passed, 47 Tauri-host tests passed, strict TypeScript
production build and native Clippy with warnings denied passed. Native sidecar
and resource staging passed. Existing headless Calibration, Integration and Map
regressions passed in Chromium and WebKit. These checks do not establish native
OS-dialog behavior or crystallographic validity outside the measurements above.
