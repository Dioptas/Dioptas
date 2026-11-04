import { setInterfaceTextSize } from "./plot_navigation.mjs";
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { createInterface } from "node:readline";
import { mkdir, writeFile, mkdtemp, copyFile, rm } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import path from "node:path";
import { chromium, webkit } from "playwright";
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
const browser = await (
  process.argv.includes("--webkit") ? webkit : chromium
).launch({ headless: true });
const page = await browser.newPage({ viewport: { width: 1600, height: 1000 } });
const errors = [];
page.on("pageerror", (e) => errors.push(e.message));
let delayWindowEdits = false;
let windowEditGate = null;
let windowEditsStarted = 0;
let selectionGate = null;
let selectionsStarted = 0;
await page.exposeFunction("__dioptasInvoke", async (action, payload) => {
  if (action === "map_roi") {
    windowEditsStarted++;
    if (windowEditGate) await windowEditGate;
  }
  if (action === "map_select") {
    selectionsStarted++;
    if (selectionGate) await selectionGate;
  }
  if (delayWindowEdits && action === "map_roi")
    await new Promise((resolve) => setTimeout(resolve, 120));
  return invoke(action, payload);
});
await page.addInitScript(() => {
  window.pywebview = {
    api: {
      invoke: async (a, p) => {
        window.__pendingCommands = (window.__pendingCommands ?? 0) + 1;
        try {
          const result = await window.__dioptasInvoke(a, p);
          if (a === "map_roi")
            window.__mapRoiResponses = (window.__mapRoiResponses ?? 0) + 1;
          return result;
        } finally {
          window.__pendingCommands--;
        }
      },
    },
  };
});
const ready = async () => {
  await page.waitForFunction(
    () =>
      !document.querySelector(".spin") &&
      !window.__pendingCommands &&
      !document.querySelector('.map-layers[aria-busy="true"]'),
  );
  assert.equal(
    await page.getByRole("alert").count(),
    0,
    JSON.stringify(await page.getByRole("alert").allTextContents()),
  );
};
const click = async (name) => {
  await page.getByRole("button", { name, exact: true }).first().click();
  await ready();
};
async function scanClick(row, col, rows, cols) {
  const canvas = page.locator(
    '[data-testid="scan-map"] [data-testid="detector-canvas"]',
  );
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
  await copyFile(
    path.join(root, "dioptas/tests/data/CeO2_Pilatus1M.poni"),
    path.join(artifacts, "calibration.poni"),
  );
  await page.goto("file://" + path.join(root, "dioptas/desktop/ui/index.html"));
  await ready();
  await click("Map");
  await click("Load map calibration");
  await page
    .locator(".map-controls")
    .getByRole("button", { name: "Load images…", exact: true })
    .click();
  await ready();
  let state = await invoke("state");
  assert.equal(state.map.points, 9);
  assert.equal(state.state.calibrated, true);
  assert.equal(state.state.integrationDirty, true);
  assert.equal(state.cake, null);
  const sharedGeometry = state.state.geometry;
  const integrationsBefore = requests.filter((a) => a === "integrate").length;
  await click("Integration");
  await page
    .locator('.cake-panel [data-testid="cake-canvas"]')
    .waitFor({ state: "attached" });
  await ready();
  state = await invoke("state");
  assert.ok(state.cake?.data, "Map selection did not produce a shared cake");
  assert.equal(state.state.integrationDirty, false);
  assert.deepEqual(state.state.geometry, sharedGeometry);
  assert.equal(
    requests.filter((a) => a === "integrate").length,
    integrationsBefore + 1,
  );
  await click("Cake");
  await page
    .locator('.cake-panel [data-testid="cake-canvas"]')
    .waitFor({ state: "visible" });
  await click("Map");
  await page
    .getByRole("listbox", { name: "Scan arrangement" })
    .getByRole("option")
    .first()
    .click();
  await ready();
  assert.equal((await invoke("state")).cake, null);
  await click("Calibration");
  await page
    .locator('.cake-panel [data-testid="cake-canvas"]')
    .waitFor({ state: "visible" });
  await ready();
  state = await invoke("state");
  assert.ok(state.cake?.data);
  assert.deepEqual(state.state.geometry, sharedGeometry);
  assert.equal(state.state.integrationDirty, false);
  await click("Map");
  await page
    .getByRole("listbox", { name: "Scan arrangement" })
    .getByRole("option")
    .first()
    .click();
  await ready();
  state = await invoke("state");
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
  const settingsButton = page.getByRole("button", {
    name: "Map settings",
    exact: true,
  });
  const settingsDialog = page.getByRole("dialog", {
    name: "Map settings",
    exact: true,
  });
  await settingsButton.click();
  const reintegrateSetting = settingsDialog.getByLabel(
    "Reintegrate selected image",
    { exact: true },
  );
  assert.equal(await reintegrateSetting.isChecked(), true);
  await reintegrateSetting.uncheck();
  await settingsDialog
    .getByRole("button", { name: "Close", exact: true })
    .click();
  const storedLength = state.pattern.y.length;
  const previousBins = state.state.bins;
  assert.equal((await invoke("integration_settings", { bins: 120 })).ok, true);
  await scanClick(1, 2, 3, 3);
  assert.equal(
    (await invoke("state")).pattern.y.length,
    storedLength,
    "Disabled reintegration did not retain the stored pattern",
  );
  await settingsButton.click();
  assert.equal(await reintegrateSetting.isChecked(), false);
  await reintegrateSetting.check();
  await settingsDialog
    .getByRole("button", { name: "Close", exact: true })
    .click();
  await scanClick(1, 2, 3, 3);
  state = await invoke("state");
  assert.equal(state.map.selected, 5);
  assert.equal(
    state.pattern.y.length,
    120,
    "Point selection did not automatically apply current integration settings",
  );
  assert.equal(
    (await invoke("integration_settings", { bins: previousBins })).ok,
    true,
  );
  await scanClick(1, 2, 3, 3);
  state = await invoke("state");
  // Hold a real image-selection request in flight to catch transient dimming
  // and preview rebuilds, then check that further file clicks are retained.
  await page.getByLabel("Smooth map", { exact: true }).check();
  await page.getByLabel("Map contours", { exact: true }).check();
  await ready();
  const displayRequests = requests.filter((a) => a === "map_display").length;
  const mapLevelRequests = requests.filter((a) => a === "map_levels").length;
  await page.evaluate(() => {
    window.__mapFlicker = [];
    window.__scanCanvas = document.querySelector(
      '[data-testid="scan-map"] canvas',
    );
    window.__mapObserver = new MutationObserver((changes) => {
      if (changes.some((c) => c.attributeName === "disabled"))
        window.__mapFlicker.push("controls toggled disabled");
      if (document.querySelector(".spin"))
        window.__mapFlicker.push("global busy indicator");
    });
    window.__mapObserver.observe(
      document.querySelector(".app") ?? document.body,
      {
        subtree: true,
        attributes: true,
        childList: true,
        attributeFilter: ["disabled"],
      },
    );
  });
  let releaseSelection;
  selectionGate = new Promise((resolve) => {
    releaseSelection = resolve;
  });
  const startedBefore = selectionsStarted;
  const points = page
    .getByRole("listbox", { name: "Scan arrangement" })
    .getByRole("option");
  await points.nth(1).click();
  await page.waitForTimeout(100);
  assert.equal(selectionsStarted, startedBefore + 1);
  assert.equal(
    await page.locator(".spin").count(),
    0,
    "Selection dimmed the whole app",
  );
  assert.equal(await points.nth(2).isEnabled(), true);
  await points.nth(2).click();
  await points.nth(3).click();
  selectionGate = null;
  releaseSelection();
  await page.waitForFunction(
    () =>
      document
        .querySelectorAll('[role="option"]')[3]
        ?.getAttribute("aria-selected") === "true",
  );
  await ready();
  assert.equal(
    selectionsStarted,
    startedBefore + 3,
    "Rapid point clicks were dropped",
  );
  assert.equal((await invoke("state")).map.selectedSlot, 3);
  assert.equal(
    requests.filter((a) => a === "map_display").length,
    displayRequests,
    "Selection rebuilt the unchanged map preview",
  );
  assert.equal(
    requests.filter((a) => a === "map_levels").length,
    mapLevelRequests,
    "Selection reset the scan histogram",
  );
  assert.deepEqual(
    await page.evaluate(() => {
      window.__mapObserver.disconnect();
      return {
        flicker: window.__mapFlicker,
        sameCanvas:
          window.__scanCanvas ===
          document.querySelector('[data-testid="scan-map"] canvas'),
      };
    }),
    { flicker: [], sameCanvas: true },
  );
  await page.getByLabel("Smooth map", { exact: true }).uncheck();
  await page.getByLabel("Map contours", { exact: true }).uncheck();
  await ready();
  assert.equal(
    await page
      .locator('.map-detector-panel [data-testid="detector-canvas"]')
      .getAttribute("data-full-width"),
    String(state.image.fullWidth),
  );
  await page.getByRole("tab", { name: "Grid", exact: true }).click();
  await page.getByLabel("Serpentine (snake) scan", { exact: true }).click();
  await ready();
  await scanClick(1, 2, 3, 3);
  assert.equal((await invoke("state")).map.selected, 3);
  const rowsInput = page.getByLabel("Map rows", { exact: true });
  const columnsInput = page.getByLabel("Map columns", { exact: true });
  await rowsInput.fill("");
  assert.equal(
    await rowsInput.inputValue(),
    "",
    "Clearing rows inserted a zero",
  );
  await rowsInput.fill("2");
  await rowsInput.press("Enter");
  await ready();
  assert.deepEqual(
    (await invoke("state")).map.dimension,
    [3, 3],
    "An incomplete, undersized grid was applied",
  );
  await columnsInput.fill("");
  assert.equal(
    await columnsInput.inputValue(),
    "",
    "Clearing columns inserted a zero",
  );
  await columnsInput.fill("5");
  await columnsInput.press("Tab");
  await ready();
  assert.deepEqual(
    (await invoke("state")).map.dimension,
    [2, 5],
    "Grid dimensions did not apply on blur",
  );
  await rowsInput.fill("3");
  await rowsInput.press("Enter");
  await ready();
  assert.deepEqual(
    (await invoke("state")).map.dimension,
    [3, 5],
    "Grid dimensions did not apply on Enter",
  );
  await rowsInput.fill("2");
  await rowsInput.press("Enter");
  await ready();
  assert.equal(
    await page.getByRole("button", { name: "Apply grid", exact: true }).count(),
    0,
  );
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
  delayWindowEdits = true;
  const fromField = page.getByLabel("Window B minimum", { exact: true });
  const toField = page.getByLabel("Window B maximum", { exact: true });
  await fromField.fill("4");
  await fromField.press("Tab");
  assert.ok(
    await toField.evaluate((el) => el === document.activeElement),
    "Tab lost the next range field while saving",
  );
  await toField.fill("");
  assert.equal(await toField.inputValue(), "");
  await toField.fill("8");
  await toField.press("Enter");
  await ready();
  assert.ok(
    await toField.evaluate((el) => el === document.activeElement),
    "Range save moved the input focus",
  );
  assert.equal((await invoke("state")).map.rois[1].min, 4);
  assert.equal(
    (await invoke("state")).map.rois[1].max,
    8,
    "Queued range edit was lost",
  );
  // An intermediate From > To must stay editable until the next field completes the pair.
  await fromField.fill("18");
  await fromField.press("Tab");
  await ready();
  assert.ok(await toField.evaluate((el) => el === document.activeElement));
  assert.equal(Number(await fromField.inputValue()), 18);
  assert.equal(
    (await invoke("state")).map.rois[1].min,
    4,
    "Incomplete range changed the scientific map",
  );
  await toField.fill("20");
  await toField.press("Enter");
  await ready();
  assert.equal((await invoke("state")).map.rois[1].min, 18);
  assert.equal((await invoke("state")).map.rois[1].max, 20);
  await fromField.fill("4");
  await fromField.press("Tab");
  await toField.fill("8");
  await toField.press("Enter");
  await ready();
  delayWindowEdits = false;
  await page.getByLabel("Expression layer name", { exact: true }).fill("Ratio");
  await page.getByLabel("Map expression", { exact: true }).fill("A/B");
  await click("Apply expression");
  assert.equal((await invoke("state")).map.active, "Ratio");
  const pattern = page.locator(
    '.map-pattern-panel [data-testid="pattern-canvas"]',
  );
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
  const edgeResponses = await page.evaluate(
    () => window.__mapRoiResponses ?? 0,
  );
  const scanCanvas = page.locator(
    '[data-testid="scan-map"] [data-testid="detector-canvas"]',
  );
  const beforeEdgePixels = await scanCanvas.screenshot();
  await page.mouse.move(x, b.y + b.height / 2);
  await page.mouse.down();
  await page.mouse.move(x + 6, b.y + b.height / 2, { steps: 6 });
  await page.waitForFunction(
    (count) => (window.__mapRoiResponses ?? 0) > count,
    edgeResponses,
  );
  await ready();
  assert.ok(
    (await invoke("state")).map.rois[1].min > roi.min,
    "Window edge must update the real model before pointer release",
  );
  assert.notDeepEqual(
    await scanCanvas.screenshot(),
    beforeEdgePixels,
    "Map pixels must redraw while the window edge is held",
  );
  const continuingResponses = await page.evaluate(
    () => window.__mapRoiResponses ?? 0,
  );
  await page.mouse.move(x + 15, b.y + b.height / 2, { steps: 6 });
  await page.waitForFunction(
    (count) => (window.__mapRoiResponses ?? 0) > count,
    continuingResponses,
  );
  await page.mouse.up();
  await ready();
  assert.ok(
    (await invoke("state")).map.rois[1].min > roi.min,
    "Window edge did not update the real model",
  );
  assert.equal(
    (await invoke("state")).map.active,
    "Ratio",
    "Dragging a source window must preserve the displayed expression",
  );
  // Inline color and value edits update the same scientific windows as Qt.
  await page.getByLabel("Window B color", { exact: true }).fill("#b050e0");
  await ready();
  assert.equal((await invoke("state")).map.rois[1].color, "#b050e0");
  await page.getByLabel("Window B value", { exact: true }).selectOption("area");
  await ready();
  assert.equal((await invoke("state")).map.rois[1].reduction, "area");
  await page.getByLabel("Window B value", { exact: true }).selectOption("sum");
  await ready();
  const original = (await invoke("state")).map.rois;
  await click("Map pattern unit Q");
  const qRegions = JSON.parse(await pattern.getAttribute("data-regions"));
  const wavelength = (await invoke("state")).state.geometry.wavelength * 1e10;
  const expectedQ =
    (4 * Math.PI * Math.sin((original[1].min * Math.PI) / 360)) / wavelength;
  assert.ok(Math.abs(qRegions[1].min - expectedQ) < 1e-10);
  assert.deepEqual(
    (await invoke("state")).map.rois,
    original,
    "Display units changed stored ROI ranges",
  );
  assert.match(await page.getByTestId("map-window-unit").textContent(), /Q/);
  assert.ok(
    Math.abs(Number(await fromField.inputValue()) - expectedQ) < 1e-5,
    "Table minimum did not switch to Q",
  );
  const qMaximum = Number(await toField.inputValue());
  const changedQ = expectedQ + (qMaximum - expectedQ) * 0.1;
  await fromField.fill(String(changedQ));
  await fromField.press("Enter");
  await ready();
  const storedAngleFromQ =
    (Math.asin((changedQ * wavelength) / (4 * Math.PI)) * 360) / Math.PI;
  assert.ok(
    Math.abs((await invoke("state")).map.rois[1].min - storedAngleFromQ) < 1e-9,
    "Q table edit was not converted to the stored angle",
  );
  await fromField.fill(String(expectedQ));
  await fromField.press("Enter");
  await ready();
  await click("Map pattern unit d");
  const dRegions = JSON.parse(await pattern.getAttribute("data-regions"));
  assert.ok(
    dRegions[1].min < dRegions[1].max,
    "Descending d conversion reversed the window",
  );
  assert.match(await page.getByTestId("map-window-unit").textContent(), /d/);
  assert.ok(
    Math.abs(Number(await fromField.inputValue()) - dRegions[1].min) < 1e-5,
    "Table From did not follow reversed d limits",
  );
  assert.ok(
    Math.abs(Number(await toField.inputValue()) - dRegions[1].max) < 1e-5,
    "Table To did not follow reversed d limits",
  );
  const changedD = dRegions[1].min + (dRegions[1].max - dRegions[1].min) * 0.1;
  await fromField.fill(String(changedD));
  await fromField.press("Enter");
  await ready();
  const storedAngleFromD =
    (Math.asin(wavelength / (2 * changedD)) * 360) / Math.PI;
  assert.ok(
    Math.abs((await invoke("state")).map.rois[1].max - storedAngleFromD) < 1e-9,
    "d table edit updated the wrong stored edge",
  );
  await fromField.fill(String(dRegions[1].min));
  await fromField.press("Enter");
  await ready();
  // Drag the lower d edge and independently verify that the *upper* stored angle changes.
  const dBox = await pattern.boundingBox();
  const initialDBounds = await pattern.evaluate((el) => ({
    left: +el.dataset.plotLeft,
    width: +el.dataset.plotWidth,
    min: +el.dataset.viewXMin,
    max: +el.dataset.viewXMax,
  }));
  const dCenter = (dRegions[1].min + dRegions[1].max) / 2;
  await page.mouse.move(
    dBox.x +
      initialDBounds.left +
      ((dCenter - initialDBounds.min) /
        (initialDBounds.max - initialDBounds.min)) *
        initialDBounds.width,
    dBox.y + dBox.height * 0.55,
  );
  await page.mouse.wheel(0, -1200);
  await page.waitForTimeout(100);
  const dBounds = await pattern.evaluate((el) => ({
    left: +el.dataset.plotLeft,
    width: +el.dataset.plotWidth,
    min: +el.dataset.viewXMin,
    max: +el.dataset.viewXMax,
  }));
  const dEdge =
    dBox.x +
    dBounds.left +
    ((dRegions[1].min - dBounds.min) / (dBounds.max - dBounds.min)) *
      dBounds.width;
  const delta = (2 / dBounds.width) * (dBounds.max - dBounds.min);
  await page.mouse.move(dEdge, dBox.y + dBox.height * 0.55);
  await page.mouse.down();
  await page.mouse.move(dEdge + 2, dBox.y + dBox.height * 0.55, { steps: 5 });
  await page.mouse.up();
  await ready();
  const angleFromD =
    (Math.asin(wavelength / (2 * (dRegions[1].min + delta))) * 360) / Math.PI;
  assert.ok(
    Math.abs((await invoke("state")).map.rois[1].max - angleFromD) < 1e-8,
    JSON.stringify({
      message: "d edge was not converted back to stored units",
      original,
      dRegions,
      dBounds,
      delta,
      angleFromD,
      after: (await invoke("state")).map.rois,
    }),
  );
  await click("Map pattern unit 2θ");
  assert.ok(
    +(await pattern.getAttribute("data-view-x-max")) < 40,
    "Unit change retained a viewport expressed in d spacing",
  );
  await page.getByLabel("Show map layer B", { exact: true }).click();
  await ready();
  // A stationary click outside the region recenters it without changing its width.
  const beforeCenter = (await invoke("state")).map.rois[1];
  const centerBox = await pattern.boundingBox();
  const centerBounds = await pattern.evaluate((el) => ({
    left: +el.dataset.plotLeft,
    width: +el.dataset.plotWidth,
    min: +el.dataset.viewXMin,
    max: +el.dataset.viewXMax,
  }));
  const center = 11;
  await page.mouse.click(
    centerBox.x +
      centerBounds.left +
      ((center - centerBounds.min) / (centerBounds.max - centerBounds.min)) *
        centerBounds.width,
    centerBox.y + centerBox.height * 0.6,
  );
  await ready();
  const afterCenter = (await invoke("state")).map.rois[1];
  assert.ok(
    Math.abs((afterCenter.max + afterCenter.min) / 2 - center) <
      (centerBounds.max - centerBounds.min) / centerBounds.width,
  );
  assert.ok(
    Math.abs(
      afterCenter.max - afterCenter.min - (beforeCenter.max - beforeCenter.min),
    ) < 1e-8,
  );
  // Shared range handles must translate as a whole and resize from either edge.
  assert.ok(
    JSON.parse(await pattern.getAttribute("data-regions")).every(
      (r) => r.appearance === "range",
    ),
  );
  const plotPoint = async (value) => {
    const box = await pattern.boundingBox();
    const bounds = await pattern.evaluate((el) => ({
      left: +el.dataset.plotLeft,
      top: +el.dataset.plotTop,
      width: +el.dataset.plotWidth,
      height: +el.dataset.plotHeight,
      min: +el.dataset.viewXMin,
      max: +el.dataset.viewXMax,
    }));
    return {
      x:
        box.x +
        bounds.left +
        ((value - bounds.min) / (bounds.max - bounds.min)) * bounds.width,
      y: box.y + bounds.top + bounds.height * 0.55,
    };
  };
  const moveBefore = (await invoke("state")).map.rois[1];
  let point = await plotPoint((moveBefore.min + moveBefore.max) / 2);
  const beforeMovePixels = await scanCanvas.screenshot();
  const moveResponses = await page.evaluate(
    () => window.__mapRoiResponses ?? 0,
  );
  await page.mouse.move(point.x, point.y);
  await page.mouse.down();
  await page.mouse.move(point.x + 8, point.y, { steps: 6 });
  await page.waitForFunction(
    (count) => (window.__mapRoiResponses ?? 0) > count,
    moveResponses,
  );
  await ready();
  assert.ok(
    (await invoke("state")).map.rois[1].min > moveBefore.min,
    "Range body must update before pointer release",
  );
  assert.notDeepEqual(
    await scanCanvas.screenshot(),
    beforeMovePixels,
    "Map pixels must redraw during body translation",
  );
  await page.mouse.move(point.x + 18, point.y, { steps: 6 });
  await page.mouse.up();
  await ready();
  const moveAfter = (await invoke("state")).map.rois[1];
  assert.ok(
    moveAfter.min > moveBefore.min && moveAfter.max > moveBefore.max,
    "Range body did not translate",
  );
  assert.ok(
    Math.abs(
      moveAfter.max - moveAfter.min - (moveBefore.max - moveBefore.min),
    ) < 1e-8,
    "Range body changed its width",
  );
  point = await plotPoint(moveAfter.max);
  let releaseWindowEdit;
  windowEditGate = new Promise((resolve) => {
    releaseWindowEdit = resolve;
  });
  const resizeStarted = windowEditsStarted;
  const resizeResponses = await page.evaluate(
    () => window.__mapRoiResponses ?? 0,
  );
  const resizeScale = await pattern.evaluate(
    (canvas) =>
      (+canvas.dataset.viewXMax - +canvas.dataset.viewXMin) /
      +canvas.dataset.plotWidth,
  );
  await page.mouse.move(point.x, point.y);
  await page.mouse.down();
  await page.mouse.move(point.x + 2, point.y);
  await page.waitForTimeout(50);
  assert.equal(windowEditsStarted, resizeStarted + 1);
  const heldView = await pattern.getAttribute("data-view-x-min");
  await page.mouse.move(point.x + 10, point.y, { steps: 5 });
  assert.equal(
    windowEditsStarted,
    resizeStarted + 1,
    "Slow reductions must coalesce pointer positions behind one request",
  );
  assert.equal(
    await page.getByLabel("Edit windows", { exact: true }).isEnabled(),
    true,
  );
  await page.mouse.up();
  windowEditGate = null;
  releaseWindowEdit();
  await ready();
  await page.waitForFunction(
    (count) => (window.__mapRoiResponses ?? 0) >= count,
    resizeResponses + 2,
  );
  await ready();
  assert.ok(
    windowEditsStarted <= resizeStarted + 2,
    "Slow resize retained intermediate movements in the queue",
  );
  assert.equal(
    await pattern.getAttribute("data-view-x-min"),
    heldView,
    "Live responses shifted the pattern viewport during resizing",
  );
  const resized = (await invoke("state")).map.rois[1];
  assert.equal(
    resized.min,
    moveAfter.min,
    "Moving upper range edge changed lower edge",
  );
  assert.ok(resized.max > moveAfter.max, "Upper range edge did not resize");
  assert.ok(
    Math.abs(resized.max - (moveAfter.max + 10 * resizeScale)) < 1e-8,
    "Release did not retain the final pointer position",
  );
  // Escape restores the range even after an intermediate map was displayed.
  point = await plotPoint((resized.min + resized.max) / 2);
  const cancelResponses = await page.evaluate(
    () => window.__mapRoiResponses ?? 0,
  );
  await page.mouse.move(point.x, point.y);
  await page.mouse.down();
  await page.mouse.move(point.x + 8, point.y, { steps: 5 });
  await page.waitForFunction(
    (count) => (window.__mapRoiResponses ?? 0) > count,
    cancelResponses,
  );
  await ready();
  await page.keyboard.press("Escape");
  await page.mouse.up();
  await ready();
  assert.deepEqual(
    (await invoke("state")).map.rois[1],
    resized,
    "Escape did not restore the range from before the drag",
  );
  // A move and Escape in the same frame must discard the unsent position.
  const beforeFastCancel = windowEditsStarted;
  await page.mouse.move(point.x, point.y);
  await page.mouse.down();
  await pattern.evaluate((canvas, point) => {
    canvas.dispatchEvent(
      new PointerEvent("pointermove", {
        clientX: point.x + 8,
        clientY: point.y,
        bubbles: true,
        pointerId: 1,
        buttons: 1,
      }),
    );
    canvas.dispatchEvent(
      new KeyboardEvent("keydown", { key: "Escape", bubbles: true }),
    );
  }, point);
  await page.mouse.up();
  await page.waitForTimeout(50);
  await ready();
  assert.equal(
    windowEditsStarted,
    beforeFastCancel,
    "Escape retained an unsent pointer position",
  );
  assert.deepEqual((await invoke("state")).map.rois[1], resized);
  const toolbar = page.getByRole("group", {
    name: "Map pattern controls",
    exact: true,
  });
  const toolbarBox = await toolbar.boundingBox(),
    plotBox = await pattern.boundingBox();
  assert.ok(
    toolbarBox.x >= plotBox.x + plotBox.width - 1,
    "Pattern controls are not beside the plot",
  );
  assert.ok(
    toolbarBox.height > toolbarBox.width * 3,
    "Pattern controls are not a vertical strip",
  );
  for (const button of [
    toolbar.getByRole("button", { name: "Map pattern unit 2θ", exact: true }),
  ]) {
    assert.equal(
      await button.evaluate((el) => getComputedStyle(el).backgroundColor),
      "rgba(0, 0, 0, 0)",
      "Plot button retained its pill background",
    );
    assert.equal(
      await button.evaluate((el) => getComputedStyle(el).borderRadius),
      "1px",
    );
  }
  assert.equal(await page.locator(".map-layers .map-note").count(), 0);
  await click("Square root map pattern intensity");
  assert.equal(await pattern.getAttribute("data-intensity-scale"), "sqrt");
  await click("Logarithmic map pattern intensity");
  assert.equal(await pattern.getAttribute("data-intensity-scale"), "log");
  await click("Logarithmic map pattern intensity");
  assert.equal(await pattern.getAttribute("data-intensity-scale"), "linear");
  await click("Show pattern windows");
  assert.deepEqual(JSON.parse(await pattern.getAttribute("data-regions")), []);
  await click("Show pattern windows");
  const storedBeforeMask = (await invoke("state")).pattern;
  await page.getByLabel("Map use mask", { exact: true }).click();
  await ready();
  await page.waitForTimeout(100);
  assert.deepEqual(
    (await invoke("state")).pattern,
    storedBeforeMask,
    "Mask display silently replaced the stored map pattern",
  );
  await page.getByLabel("Map use mask", { exact: true }).click();
  await ready();
  await page.getByLabel("Map transparent mask", { exact: true }).click();
  await ready();
  assert.equal((await invoke("state")).state.transparentMask, true);
  await page.getByLabel("Map transparent mask", { exact: true }).click();
  await ready();
  await page.getByLabel("Layer Ratio name", { exact: true }).fill("Contrast");
  await page.getByLabel("Layer Ratio name", { exact: true }).press("Enter");
  await ready();
  assert.equal((await invoke("state")).map.expressions.Contrast, "A/B");
  await page.getByLabel("Layer Contrast name", { exact: true }).fill("Ratio");
  await page.getByLabel("Layer Contrast name", { exact: true }).press("Enter");
  await ready();
  await page.getByRole("tab", { name: "Points", exact: true }).click();
  assert.equal(
    await page
      .locator(".map-toolbar")
      .getByRole("button", { name: "Live map", exact: true })
      .count(),
    0,
  );
  assert.equal(
    await page
      .getByRole("button", { name: "Load map images", exact: true })
      .count(),
    0,
  );
  assert.equal(
    await page
      .getByRole("button", { name: "Load processed batch…", exact: true })
      .count(),
    0,
  );
  assert.ok(
    await page
      .locator(".map-controls")
      .getByRole("button", { name: "Live map", exact: true })
      .isVisible(),
  );
  await click("Live map");
  await page.waitForTimeout(1450);
  assert.ok(requests.includes("map_poll"));
  await click("Live map");
  await click("Edit windows");
  const before = await pattern.getAttribute("data-view-x-max");
  await pattern.hover();
  await page.mouse.wheel(0, -150);
  await page.waitForTimeout(80);
  assert.notEqual(await pattern.getAttribute("data-view-x-max"), before);
  const mapCanvas = page.locator(
    '[data-testid="scan-map"] [data-testid="detector-canvas"]',
  );
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
  await page.getByRole("tab", { name: "Points", exact: true }).click();
  const options = page
    .getByRole("listbox", { name: "Scan arrangement" })
    .getByRole("option");
  await options.nth(0).click();
  await ready();
  await options.nth(0).press("ArrowDown");
  await ready();
  await options.nth(1).press("ArrowDown");
  await ready();
  assert.equal(
    (await invoke("state")).map.selectedSlot,
    2,
    "Arrow selection did not follow keyboard focus",
  );
  const pointOrder = (await invoke("state")).map.slots;
  await options.nth(0).dragTo(options.nth(2));
  await ready();
  const moved = (await invoke("state")).map.slots;
  assert.equal(moved[2], pointOrder[0]);
  await click("Insert blank");
  const withBlank = await invoke("state");
  assert.ok(withBlank.map.slots.includes(null));
  await click("Exclude point");
  assert.ok((await invoke("state")).map.excluded.length > 0);
  await click("Include point");
  assert.equal((await invoke("state")).map.excluded.length, 0);
  assert.equal(
    await page.getByText("Reintegrate selected image", { exact: true }).count(),
    0,
  );
  assert.equal(
    await page.locator(".map-points-section > .map-note").count(),
    0,
  );
  const normalizeButton = settingsButton;
  await normalizeButton.click();
  const normalizationDialog = settingsDialog;
  assert.ok(await normalizationDialog.isVisible());
  const dialogBounds = await normalizationDialog.boundingBox();
  assert.ok(
    dialogBounds.width <= 350 && dialogBounds.height <= 320,
    "Map settings dialog is not compact",
  );
  const gearBounds = await settingsButton.boundingBox();
  assert.ok(
    Math.abs(
      dialogBounds.x + dialogBounds.width - gearBounds.x - gearBounds.width,
    ) <= 2,
    "Map settings is not aligned to its gear button",
  );
  assert.ok(
    dialogBounds.y >= gearBounds.y + gearBounds.height &&
      dialogBounds.y - gearBounds.y - gearBounds.height <= 8,
    "Map settings did not open next to its trigger",
  );
  const referenceFile = normalizationDialog.getByLabel(
    "Normalization reference",
    { exact: true },
  );
  const referenceMap = (await invoke("state")).map;
  const referenceSlot = referenceMap.slots.findIndex(
    (point, slot) => point !== null && point !== slot,
  );
  assert.ok(
    referenceSlot >= 0,
    "Reference fixture must include rearranged points",
  );
  const referencePoint = referenceMap.slots[referenceSlot];
  await referenceFile.selectOption(String(referencePoint));
  assert.equal(
    await referenceFile.locator("option:checked").textContent(),
    `${referenceSlot + 1} · ${referenceMap.labels[referenceSlot]}`,
  );
  for (let slot = 0; slot < referenceMap.slots.length; slot++) {
    const option = referenceFile.locator("option").nth(slot);
    assert.ok((await option.textContent()).startsWith(`${slot + 1} · `));
    assert.equal(
      await option.evaluate((el) => el.disabled),
      referenceMap.slots[slot] === null,
      `Reference entry ${slot + 1} has the wrong blank-cell state`,
    );
  }
  const minimum = normalizationDialog.getByLabel("Normalization minimum", {
    exact: true,
  });
  const maximum = normalizationDialog.getByLabel("Normalization maximum", {
    exact: true,
  });
  await minimum.fill("");
  assert.equal(await minimum.inputValue(), "");
  await minimum.fill("2");
  await minimum.press("Tab");
  assert.ok(await maximum.evaluate((el) => el === document.activeElement));
  await maximum.fill("8");
  const rangeUnit = normalizationDialog.getByLabel("Normalization unit", {
    exact: true,
  });
  const initialUnit = await rangeUnit.inputValue();
  const alternateUnit = initialUnit === "q_A^-1" ? "d_A" : "q_A^-1";
  await rangeUnit.selectOption(alternateUnit);
  await rangeUnit.selectOption(initialUnit);
  assert.ok(Math.abs(Number(await minimum.inputValue()) - 2) < 1e-10);
  assert.ok(Math.abs(Number(await maximum.inputValue()) - 8) < 1e-10);
  await page.screenshot({
    path: path.join(artifacts, "map-settings-range.png"),
  });
  await click("Normalize");
  assert.equal((await invoke("state")).map.normalized, true);
  assert.equal(
    (await invoke("state")).map.normalizationReference,
    referencePoint,
    "Reference file selection used its displayed row as the stored pattern index",
  );
  await normalizationDialog
    .getByRole("button", { name: "Close", exact: true })
    .click();
  await options.first().click();
  await ready();
  const normalizedSelection = await invoke("state");
  const expectedNormalized = await invoke("map_select", {
    index: normalizedSelection.map.selected,
    reintegrate: false,
  });
  assert.deepEqual(
    normalizedSelection.pattern,
    expectedNormalized.pattern,
    "Automatic selection replaced the normalized pattern with a raw reintegration",
  );
  await normalizeButton.click();
  assert.equal(await referenceFile.inputValue(), String(referencePoint));
  await click("Restore original");
  assert.equal((await invoke("state")).map.normalized, false);
  await normalizationDialog
    .getByLabel("Normalization source", { exact: true })
    .selectOption("window");
  const chosenWindow = await normalizationDialog
    .getByLabel("Normalization window", { exact: true })
    .inputValue();
  await click("Normalize");
  assert.equal(
    (await invoke("state")).map.normalizationCoordinates.window,
    chosenWindow,
  );
  await page.screenshot({
    path: path.join(artifacts, "map-settings-window.png"),
  });
  await click("Restore original");
  await normalizationDialog
    .getByRole("button", { name: "Close", exact: true })
    .click();
  await page.waitForFunction(
    () => !document.querySelector(".map-settings-dialog"),
  );
  assert.ok(
    await normalizeButton.evaluate((el) => el === document.activeElement),
    "Closing normalization did not restore focus",
  );
  await normalizeButton.click();
  await page.keyboard.press("Escape");
  await page.waitForFunction(
    () => !document.querySelector(".map-settings-dialog"),
  );
  assert.ok(
    await normalizeButton.evaluate((el) => el === document.activeElement),
    "Escape did not return focus to normalization",
  );
  await settingsButton.click();
  await page.mouse.click(80, 500);
  await page.waitForFunction(
    () => !document.querySelector(".map-settings-dialog"),
  );
  assert.ok(
    await settingsButton.evaluate((el) => el === document.activeElement),
    "Outside dismissal did not return focus to the gear",
  );
  await click("Save PNG…");
  await click("Save map data…");
  await page.getByLabel("Map layer", { exact: true }).selectOption("Ratio");
  await ready();
  await click("Save project");
  await click("Expand map");
  assert.equal(await page.locator(".map-detector-panel").count(), 0);
  await click("Dock detector / pattern");
  await page.getByLabel("Smooth map", { exact: true }).click();
  await page.getByLabel("Map contours", { exact: true }).click();
  await page.waitForTimeout(500);
  assert.ok(requests.includes("map_display"));
  await page.getByLabel("Smooth map", { exact: true }).click();
  await page.getByLabel("Map contours", { exact: true }).click();
  await page.getByRole("tab", { name: "Grid", exact: true }).click();
  await setInterfaceTextSize(page, true);
  assert.equal(
    await page
      .locator(".map-controls input[type=number]")
      .first()
      .evaluate((el) => getComputedStyle(el).fontSize),
    "16px",
  );
  await setInterfaceTextSize(page, false);
  await page.getByRole("tab", { name: "Points", exact: true }).click();
  await page.screenshot({
    path: path.join(artifacts, "map-points-controls.png"),
    fullPage: true,
  });
  await page.getByRole("tab", { name: "Grid", exact: true }).click();
  await page.screenshot({
    path: path.join(artifacts, "map-grid-controls.png"),
    fullPage: true,
  });
  await page.getByRole("tab", { name: "Layers", exact: true }).click();
  await page.getByLabel("Map layer", { exact: true }).selectOption("Ratio");
  await ready();
  await page.waitForTimeout(180);
  await page.screenshot({
    path: path.join(artifacts, "map-desktop.png"),
    fullPage: true,
  });
  await page.setViewportSize({ width: 1000, height: 760 });
  await page.waitForTimeout(100);
  const mapBounds = await page.locator(".map-task-panel").boundingBox();
  const tableBounds = await page
    .getByRole("table", { name: "Pattern windows", exact: true })
    .boundingBox();
  assert.ok(
    tableBounds.x >= mapBounds.x &&
      tableBounds.x + tableBounds.width <= mapBounds.x + mapBounds.width,
  );
  await page.getByRole("tab", { name: "Image", exact: true }).click();
  assert.ok(
    await page
      .locator('.map-detector-panel [data-testid="detector-canvas"]')
      .isVisible(),
  );
  await page.getByRole("tab", { name: "Layers", exact: true }).click();
  await page.waitForTimeout(180);
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
  await page.setViewportSize({ width: 1000, height: 700 });
  const heightDivider = page.getByRole("separator", {
    name: "Detector and pattern heights",
    exact: true,
  });
  await heightDivider.focus();
  for (let i = 0; i < 6; i++) await heightDivider.press("ArrowUp");
  for (const tab of ["Points", "Layers", "Grid"]) {
    await page.getByRole("tab", { name: tab, exact: true }).click();
    await page.waitForTimeout(40);
    const panel = page.locator("#map-tab-content");
    const surface =
      tab === "Points"
        ? page.getByRole("listbox", { name: "Scan arrangement" })
        : panel;
    const scroll = await surface.evaluate((el) => ({
      overflow: el.scrollHeight > el.clientHeight,
      reserved: el.offsetWidth - el.clientWidth,
      track: getComputedStyle(el, "::-webkit-scrollbar").width,
      fieldsFit: [...el.querySelectorAll("input, select, button")]
        .filter((field) => field.getBoundingClientRect().width > 0)
        .every(
          (field) =>
            field.getBoundingClientRect().right <=
            el.getBoundingClientRect().left +
              el.clientLeft +
              el.clientWidth +
              1,
        ),
    }));
    assert.ok(scroll.overflow, `${tab} fixture did not exercise overflow`);
    assert.ok(
      scroll.reserved >= 10 && scroll.track === "10px",
      `${tab} scrollbar was not visible immediately`,
    );
    assert.ok(scroll.fieldsFit, `${tab} controls overlapped the scrollbar`);
    if (tab === "Points") {
      const verifyPointLayout = async () => {
        assert.equal(
          await panel.evaluate((el) => el.scrollHeight > el.clientHeight + 1),
          false,
          "Points acquired a second scrolling surface",
        );
        const actions = page.getByRole("toolbar", {
          name: "Point arrangement actions",
        });
        const toolbarBox = await actions.boundingBox();
        const listBox = await surface.boundingBox();
        assert.ok(
          toolbarBox.y + toolbarBox.height <= listBox.y + 1,
          "Point actions are not above the file list",
        );
        const buttonTops = await actions
          .locator("button")
          .evaluateAll((buttons) =>
            buttons.map((button) => button.getBoundingClientRect().top),
          );
        assert.ok(
          Math.max(...buttonTops) - Math.min(...buttonTops) < 1,
          "Point actions no longer fit in one row",
        );
        const alignment = await surface
          .getByRole("option")
          .evaluateAll((rows) =>
            rows.map((row) => ({
              numberRight: row.children[0].getBoundingClientRect().right,
              nameLeft: row.children[1].getBoundingClientRect().left,
            })),
          );
        assert.ok(
          alignment.length >= 10,
          "Point alignment fixture needs two-digit indices",
        );
        for (const row of alignment) {
          assert.ok(
            Math.abs(row.numberRight - alignment[0].numberRight) < 1,
            "Point numbers do not share a column",
          );
          assert.ok(
            Math.abs(row.nameLeft - alignment[0].nameLeft) < 1,
            "Point filenames do not share a column",
          );
        }
      };
      await verifyPointLayout();
      await surface.hover();
      await page.mouse.wheel(0, 300);
      await page.waitForTimeout(150);
      assert.ok(
        await surface.evaluate((el) => el.scrollTop > 0),
        "The file list did not scroll",
      );
      assert.equal(
        await panel.evaluate((el) => el.scrollTop),
        0,
        "Scrolling the file list moved the Points panel",
      );
      await page
        .getByRole("toolbar", { name: "Point arrangement actions" })
        .hover();
      await page.mouse.wheel(0, 300);
      await page.waitForTimeout(100);
      assert.equal(
        await panel.evaluate((el) => el.scrollTop),
        0,
        "Scrolling over actions moved the Points panel",
      );
      await page.screenshot({
        path: path.join(artifacts, "map-points-short-panel.png"),
      });
      await setInterfaceTextSize(page, true);
      await verifyPointLayout();
      await page.screenshot({
        path: path.join(artifacts, "map-points-short-panel-large-text.png"),
      });
      await setInterfaceTextSize(page, false);
    }
  }
  await heightDivider.press("Home");
  await page.setViewportSize({ width: 1600, height: 1000 });
  await click("Open project");
  assert.equal((await invoke("state")).map.active, "Ratio");
  await click("Calibration");
  assert.equal(
    await page
      .getByRole("tab", { name: "Step 2: Pick rings", exact: true })
      .count(),
    1,
  );
  // Exercise the GUI's pending-file check and serialized append, not only its Live toggle.
  const liveFolder = await mkdtemp(path.join(artifacts, "map-live-"));
  try {
    const firstImage = path.join(liveFolder, "scan_001.tif");
    await copyFile(
      path.join(root, "dioptas/tests/data/CeO2_Pilatus1M.tif"),
      firstImage,
    );
    assert.equal((await invoke("map_load", { paths: [firstImage] })).ok, true);
    await page.reload();
    await ready();
    await click("Map");
    await click("Live map");
    await copyFile(firstImage, path.join(liveFolder, "scan_002.tif"));
    await page.waitForFunction(
      () =>
        document.querySelectorAll('.map-file-list [role="option"]').length ===
        2,
      null,
      { timeout: 45000 },
    );
    await ready();
    const liveState = await invoke("state");
    assert.equal(
      liveState.map.selected,
      1,
      "Live did not follow the appended point",
    );
    assert.equal(liveState.map.points, 2);
    assert.equal(liveState.state.hasImage, true);
    await click("Live map");
    // Automatic reintegration must retain stored-pattern access when raw files disappear.
    await rm(firstImage);
    await page
      .getByRole("listbox", { name: "Scan arrangement" })
      .getByRole("option")
      .first()
      .click();
    await ready();
    const storedOnly = await invoke("state");
    assert.equal(storedOnly.state.hasImage, false);
    assert.ok(
      storedOnly.pattern?.y.length > 0,
      "Missing raw source prevented stored-pattern selection",
    );
  } finally {
    await rm(liveFolder, { recursive: true, force: true });
  }
  assert.deepEqual(errors, []);
  await writeFile(
    path.join(artifacts, "map-smoke.json"),
    JSON.stringify(
      {
        ok: true,
        points: 9,
        linkedSelection: true,
        sharedCalibrationCake: true,
        quietSelection: true,
        stableScanPreview: true,
        rapidSelectionQueue: true,
        blankSelection: true,
        serpentine: true,
        windowDrag: true,
        liveAppend: true,
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
} catch (error) {
  await page.screenshot({
    path: path.join(artifacts, "map-failure.png"),
    fullPage: true,
  });
  throw error;
} finally {
  await browser.close();
  host.stdin.end();
  await writeFile(path.join(artifacts, "map-smoke.log"), logs.join(""));
}
