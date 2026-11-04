// Loaded by the existing isolated Map smoke, before its final report.
window.__dioptasMapWindowSmoke = async ({
  call,
  click,
  wait,
  ready,
  check,
}) => {
  const invoke = window.__TAURI_INTERNALS__.invoke;
  let resolveReport;
  const completed = new Promise((resolve) => {
    resolveReport = resolve;
  });
  const handler = window.__TAURI_INTERNALS__.transformCallback((event) =>
    resolveReport(event.payload),
  );
  const eventId = await invoke("plugin:event|listen", {
    event: "map-window-smoke",
    target: { kind: "Any" },
    handler,
  });
  try {
    click("Detach map");
    await wait(
      () =>
        document
          .querySelector('[aria-label="Integration"]')
          ?.getAttribute("aria-pressed") === "true",
      "Main window did not return to Integration",
    );
    const report = await Promise.race([
      completed,
      new Promise((_, reject) =>
        setTimeout(
          () => reject(Error("Native map child did not report")),
          40000,
        ),
      ),
    ]);
    check(report.ok, report.error || "Native map child failed");
    await wait(
      () => document.querySelector('button[aria-label="Detach map"]'),
      "Dock did not restore Map mode",
    );
    await ready();
    const state = await call("state");
    check(
      state.cake && state.pattern && !state.state.integrationDirty,
      "Selected map point did not populate Integration's cake and pattern",
    );
    check(
      state.map.selected === 5 && state.map.points === 6,
      "Dock lost map selection/data",
    );
    // Reopen then close through the native window's normal close lifecycle.
    await invoke("open_map_window");
    await invoke("open_map_window");
    await invoke("close_map_window");
    await ready();
    check(
      (await call("state")).map.points === 6,
      "Closing the map stopped the shared processor",
    );
    return report;
  } finally {
    window.__TAURI_EVENT_PLUGIN_INTERNALS__.unregisterListener(
      "map-window-smoke",
      eventId,
    );
    await invoke("plugin:event|unlisten", {
      event: "map-window-smoke",
      eventId,
    });
  }
};
