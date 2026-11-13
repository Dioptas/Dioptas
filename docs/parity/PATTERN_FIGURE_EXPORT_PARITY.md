# Integration pattern figure editor — November 10, 2026

**Save pattern** retains numerical XY/XYE/CHI/DAT/FXYE export. An icon-only
**Export pattern figure** button sits immediately to its right, as requested.
The image icon opens the editor directly, without first choosing a destination.
The native chooser opens when saving the figure; later saves in the same editor
can reuse the chosen path. **Save as…** always opens the chooser. Cancellation
keeps the editor and its settings available.

The earlier direct-capture workflow in `908dc3f6` has been superseded by this
editor. Its display capture hook and regression checks remain available.
Read-only references were Qt's `PatternController.save_pattern`,
`PatternWidget.save_png/save_svg`, and MossA's `FigureExportDialog.tsx`,
`figure.ts`, `figure-layout.ts`, and `figure-settings.ts`.

## Editor

- A fitted live paper preview and a magnified, scrollable preview use the same
  standalone SVG that is saved or rasterized to PNG.
- Single-column, double-column and widescreen presets, custom dimensions in mm,
  font family/size in pt, optional title, and white/transparent/dark backgrounds.
- Current/full/custom horizontal limits in the plot's existing units, independent
  linear/log/√ intensity display and current/automatic/custom intensity limits.
  Editable axis labels, grid, boxed axes, tick direction and intensity tick labels.
- Per-curve labels, colors, visibility, line width/style, points, and drawing order.
  These controls operate on the measured/overlay curves supplied by the plot.
- Legend placement inside corners, an automatic corner heuristic, above/below,
  right, or hidden. Outside horizontal legends use wrapped columns.
- Phase references can remain inside the pattern, occupy separate aligned rows,
  or be hidden. Each phase has editable labels/colors/visibility. Separate rows
  retain exact x coordinates and relative reflection strengths within each phase;
  equal-height ticks identify each reflection, with optional intensity-weighted
  thickness. Labels can sit beside each row or in an independent phase legend.
- SVG remains editable paths and text, with no raster image or foreignObject.
  PNG supports 150/300/600 dpi, exact pixel dimensions, alpha transparency and
  native pHYs resolution metadata for document insertion at the chosen size.

Valid appearance settings are remembered locally. Named-plot labels/colors and
custom ranges are restored for the same source; other sources inherit reusable
layout settings and refresh their labels/ranges. Invalid optional preferences
fall back to defaults. Settings are not yet embedded in `.dio` projects.
Invalid ranges, insufficient layout space, unavailable positive log intensities
or oversized PNG output disable publication with an explanation, rather than
saving a stale preview. Labels accept Unicode; mathematical text outlining,
PDF/EPS and multi-panel page composition are outside this implementation.

## Ownership and scientific semantics

`PatternView` supplies a display snapshot through `PlotFigureExport.source`.
Metadata snapshots follow label/view changes without adding redraw dependencies
to the existing WebGL/Canvas hot path. The editor retains the source captured at
opening, so subsequent source replacement cannot silently change its figure.
`patternFigure.ts` handles paper layout and uses the existing tick generation,
visible-sample lookup, phase scaling and SVG Canvas recording infrastructure.
The editor reads the original displayed sample arrays, including descending d,
nonfinite gaps and already-applied background/overlay transformations. It does
not integrate, resample, change units, normalize or modify scientific arrays.
The square-root display retains the working plot's clamp of negative samples.
Main plot ranges, colors, phase settings and view preferences remain unchanged.

Publication stays on the existing Tauri → Rust stdio command. The editor sends
rendered SVG or PNG bytes with an explicit format. Native dialogs use that
format's filter and suggested name. A missing suffix adopts the figure format;
a mismatched suffix is rejected before replacing any file. Rust parses SVG or
validates PNG, writes PNG resolution metadata when requested, and atomically
publishes the file. Existing raw-image/Batch PNG paths retain their bytes and
metadata behavior. There is no additional processing session or Python fallback.

The original `PlotFigureExport.capture` remains a small extensible display hook
for future profile/spottiness figure work. Its quick PNG composes the actual
WebGL/Canvas layers at device resolution; the vector capture records the same
plot drawing code. This is separate from the paper editor's optional styling.

## Verification

- Production frontend build and all existing frontend unit/architecture checks.
- `npm run test:pattern-figure-export` runs three headless scripts in Chromium
  and WebKit: original display-capture regression, real native Save/image-button
  workflows, and the figure editor/rendering checks.
- Eighteen quick-capture cases and eighteen paper-rendering cases cover zoomed
  2θ/Q/descending d, linear/log/√, overlays, gaps and phase positions. Independent
  resvg rendering checks standalone SVG content. Quick PNG pixels outside DOM
  legends match the active renderer exactly; the paper preview and saved SVG
  have identical markup. Source arrays remain unchanged.
- Real native data exports match all five direct writers. Image-icon adjacency,
  direct editor opening, both UI text sizes at 1000 × 668, all editor tabs,
  complete preview labels, edited styles/order/ranges/phase labels, persistence,
  malformed preferences, source changes, negative √ samples, cancellation,
  failed writes and retry are checked. Native PNG files are read back to verify
  physical pixel dimensions, pHYs density and transparent alpha.
- Focused Rust tests cover atomic publication, invalid SVG/PNG/DPI, pixel
  preservation, explicit/case-insensitive paths, suffix mismatch and dotless
  figure destinations. Host tests cover separate numerical/figure filters.
- Backend formatting and Clippy with warnings denied pass.

Receipts and inspected figures/screenshots are in
`artifacts/pattern-figure-export/` and `artifacts/pattern-figure-editor/`.
No visible/native windows were opened. Actual OS save-panel interaction and
Windows/Linux behavior are not newly qualified by these headless checks.

## Reconciliation with the current desktop

The isolated feature branch incorporates primary commit `feee6f2c`, including
Spottiness, cake Q/profile, correction previews and the detached detector window.
The image-button/editor changes remain confined to the pattern export path;
`SpottinessPattern` forwards the export hook only to the measured pattern.
Generic plot-unit support and the diagnostic's fixed axis gutter are retained.
Initial reconciliation took place in the isolated worktree; primary integration is recorded below.

After reconciliation, the frontend build and 112 unit/architecture checks pass,
as do the complete Rust processor suite (external-image opt-in checks remain
ignored), 31 host tests, all three figure-export scripts, Spottiness, cake-profile
and correction-preview headless checks in both browsers, and the shared Chromium
rendering regression. The export check explicitly asserts that the image icon is
immediately right of numerical Save and opens the editor without a chooser.
The three Rust figure-publication tests cover the new resolution and suffix rules.


## Primary integration for testing

At the user's request, `codex/rust-desktop` was fast-forwarded from `feee6f2c`
to the reconciled feature commit `9827debd`. The primary checkout was clean
before integration. Its frontend build and 112 unit checks pass. All three
headless figure scripts pass from primary, including real native data/figure
writes in Chromium and WebKit; the three Rust figure-publication tests pass.
The native Save/editor checks were run after rebuilding the primary processor.

The primary debug `Dioptas Desktop.app` was rebuilt with the matching processor
and embedded UI, then locally ad-hoc signed and verified. The artifact is
`src-tauri/target/debug/bundle/macos/Dioptas Desktop.app`.
No application windows were opened or user processes stopped. Open the rebuilt
app and use the image icon immediately right of Save above the Integration
pattern. This is a local testing build, not a published or notarized release.


## Phase-row and single-column revision

Phase references never join the curve legend. The Phases tab provides its own
label/legend placement: names beside reference rows, a separate titled phase
legend, or hidden labels. A separate legend uses vertical reference-tick symbols;
the curve legend retains the measured-curve line/point symbols. Automatic legends
move below the plot if no empty corner exists, rather than covering measured
peaks. Occupancy uses clipped line segments, including sparse curves.

The default row display has one compact row per phase below all measured curves.
All positive finite reflections have equal tick height. Thickness can be uniform
or gently weighted by relative intensity within the visible phase. Row labels
occupy a reserved right column, leaving the reference positions unobscured.
Rows retain the exact shared 2θ/Q/d coordinates; no scientific arrays or phase
positions are changed.

Size presets now set typography as well as dimensions: single column 90 × 80 mm
uses 8 pt, double column uses 10 pt, and widescreen uses 14 pt. The old saved
single-column preset's inherited 10 pt default is migrated to 8 pt, while custom
font choices remain intact. The preview offers an explicit actual-size mode.
SVG text uses explicit font-size/family/weight/style attributes so independent
viewers do not substitute their default size for CSS font shorthand.

The editor checks now use three phases with different strengths in 2θ/Q/d and
linear/log/√ cases. They verify stacked baselines, equal heights, uniform and
intensity-dependent widths, independent legend contents, unchanged source data,
legacy preferences, and 8 pt at actual-size scaling. Independent resvg PNG/SVG
artifacts include both row labels and separate legends at single-column size.


## Reusable styles and phase-row controls — November 11, 2026

Layout now includes a local, named style library. Save the current appearance,
select and apply a saved style, or expand the management controls to update,
rename or delete one. Styles transfer dimensions, typography, backgrounds,
legend/axis appearance, phase-row geometry, curve colors/widths/line styles and
phase colors. Palettes follow the current drawing order and repeat when the
new dataset has more entries. Labels, titles, identities, visibility, order,
axis scales and numerical limits stay with the current figure. File format
and resolution are independent. Styles are saved on this computer under the
app's local preferences; they are not embedded in projects or export files.
Corrupt entries are ignored individually, and failed local writes are reported
without replacing the in-memory library.

Phases now have Up/Down controls, which reorder both reference rows and the
separate phase legend. Minimum row spacing (1–20 mm), tick height (0.5–10 mm)
and horizontal row guides are adjustable. Row spacing expands to fit tall
ticks and wrapped labels. Every reference retains its original horizontal
coordinate and intensity weighting. These edits affect only the exported
figure; application phase order and scientific data remain unchanged. Existing
appearance preferences receive defaults for the new row controls.

The editor headless check exercises style creation, duplicate-name handling,
application, update/rename, deletion, reopening, unavailable storage, malformed
entries and palettes applied to another dataset with more/fewer/no phases. It
checks preservation of labels, custom ranges, scale, hidden entries, current
order and source arrays. Phase checks verify reordering, unchanged reference
positions, physical row/tick dimensions, guide visibility, legacy defaults and
space for tall ticks and wrapped names. Chromium/WebKit screenshots cover both
text sizes, including the compact responsive layout.
