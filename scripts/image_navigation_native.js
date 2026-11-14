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
  const wait = async (test, message, timeout = 30000) => {
    const start = performance.now();
    while (!test()) {
      if (performance.now() - start > timeout) throw Error(message);
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
  let verification = null;
  const contexts = new Set();
  const discardedSamples = [];
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
      if (
        active &&
        ["raster-submitted", "pattern-rendered", "batch-rendered"].includes(
          event.stage,
        )
      ) {
        const sample = active;
        const generation = (sample.drawGeneration =
          (sample.drawGeneration ?? 0) + 1);
        // Register at the draw rather than two frames after polling detects it.
        // The second callback bounds a paint opportunity after all matching draws.
        requestAnimationFrame(() => {
          for (const gl of contexts)
            if (gl.canvas.isConnected && !gl.isContextLost()) gl.finish();
          requestAnimationFrame(() => {
            if (active === sample && sample.drawGeneration === generation)
              sample.presentationAt = performance.now();
          });
        });
      }
      if (
        verification &&
        ((event.stage === "raster-submitted" && event.kind === "detector") ||
          event.stage === "pattern-rendered")
      ) {
        const kind =
          event.stage === "pattern-rendered" ? "pattern" : "detector";
        const canvas = document.querySelector(`[data-testid="${kind}-gpu"]`);
        const gl = canvas?.getContext("webgl2");
        if (!gl || gl.isContextLost())
          throw Error("Verification renderer unavailable");
        const pixels = new Uint8Array(canvas.width * canvas.height * 4);
        gl.readPixels(
          0,
          0,
          canvas.width,
          canvas.height,
          gl.RGBA,
          gl.UNSIGNED_BYTE,
          pixels,
        );
        verification.set(kind, {
          width: canvas.width,
          height: canvas.height,
          pixels,
        });
      }
    };
    const originalContext = HTMLCanvasElement.prototype.getContext;
    HTMLCanvasElement.prototype.getContext = function (...args) {
      const context = originalContext.apply(this, args);
      if (args[0] === "webgl2" && context) contexts.add(context);
      return context;
    };
    for (const operation of ["texImage2D", "texSubImage2D"]) {
      const originalUpload = WebGL2RenderingContext.prototype[operation];
      WebGL2RenderingContext.prototype[operation] = function (...args) {
        const start = performance.now();
        const result = originalUpload.apply(this, args);
        contexts.add(this);
        if (active)
          active.uploads.push({
            operation,
            kind: this.canvas.dataset.testid ?? "pattern",
            ms: performance.now() - start,
            bytes: args[8]?.byteLength ?? 0,
          });
        return result;
      };
    }
    for (const name of ["getError", "isContextLost", "drawArrays"]) {
      const original = WebGL2RenderingContext.prototype[name];
      WebGL2RenderingContext.prototype[name] = function (...args) {
        contexts.add(this);
        const start = performance.now();
        const result = original.apply(this, args);
        if (active)
          (active.gpuCalls ??= []).push({
            operation: name,
            kind: this.canvas.dataset.testid ?? "pattern",
            ms: performance.now() - start,
          });
        return result;
      };
    }
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
    const loading = [];
    const series = [];
    const rendered = [];
    const integrationButton = () => {
      const button =
        document.querySelector('button[aria-label="Integration"]') ??
        [...document.querySelectorAll("button")].find(
          (button) => button.textContent.trim() === "Integration",
        );
      if (!button) throw Error("Integration mode button missing");
      return button;
    };
    const configure = async (image, calibration, reset = false) => {
      // Open calibration while already in Integration/Image, so validation does
      // not request a cake during the hidden-cake campaigns.
      integrationButton().click();
      await paint();
      const start = performance.now();
      await call("open_image", {
        path: image,
        ...(reset ? { reset_calibration: true } : {}),
      });
      const opened = performance.now();
      await call("open_calibration", { path: calibration });
      loading.push({
        image,
        openToPaintMs: opened - start,
        calibrationToPaintMs: performance.now() - opened,
      });
      await call("integration_settings", { bins: 1000, cake_bins: 360 });
      integrationButton().click();
      await paint();
      await wait(
        () =>
          document.querySelector('[aria-label="Integration next image"]') &&
          !document.querySelector(".spin"),
        "Integration image browser unavailable",
      );
      await paint();
    };
    // options: {action, click, selected, complete, detached, index} time Batch
    // and Map selections through the same draw/presentation path as arrows.
    const step = async (
      scenario,
      direction,
      boundary = false,
      options = {},
    ) => {
      if (config.foreground && !options.detached && !document.hasFocus()) {
        await invoke("native_smoke_report", {
          report: { stage: "diagnostic", navigationPause: scenario },
        });
        await wait(
          () => document.hasFocus() && document.visibilityState === "visible",
          "Native timing paused waiting for its test window",
          120000,
        );
      }
      const source = scenario.startsWith("eiger") ? "frame" : "image";
      const action =
        options.action ??
        (source === "frame" ? "integration_navigation" : "next_image");
      const button = options.click
        ? null
        : document.querySelector(
            `[aria-label="Integration ${direction > 0 ? "next" : "previous"} ${source}"]`,
          );
      if (!options.click && (!button || button.disabled))
        throw Error("Native image navigation is disabled");
      const before = probe.state();
      const beforeBuffer = probe.image()?.bufferId;
      active = {
        start: performance.now(),
        startFocused: document.hasFocus(),
        events: [],
        uploads: [],
      };
      const started = options.click ? await options.click() : button.click();
      if (started?.startAbs != null)
        active.start = started.startAbs - performance.timeOrigin;
      if (started?.focused != null) active.startFocused = started.focused;
      await wait(() => {
        const hydrated = active.events.find(
          (event) => event.stage === "ipc-hydrated" && event.action === action,
        );
        if (!hydrated) return false;
        if (boundary)
          return document
            .querySelector(".workflow-status")
            ?.textContent.includes("No new image available");
        const response = active.events.find(
          (event) =>
            event.stage === "command-response" && event.action === action,
        );
        const id = probe.image()?.bufferId;
        return (
          (!options.selected || options.selected()) &&
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
      if (!boundary)
        await wait(
          () => active.presentationAt != null,
          "No presentation marker",
        );
      const companion = await options.complete?.();
      const trace = active;
      active = null;
      const after = probe.state();
      if (
        !boundary &&
        !options.action &&
        before.imagePath === after.imagePath &&
        before.integration.frames > 1 &&
        after.integration.frame !== before.integration.frame + direction
      )
        throw Error(
          "The displayed source frame did not follow the clicked arrow",
        );
      if (document.querySelector('[role="dialog"]') || errors.length)
        throw Error(errors.join("\n") || "Native navigation opened a dialog");
      if (config.foreground && document.visibilityState !== "visible") {
        discardedSamples.push({
          scenario,
          reason: "Focus/visibility changed during sample",
        });
        return null;
      }
      const event = (stage) =>
        trace.events.find(
          (entry) =>
            entry.stage === stage && (!entry.action || entry.action === action),
        );
      const wire = event("ipc-hydrated");
      if (hiddenCake && wire.cakeBufferId)
        throw Error(`Hidden cake was calculated/transferred in ${scenario}`);
      if (hiddenCake && wire.calibrationRingCount)
        throw Error(
          `Unused calibration contours were transferred in ${scenario}`,
        );
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
        action,
        requestId: wire.requestId,
        clickToPresentationMs: boundary
          ? null
          : Math.max(
              trace.presentationAt,
              companion?.presentationAbs != null
                ? companion.presentationAbs - performance.timeOrigin
                : 0,
            ) - trace.start,
        mainPresentationMs: boundary
          ? null
          : trace.presentationAt - trace.start,
        companion,
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
        cakeBufferId: wire.cakeBufferId ?? null,
        calibrationRingCount: wire.calibrationRingCount,
        bufferId: probe.image()?.bufferId,
        selectedIndex: options.index ?? null,
        sourceFrame: after.integration.frame,
        image: after.imageName,
        startFocused: trace.startFocused,
        focused: document.hasFocus(),
        visibility: document.visibilityState,
        renderer: document.querySelector('[data-testid="detector-canvas"]')
          ?.dataset.renderer,
        uploads: trace.uploads,
        gpuCalls: trace.gpuCalls ?? [],
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
            clickToPresentationMs: row.clickToPresentationMs,
            clickToPaintMs: row.clickToPaintMs,
            ipcMs: row.ipcMs,
            pixelBytes: row.pixelBytes,
          },
        },
      });
      return row;
    };
    // Batch/Map selection campaigns keep the Cake hidden and assert that no
    // cake or unused calibration contour is calculated or transferred.
    const hiddenCake = !!(config.seriesNavigation || config.allViews);
    const imageBrowsing = !config.seriesNavigation || config.allViews;
    if (imageBrowsing && !config.series && !config.eigerOnly) {
      await configure(
        `${config.root}/tests/data/image_001.tif`,
        `${config.root}/tests/data/LaB6_40keV_MarCCD.poni`,
      );
      await step("tiff-first-next", 1);
      await step("tiff-first-previous", -1);
      for (let i = 0; i < 12; i++)
        await step("tiff-cached", i % 2 === 0 ? 1 : -1);
      await step(config.allViews ? "tiff-boundary-setup" : "tiff-cached", 1);
      await step("tiff-boundary", 1, true);
      await invoke("native_smoke_report", {
        report: { stage: "diagnostic", capture: "tiff-native-navigation" },
      });
      await delay(800);
    }
    if (config.eiger && imageBrowsing) {
      await configure(
        config.eiger,
        config.eiger.replace(/\.h5$/, ".poni"),
        true,
      );
      if (config.series) {
        const diagnostic = async () => {
          const wire = await invoke("desktop_invoke", {
            action: "integration_diagnostics",
            payload: {},
            cachedBuffers: [],
          });
          const length = new DataView(wire).getUint32(0, true);
          return JSON.parse(
            new TextDecoder().decode(new Uint8Array(wire, 4, length)),
          ).result.integrationDiagnostics;
        };
        const presets = config.seriesMethod
          ? [
              {
                name: "method-no-errors",
                bins: 2000,
                poisson_errors: false,
                method: config.seriesMethod,
              },
              {
                name: "method-poisson",
                bins: 2000,
                poisson_errors: true,
                method: config.seriesMethod,
              },
            ]
          : config.seriesExtra
            ? [
                {
                  name: "bins-control-1000",
                  bins: 1000,
                  poisson_errors: false,
                },
                {
                  name: "bins-control-2000",
                  bins: 2000,
                  poisson_errors: false,
                },
                {
                  name: "compatibility-sample",
                  bins: 2000,
                  poisson_errors: false,
                  method: "pyfai_full",
                  frames: 32,
                },
              ]
            : [
                { name: "default", bins: 1000, poisson_errors: false },
                { name: "matched-poisson", bins: 2000, poisson_errors: true },
              ];
        for (const preset of presets) {
          const frames = preset.frames ?? probe.state().integration.frames;
          const method = preset.method ?? "polygon";
          await call("integration_settings", {
            bins: preset.bins,
            poisson_errors: preset.poisson_errors,
            method,
            sparse_layout: "csr",
            polarization: 0.965,
          });
          for (const view of ["batch"]) {
            const action = "batch_load_data";
            for (const pass of ["first", "warm"]) {
              const progress = [];
              const observer = new MutationObserver(() => {
                const text =
                  document.querySelector(".workflow-status")?.textContent ?? "";
                if (text.includes("images/s") && text !== progress.at(-1))
                  progress.push(text);
              });
              observer.observe(document.body, {
                subtree: true,
                childList: true,
                characterData: true,
              });
              const before = await diagnostic();
              active = { start: performance.now(), events: [], uploads: [] };
              await call(action, { paths: [config.eiger], stop: frames });
              for (const gl of contexts)
                if (gl.canvas.isConnected && !gl.isContextLost()) gl.finish();
              await paint();
              const seconds = (performance.now() - active.start) / 1000;
              const events = active.events;
              active = null;
              observer.disconnect();
              const after = await diagnostic();
              const delta = Object.fromEntries(
                Object.keys(after).map((k) => [k, after[k] - (before[k] ?? 0)]),
              );
              if (
                method === "polygon" &&
                delta.frameParallelIntegrations !== frames
              )
                throw Error("Full Eiger series did not use the frame pipeline");
              if (!progress.length && frames === 625)
                throw Error("Live integration images/s was not displayed");
              const start = events.find(
                (e) => e.stage === "ipc-start" && e.action === action,
              );
              const received = events.find(
                (e) => e.stage === "ipc-received" && e.action === action,
              );
              series.push({
                preset: preset.name,
                bins: preset.bins,
                poisson: preset.poisson_errors,
                view,
                pass,
                frames,
                method,
                seconds,
                fps: frames / seconds,
                nativeIpcSeconds: (received.at - start.at) / 1000,
                diagnosticsDelta: delta,
                progress,
              });
              await invoke("native_smoke_report", {
                report: { stage: "hmr", navigationProgress: series.at(-1) },
              });
            }
          }
        }
      }
      if (!config.series) {
        if (config.singleMethod) {
          for (const poisson of [false, true]) {
            await call("integration_settings", {
              method: config.singleMethod,
              bins: config.singleBins,
              poisson_errors: poisson,
              trim_zeros: false,
            });
            const tag = `eiger-${poisson ? "poisson" : "no-errors"}`;
            // Same calibrated first frame and display settings in every variant.
            // Record actual App commands through presentation opportunities.
            for (let i = 0; i < 3; i++) {
              const start = performance.now();
              const frame = [0, 312, 624][i];
              await call("open_image", { path: config.eiger, frame });
              loading.push({
                image: config.eiger,
                scenario: tag,
                repeat: i,
                sourceFrame: frame + 1,
                expectedBufferReuse: i === 0,
                calibratedOpenToPaintMs: performance.now() - start,
              });
            }
            await call("open_image", { path: config.eiger, frame: 0 });
            for (let i = 0; i < config.singleSteps; i++)
              await step(`${tag}-new-frame`, 1);
            await step(`${tag}-cached`, -1);
            for (let i = 0; i < config.singleSteps; i++)
              await step(`${tag}-cached`, i % 2 === 0 ? 1 : -1);
            // Untimed actual GPU pixel readback checks, before presentation
            // clears the drawing buffers. Keep verification out of timings.
            verification = new Map();
            await call("open_image", { path: config.eiger, frame: 312 });
            const captured = verification;
            verification = null;
            if (captured.size !== 2)
              throw Error("Missing detector/pattern verification pixels");
            for (const [kind, { width, height, pixels }] of captured) {
              const digest = await crypto.subtle.digest("SHA-256", pixels);
              rendered.push({
                scenario: tag,
                sourceFrame: 313,
                kind,
                width,
                height,
                sha256: [...new Uint8Array(digest)]
                  .map((v) => v.toString(16).padStart(2, "0"))
                  .join(""),
              });
            }
          }
        } else if (config.allViews) {
          // Match the Batch/Map campaign's source frames 2–13 exactly
          // (1-based frame payload 2 is source index 1).
          await call("integration_navigation", { frame: 2 });
          for (let i = 0; i < 12; i++) await step("eiger-new-frame", 1);
          // Warm indices 0/1, then time the same alternating pair as Batch/Map.
          await call("integration_navigation", { frame: 1 });
          await step("eiger-cached-warmup", 1);
          for (let i = 0; i < 12; i++)
            await step("eiger-cached", i % 2 === 0 ? -1 : 1);
        } else {
          for (let i = 0; i < 12; i++) await step("eiger-new-frame", 1);
          await step("eiger-cached", -1);
          for (let i = 0; i < 12; i++)
            await step("eiger-cached", i % 2 === 0 ? 1 : -1);
        }
      }
      await invoke("native_smoke_report", {
        report: { stage: "diagnostic", capture: "eiger-native-navigation" },
      });
      await delay(800);
    }
    if (config.seriesNavigation || config.allViews)
      await window.__dioptasSeriesNavigation({
        config,
        call,
        configure,
        step,
        wait,
        paint,
        delay,
        invoke,
      });
    const summaries = {};
    for (const scenario of new Set(reports.map((row) => row.scenario))) {
      const rows = reports.filter((row) => row.scenario === scenario);
      summaries[scenario] = Object.fromEntries(
        [
          "clickToPresentationMs",
          "mainPresentationMs",
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
    const diagnosticsWire = await invoke("desktop_invoke", {
      action: "integration_diagnostics",
      payload: {},
      cachedBuffers: [],
    });
    const diagnosticsLength = new DataView(diagnosticsWire).getUint32(0, true);
    const diagnostics = JSON.parse(
      new TextDecoder().decode(
        new Uint8Array(diagnosticsWire, 4, diagnosticsLength),
      ),
    ).result.integrationDiagnostics;
    if (
      hiddenCake &&
      (diagnostics.cakeIntegrations !== 0 || diagnostics.cakePlanBuilds !== 0)
    )
      throw Error(
        `Hidden browsing performed ${diagnostics.cakeIntegrations} cake integrations`,
      );
    await invoke("native_smoke_report", {
      report: {
        stage: "complete",
        ok: true,
        processingPid: host.pid,
        scope: config.series
          ? "Actual React App Batch load action in Tauri WKWebView, production binary IPC, GUI processing and GPU renderers; complete command through GPU completion and paint opportunities; excludes OS file picker and initial image/calibration setup; physical LCD scanout unmeasured"
          : "Actual React App in Tauri WKWebView, production binary IPC and GPU renderers; DOM activation to draw-anchored two-frame presentation opportunity (clickToPresentationMs); legacy poll-then-two-frame timing (clickToPaintMs) retained for comparison; physical LCD scanout unmeasured",
        viewport: [innerWidth, innerHeight],
        devicePixelRatio,
        summaries,
        loading,
        series,
        rendered,
        diagnostics,
        discardedSamples,
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
