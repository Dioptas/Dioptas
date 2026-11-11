# Native azimuthal cake profile — 2026-11-10

Integration's **Profile** toggle opens the azimuthal profile to the left of the
cake, with intensity horizontally and the shared cake azimuth axis vertically.
Turning it on from Image switches to Cake. The profile is hidden in Image mode
and during correction-map previews. Select a radial position by clicking the
detector, cake or pattern.
**Width (bins)** commits on Enter/blur (1–1,000,000). The save icon writes XY,
DAT, TXT or CSV through the existing Tauri chooser and Rust atomic file writer.
Invalid width drafts cannot submit a save. The profile is shown only with the
cake; hiding the cake stops profile requests and restores ordinary lazy cake
demand.

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
The UI requests unshifted native samples and wraps those existing rows locally
when the slider moves; slider movement performs no profile request and never
clears the curve. Saving still asks Rust for the selected shift and writes its
native float64 samples. Initial loading/empty messages are drawn inside the
clipped plot area, leaving the shared azimuth axis unobscured.
A missing cake is produced through `ensure_cake`, with per-command display demand
restored afterward. Closing Profile with Image displayed restores ordinary lazy
cake demand. Combined cakes' explicit units are respected; displayed axis
relabeling is separate from these source coordinates.

## Deliberate differences and boundaries

- Qt's helper excludes its first bin center and can wrap negative radial
  indices or raise IndexError when a wide window extends beyond an edge. The
  native path accepts both endpoint centers, clips missing columns to zero,
  keeps the requested-width divisor and explains clipping in the toolbar/Save
  tooltip. Positions outside
  the center range return an empty profile and cannot be saved.
- The layout follows Qt: intensity is horizontal to the left of the cake and
  azimuth is shared vertically. `CakeProfileView` draws each native profile
  sample at its cake-row center (`i + 0.5`), using the same plot insets and a
  common source-pixel y viewport. The profile carries the single visible azimuth axis at the far left of both plots.
  Gestures, tick generation and typography reuse the shared plot primitives.
  Cake navigation updates the profile; profile navigation updates cake azimuth
  without changing the radial interval. F in the profile restores full azimuth
  and automatic intensity limits; F in the cake fits the cake. Width/radial
  changes preserve manual intensity zoom. Both main and detached cake views use
  the same layout and source-row convention, including azimuth shifts.
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

## Consolidated integration — November 10, 2026

Integrated with source-aware Q-axis commit `6ee8faf0`. Both features retain the
same scientific bin-center convention and explicit source units. Native tests
and extended Chromium/WebKit checks prove that 2θ/Q/d display transitions leave
profile samples, cake buffers, physical selection and both plot viewports
unchanged, for angular and Q-sourced cakes. Saved projects restore the scientific
source grid before profile extraction. The profile's original controls, export,
shift and lazy-demand checks remain in the same workflow.

The merged tree passes 209 native tests (two existing ignored checks), all 110
frontend tests and 27 Tauri host tests, plus native Clippy and frontend build.
Both headless browsers pass cake axis/profile, real-image calibration and
Integration checks. Host-wide rustfmt checking still finds pre-existing
formatting in unrelated host files; no broad reformatting was included.
See [cake-axis integration details](CAKE_Q_AXIS_PARITY.md).

## Shared cake azimuth layout — November 10, 2026

The profile now occupies the left column of the cake workspace rather than a
separate panel below the image. It is mounted only in Cake view, including in the
detached image window. Image mode and correction previews do not render it or
request profile products. The native Rust extraction, signed intensities, width
edge handling and degree/intensity export are unchanged.

The headless profile workflow checks exact top/bottom alignment and shared y
limits at 1440×900 and 1000×668, Standard and Larger text, through profile/cake
zoom, profile pan/F reset, widths, radial clicks, shifts, units and configuration
changes. It also checks that profile gestures retain the cake radial interval,
and image mode suppresses profile reads and hidden-cake demand. Detached-source
checks exercise both directions of linked navigation and profile visibility
across Image/Cake and correction preview/Back. No visible windows are used.

Validation for this layout update: frontend build and 113 frontend tests pass;
five native profile tests and two source-axis tests pass. Chromium and WebKit
pass the updated profile workflow (both histogram orientations), cake-Q-axis,
correction-preview and detached-source workflows. The detached checks include
close/reopen and Back from a correction preview, keeping the selected source,
scientific results and detector orientation intact.


## Width divider and outer-axis gestures — November 11, 2026

A compact divider between the profile and cake adjusts the profile width. It
reuses `LayoutDivider`: drag, Left/Right (Shift for larger steps), Home or
double-click for the default, and End for the maximum. The width is remembered
as a window layout preference, with bounds that keep the neighboring cake
usable. Resizing the window temporarily clamps the displayed width without
erasing the preferred value. This works in the main and detached cake views.

The shared azimuth labels and title now sit entirely on the far left of the
profile. A left-button zoom selection starting on that axis can extend into
the profile or across the divider into the cake. The plot under the released
pointer determines the intensity or radial interval; azimuth stays linked.
Crossing back to the profile before release selects its interval. The divider
itself retains its separate width-resize gesture. The implementation forwards
axis-started gestures to the existing plot navigation primitive within each
window; no scientific processing or arrays are changed.

Updated Chromium/WebKit profile and detached-source checks cover pointer and
keyboard resizing, persisted width and reset, axis drags into either plot and
back across the divider, shared y limits, unchanged scientific viewports during
resize, source pixels and profile samples. Cake-Q-axis and native calibration
browser regressions, the frontend build and 113 frontend tests also pass.


## Stable width controls — November 11, 2026

The bin-width input has a fixed 48 × 24 px box with 1 px vertical and 2 px
horizontal padding. Its field and Save button do not flex in response to
selection status. The inline three-dot edge-clipping marker has been removed;
the existing toolbar/Save tooltip explains the missing-bin contribution when
applicable. Numerical extraction and export metadata still report clipping.
The headless profile check selects center and both radial-edge positions with
a narrow profile panel and asserts identical control positions and dimensions.
The input overrides the general form field's top margin so it shares a vertical
center with the Bins label and Save icon. Chromium and WebKit check this alignment
at both viewport sizes and with larger text enabled.

The headless profile regression also checks positive/negative slider movements,
rounding ties, zero and both endpoints against independent native shifted
extractions. It asserts unchanged native request counts, a continuously present
profile, shared cake/profile axes and the native save path.
