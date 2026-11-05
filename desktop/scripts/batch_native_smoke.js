// Real WKWebView, binary IPC, Python BatchModel and stored-series selection.
(async () => {
  if (window.__batchSmokeRunning) return;
  window.__batchSmokeRunning = true;
  const call = window.__dioptasNativeCall;
  const delay = () => new Promise((r) => setTimeout(r, 80));
  const check = (ok, why) => {
    if (!ok) throw Error(why);
  };
  const ready = async () => {
    await delay();
    for (let i = 0; i < 1000; i++) {
      const error = document.querySelector('[role="alert"]');
      if (error) throw Error(error.textContent);
      if (!document.querySelector(".spin")) return;
      await delay();
    }
    throw Error("Batch UI did not finish");
  };
  const click = (label) => {
    const button = [...document.querySelectorAll("button")].find(
      (b) =>
        b.getAttribute("aria-label") === label ||
        b.textContent.trim() === label,
    );
    check(button && !button.disabled, `Missing ${label}`);
    button.click();
  };
  try {
    await ready();
    const host = await call("__host__");
    check(
      host.ok && !host.qtApplication && host.tcpListeners === 0,
      "Unexpected processing boundary",
    );
    let state = await call("state");
    if (!sessionStorage.getItem("batch-smoke-loaded")) {
      const cal = await call("open_calibration", {
        path: state.state.imagePath.replace(/\.tif$/, ".poni"),
      });
      check(cal.ok, cal.error);
      const batch = await call("open_image", {
        paths: Array(5).fill(state.state.imagePath),
        multiple: true,
      });
      check(
        batch.ok &&
          batch.batch.entries.length === 5 &&
          batch.batch.raster.data instanceof ArrayBuffer,
        batch.error || "Batch transfer failed",
      );
      sessionStorage.setItem("batch-smoke-loaded", "1");
      location.reload();
      return;
    }
    click("Batch");
    await ready();
    check(
      document.querySelectorAll(".batch-layout .intensity-histogram").length ===
        2,
      "Independent histograms missing",
    );
    click("Select batch pattern 4");
    await ready();
    state = await call("state");
    check(state.batch.selected === 3, "File selection was not linked");
    const canvas = document.querySelector('[data-testid="batch-heatmap"]'),
      b = canvas.getBoundingClientRect();
    canvas.setPointerCapture = canvas.releasePointerCapture = () => {};
    for (const type of ["pointerdown", "pointerup"])
      canvas.dispatchEvent(
        new PointerEvent(type, {
          bubbles: true,
          pointerId: 1,
          button: 0,
          clientX: b.x + 100,
          clientY: b.y + 12 + ((b.height - 58) * 1.5) / 5,
        }),
      );
    await ready();
    state = await call("state");
    check(state.batch.selected === 1, "Heatmap selection was not linked");
    const wheel = new WheelEvent("wheel", {
      bubbles: true,
      cancelable: true,
      clientX: b.x + 100,
      clientY: b.y + 100,
      deltaY: -100,
    });
    canvas.dispatchEvent(wheel);
    check(wheel.defaultPrevented, "Wheel scrolled workspace");
    const output = state.state.imagePath.replace(
      /dioptas\/tests\/data\/.+$/,
      "desktop/artifacts/native-batch.h5",
    );
    const save = await call("integration_save_batch", { path: output });
    check(save.ok, save.error);
    const loaded = await call("batch_open", { path: output });
    check(
      loaded.ok && loaded.batch.entries.length === 5,
      loaded.error || "HDF5 roundtrip failed",
    );
    await window.__TAURI_INTERNALS__.invoke("native_smoke_report", {
      report: {
        ok: true,
        processingPid: host.pid,
        qtApplication: host.qtApplication,
        tcpListeners: host.tcpListeners,
        batchPatterns: 5,
        binaryBatch: true,
        linkedSelection: true,
        independentHistograms: true,
        wheelPrevented: true,
        savedPath: output,
      },
    });
  } catch (e) {
    await window.__TAURI_INTERNALS__.invoke("native_smoke_report", {
      report: { ok: false, error: String(e.stack || e) },
    });
  }
})();
