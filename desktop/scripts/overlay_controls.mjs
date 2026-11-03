import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { createInterface } from "node:readline";
import { mkdir, writeFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import path from "node:path";
import { chromium, webkit } from "playwright";
import { setInterfaceTextSize } from "./plot_navigation.mjs";

const root = fileURLToPath(new URL("../../", import.meta.url));
const artifacts = path.join(root, "desktop/artifacts");
await mkdir(artifacts, { recursive: true });
const host = spawn(
  path.join(root, ".venv/bin/python"),
  ["-u", "desktop/scripts/bridge_host.py"],
  { cwd: root, stdio: ["pipe", "pipe", "pipe"] },
);
const pending = new Map();
let nextId = 0;
let logs = "";
host.stderr.on("data", (data) => (logs += data));
createInterface({ input: host.stdout }).on("line", (line) => {
  const message = JSON.parse(line);
  pending.get(message.id)?.(message.result);
  pending.delete(message.id);
});
const invoke = async (action, payload = {}) => {
  const result = await new Promise((resolve) => {
    const id = ++nextId;
    pending.set(id, resolve);
    host.stdin.write(JSON.stringify({ id, action, payload }) + "\n");
  });
  assert.ok(result.ok, result.error);
  return result;
};
const engine = process.argv.includes("--webkit") ? webkit : chromium;
const browser = await engine.launch({ headless: true });
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
const errors = [];
page.on("pageerror", (e) => errors.push(e.message));
await page.exposeFunction("__dioptasInvoke", invoke);
await page.addInitScript(() => {
  window.__overlayStrokes = [];
  window.__overlayPixels = [];
  window.__overlayPending = 0;
  window.__rasterDraws = 0;
  const canvasWidth = Object.getOwnPropertyDescriptor(
    HTMLCanvasElement.prototype,
    "width",
  );
  Object.defineProperty(HTMLCanvasElement.prototype, "width", {
    ...canvasWidth,
    set(value) {
      canvasWidth.set.call(this, value);
      if (["detector-canvas", "cake-canvas"].includes(this.dataset.testid))
        window.__rasterDraws++;
      if (this.dataset.testid === "pattern-canvas") {
        window.__overlayStrokes = [];
        window.__overlayPixels = [];
      }
    },
  });
  const stroke = CanvasRenderingContext2D.prototype.stroke;
  CanvasRenderingContext2D.prototype.stroke = function (...args) {
    if (this.canvas.dataset.testid === "pattern-canvas") {
      window.__overlayStrokes.push({
        color: this.strokeStyle,
        width: this.lineWidth,
      });
      if (window.__overlayStrokes.length > 512) window.__overlayStrokes.shift();
    }
    return stroke.apply(this, args);
  };
  const fill = CanvasRenderingContext2D.prototype.fillRect;
  CanvasRenderingContext2D.prototype.fillRect = function (...args) {
    if (
      this.canvas.dataset.testid === "pattern-canvas" &&
      args[2] === 2 &&
      args[3] === 2 &&
      window.__overlayPixels.at(-1)?.color !== this.fillStyle
    )
      window.__overlayPixels.push({
        color: this.fillStyle,
        width: args[2],
        height: args[3],
      });
    return fill.apply(this, args);
  };

  window.pywebview = {
    api: {
      invoke: async (command, payload) => {
        window.__overlayPending++;
        try {
          return await window.__dioptasInvoke(command, payload);
        } finally {
          window.__overlayPending--;
        }
      },
    },
  };
});
const ready = async () => {
  await page.waitForFunction(
    () => !document.querySelector(".spin") && !window.__overlayPending,
  );
  assert.deepEqual(await page.getByRole("alert").allTextContents(), []);
};
const click = async (name) => {
  await (name === "As Bkg" ? page.locator(".qt-overlay-parameters") : page)
    .getByRole("button", { name, exact: true })
    .click();
  await ready();
};
const edit = async (label, value) => {
  const field = page.getByLabel(label, { exact: true });
  await field.fill(String(value));
  await field.press("Enter");
  await ready();
};
const state = async () => (await invoke("state")).state.integration;
const clearOverlays = async () => {
  await click("Clear overlays");
  await page
    .getByRole("dialog", { name: "Clear all overlays?" })
    .getByRole("button", { name: "Clear all", exact: true })
    .click();
  await ready();
};
try {
  await invoke("integration_overlay", {
    operation: "load",
    paths: [path.join(root, "dioptas/tests/data/pattern_001.xy")],
  });
  await page.goto("file://" + path.join(root, "dioptas/desktop/ui/index.html"));
  await ready();
  await click("Integration");
  assert.equal(
    await page.getByTestId("pattern-canvas").getAttribute("data-curve-count"),
    "1",
    "Overlay-only plotting does not require a calibration or current pattern",
  );
  assert.deepEqual((await invoke("state")).pattern.x, []);
  await page.getByRole("tab", { name: "Overlay", exact: true }).click();
  await click("Toggle all overlays");
  assert.ok(
    Number.isFinite(
      Number(
        await page
          .getByTestId("pattern-canvas")
          .getAttribute("data-view-x-min"),
      ),
    ),
  );
  await click("Clear overlays");
  const clearDialog = page.getByRole("dialog", { name: "Clear all overlays?" });
  assert.equal(
    (await state()).overlays.length,
    1,
    "Opening confirmation preserves overlays",
  );
  assert.equal(
    await clearDialog
      .getByRole("button", { name: "Cancel", exact: true })
      .evaluate((el) => el === document.activeElement),
    true,
  );
  await page.screenshot({
    path: path.join(artifacts, `overlay-${engine.name()}-clear-confirm.png`),
  });
  await page.keyboard.press("Escape");
  assert.equal(await clearDialog.count(), 0);
  await click("Clear overlays");
  await clearDialog
    .getByRole("button", { name: "Cancel", exact: true })
    .click();
  assert.equal((await state()).overlays.length, 1);
  await click("Clear overlays");
  await page.mouse.click(20, 20);
  assert.equal(
    await clearDialog.count(),
    0,
    "Outside click dismisses confirmation",
  );
  assert.equal((await state()).overlays.length, 1);
  await clearOverlays();
  await invoke("example");
  await invoke("open_calibration", {
    path: path.join(root, "dioptas/tests/data/CeO2_Pilatus1M.poni"),
  });
  for (const name of ["overlay-one.xy", "overlay-two.xy"])
    await invoke("integration_save_pattern", {
      path: path.join(artifacts, name),
    });
  await page.goto("file://" + path.join(root, "dioptas/desktop/ui/index.html"));
  await ready();
  await click("Integration");
  await page.getByRole("tab", { name: "Overlay", exact: true }).click();
  await click("Add overlay files");
  assert.equal(
    (await state()).overlays.length,
    2,
    "Native-style multi-file loader adds both chosen files",
  );
  assert.equal(
    await page.locator('.qt-overlay-table tr[aria-selected="true"]').count(),
    1,
  );
  const originalToggle = page.getByRole("checkbox", {
    name: "Original pattern",
    exact: true,
  });
  assert.equal(
    await originalToggle.isChecked(),
    true,
    "Original pattern is visible by default when overlays are loaded",
  );
  const setOriginalVisible = async (visible) => {
    if ((await originalToggle.isChecked()) !== visible)
      await originalToggle.click();
    await ready();
    assert.equal(await originalToggle.isChecked(), visible);
  };
  const name = page.getByLabel("Overlay 2 name", { exact: true });
  await name.dblclick();
  await name.fill("Second reference");
  await name.press("Enter");
  await ready();
  assert.equal((await state()).overlays[1].name, "Second reference");
  assert.ok(
    (
      await page.getByLabel("Pattern legend", { exact: true }).innerText()
    ).includes("Second reference"),
  );
  const legend = page.getByLabel("Pattern legend", { exact: true });
  const legendBox = await legend.boundingBox();
  await page.mouse.move(legendBox.x + legendBox.width / 2, legendBox.y + 10);
  await page.mouse.down();
  await page.mouse.move(
    legendBox.x + legendBox.width / 2 - 50,
    legendBox.y + 30,
  );
  await page.mouse.up();
  assert.ok(
    Math.abs((await legend.boundingBox()).x - legendBox.x + 50) < 2,
    "Pattern legend drags like Qt",
  );
  const beforeSelection = await invoke("state");
  const colors = beforeSelection.state.integration.overlays.map((o) =>
    o.color.toLowerCase(),
  );
  for (const row of [0, 1]) {
    await page.evaluate(() => {
      window.__overlayStrokes = [];
    });
    await page.getByLabel(`Overlay ${row + 1} name`, { exact: true }).click();
    await page.waitForFunction(
      (color) =>
        window.__overlayStrokes.some(
          (s) => s.color === color && Math.abs(s.width - 2.4) < 0.01,
        ),
      colors[row],
    );
    const widths = await page.evaluate(
      (colors) =>
        window.__overlayStrokes.filter((s) => colors.includes(s.color)),
      colors,
    );
    assert.equal(
      widths.at(-1).color,
      colors[row],
      "Selected overlay draws last",
    );
    assert.ok(Math.abs(widths.at(-1).width - 2.4) < 0.01);
    assert.ok(
      widths.some(
        (s) => s.color === colors[1 - row] && Math.abs(s.width - 1.2) < 0.01,
      ),
      "Unselected curve retains its normal width",
    );
  }
  assert.equal(
    (await invoke("state")).state.revision,
    beforeSelection.state.revision,
    "Selection changes presentation without scientific commands",
  );
  const originalRow = page.locator(".qt-overlay-original-row");
  await page.evaluate(() => {
    window.__overlayStrokes = [];
  });
  await originalRow.click();
  await page.waitForFunction(() =>
    window.__overlayStrokes.some(
      (s) => s.color === "#ffffff" && Math.abs(s.width - 2.4) < 0.01,
    ),
  );
  for (const action of [
    "Delete selected overlay",
    "Move overlay up",
    "Move overlay down",
  ])
    assert.equal(
      await page
        .getByRole("button", { name: action, exact: true })
        .isDisabled(),
      true,
    );
  assert.equal(
    await page
      .locator(".qt-overlay-parameters")
      .getByRole("button", { name: "As Bkg", exact: true })
      .isDisabled(),
    true,
  );
  assert.equal(
    await page
      .getByLabel("Original pattern scale", { exact: true })
      .textContent(),
    "1",
  );
  assert.equal(
    await page
      .getByLabel("Original pattern offset", { exact: true })
      .textContent(),
    "0",
  );
  assert.equal(
    await originalRow.locator('input[type="number"]').count(),
    0,
    "Original scale/offset are read-only",
  );
  const originalColor = page.getByLabel("Original pattern color", {
    exact: true,
  });
  const setOriginalColor = async (color) => {
    await originalColor.evaluate((input, color) => {
      Object.getOwnPropertyDescriptor(
        HTMLInputElement.prototype,
        "value",
      ).set.call(input, color);
      input.dispatchEvent(new Event("input", { bubbles: true }));
      input.dispatchEvent(new Event("change", { bubbles: true }));
    }, color);
    await ready();
    await page.waitForFunction(
      (color) =>
        window.__overlayStrokes.some(
          (s) => s.color === color && Math.abs(s.width - 2.4) < 0.01,
        ),
      color,
    );
  };
  const beforeOriginalColor = await invoke("state");
  await setOriginalColor("#e9c46a");
  assert.equal(await originalColor.inputValue(), "#e9c46a");
  assert.equal(
    await page
      .getByLabel("Pattern legend", { exact: true })
      .getByTitle(beforeOriginalColor.state.integration.patternName, {
        exact: true,
      })
      .evaluate((el) => getComputedStyle(el).color),
    "rgb(233, 196, 106)",
  );
  assert.equal((await state()).originalPatternColor, "#e9c46a");
  await click("Undo");
  assert.equal(
    await originalColor.inputValue(),
    "#ffffff",
    "Original color follows shared Undo",
  );
  await click("Redo");
  assert.equal(
    await originalColor.inputValue(),
    "#e9c46a",
    "Original color follows shared Redo",
  );
  await page.getByRole("tab", { name: "Pattern", exact: true }).click();
  await page.getByRole("tab", { name: "Overlay", exact: true }).click();
  assert.equal(await originalColor.inputValue(), "#e9c46a");
  // Watch complete command cycles: controls must not disable/re-enable or
  // detector/cake canvases clear when only overlay presentation changes.
  await page.mouse.move(20, 20);
  await page.waitForTimeout(200);
  const rasterDraws = await page.evaluate(() => {
    window.__overlayDisabledChanges = [];
    window.__overlayObserver = new MutationObserver((records) => {
      for (const r of records)
        if (r.target.matches(".qt-overlay-controls input"))
          window.__overlayDisabledChanges.push(
            r.target.getAttribute("aria-label"),
          );
    });
    window.__overlayObserver.observe(document.body, {
      subtree: true,
      attributes: true,
      attributeFilter: ["disabled"],
    });
    return window.__rasterDraws;
  });
  const oldColors = (await state()).overlays.map((o) => o.color);
  await click("Color overlays by scale");
  const colorScales = page.getByRole("dialog", { name: "Overlay color scale" });
  await page.screenshot({
    path: path.join(artifacts, `overlay-${engine.name()}-color-scales.png`),
  });
  await colorScales
    .getByRole("button", { name: /Apply viridis to overlays/i })
    .click();
  await ready();
  const scaledColors = (await state()).overlays.map((o) => o.color);
  assert.notDeepEqual(scaledColors, oldColors);
  assert.equal(new Set(scaledColors).size, 2);
  assert.equal(
    await originalColor.inputValue(),
    "#e9c46a",
    "Color scale excludes the Original row",
  );
  await click("Undo");
  assert.deepEqual(
    (await state()).overlays.map((o) => o.color),
    oldColors,
    "One Undo restores every overlay color",
  );
  await click("Redo");
  assert.deepEqual(
    (await state()).overlays.map((o) => o.color),
    scaledColors,
  );
  await click("Undo");
  await originalRow.click();
  await setOriginalColor("#f6a953");
  await click("Undo");
  assert.equal(await originalColor.inputValue(), "#e9c46a");
  await click("Redo");
  assert.equal(await originalColor.inputValue(), "#f6a953");
  await click("Undo");
  await setOriginalVisible(false);
  await click("Undo");
  assert.equal(
    await originalToggle.isChecked(),
    true,
    "Undo restores Original visibility",
  );
  await click("Redo");
  assert.equal(
    await originalToggle.isChecked(),
    false,
    "Redo hides Original again",
  );
  assert.equal(
    await page
      .getByTestId("pattern-canvas")
      .getAttribute("data-original-visible"),
    "false",
  );
  await click("Undo");
  for (const scale of [1.5, 1.8, 2]) await edit("Overlay 1 scale", scale);
  await click("Undo");
  assert.equal(
    (await state()).overlays[0].scale,
    1,
    "One Undo restores the initial scale before consecutive edits",
  );
  await click("Redo");
  assert.equal(
    (await state()).overlays[0].scale,
    2,
    "One Redo restores the final scale",
  );
  await click("Undo");
  for (const offset of [-25, -75, -125]) await edit("Overlay 1 offset", offset);
  await click("Undo");
  assert.equal(
    (await state()).overlays[0].offset,
    0,
    "Offset changes form their own Undo group",
  );
  assert.ok(
    await page
      .locator(".qt-overlay-table-scroll tr")
      .first()
      .evaluate((row) => row.getBoundingClientRect().height <= 26),
    "Compact overlay rows show more patterns without reducing text size",
  );
  const overlayToggle = page.getByLabel("Show overlay 1", { exact: true });
  await overlayToggle.click();
  await ready();
  assert.equal(await overlayToggle.isChecked(), false);
  await click("Undo");
  await page.waitForTimeout(100);
  assert.deepEqual(
    await page.evaluate(() => window.__overlayDisabledChanges),
    [],
    "Overlay edits and Undo/Redo never flash disabled table fields",
  );
  assert.equal(
    await page.evaluate(() => window.__rasterDraws),
    rasterDraws,
    "Overlay colors, scale, visibility and Undo/Redo do not repaint detector/cake",
  );
  await page.evaluate(() => window.__overlayObserver.disconnect());
  await originalRow.click();
  await setOriginalColor("#ffffff");
  await originalRow.focus();
  await originalRow.press("ArrowDown");
  assert.equal(
    await page
      .locator('.qt-overlay-table-scroll tr[aria-selected="true"]')
      .count(),
    1,
  );
  await page
    .locator('.qt-overlay-table-scroll tr[aria-selected="true"]')
    .press("ArrowUp");
  assert.equal(
    await originalRow.getAttribute("aria-selected"),
    "true",
    "Keyboard navigation includes the fixed original row",
  );
  await page.getByLabel("Overlay 2 name", { exact: true }).click();
  await click("Antialias pattern");
  await page.waitForFunction(
    (color) => window.__overlayPixels.some((s) => s.color === color),
    colors[1],
  );
  await click("Antialias pattern");
  await edit("Overlay 2 scale", 1.5);
  await edit("Overlay 2 offset", 12);
  await edit("Scale Step", 0.02);
  await page.getByLabel("Overlay 2 scale", { exact: true }).press("ArrowUp");
  await page.getByLabel("Overlay 2 scale", { exact: true }).press("Tab");
  await ready();
  assert.equal((await state()).overlays[1].scale, 1.52);
  await page.getByLabel("Scale Step", { exact: true }).press("ArrowUp");
  assert.equal(
    await page.getByLabel("Scale Step", { exact: true }).inputValue(),
    "0.05",
    "Qt 1/2/5 step sequence",
  );
  const scaleStepBox = await page
    .getByLabel("Scale Step", { exact: true })
    .boundingBox();
  await page.mouse.click(
    scaleStepBox.x + scaleStepBox.width - 7,
    scaleStepBox.y + scaleStepBox.height * 0.25,
  );
  assert.equal(
    await page.getByLabel("Scale Step", { exact: true }).inputValue(),
    "0.1",
    "Native spin arrow keeps 1/2/5 stepping with the mouse",
  );
  await page.getByLabel("Scale Step", { exact: true }).press("ArrowDown");
  const offsetStep = page.getByLabel("Offset Step", { exact: true });
  await offsetStep.press("ArrowUp");
  assert.equal(await offsetStep.inputValue(), "200");
  await offsetStep.press("ArrowUp");
  assert.equal(await offsetStep.inputValue(), "500");
  await offsetStep.press("ArrowDown");
  assert.equal(await offsetStep.inputValue(), "200");
  await edit("Offset Step", 100);
  const separation = page.getByLabel("Waterfall separation", { exact: true });
  await separation.press("ArrowUp");
  await ready();
  assert.equal((await state()).waterfallSeparation, 200);
  await separation.press("ArrowDown");
  await ready();
  assert.equal((await state()).waterfallSeparation, 100);
  await page.getByLabel("Scale Step", { exact: true }).hover();
  await page.mouse.wheel(0, -100);
  await page.waitForFunction(
    () =>
      document.querySelector('input[aria-label="Scale Step"]').value === "0.1",
  );
  await page.mouse.wheel(0, 100);
  await page.waitForFunction(
    () =>
      document.querySelector('input[aria-label="Scale Step"]').value === "0.05",
  );
  const wheelField = async (label, deltaY) => {
    const prevented = await page
      .getByLabel(label, { exact: true })
      .evaluate((el, deltaY) => {
        const event = new WheelEvent("wheel", {
          deltaY,
          bubbles: true,
          cancelable: true,
        });
        el.dispatchEvent(event);
        return event.defaultPrevented;
      }, deltaY);
    assert.ok(
      prevented,
      "Numeric wheel interaction must not scroll the parameter rail",
    );
    await ready();
  };
  await wheelField("Scale Step", -100);
  assert.equal(
    await page.getByLabel("Scale Step", { exact: true }).inputValue(),
    "0.1",
  );
  await wheelField("Scale Step", 100);
  assert.equal(
    await page.getByLabel("Scale Step", { exact: true }).inputValue(),
    "0.05",
  );
  await wheelField("Offset Step", -100);
  assert.equal(await offsetStep.inputValue(), "200");
  await wheelField("Offset Step", 100);
  assert.equal(await offsetStep.inputValue(), "100");
  await wheelField("Waterfall separation", -100);
  assert.equal((await state()).waterfallSeparation, 200);
  await wheelField("Waterfall separation", 100);
  assert.equal((await state()).waterfallSeparation, 100);
  await wheelField("Overlay 2 scale", -100);
  assert.equal((await state()).overlays[1].scale, 1.57);
  await wheelField("Overlay 2 offset", 100);
  assert.equal((await state()).overlays[1].offset, -88);
  await edit("Waterfall separation", -100);
  await separation.press("ArrowUp");
  await ready();
  assert.equal((await state()).waterfallSeparation, -50);
  await separation.press("ArrowDown");
  await ready();
  assert.equal((await state()).waterfallSeparation, -100);
  await wheelField("Waterfall separation", 100);
  assert.equal((await state()).waterfallSeparation, -200);
  await click("Waterfall");
  assert.deepEqual(
    (await state()).overlays.map((o) => o.offset),
    [400, 200],
    "Negative separation reverses waterfall direction",
  );
  await click("Reset");
  await edit("Waterfall separation", 0.01);
  await separation.press("ArrowDown");
  await ready();
  assert.equal((await state()).waterfallSeparation, 0);
  await separation.press("ArrowDown");
  await ready();
  assert.equal((await state()).waterfallSeparation, -0.01);
  await separation.press("ArrowUp");
  await ready();
  assert.equal((await state()).waterfallSeparation, 0);
  await edit("Waterfall separation", 100);
  const waterfallBox = await page
    .getByRole("button", { name: "Waterfall", exact: true })
    .boundingBox();
  assert.ok(
    waterfallBox.width >= 70 && waterfallBox.height >= 30,
    "Compact Waterfall action remains readable",
  );
  await page.getByRole("tab", { name: "Pattern", exact: true }).click();
  await page.getByRole("tab", { name: "Overlay", exact: true }).click();
  assert.equal(
    await page.getByLabel("Scale Step", { exact: true }).inputValue(),
    "0.05",
    "Step size survives tab navigation",
  );
  const selected = (await state()).overlays[1].uid;
  await click("Mask");
  await click("Integration");
  assert.equal(
    await page
      .getByRole("tab", { name: "Overlay", exact: true })
      .getAttribute("aria-selected"),
    "true",
  );
  assert.equal(
    await page.getByLabel("Scale Step", { exact: true }).inputValue(),
    "0.05",
  );
  await page.evaluate(() => {
    window.__overlayStrokes = [];
  });
  await click("Move overlay up");
  await page.waitForFunction(
    (color) =>
      window.__overlayStrokes.some(
        (s) => s.color === color && Math.abs(s.width - 2.4) < 0.01,
      ),
    colors[1],
  );
  assert.equal((await state()).overlays[0].uid, selected);
  assert.equal(
    await page
      .locator(
        '.qt-overlay-table tr[aria-selected="true"] input[aria-label="Overlay 1 name"]',
      )
      .count(),
    1,
  );
  await page
    .getByLabel("Overlay 1 name", { exact: true })
    .click({ button: "right" });
  await page.getByRole("menuitem", { name: "Match intensity" }).click();
  await ready();
  assert.ok(Math.abs((await state()).overlays[0].scale - 1) < 1e-4);
  assert.equal((await state()).overlays[0].offset, 0);
  await click("Toggle all overlays");
  assert.equal(
    await page.getByTestId("pattern-canvas").getAttribute("data-curve-count"),
    "0",
  );
  await click("Toggle all overlays");
  await click("As Bkg");
  assert.equal((await state()).overlays[0].background, true);
  assert.equal(
    await page
      .locator(".qt-overlay-parameters")
      .getByRole("button", { name: "As Bkg", exact: true })
      .getAttribute("aria-pressed"),
    "true",
  );
  await click("As Bkg");
  assert.equal((await state()).overlays[0].visible, true);
  await edit("Waterfall separation", 200);
  await click("Waterfall");
  assert.deepEqual(
    (await state()).overlays.map((o) => o.offset),
    [-400, -200],
  );
  const visibleSnapshot = await invoke("state");
  const patternCanvas = page.getByTestId("pattern-canvas");
  const withOriginalTop = Number(
    await patternCanvas.getAttribute("data-view-y-max"),
  );
  await page.evaluate(() => {
    window.__overlayStrokes = [];
  });
  await setOriginalVisible(false);
  await page.waitForFunction(
    () =>
      document.querySelector('[data-testid="pattern-canvas"]').dataset
        .originalVisible === "false",
  );
  await page.evaluate(
    () =>
      new Promise((resolve) =>
        requestAnimationFrame(() => requestAnimationFrame(resolve)),
      ),
  );
  assert.equal(
    await page.evaluate(() =>
      window.__overlayStrokes.some(
        (s) => s.color === "#ffffff" && s.width >= 1.39,
      ),
    ),
    false,
    "Hiding the original removes its rendered curve",
  );
  assert.equal(await patternCanvas.getAttribute("data-curve-count"), "2");
  assert.ok(
    !(
      await page.getByLabel("Pattern legend", { exact: true }).innerText()
    ).includes(visibleSnapshot.state.integration.patternName),
    "Hidden original is removed from the legend",
  );
  assert.ok(
    Number(await patternCanvas.getAttribute("data-view-y-max")) <
      withOriginalTop,
    "Automatic axes fit only the visible waterfall overlays",
  );
  const afterHide = await invoke("state");
  assert.equal(afterHide.state.integration.originalPatternVisible, false);
  assert.deepEqual(
    afterHide.pattern.y,
    visibleSnapshot.pattern.y,
    "Visibility does not change numerical pattern data",
  );
  await page.screenshot({
    path: path.join(artifacts, `overlay-${engine.name()}-waterfall-only.png`),
  });
  await page.getByRole("tab", { name: "Pattern", exact: true }).click();
  await page.getByRole("tab", { name: "Overlay", exact: true }).click();
  assert.equal(
    await originalToggle.isChecked(),
    false,
    "Original visibility survives tab navigation",
  );
  await setOriginalVisible(true);
  await page.waitForFunction(
    () =>
      document.querySelector('[data-testid="pattern-canvas"]').dataset
        .originalVisible === "true",
  );
  await click("Pattern auto range");
  const held = await patternCanvas.evaluate((el) => [
    el.dataset.viewXMin,
    el.dataset.viewXMax,
    el.dataset.viewYMin,
    el.dataset.viewYMax,
  ]);
  await setOriginalVisible(false);
  await page.evaluate(
    () =>
      new Promise((resolve) =>
        requestAnimationFrame(() => requestAnimationFrame(resolve)),
      ),
  );
  assert.deepEqual(
    await patternCanvas.evaluate((el) => [
      el.dataset.viewXMin,
      el.dataset.viewXMax,
      el.dataset.viewYMin,
      el.dataset.viewYMax,
    ]),
    held,
    "Manual view limits remain fixed when toggling the original",
  );
  await setOriginalVisible(true);
  await click("Pattern auto range");
  await click("Reset");
  await page.getByLabel("Overlay 1 name", { exact: true }).click();
  await click("Move overlay down");
  assert.equal((await state()).overlays[1].uid, selected);
  await page.screenshot({
    path: path.join(artifacts, `overlay-${engine.name()}-wide.png`),
  });
  const expandedClearHeight = await page
    .locator(".qt-overlay-clear-group")
    .evaluate((el) => el.getBoundingClientRect().height);
  for (const size of ["normal", "large"]) {
    await page.setViewportSize({ width: 1000, height: 668 });
    await setInterfaceTextSize(page, size === "large");
    await page.getByRole("tab", { name: "Overlay", exact: true }).click();
    const divider = page.getByRole("separator", {
      name: "Controls and pattern divider",
    });
    for (let i = 0; i < 20; i++) await divider.press("ArrowUp");
    const alignment = await page.locator(".qt-overlay-table").evaluate((body) =>
      [...body.querySelectorAll("tbody tr")].every((row) => {
        const cell = row.querySelector("td"),
          checkbox = cell.querySelector('input[type="checkbox"]');
        const r = row.getBoundingClientRect(),
          b = checkbox.getBoundingClientRect();
        return Math.abs((b.top + b.bottom) / 2 - (r.top + r.bottom) / 2) < 1;
      }),
    );
    assert.ok(
      alignment,
      "Overlay checkboxes are vertically centered at both text sizes",
    );
    const swatches = await page
      .locator('.qt-overlay-table input[type="color"]')
      .evaluateAll((inputs) =>
        inputs.map((input) => {
          const box = input.getBoundingClientRect();
          return { width: box.width, height: box.height };
        }),
      );
    assert.ok(
      swatches.every((box) => Math.abs(box.width - box.height) < 0.1),
      `Color swatches stay square under the full app stylesheet at ${size} text size: ${JSON.stringify(swatches)}`,
    );
    const actionRail = await page
      .locator(".qt-overlay-actions")
      .evaluate((el) => {
        const bounds = el.getBoundingClientRect();
        return {
          sizes: {
            scrollWidth: el.scrollWidth,
            clientWidth: el.clientWidth,
            scrollHeight: el.scrollHeight,
            clientHeight: el.clientHeight,
            bounds: { top: bounds.top, bottom: bounds.bottom },
            buttons: [...el.querySelectorAll("button")].map((b) => {
              const r = b.getBoundingClientRect();
              return { top: r.top, bottom: r.bottom, height: r.height };
            }),
          },
          fits:
            el.scrollHeight <= el.clientHeight &&
            el.scrollWidth <= el.clientWidth,
          allVisible: [...el.querySelectorAll("button")].every((button) => {
            const b = button.getBoundingClientRect();
            return b.top >= bounds.top && b.bottom <= bounds.bottom;
          }),
        };
      });
    assert.ok(
      actionRail.fits && actionRail.allVisible,
      `All left action buttons fit without scrolling at minimum pane height: ${JSON.stringify(actionRail)}`,
    );
    const pairSpacing = await page
      .locator(".qt-overlay-action-pair")
      .evaluateAll((groups) =>
        groups.map((group) => {
          const [first, second] = group.querySelectorAll("button");
          return (
            second.getBoundingClientRect().top -
            first.getBoundingClientRect().bottom
          );
        }),
      );
    assert.ok(
      pairSpacing.every((gap) => gap >= 3.9),
      "Open/Delete and Up/Down pairs retain their spacing at minimum pane height",
    );
    assert.ok(
      (await page
        .locator(".qt-overlay-clear-group")
        .evaluate((el) => el.getBoundingClientRect().height)) <
        expandedClearHeight,
      "Clear-all/divider spacing absorbs the reduced pane height",
    );
    assert.ok(
      await page
        .locator(".qt-overlay-clear-group hr")
        .evaluateAll((lines) =>
          lines.every(
            (line) =>
              getComputedStyle(line).marginTop === "0px" &&
              getComputedStyle(line).marginBottom === "0px",
          ),
        ),
      "Divider spacing can collapse without fixed margins",
    );
    const pinned = await page
      .locator(".qt-overlay-parameters")
      .evaluate((el) => {
        const button = el.querySelector(".qt-overlay-background-action button");
        const area = el.getBoundingClientRect(),
          rect = button.getBoundingClientRect();
        const scroll = el.querySelector(".qt-overlay-parameter-scroll");
        scroll.scrollTop = 0;
        return {
          inside: rect.top >= area.top && rect.bottom <= area.bottom,
          overflow: scroll.scrollHeight > scroll.clientHeight,
          gutter: scroll.offsetWidth - scroll.clientWidth,
        };
      });
    assert.ok(
      pinned.inside,
      "As Bkg stays visible at the smallest pane height without scrolling",
    );
    assert.ok(
      pinned.overflow && pinned.gutter >= 10,
      "Side options show a persistent scrollbar when they overflow",
    );
    await page
      .getByRole("button", { name: "Reset", exact: true })
      .scrollIntoViewIfNeeded();
    await click("Waterfall");
    assert.deepEqual(
      (await state()).overlays.map((o) => o.offset),
      [-400, -200],
    );
    await click("Reset");
    const buttonSizing = await page
      .locator(".qt-overlay-parameters")
      .evaluate((el) => {
        const background = el.querySelector(
            ".qt-overlay-background-action button",
          ),
          waterfall = el.querySelector(".qt-overlay-waterfall-actions button");
        const b = getComputedStyle(background),
          w = getComputedStyle(waterfall);
        return (
          Math.abs(
            background.getBoundingClientRect().height -
              waterfall.getBoundingClientRect().height,
          ) < 1 && b.padding === w.padding
        );
      });
    assert.ok(buttonSizing, "As Bkg matches Waterfall height and padding");
    const backgroundVisible = await page
      .locator(".qt-overlay-background-action button")
      .evaluate((button) => {
        const bounds = button
            .closest(".qt-overlay-parameters")
            .getBoundingClientRect(),
          rect = button.getBoundingClientRect();
        return rect.top >= bounds.top && rect.bottom <= bounds.bottom;
      });
    assert.ok(
      backgroundVisible,
      "Scrolling to Waterfall/Reset does not move As Bkg out of view",
    );
    const resetBox = await page
      .getByRole("button", { name: "Reset", exact: true })
      .boundingBox();
    const waterBox = await page
      .getByRole("button", { name: "Waterfall", exact: true })
      .boundingBox();
    assert.ok(
      Math.abs(resetBox.y - waterBox.y) < 1 && resetBox.x > waterBox.x,
      "Reset sits beside Waterfall",
    );
    const outside = await page
      .locator(".qt-overlay-controls")
      .evaluate((el) => {
        const box = el.getBoundingClientRect();
        return [
          ...el.querySelectorAll(
            ".qt-overlay-actions button, .qt-overlay-parameters button, .qt-overlay-parameters input",
          ),
        ]
          .filter((control) => {
            const b = control.getBoundingClientRect();
            const scroll = control.closest(
              ".qt-overlay-actions, .qt-overlay-parameters",
            );
            const sb = scroll.getBoundingClientRect();
            return (
              b.left < box.left - 1 ||
              b.right > box.right + 1 ||
              (b.width < (control.type === "checkbox" ? 17 : 20) &&
                !control.closest(".qt-overlay-spin")) ||
              sb.right > box.right + 1
            );
          })
          .map((el) => el.outerHTML);
      });
    assert.deepEqual(
      outside,
      [],
      "Action and parameter rails remain readable at compact sizes",
    );
    const scroller = page.locator(".qt-overlay-table-scroll");
    await scroller.evaluate((el) => {
      el.scrollLeft = el.scrollWidth;
    });
    await page.evaluate(
      () =>
        new Promise((resolve) =>
          requestAnimationFrame(() => requestAnimationFrame(resolve)),
        ),
    );
    const headerAndBody = await page
      .locator(".qt-overlay-table")
      .evaluate((table) => {
        const head = table.querySelector("thead"),
          body = table.querySelector(".qt-overlay-table-scroll");
        const headCell = head.querySelectorAll("th")[2].getBoundingClientRect();
        const bodyCell = body
          .querySelector("tr")
          .querySelectorAll("td")[2]
          .getBoundingClientRect();
        return {
          rects: {
            headLeft: headCell.left,
            headWidth: headCell.width,
            bodyLeft: bodyCell.left,
            bodyWidth: bodyCell.width,
            scrollLeft: body.scrollLeft,
          },
          below:
            body.getBoundingClientRect().top >=
            head.getBoundingClientRect().bottom - 1,
          aligned:
            Math.abs(headCell.left - bodyCell.left) < 1 &&
            Math.abs(headCell.width - bodyCell.width) < 1,
        };
      });
    assert.ok(
      headerAndBody.below && headerAndBody.aligned,
      `Only the items scroll, with the fixed header aligned during horizontal scrolling: ${JSON.stringify(headerAndBody)}`,
    );
    await edit("Overlay 2 offset", 123);
    await page
      .locator(".qt-overlay-parameters")
      .getByRole("button", { name: "As Bkg", exact: true })
      .scrollIntoViewIfNeeded();
    await click("As Bkg");
    await click("As Bkg");
    await page.screenshot({
      path: path.join(
        artifacts,
        `overlay-${engine.name()}-${size}-compact.png`,
      ),
    });
  }
  const originalTopBeforeScroll = await originalRow.evaluate(
    (el) => el.getBoundingClientRect().top,
  );
  for (let i = 0; i < 4; i++) await click("Add overlay files");
  assert.equal((await state()).overlays.length, 10);
  assert.ok(
    await page
      .locator(".qt-overlay-table-scroll")
      .evaluate((el) => el.scrollTop > 0),
    "Newly added overlay scrolls into view",
  );
  const tableOverflow = await page
    .locator(".qt-overlay-table-scroll")
    .evaluate((el) => ({
      overflow: el.scrollHeight > el.clientHeight,
      gutter: el.offsetWidth - el.clientWidth,
    }));
  assert.ok(
    tableOverflow.overflow && tableOverflow.gutter >= 10,
    "Overlay table shows its vertical scrollbar with many rows",
  );
  await page.screenshot({
    path: path.join(artifacts, `overlay-${engine.name()}-scrollbars.png`),
  });
  assert.equal(
    await originalRow.evaluate((el) => el.getBoundingClientRect().top),
    originalTopBeforeScroll,
    "Original row stays pinned while overlay items scroll",
  );
  await click("Delete selected overlay");
  assert.equal((await state()).overlays.length, 9);
  await clearOverlays();
  assert.equal((await state()).overlays.length, 0);
  assert.equal(
    await originalToggle.count(),
    1,
    "Fixed original row remains after clearing all overlays",
  );
  assert.equal(
    await page
      .getByTestId("pattern-canvas")
      .getAttribute("data-original-visible"),
    "true",
    "The original remains visible after clearing all overlays",
  );
  assert.equal(
    await page
      .locator(".qt-overlay-parameters")
      .getByRole("button", { name: "As Bkg", exact: true })
      .isDisabled(),
    true,
  );
  assert.equal(await page.locator(".qt-overlay-table-scroll tr").count(), 0);
  assert.equal(await originalRow.count(), 1);
  await setOriginalVisible(false);
  await page.waitForFunction(
    () =>
      document.querySelector('[data-testid="pattern-canvas"]').dataset
        .originalVisible === "false",
  );
  await setOriginalVisible(true);
  assert.equal(
    (await state()).overlays.length,
    0,
    "Original visibility does not create an overlay model entry",
  );
  assert.deepEqual(errors, []);
  await writeFile(
    path.join(artifacts, `overlay-${engine.name()}.json`),
    JSON.stringify(
      {
        ok: true,
        engine: engine.name(),
        checks: [
          "multiple files",
          "rename",
          "scale and steps",
          "selected-row reordering",
          "match intensity",
          "show/hide all",
          "background toggle",
          "waterfall/reset",
          "delete/clear",
          "compact normal/large text",
        ],
      },
      null,
      2,
    ),
  );
  console.log(`Overlay controls passed (${engine.name()})`);
} catch (e) {
  await page.screenshot({
    path: path.join(artifacts, `overlay-${engine.name()}-failure.png`),
  });
  console.error(logs);
  throw e;
} finally {
  await browser.close();
  host.stdin.end();
}
