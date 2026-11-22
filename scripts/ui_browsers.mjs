// DIOPTAS_GATE_UI_BROWSERS=chromium runs the UI checks in Chromium only.
// CI's Windows job sets it: Tauri renders with WebView2 (Chromium) on
// Windows, so Playwright's Windows WebKit build tests an engine no Windows
// user runs. Linux CI keeps both engines; WebKit there stands in for the
// WebKitGTK and WKWebView hosts.
export const chromiumOnly = process.env.DIOPTAS_GATE_UI_BROWSERS === "chromium";

// Spread into a [name, browserType] list in place of ["webkit", webkit].
export const withWebkit = (webkit) =>
  chromiumOnly ? [] : [["webkit", webkit]];
