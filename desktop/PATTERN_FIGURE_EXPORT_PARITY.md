# Integration pattern figure export — November 10, 2026

The existing **Save pattern** action offers XY, XYE, CHI, DAT, FXYE, PNG and SVG
through the native Save chooser. There is no additional Export toolbar action.
The data formats and automatic data-file creation retain their existing paths.

The reference is `dioptas/controller/integration/PatternController.py`:
`save_pattern` offers these seven formats and routes figures to
`widgets/plot_widgets/PatternWidget.py`'s `save_png` / `save_svg`. Qt uses
pyqtgraph's ImageExporter and SVGExporter; its SVG is vector content.

## Rendering and ownership

`PatternView` exposes the small display-only `PlotFigureExport.capture` hook.
It can also be implemented by a future spottiness or azimuthal-profile plot;
no additional plot or scientific implementation is introduced here.

The native host chooses the destination first. Numerical saves proceed directly
to the existing Rust command. Cancel returns without rendering or publication.
For a PNG/SVG choice, the host returns `figureExportPath`; `patternFigureSave.ts`
asks the mounted renderer for the figure and submits the explicit destination
through the same native command. Ordinary numerical exports do not allocate
or transfer PNG/SVG buffers. Capture failures use the existing error report UI.
The Rust worker validates the PNG or parses the SVG, then uses the existing
single-file atomic replacement. Invalid/missing capture or a destination error
cannot replace the preceding file. Explicit paths bypass the chooser.

PNG composites the actual displayed background, WebGL/Canvas curves and Canvas
annotations at device-pixel resolution, then paints the currently positioned DOM
legends as text. The existing transparent layers remain transparent until the
final workspace-background composition. Because WebGL discards its drawing
buffer after presentation, capture repaints the identical retained GPU frame
immediately before copying it. Context loss retains the Canvas export path.

SVG records an on-demand pass through the same plot drawing code. Tick helpers,
view ranges, transforms, visible measured/overlay curves, order/emphasis/colors,
phase scaling and positions, axes, labels, regions and linked guides retain their
renderer ownership. The interactive hot path performs no SVG recording. SVG
contains paths, rectangles, clipping and text; there is no raster image or
foreignObject. With curve antialiasing off it uses crisp vector paths instead of
millions of pixel rectangles. Legends retain dragged positions, clipping,
scrolling, ellipsis/wrapping, colors and workspace text shadows. Controls, tool
buttons and focus outlines are excluded from the figure.

Exports never modify scientific arrays or radial/phase coordinates and do not
reintegrate. The plot's persistent view/zoom preferences remain owned by the
existing navigation helpers. Pattern saving uses the same displayed renderer
for individual and combined patterns.

Intentional differences from Qt: SVG retains the displayed charcoal background
and current colors, rather than Qt's temporary color inversion; it retains the
Unicode 2θ label rather than Qt's SVG-specific `2th_deg` substitution. SVG text
uses font families, so independent viewers can substitute unavailable fonts.
Vector stroke rasterization can differ slightly from GPU antialiasing. There is
no publication-layout designer or custom export size/DPI editor.

## Verification

- `npm run build` passes; `npm test` passes all 105 existing unit/architecture checks.
- `npm run test:pattern-figure-export` runs headless Chromium and WebKit at 2×
  device scale. Eighteen zoomed cases cover 2θ/Q/descending d, linear/log/√,
  selected overlays, gaps, phase positions/strengths, labels and moved legends.
  PNG pixels outside the DOM legend boxes match the displayed renderer layers
  exactly (maximum channel error 0); dimensions match physical canvas size.
  Scientific source arrays remain identical after capture.
- Each SVG is parsed, checked for paths/text and absence of raster content,
  loaded as an independent SVG image in both browsers, and rendered with resvg
  (a development-only test dependency). The browser PNG/SVG mean channel
  difference is below 1/255 across all cases. Independent render dimensions and
  curve/reference colors are checked. Canvas fallback, hidden measured curves,
  antialias-off and larger plot text are also exercised.
- The real Rust processor is driven through the actual compact Integration Save
  button in both browsers. All five numerical formats match direct native exports
  (apart from filename-bearing headers); PNG/SVG files are independently read.
  The chooser alone is replaced by a test adapter. Cancellation, failed writes,
  retry, unchanged figure-save scientific state and 1000 × 668 Standard/Larger
  controls are checked.
- Focused Rust publication test, 15 native-session tests, 31 scientific functional
  flows, and all 29 Tauri host tests pass. These include all five data formats,
  case-insensitive figure extensions, explicit paths, native format routing,
  render-request capability, invalid SVG/PNG and atomic failure preservation.
- Existing `rendering_smoke.mjs` passes in both browsers, including shared gestures,
  transparent rendering, reused storage, context recovery and Canvas fallback.
- Backend formatting and Clippy with warnings denied pass.

Receipts and visually inspected files are in `artifacts/pattern-figure-export/`;
existing renderer receipts are `artifacts/rendering-{chromium,webkit}.json`.
No visible/native windows were opened. Actual OS Save-panel interaction and
Windows/Linux behavior are not newly qualified by these headless checks.

Implementation is committed on the isolated `codex/pattern-figure-export` branch.
The primary checkout was inspected read-only and remained clean at `b31e7650`
before the feature commit. Primary integration is left to the coordinating chat;
this ledger does not claim that the consolidated desktop already contains it.
