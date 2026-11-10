# Native azimuthal cake profile — 2026-11-10

Integration's **Profile** toggle opens intensity versus azimuth below the
image/cake. Select a radial position by clicking the detector, cake or pattern.
**Width (bins)** commits on Enter/blur (1–1,000,000). The save icon writes XY,
DAT, TXT or CSV through the existing Tauri chooser and Rust atomic file writer.
Invalid width drafts cannot submit a save. The profile can remain visible with
the detector image; it explicitly requests the required hidden cake.

## Scientific ownership and Qt reference

`backend/src/cake_profile.rs` extracts from `Session::displayed_cake_values()`:
the native float64 individual or combined cake, after the existing mask,
background, flat/transfer/factor and correction processing. No scientific
integration, image processing, or uncertainty estimator was added. The float32
raster is never used to calculate or export the profile.

The port references `CalibrationModel.cake_integral`,
`ImageController.plot_cake_integral/_update_cake_integral/save_cake_integral`,
`CakeImgWidget` and the Qt cake controls. Convert the selected physical 2θ to
the cake's declared scientific radial unit using the session wavelength. The
metadata endpoints are bin centers. For fractional index p and width w, average
the overlaps of columns with `[p + 0.5 - w/2, p + 0.5 + w/2]`, dividing by w.
This reproduces Qt's fractional y1/slice/y3 expression for valid interior
windows. A width of one linearly interpolates neighboring columns.

The azimuth roll uses the same integer row shift as `useShiftedCake` and shifts
the degree coordinates by that many bin steps. The existing desktop slider is
in degrees and rounds to cake rows (JavaScript ties toward positive infinity);
Qt's slider is directly in rows. Narrow sectors are not rolled, matching the
existing desktop cake control. No source cake, image, scientific settings,
configuration identity/selection or integration history is changed by extraction.
A missing cake is produced through `ensure_cake`, with per-command display demand
restored afterward. Closing Profile with Image displayed restores ordinary lazy
cake demand. Combined cakes' explicit units are respected; displayed axis
relabeling is separate from these source coordinates.

## Deliberate differences and boundaries

- Qt's helper excludes its first bin center and can wrap negative radial
  indices or raise IndexError when a wide window extends beyond an edge. The
  native path accepts both endpoint centers, clips missing columns to zero,
  keeps the requested-width divisor and marks **Edge clipped**. Positions outside
  the center range return an empty profile and cannot be saved.
- Qt puts intensity horizontally beside the cake and links its vertical pixel
  coordinate to cake zoom. This compact desktop panel puts azimuth on x and
  intensity on y, reusing `PatternView`, shared gestures, zoom controls and
  viewport memory. Its zoom is independent of the cake; radial selection and
  linked azimuth markers remain shared. Radial clicks/width updates retain the
  profile viewport; a new configuration, wavelength or shifted azimuth extent
  resets its view context. No separate drawing/navigation implementation exists.
- Qt's plot changes nonpositive intensities to NaN and its save action uses the
  plotted intensity/pixel arrays. Native plots and saves retain zero and signed
  numerical intensities. Files contain actual azimuth bin centers in degrees,
  followed by native intensity in a.u., with metadata comments and no invented
  error column. Nonfinite data fail export before replacing an existing file.
- Width, visibility and zoom are session view state; no new project fields or
  scientific configuration settings are introduced. Existing project-owned
  arrays/corrections/configurations are reused after reload. The explicit
  compatibility Python processor does not implement these new native commands.

## Validation

From `desktop/`:

```sh
npm run backend:prepare -- --debug
cargo test --locked --manifest-path backend/Cargo.toml --all-features --lib
cargo test --locked --manifest-path backend/Cargo.toml --all-features --test requested_products
cargo clippy --locked --manifest-path backend/Cargo.toml --all-features -- -D warnings
cargo test --locked --manifest-path src-tauri/Cargo.toml --bin dioptas-desktop
npm run build
npm test
npm run test:cake-profile
```

- Native library: 68 passed, 2 existing external-image checks ignored; includes
  five profile tests. Requested-products regression: 5 passed. Native Clippy
  passes with warnings denied. Tauri host: 27 passed, including chooser filters.
- Numerical tests use a literal independent Qt y1/slice/y3 reference expression
  on actual native float64 cakes, plus fixed synthetic expectations. They cover
  center/fractional/first/last/outside selections; widths 1/2/3/9/1,000,000;
  positive/negative shifts and half ties; a one-column cake and narrow sectors;
  masked/background/absorption-corrected individual and combined cakes; Q/2θ/d
  pattern settings, two wavelengths and fresh project owners. Source array Arc
  identities, settings, revision, pattern and selected configuration are checked.
  Tolerance is 3e-10 relative plus 1e-12 of the row maximum for coordinate-conversion
  roundoff near empty endpoint bins. This is a source-expression comparison,
  not a separately run Qt/pyFAI integration oracle or universal detector audit.
- XY/CSV export samples parse back exactly to the profile's float64 values.
  Invalid widths/formats, out-of-range selections and cancellation preserve an
  existing output; errors have no column and no temporary-file leftovers.
- Frontend build and 105 unit/architecture tests pass. Headless Chromium and
  WebKit exercise linked detector/pattern/cake/profile clicks, width edits,
  profile zoom/F reset and zoom retention, native degree shifts, shared footer,
  save/cancel, combined Q profiles and configuration selection, and restored
  lazy demand. Layouts at 1440×900 and 1000×668 with Standard/Larger text check
  both profile controls and the wrapped image tools against their container.
  Screenshots and receipts: `artifacts/cake-profile/` (ignored). No visible windows
  were opened. Actual OS chooser interaction and Windows/Linux remain untested.

The implementation is isolated on `codex/cake-azimuthal-profile`; primary
integration is coordinated separately. The cake-Q-axis feature's edits were
inspected read-only: this implementation reads source `cake.unit/radialRange`
and never substitutes display labels for scientific radial coordinates.
