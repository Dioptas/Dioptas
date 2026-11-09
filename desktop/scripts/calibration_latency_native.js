// Injected only into the isolated --navigation-benchmark test host.
(async () => {
  const invoke = window.__TAURI_INTERNALS__.invoke;
  const delay = (ms) => new Promise((r) => setTimeout(r, ms));
  const wait = async (test, message) => {
    const t = performance.now();
    while (!test()) {
      if (performance.now() - t > 45000) throw Error(message);
      await delay(2);
    }
  };
  const frames = () =>
    new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
  let active = null;
  try {
    await wait(
      () =>
        window.__dioptasNavigationProbe?.state() &&
        !document.querySelector(".spin"),
      "UI unavailable",
    );
    const probe = window.__dioptasNavigationProbe,
      config = window.__dioptasNavigationConfig;
    const originalClear = CanvasRenderingContext2D.prototype.clearRect,
      originalArc = CanvasRenderingContext2D.prototype.arc,
      originalStroke = CanvasRenderingContext2D.prototype.stroke;
    CanvasRenderingContext2D.prototype.clearRect = function (...args) {
      this.__peakCount = 0;
      return originalClear.apply(this, args);
    };
    CanvasRenderingContext2D.prototype.arc = function (...args) {
      if (
        this.canvas.dataset.testid === "detector-canvas" &&
        ["#ff8c00", "#ff0000"].includes(this.fillStyle)
      )
        this.__peakCount = (this.__peakCount || 0) + 1;
      return originalArc.apply(this, args);
    };
    CanvasRenderingContext2D.prototype.stroke = function (...args) {
      const result = originalStroke.apply(this, args);
      const m = active;
      if (
        m?.responseAt &&
        !m.drawnAt &&
        this.canvas.dataset.testid === "detector-canvas" &&
        m.expectedCount > 0 &&
        m.expectedCount === this.__peakCount
      ) {
        m.drawnAt = performance.now();
        requestAnimationFrame(() => {
          m.nextFrameAt = performance.now();
          requestAnimationFrame(() => {
            m.presentedBy = performance.now();
          });
        });
      }
      return result;
    };
    window.__dioptasNavigationTrace = (e) => {
      if (!active) return;
      active.events.push(e);
      if (e.stage === "command-start" && e.action === active.action)
        active.commandAt = e.at;
      if (e.stage === "command-response" && e.action === active.action)
        active.bridgeResponseAt = e.at;
      if (e.stage === "command-applied" && e.action === active.action) {
        active.responseAt = e.at;
        active.expectedCount = probe
          .state()
          .calibration.picks.reduce((n, g) => n + g.points.length, 0);
      }
    };
    const ready = async () => {
      await wait(() => !document.querySelector(".spin"), "Still busy");
      await frames();
    };
    const call = async (action, payload = {}) => {
      await probe.run(action, payload);
      await ready();
      if (document.querySelector("[role=dialog]"))
        throw Error("Unexpected dialog after " + action);
    };
    const rows = [];
    const finish = async (kind) => {
      await wait(() => active?.presentedBy, "No final marker frame");
      const m = active;
      active = null;
      const s = probe.state();
      rows.push({
        kind,
        eventToDrawMs: m.drawnAt - m.start,
        commandMs: m.bridgeResponseAt - m.commandAt,
        responseToDrawMs: m.drawnAt - m.bridgeResponseAt,
        nextFrameMs: m.nextFrameAt - m.start,
        presentedByMs: m.presentedBy - m.start,
        events: m.events,
        science: {
          picks: s.calibration.picks,
          geometry: s.geometry,
          rms: s.calibration.rmsDegrees,
        },
      });
      await ready();
    };
    const pick = async (x, y, ring, kind) => {
      document.querySelector('[aria-label="Current calibrant ring"]').click();
      await wait(
        () => document.querySelector("[role=listbox]"),
        "Ring menu absent",
      );
      document.querySelector(`[role=option][data-ring="${ring}"]`).click();
      await ready();
      const c = document.querySelector("[data-testid=detector-canvas]"),
        d = c.dataset,
        b = c.getBoundingClientRect();
      const cx =
          b.x +
          +d.plotLeft +
          ((x - +d.viewXMin) / (+d.viewXMax - +d.viewXMin)) * +d.plotWidth,
        cy =
          b.y +
          +d.plotTop +
          ((+d.viewYMax - y) / (+d.viewYMax - +d.viewYMin)) * +d.plotHeight;
      // Synthetic native-webview input uses the real React handlers; pointer
      // capture itself requires an OS pointer, which this isolated probe avoids.
      c.setPointerCapture = () => {};
      c.dispatchEvent(
        new PointerEvent("pointerdown", {
          bubbles: true,
          pointerId: 1,
          pointerType: "mouse",
          clientX: cx,
          clientY: cy,
          button: 0,
          buttons: 1,
        }),
      );
      active = { action: "pick_peak", start: performance.now(), events: [] };
      c.dispatchEvent(
        new PointerEvent("pointerup", {
          bubbles: true,
          pointerId: 1,
          pointerType: "mouse",
          clientX: cx,
          clientY: cy,
          button: 0,
          buttons: 0,
        }),
      );
      await finish(kind);
    };
    const seeds = [
      [637, 564, 1],
      [671, 511, 2],
      [668, 703, 3],
      [350.5, 592.8, 1],
      [554.3, 367.9, 1],
    ];
    for (const fixture of ["CeO2", "LaB6"]) {
      if (fixture === "CeO2") await call("example");
      else {
        await call("open_image", {
          path: config.root + "/dioptas/tests/data/LaB6_40keV_MarCCD.tif",
          reset_calibration: true,
        });
        await call("calibration_setup", {
          calibrant: "LaB6",
          wavelength: 0.31,
          distance: 200,
          pixel_x: 79,
          pixel_y: 79,
        });
      }
      await call("workflow_settings", { autoIncrement: false });
      const points =
        fixture === "CeO2"
          ? seeds
          : [
              [1129.4, 1179.6, 1],
              [1119.8, 1268.5, 2],
            ];
      for (let i = 0; i < 8; i++)
        await pick(
          ...points[i % points.length],
          fixture + (i === 0 ? "-cold" : "-warm"),
        );
    }
    for (const automatic of [false, true])
      for (const rings of automatic ? [4, 15] : [4])
        for (let i = 0; i < 3; i++) {
          await call("example");
          await call("workflow_settings", { autoIncrement: false });
          for (const p of seeds) await pick(...p, "setup");
          await call("workflow_settings", {
            automaticRefinement: automatic,
            numberOfRings: rings,
          });
          const tab =
            document.querySelector(
              '[role=tab][aria-label="Step 3: Calibrate"]',
            ) ??
            [...document.querySelectorAll("[role=tab]")].find((x) =>
              x.textContent.includes("Fit"),
            );
          if (!tab) throw Error("Fit tab missing");
          tab.click();
          await ready();
          const button = [...document.querySelectorAll("button")].find(
            (b) => b.textContent.trim() === "Calibrate",
          );
          if (!button) throw Error("Calibrate button missing");
          active = {
            action: "calibrate",
            start: performance.now(),
            events: [],
          };
          button.click();
          await finish(automatic ? "automatic-" + rings : "manual-fit");
          // Calibrate switches to validation; return to Image for next seed set.
          const imageTab = document.querySelector(
            '[role=tab][aria-label="Step 1: Image"]',
          );
          if (imageTab) {
            imageTab.click();
            await ready();
          }
        }
    await invoke("native_smoke_report", {
      report: {
        ok: true,
        kind: "calibration-latency",
        label: config.label,
        visibility: document.visibilityState,
        focused: document.hasFocus(),
        scope:
          "Actual Tauri WKWebView and binary Rust IPC; synthetic DOM activation through real React handlers to final canvas strokes and frame opportunities; physical scanout unmeasured",
        rows: rows.filter((r) => r.kind !== "setup"),
      },
    });
  } catch (error) {
    await invoke("native_smoke_report", {
      report: { ok: false, error: String(error), active },
    });
  }
})();
