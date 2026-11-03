// Injected only by an explicitly launched --smoke native window.
(async () => {
  if (window.__dioptasNativeSmokeRunning) return;
  window.__dioptasNativeSmokeRunning = true;
  const call = window.__dioptasNativeCall;
  // Capture only in this test window, before the compositor discards a GPU frame.
  const frames = new WeakMap();
  const drawArrays = WebGL2RenderingContext.prototype.drawArrays;
  WebGL2RenderingContext.prototype.drawArrays = function (...args) {
    const result = drawArrays.apply(this, args);
    if (/^(detector|cake)-gpu$/.test(this.canvas.dataset.testid ?? "")) {
      const frame = frames.get(this.canvas) ?? document.createElement("canvas");
      frame.width = this.canvas.width;
      frame.height = this.canvas.height;
      frame.getContext("2d").drawImage(this.canvas, 0, 0);
      frames.set(this.canvas, frame);
    }
    return result;
  };
  const delay = (ms = 60) => new Promise((r) => setTimeout(r, ms));
  const check = (condition, message) => {
    if (!condition) throw Error(message);
  };
  const wait = async (predicate, message) => {
    for (let i = 0; i < 1000; i++) {
      if (predicate()) return;
      const error = document.querySelector('[role="alert"]');
      if (error) throw Error(error.textContent);
      await delay();
    }
    throw Error(message);
  };
  const ready = () =>
    wait(
      () => !document.querySelector('.spin, .mask-view[aria-busy="true"]'),
      "Processing did not finish",
    );
  const click = (label) => {
    const button = [...document.querySelectorAll("button")].find(
      (b) =>
        b.getAttribute("aria-label") === label ||
        b.textContent.trim() === label,
    );
    check(button && !button.disabled, `Missing or disabled button: ${label}`);
    button.click();
  };
  const input = (label, value) => {
    const element = document.querySelector(`input[aria-label="${label}"]`);
    check(element, `Missing input: ${label}`);
    Object.getOwnPropertyDescriptor(
      HTMLInputElement.prototype,
      "value",
    ).set.call(element, value);
    element.dispatchEvent(new Event("input", { bubbles: true }));
  };
  try {
    await wait(
      () => document.querySelector('[data-testid="detector-canvas"]'),
      "The native detector did not mount",
    );
    await ready();
    const host = await call("__host__");
    check(
      host.ok && host.transport === "stdio" && !host.qtApplication,
      "Wrong processing host",
    );
    check(
      host.tcpListeners === 0,
      "The native host or processing child opened a TCP listener",
    );
    await wait(
      () =>
        document.querySelector('[data-testid="detector-canvas"]')?.dataset
          .renderer === "webgl2",
      "Native detector did not use WebGL 2",
    );
    const initial = await call("state");
    check(
      initial.ok && !initial.state.calibrated,
      "The example must start uncalibrated",
    );
    check(
      initial.image.step === 1 &&
        initial.image.width === initial.image.fullWidth,
      "Detector resolution was reduced",
    );
    const expectedTitle = `${initial.state.imageName} — Dioptas`;
    await wait(
      () => document.title === expectedTitle,
      "Image document title did not update",
    );
    const nativeTitle = await window.__TAURI_INTERNALS__.invoke(
      "plugin:window|title",
      { label: "main" },
    );
    check(
      nativeTitle === expectedTitle,
      "Native title does not show the image filename",
    );
    check(
      document.querySelector(".setup-image-filename")?.textContent ===
        initial.state.imageName,
      "Filename missing below Open image",
    );
    // Picking and its ring control remain available on Image, before visiting Peaks.
    await ready();
    const ringStrip = document.querySelector(".calibration-ring-controls");
    const tabs = document.querySelector(".calibration-workflow-tabs");
    check(
      ringStrip &&
        tabs &&
        ringStrip.getBoundingClientRect().bottom <=
          tabs.getBoundingClientRect().top,
      "Shared ring controls must be above the tabs",
    );
    check(
      ![...document.querySelectorAll(".calibration-task-footer button")].some(
        (button) =>
          /Back|Next:|Apply detector settings/.test(button.textContent),
      ),
      "Wizard actions remain in the footer",
    );
    const pixelWidth = document.querySelector(
      '[aria-label="Pixel width in micrometres"]',
    );
    input(
      "Pixel width in micrometres",
      String(initial.state.calibration.pixelX + 1),
    );
    pixelWidth.dispatchEvent(
      new KeyboardEvent("keydown", { key: "Enter", bubbles: true }),
    );
    await delay();
    await ready();
    check(
      Math.abs(
        (await call("state")).state.calibration.pixelX -
          initial.state.calibration.pixelX -
          1,
      ) < 1e-9,
      "Enter did not apply detector pixels automatically",
    );
    input(
      "Pixel width in micrometres",
      String(initial.state.calibration.pixelX),
    );
    pixelWidth.focus();
    pixelWidth.blur();
    await delay();
    await ready();
    check(
      Math.abs(
        (await call("state")).state.calibration.pixelX -
          initial.state.calibration.pixelX,
      ) < 1e-9,
      "Leaving the detector field did not apply its value",
    );
    await wait(
      () => document.querySelector('[aria-label="Current calibrant ring"]'),
      "Persistent ring picker is missing",
    );
    await delay();
    const canvas = document.querySelector('[data-testid="detector-canvas"]');
    // Synthetic pointer events cannot acquire native pointer capture. Real
    // pointer capture/drag behavior is separately covered by Playwright.
    canvas.setPointerCapture = canvas.releasePointerCapture = () => {};
    const seeds = [
      [637, 564, 1],
      [671, 511, 2],
      [668, 703, 3],
      [350.5, 592.8, 1],
      [554.3, 367.9, 1],
    ];
    for (const [x, y, ring] of seeds) {
      click("Current calibrant ring");
      await delay();
      const option = document.querySelector(
        `.calibration-ring-options [data-ring="${ring}"]`,
      );
      check(option, `Missing ring ${ring}`);
      option.click();
      await delay();
      const box = canvas.getBoundingClientRect();
      const view = canvas.dataset;
      const clientX =
        box.x +
        +view.plotLeft +
        ((x - +view.viewXMin) / (+view.viewXMax - +view.viewXMin)) *
          +view.plotWidth;
      const clientY =
        box.y +
        +view.plotTop +
        ((+view.viewYMax - y) / (+view.viewYMax - +view.viewYMin)) *
          +view.plotHeight;
      for (const type of ["pointerdown", "pointerup"])
        canvas.dispatchEvent(
          new PointerEvent(type, {
            bubbles: true,
            pointerId: 1,
            button: 0,
            buttons: type === "pointerdown" ? 1 : 0,
            clientX,
            clientY,
          }),
        );
      await delay();
      await ready();
    }
    const picked = await call("state");
    check(
      picked.state.calibration.picks.length === seeds.length,
      "Native image picking lost peak groups",
    );
    const peakPath =
      initial.state.imagePath.split("/dioptas/tests/data/")[0] +
      "/desktop/artifacts/native-calibration-peaks.json";
    const savedPeaks = await call("save_peaks", { path: peakPath });
    check(savedPeaks.ok, savedPeaks.error || "Native peaks save failed");
    check((await call("clear_peaks")).ok, "Native peaks clear failed");
    const loadedPeaks = await call("load_peaks", { path: peakPath });
    check(
      loadedPeaks.ok &&
        JSON.stringify(loadedPeaks.state.calibration.picks) ===
          JSON.stringify(picked.state.calibration.picks),
      loadedPeaks.error || "Native peaks round trip changed the picked groups",
    );
    const undonePeaks = await call("undo_calibration");
    check(
      undonePeaks.ok && undonePeaks.state.calibration.picks.length === 0,
      "Undo did not restore the table before loading peaks",
    );
    const redonePeaks = await call("redo_calibration");
    check(
      redonePeaks.ok &&
        redonePeaks.state.calibration.picks.length === seeds.length,
      "Redo did not restore the loaded peaks",
    );
    click("Step 3: Calibrate");
    await delay();
    const fitControls = document.querySelector(".calibration-fit-controls");
    check(fitControls, "Fit controls are missing");
    const originalFitHeight = fitControls.style.maxHeight;
    const footer = document.querySelector(".calibration-task-footer");
    const footerTop = footer.getBoundingClientRect().top;
    fitControls.style.maxHeight = "300px";
    await delay();
    const fitScrollbar = {
      overflow: fitControls.scrollHeight - fitControls.clientHeight,
      width: fitControls.offsetWidth - fitControls.clientWidth,
    };
    check(
      fitScrollbar.overflow > 0 && fitScrollbar.width > 0,
      "Overflowing Fit controls need a visible scrollbar before interaction",
    );
    const lastFitControl = [
      ...fitControls.querySelectorAll("input,select,button"),
    ].at(-1);
    lastFitControl.scrollIntoView({ block: "nearest" });
    await delay();
    check(fitControls.scrollTop > 0, "Lower Fit controls are unreachable");
    check(
      footer.getBoundingClientRect().top === footerTop,
      "Scrolling Fit moved the calibration action",
    );
    fitControls.scrollTop = 0;
    fitControls.style.maxHeight = originalFitHeight;
    const automatic = document.querySelector(
      'input[aria-label="Automatic refinement"]',
    );
    check(automatic, "Automatic refinement control is missing");
    if (automatic.checked) automatic.click();
    await delay();
    await ready();
    click("Calibrate");
    await delay();
    await ready();
    const fitted = await call("state");
    check(
      fitted.ok && fitted.state.calibrated,
      "Native calibration did not complete",
    );
    check(
      Math.abs(fitted.state.geometry.dist - 0.20865) < 0.002,
      "Unexpected fitted detector distance",
    );
    check(
      document.querySelector('[data-testid="cake-canvas"]'),
      "Validation cake is missing",
    );
    await wait(
      () =>
        document.querySelector('[data-testid="cake-canvas"]')?.dataset
          .renderer === "webgl2",
      "Native cake did not use WebGL 2",
    );
    for (const [label, id] of [
      ["Pattern", "pattern"],
      ["Cake", "cake"],
    ]) {
      const canvas = document.querySelector(`[data-testid="${id}-canvas"]`);
      check(
        canvas.dataset.zoomMode === "rectangle",
        `${label} must default to rectangle zoom`,
      );
      const box = canvas.getBoundingClientRect();
      for (const mode of ["rectangle", "X-range"]) {
        const button = document.querySelector(
          `button[aria-label="${label} ${mode} zoom"]`,
        );
        check(
          button && !button.textContent.trim(),
          `${label} zoom controls must be icon-only`,
        );
        const bounds = button.getBoundingClientRect();
        check(
          bounds.right <= box.left + +canvas.dataset.plotLeft &&
            bounds.top >=
              box.top + +canvas.dataset.plotTop + +canvas.dataset.plotHeight,
          `${label} zoom buttons must sit outside the axes in the lower-left corner`,
        );
      }
      click(`${label} X-range zoom`);
      await delay();
      check(
        canvas.dataset.zoomMode === "horizontal",
        `${label} X-range selector did not apply`,
      );
      click(`${label} rectangle zoom`);
      await delay();
    }
    const event = new WheelEvent("wheel", {
      bubbles: true,
      cancelable: true,
      deltaY: -120,
      clientX: 300,
      clientY: 300,
    });
    const wheelPrevented =
      !canvas.dispatchEvent(event) && event.defaultPrevented;
    check(wheelPrevented, "Wheel event escaped to the workspace");
    check(
      document.querySelectorAll(".intensity-histogram").length === 2,
      "Both images need histograms",
    );
    click("Integration");
    await delay();
    const imageBox = document
      .querySelector(".detector-panel")
      .getBoundingClientRect();
    const controlsBox = document
      .querySelector(".sidebar")
      .getBoundingClientRect();
    const patternBox = document
      .querySelector(".pattern-panel")
      .getBoundingClientRect();
    check(
      imageBox.right <= controlsBox.left &&
        controlsBox.bottom <= patternBox.top,
      "Native Integration must use the Qt image-left / controls-over-pattern layout",
    );
    check(
      imageBox.height > controlsBox.height + patternBox.height - 50,
      "Native Integration image must fill the left column",
    );
    click("Settings");
    await delay();
    document
      .querySelector(
        '#settings-workspace [role="tab"][id="settings-tab-integration"]',
      )
      .click();
    await delay();
    const automaticBinning = document.querySelector(
      'input[aria-label="Automatic radial binning"]',
    );
    check(automaticBinning, "Automatic radial binning control is missing");
    if (automaticBinning.checked) automaticBinning.click();
    await delay();
    input("Radial bins", "600");
    input("Cake azimuth bins", "90");
    await delay();
    click("Apply integration options");
    await delay();
    await ready();
    const integrated = await call("state");
    check(
      integrated.state.bins === 600 && integrated.cake.height === 90,
      "Native integration options were not applied",
    );
    click("Close settings");
    await delay();
    click("Overlay");
    await delay();
    click("As Overlay");
    await delay();
    await ready();
    check(
      document.querySelector('[data-testid="pattern-canvas"]').dataset
        .curveCount === "1",
      "Native overlay did not render",
    );
    check(
      document.querySelector('.qt-overlay-table tr[aria-selected="true"]'),
      "Overlay table must select the added row",
    );
    click("As Overlay");
    await delay();
    await ready();
    const overlayUids = (await call("state")).state.integration.overlays.map(
      (o) => o.uid,
    );
    click("Move overlay up");
    await delay();
    await ready();
    check(
      (await call("state")).state.integration.overlays[0].uid ===
        overlayUids[1],
      "Overlay reordering failed",
    );
    const backgroundToggle = () =>
      document
        .querySelector(".qt-overlay-parameters button[aria-pressed]")
        .click();
    backgroundToggle();
    await delay();
    await ready();
    check(
      (await call("state")).state.integration.overlays[0].background,
      "Selected overlay did not become background",
    );
    backgroundToggle();
    await delay();
    await ready();
    click("Waterfall");
    await delay();
    await ready();
    check(
      (await call("state")).state.integration.overlays[0].offset === -200,
      "Qt waterfall ordering differs",
    );
    click("Reset");
    await delay();
    await ready();
    click("Delete selected overlay");
    await delay();
    await ready();
    check(
      (await call("state")).state.integration.overlays.length === 1,
      "Selected overlay deletion failed",
    );
    const sourceRoot = initial.state.imagePath.split("/dioptas/tests/data/")[0];
    // Native IPC is immutable. Check the toolbar control, then verify image
    // writing through the real native/Python path using explicit test filenames.
    // The browser smoke exercises the button's 2048-pixel export renderer.
    const imageExports = [];
    for (const source of ["image", "cake"]) {
      if (
        document.querySelector(".integration-layout").dataset
          .integrationDisplay !== source
      )
        click(source === "image" ? "Image" : "Cake");
      await delay();
      const saveButton = document.querySelector(
        ".integration-image-tools button",
      );
      check(
        saveButton?.getAttribute("aria-label") === "Save image" &&
          !saveButton.disabled,
        "Save image must be the first enabled toolbar action",
      );
      const canvas = document.querySelector(
        `[data-testid="${source === "cake" ? "cake" : "detector"}-canvas"]`,
      );
      const composite = document.createElement("canvas");
      composite.width = canvas.width;
      composite.height = canvas.height;
      const context = composite.getContext("2d");
      const gpuCanvas = canvas.previousElementSibling;
      if (canvas.dataset.renderer === "webgl2") {
        check(frames.has(gpuCanvas), "GPU image was not captured");
        context.drawImage(frames.get(gpuCanvas), 0, 0);
      }
      context.drawImage(canvas, 0, 0);
      const path = sourceRoot + `/desktop/artifacts/native-saved-${source}.png`;
      const saved = await call("integration_save_image", {
        path,
        source,
        png_data: composite.toDataURL("image/png").split(",")[1],
      });
      check(
        saved.ok && saved.savedPath === path,
        saved.error || "Native image export failed",
      );
      imageExports.push(path);
    }
    click("Image");
    await delay();
    const savedPattern = await call("integration_save_pattern", {
      path: sourceRoot + "/desktop/artifacts/native-integration.xy",
    });
    check(savedPattern.ok, savedPattern.error);
    const phase = await call("integration_phase", {
      operation: "load",
      path: sourceRoot + "/dioptas/tests/data/jcpds/au_version3.jcpds",
    });
    check(
      phase.ok && phase.pattern.phaseLines.length > 0,
      phase.error || "Native phase reference failed",
    );
    click("Pattern unit 2θ");
    await delay();
    await ready();
    check(
      +document.querySelector('[data-testid="pattern-canvas"]').dataset
        .referenceCount > 0,
      "Native phase lines did not render",
    );
    check(
      document.querySelectorAll(".intensity-histogram").length === 2,
      "Integration histograms are not independent",
    );
    const phaseControls = await window.__dioptasPhaseNativeSmoke({
      call,
      click,
      ready,
      delay,
      check,
      root: sourceRoot,
    });
    const maskWorkflow = await window.__dioptasMaskNativeSmoke({
      call,
      click,
      input,
      ready,
      delay,
      check,
    });
    WebGL2RenderingContext.prototype.drawArrays = drawArrays;
    const binaryTransfer = await window.__dioptasBinaryNativeSmoke({
      call,
      click,
      ready,
      delay,
      check,
      root: initial.state.imagePath.slice(
        0,
        initial.state.imagePath.lastIndexOf("/dioptas/tests/data/"),
      ),
    });
    let hotReloadVerified = false;
    if (location.hostname === "127.0.0.1") {
      const token = {};
      window.__dioptasTauriReloadToken = token;
      await import("/src/__dioptas_live_check_tauri.css?import");
      const value = () =>
        getComputedStyle(document.documentElement)
          .getPropertyValue("--dioptas-tauri-hmr")
          .trim();
      await wait(() => value() === "before", "The live CSS probe did not load");
      await window.__TAURI_INTERNALS__.invoke("native_smoke_report", {
        report: { stage: "hmr" },
      });
      await wait(
        () => value() === "after",
        "The running Tauri window did not apply the CSS edit",
      );
      hotReloadVerified = window.__dioptasTauriReloadToken === token;
      check(hotReloadVerified, "Live CSS changes reloaded the document");
    }
    await window.__TAURI_INTERNALS__.invoke("native_smoke_report", {
      report: {
        ok: true,
        host: "tauri",
        transport: host.transport,
        processingPid: host.pid,
        qtApplication: host.qtApplication,
        tcpListeners: host.tcpListeners,
        fullResolution: initial.image.step === 1,
        pickedGroups: seeds.length,
        peakFileRoundTrip: true,
        fitScrollbar,
        fittedDistanceMm: fitted.state.geometry.dist * 1000,
        wheelPrevented,
        validationImages: 2,
        rasterRenderer: "webgl2",
        plotZoomSelectors: true,
        qtIntegrationLayout: true,
        integrationBins: integrated.state.bins,
        integrationCakeBins: integrated.cake.height,
        integrationOverlay: true,
        integrationPhaseLines: phase.pattern.phaseLines.length,
        phaseControls,
        integrationPatternSaved: savedPattern.savedPath,
        integrationImagesSaved: imageExports,
        hotReloadVerified,
        maskWorkflow,
        binaryTransfer,
      },
    });
  } catch (error) {
    await window.__TAURI_INTERNALS__.invoke("native_smoke_report", {
      report: { ok: false, error: String(error) },
    });
  }
})();
