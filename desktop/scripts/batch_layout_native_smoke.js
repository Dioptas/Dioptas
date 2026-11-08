// Isolated restart campaign. The runner reuses one disposable app identifier.
(async () => {
  const invoke = window.__TAURI_INTERNALS__.invoke;
  const call = window.__dioptasNativeCall;
  const stage = window.__batchLayoutStage;
  let childReady = false;
  let existingWindowRaised = false;
  let placement = null;
  const bounds = async () => {
    const size = await invoke("plugin:window|inner_size", {
      label: "batch-window",
    });
    const scale = await invoke("plugin:window|scale_factor", {
      label: "batch-window",
    });
    return {
      width: size.width / scale,
      height: size.height / scale,
      position: await invoke("plugin:window|outer_position", {
        label: "batch-window",
      }),
    };
  };
  const events = [];
  const check = (value, message) => {
    if (!value) throw Error(message);
  };
  const wait = async (fn, message) => {
    for (let i = 0; i < 250; i++) {
      if (await fn()) return;
      const alert = document.querySelector('[role="alert"]');
      if (alert?.textContent.trim()) throw Error(alert.textContent);
      await new Promise((resolve) => setTimeout(resolve, 40));
    }
    throw Error(message);
  };
  const button = (label) =>
    [...document.querySelectorAll("button")].find(
      (b) =>
        b.getAttribute("aria-label") === label ||
        b.textContent.trim() === label,
    );
  const click = (label) => {
    const b = button(label);
    check(b && !b.disabled, `Missing ${label}`);
    b.click();
  };
  const divider = (label) =>
    document.querySelector(`[role="separator"][aria-label="${label}"]`);
  const key = (node, k) =>
    node.dispatchEvent(
      new KeyboardEvent("keydown", { key: k, bubbles: true, cancelable: true }),
    );
  const read = (key) => localStorage.getItem(key);
  try {
    const handler = window.__TAURI_INTERNALS__.transformCallback((e) => {
      events.push(e.payload);
      if (e.payload?.type === "ready") childReady = true;
    });
    await invoke("plugin:event|listen", {
      event: "batch-window-main",
      target: { kind: "Any" },
      handler,
    });
    await wait(
      () => button("Open project") && !button("Open project").disabled,
      "Main did not become ready",
    );
    const host = await call("__host__");
    if (stage === "seed") {
      click("Integration");
      await wait(
        () => divider("Image and analysis divider"),
        "No Integration splitters",
      );
      key(divider("Image and analysis divider"), "ArrowRight");
      await new Promise((r) => setTimeout(r, 50));
      key(divider("Image and analysis divider"), "ArrowRight");
      key(divider("Controls and pattern divider"), "ArrowDown");
      await new Promise((r) => setTimeout(r, 50));
      key(divider("Controls and pattern divider"), "ArrowDown");
      click("Batch view…");
      await wait(
        () => childReady && read("dioptas-batch:docked") === "false",
        "Batch did not finish opening",
      );
      await invoke("plugin:window|minimize", { label: "batch-window" });
      await wait(
        () => invoke("plugin:window|is_minimized", { label: "batch-window" }),
        "Batch was not minimized",
      );
      await invoke("plugin:window|set_focus", { label: "main" });
      click("Batch view…");
      await wait(
        async () =>
          !(await invoke("plugin:window|is_minimized", {
            label: "batch-window",
          })) &&
          (await invoke("plugin:window|is_focused", { label: "batch-window" })),
        "Batch button did not restore and focus the existing window",
      );
      const windows = await invoke("plugin:window|get_all_windows");
      check(
        windows.filter((label) => label === "batch-window").length === 1,
        "Batch window duplicated",
      );
      existingWindowRaised = true;
      await invoke("plugin:window|set_size", {
        label: "batch-window",
        value: { Logical: { width: 860, height: 620 } },
      });
      await invoke("plugin:window|set_position", {
        label: "batch-window",
        value: { Logical: { x: 120, y: 100 } },
      });
      await wait(async () => {
        const b = await bounds();
        return b.width === 860 && b.height === 620;
      }, "Batch did not resize");
      await new Promise((r) => setTimeout(r, 100));
      placement = await bounds();

      check(
        read("dioptas-batch:open") === "true" &&
          read("dioptas-batch:docked") === "false",
        "Floating state not saved",
      );
    } else if (stage === "floating") {
      await wait(
        () => childReady,
        "Floating Batch was not restored after quitting",
      );
      check(
        divider("Image and analysis divider").getAttribute("aria-valuenow") ===
          "54",
        "Image split not restored",
      );
      check(
        divider("Controls and pattern divider").getAttribute(
          "aria-valuenow",
        ) === "42",
        "Controls split not restored",
      );
      check(
        read("dioptas-batch:open") === "true",
        "Quitting changed open state",
      );
      await wait(async () => {
        const b = await bounds();
        return b.width === 860 && b.height === 620;
      }, "Batch size was not restored after quitting");
      placement = await bounds();

      // A native close, rather than the Dock/Hide React actions.
      await invoke("close_batch_window");
      await wait(
        () => read("dioptas-batch:open") === "false",
        "Native close was not remembered",
      );
    } else if (stage === "closed") {
      await new Promise((r) => setTimeout(r, 350));
      check(
        !childReady && read("dioptas-batch:open") === "false",
        "Closed Batch reopened",
      );
      click("Integration");
      await wait(() => button("Batch view…"), "Integration did not appear");
      click("Batch view…");
      await wait(() => childReady, "Batch did not reopen");
      await invoke("plugin:event|emit", {
        event: "batch-window-main",
        payload: { type: "dock" },
      });
      await wait(
        () => document.querySelector(".batch-dock"),
        "Batch did not dock",
      );
      for (let i = 0; i < 3; i++) {
        key(divider("Image and batch divider"), "ArrowUp");
        await new Promise((r) => setTimeout(r, 50));
      }
      click("Collapse batch overview");
      await wait(
        () => read("dioptas-batch:collapsed") === "true",
        "Collapse state not saved",
      );
      check(
        read("dioptas-batch:dock-height") === "380",
        "Dock height not saved",
      );
    } else if (stage === "docked") {
      await wait(
        () => document.querySelector(".batch-dock-collapsed"),
        "Dock/collapse state was not restored",
      );
      check(!childReady, "Dock restored as a floating window");
      click("Expand batch overview");
      await wait(
        () => divider("Image and batch divider"),
        "Dock did not expand",
      );
      check(
        divider("Image and batch divider").getAttribute("aria-valuenow") ===
          "380",
        "Dock height not restored",
      );
      check(
        divider("Image and analysis divider").getAttribute("aria-valuenow") ===
          "54",
        "Image split changed",
      );
      check(
        divider("Controls and pattern divider").getAttribute(
          "aria-valuenow",
        ) === "42",
        "Controls split changed",
      );
      click("Hide batch view");
      check(read("dioptas-batch:open") === "false", "Hide was not saved");
      await wait(
        () => !document.querySelector(".batch-dock"),
        "Hide did not finish rendering",
      );
      click("Batch view…");
      await wait(
        () => document.querySelector(".batch-dock"),
        "Batch button did not reopen dock",
      );
      click("Batch view…");
      await wait(
        () => !document.querySelector(".batch-dock"),
        "Batch button did not hide dock",
      );
      check(
        read("dioptas-batch:open") === "false",
        "Button toggle did not save closed state",
      );
      check(
        read("dioptas-batch:docked") === "true",
        "Button toggle lost dock preference",
      );
    }
    await invoke("native_smoke_report", {
      report: {
        ok: true,
        stage,
        processingPid: host.pid,
        childReady,
        existingWindowRaised,
        placement,
        open: read("dioptas-batch:open"),
        docked: read("dioptas-batch:docked"),
      },
    });
  } catch (error) {
    await invoke("native_smoke_report", {
      report: {
        ok: false,
        error: `${error}\n${error.stack ?? ""}`,
        stage,
        events,
        open: read("dioptas-batch:open"),
        docked: read("dioptas-batch:docked"),
        dockVisible: !!document.querySelector(".batch-dock"),
        mode: [
          ...document.querySelectorAll(
            '.mode-navigation button[aria-pressed="true"]',
          ),
        ].map((b) => b.getAttribute("aria-label")),
      },
    });
  }
})();
