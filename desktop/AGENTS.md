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
  in every calibration tab. All plots default to rectangle zoom; cake and pattern
  have separate icon-only rectangle/X-range selectors in the empty corner below
  the y-axis and left of the x-axis. Keep them small and rectangular, with a
  little left inset and transparent backgrounds; the selected icon is orange,
  other icons are neutral, and the neutral button background appears only on hover.
  The pattern choice is also available in Settings. Mask drawing controls stay
  in the right task panel. F and right double click restore the image view.
- Settings is anchored at the bottom of the left sidebar. Coordinates,
  intensities, plot hints, selection feedback and processing/save/error messages
  use one app footer beside the full-height left sidebar: active plot readout
  left, messages right. No per-plot
  readout/footer rows or floating pattern readout. Keep the footer to one line,
  without Image/Cake/Pattern source labels. Use fixed-width coordinate/intensity
  fields and coordinate precision that follows the visible axis range and plot
  size, increasing when zoomed. Integration and Map share a compact Click
  position beside the live readout and linked green click markers across modes.
  Pattern readouts show the mouse y coordinate separately from curve intensity. Always show 2θ, Q and d together in radial
  hover and clicked readings, using the session wavelength; include these on
  calibrated detector hover too. Click readings use green text. Keep updates near 10 Hz.
- Every image has independent intensity limits, linear/log (linear default),
  Auto modes and visual colour-map selector. Use existing ImageIntensity:
  default right in single-image views, top in multi-image views.
- Preserve original detector resolution, orientation and square pixels on
  resize. No detector axes/ticks/card. Display rows count downward from top;
  scientific arrays/control points retain the existing Dioptas convention.
- Shared gestures: left rectangle zoom, right drag pan, right click 2× out,
  right double-click full fit; wheel zoom must not scroll the workspace. Pattern
  and cake offer X-range zoom: horizontal zoom-out preserves cake azimuth and
  fits both pattern intensity limits to visible data. Moving readout ~10 Hz.
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

The primary live preview owns port 1420. Do not reuse or kill the primary
server/window. Other user windows may contain work. If a native test is needed,
use your own bundled test window or a temporary Tauri config with a distinct
Vite port.

## GUI testing

Use headless tests by default. Run routine GUI interaction, layout, rendering,
and screenshot checks through headless Playwright, alongside relevant model,
unit, and build checks. Do not open native or headed browser windows, move the
real mouse, or steal focus for routine verification.

Open a real test window only when the behavior under test requires it, such as
native window management, OS dialogs, native focus behavior, or a Tauri/WebKit
integration issue that headless checks cannot adequately cover. Do not run
visible native smoke tests after every small UI change. When a visible check
is necessary, explain briefly why, use an isolated test window, and close only
that test's windows and processes. Preserve the user's previews and work.

Use standard CPython 3.13: `uv sync --python 3.13 --extra test` in your checkout,
and `npm ci` in desktop. Never share an editable .venv or mutate another
checkout's dependencies. Build with `npm run build`; exercise real models and
meaningful Qt parity/interaction checks, then existing calibration/browser
regressions as appropriate. When required by the criteria above, native smoke:
`npm run tauri:smoke` (uses embedded assets, no Vite port). Record remaining gaps
honestly; do not add dead buttons or fabricated scientific results.
