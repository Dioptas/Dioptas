import { installRasterProbe } from "./raster_probe.mjs";
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { createInterface } from "node:readline";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import path from "node:path";
import { chromium } from "playwright";
import {
  setInterfaceTextSize,
  verifyPlotNavigation,
  verifyCalibrationNavigation,
} from "./plot_navigation.mjs";

import { verifyDetectorGeometry } from "./detector_geometry.mjs";
import {
  verifyImageControls,
  verifyWheelCapture,
  selectColorMap,
} from "./image_controls.mjs";

const root = fileURLToPath(new URL("../../", import.meta.url));
const artifacts = path.join(root, "desktop/artifacts");
await mkdir(artifacts, { recursive: true });
const host = spawn(
  path.join(root, ".venv/bin/python"),
  ["-u", "desktop/scripts/bridge_host.py"],
  { cwd: root, stdio: ["pipe", "pipe", "pipe"] },
);
let nextId = 0;
const pending = new Map();
const diagnostics = [];
const pixelRequests = [];
const commands = [];
host.stderr.on("data", (chunk) => diagnostics.push(chunk.toString()));
createInterface({ input: host.stdout }).on("line", (line) => {
  try {
    const message = JSON.parse(line);
    const task = pending.get(message.id);
    if (task) {
      clearTimeout(task.timer);
      pending.delete(message.id);
      task.resolve(message.result);
    }
  } catch {
    diagnostics.push(line);
  }
});
host.on("exit", (code) => {
  for (const task of pending.values()) {
    clearTimeout(task.timer);
    task.reject(new Error(`Bridge host exited ${code}`));
  }
  pending.clear();
});
function invoke(action, payload = {}) {
  commands.push(action);
  if (action === "pixel")
    pixelRequests.push({ time: performance.now(), ...payload });
  return new Promise((resolve, reject) => {
    const id = ++nextId;
    const timer = setTimeout(() => {
      pending.delete(id);
      reject(new Error(`Timed out: ${action}`));
    }, 45000);
    pending.set(id, { resolve, reject, timer });
    host.stdin.write(JSON.stringify({ id, action, payload }) + "\n");
  });
}
const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({
  viewport: { width: 1440, height: 1000 },
  deviceScaleFactor: 1,
});
const errors = [];
page.on("pageerror", (e) => errors.push(e.message));
page.on("console", (message) => {
  if (/passive.*listener|Unable to preventDefault/i.test(message.text()))
    errors.push(message.text());
});
await page.exposeFunction("__dioptasInvoke", invoke);
await page.addInitScript(installRasterProbe);
await page.addInitScript(() => {
  window.__colourBuilds = 0;
  const createPixels = CanvasRenderingContext2D.prototype.createImageData;
  CanvasRenderingContext2D.prototype.createImageData = function (...args) {
    if (args[0] === 981 && args[1] === 1043) window.__colourBuilds++;
    return createPixels.apply(this, args);
  };
  const draw = CanvasRenderingContext2D.prototype.drawImage;
  CanvasRenderingContext2D.prototype.drawImage = function (...args) {
    if (this.canvas.dataset.testid === "detector-canvas" && args.length === 5) {
      window.__detectorSource = args[0];
      const matrix = this.getTransform();
      window.__detectorDraw = {
        sx: Math.abs((args[3] * matrix.a) / +this.canvas.dataset.fullWidth),
        sy: Math.abs((args[4] * matrix.d) / +this.canvas.dataset.fullHeight),
        flippedY: matrix.d < 0,
      };
    }
    return draw.apply(this, args);
  };
  window.__detectorLabels = [];
  const text = CanvasRenderingContext2D.prototype.fillText;
  CanvasRenderingContext2D.prototype.fillText = function (...args) {
    if (this.canvas.dataset.testid === "detector-canvas")
      window.__detectorLabels.push(args[0]);
    return text.apply(this, args);
  };
  const ellipse = CanvasRenderingContext2D.prototype.ellipse;
  CanvasRenderingContext2D.prototype.ellipse = function (...args) {
    if (this.canvas.dataset.testid === "detector-canvas") {
      const d = this.canvas.dataset;
      const sx = (+d.viewXMax - +d.viewXMin) / +d.plotWidth;
      const sy = (+d.viewYMax - +d.viewYMin) / +d.plotHeight;
      window.__maskCircle = {
        cx: +d.viewXMin + (args[0] - +d.plotLeft) * sx,
        cy: +d.viewYMax - (args[1] - +d.plotTop) * sy,
        rx: args[2] * sx,
        ry: args[3] * sy,
      };
    }
    return ellipse.apply(this, args);
  };
  window.pywebview = {
    api: {
      invoke: async (command, payload) => {
        const result = await window.__dioptasInvoke(command, payload);
        if (command === "mask_edit" && window.__maskResponseDelay)
          await new Promise((resolve) =>
            setTimeout(resolve, window.__maskResponseDelay),
          );
        return result;
      },
    },
  };
});
const waitReady = async () => {
  await page.waitForFunction(
    () => !document.querySelector('.spin, .mask-view[aria-busy="true"]'),
    {
      timeout: 45000,
    },
  );
  assert.equal(
    await page.getByRole("alert").count(),
    0,
    JSON.stringify(await page.getByRole("alert").allTextContents()),
  );
};

const button = (name) =>
  page.getByRole(name.startsWith("Step ") ? "tab" : "button", {
    name,
    exact: true,
  });
const state = () => invoke("state");
const maskBytes = (result) => Buffer.from(result.mask.data, "base64");
const sourcePixel = (x, y) =>
  page.evaluate(
    ({ x, y }) => {
      const el = document.querySelector('[data-testid="detector-canvas"]');
      if (el.dataset.renderer !== "webgl2")
        return Array.from(
          window.__detectorSource.getContext("2d").getImageData(x, y, 1, 1)
            .data,
        );
      const d = el.dataset,
        frame = window.__detectorPixels;
      const px = Math.floor(
        ((+d.plotLeft +
          ((x + 0.5 - +d.viewXMin) / (+d.viewXMax - +d.viewXMin)) *
            +d.plotWidth) *
          frame.width) /
          el.clientWidth,
      );
      const py = Math.floor(
        ((+d.plotTop +
          ((+d.viewYMax - y - 0.5) / (+d.viewYMax - +d.viewYMin)) *
            +d.plotHeight) *
          frame.height) /
          el.clientHeight,
      );
      const offset = ((frame.height - 1 - py) * frame.width + px) * 4;
      return Array.from(frame.pixels.slice(offset, offset + 4));
    },
    { x, y },
  );
const sourcePosition = (x, y) =>
  page.getByTestId("detector-canvas").evaluate(
    (el, { x, y }) => {
      const b = el.getBoundingClientRect(),
        d = el.dataset;
      return {
        x:
          b.x +
          +d.plotLeft +
          ((x - +d.viewXMin) / (+d.viewXMax - +d.viewXMin)) * +d.plotWidth,
        y:
          b.y +
          +d.plotTop +
          ((+d.viewYMax - y) / (+d.viewYMax - +d.viewYMin)) * +d.plotHeight,
      };
    },
    { x, y },
  );
const clickSource = async (x, y, options = {}) => {
  const target = await sourcePosition(x, y);
  await page.mouse.click(target.x, target.y, options);
};
const dragSource = async (from, to, modifier) => {
  const start = await sourcePosition(...from);
  const end = await sourcePosition(...to);
  if (modifier) await page.keyboard.down(modifier);
  try {
    await page.mouse.move(start.x, start.y);
    await page.mouse.down();
    await page.mouse.move(end.x, end.y, { steps: 8 });
    await page.mouse.up();
  } finally {
    if (modifier) await page.keyboard.up(modifier);
  }
  await page.evaluate(() => new Promise(requestAnimationFrame));
};
const square = async () => {
  await page.waitForTimeout(80);
  const draw = await page.evaluate(() => window.__detectorDraw);
  assert.ok(draw.flippedY && Math.abs(draw.sx / draw.sy - 1) < 1e-7);
};
try {
  await page.goto("file://" + path.join(root, "dioptas/desktop/ui/index.html"));
  await waitReady();
  await button("Explore example").click();
  await waitReady();
  await button("Mask").click();
  await page.getByLabel("Mask detector workspace").waitFor();
  assert.equal(await page.locator(".intensity-histogram").count(), 1);
  await square();
  const originalImage = (await state()).image.data;
  await button("Detector histogram settings").click();
  await page.getByLabel("Image scale", { exact: true }).selectOption("log");
  await page.getByLabel("Maximum intensity", { exact: true }).fill("1000");
  await button("Close detector display settings").click();
  await selectColorMap(page, "Color map", "thermal");
  const detector = page.getByTestId("detector-canvas");
  assert.equal(await detector.getAttribute("data-intensity-scale"), "log");
  assert.equal((await state()).image.data, originalImage);
  await page.evaluate(() => {
    window.__maskResponseDelay = 300;
    window.__drawingDisabledChanges = [];
    window.__drawingObserver = new MutationObserver((changes) => {
      window.__drawingDisabledChanges.push(
        ...changes.map((c) => c.target.outerHTML),
      );
    });
    window.__drawingObserver.observe(document.querySelector(".mask-controls"), {
      attributes: true,
      attributeFilter: ["disabled"],
      subtree: true,
    });
  });
  const colourBuilds = await page.evaluate(() => window.__colourBuilds);
  const beforeShapePixel = await sourcePixel(120, 220);
  await button("Rectangle").click();
  await clickSource(101.2, 201.2);
  await clickSource(161.2, 251.2);
  assert.equal(
    await page.getByLabel("Mask detector workspace").getAttribute("aria-busy"),
    "true",
  );
  assert.equal(await button("Circle").isEnabled(), true);
  assert.equal(await page.locator(".spin").count(), 0);
  await waitReady();
  const drawingChanges = await page.evaluate(() => {
    window.__drawingObserver.disconnect();
    window.__maskResponseDelay = 0;
    return window.__drawingDisabledChanges;
  });
  assert.deepEqual(drawingChanges, []);
  assert.equal(await page.evaluate(() => window.__colourBuilds), colourBuilds);
  let current = await state();
  let bytes = maskBytes(current);
  assert.equal(current.state.maskedPixels, 60 * 50);
  assert.equal(bytes[220 * 981 + 120], 1);
  assert.equal(bytes[120 * 981 + 220], 0);
  const opacity = current.state.transparentMask ? 0.4 : 1;
  assert.deepEqual(
    await sourcePixel(120, 220),
    Array.from(
      new Uint8ClampedArray([
        255 * opacity + beforeShapePixel[0] * (1 - opacity),
        beforeShapePixel[1] * (1 - opacity),
        beforeShapePixel[2] * (1 - opacity),
        255,
      ]),
    ),
  );
  await button("Undo").click();
  await waitReady();
  assert.equal((await state()).state.maskedPixels, 0);
  assert.deepEqual(await sourcePixel(120, 220), beforeShapePixel);
  await button("Redo").click();
  await waitReady();
  assert.equal((await state()).state.maskedPixels, 3000);
  await button("Clear").click();
  await waitReady();
  // Hold responses long enough to finish another shape, then an ordinary
  // edit. All requests must reach the model in order without losing an edit.
  await page.evaluate(() => (window.__maskResponseDelay = 500));
  await clickSource(10.2, 10.2);
  await clickSource(30.2, 30.2);
  await clickSource(50.2, 10.2);
  await clickSource(70.2, 30.2);
  await waitReady();
  assert.equal((await state()).state.maskedPixels, 800);
  await clickSource(90.2, 10.2);
  await clickSource(110.2, 30.2);
  await button("Clear").click();
  await waitReady();
  assert.equal((await state()).state.maskedPixels, 0);
  await page.evaluate(() => (window.__maskResponseDelay = 0));
  await page.keyboard.press("v");
  let box = await page.getByTestId("detector-canvas").boundingBox();
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
  await page.mouse.wheel(0, -250);
  await page.waitForTimeout(100);
  await page.setViewportSize({ width: 1180, height: 820 });
  await square();
  await button("Rectangle").click();
  await clickSource(450.2, 480.2);
  await clickSource(480.2, 520.2);
  await waitReady();
  current = await state();
  bytes = maskBytes(current);
  assert.equal(current.state.maskedPixels, 1200);
  assert.equal(bytes[500 * 981 + 460], 1);
  const zoomBeforeUndo = await detector.getAttribute("data-view-x-min");
  const contrastBeforeUndo = await detector.getAttribute("data-intensity-max");
  await button("Undo").click();
  await waitReady();
  assert.equal(await detector.getAttribute("data-view-x-min"), zoomBeforeUndo);
  assert.equal(
    await detector.getAttribute("data-intensity-max"),
    contrastBeforeUndo,
  );
  await button("Redo").click();
  await waitReady();
  await page.keyboard.press("f");
  await square();
  await button("Circle").click();
  await clickSource(300.2, 400.2);
  const beforeCircle = (await state()).state.maskedPixels;
  for (const [x, y] of [
    [330.2, 440.2],
    [250.2, 400.2],
    [300.2, 450.2],
  ]) {
    const target = await sourcePosition(x, y);
    await page.mouse.move(target.x, target.y);
    await page.waitForFunction(() => window.__maskCircle?.rx > 0);
    await page.waitForTimeout(50);
    const preview = await page.evaluate(() => window.__maskCircle);
    for (const [key, value] of Object.entries({
      cx: 300.2,
      cy: 400.2,
      rx: 50,
      ry: 50,
    }))
      assert.ok(Math.abs(preview[key] - value) < 0.02, JSON.stringify(preview));
    assert.equal((await state()).state.maskedPixels, beforeCircle);
  }
  // Stay clear of integer-pixel boundaries after browser coordinate mapping.
  await clickSource(300.2, 450.4);
  await waitReady();
  assert.ok((await state()).state.maskedPixels > 1200);
  bytes = maskBytes(await state());
  for (const [x, y] of [
    [300, 400],
    [251, 400],
    [349, 400],
    [300, 351],
    [300, 449],
  ])
    assert.equal(bytes[y * 981 + x], 1, `Circle must contain (${x}, ${y})`);
  assert.equal(bytes[440 * 981 + 340], 0);
  await button("Polygon").click();
  await clickSource(200, 300);
  await clickSource(240, 300);
  await clickSource(220, 340);
  const beforePendingPolygon = (await state()).state.maskedPixels;
  await button("Settings").click();
  await page.keyboard.press("Enter");
  await waitReady();
  assert.equal(
    (await state()).state.maskedPixels,
    beforePendingPolygon,
    "Settings must not commit the pending mask polygon",
  );
  await page.keyboard.press("Escape");
  // Enter belongs to a focused button; focus the plot to finish its polygon.
  await page.getByTestId("detector-canvas").focus();
  await page.keyboard.press("Enter");
  await waitReady();
  const polygonCount = (await state()).state.maskedPixels;
  assert.ok(
    polygonCount > beforePendingPolygon,
    "Returning from Settings preserves the pending polygon",
  );
  await clickSource(200, 300);
  await page.keyboard.press("Escape");
  assert.equal((await state()).state.maskedPixels, polygonCount);
  await button("Arc").click();
  await clickSource(100, 100);
  await clickSource(120, 120);
  await clickSource(140, 100);
  await clickSource(120, 127);
  await waitReady();
  assert.ok((await state()).state.maskedPixels > polygonCount);
  await button("Point").click();
  await page.getByLabel("Mask point diameter").fill("20");
  await clickSource(500, 600);
  await waitReady();
  bytes = maskBytes(await state());
  assert.equal(bytes[600 * 981 + 500], 1);
  await page.getByRole("radio", { name: "Unmask", exact: true }).check();
  await clickSource(500, 600);
  await waitReady();
  bytes = maskBytes(await state());
  assert.equal(bytes[600 * 981 + 500], 0);
  await page.getByRole("radio", { name: "Mask", exact: true }).check();
  const beforePointZoom = await state();
  const beforePointRange = await detector.getAttribute("data-view-x-max");
  const strokeCount = commands.filter(
    (command) => command === "mask_stroke",
  ).length;
  await dragSource([430.2, 530.2], [650.2, 750.2]);
  await waitReady();
  assert.notEqual(
    await detector.getAttribute("data-view-x-max"),
    beforePointRange,
  );
  assert.equal(
    (await state()).mask.data,
    beforePointZoom.mask.data,
    "Ordinary Point drag must zoom without modifying the mask",
  );
  assert.equal(
    commands.filter((command) => command === "mask_stroke").length,
    strokeCount,
  );
  const pointZoom = await detector.getAttribute("data-view-x-min");
  await dragSource([510.2, 610.2], [570.2, 650.2], "Shift");
  await waitReady();
  bytes = maskBytes(await state());
  for (const [x, y] of [
    [510, 610],
    [540, 630],
    [570, 650],
  ])
    assert.equal(
      bytes[y * 981 + x],
      1,
      "Shift-drag must paint a continuous stroke",
    );
  assert.equal(await detector.getAttribute("data-view-x-min"), pointZoom);
  await page.getByRole("radio", { name: "Unmask", exact: true }).check();
  await dragSource([510.2, 610.2], [570.2, 650.2], "Shift");
  await waitReady();
  bytes = maskBytes(await state());
  for (const [x, y] of [
    [510, 610],
    [540, 630],
    [570, 650],
  ])
    assert.equal(bytes[y * 981 + x], 0, "Shift-drag must erase in Unmask mode");
  const beforePointPan = (await state()).mask.data;
  await dragSource([510.2, 610.2], [530.2, 630.2], "Control");
  await waitReady();
  assert.notEqual(await detector.getAttribute("data-view-x-min"), pointZoom);
  assert.equal(
    (await state()).mask.data,
    beforePointPan,
    "Ctrl-drag must pan without painting",
  );
  await page.getByRole("radio", { name: "Mask", exact: true }).check();
  await page.keyboard.press("f");
  await square();
  await button("Save Mask").click();
  await waitReady();
  const saved = (await state()).mask.data;
  await button("Clear").click();
  await waitReady();
  await button("Load Mask").click();
  await waitReady();
  assert.equal((await state()).mask.data, saved);
  await button("Add Mask").click();
  await waitReady();
  assert.equal((await state()).mask.data, saved);
  const beforeTransparency = (await state()).state;
  await page.evaluate(() => {
    const controls = document.querySelector(".mask-controls");
    window.__transparencyButtons = [...controls.querySelectorAll("button")];
    window.__transparencyDisabledChanges = [];
    window.__transparencyObserver = new MutationObserver((changes) => {
      window.__transparencyDisabledChanges.push(
        ...changes.map((c) => c.target.outerHTML),
      );
    });
    window.__transparencyObserver.observe(controls, {
      attributes: true,
      attributeFilter: ["disabled"],
      subtree: true,
    });
  });
  const transparency = page.getByRole("checkbox", {
    name: "Transparent",
    exact: true,
  });
  await transparency.click();
  await waitReady();
  assert.equal(
    (await state()).state.transparentMask,
    !beforeTransparency.transparentMask,
  );
  assert.equal(
    await transparency.isChecked(),
    !beforeTransparency.transparentMask,
  );
  await transparency.click();
  await waitReady();
  assert.equal(
    (await state()).state.transparentMask,
    beforeTransparency.transparentMask,
  );
  assert.equal((await state()).state.useMask, beforeTransparency.useMask);
  const transparencyUpdates = await page.evaluate(() => {
    window.__transparencyObserver.disconnect();
    return {
      disabledChanges: window.__transparencyDisabledChanges,
      sameButtons: window.__transparencyButtons.every(
        (button) => button.isConnected,
      ),
    };
  });
  assert.deepEqual(transparencyUpdates.disabledChanges, []);
  assert.equal(transparencyUpdates.sameButtons, true);
  assert.equal(await page.getByLabel("Use mask", { exact: true }).count(), 0);
  assert.equal(
    await page.getByLabel("Display mask", { exact: true }).count(),
    0,
  );
  assert.equal(await button("Fit mask detector").count(), 0);
  assert.equal((await state()).mask.data, saved);
  await button("Clear").click();
  await waitReady();
  await page.getByLabel("Above threshold counts", { exact: true }).fill("1000");
  await button("Above Thresh").click();
  await waitReady();
  const threshold = (await state()).state.maskedPixels;
  assert.ok(threshold > 0);
  await button("Clear").click();
  await waitReady();
  for (const plugin of (await state()).state.maskDetails.plugins) {
    const help = button(`Help: ${plugin.name}`);
    await help.hover();
    await page.getByRole("tooltip").waitFor({ state: "visible" });
    assert.equal(
      await page.getByRole("tooltip").textContent(),
      plugin.description,
    );
    await page.keyboard.press("Escape");
    const settings = button(`${plugin.name} settings`);
    await settings.click();
    assert.equal(await settings.getAttribute("aria-expanded"), "true");
    for (const [key, spec] of Object.entries(plugin.schema)) {
      if (!spec.description) continue;
      const parameterHelp = button(
        `Help: ${plugin.name}: ${spec.label ?? key}`,
      );
      await parameterHelp.focus();
      await page.getByRole("tooltip").waitFor({ state: "visible" });
      assert.equal(
        await page.getByRole("tooltip").textContent(),
        spec.description,
      );
      await page.keyboard.press("Escape");
    }
    await settings.click();
    assert.equal(await settings.getAttribute("aria-expanded"), "false");
  }
  await button("Threshold Mask settings").click();
  assert.equal(
    await page.getByText("DYNAMIC MASKING PLUGINS", { exact: true }).count(),
    1,
  );
  assert.equal(await button("Apply settings").count(), 0);
  const dynamicHelp = button("Help: Dynamic masking plugins");
  await dynamicHelp.hover();
  const dynamicTooltip = page.getByRole("tooltip");
  await dynamicTooltip.waitFor({ state: "visible" });
  assert.match(
    await dynamicTooltip.textContent(),
    /every image using its pixel intensities/,
  );
  const helpBox = await dynamicHelp.boundingBox();
  const headingBox = await page
    .locator(".mask-plugins > .section-label")
    .boundingBox();
  assert.ok(
    helpBox.x >= headingBox.x &&
      helpBox.x + helpBox.width <= headingBox.x + headingBox.width,
  );
  await page.keyboard.press("Escape");
  await dynamicTooltip.waitFor({ state: "hidden" });
  await dynamicHelp.focus();
  await dynamicTooltip.waitFor({ state: "visible" });
  await page.keyboard.press("Tab");
  await dynamicTooltip.waitFor({ state: "hidden" });
  const plugin = page.locator(".mask-plugin-row").filter({
    has: button("Threshold Mask settings"),
  });
  await page.getByLabel("Threshold Mask", { exact: true }).click();
  await waitReady();
  const upperThreshold = page.getByLabel("Threshold Mask: Upper threshold", {
    exact: true,
  });
  const pluginCommandCount = () =>
    commands.filter((command) => command === "mask_plugin").length;
  const beforeEnter = pluginCommandCount();
  await upperThreshold.fill("1000");
  assert.equal(
    pluginCommandCount(),
    beforeEnter,
    "Typing keeps the incomplete number local",
  );
  await upperThreshold.press("Enter");
  await waitReady();
  assert.equal(
    pluginCommandCount(),
    beforeEnter + 1,
    "Enter commits exactly once",
  );
  assert.equal((await state()).state.maskedPixels, threshold);
  await upperThreshold.fill("2000");
  await upperThreshold.press("Tab");
  await waitReady();
  const afterBlur = (await state()).state;
  assert.equal(afterBlur.maskDetails.plugins[0].settings.above_value, 2000);
  assert.ok(
    afterBlur.maskedPixels < threshold,
    "Blur recomputes the enabled mask",
  );
  await page
    .getByLabel("Threshold Mask: Mask above", { exact: true })
    .uncheck();
  await waitReady();
  assert.equal(
    (await state()).state.maskedPixels,
    0,
    "Checkbox updates immediately",
  );
  await upperThreshold.fill("3000");
  const beforeDefaults = pluginCommandCount();
  await plugin.getByRole("button", { name: "Defaults", exact: true }).click();
  await waitReady();
  assert.equal(
    pluginCommandCount(),
    beforeDefaults + 1,
    "Defaults replaces the draft in one command",
  );
  assert.deepEqual((await state()).state.maskDetails.plugins[0].settings, {
    above_enabled: true,
    above_value: 1e7,
    below_enabled: false,
    below_value: 0,
  });
  assert.equal(await upperThreshold.inputValue(), "10000000");
  assert.equal(
    (await state()).state.maskedPixels,
    0,
    "Defaults recomputes without Apply",
  );
  await upperThreshold.fill("");
  const beforeEmpty = pluginCommandCount();
  await upperThreshold.press("Tab");
  assert.equal(
    pluginCommandCount(),
    beforeEmpty,
    "Empty numbers do not become zero",
  );
  assert.equal(await upperThreshold.inputValue(), "10000000");
  await upperThreshold.fill("1000");
  await upperThreshold.press("Enter");
  await waitReady();
  assert.equal((await state()).state.maskedPixels, threshold);
  await plugin
    .getByRole("button", { name: "Imprint Threshold Mask", exact: true })
    .click();
  await waitReady();
  assert.equal((await state()).state.maskDetails.plugins[0].enabled, false);
  await button("Undo").click();
  await waitReady();
  assert.equal((await state()).state.maskDetails.plugins[0].enabled, true);
  await page.getByLabel("Threshold Mask", { exact: true }).click();
  await waitReady();
  await button("Calibration").click();
  await button("Step 1: Image & setup").click();
  await button("Rotate image +90°").click();
  await waitReady();
  await button("Mask").click();
  await square();
  await button("Rectangle").click();
  await clickSource(50, 60);
  await clickSource(80, 100);
  await waitReady();
  current = await state();
  assert.equal(current.mask.fullWidth, 1043);
  assert.equal(maskBytes(current)[80 * 1043 + 60], 1);
  await button("Save Mask").click();
  await waitReady();
  // Reference geometry is explicitly loaded for integration checks, not fitted by these mask tests.
  const loaded = await invoke("open_calibration", {
    path: path.join(root, "dioptas/tests/data/CeO2_Pilatus1M.poni"),
  });
  assert.ok(loaded.ok, loaded.error);
  await button("Clear").click();
  await waitReady();
  await page.getByLabel("Mask range minimum").fill("5");
  await page.getByLabel("Mask range maximum").fill("8");
  await button("Inside").click();
  await waitReady();
  current = await state();
  assert.ok(current.state.maskedPixels > 0);
  assert.equal(current.state.integrationDirty, true);
  assert.equal(current.pattern, null);
  assert.equal(current.cake, null);
  const integrationCount = () =>
    commands.filter((c) => c === "integrate").length;
  const beforeRefresh = integrationCount();
  await button("Integration").click();
  await waitReady();
  current = await state();
  assert.equal(current.state.integrationDirty, false);
  assert.ok(current.pattern && current.cake);
  assert.equal(integrationCount(), beforeRefresh + 1);
  await button("Mask").click();
  await button("Integration").click();
  await waitReady();
  assert.equal(integrationCount(), beforeRefresh + 1);
  await button("Mask").click();
  await button("Undo").click();
  await waitReady();
  assert.equal((await state()).state.integrationDirty, true);
  assert.equal(integrationCount(), beforeRefresh + 1);
  await button("Map").click();
  await waitReady();
  current = await state();
  assert.equal(current.state.integrationDirty, false);
  assert.ok(current.pattern && current.cake);
  assert.equal(integrationCount(), beforeRefresh + 2);
  await button("Mask").click();
  await button("Redo").click();
  await waitReady();
  assert.equal((await state()).state.integrationDirty, true);
  assert.equal(integrationCount(), beforeRefresh + 2);
  await button("Calibration").click();
  await waitReady();
  assert.equal((await state()).state.integrationDirty, false);
  assert.equal(integrationCount(), beforeRefresh + 3);
  await button("Step 4: Validate").click();
  await waitReady();
  assert.equal((await state()).state.integrationDirty, false);
  assert.equal(integrationCount(), beforeRefresh + 3);
  await button("Mask").click();
  await page.getByLabel("Mask radial unit").selectOption("q_A^-1");
  assert.equal(await page.getByLabel("Mask range minimum").inputValue(), "");
  const verifyPinnedMaskFiles = async () => {
    const footer = page.locator(".mask-file-actions");
    const before = await footer.boundingBox();
    const sidebar = await page.locator("aside.sidebar").boundingBox();
    assert.ok(
      Math.abs(before.y + before.height - sidebar.y - sidebar.height) < 2,
    );
    const controls = page.locator(".mask-controls-scroll");
    await controls.evaluate((el) => (el.scrollTop = el.scrollHeight));
    const after = await footer.boundingBox();
    assert.equal(after.y, before.y);
    for (const label of ["Load Mask", "Add Mask", "Save Mask"]) {
      const bounds = await button(label).boundingBox();
      assert.ok(bounds.y >= after.y);
      assert.ok(bounds.y + bounds.height <= after.y + after.height);
    }
    await controls.evaluate((el) => (el.scrollTop = 0));
  };
  const verifyMaskShapeLayout = async () => {
    const heights = await page
      .locator(".mask-shape-grid > button")
      .evaluateAll((buttons) =>
        buttons.map((button) => button.getBoundingClientRect().height),
      );
    const diameter = await page.getByLabel("Mask point diameter").boundingBox();
    assert.ok(
      heights.every((height) => Math.abs(height - diameter.height) < 1),
    );
    const selected = page.locator(
      '.mask-shape-grid button[aria-pressed="true"]',
    );
    const finish = await selected.evaluate((button) => {
      const style = getComputedStyle(button);
      return {
        image: style.backgroundImage,
        shadow: style.boxShadow,
        fill: style.backgroundColor,
      };
    });
    assert.equal(finish.image, "none");
    assert.equal(finish.shadow, "none");
    const inactiveFill = await page
      .locator('.mask-shape-grid button[aria-pressed="false"]')
      .first()
      .evaluate((button) => getComputedStyle(button).backgroundColor);
    assert.notEqual(
      finish.fill,
      inactiveFill,
      "The active tool stays distinct",
    );
  };
  await verifyPinnedMaskFiles();
  await verifyMaskShapeLayout();
  await page.waitForTimeout(4600);
  await page.screenshot({ path: path.join(artifacts, "mask-mode.png") });
  await page.setViewportSize({ width: 1000, height: 760 });
  await square();
  await verifyPinnedMaskFiles();
  await verifyMaskShapeLayout();
  await page.screenshot({ path: path.join(artifacts, "mask-compact.png") });
  assert.equal(
    await page.evaluate(
      () => document.documentElement.scrollWidth > innerWidth,
    ),
    false,
  );
  await setInterfaceTextSize(page, true);
  await verifyPinnedMaskFiles();
  await verifyMaskShapeLayout();
  assert.ok(
    (await button("Circle").evaluate((el) =>
      parseFloat(getComputedStyle(el).fontSize),
    )) >= 17,
  );
  assert.deepEqual(errors, []);
  await writeFile(
    path.join(artifacts, "mask-browser-smoke.json"),
    JSON.stringify(
      {
        ok: true,
        shapes: ["rectangle", "circle", "point", "polygon", "arc"],
        undoRedo: true,
        deferredIntegration: true,
        zoomResizeSourcePixels: true,
        transformSourcePixels: true,
        fileActions: true,
        pluginImprint: true,
        dynamicPluginUpdates: true,
        radialRange: true,
        squarePixels: true,
        compact: true,
      },
      null,
      2,
    ),
  );
  console.log("Mask browser smoke passed");
} catch (error) {
  await page.screenshot({ path: path.join(artifacts, "mask-failure.png") });
  throw error;
} finally {
  await browser.close();
  host.stdin.end();
  await writeFile(
    path.join(artifacts, "mask-browser-smoke.log"),
    diagnostics.join("\n"),
  );
}
