// Injected only into the map child of this isolated --smoke process.
(async () => {
  const invoke = window.__TAURI_INTERNALS__.invoke;
  const delay = (ms = 30) => new Promise((resolve) => setTimeout(resolve, ms));
  const check = (ok, message) => {
    if (!ok) throw Error(message);
  };
  const wait = async (predicate) => {
    for (let i = 0; i < 800; i++) {
      if (await predicate()) return;
      await delay();
    }
    throw Error("Detached map did not settle: " + document.body.innerText);
  };
  let report;
  try {
    await wait(
      () =>
        document.querySelector('[data-testid="scan-map"] canvas') &&
        !document.querySelector("footer")?.textContent.includes("Processing…"),
    );
    check(
      document.querySelectorAll(".intensity-histogram").length === 1,
      "Detached map histogram missing",
    );
    check(
      !document.querySelector(".mode-navigation"),
      "Detached window contains the main workspace",
    );
    const before = await invoke("plugin:window|outer_position", {
      label: "map-window",
    });
    await invoke("plugin:window|set_position", {
      label: "map-window",
      value: { Physical: { x: before.x + 70, y: before.y + 20 } },
    });
    const after = await invoke("plugin:window|outer_position", {
      label: "map-window",
    });
    check(before.x !== after.x, "Map did not move independently");
    await invoke("plugin:window|set_size", {
      label: "map-window",
      value: { Logical: { width: 620, height: 520 } },
    });
    await delay(100);
    check(
      document.documentElement.scrollWidth <= innerWidth,
      "Detached map overflows its window",
    );
    let rejected = false;
    try {
      await invoke("desktop_invoke", {
        action: "integration_settings",
        payload: { bins: 12 },
      });
    } catch {
      rejected = true;
    }
    check(rejected, "Map window bypassed the main command queue");
    const canvas = document.querySelector(
      '[data-testid="scan-map"] [data-testid="detector-canvas"]',
    );
    canvas.setPointerCapture = canvas.releasePointerCapture = () => {};
    const b = canvas.getBoundingClientRect();
    const snapshot = await window.__dioptasNativeCall("map_snapshot");
    const [rows, columns] = snapshot.map.dimension;
    const scale = Math.min(b.width / columns, b.height / rows);
    const x = b.x + (b.width - columns * scale) / 2 + (columns - 0.5) * scale;
    const y = b.y + (b.height - rows * scale) / 2 + (rows - 0.5) * scale;
    for (const type of ["pointerdown", "pointerup"])
      canvas.dispatchEvent(
        new PointerEvent(type, {
          bubbles: true,
          clientX: x,
          clientY: y,
          button: 0,
          buttons: type === "pointerdown" ? 1 : 0,
          pointerId: 7,
        }),
      );
    await wait(
      async () =>
        (await window.__dioptasNativeCall("map_snapshot")).map.selected === 5,
    );
    check(!document.querySelector('[role="alert"]'), "Map selection failed");
    report = {
      ok: true,
      independentlyMoved: true,
      resized: true,
      binarySnapshot: true,
      linkedSelection: true,
      queueRestricted: true,
    };
  } catch (error) {
    report = { ok: false, error: String(error) };
  }
  await invoke("plugin:event|emit", {
    event: "map-window-smoke",
    payload: report,
  });
  if (report.ok) {
    const dock = [...document.querySelectorAll("button")].find(
      (button) => button.textContent.trim() === "Dock map",
    );
    dock.click();
  }
})();
