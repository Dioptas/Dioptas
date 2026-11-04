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
  const nextReport = () =>
    new Promise((resolve) => {
      resolveReport = resolve;
    });
  const handler = window.__TAURI_INTERNALS__.transformCallback((event) =>
    resolveReport?.(event.payload),
  );
  const completed = nextReport();
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
    const reopened = nextReport();
    click("Detach map");
    const second = await reopened;
    check(second.ok, second.error || "Reopened map failed");
    const expected = report.placed,
      actual = second.initial;
    check(
      Math.abs(actual.position.x - expected.position.x) <= 2 &&
        Math.abs(actual.position.y - expected.position.y) <= 2 &&
        Math.abs(actual.width - expected.width) <= 1 &&
        Math.abs(actual.height - expected.height) <= 1,
      "Map bounds changed after docking: " +
        JSON.stringify({ expected, actual }),
    );
    await wait(
      () => document.querySelector('button[aria-label="Detach map"]'),
      "Second dock did not restore Map mode",
    );
    await ready();
    report.geometryRestored = true;
    report.lastPlacement = second.placed;
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
