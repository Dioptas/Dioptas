# Shared interface and design audit

> Moved from the former desktop README (now `DEVELOPMENT.md`). Source paths and commands are relative to the repository root.

`TabList` owns task-tab keyboard navigation across the modes, settings and phase
editors. `Dialog` / `DialogHeader` own native modal focus, dismissal and headers;
nonmodal color and action menus retain their own list/menu interactions.
`ScientificNumberInput` formats a visual preview while keeping the exact input
value. `usePlotTypography` carries the Standard/Larger preference into canvas
labels and axes, and `GeometryProvenance`, `PatternFreshness` and
`StatusMessage` share scientific context and feedback. Chrome tokens live in
`uiTheme.css`; scientific palettes remain independent. Integration options are
kept as a session draft and applied together, including the radial coordinate.
The model's shared history action determines Undo/Redo routing and labels.
Manual geometry keeps full-precision drafts, allows convention comparisons and
requires applying/resetting a pending draft before editing the other convention.

The historical UI audit and before/after reports remain as evidence in Git
history. Their former Python bridge runners have been retired. Current checks
use `npm run test:ui-components`, the native headless workflow checks, and the
Rust scientific tests. Existing dated ratings below describe their original
review, not a fresh certification of this cleanup.

The fixed 25-category definitions and equal weights are in `UI_DESIGN_RUBRIC.json`.
`UI_DESIGN_REVIEW.json` records separate Codex and Claude ratings, evidence,
source revisions and limits. `UI_PEER_REVIEW.txt` retains the independent review
and its follow-up addendum verbatim. The current Codex mean is 9.472/10 (9.5 to
one decimal); Claude's independent mean is 9.02/10. These are scoped design
judgments, not scientific accuracy, production readiness or accessibility
certification. Subsequent fixes do not imply a new peer score.

## Evidence and remaining limits

The current checks include 65 frontend unit tests, 17 Rust tests, and 58 captured
views plus 39 behavior checks in each of Chromium and WebKit. Batch and pattern controls are checked against clipping ancestors and pointer hit
targets, and their headers must fit one row. Each engine inspects 465 resting
field appearances across captured states, including scientific tables. ARIA snapshots and raw axe
violations/incomplete findings accompany screenshots. Explicit failures and
UI-build hashes prevent incomplete or stale runs being published as current.

Focused regressions are available with `node scripts/ui_audit.mjs --stage=polish
--focus=polish` and `node scripts/ui_audit.mjs --stage=peer-check --focus=peer`.
The full audit includes both. A synthetic three-frame HDF5 fixture verifies
frame navigation; TIFF fixtures follow the existing first-page PIL path. Gold
phase/editor fixtures are not specimen identifications. The original screenshot
baseline is `b418d66b`; the earlier 9.1 checkpoint is `876e0651`.

Native macOS qualification now passes: six Batch detach/dock cycles with changing
bounds; four application-launch stages for floating/closed/docked/collapsed state,
splitters and native bounds; Map docking and a full application restart; measured
CeO2 calibration, WebGL detector/cake/pattern rendering, masking, phase/database
editing, exports and project round trips. Native open, save and batch chooser
cancellation preserves scientific state. All four native help popups retain main
window focus, including screen-edge placement and Escape/blur dismissal.

The original failed runs remain in `artifacts/ui-audit/native/`; they are historical
failures, not rewritten passes. Current reports, commands and scope are described
in [Native verification](NATIVE_VERIFICATION.md). Native screenshots are actual
window captures, distinct from the browser screenshots. Native tests use private
WebKit stores and disposable preference files; restart stages intentionally share
their own store. Screen readers, colour-panel interaction, Windows/Linux packaging,
native display-latency measurement remains outside
this qualification.

Retina WebGL results in `artifacts/ui-audit/performance/` retain both WebKit's
reported Apple GPU result and Chromium's slower SwiftShader wide-pan result.
The provenance file identifies the measured source and its limits. These are
headless browser measurements, not native GPU/display-latency certification.

The scan map uses its existing histogram/settings and Layer/ROI controls for scale and calculation context. The redundant permanent summary/color-key block below the map is removed in both main and detached Map views; a concise accessible description retains context without taking plot space.

Batch follows the same layout as Map: the redundant permanent intensity/source-units/color-key row below the heatmap is removed in both docked and detached views. Its histogram and display settings own the scale controls, with accessible context on the series. The now-unused `ColorScaleLegend` component and styles have been removed.
