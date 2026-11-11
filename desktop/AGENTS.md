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
- No scientific HTTP server or Qt application in the new host. Following the
  user-authorized migration, processing defaults to Rust/Dioptrin over Tauri-owned
  stdio. Python is an explicitly selected comparison backend; this is not WASM.

## Working branch and checkouts

The cohesive development checkout is `worktrees/rust-desktop`, branch
`develop`, reached through the workspace's `Dioptas` symlink. The former
`codex/rust-desktop` branch is retained for compatibility; new work targets
`develop`. Qt maintenance belongs on `legacy/qt`.
Continue new desktop work here. The Qt checkout, earlier view worktrees and
experimental `codex/desktop-scxrd` checkout are preserved separately.
Create separate worktrees from the actual application repository when needed;
do not create another application repository in the workspace wrapper.

Use the Rust processor in `backend/` for new scientific commands. Port an
existing Python feature to Rust before exposing it in the default application;
never silently fall back to Python. Compatibility/reference Python source stays
available for independent qualification. See `RUST_DESKTOP_CONSOLIDATION.md`.

The development server uses port 1420. Never kill or reuse another preview's
server/window. Use headless tests on an ephemeral port or the embedded frontend.

## Shared UI components

Use `Button`, `Input`, `Select`, `TextArea`, `Dialog`, `DialogHeader`,
`DialogPanel`, `Popover`, `Tooltip` and `Portal` from `src/ui` for controls and
floating surfaces in every mode and detached window. Shared appearance belongs
in `src/ui/ui.css`; view CSS owns layout and scientific state feedback. Compose
existing scientific field editors instead of changing their commit behavior.
Do not introduce raw control/dialog JSX, private portal implementations or a
second field/dialog palette. See `UI_COMPONENTS.md`. Run `npm test` and
`npm run test:ui-components` when changing the shared components.

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

The default Rust app and standalone build require no Python. For independent
Python references only, use standard CPython 3.13: `uv sync --python 3.13 --extra test`
in your checkout. Use `npm ci` in desktop. Never share an editable .venv or mutate another
checkout's dependencies. Build with `npm run build`; exercise real models and
meaningful Qt parity/interaction checks, then existing calibration/browser
regressions as appropriate. When required by the criteria above, native smoke:
`npm run tauri:smoke` (uses embedded assets, no Vite port). Record remaining gaps
honestly; do not add dead buttons or fabricated scientific results.
