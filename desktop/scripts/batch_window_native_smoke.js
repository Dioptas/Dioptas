(async () => {
  if (window.__batchWindowSmoke) return;
  window.__batchWindowSmoke = true;
  const invoke = window.__TAURI_INTERNALS__.invoke,
    call = window.__dioptasNativeCall;
  const delay = () => new Promise((r) => setTimeout(r, 80));
  const check = (v, m) => {
    if (!v) throw Error(m);
  };
  const wait = async (fn) => {
    for (let i = 0; i < 500; i++) {
      if (await fn()) return;
      await delay();
    }
    throw Error("Batch child timed out");
  };
  const windowSize = async () => {
    const physical = await invoke("plugin:window|inner_size", {
      label: "batch-window",
    });
    const scale = await invoke("plugin:window|scale_factor", {
      label: "batch-window",
    });
    return { width: physical.width / scale, height: physical.height / scale };
  };
  let report;
  try {
    await wait(
      () =>
        document.querySelector('[data-testid="batch-heatmap"]') &&
        !document.querySelector('[aria-label="Selected batch frame"]')
          ?.disabled,
    );
    // PageLoad can finish while Rust is still restoring this hidden window.
    // Inspect native placement only after the restore/show sequence completes.
    await wait(() =>
      invoke("plugin:window|is_visible", { label: "batch-window" }),
    );
    const initial = {
      ...(await windowSize()),
      position: await invoke("plugin:window|outer_position", {
        label: "batch-window",
      }),
    };
    check(
      document.querySelectorAll(".intensity-histogram").length === 1,
      "Batch has duplicated plots",
    );
    let rejected = false;
    try {
      await invoke("desktop_invoke", {
        action: "batch_select",
        payload: { index: 2 },
      });
    } catch {
      rejected = true;
    }
    check(rejected, "Batch bypassed main queue");
    const snapshot = await call("batch_snapshot");
    check(
      snapshot.ok && snapshot.batch.raster.data instanceof ArrayBuffer,
      "Not binary snapshot",
    );
    const target =
      (snapshot.batch.selected + 1) % snapshot.batch.entries.length;
    const canvas = document.querySelector('[data-testid="batch-heatmap"]');
    canvas.setPointerCapture = canvas.releasePointerCapture = () => {};
    await wait(
      () =>
        Number(canvas.dataset.plotHeight) > 0 &&
        Number(canvas.dataset.viewYMax) > target,
    );
    await delay();
    const b = canvas.getBoundingClientRect();
    const yMin = Number(canvas.dataset.viewYMin),
      yMax = Number(canvas.dataset.viewYMax);
    for (const type of ["pointerdown", "pointerup"])
      canvas.dispatchEvent(
        new PointerEvent(type, {
          bubbles: true,
          pointerId: 7,
          button: 0,
          clientX:
            b.x +
            Number(canvas.dataset.plotLeft) +
            Number(canvas.dataset.plotWidth) * 0.5,
          clientY:
            b.y +
            Number(canvas.dataset.plotTop) +
            Number(canvas.dataset.plotHeight) *
              (1 - (target + 0.5 - yMin) / (yMax - yMin)),
        }),
      );
    await wait(
      async () => (await call("batch_snapshot")).batch.selected === target,
    );
    check(
      !document.querySelector('[role="alert"]')?.textContent.trim(),
      "Batch selection failed",
    );
    await invoke("plugin:window|set_size", {
      label: "batch-window",
      value: { Logical: { width: 820, height: 560 } },
    });
    await wait(async () => {
      const size = await windowSize();
      return Math.abs(size.width - 820) < 1 && Math.abs(size.height - 560) < 1;
    });
    await invoke("plugin:window|set_position", {
      label: "batch-window",
      value: { Logical: { x: 100, y: 90 } },
    });
    await delay();
    await delay();
    report = {
      ok: true,
      selected: target,
      initial,
      placed: {
        ...(await windowSize()),
        viewport: { width: innerWidth, height: innerHeight },
        position: await invoke("plugin:window|outer_position", {
          label: "batch-window",
        }),
      },
    };
  } catch (e) {
    report = { ok: false, error: `${e}\n${e.stack ?? ""}` };
  }
  await invoke("plugin:event|emit", {
    event: "batch-window-smoke",
    payload: report,
  });
  if (report.ok)
    document.querySelector('[aria-label="Dock batch below image"]').click();
})();
