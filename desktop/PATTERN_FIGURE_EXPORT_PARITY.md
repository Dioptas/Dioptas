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
  labels occupy a separate band above the sticks.
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
