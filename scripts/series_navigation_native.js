// Runs only in the explicit --navigation-benchmark native test window, with
// --series-navigation or --all-views. Native setup and real plot selections;
// no scientific/IPC substitute.
window.__dioptasSeriesNavigation = async ({
  config,
  call,
  configure,
  step,
  wait,
  paint,
  delay,
  invoke,
}) => {
  const series = () => window.__dioptasNavigationProbe.series();
  const button = (label) => {
    const element = document.querySelector(`[aria-label="${label}"]`);
    if (!element || element.disabled)
      throw Error(`Unavailable control: ${label}`);
    return element;
  };
  const mode = async (label) => {
    button(label).click();
    await paint();
  };
  const pointer = (canvas, x, y) => {
    // Synthetic PointerEvents have no OS pointer to capture. All gesture and
    // scientific selection handlers still execute unchanged.
    canvas.setPointerCapture = canvas.releasePointerCapture = () => {};
    for (const type of ["pointerdown", "pointerup"])
      canvas.dispatchEvent(
        new PointerEvent(type, {
          bubbles: true,
          pointerId: 71,
          button: 0,
          buttons: type === "pointerdown" ? 1 : 0,
          clientX: x,
          clientY: y,
        }),
      );
  };
  const batchClick = (index) => {
    const c = document.querySelector('[data-testid="batch-heatmap"]');
    if (!c) throw Error("Docked Batch overview missing");
    const b = c.getBoundingClientRect(),
      d = c.dataset;
    pointer(
      c,
      b.x + Number(d.plotLeft) + Number(d.plotWidth) / 2,
      b.y +
        Number(d.plotTop) +
        Number(d.plotHeight) *
          (1 -
            (index + 0.5 - Number(d.viewYMin)) /
              (Number(d.viewYMax) - Number(d.viewYMin))),
    );
  };
  const mapClick = (index) => {
    const map = series().map,
      c = document.querySelector(
        '[data-testid="scan-map"] [data-testid="detector-canvas"]',
      );
    const row = map.indices.findIndex((values) => values.includes(index)),
      column = map.indices[row]?.indexOf(index);
    if (!c || row < 0 || column < 0) throw Error(`Map cell ${index} missing`);
    const b = c.getBoundingClientRect(),
      [rows, columns] = map.dimension;
    const scale = Math.min(b.width / columns, b.height / rows);
    pointer(
      c,
      b.x + (b.width - columns * scale) / 2 + (column + 0.5) * scale,
      b.y + (b.height - rows * scale) / 2 + (row + 0.5) * scale,
    );
  };
  const capture = async (name, window = "main") => {
    await invoke("native_smoke_report", {
      report: { stage: "diagnostic", capture: name, window },
    });
    await delay(800);
  };
  const childMessages = [];
  const handler = window.__TAURI_INTERNALS__.transformCallback((event) =>
    childMessages.push(event.payload),
  );
  const subscription = await invoke("plugin:event|listen", {
    event: "navigation-benchmark-child-result",
    target: { kind: "Any" },
    handler,
  });
  let childId = 0;
  const child = async (command, index) => {
    const id = ++childId;
    await invoke("plugin:event|emit", {
      event: "navigation-benchmark-child-step",
      payload: { command, index, id },
    });
    const get = (stage) =>
      childMessages.find(
        (message) => message.id === id && message.stage === stage,
      );
    const complete = async () => {
      await wait(
        () => get("complete") || get("error"),
        "Floating Batch selection did not render",
      );
      const result = get("complete") ?? get("error");
      if (
        result.error ||
        (command === "select" && !result.startFocused) ||
        result.visibility !== "visible"
      )
        throw Error(
          result.error ?? "Floating Batch is not focused and visible",
        );
      return result;
    };
    if (command !== "select") return complete();
    await wait(
      () => get("started") || get("error"),
      "Floating Batch click did not start",
    );
    if (get("error")) throw Error(get("error").error);
    return { ...get("started"), complete };
  };
  try {
    const sources = [
      {
        name: "tiff",
        image: `${config.root}/tests/data/image_001.tif`,
        calibration: `${config.root}/tests/data/LaB6_40keV_MarCCD.poni`,
        paths: ["001", "002"].map(
          (i) => `${config.root}/tests/data/image_${i}.tif`,
        ),
        count: 2,
      },
      ...(config.eiger
        ? [
            {
              name: "eiger",
              image: config.eiger,
              calibration: config.eiger.replace(/\.h5$/, ".poni"),
              paths: [config.eiger],
              count: 14,
            },
          ]
        : []),
    ];
    for (const source of sources) {
      localStorage.setItem("dioptas-batch:docked", "true");
      await configure(
        source.image,
        source.calibration,
        source.name === "eiger" || config.allViews,
      );
      await call("batch_load", {
        paths: source.paths,
        start: 1,
        stop: source.count,
      });
      await wait(
        () =>
          document.querySelector('[data-testid="batch-heatmap"]') &&
          document
            .querySelector(".batch-series-panel")
            ?.getAttribute("aria-busy") === "false",
        "Batch dock not ready",
      );
      await paint();
      const choose = (kind, index, group) =>
        step(`${source.name}-${kind}-${group}`, 0, false, {
          action: kind.startsWith("batch") ? "batch_select" : "map_select",
          index,
          selected: () =>
            kind.startsWith("batch")
              ? series().batch.selected === index
              : series().map.selected === index,
          click: () =>
            kind.startsWith("batch") ? batchClick(index) : mapClick(index),
        });
      const samples = async (kind) => {
        if (source.name === "eiger")
          for (let index = 2; index < source.count; index++)
            await choose(kind, index, "new-frame");
        const selected = kind.startsWith("batch")
          ? series().batch.selected
          : series().map.selected;
        if (selected !== 0) await choose(kind, 0, "warmup");
        await choose(kind, 1, "warmup");
        for (let i = 0; i < 12; i++) await choose(kind, i % 2, "cached");
      };
      await samples("batch-docked");
      await capture(`${source.name}-batch-docked`);
      const readyCount = childMessages.filter(
        (message) => message.stage === "ready",
      ).length;
      button("Detach batch").click();
      await wait(
        () =>
          childMessages.filter((message) => message.stage === "ready").length >
          readyCount,
        "Floating Batch benchmark did not connect",
      );
      await child("prepare");
      // The child remains beside the main display so both webviews can paint.
      const targets = [
        ...(source.name === "eiger"
          ? Array.from({ length: 12 }, (_, i) => ({
              index: i + 2,
              group: "new-frame",
            }))
          : []),
        ...Array.from({ length: 14 }, (_, i) => ({
          index: i % 2,
          group: i < 2 ? "warmup" : "cached",
        })),
      ];
      for (const { index, group } of targets) {
        let completion;
        await step(`${source.name}-batch-floating-${group}`, 0, false, {
          action: "batch_select",
          index,
          detached: true,
          selected: () => series().batch.selected === index,
          click: async () => {
            const started = await child("select", index);
            completion = started.complete;
            return started;
          },
          complete: () => completion(),
        });
      }
      await capture(`${source.name}-batch-floating`, "batch-window");
      await child("dock");
      await wait(
        () => document.querySelector('[data-testid="batch-heatmap"]'),
        "Batch did not dock",
      );
      await invoke("plugin:window|set_focus", { label: "main" });
      await paint();
      button("Hide batch view").click();
      const saved = `${config.output}/${source.name}-navigation-batch.h5`;
      await call("integration_save_batch", { path: saved });
      await call("map_batch", { path: saved });
      await call("map_grid", { rows: 1, columns: source.count });
      for (const reintegrate of [true, false]) {
        await mode("Integration");
        localStorage.setItem(
          "dioptas-map:reintegrate-selected",
          JSON.stringify(reintegrate),
        );
        await mode("Map");
        document.querySelector("#map-tab-Image")?.click();
        await paint();
        await wait(
          () =>
            document.querySelector(
              '[aria-label="Map detector image"] [data-testid="detector-canvas"]',
            ),
          "Map detector view not visible",
        );
        await samples(reintegrate ? "map-reintegrated" : "map-stored");
        await capture(
          `${source.name}-map-${reintegrate ? "reintegrated" : "stored"}`,
        );
      }
      await mode("Integration");
    }
  } finally {
    await invoke("plugin:event|unlisten", {
      event: "navigation-benchmark-child-result",
      eventId: subscription,
    });
  }
};
