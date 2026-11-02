# Desktop interface work

This React/Tauri preview reuses local Dioptas scientific models. Read README.md
and CALIBRATION_PARITY.md before changing its command or plot boundaries.

## User requirements

- Use current Qt Dioptas views as the reference. Preserve workflow, terminology,
  control grouping, layout and interactions; improve awkward spacing,
  readability and visual treatment without redesigning the product.
- Mode navigation stays left; task controls stay right. Avoid large redundant
  view headlines. Controls use readable 14–15 px text, with the existing larger
  text option. Neutral charcoal backgrounds, orange accents, green elongated
  crystal identity. Do not turn backgrounds green.
- Images have no extra title/dimension header, Fit button or Display mask
  toggle, and no tool/zoom selection strip above them. The shared Ring / Auto /
  Pick peaks strip stays above the calibration tabs; its switch controls picking
  in every calibration tab. Images use rectangle zoom, while the pattern's optional
  horizontal/rectangle choice lives in Settings. Mask drawing controls stay
  in the right task panel. F and right double click restore the image view.
- Settings is anchored at the bottom of the left sidebar. Coordinates,
  intensities, plot hints, selection feedback and processing/save/error messages
  use one app footer beside the full-height left sidebar: active plot readout
  left, messages right. No per-plot
  readout/footer rows or floating pattern readout. Detector readouts omit the
  source label and reserve fixed-width x/y fields so digits do not move the
  following coordinate. Keep updates near 10 Hz.
- Every image has independent intensity limits, linear/log (linear default),
  Auto modes and visual colour-map selector. Use existing ImageIntensity:
  default right in single-image views, top in multi-image views.
- Preserve original detector resolution, orientation and square pixels on
  resize. No detector axes/ticks/card. Display rows count downward from top;
  scientific arrays/control points retain the existing Dioptas convention.
- Shared gestures: left rectangle zoom, right drag pan, right click 2× out,
  right double-click full fit; wheel zoom must not scroll the workspace. Pattern
  defaults to horizontal zoom with optional rectangle. Moving readout ~10 Hz.
- Keep calibration working. Do not restore the removed top-level Export pattern
  button. Normal Qt-style file/save workflows can live in appropriate
  integration controls.
- No scientific HTTP server, mandatory Dioptrin, or Qt application in the new
  host. Processing is currently Python over Tauri-owned stdio, not Rust/WASM.

## Parallel view implementation

Mask, Integration and Map are developed in separate worktrees/branches from a
shared checkpoint. Work only in the checkout assigned to your chat. Do not edit,
merge into or run cleanup against the primary preview or another view checkout.
Keep mode-specific components, styling, command adapters and tests in separate
files. Keep necessary App.tsx/types.ts/session.py routing changes small so the
views can be combined. Do not perform unrelated shared-shell refactors.

The primary live preview owns port 1420. Test your own bundled native window or
use a temporary Tauri config with a distinct Vite port; do not reuse or kill the
primary server/window. Other user windows may contain work.

Use standard CPython 3.13: `uv sync --python 3.13 --extra test` in your checkout,
and `npm ci` in desktop. Never share an editable .venv or mutate another
checkout's dependencies. Build with `npm run build`; exercise real models and
meaningful Qt parity/interaction checks, then existing calibration/browser
regressions as appropriate. Native smoke: `npm run tauri:smoke` (uses embedded
assets, no Vite port). Record remaining gaps honestly; do not add dead buttons
or fabricated scientific results.
