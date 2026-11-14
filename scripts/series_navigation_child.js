// Isolated native benchmark only. Selection still uses the real Batch UI,
// event channel, main command queue and binary snapshots.
(async () => {
  const invoke = window.__TAURI_INTERNALS__.invoke;
  const delay = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
  const wait = async (test) => {
    const start = performance.now();
    while (!test()) {
      if (performance.now() - start > 30000)
        throw Error("Floating Batch timed out");
      await delay(5);
    }
  };
  const paint = () =>
    new Promise((resolve) =>
      requestAnimationFrame(() => requestAnimationFrame(resolve)),
    );
  const now = () => performance.timeOrigin + performance.now();
  const emit = (payload) =>
    invoke("plugin:event|emit", {
      event: "navigation-benchmark-child-result",
      payload,
    });
  let selectedRender = null,
    collecting = false,
    presentationAbs = null,
    renderAbs = null,
    drawGeneration = 0;
  window.__dioptasNavigationTrace = (event) => {
    if (collecting && event.stage === "batch-rendered") {
      selectedRender = event.selected;
      renderAbs = now();
      const generation = ++drawGeneration;
      requestAnimationFrame(() =>
        requestAnimationFrame(() => {
          if (collecting && drawGeneration === generation)
            presentationAbs = now();
        }),
      );
    }
  };
  const handler = window.__TAURI_INTERNALS__.transformCallback(
    async (event) => {
      const { command, index, id } = event.payload;
      let startAbs = null;
      let startFocused = null;
      try {
        await wait(
          () =>
            document.querySelector('[data-testid="batch-heatmap"]') &&
            document
              .querySelector(".batch-series-panel")
              ?.getAttribute("aria-busy") === "false",
        );
        if (command === "prepare") {
          await invoke("plugin:window|set_size", {
            label: "batch-window",
            value: { Logical: { width: 600, height: 680 } },
          });
          await invoke("plugin:window|set_position", {
            label: "batch-window",
            value: { Logical: { x: 1080, y: 60 } },
          });
          await invoke("plugin:window|set_focus", { label: "batch-window" });
          await wait(
            () => document.hasFocus() && document.visibilityState === "visible",
          );
        } else if (command === "dock") {
          await emit({
            stage: "complete",
            id,
            focused: document.hasFocus(),
            visibility: document.visibilityState,
          });
          document
            .querySelector('[aria-label="Dock batch below image"]')
            .click();
          return;
        } else if (command === "select") {
          if (!document.hasFocus()) {
            await invoke("plugin:window|set_focus", { label: "batch-window" });
            await wait(() => document.hasFocus());
          }
          const c = document.querySelector('[data-testid="batch-heatmap"]'),
            b = c.getBoundingClientRect(),
            d = c.dataset;
          c.setPointerCapture = c.releasePointerCapture = () => {};
          const x = b.x + Number(d.plotLeft) + Number(d.plotWidth) / 2;
          const y =
            b.y +
            Number(d.plotTop) +
            Number(d.plotHeight) *
              (1 -
                (index + 0.5 - Number(d.viewYMin)) /
                  (Number(d.viewYMax) - Number(d.viewYMin)));
          selectedRender = null;
          presentationAbs = null;
          renderAbs = null;
          collecting = true;
          startAbs = now();
          startFocused = document.hasFocus();
          for (const type of ["pointerdown", "pointerup"])
            c.dispatchEvent(
              new PointerEvent(type, {
                bubbles: true,
                pointerId: 72,
                button: 0,
                buttons: type === "pointerdown" ? 1 : 0,
                clientX: x,
                clientY: y,
              }),
            );
          await emit({ stage: "started", id, startAbs, focused: startFocused });
          await wait(
            () =>
              selectedRender === index &&
              Number(
                document.querySelector(".batch-series-panel")?.dataset
                  .selectedFrame,
              ) === index,
          );
        }
        await paint();
        if (command === "select") await wait(() => presentationAbs != null);
        collecting = false;
        await emit({
          stage: "complete",
          id,
          paintAbs: now(),
          presentationAbs,
          renderAbs,
          startFocused,
          startAbs,
          selected: index,
          focused: document.hasFocus(),
          visibility: document.visibilityState,
          viewport: [innerWidth, innerHeight],
        });
      } catch (error) {
        await emit({ stage: "error", id, error: String(error) });
      }
    },
  );
  await invoke("plugin:event|listen", {
    event: "navigation-benchmark-child-step",
    target: { kind: "Any" },
    handler,
  });
  await emit({ stage: "ready" });
})();
