// Injected only into a disposable --tooltip-smoke native window.
(async () => {
  const invoke = window.__TAURI_INTERNALS__.invoke;
  const delay = () => new Promise((resolve) => setTimeout(resolve, 60));
  const check = (condition, message) => {
    if (!condition) throw Error(message);
  };
  const wait = async (predicate, message) => {
    for (let i = 0; i < 150; i++) {
      if (await predicate()) return;
      await delay();
    }
    throw Error(message);
  };
  const command = (name, label = "main", args = {}) =>
    invoke(`plugin:window|${name}`, { label, ...args });
  const visible = async () => {
    try {
      return await command("is_visible", "calibration-tooltip");
    } catch {
      return false;
    }
  };
  try {
    await wait(() => {
      const tab = document.querySelector(
        '[role="tab"][aria-label="Step 3: Calibrate"]',
      );
      return tab && !tab.disabled;
    }, "Calibration tabs did not mount");
    document
      .querySelector('[role="tab"][aria-label="Step 3: Calibrate"]')
      .click();
    await wait(
      () => document.querySelector(".calibration-help-button"),
      "Refinement help did not mount",
    );
    const monitor = await command("current_monitor");
    const scale = monitor.scaleFactor;
    const work = monitor.workArea;
    await command("set_size", "main", {
      value: { Logical: { width: 1000, height: 700 } },
    });
    await command("set_position", "main", {
      value: {
        Physical: {
          x: work.position.x + Math.round(20 * scale),
          y: work.position.y + Math.round(20 * scale),
        },
      },
    });
    await command("set_focus");
    await delay();
    const helps = [...document.querySelectorAll(".calibration-help-button")];
    for (const help of helps) {
      help.scrollIntoView({ block: "center" });
      help.focus();
      await wait(visible, "Native help did not become visible");
      const popup = await command("outer_position", "calibration-tooltip");
      const popupSize = await command("outer_size", "calibration-tooltip");
      const origin = await command("inner_position");
      const size = await command("inner_size");
      const anchor = help.getBoundingClientRect();
      check(
        popup.x >= origin.x + anchor.right * scale + 6 * scale,
        "Help did not prefer the upper right",
      );
      check(
        popup.x + popupSize.width > origin.x + size.width,
        "Help remained clipped to the application window",
      );
      check(
        popup.y + popupSize.height <= origin.y + anchor.top * scale,
        "Help did not sit above its button",
      );
      check(await command("is_focused"), "Help stole keyboard focus");
      window.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape" }));
      help.blur();
      await wait(
        async () => !(await visible()),
        "Escape did not dismiss native help",
      );
    }
    const size = await command("outer_size");
    await command("set_position", "main", {
      value: {
        Physical: {
          x:
            work.position.x +
            work.size.width -
            size.width -
            Math.round(20 * scale),
          y: work.position.y + Math.round(20 * scale),
        },
      },
    });
    await delay();
    const help = helps[0];
    help.scrollIntoView({ block: "center" });
    help.focus();
    await wait(visible, "Screen-edge help did not become visible");
    const popup = await command("outer_position", "calibration-tooltip");
    const popupSize = await command("outer_size", "calibration-tooltip");
    const origin = await command("inner_position");
    const anchor = help.getBoundingClientRect();
    check(
      popup.x + popupSize.width <= origin.x + anchor.left * scale,
      "Help did not fall back to the upper left at the screen edge",
    );
    check(
      popup.x >= work.position.x &&
        popup.y >= work.position.y &&
        popup.x + popupSize.width <= work.position.x + work.size.width,
      "Help exceeded the screen work area",
    );
    help.blur();
    await wait(
      async () => !(await visible()),
      "Blur did not dismiss native help",
    );
    // Dismiss while the native show request is still queued.
    help.focus();
    window.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape" }));
    help.blur();
    for (let i = 0; i < 8; i++) await delay();
    check(!(await visible()), "A stale show request reopened dismissed help");
    await invoke("native_smoke_report", {
      report: {
        ok: true,
        nativeTooltip: true,
        helpButtons: helps.length,
        outsideApp: true,
        screenFallback: true,
        focusPreserved: true,
      },
    });
  } catch (error) {
    await invoke("native_smoke_report", {
      report: { ok: false, error: String(error) },
    });
  }
})();
