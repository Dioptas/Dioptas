// Injected only in the explicit --pattern-benchmark window.
(async () => {
  const invoke = window.__TAURI_INTERNALS__.invoke;
  try {
    for (let i = 0; !window.__patternBenchmark && i < 1000; i++)
      await new Promise((r) => setTimeout(r, 20));
    if (!window.__patternBenchmark)
      throw Error("Pattern benchmark bundle not loaded");
    document.title = "Dioptas · Canvas/WebGL pattern benchmark";
    await invoke("plugin:window|set_title", {
      label: "main",
      value: document.title,
    });
    const call = window.__dioptasNativeCall;
    const initial = await call("state");
    const root = initial.state.imagePath.split("/dioptas/tests/data/")[0];
    const opened = await call("open_calibration", {
      path: root + "/dioptas/tests/data/CeO2_Pilatus1M.poni",
    });
    if (!opened.ok) throw Error(opened.error);
    const real = await call("settings", { bins: 2000 });
    if (!real.ok || !real.pattern?.x.length)
      throw Error(real.error ?? "Measured pattern unavailable");
    const cases = [
      {
        name: "measured-CeO2",
        points: real.pattern.x.length,
        curves: 1,
        pattern: real.pattern,
      },
      { name: "normal", points: 2000, curves: 1 },
      { name: "many-overlays", points: 4000, curves: 20 },
      { name: "dense", points: 100000, curves: 1 },
      { name: "dense-overlays", points: 100000, curves: 8 },
      { name: "million", points: 1000000, curves: 1 },
    ];
    window.__patternBenchmarkProgress = (sample) =>
      invoke("native_smoke_report", {
        report: { stage: "hmr", patternProgress: sample },
      });
    const reports = {};
    // Sequential runs in the same native window, fixed plot size and data.
    for (const backend of ["original", "canvas2d", "webgl2"])
      reports[backend] = await window.__patternBenchmark.run({
        backend,
        cases,
      });
    await invoke("native_smoke_report", {
      report: {
        ok: true,
        kind: "pattern-benchmark",
        source:
          "Measured CeO2 detector integrated with its reference PONI; all other workloads are synthetic stress patterns.",
        reports,
      },
    });
  } catch (error) {
    await invoke("native_smoke_report", {
      report: { ok: false, error: String(error) },
    });
  }
})();
