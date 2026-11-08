// Runs only in the explicit --navigation-benchmark native test window.
(async () => {
  const invoke = window.__TAURI_INTERNALS__.invoke;
  const delay = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
  const paint = () =>
    new Promise((resolve, reject) => {
      const timeout = setTimeout(
        () => reject(Error("The native test window stopped presenting frames")),
        8000,
      );
      requestAnimationFrame(() =>
        requestAnimationFrame(() => {
          clearTimeout(timeout);
          resolve();
        }),
      );
    });
  const wait = async (test, message) => {
    const start = performance.now();
    while (!test()) {
      if (performance.now() - start > 30000) throw Error(message);
      await delay(5);
    }
  };
  const median = (values) =>
    [...values].sort((a, b) => a - b)[Math.floor(values.length / 2)];
  const errors = [];
  window.addEventListener("error", (event) =>
    errors.push(String(event.error ?? event.message)),
  );
  window.addEventListener("unhandledrejection", (event) =>
    errors.push(String(event.reason)),
  );
  let active = null;
  const contexts = new Set();
  try {
    const config = window.__dioptasNavigationConfig;
    if (!config?.root)
      throw Error("Missing native navigation test configuration");
    if (config.foreground) {
      await wait(
        () => document.visibilityState === "visible" && document.hasFocus(),
        "The isolated native test window could not become visible and focused",
      );
    }
    await wait(
      () =>
        window.__dioptasNavigationProbe?.state() &&
        !document.querySelector(".spin"),
      "Navigation benchmark bundle did not connect",
    );
    const probe = window.__dioptasNavigationProbe;
    window.__dioptasNavigationTrace = (event) => {
      if (active) active.events.push(event);
    };
    const originalUpload = WebGL2RenderingContext.prototype.texImage2D;
    WebGL2RenderingContext.prototype.texImage2D = function (...args) {
      const start = performance.now();
      const result = originalUpload.apply(this, args);
      contexts.add(this);
      if (active)
        active.uploads.push({
          kind: this.canvas.dataset.testid ?? "pattern",
          ms: performance.now() - start,
          bytes: args[8]?.byteLength ?? 0,
        });
      return result;
    };
    const call = async (action, payload = {}) => {
      await probe.run(action, payload);
      if (document.querySelector('[role="dialog"]'))
        throw Error(`Unexpected dialog after ${action}`);
      await wait(
        () => !document.querySelector(".spin"),
        `${action} stayed busy`,
      );
      await paint();
    };
    const hostWire = await invoke("desktop_invoke", {
      action: "__host__",
      payload: {},
      cachedBuffers: [],
    });
    const hostLength = new DataView(hostWire).getUint32(0, true);
    const host = JSON.parse(
      new TextDecoder().decode(new Uint8Array(hostWire, 4, hostLength)),
    ).result;
    await invoke("native_smoke_report", {
      report: {
        stage: "diagnostic",
        processingPid: host.pid,
        message: "Native navigation benchmark connected",
      },
    });
    const reports = [];
    const configure = async (image, calibration, reset = false) => {
      await call("open_image", {
        path: image,
        ...(reset ? { reset_calibration: true } : {}),
      });
      await call("open_calibration", { path: calibration });
      await call("integration_settings", { bins: 1000, cake_bins: 360 });
      const integration =
        document.querySelector('button[aria-label="Integration"]') ??
        [...document.querySelectorAll("button")].find(
          (button) => button.textContent.trim() === "Integration",
        );
      if (!integration) throw Error("Integration mode button missing");
      integration.click();
      await paint();
      await wait(
        () =>
          document.querySelector('[aria-label="Integration next image"]') &&
          !document.querySelector(".spin"),
        "Integration image browser unavailable",
      );
      await paint();
    };
    const step = async (scenario, direction, boundary = false) => {
      const button = document.querySelector(
        `[aria-label="Integration ${direction > 0 ? "next" : "previous"} image"]`,
      );
      if (!button || button.disabled)
        throw Error("Native image navigation is disabled");
      const before = probe.state();
      const beforeBuffer = probe.image()?.bufferId;
      active = { start: performance.now(), events: [], uploads: [] };
      button.click();
      await wait(() => {
        const hydrated = active.events.find(
          (event) =>
            event.stage === "ipc-hydrated" && event.action === "next_image",
        );
        if (!hydrated) return false;
        if (boundary)
          return document
            .querySelector(".workflow-status")
            ?.textContent.includes("No new image available");
        const response = active.events.find(
          (event) =>
            event.stage === "command-response" && event.action === "next_image",
        );
        const id = probe.image()?.bufferId;
        return (
          id !== beforeBuffer &&
          active.events.some(
            (event) =>
              event.stage === "raster-submitted" &&
              event.kind === "detector" &&
              event.bufferId === id,
          ) &&
          active.events.some(
            (event) =>
              event.stage === "pattern-rendered" && event.at > response?.at,
          )
        );
      }, `No new rendered frame in ${scenario}`);
      const submittedAt = performance.now();
      // Wait for the actual native GPU work, then allow a WebKit paint cycle.
      // This is an upper bound on presentation, not an LCD scanout measurement.
      const finishStart = performance.now();
      for (const gl of contexts)
        if (gl.canvas.isConnected && !gl.isContextLost()) gl.finish();
      const gpuCompleteAt = performance.now();
      await paint();
      const end = performance.now();
      const trace = active;
      active = null;
      const after = probe.state();
      if (
        !boundary &&
        before.imagePath === after.imagePath &&
        before.integration.frames > 1 &&
        after.integration.frame !== before.integration.frame + direction
      )
        throw Error(
          "The displayed source frame did not follow the clicked arrow",
        );
      if (document.querySelector('[role="dialog"]') || errors.length)
        throw Error(errors.join("\n") || "Native navigation opened a dialog");
      if (
        config.foreground &&
        (!document.hasFocus() || document.visibilityState !== "visible")
      )
        throw Error("Native navigation lost its visible foreground window");
      const event = (stage) =>
        trace.events.find(
          (entry) =>
            entry.stage === stage &&
            (!entry.action || entry.action === "next_image"),
        );
      const wire = event("ipc-hydrated");
      const raster = trace.events
        .filter(
          (entry) =>
            entry.stage === "raster-submitted" && entry.kind === "detector",
        )
        .at(-1);
      const row = {
        scenario,
        direction,
        boundary,
        requestId: wire.requestId,
        clickToGpuCompleteMs: gpuCompleteAt - trace.start,
        clickToPaintMs: end - trace.start,
        ipcMs: event("ipc-received").at - event("ipc-start").at,
        hydrationMs: wire.at - event("ipc-received").at,
        responseToDetectorSubmitMs: raster ? raster.at - wire.at : null,
        gpuFinishWaitMs: gpuCompleteAt - finishStart,
        paintWaitMs: end - gpuCompleteAt,
        pollWaitAfterSubmitMs: submittedAt - (raster?.at ?? wire.at),
        pixelBytes: wire.pixelBytes,
        headerBytes: wire.headerBytes,
        sourceFrame: after.integration.frame,
        image: after.imageName,
        focused: document.hasFocus(),
        visibility: document.visibilityState,
        renderer: document.querySelector('[data-testid="detector-canvas"]')
          ?.dataset.renderer,
        uploads: trace.uploads,
        events: trace.events.map((entry) => ({
          ...entry,
          at: entry.at - trace.start,
        })),
      };
      reports.push(row);
      await invoke("native_smoke_report", {
        report: {
          stage: "hmr",
          navigationProgress: {
            scenario,
            clickToPaintMs: row.clickToPaintMs,
            ipcMs: row.ipcMs,
            pixelBytes: row.pixelBytes,
          },
        },
      });
      return row;
    };
    await configure(
      `${config.root}/dioptas/tests/data/image_001.tif`,
      `${config.root}/dioptas/tests/data/LaB6_40keV_MarCCD.poni`,
    );
    await step("tiff-first-next", 1);
    await step("tiff-first-previous", -1);
    for (let i = 0; i < 12; i++)
      await step("tiff-cached", i % 2 === 0 ? 1 : -1);
    await step("tiff-cached", 1);
    await step("tiff-boundary", 1, true);
    await invoke("native_smoke_report", {
      report: { stage: "diagnostic", capture: "tiff-native-navigation" },
    });
    await delay(800);
    if (config.eiger) {
      await configure(
        config.eiger,
        config.eiger.replace(/\.h5$/, ".poni"),
        true,
      );
      for (let i = 0; i < 12; i++) await step("eiger-new-frame", 1);
      await step("eiger-cached", -1);
      for (let i = 0; i < 12; i++)
        await step("eiger-cached", i % 2 === 0 ? 1 : -1);
      await invoke("native_smoke_report", {
        report: { stage: "diagnostic", capture: "eiger-native-navigation" },
      });
      await delay(800);
    }
    const summaries = {};
    for (const scenario of new Set(reports.map((row) => row.scenario))) {
      const rows = reports.filter((row) => row.scenario === scenario);
      summaries[scenario] = Object.fromEntries(
        [
          "clickToGpuCompleteMs",
          "clickToPaintMs",
          "ipcMs",
          "hydrationMs",
          "responseToDetectorSubmitMs",
          "gpuFinishWaitMs",
          "paintWaitMs",
          "pixelBytes",
        ].map((key) => [
          key,
          median(rows.map((row) => row[key]).filter((value) => value !== null)),
        ]),
      );
    }
    await invoke("native_smoke_report", {
      report: {
        stage: "complete",
        ok: true,
        processingPid: host.pid,
        scope:
          "Actual React App in Tauri WKWebView, production binary IPC and GPU renderers; DOM button activation to GPU completion and two animation-frame presentation opportunity; physical LCD scanout unmeasured",
        viewport: [innerWidth, innerHeight],
        devicePixelRatio,
        summaries,
        reports,
        errors,
      },
    });
  } catch (error) {
    await invoke("native_smoke_report", {
      report: {
        ok: false,
        error: String(error),
        stack: error?.stack,
        events: active?.events,
        errors,
      },
    });
  }
})();
