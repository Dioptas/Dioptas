import { setInterfaceTextSize } from "./plot_navigation.mjs";
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { createInterface } from "node:readline";
import { mkdir, writeFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import path from "node:path";
import { chromium } from "playwright";
const root = fileURLToPath(new URL("../../", import.meta.url));
const artifacts = path.join(root, "desktop/artifacts");
await mkdir(artifacts, { recursive: true });
const host = spawn(
  path.join(root, ".venv/bin/python"),
  ["-u", "desktop/scripts/bridge_host.py"],
  { cwd: root, stdio: ["pipe", "pipe", "pipe"] },
);
let identifier = 0;
const pending = new Map(),
  logs = [],
  requests = [];
host.stderr.on("data", (b) => logs.push(b.toString()));
createInterface({ input: host.stdout }).on("line", (line) => {
  const message = JSON.parse(line),
    task = pending.get(message.id);
  if (task) {
    clearTimeout(task.timer);
    pending.delete(message.id);
    task.resolve(message.result);
  }
});
function invoke(action, payload = {}) {
  requests.push(action);
  return new Promise((resolve, reject) => {
    const id = ++identifier;
    const timer = setTimeout(() => reject(Error(`Timed out ${action}`)), 45000);
    pending.set(id, { resolve, timer });
    host.stdin.write(JSON.stringify({ id, action, payload }) + "\n");
  });
}
const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({ viewport: { width: 1600, height: 1000 } });
const errors = [];
page.on("pageerror", (e) => errors.push(e.message));
await page.exposeFunction("__dioptasInvoke", invoke);
await page.addInitScript(() => {
  window.pywebview = {
    api: { invoke: (a, p) => window.__dioptasInvoke(a, p) },
  };
});
const ready = async () => {
  await page.waitForFunction(() => !document.querySelector(".spin"));
  assert.equal(
    await page.getByRole("alert").count(),
    0,
    JSON.stringify(await page.getByRole("alert").allTextContents()),
  );
};
const click = async (name) => {
  await page.getByRole("button", { name, exact: true }).click();
  await ready();
};
async function scanClick(row, col, rows, cols) {
  const canvas = page.locator('[data-testid="scan-map"] canvas').first();
  const b = await canvas.boundingBox();
  const scale = Math.min((b.width - 8) / cols, (b.height - 8) / rows);
  await page.mouse.click(
    b.x + (b.width - cols * scale) / 2 + (col + 0.5) * scale,
    b.y + (b.height - rows * scale) / 2 + (row + 0.5) * scale,
  );
  await ready();
}
try {
  assert.equal((await invoke("example")).ok, true);
  assert.equal(
    (
      await invoke("open_calibration", {
        path: path.join(root, "dioptas/tests/data/CeO2_Pilatus1M.poni"),
      })
    ).ok,
    true,
  );
  await page.goto("file://" + path.join(root, "dioptas/desktop/ui/index.html"));
  await ready();
  await click("Map");
  await page
    .locator(".map-controls")
    .getByRole("button", { name: "Load images…", exact: true })
    .click();
  await ready();
  let state = await invoke("state");
  assert.equal(state.map.points, 9);
  assert.equal(
    await page.locator(".map-layout .intensity-histogram").count(),
    2,
  );
  for (const panel of [".map-scan-panel", ".map-detector-panel"])
    assert.equal(
      await page
        .locator(panel + " .image-intensity")
        .getAttribute("data-orientation"),
      "horizontal",
    );
  await scanClick(1, 2, 3, 3);
  state = await invoke("state");
  assert.equal(state.map.selected, 5);
  assert.equal(
    await page
      .locator(".map-detector-panel canvas")
      .first()
      .getAttribute("data-full-width"),
    String(state.image.fullWidth),
  );
  await page.getByRole("tab", { name: "Grid", exact: true }).click();
  await page.getByLabel("Serpentine (snake) scan", { exact: true }).click();
  await ready();
  await scanClick(1, 2, 3, 3);
  assert.equal((await invoke("state")).map.selected, 3);
  await page.getByLabel("Map rows", { exact: true }).fill("2");
  await page.getByLabel("Map columns", { exact: true }).fill("5");
  await click("Apply grid");
  await scanClick(1, 0, 2, 5); // trailing blank after snake
  state = await invoke("state");
  assert.equal(state.map.selected, null);
  assert.equal(state.pattern, null);
  assert.equal(
    await page.locator(".map-detector-panel .empty-view").count(),
    1,
  );
  await scanClick(0, 0, 2, 5);
  await page.getByRole("tab", { name: "Layers", exact: true }).click();
  await click("Add window");
  await page.getByLabel("Window B minimum", { exact: true }).fill("4");
  await page.getByLabel("Window B maximum", { exact: true }).fill("8");
  await page
    .locator(".map-window")
    .nth(1)
    .getByRole("button", { name: "Apply window", exact: true })
    .click();
  await ready();
  await page.getByLabel("Expression layer name", { exact: true }).fill("Ratio");
  await page.getByLabel("Map expression", { exact: true }).fill("A/B");
  await click("Apply expression");
  assert.equal((await invoke("state")).map.active, "Ratio");
  await click("Edit windows");
  const pattern = page.locator(".map-pattern-panel canvas");
  let b = await pattern.boundingBox();
  state = await invoke("state");
  const roi = state.map.rois[1],
    min = Math.min(state.pattern.x[0], state.pattern.x.at(-1)),
    max = Math.max(state.pattern.x[0], state.pattern.x.at(-1));
  const bounds = await pattern.evaluate((el) => ({
    left: +el.dataset.plotLeft,
    width: +el.dataset.plotWidth,
  }));
  const x = b.x + bounds.left + ((roi.min - min) / (max - min)) * bounds.width;
  await page.mouse.move(x, b.y + b.height / 2);
  await page.mouse.down();
  await page.mouse.move(x + 15, b.y + b.height / 2, { steps: 6 });
  await page.mouse.up();
  await ready();
  assert.ok(
    (await invoke("state")).map.rois[1].min > roi.min,
    "Window edge did not update the real model",
  );
  await click("Edit windows");
  const before = await pattern.getAttribute("data-view-x-max");
  await pattern.hover();
  await page.mouse.wheel(0, -150);
  await page.waitForTimeout(80);
  assert.notEqual(await pattern.getAttribute("data-view-x-max"), before);
  const mapCanvas = page.locator('[data-testid="scan-map"] canvas').first();
  const beforeView = await mapCanvas.getAttribute("data-view-x-max");
  await mapCanvas.hover();
  await page.mouse.wheel(0, -120);
  await page.waitForTimeout(80);
  assert.notEqual(await mapCanvas.getAttribute("data-view-x-max"), beforeView);
  const countsBeforeHover = requests.length;
  for (let i = 0; i < 10; i++) {
    const c = await mapCanvas.boundingBox();
    await page.mouse.move(c.x + c.width / 2 + i, c.y + c.height / 2);
  }
  assert.equal(
    requests.length,
    countsBeforeHover,
    "Map hover made scientific payload requests",
  );
  await page.getByRole("tab", { name: "Files", exact: true }).click();
  await page.getByText("Normalize patterns", { exact: true }).click();
  await click("Normalize");
  assert.equal((await invoke("state")).map.normalized, true);
  await click("Restore original");
  assert.equal((await invoke("state")).map.normalized, false);
  await click("Save PNG…");
  await click("Save map data…");
  await click("Save");
  await click("Expand map");
  assert.equal(await page.locator(".map-detector-panel").count(), 0);
  await click("Dock detector / pattern");
  await page.getByLabel("Smooth map", { exact: true }).click();
  await page.getByLabel("Map contours", { exact: true }).click();
  await page.waitForTimeout(500);
  assert.ok(requests.includes("map_display"));
  await page.getByLabel("Smooth map", { exact: true }).click();
  await page.getByLabel("Map contours", { exact: true }).click();
  await setInterfaceTextSize(page, true);
  assert.equal(
    await page
      .locator(".map-controls input[type=number]")
      .first()
      .evaluate((el) => getComputedStyle(el).fontSize),
    "16px",
  );
  await setInterfaceTextSize(page, false);
  await page.locator(".sidebar-scroll").evaluate((el) => (el.scrollTop = 0));
  await page.screenshot({
    path: path.join(artifacts, "map-desktop.png"),
    fullPage: true,
  });
  await page.setViewportSize({ width: 1000, height: 760 });
  await page.screenshot({
    path: path.join(artifacts, "map-compact.png"),
    fullPage: true,
  });
  assert.equal(
    await page.evaluate(
      () => document.documentElement.scrollWidth > innerWidth,
    ),
    false,
  );
  await page.setViewportSize({ width: 1600, height: 1000 });
  await click("Open project");
  assert.equal((await invoke("state")).map.active, "Ratio");
  await click("Calibration");
  assert.equal(
    await page
      .getByRole("button", { name: "Step 2: Pick rings", exact: true })
      .count(),
    1,
  );
  assert.deepEqual(errors, []);
  await writeFile(
    path.join(artifacts, "map-smoke.json"),
    JSON.stringify(
      {
        ok: true,
        points: 9,
        linkedSelection: true,
        blankSelection: true,
        serpentine: true,
        windowDrag: true,
        normalization: true,
        projectRoundTrip: true,
        independentHistograms: true,
        sharedNavigation: true,
        errors,
      },
      null,
      2,
    ),
  );
  console.log("Map browser smoke passed");
} finally {
  await browser.close();
  host.stdin.end();
  await writeFile(path.join(artifacts, "map-smoke.log"), logs.join(""));
}
