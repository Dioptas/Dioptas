// Runs only in its isolated --batch native test window.
(async () => {
  if (window.__batchSmokeRunning) return;
  window.__batchSmokeRunning = true;
  const call = window.__dioptasNativeCall,
    invoke = window.__TAURI_INTERNALS__.invoke;
  const delay = (ms = 70) => new Promise((r) => setTimeout(r, ms));
  const check = (v, m) => {
    if (!v) throw Error(m);
  };
  const wait = async (fn, message) => {
    for (let i = 0; i < 600; i++) {
      if (await fn()) return;
      const e = document.querySelector('[role="alert"]');
      if (e) throw Error(e.textContent);
      await delay();
    }
    throw Error(message);
  };
  const ready = () =>
    wait(
      () => !document.querySelector(".spin"),
      "Main processing did not finish",
    );
  const click = (label) => {
    const b = [...document.querySelectorAll("button")].find(
      (b) =>
        b.getAttribute("aria-label") === label ||
        b.textContent.trim() === label,
    );
    check(b && !b.disabled, `Missing ${label}`);
    b.click();
  };
  try {
    await ready();
    const host = await call("__host__");
    check(
      host.ok && !host.qtApplication && host.tcpListeners === 0,
      "Wrong processing boundary",
    );
    let state = await call("state");
    if (!sessionStorage.getItem("batch-smoke-loaded")) {
      check(
        (
          await call("open_calibration", {
            path: state.state.imagePath.replace(/\.tif$/, ".poni"),
          })
        ).ok,
        "Calibration failed",
      );
      const batch = await call("batch_load", {
        paths: Array(5).fill(state.state.imagePath),
      });
      check(
        batch.ok &&
          batch.batch.raster.data instanceof ArrayBuffer &&
          batch.cake,
        "Binary batch/cake failed",
      );
      sessionStorage.setItem("batch-smoke-loaded", "1");
      location.reload();
      return;
    }
    click("Integration");
    await delay();
    check(
      !document.querySelector('button[aria-label="Batch"]'),
      "Batch still exists in mode navigation",
    );
    localStorage.setItem("dioptas-batch:docked", "false");
    let resolveReport;
    const next = () => new Promise((r) => (resolveReport = r));
    const handler = window.__TAURI_INTERNALS__.transformCallback((e) =>
      resolveReport?.(e.payload),
    );
    await invoke("plugin:event|listen", {
      event: "batch-window-smoke",
      target: { kind: "Any" },
      handler,
    });
    const firstPromise = next();
    click("Batch view…");
    const first = await firstPromise;
    check(first.ok, first.error);
    await wait(
      () => document.querySelector(".batch-dock"),
      "Batch did not dock",
    );
    await ready();
    state = await call("state");
    check(
      state.batch.selected === first.selected && state.cake && state.pattern,
      "Companion selection did not update Integration",
    );
    check(
      document
        .querySelector('[aria-label="Integration"]')
        .getAttribute("aria-pressed") === "true",
      "Integration was replaced",
    );
    const dock = document.querySelector(".batch-dock").getBoundingClientRect(),
      image = document.querySelector(".detector-panel").getBoundingClientRect();
    check(dock.y >= image.bottom - 1, "Dock is not below image");
    const secondPromise = next();
    click("Detach batch");
    const second = await secondPromise;
    check(second.ok, second.error);
    check(
      Math.abs(second.initial.width - first.placed.width) < 2 &&
        Math.abs(second.initial.height - first.placed.height) < 2,
      "Batch window size was not remembered",
    );
    check(
      Math.abs(second.initial.position.x - first.placed.position.x) < 2 &&
        Math.abs(second.initial.position.y - first.placed.position.y) < 2,
      "Batch window position was not remembered",
    );
    await wait(
      () => document.querySelector(".batch-dock"),
      "Second dock failed",
    );
    state = await call("state");
    check(
      state.batch.selected === second.selected && state.cake,
      "Reopened selection lost cake",
    );
    const output = state.state.imagePath.replace(
      /dioptas\/tests\/data\/.+$/,
      "desktop/artifacts/native-batch.h5",
    );
    check(
      (await call("integration_save_batch", { path: output })).ok,
      "Save failed",
    );
    check(
      (await call("batch_open", { path: output })).ok,
      "Stored batch failed",
    );
    await invoke("native_smoke_report", {
      report: {
        ok: true,
        processingPid: host.pid,
        companionWindow: true,
        lowerLeftDock: true,
        linkedCake: true,
        binaryBatch: true,
        queueRestricted: true,
        placementRestored: true,
        batchPatterns: 5,
        savedPath: output,
      },
    });
  } catch (e) {
    await invoke("native_smoke_report", {
      report: { ok: false, error: `${e}\n${e.stack ?? ""}` },
    });
  }
})();
