import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { createInterface } from "node:readline";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import path from "node:path";
import { chromium } from "playwright";
import {
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
await page.addInitScript(() => {
  const draw = CanvasRenderingContext2D.prototype.drawImage;
  CanvasRenderingContext2D.prototype.drawImage = function (...args) {
    if (this.canvas.dataset.testid === "detector-canvas" && args.length === 5) {
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
  window.pywebview = {
    api: {
      invoke: (command, payload) => window.__dioptasInvoke(command, payload),
    },
  };
});
const waitReady = async () => {
  await page.waitForFunction(() => !document.querySelector(".spin"), {
    timeout: 45000,
  });
  assert.equal(
    await page.getByRole("alert").count(),
    0,
    JSON.stringify(await page.getByRole("alert").allTextContents()),
  );
};

const button = (name) => page.getByRole("button", { name, exact: true });
const state = () => invoke("state");
const maskBytes = (result) => Buffer.from(result.mask.data, "base64");
const clickSource = async (x, y, options = {}) => {
  const target = await page.getByTestId("detector-canvas").evaluate(
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
  await page.mouse.click(target.x, target.y, options);
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
  await button("Configure detector display").click();
  await page.getByLabel("Image scale", {exact:true}).selectOption("log");
  await page.getByLabel("Maximum intensity", {exact:true}).fill("1000");
  await button("Close detector display settings").click();
  await selectColorMap(page, "Color map", "thermal");
  const detector = page.getByTestId("detector-canvas");
  assert.equal(await detector.getAttribute("data-intensity-scale"), "log");
  assert.equal((await state()).image.data, originalImage);
  await button("Rectangle").click();
  await clickSource(101.2, 201.2);
  await clickSource(161.2, 251.2);
  await waitReady();
  let current = await state();
  let bytes = maskBytes(current);
  assert.equal(current.state.maskedPixels, 60 * 50);
  assert.equal(bytes[220 * 981 + 120], 1);
  assert.equal(bytes[120 * 981 + 220], 0);
  await button("Undo mask").click();
  await waitReady();
  assert.equal((await state()).state.maskedPixels, 0);
  await button("Redo mask").click();
  await waitReady();
  assert.equal((await state()).state.maskedPixels, 3000);
  await button("Clear").click();
  await waitReady();
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
  await button("Undo mask").click();await waitReady();
  assert.equal(await detector.getAttribute("data-view-x-min"), zoomBeforeUndo);
  assert.equal(await detector.getAttribute("data-intensity-max"), contrastBeforeUndo);
  await button("Redo mask").click();await waitReady();
  await button("Fit mask detector").click();
  await square();
  await button("Circle").click();
  await clickSource(300, 400);
  await clickSource(360, 460);
  await waitReady();
  assert.ok((await state()).state.maskedPixels > 1200);
  await button("Polygon").click();
  await clickSource(200, 300);
  await clickSource(240, 300);
  await clickSource(220, 340);
  await page.keyboard.press("Enter");
  await waitReady();
  const polygonCount = (await state()).state.maskedPixels;
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
  await page.getByLabel("Transparent mask", { exact: true }).click();
  await waitReady();
  await page.getByLabel("Use mask", { exact: true }).click();
  await waitReady();
  assert.equal((await state()).state.useMask, false);
  await page.getByLabel("Display mask", { exact: true }).uncheck();
  assert.equal((await state()).mask.data, saved);
  await page.getByLabel("Display mask", { exact: true }).check();
  await button("Clear").click();
  await waitReady();
  await page.getByLabel("Above threshold counts", { exact: true }).fill("1000");
  await button("Above Thresh").click();
  await waitReady();
  const threshold = (await state()).state.maskedPixels;
  assert.ok(threshold > 0);
  await button("Clear").click();
  await waitReady();
  await page.getByText("Threshold Mask settings", { exact: true }).click();
  await page
    .getByLabel("Threshold Mask: Upper threshold", { exact: true })
    .fill("1000");
  const plugin = page.locator(".mask-plugin-row").filter({
    has: page.getByText("Threshold Mask settings", { exact: true }),
  });
  await plugin
    .getByRole("button", { name: "Apply settings", exact: true })
    .click();
  await waitReady();
  await page.getByLabel("Threshold Mask", { exact: true }).click();
  await waitReady();
  assert.equal((await state()).state.maskedPixels, threshold);
  await plugin.getByRole("button", { name: "Imprint", exact: true }).click();
  await waitReady();
  assert.equal((await state()).state.maskDetails.plugins[0].enabled, false);
  await button("Undo mask").click();
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
  assert.ok((await state()).state.maskedPixels > 0);
  await page.getByLabel("Mask radial unit").selectOption("q_A^-1");
  assert.equal(await page.getByLabel("Mask range minimum").inputValue(), "");
  await page.locator(".sidebar-scroll").evaluate(el=>el.scrollTop=0);
  await page.waitForTimeout(4600);
  await page.screenshot({ path: path.join(artifacts, "mask-mode.png") });
  await page.setViewportSize({ width: 1000, height: 760 });
  await square();
  await page.screenshot({ path: path.join(artifacts, "mask-compact.png") });
  assert.equal(
    await page.evaluate(
      () => document.documentElement.scrollWidth > innerWidth,
    ),
    false,
  );
  await button("Larger text").click();
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
        zoomResizeSourcePixels: true,
        transformSourcePixels: true,
        fileActions: true,
        pluginImprint: true,
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
