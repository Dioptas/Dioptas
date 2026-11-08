import assert from "node:assert/strict";

/** Verify documented shortcuts through the actual React event handlers. File
 * dialogs are cancelled at the chooser boundary; edits use the real models. */
export async function verifyShortcuts({ page, ready, invoke }) {
  const checks = [];
  const button = (name) => page.getByRole("button", { name, exact: true });
  const click = async (name) => {
    await button(name).click();
    await ready();
  };
  const unfocus = () => page.evaluate(() => document.activeElement?.blur());
  for (const mode of ["Calibration", "Mask", "Integration", "Calibration"]) {
    await click(mode);
    await page.evaluate(() =>
      window.dispatchEvent(
        new KeyboardEvent("keydown", { key: "Escape", bubbles: true }),
      ),
    );
    await ready();
  }
  await click("Settings");
  await page.evaluate(() =>
    window.dispatchEvent(
      new KeyboardEvent("keydown", { key: "Escape", bubbles: true }),
    ),
  );
  await ready();
  assert.equal(await page.locator(".settings-workspace:visible").count(), 0);
  checks.push(
    "Window-targeted Escape works in Calibration, Mask, Integration and Settings without assuming an element target",
  );
  await page.evaluate(() => {
    const original = window.__invoke;
    window.__shortcutCalls = [];
    window.__invoke = async (a, p) => {
      window.__shortcutCalls.push({ action: a, payload: p });
      if (["open_image", "save_project", "mask_file"].includes(a))
        return { ok: true, cancelled: true };
      return original(a, p);
    };
  });
  const count = (action) =>
    page.evaluate(
      (a) => window.__shortcutCalls.filter((c) => c.action === a).length,
      action,
    );
  const pressCommand = async (key, action) => {
    await unfocus();
    const before = await count(action);
    await page.keyboard.press(key);
    await ready();
    assert.equal(
      await count(action),
      before + 1,
      `${key} dispatches ${action} exactly once`,
    );
  };
  const pressHistory = async (key) => {
    await unfocus();
    const before = await page.evaluate(
      () =>
        window.__shortcutCalls.filter((c) =>
          /^(undo|redo)_(calibration|mask)$/.test(c.action),
        ).length,
    );
    await page.keyboard.press(key);
    await ready();
    const after = await page.evaluate(
      () =>
        window.__shortcutCalls.filter((c) =>
          /^(undo|redo)_(calibration|mask)$/.test(c.action),
        ).length,
    );
    assert.equal(
      after,
      before + 1,
      `${key} traverses the shared scientific history once`,
    );
  };
  await click("Calibration");
  for (const modifier of ["Control", "Meta"]) {
    await pressCommand(`${modifier}+o`, "open_image");
    await pressCommand(`${modifier}+s`, "save_project");
    await pressHistory(`${modifier}+z`);
    await pressHistory(`${modifier}+Shift+z`);
  }
  await pressHistory("Control+z");
  await pressHistory("Control+y");
  for (
    let remaining = 0;
    (await invoke("state")).state.canRedoMask && remaining < 20;
    remaining++
  )
    await pressHistory("Control+y");
  assert.equal((await invoke("state")).state.canRedoMask, false);
  const disabledRedo = await page.evaluate(
    () =>
      window.__shortcutCalls.filter((c) =>
        /^(undo|redo)_(calibration|mask)$/.test(c.action),
      ).length,
  );
  await page.keyboard.press("Control+y");
  assert.equal(
    await page.evaluate(
      () =>
        window.__shortcutCalls.filter((c) =>
          /^(undo|redo)_(calibration|mask)$/.test(c.action),
        ).length,
    ),
    disabledRedo,
    "Redo with no available history stays disabled for keyboard too",
  );
  checks.push(
    "Ctrl and Cmd: Open, Save project, shared scientific Undo/Redo; Ctrl+Y",
  );
  const picking = page.getByLabel("Pick peaks", { exact: true });
  await picking.uncheck();
  const calibrationTab = page.getByRole("tab", {
    name: "Step 1: Image & setup",
    exact: true,
  });
  await calibrationTab.focus();
  await page.keyboard.press("p");
  assert(
    await picking.isChecked(),
    "P enables picking even when a task tab has focus",
  );
  await picking.uncheck();
  for (const mode of ["Integration", "Map"]) {
    await click(mode);
    await unfocus();
    await page.keyboard.press("p");
    await ready();
    assert.equal(
      await button("Calibration").getAttribute("aria-pressed"),
      "true",
    );
    assert(await picking.isChecked());
    await picking.uncheck();
  }
  await click("Mask");
  await unfocus();
  await page.keyboard.press("p");
  assert.equal(
    await button("Mask").getAttribute("aria-pressed"),
    "true",
    "P is intentionally inactive in Mask",
  );
  checks.push(
    "P switches Integration/Map to Calibration and remains inactive in Mask",
  );

  for (const [key, radio] of [
    ["b", "Mask"],
    ["e", "Unmask"],
  ]) {
    await unfocus();
    await page.keyboard.press(key);
    await ready();
    assert(
      await page.getByRole("radio", { name: radio, exact: true }).isChecked(),
    );
    assert.equal(await button("Point").getAttribute("aria-pressed"), "true");
  }
  const diameter = page.getByLabel("Mask point diameter", { exact: true });
  await unfocus();
  const initial = +(await diameter.inputValue());
  await page.keyboard.press("q");
  assert.equal(+(await diameter.inputValue()), initial + 1);
  await page.keyboard.press("w");
  assert.equal(+(await diameter.inputValue()), initial);
  await page.getByTestId("intensity-colour-bar").focus();
  await page.keyboard.press("Enter");
  const palette = page.getByRole("listbox");
  await palette.waitFor();
  await palette.getByRole("option").first().focus();
  await page.keyboard.press("q");
  await page.keyboard.press("b");
  assert.equal(
    +(await diameter.inputValue()),
    initial,
    "Palette keys cannot edit brush diameter",
  );
  assert(
    await page.getByRole("radio", { name: "Unmask", exact: true }).isChecked(),
    "Palette keys cannot change the active mask tool",
  );
  await page.keyboard.press("Escape");
  await unfocus();

  await page.keyboard.press("v");
  assert.equal(await button("Point").getAttribute("aria-pressed"), "false");
  checks.push(
    "B/E select the actual brush/eraser; Q/W change source-pixel diameter; V navigates",
  );
  await pressCommand("Control+s", "mask_file");
  const beforeMask = (await invoke("state")).state.maskedPixels;
  await click("Invert");
  const editedMask = (await invoke("state")).state.maskedPixels;
  assert.notEqual(editedMask, beforeMask);
  await pressCommand("Control+z", "undo_mask");
  assert.equal((await invoke("state")).state.maskedPixels, beforeMask);
  await pressCommand("Control+Shift+z", "redo_mask");
  assert.equal((await invoke("state")).state.maskedPixels, editedMask);
  await pressCommand("Control+z", "undo_mask");
  checks.push(
    "Mask Ctrl+S uses mask_file; Undo/Redo restore actual scientific mask pixels",
  );
  await click("Polygon");
  const canvas = page.getByTestId("detector-canvas");
  const box = await canvas.boundingBox();
  const point = async (x, y) => {
    await page.mouse.click(box.x + box.width * x, box.y + box.height * y);
  };
  await point(0.35, 0.35);
  await point(0.45, 0.35);
  await point(0.4, 0.45);
  const beforePolygon = await count("mask_edit");
  await canvas.focus();
  await page.keyboard.press("Escape");
  await ready();
  assert.equal(
    await count("mask_edit"),
    beforePolygon,
    "Escape cancels without editing the scientific mask",
  );
  await point(0.35, 0.35);
  await point(0.45, 0.35);
  await point(0.4, 0.45);
  await canvas.focus();
  await page.keyboard.press("Enter");
  await ready();
  assert.equal(
    await count("mask_edit"),
    beforePolygon + 1,
    "Enter commits the polygon",
  );
  await pressCommand("Control+z", "undo_mask");
  checks.push("Polygon Enter commits; Escape cancels without a mask command");
  await click("Integration");
  await pressCommand("Enter", "integrate");
  await page.getByRole("tab", { name: "Image", exact: true }).click();
  const image = page.getByTestId("detector-canvas");
  const range = async (locator) =>
    locator.evaluate((e) => [+e.dataset.viewXMin, +e.dataset.viewXMax]);
  for (const [name, plot] of [
    ["detector", image],
    ["pattern", page.getByTestId("pattern-canvas")],
  ]) {
    await plot.focus();
    await page.keyboard.press("Home");
    const fit = await range(plot);
    await page.keyboard.press("+");
    const zoom = await range(plot);
    assert(zoom[1] - zoom[0] < (fit[1] - fit[0]) * 0.6, `${name}: + zooms`);
    await page.keyboard.press("ArrowRight");
    const pan = await range(plot);
    assert(pan[0] > zoom[0]);
    await page.keyboard.press("-");
    const out = await range(plot);
    assert(out[1] - out[0] > zoom[1] - zoom[0]);
    await page.keyboard.press("f");
    const reset = await range(plot);
    assert(
      Math.abs(reset[0] - fit[0]) < 1e-6 && Math.abs(reset[1] - fit[1]) < 1e-6,
    );
  }
  checks.push(
    "Detector/pattern keyboard +/− zoom, arrows pan, F/Home restore measured view ranges",
  );
  await button("Settings").focus();
  const beforeButton = await count("integrate");
  await page.keyboard.press("Enter");
  await ready();
  assert(
    await page
      .getByRole("region", { name: "Settings", exact: true })
      .isVisible(),
  );
  assert.equal(
    await count("integrate"),
    beforeButton,
    "Enter on a button does not also integrate",
  );
  const callsBefore = await count("undo_mask");
  await page.keyboard.press("Control+z");
  assert.equal(
    await count("undo_mask"),
    callsBefore,
    "Settings does not undo a mask",
  );
  await page.keyboard.press("Escape");
  assert.equal(
    await page.getByRole("region", { name: "Settings", exact: true }).count(),
    0,
  );
  await click("Calibration");
  await calibrationTab.click();
  const input = page.getByLabel("Pixel width in micrometres", { exact: true });
  await input.focus();
  const beforeInput = await count("save_project");
  await page.keyboard.press("Control+s");
  assert.equal(
    await count("save_project"),
    beforeInput,
    "Text editing owns modified keys",
  );
  assert.equal(await picking.isChecked(), false);
  await page.keyboard.press("p");
  assert.equal(
    await picking.isChecked(),
    false,
    "Typing P in an input does not enable picking",
  );
  await click("Settings");
  await page.getByRole("tab", { name: "Keyboard shortcuts", exact: true }).click();
  await page.keyboard.press("b");
  assert.equal(
    await button("Calibration").getAttribute("aria-pressed"),
    "true",
    "Shortcut settings prevent background mode shortcuts",
  );
  await page.keyboard.press("Escape");
  checks.push(
    "Button Enter, field typing, and Settings shortcuts stay in their own context",
  );
  return checks;
}
