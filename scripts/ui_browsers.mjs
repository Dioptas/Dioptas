// DIOPTAS_GATE_UI_BROWSERS controls which Playwright engines the UI checks use:
//   unset / "all"   : Chromium + WebKit on every dual-engine check (default, develop).
//   "chromium"      : Chromium only (Windows CI, where Tauri uses WebView2).
//   "webkit-subset" : Handled by check_native_desktop.mjs, which keeps WebKit
//                     for the curated engine-sensitive subset and passes
//                     DIOPTAS_GATE_UI_BROWSERS=chromium to workflow-only checks.
export const chromiumOnly = process.env.DIOPTAS_GATE_UI_BROWSERS === "chromium";

// Spread into a [name, browserType] list in place of ["webkit", webkit].
export const withWebkit = (webkit) =>
  chromiumOnly ? [] : [["webkit", webkit]];
