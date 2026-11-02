// Injected only by an explicitly launched --smoke native window.
(async () => {
  if (window.__dioptasNativeSmokeRunning) return;
  window.__dioptasNativeSmokeRunning = true;
  const call = window.__dioptasNativeCall;
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
    click("Calibrate detector");
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
    click("Add pattern");
    await delay();
    await ready();
    check(
      document.querySelector('[data-testid="pattern-canvas"]').dataset
        .curveCount === "1",
      "Native overlay did not render",
    );
    const sourceRoot = initial.state.imagePath.split("/dioptas/tests/data/")[0];
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
    const maskWorkflow = await window.__dioptasMaskNativeSmoke({
      call,
      click,
      input,
      ready,
      delay,
      check,
    });
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
        qtIntegrationLayout: true,
        integrationBins: integrated.state.bins,
        integrationCakeBins: integrated.cake.height,
        integrationOverlay: true,
        integrationPhaseLines: phase.pattern.phaseLines.length,
        integrationPatternSaved: savedPattern.savedPath,
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
