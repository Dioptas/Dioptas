// One isolated packaged-window check; no OS dialogs or existing previews.
(async () => {
  const call = window.__dioptasNativeCall;
  const check = (condition, message) => {
    if (!condition) throw Error(message);
  };
  const invoke = async (action, payload = {}) => {
    const result = await call(action, payload);
    check(result.ok, `${action}: ${result.error}`);
    return result;
  };
  try {
    for (
      let i = 0;
      i < 400 && !document.querySelector('[data-testid="detector-canvas"]');
      i++
    )
      await new Promise((resolve) => setTimeout(resolve, 50));
    check(
      document.querySelector('[data-testid="detector-canvas"]'),
      "Bundled interface did not load",
    );
    const host = await invoke("__host__");
    check(
      host.runtime === "rust" && host.engine === "dioptrin",
      "Wrong packaged processor",
    );
    const initial = await invoke("state");
    check(
      initial.state.hasImage && !initial.state.calibrated,
      "Example must start raw and uncalibrated",
    );
    check(
      initial.image.width === 981 &&
        initial.image.height === 1043 &&
        initial.image.step === 1,
      "Example pixels were reduced or changed",
    );
    check(
      initial.state.calibration.calibrants.length > 10,
      "Embedded calibrants missing",
    );
    check(
      initial.state.calibration.detectors.length > 100,
      "Embedded detector catalogue missing",
    );
    const image = initial.state.imagePath;
    check(
      image.includes("/examples/"),
      "Example was not loaded from packaged resources",
    );
    await invoke("integration_settings", { bins: 128, cake_bins: 36 });
    await invoke("open_calibration", {
      path: image.replace(/\.tif$/, ".poni"),
    });
    const pattern = await invoke("integrate");
    check(
      pattern.pattern.x.length > 10 && pattern.cake.width > 0,
      "Packaged integration failed",
    );
    const directory = window.__dioptasStandaloneDirectory;
    check(directory, "Missing isolated smoke output directory");
    await invoke("integration_autocreate", { enabled: true });
    const protectedOutput = await call("integrate");
    check(
      !protectedOutput.ok &&
        protectedOutput.error.includes("outside the application"),
      "Automatic output modified the application",
    );
    await invoke("integration_output_directory", { path: directory });
    await invoke("integrate");
    await invoke("integration_autocreate", { enabled: false });
    await invoke("integration_phase", {
      operation: "load",
      path: image.replace(/[^/]+$/, "mo.jcpds"),
    });
    const catalog = await invoke("integration_phase_catalog", {
      query: "gold",
    });
    check(
      catalog.phaseCatalog.length > 0,
      "Embedded material catalogue missing",
    );
    await invoke("configuration", { operation: "duplicate" });
    const project = `${directory}/standalone.dio`;
    await invoke("save_project", { path: project });
    const restored = await invoke("open_project", { path: project });
    check(
      restored.state.configurationCount === 2,
      "Standalone project/configuration round trip failed",
    );
    await invoke("export_pattern", { path: `${directory}/standalone.xy` });
    await window.__TAURI_INTERNALS__.invoke("native_smoke_report", {
      report: {
        ok: true,
        standalone: true,
        runtime: host.runtime,
        engine: host.engine,
        processingPid: host.pid,
        uiLoaded: true,
        fullResolution: [981, 1043],
        patternPoints: pattern.pattern.x.length,
        cake: [pattern.cake.width, pattern.cake.height],
        configurations: restored.state.configurationCount,
        examplePath: image,
        materialCatalog: catalog.phaseCatalog.length,
        protectedResources: true,
      },
    });
  } catch (error) {
    await window.__TAURI_INTERNALS__.invoke("native_smoke_report", {
      report: {
        ok: false,
        standalone: true,
        error: error.stack || String(error),
      },
    });
  }
})();
