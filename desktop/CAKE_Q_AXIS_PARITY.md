# Cake 2θ/Q display — November 10, 2026

## Workflow and Qt reference

The existing pattern **2θ** and **Q** buttons also select the cake radial axis.
Qt's `ImageController.create_signals`, `update_cake_x_axis`,
`set_cake_axis_to_2th` and `set_cake_axis_to_q` provide the reference. Qt does not
wire its d button to a cake d axis. This implementation retains the last 2θ/Q
cake selection when d is selected (2θ initially), without adding a d cake axis.
Calibration validation uses the same source-aware renderer and session wavelength.

Qt changes an axis range without changing the image grid. Here rounded display
ticks are additionally positioned through the inverse nonlinear conversion,
so a tick's physical position agrees with a click at that position even at high
angles. This is a deliberate accuracy improvement over linearly interpolating
converted range endpoints. The physical conversion is
`Q = 4π sin(2θ / 2) / λ`, with λ converted from session metres to angstroms.

## Coordinate and processing contract

- `Cake.unit` and `Cake.radialRange` always describe the scientific source grid.
  The range contains first/last **bin centers**. A center at column `i` is at
  image coordinate `i + 0.5`; its source coordinate interpolates using `width - 1`.
  The previous edge-based interpolation introduced a half-bin error. Azimuth
  conventions are unchanged by this feature.
- `src/cakeRadialAxis.ts` owns source-pixel/source-coordinate conversion, display
  bounds, ticks and inverse positioning. `useCakeRadialAxis.ts` supplies the
  two-unit Qt display selection. They never allocate, resample or mutate pixels.
  RasterView receives one optional adapter; detector rendering is unchanged.
- Individual cakes remain native angular integrations. Unit-only settings and
  their native Undo/Redo retain the exact cake raster and f64 value ownership;
  only the independent 1D integration changes grids. The frontend retains the
  cake's pixel viewport across the unit buttons. Shared zoom/pan gestures,
  inspection, phase/calibrant guides and independent intensity controls remain.
- Combined cakes may have either an angular or a Q source grid. Native reuse
  checks geometry, masks, source f64 ownership, binning, polarization and cake
  sector, rather than assuming that the pattern's selected unit describes the
  existing cake. A display-unit change never rebins a valid existing cake.
  Actual scientific input changes still use the existing shared-grid algorithm.
- Native projects record `combination.cake_source_unit` in their existing
  `react_desktop` metadata. Reopen (including hidden/lazy cake requests) restores
  that source grid before calculating the pattern in its selected unit. There
  is no second scientific session, processor, integration algorithm or Python
  dependency. Older projects without this optional metadata use the prior
  native initial-grid selection.
- Readouts, click requests and Map's retained inspection use explicit source
  coordinates and session wavelength. Neither a Q source nor a Q display is
  converted twice. The linked inspection owner still stores physical 2θ.
- Missing/nonfinite/nonpositive wavelength leaves the source unit displayed,
  with an axis notice and explanatory tooltip. A Q range outside the physical
  angular branch at a changed wavelength also stays in its source unit. Panning
  outside the physical conversion domain does not invent inverse positions.
- PNG exports use the same displayed ticks and current viewport. Qt-style
  TXT/CSV and TIFF exports continue to contain the scientific source grid/data;
  changing labels does not rewrite numerical exports. Integration Settings
  explains this distinction. No data-export format was redesigned.

## Validation

`npm test` includes `scripts/cake_radial_axis.test.mjs`: bin centers, fixed
physical positions, nonlinear inverse tick locations, zoom bounds, 0.2/0.4/1.54 Å,
Q source cakes, missing/changed wavelength, unchanged buffers and Qt's d behavior.

`cargo test --locked --manifest-path backend/Cargo.toml --test cake_axis` checks
immutable raster-buffer reuse, native cake-integration counters, unchanged CSV,
Undo/Redo, scientific-setting invalidation, angular/Q combined sources, linked
inspection, eager/lazy project reopen/resave and changed frames. Consolidation
checks now assert retained source units rather than assuming rebinning on every
unit button. The full native suite passes (204 passed, two pre-existing ignored checks), as
do all 110 frontend tests, native Clippy with warnings denied, and the frontend
build.

`npm run test:cake-q-axis` runs real Rust processing through headless Chromium
and WebKit. It checks actual canvas-label positions, Q/d/2θ transitions, the
unchanged zoom interval and cake buffer, source-coordinate clicks, independent
detector/cake intensity, combined Q grids displayed in both units, a wavelength
change, project reopen, source-grid CSV and a 2048-pixel PNG. Screenshots cover
1000 × 668 at Standard and Larger text. Receipts are under ignored
`artifacts/cake-q-axis/`. Existing real-image headless native calibration checks
also pass. No native/headed windows were opened and no user preview was stopped.

## Consolidated integration — November 10, 2026

Combined with azimuthal-profile commit `b82067d4` in the consolidated desktop.
Both hooks and their requested-product ownership are retained. `Cake.unit` and
`Cake.radialRange` remain scientific source metadata; profile windows never use
converted display ticks. Shared App imports, PlotStatus, types and command
routing preserve both features. Shallow cakes abbreviate the azimuth title to
χ (°) so it fits beside the optional profile at compact window heights.

Joint Rust checks assert unchanged float64 profile samples across 2θ/Q/d
selection and project reopen for angular and Q combined grids. The extended
profile browser check asserts unchanged samples, cake buffers and both plot
viewports through the same transitions, alongside the original width, shift,
export, lazy-demand, configuration and Standard/Larger layout checks.

Merged validation: 209 native tests passed (two existing ignored checks),
110 frontend tests and 27 Tauri host tests passed. Native Clippy, frontend build
and headless Chromium/WebKit cake-axis, profile, calibration and Integration
workflows passed. Host-wide rustfmt checking reports existing formatting
in unrelated host modules; those files were preserved. No visible windows
were opened, no user processing was stopped and no release was published.
