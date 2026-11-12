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

## Historical summation diagnostic

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

## Corrected native protocol comparison

The initial summation result above is retained as a negative control. The current
PhaseSmith protocol path uses the complete native coordinator at every
checkpoint. With the same v29 protocol, source hashes, mask assumptions, supplied
metric and symmetry, standalone and Dioptas retain the same 7,277 rows, 4,125
eligible observations and 660 profile-mismatch warnings. Both give Rint 3.93649%.
Prepared-frame hashes, HKLs, flags and eligibility match exactly; numerical
intensity/sigma differences pass the unchanged native equivalence gates.
With development optimization settings matched, all 54 archived arrays are byte-exact,
including the profile diagnostics. The fresh raw-frame GUI setup and saved-recipe
replay both reproduce the reduction and candidate R1 4.11283549% (anisotropic,
90 parameters; candidate refinement reaches its iteration limit). Reference
coordinate/count grading is not performed without a reference model.
See [the full matched comparison](SCXRD_RINT_COMPARISON.md) for every control,
mask ablation, archive checks and remaining scientific limits.

## Reproducing the checks

From the worktree root, first build the native processor and frontend, then:

```sh
CARGO_PROFILE_DEV_DEBUG=0 CARGO_INCREMENTAL=0 cargo run --locked --manifest-path desktop/backend/Cargo.toml --example scxrd_fixture -- desktop/artifacts/scxrd-fixture
npm --prefix desktop run test:scxrd
# Optional measured protocol replay, always choose new output directories:
DIOPTAS_SCXRD_STEPWISE=1 DIOPTAS_SCXRD_MEASURED_DIR='/path/to/MgSiO3 example' npm --prefix desktop run test:scxrd-protocol -- /new/reduction-output
npm --prefix desktop run test:scxrd-protocol-gui -- /new/reduction-output/matched.scxrd.json /new/replay-gui-output
# Drive setup from raw frames through the GUI, rather than opening that recipe:
DIOPTAS_SCXRD_FRESH_SETUP=1 DIOPTAS_SCXRD_MEASURED_DIR='/path/to/MgSiO3 example' npm --prefix desktop run test:scxrd-protocol-gui -- /unused/recipe /new/fresh-gui-output
# test:scxrd-measured and test:scxrd-measured-gui retain the historical summation control.
```

Artifacts under ignored `desktop/artifacts/scxrd-*` retain observations, recipes,
receipts, full-precision photon-budget comparisons, screenshots and accessibility
results. GUI probes use the real Rust processor with Python unavailable and
headless Chromium/WebKit. Nine tabs at 1500×1000, 1050×760 and larger-text
1100×850 give 54 layout captures; tests check panel overflow and primary-action
reachability. They exercise actual number typing, cell decisions, track
exclusion/Undo, masks/Escape, frame keys, own-image hover, contrast, mode-switch
drafts, recipe export and WCAG A/AA Axe checks. A separate measured GUI check
covers real-scan display and cancellation. The native protocol probe additionally
checks fresh raw-frame setup (cell entry before indexing), inspected/exported
effective settings, protocol undo, 27 native layouts, readable quality reasons,
nine Axe checks, global usable/excluded view filtering and paging, and stopping
after a completed native mask checkpoint. Undo after Stop restores the prior
reduction/candidate; this is Undo of the clear-stage edit, not of processing. Headless evidence does not qualify
native OS dialogs or every Tauri/WebKit platform.

Rust regressions cover validation/invalidation, source and calibration write
protection, recipe verification/preset transfer, detector overload resets,
independent image previews, symmetry scoring, export precision and atomic edits.
Frontend model/build checks and existing powder/Map workflows guard integration.
See [review record](SCXRD_REVIEW.md) for reviewer findings and final ratings.

The corrected-protocol validation includes the full backend suite, final focused
SC regressions, 176 frontend tests, 47 Tauri-host tests, strict TypeScript
production build and native Clippy with warnings denied. Native resource staging
and the analytical photon-budget/summation smoke pass. Headless synthetic
Chromium/WebKit checks pass 54 layouts/18 Axe views; measured protocol checks pass
27 layouts/nine Axe views. All earlier failed trials and build-control differences
remain in the local evidence, with scope in the [comparison](SCXRD_RINT_COMPARISON.md).
These checks do not establish native OS-dialog behavior or crystallographic
validity outside the measurements above.


## Canonical develop integration — 2026-11-12

The native mode and protocol branch was merged into `develop` in
`/Users/clemens/Programming/Dioptas`, retaining the current rc.1 version/title,
packaging changes and independent embedded Map detector behavior. The shared
readout guard preserves both Map and SCXRD contexts. The combined checkout passes
182 frontend tests, 31 focused SC backend tests, 47 host tests, production build,
54 Chromium/WebKit SC layout checks with 18 Axe views, and the two-engine Map
detector-independence regression. Its MgSiO3 v29 replay again matches every one
of the 54 standalone stage arrays byte-for-byte with the declared matched
optimization settings. Logs and new replay products are in ignored
`desktop/artifacts/scxrd-develop-merge/`. The locally built native app is for
workflow testing, not a newly published release.
