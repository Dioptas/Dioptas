# Detector combination

Implemented in the isolated `codex/detector-combination` checkout. The reference
is Qt's `ConfigurationController`, `ConfigurationWidget` and `DioptasModel`.

The existing `DioptasModel.configurations` and standard `.dio` project state are
the starting point. This work adds selection of those configurations to the
React command boundary so factors, calibration and masks can be inspected and
edited independently. It does not replace configuration management or add a
second scientific implementation.

## Workflow

For a project with at least two configurations, a compact bar offers the selected
configuration, its image factor, independent Combine patterns / Combine cakes
switches, and Save combined pattern. Factor commits on blur or Enter and uses
`ImgModel.factor`, like Qt. It affects that detector's corrected pixels before
integration. It does not alter another detector's pixels, geometry or mask.

The left display remains the selected detector image or the cake. Combining
operates on calibrated diffraction coordinates, never on an image mosaic.
Detector contrast limits, linear/log scaling, palettes and Auto preferences
are remembered per configuration during the session; individual and combined
cake displays have separate contrast memory. The current scientific image,
calibration, masks, corrections and loaded project state remain in the existing
configuration models. Calibration workflow metadata follows configuration selection.

Combination requires an image and calibration in every configuration. An
incomplete configuration is identified in the bar; unavailable results are
cleared. The controls retain the ability to turn combination off. The normal
single-detector behavior returns when its switch is off.

## Scientific contract

The selected configuration supplies the output radial unit and bin count, cake
azimuth bin count, polarization and solid-angle setting, as Qt does. All
configurations supply their own corrected/scaled image, geometry, mask and ROI.
Combined coverage spans all detectors, including gaps; overlap is accumulated
before normalization, rather than averaging normalized patterns or cakes.
Qt's combined path does not apply the individual 1D/cake azimuth-sector settings;
this interface keeps that behavior.

The pyFAI selection calls the existing Qt model combination methods. The desktop
restores its explicit processing policy after Qt's cake entry point activates
individual cakes. No background worker or scientific HTTP server is introduced.

For a compatible installed Dioptrin with `MultiIntegrator.integrate2d`, the
Dioptrin selection uses that shared-grid API with `normalization="absolute"`.
The adapter supplies common physical bin ranges and independent detector masks
and geometry. Pattern combination uses one azimuth bin of the same native
accumulation path, preserving the absolute detector normalization and fractional
pixel weights of the new API. Legacy `MultiIntegrator.integrate1d` has a different
relative/row-normalization contract and is not substituted silently.

Spline, curved or nonuniform detectors, detector supersampling, disabled
solid-angle correction, and older/missing native APIs retain the existing pyFAI
combination path. Actual backend and any fallback reason are present in state
and combination-button tooltips. Pattern and cake integrators retain separate prepared grids and are cached by geometry,
mask, unit and shared radial bounds and released on the processing thread.
Dioptrin remains optional.

The combined pattern uses 2θ, Q or d. Like Qt's combined model, the cake is in Q
when the selected radial unit is Q, and in 2θ for both 2θ and d selections.
Axis labels, live readings, physical linked clicks, phase guides, Auto intensity,
and exported cake coordinates follow the actual cake unit. Ordinary cakes keep
their existing 2θ convention.

## Saving and persistence

Save combined pattern writes the displayed combined result using the existing
`xypattern` writer and supports Qt's XY, CHI, DAT and FXYE choices. The ordinary
Save displayed pattern action also saves the combined result when it is shown.
Cake PNG, TIFF, TXT and CSV saving and cake Auto levels use the displayed combined
array rather than the selected detector's ordinary cake.

Images, geometry, masks, factors and selected configuration use standard `.dio`
state and remain readable in Qt. Combination switches and per-configuration
calibration workflow values use the optional `react_desktop` attribute. Qt can
ignore that attribute; saving again in Qt does not retain these desktop options.
Per-configuration contrast memory lasts for the desktop session.

## Verification

`desktop/tests/test_combination.py` compares the actual Qt model against the
command boundary for 2θ/Q/d, overlapping/disjoint coverage, unequal image shapes,
pixel pitches, distances and rotations, factors and masks. It verifies restored
individual results, exact preservation of geometry/masks, combined output data,
project round trips, configuration workflow metadata, rejected invalid input,
physical cake-click conversion, optional-engine fallback and native cache lifetime.
The local native wheel was built from Dioptrin commit `7e6b73b` in
`/Users/clemens/Programming/Dioptrin-multi2d`. That API is not released yet; the
ordinary optional dependency pin is unchanged, and older installations use the
capability-checked pyFAI fallback. Only this isolated checkout's Python
environment was given the local wheel.

With pyFAI 2026.9.0, the six 2θ/Q/d and overlapping/disjoint comparisons give:

| Metric | Largest measured difference |
| --- | ---: |
| Combined pattern, relative L2 | 0.156% |
| Cake, relative L2 over common populated bins | 0.411% |
| Cake, relative L2 over all bins | 7.26% |
| Different populated/empty cake bins | 20 of 4,320 |

Coverage differences are checked separately and are confined to one bin of a
coverage boundary. The tests bound both their number and whole-array error;
they are not silently dropped from the comparison. The counting-mode adapter
checks matching coverage and absolute intensity scaling against pyFAI to
`rtol=2e-6`. These fixture results do not establish universal detector accuracy
or bitwise equivalence between full-polygon splitting implementations. The raw
six-case report is in `desktop/artifacts/detector-combination/numerical.json`.
The upstream report documents the algorithm differences in greater detail.

`npm run test:combination` (add `-- --webkit` for WebKit or
`-- --dioptrin` for the new native path) uses headless Playwright
and real Python models. It checks independent contrast, scale, factors,
combination switches, saving, and visible image/control bounds at 1000 × 668
with both interface text sizes. Screenshots and reports are written under ignored
`desktop/artifacts/detector-combination/`. No visible browser/native window is
needed. Tauri's native file-dialog route has a Rust unit test.

## Recorded checks (2026-11-08)

- Full desktop suite with the existing optional Dioptrin 0.9.0 wheel: **333 passed**.
- Final combination suite with the local shared-grid wheel: **21 passed**.
- Backend/session/binary regression subset with that wheel: **31 passed**.
- Frontend unit checks: **61 passed**; TypeScript and Vite build passed.
- Rust host tests: **18 passed**, including combined-save dialog routing.
- Headless Chromium and WebKit workflows passed, including the actual Dioptrin
  backend, configuration contrast restoration, combined Q-cake clicks and guides,
  saving, and both text sizes at 1000 × 668.

The implementation stays on `codex/detector-combination`; the primary checkout
and existing user previews were not changed or restarted. The worktree's parent
commit `a814caab` captures the source already present in the primary checkout
when this work began. It is a baseline snapshot, not part of the combination
change. The following feature commit can be reviewed or applied separately.
