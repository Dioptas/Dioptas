// Explicit smoke windows only: make native startup failures reviewable.
(() => {
  if (window.__nativeSmokeDiagnostics) return;
  window.__nativeSmokeDiagnostics = true;
  const report = (diagnostics) =>
    window.__TAURI_INTERNALS__
      .invoke("plugin:event|emit", {
        event: "native-smoke-diagnostic",
        payload: {
          window: window.__TAURI_INTERNALS__.metadata?.currentWindow?.label,
          ...diagnostics,
        },
      })
      .catch(() => {});
  window.addEventListener("error", (event) =>
    report({
      type: "error",
      message: event.message,
      source: event.filename,
      line: event.lineno,
      stack: event.error?.stack,
    }),
  );
  window.addEventListener("unhandledrejection", (event) =>
    report({
      type: "rejection",
      message: String(event.reason),
      stack: event.reason?.stack,
    }),
  );
  setTimeout(
    () =>
      report({
        type: "startup",
        viewport: { width: innerWidth, height: innerHeight },
        visibility: document.visibilityState,
        focused: document.hasFocus(),
        rootChildren: document.getElementById("root")?.children.length,
        app: !!document.querySelector(".app"),
        alert: document.querySelector('[role="alert"]')?.textContent,
        body: document.body.innerText.slice(0, 1600),
      }),
    2500,
  );
})();
