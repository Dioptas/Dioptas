// No scientific bridge is granted to this window, including in this test.
(async () => {
  const invoke = window.__TAURI_INTERNALS__.invoke;
  const delay = (ms = 50) => new Promise((r) => setTimeout(r, ms));
  const check = (v, m) => {
    if (!v) throw Error(m);
  };
  const wait = async (fn) => {
    for (let i = 0; i < 600; i++) {
      if (await fn()) return;
      await delay();
    }
    throw Error("No native detector: " + document.body.innerText);
  };
  let report;
  const round = +(localStorage.getItem("detector-native-round") || 0) + 1;
  localStorage.setItem("detector-native-round", String(round));
  const size = async () => {
    const physical = await invoke("plugin:window|inner_size", {
      label: "detector-window",
    });
    const scale = await invoke("plugin:window|scale_factor", {
      label: "detector-window",
    });
    return { width: physical.width / scale, height: physical.height / scale };
  };
  try {
    await wait(() => document.querySelector('[data-testid="detector-canvas"]'));
    await wait(() =>
      invoke("plugin:window|is_visible", { label: "detector-window" }),
    );
    const initial = {
      ...(await size()),
      position: await invoke("plugin:window|outer_position", {
        label: "detector-window",
      }),
    };
    const first = await invoke("detector_snapshot", { cachedBuffers: [] });
    check(
      first instanceof ArrayBuffer,
      "Detector pixels did not use binary IPC",
    );
    const n = new DataView(first).getUint32(0, true),
      header = JSON.parse(
        new TextDecoder().decode(new Uint8Array(first, 4, n)),
      );
    check(header.buffers.length > 0, "No native pixel buffers");
    const second = await invoke("detector_snapshot", {
      cachedBuffers: header.buffers.map((b) => b.id),
    });
    const n2 = new DataView(second).getUint32(0, true);
    check(second.byteLength === 4 + n2, "Cached pixels were duplicated");
    const canvas = document.querySelector('[data-testid="detector-canvas"]');
    check(
      canvas.dataset.fullWidth === "981" &&
        canvas.dataset.fullHeight === "1043",
      "Detector was downsampled",
    );
    check(
      document.querySelectorAll(".intensity-histogram").length === 1,
      "Histogram missing/duplicated",
    );
    let rejected = false;
    try {
      await invoke("desktop_invoke", { action: "open_image", payload: {} });
    } catch {
      rejected = true;
    }
    check(rejected, "Child bypassed main processing queue");
    if (round === 1) {
      await invoke("plugin:window|set_position", {
        label: "detector-window",
        value: {
          Physical: { x: initial.position.x + 40, y: initial.position.y + 20 },
        },
      });
      await invoke("plugin:window|set_size", {
        label: "detector-window",
        value: { Logical: { width: 680, height: 590 } },
      });
      await delay(150);
      await invoke("plugin:window|minimize", { label: "detector-window" });
    }
    report = {
      ok: true,
      initial,
      placed: {
        ...(await size()),
        position: await invoke("plugin:window|outer_position", {
          label: "detector-window",
        }),
      },
      binarySnapshot: true,
      cachedPixels: true,
      queueRestricted: true,
    };
  } catch (error) {
    report = { ok: false, error: String(error) };
  }
  await invoke("plugin:event|emit_to", {
    target: { kind: "WebviewWindow", label: "main" },
    event: "detector-native-test",
    payload: report,
  });
  if (round === 2 && report.ok) {
    await delay(150);
    await invoke("plugin:window|close", { label: "detector-window" });
  }
})();
