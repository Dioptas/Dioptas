# Native macOS verification — 2026-11-06

Verified in the scientific UI worktree with measured CeO2 data, the existing
scientific Python worker, and the real Tauri/WKWebView app. Ordinary browser
checks remain headless. Native windows are opened here for OS window, popup,
focus, file-dialog and native-renderer behavior.

| Check | Result | Evidence |
| --- | --- | --- |
| Batch detach/dock and linked detector/cake/pattern selection | Six reopen cycles pass with different sizes and positions; native logical bounds restored | `artifacts/tauri-batch-smoke.json` |
| Batch app restart, native close, minimize/raise, dock/collapse, splitters and saved window bounds | Four launch stages pass; each processor is reaped | `artifacts/tauri-batch-layout.json` |
| Main scientific workflow | Measured peak picking and calibration, original-resolution WebGL detector/cake, WebGL pattern, units/bins, overlays, phases/database, detached editor, masking, export and project round trips pass | `artifacts/tauri-native-smoke.json` |
| Native file dialogs | Open-calibration, save-project and multi-file Batch panels appear and cancel without changing scientific state | `nativeFileDialogs` in the main report |
| Map window | Binary snapshot, linked selection, independent movement, dock/reopen and full app restart pass | `artifacts/tauri-map-smoke.json` |
| Native help | Four popups extend outside the app, flip at the screen edge, retain main-window focus and dismiss on Escape/blur; stale shows remain dismissed | `artifacts/calibration-tooltip-native-smoke.json` |
| Field appearance | 465 resting-field samples per browser engine; native Batch/editor fields also pass. Table validation and focus remain visible | Browser `fieldAppearance` inventories and native `quietFields` / `tableFieldFocusAndError` |

Actual native window PNGs are under `artifacts/native-workflow/`,
`artifacts/native-batch/` and `artifacts/native-map/`. Historical native failures
remain under `artifacts/ui-audit/native/` alongside the current qualification summary.

## Findings and fixes

The current Batch check passed before changing the window-placement algorithm.
Earlier placement failures did not reproduce in six varied reopen cycles and the
restart campaign. The tests now use private WebKit stores rather than assuming
that a new bundle identifier isolates WKWebView's default store. They distinguish
native logical bounds from the WebKit content viewport, wait for native window
readiness/destruction and separate diagnostic messages from final results.

Native help did reveal a production issue: Tauri's macOS `show()` path requests
keyboard focus. The non-focusing help popup now uses AppKit `orderFront` instead.
Window-level Escape also exposed unchecked `event.target.closest()` calls;
shared shortcut contexts now handle non-element event targets safely.

The shared table stylesheet retained the old pale input-border token even though
ordinary form fields were already quiet. Table fields now use the same transparent
resting edge, with visible focus/error states. The old token is removed. A shared
rendered-field check covers both browser captures and native smoke windows.

## Reproduce

Run from `desktop/`, sequentially for native windows:

```sh
npm run tauri:smoke -- --batch
node scripts/tauri_batch_layout.mjs
npm run tauri:smoke
node scripts/map_window_geometry.mjs
node scripts/calibration_tooltip_native_smoke.mjs
```

These tests compile embedded assets and do not use the primary Vite preview.
Named persistent test stores require macOS 14 or newer; native test runs without
a named store use incognito storage. Test-only window inspection/cancellation
capabilities do not grant production scientific access to companion windows.

This is scoped macOS regression evidence, not exhaustive scientific validation or
certification. File-panel cancellation is tested with real panels; data exports
and reloads use explicit fixture paths. Human file selection, native colour-panel
interaction, screen readers, Windows/Linux packaging, mixed-DPI physical monitor
changes and native display-latency measurements remain unqualified. Pure placement
calculations for monitor changes remain covered by Rust unit tests.


The last native colour checks/screenshots were recorded at `60330f06`. A later
user clarification retains gray focus outlines but restores orange active
selections in tables, tabs and controls. That cosmetic correction is verified in
both browser engines, including Batch heatmap focus; it does not reopen native
windows for routine styling checks. The app bundle is rebuilt with the correction.
