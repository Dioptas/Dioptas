// Native WKWebView + real stdio map workflow. Launched only with --map-smoke.
(async () => {
  if (window.__dioptasMapSmokeRunning) return;
  window.__dioptasMapSmokeRunning = true;
  const call = window.__dioptasNativeCall;
  const delay = (ms = 80) => new Promise((resolve) => setTimeout(resolve, ms));
  const check = (value, message) => {
    if (!value) throw Error(message);
  };
  const wait = async (fn, message) => {
    for (let i = 0; i < 1000; i++) {
      if (fn()) return;
      const error = document.querySelector('[role="alert"]');
      if (error) throw Error(error.textContent);
      await delay();
    }
    throw Error(message);
  };
  const ready = async () => {
    await delay();
    await wait(
      () => !document.querySelector(".spin"),
      "Map processing did not finish",
    );
  };
  const click = (label) => {
    const b = [...document.querySelectorAll("button")].find(
      (b) =>
        b.textContent.trim() === label ||
        b.getAttribute("aria-label") === label,
    );
    check(b && !b.disabled, `Missing/disabled ${label}`);
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
    if (!sessionStorage.getItem("dioptas-map-smoke-loaded")) {
      check(
        state.image && !state.state.calibrated,
        "Expected raw native example",
      );
      const calibration = await call("open_calibration", {
        path: state.state.imagePath.replace(/\.tif$/, ".poni"),
      });
      check(calibration.ok, calibration.error);
      const loaded = await call("map_load", {
        paths: Array(6).fill(state.state.imagePath),
      });
      check(
        loaded.ok && loaded.map.points === 6,
        loaded.error || "Native map integration failed",
      );
      sessionStorage.setItem("dioptas-map-smoke-loaded", "1");
      location.reload();
      return;
    }
    click("Map");
    await ready();
    check(
      document.querySelectorAll(".map-layout .intensity-histogram").length ===
        2,
      "Independent native histograms missing",
    );
    click("Grid");
    await delay();
    const rows = document.querySelector('input[aria-label="Map rows"]');
    const columns = document.querySelector('input[aria-label="Map columns"]');
    const input = (element, value) => {
      Object.getOwnPropertyDescriptor(
        HTMLInputElement.prototype,
        "value",
      ).set.call(element, value);
      element.dispatchEvent(new Event("input", { bubbles: true }));
    };
    input(rows, "2");
    input(columns, "3");
    await delay();
    click("Apply grid");
    await ready();
    const canvas = document.querySelector('[data-testid="scan-map"] canvas');
    check(canvas, "Native map canvas missing");
    canvas.setPointerCapture = canvas.releasePointerCapture = () => {};
    const b = canvas.getBoundingClientRect(),
      scale = Math.min((b.width - 8) / 3, (b.height - 8) / 2);
    const x = b.x + (b.width - 3 * scale) / 2 + 1.5 * scale,
      y = b.y + (b.height - 2 * scale) / 2 + 0.5 * scale;
    for (const type of ["pointerdown", "pointerup"])
      canvas.dispatchEvent(
        new PointerEvent(type, {
          bubbles: true,
          pointerId: 1,
          button: 0,
          buttons: type === "pointerdown" ? 1 : 0,
          clientX: x,
          clientY: y,
        }),
      );
    await ready();
    state = await call("state");
    check(
      state.map.selected === 1,
      "Native map selection did not link to point 1",
    );
    check(
      state.image.step === 1 && state.pattern.y.length === state.state.bins,
      "Native linked image/pattern resolution mismatch",
    );
    click("Layers");
    await delay();
    click("Add window");
    await ready();
    state = await call("state");
    check(state.map.rois.length === 2, "Native window creation failed");
    const event = new WheelEvent("wheel", {
      bubbles: true,
      cancelable: true,
      deltaY: -120,
      clientX: x,
      clientY: y,
    });
    check(
      !canvas.dispatchEvent(event) && event.defaultPrevented,
      "Native map wheel escaped",
    );
    const source = state.state.imagePath,
      root = source.slice(0, source.indexOf("/dioptas/tests/data/"));
    check(root, "Native fixture root missing");
    const exported = await call("map_export", {
      path: root + "/desktop/artifacts/native-map.txt",
    });
    check(exported.ok, exported.error);
    const saved = await call("save_project", {
      path: root + "/desktop/artifacts/native-map.dio",
    });
    check(saved.ok, saved.error);
    const reopened = await call("open_project", { path: saved.savedPath });
    check(
      reopened.ok && reopened.map.rois.length === 2,
      "Native project map did not reopen",
    );
    await window.__TAURI_INTERNALS__.invoke("native_smoke_report", {
      report: {
        ok: true,
        host: "tauri",
        transport: host.transport,
        processingPid: host.pid,
        qtApplication: host.qtApplication,
        tcpListeners: host.tcpListeners,
        mapPoints: 6,
        linkedSelection: true,
        fullResolution: true,
        independentHistograms: true,
        windowCreation: true,
        wheelPrevented: true,
        projectRoundTrip: true,
        mapTextExport: true,
      },
    });
  } catch (error) {
    await window.__TAURI_INTERNALS__.invoke("native_smoke_report", {
      report: { ok: false, error: String(error) },
    });
  }
})();
