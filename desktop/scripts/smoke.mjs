import {
  selectCalibrationRing,
  verifyCalibrationRingPicker,
  verifyFiftyRingPicker,
} from "./calibration_ring_picker.mjs";
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
  verifyCakeMarginNavigation,
} from "./plot_navigation.mjs";

import {
  openIntegrationSettings,
  verifyIntegrationControls,
} from "./integration_controls.mjs";
import { verifyIntegrationLayout } from "./integration_layout.mjs";
import {
  verifyCalibrationSizes,
  verifyCalibrationFits,
} from "./calibration_layout.mjs";
import { verifyCalibrationSetup } from "./calibration_setup.mjs";
import { verifyCalibrationWorkspace } from "./calibration_workspace.mjs";
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
  localStorage.setItem("dioptas-accent-v2", "green");
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
async function verifyCakeCalibrantLines(snapshot) {
  const lines = page.getByLabel("Show calibrant lines", { exact: true });
  const cakeCanvas = page.getByTestId("cake-canvas");
  await lines.uncheck();
  await cakeCanvas.evaluate((canvas) => {
    window.__cakeWithoutCalibrants = canvas
      .getContext("2d")
      .getImageData(0, 0, canvas.width, canvas.height).data;
  });
  await lines.check();
  const result = await cakeCanvas.evaluate(
    (canvas, { rings, range }) => {
      const d = canvas.dataset;
      const current = canvas
        .getContext("2d")
        .getImageData(0, 0, canvas.width, canvas.height).data;
      const baseline = window.__cakeWithoutCalibrants;
      const visible = rings
        .map(({ twoTheta }) => {
          const pixel =
            ((twoTheta - range[0]) / (range[1] - range[0])) * +d.fullWidth;
          return (
            +d.plotLeft +
            ((pixel - +d.viewXMin) / (+d.viewXMax - +d.viewXMin)) * +d.plotWidth
          );
        })
        .filter(
          (x) => x > +d.plotLeft + 3 && x < +d.plotLeft + +d.plotWidth - 3,
        );
      const changed = visible.filter((x) =>
        [-1, 0, 1].some((dx) => {
          const y = Math.floor(+d.plotTop + +d.plotHeight * 0.5);
          const i = (y * canvas.width + Math.floor(x) + dx) * 4;
          return [0, 1, 2].some((c) => current[i + c] !== baseline[i + c]);
        }),
      );
      delete window.__cakeWithoutCalibrants;
      return { visible: visible.length, changed: changed.length };
    },
    {
      rings: snapshot.state.calibration.rings,
      range: snapshot.cake.radialRange,
    },
  );
  assert.ok(result.visible > 2, "Fixture must show several calibrant rings");
  assert.equal(
    result.changed,
    result.visible,
    "Cake guides must render at the calibrant's actual 2θ positions",
  );
}
try {
  await page.goto("file://" + path.join(root, "dioptas/desktop/ui/index.html"));
  await waitReady();
  if (process.argv.includes("--dioptrin")) {
    await page.getByRole("button", { name: "Settings", exact: true }).click();

    await page
      .getByLabel("Processing engine", { exact: true })
      .selectOption("dioptrin");
    await waitReady();
    await page.keyboard.press("Escape");
  }
  assert.equal(
    await page.getByLabel("Accent color", { exact: true }).count(),
    0,
  );
  assert.equal(
    await page
      .locator(".app")
      .evaluate((el) =>
        getComputedStyle(el).getPropertyValue("--accent").trim(),
      ),
    "#ff9500",
  );
  await setInterfaceTextSize(page, true);
  assert.equal(
    await page.locator(".app").getAttribute("data-text-size"),
    "large",
  );
  await page.getByRole("button", { name: "Settings", exact: true }).click();
  assert.ok(
    (await page
      .getByLabel("Processing engine", { exact: true })
      .evaluate((el) => parseFloat(getComputedStyle(el).fontSize))) >= 17,
  );
  assert.equal(
    await page
      .locator("#settings-panel-0")
      .getByLabel("Processing engine", { exact: true })
      .isVisible(),
    true,
  );
  const engineOptions = await page
    .getByLabel("Processing engine", { exact: true })
    .locator("option")
    .evaluateAll((options) =>
      options.map((option) => ({
        id: option.value,
        disabled: option.disabled,
      })),
    );
  assert.deepEqual(
    engineOptions,
    (await invoke("state")).state.calibration.engines.map((engine) => ({
      id: engine.id,
      disabled: !engine.available,
    })),
  );
  await page
    .getByRole("button", { name: "Close settings", exact: true })
    .click();
  assert.equal(
    await page.getByLabel("Processing engine", { exact: true }).count(),
    0,
  );
  await setInterfaceTextSize(page, false);
  const settingsButton = page.getByRole("button", {
    name: "Settings",
    exact: true,
  });
  const settingsBox = await settingsButton.boundingBox();
  const navigationBox = await page
    .getByRole("navigation", { name: "Workspace modes" })
    .boundingBox();
  assert.ok(
    settingsBox.y > navigationBox.y + navigationBox.height * 0.75,
    "Settings belongs at the bottom of the left sidebar",
  );
  await settingsButton.click();
  await page.getByRole("button", { name: "Larger", exact: true }).click();
  assert.equal(
    await page.locator(".app").getAttribute("data-text-size"),
    "large",
  );
  await page.getByRole("button", { name: "Standard", exact: true }).click();
  await page.screenshot({ path: path.join(artifacts, "settings.png") });
  await page.keyboard.press("Escape");
  assert.equal(
    await page.getByRole("region", { name: "Settings", exact: true }).count(),
    0,
  );
  await page.screenshot({ path: path.join(artifacts, "empty-workspace.png") });
  await verifyCalibrationSizes(page, {
    screenshots: artifacts,
    prefix: "empty-calibration-sidebar",
  });
  await page
    .getByRole("button", { name: "Explore example", exact: true })
    .click();
  await page.getByTestId("detector-canvas").waitFor();
  await waitReady();
  let current = await invoke("state");
  assert.equal(
    current.state.calibrated,
    false,
    "Example must start without an imported calibration",
  );
  assert.equal(current.state.calibration.picks.length, 0);
  const calibrationSetupChecks = await verifyCalibrationSetup(
    page,
    invoke,
    artifacts,
    waitReady,
  );
  const detectorGeometryChecks = await verifyDetectorGeometry(page, invoke);
  const imageControlChecks = await verifyImageControls(
    page,
    invoke,
    pixelRequests,
  );
  await verifyCalibrationNavigation(page);
  assert.equal(
    (await invoke("state")).state.calibration.picks.length,
    0,
    "Dragging in peak-picking mode must not add peaks",
  );
  await page.screenshot({
    path: path.join(artifacts, "calibration-start.png"),
  });

  const detector = page.getByTestId("detector-canvas");
  // Real CeO2 peak seeds, identified against the existing reference fixture.
  // Only measured-image clicks enter the new fit; no reference geometry does.
  const seeds = [
    [637, 564, 1],
    [671, 511, 2],
    [668, 703, 3],
    [350.5, 592.8, 1],
    [554.3, 367.9, 1],
  ];
  // Pick additional real-image groups to exercise scrolling at compact sizes;
  // remove the extras before running the existing scientific fit checks.
  const layoutSeeds = [...seeds, ...seeds, ...seeds];
  for (const [x, y, ring] of layoutSeeds) {
    await selectCalibrationRing(page, ring);
    const box = await detector.boundingBox();
    const view = await detector.evaluate((el) => ({
      left: +el.dataset.plotLeft,
      top: +el.dataset.plotTop,
      width: +el.dataset.plotWidth,
      height: +el.dataset.plotHeight,
      xMin: +el.dataset.viewXMin,
      xMax: +el.dataset.viewXMax,
      yMin: +el.dataset.viewYMin,
      yMax: +el.dataset.viewYMax,
    }));
    await page.mouse.click(
      box.x +
        view.left +
        ((x - view.xMin) / (view.xMax - view.xMin)) * view.width,
      box.y +
        view.top +
        ((view.yMax - y) / (view.yMax - view.yMin)) * view.height,
    );
    await waitReady();
    assert.equal(
      await page
        .getByLabel("Current calibrant ring", { exact: true })
        .getAttribute("data-ring"),
      String(ring + 1),
      "Automatic increase must visibly identify the next picking ring",
    );
  }
  await verifyCalibrationSizes(page, {
    screenshots: artifacts,
    prefix: "picked-sidebar",
    expectedGroups: layoutSeeds.length,
  });
  const savedPeakGroups = (await invoke("state")).state.calibration.picks;
  await page
    .getByRole("button", { name: "Save picked peaks", exact: true })
    .click();
  await waitReady();
  const peakFile = JSON.parse(
    await readFile(path.join(artifacts, "calibration-peaks.json"), "utf8"),
  );
  assert.deepEqual(peakFile.groups, savedPeakGroups);
  const selectAllGroups = page.getByRole("checkbox", {
    name: "Select all peak groups",
    exact: true,
  });
  await selectAllGroups.check();
  assert.equal(
    await page.locator('.peak-row input[type="checkbox"]:checked').count(),
    layoutSeeds.length,
  );
  await page.getByLabel("Select peak group 1", { exact: true }).uncheck();
  assert.ok(await selectAllGroups.evaluate((el) => el.indeterminate));
  await selectAllGroups.check();
  assert.ok(await selectAllGroups.isChecked());
  await selectAllGroups.uncheck();
  assert.equal(
    await page.locator('.peak-row input[type="checkbox"]:checked').count(),
    0,
  );
  assert.ok(
    await page
      .getByRole("button", { name: "Delete selected", exact: true })
      .isDisabled(),
  );
  await page
    .getByRole("button", { name: "Clear calibration peaks", exact: true })
    .click();
  const clearPeaksDialog = page.getByRole("dialog", {
    name: "Clear all peaks?",
    exact: true,
  });
  await clearPeaksDialog.waitFor();
  assert.equal(
    (await invoke("state")).state.calibration.picks.length,
    layoutSeeds.length,
    "Opening Clear all does not remove peaks",
  );
  assert.ok(
    await clearPeaksDialog
      .getByRole("button", { name: "Cancel", exact: true })
      .evaluate((el) => el === document.activeElement),
    "Cancel receives focus by default",
  );
  const confirmationBounds = await clearPeaksDialog.boundingBox();
  const triggerBounds = await page
    .getByRole("button", {
      name: "Clear calibration peaks",
      exact: true,
    })
    .boundingBox();
  assert.ok(
    Math.abs(
      confirmationBounds.y - (triggerBounds.y + triggerBounds.height + 8),
    ) <= 1 &&
      Math.abs(
        confirmationBounds.x +
          confirmationBounds.width -
          (triggerBounds.x + triggerBounds.width),
      ) <= 1,
    "Confirmation opens directly below the Clear all icon, aligned to its right edge",
  );
  await page.screenshot({
    path: path.join(artifacts, "clear-peaks-confirmation.png"),
  });
  await clearPeaksDialog
    .getByRole("button", { name: "Cancel", exact: true })
    .click();
  assert.equal(
    (await invoke("state")).state.calibration.picks.length,
    layoutSeeds.length,
    "Cancel preserves every peak group",
  );
  const clearPeaksButton = page.getByRole("button", {
    name: "Clear calibration peaks",
    exact: true,
  });
  assert.ok(
    await clearPeaksButton.evaluate((el) => el === document.activeElement),
  );
  await clearPeaksButton.click();
  await page.mouse.click(triggerBounds.x - 80, triggerBounds.y + 15);
  assert.ok(await clearPeaksDialog.isHidden());
  assert.equal(
    (await invoke("state")).state.calibration.picks.length,
    layoutSeeds.length,
    "Clicking outside dismisses the confirmation without changing peaks",
  );
  await clearPeaksButton.click();
  await page.keyboard.press("Escape");
  assert.ok(await clearPeaksDialog.isHidden());
  await clearPeaksButton.click();
  await page.keyboard.press("Enter");
  assert.ok(await clearPeaksDialog.isHidden());
  assert.equal(
    (await invoke("state")).state.calibration.picks.length,
    layoutSeeds.length,
    "Escape and default Enter preserve every peak group",
  );
  await clearPeaksButton.click();
  await clearPeaksDialog
    .getByRole("button", { name: "Clear all", exact: true })
    .click();
  await waitReady();
  assert.equal((await invoke("state")).state.calibration.picks.length, 0);
  assert.ok(await selectAllGroups.isDisabled());
  assert.ok(
    await page
      .getByRole("button", { name: "Save picked peaks", exact: true })
      .isDisabled(),
  );
  await page
    .getByRole("button", { name: "Load picked peaks", exact: true })
    .click();
  await waitReady();
  assert.deepEqual(
    (await invoke("state")).state.calibration.picks,
    savedPeakGroups,
  );
  assert.equal(
    await page.locator('.peak-row input[type="checkbox"]:checked').count(),
    0,
  );
  await page.getByRole("button", { name: "Undo", exact: true }).click();
  await waitReady();
  assert.equal((await invoke("state")).state.calibration.picks.length, 0);
  await page.getByRole("button", { name: "Redo", exact: true }).click();
  await waitReady();
  assert.equal(
    (await invoke("state")).state.calibration.picks.length,
    layoutSeeds.length,
  );
  for (const checkbox of await page
    .locator('.peak-row input[type="checkbox"]')
    .all())
    await checkbox.uncheck();
  for (let index = seeds.length; index < layoutSeeds.length; index++)
    await page
      .getByLabel(`Select peak group ${index + 1}`, { exact: true })
      .check();
  await page
    .getByRole("button", { name: "Delete selected", exact: true })
    .click();
  await waitReady();
  assert.equal(
    (await invoke("state")).state.calibration.picks.length,
    seeds.length,
  );
  const originalRing = (await invoke("state")).state.calibration.picks[0].ring;
  await page.getByLabel("Ring assignment 1", { exact: true }).fill("3");
  await page.getByLabel("Ring assignment 1", { exact: true }).press("Tab");
  await waitReady();
  assert.equal((await invoke("state")).state.calibration.picks[0].ring, 3);
  await page.getByRole("button", { name: "Undo", exact: true }).click();
  await waitReady();
  assert.equal(
    (await invoke("state")).state.calibration.picks[0].ring,
    originalRing,
  );
  for (const checkbox of await page
    .locator('.peak-row input[type="checkbox"]')
    .all())
    await checkbox.uncheck();
  await page.getByLabel("Select peak group 1", { exact: true }).check();
  await page.getByLabel("Select peak group 2", { exact: true }).check();
  const beforeDeletion = (await invoke("state")).state.calibration.picks.length;
  await page
    .getByRole("button", { name: "Delete selected", exact: true })
    .click();
  await waitReady();
  assert.equal(
    (await invoke("state")).state.calibration.picks.length,
    beforeDeletion - 2,
  );
  await page.getByRole("button", { name: "Undo", exact: true }).click();
  await waitReady();
  assert.equal(
    (await invoke("state")).state.calibration.picks.length,
    beforeDeletion,
  );
  await page
    .getByRole("tab", { name: "Step 3: Calibrate", exact: true })
    .click();
  assert.equal(
    await page.getByLabel("Refine rotation 3", { exact: true }).isChecked(),
    true,
  );
  assert.equal(
    await page.getByLabel("Refine wavelength", { exact: true }).isChecked(),
    false,
  );
  assert.equal(
    await page
      .getByRole("button", { name: "Load custom calibrant…", exact: true })
      .isVisible(),
    true,
  );
  await verifyCalibrationSizes(page, {
    screenshots: artifacts,
    prefix: "calibrate-sidebar",
  });
  await page.getByLabel("Refine rotation 1", { exact: true }).uncheck();
  assert.equal(
    await page.getByLabel("Refine rotation 1", { exact: true }).isChecked(),
    false,
  );
  await page.getByLabel("Refine rotation 1", { exact: true }).check();
  await page.getByLabel("Number of rings", { exact: true }).fill("4");
  await page.getByLabel("Number of rings", { exact: true }).press("Tab");
  await waitReady();
  await page
    .getByLabel("Refinement peak-search algorithm", { exact: true })
    .selectOption("Blob");
  await waitReady();
  assert.equal(
    await page.getByLabel("Number of rings", { exact: true }).inputValue(),
    "4",
    "Algorithm selection must preserve the applied refinement options",
  );
  assert.equal(
    await page
      .getByRole("button", { name: "Apply refinement options", exact: true })
      .count(),
    0,
  );
  assert.equal(
    (await invoke("state")).state.calibration.workflow.numberOfRings,
    4,
  );
  const searchWidth = page.getByLabel("Search width Δ2θ · °", { exact: true });
  await searchWidth.fill("0.2");
  await searchWidth.press("Enter");
  await waitReady();
  assert.equal(
    (await invoke("state")).state.calibration.workflow.deltaTth,
    0.2,
  );
  await page
    .getByLabel("Refinement peak-search algorithm", { exact: true })
    .selectOption("Massif");
  await waitReady();
  await page.getByLabel("Automatic refinement", { exact: true }).uncheck();
  await waitReady();
  await page
    .getByLabel("Distance constraint value", { exact: true })
    .fill("203");
  await page
    .getByRole("tab", { name: "Step 2: Pick rings", exact: true })
    .click();
  await page
    .getByRole("tab", { name: "Step 3: Calibrate", exact: true })
    .click();
  assert.equal(
    await page
      .getByLabel("Distance constraint value", { exact: true })
      .inputValue(),
    "203",
    "Fit drafts survive visits to Peaks",
  );
  await page
    .getByLabel("Distance constraint value", { exact: true })
    .fill("200");
  await page
    .getByLabel("Wavelength constraint value", { exact: true })
    .fill("-0.5");
  await page.waitForFunction(
    () => document.querySelector(".fit-button").disabled,
  );
  assert.equal(
    await page
      .getByRole("button", { name: "Apply fit parameters", exact: true })
      .count(),
    0,
  );
  assert.equal(
    await page.getByRole("tab", { name: "Parameters", exact: true }).count(),
    0,
  );
  assert.equal(
    await page.getByRole("tab", { name: "Refinement", exact: true }).count(),
    0,
  );
  await page
    .getByLabel("Wavelength constraint value", { exact: true })
    .fill("0.406626");
  await page
    .getByRole("button", { name: "Calibrate", exact: true })
    .click();
  await page.getByTestId("pattern-canvas").waitFor({ timeout: 45000 });
  await waitReady();
  current = await invoke("state");
  assert.equal(current.state.calibrated, true);
  assert.ok(
    Math.abs(current.state.geometry.dist - 0.20865) < 0.003,
    JSON.stringify(current.state.geometry),
  );
  assert.ok(current.state.calibration.rmsDegrees < 0.03);
  assert.ok(current.rings.length > 2);
  await verifyCakeCalibrantLines(current);
  const cakeGuideCanvas = page.getByTestId("cake-canvas");
  const cakeGuideBounds = await cakeGuideCanvas.boundingBox();
  await page.mouse.move(
    cakeGuideBounds.x + cakeGuideBounds.width * 0.5,
    cakeGuideBounds.y + cakeGuideBounds.height * 0.5,
  );
  await page.mouse.wheel(0, -180);
  await verifyCakeCalibrantLines(current);
  await cakeGuideCanvas.dblclick({ button: "right" });
  assert.equal(await page.locator(".cake-panel .image-intensity").count(), 1);
  assert.equal(
    await page
      .locator(".detector-panel .image-intensity")
      .getAttribute("data-orientation"),
    "horizontal",
  );
  assert.equal(
    await page
      .locator(".cake-panel .image-intensity")
      .getAttribute("data-orientation"),
    "horizontal",
  );
  const detectorPlot = await detector.boundingBox(),
    detectorBar = await page.getByTestId("intensity-histogram").boundingBox();
  const cakePlot = await page.getByTestId("cake-canvas").boundingBox(),
    cakeBar = await page.getByTestId("cake-intensity-histogram").boundingBox();
  assert.ok(
    detectorBar.y < detectorPlot.y && cakeBar.y < cakePlot.y,
    "Multi-image colour/histogram bars belong above their images",
  );
  const detectorLimitsBeforeCake = [
    await detector.getAttribute("data-intensity-min"),
    await detector.getAttribute("data-intensity-max"),
  ];
  assert.equal(await detector.getAttribute("data-intensity-scale"), "linear");
  assert.equal(
    await page.getByTestId("cake-canvas").getAttribute("data-intensity-scale"),
    "linear",
  );
  const cakeBefore = await page
    .getByTestId("cake-canvas")
    .evaluate((el) => el.toDataURL());
  await page
    .getByRole("button", { name: "Cake histogram settings", exact: true })
    .click();
  await page
    .getByLabel("Cake image scale", { exact: true })
    .selectOption("log");
  assert.notEqual(
    await page.getByTestId("cake-canvas").evaluate((el) => el.toDataURL()),
    cakeBefore,
  );
  assert.equal(await detector.getAttribute("data-intensity-scale"), "linear");
  await page
    .getByLabel("Cake auto intensity mode", { exact: true })
    .selectOption("mean3std");
  await waitReady();
  const expectedCake = (
    await invoke("image_levels", {
      source: "cake",
      mode: "mean3std",
      percentile: 2.5,
      filter_gaps: true,
    })
  ).levels;
  await page.waitForFunction((expected) => {
    const el = document.querySelector('[data-testid="cake-canvas"]');
    return (
      +el.dataset.intensityMin === expected[0] &&
      +el.dataset.intensityMax === expected[1]
    );
  }, expectedCake);
  assert.deepEqual(
    [
      await detector.getAttribute("data-intensity-min"),
      await detector.getAttribute("data-intensity-max"),
    ],
    detectorLimitsBeforeCake,
  );
  await page
    .getByLabel("Cake histogram orientation", { exact: true })
    .selectOption("horizontal");
  await page
    .getByRole("button", { name: "Close cake display settings", exact: true })
    .click();
  await selectColorMap(page, "Cake color map", "viridis");
  assert.equal(
    await page
      .getByRole("button", { name: "Color map", exact: true })
      .getAttribute("data-color-map"),
    "grey",
  );
  await page.getByRole("tab", { name: "Fit2D", exact: true }).click();
  assert.equal(
    await page.getByLabel("Manual center x", { exact: true }).isVisible(),
    true,
  );
  await page
    .getByRole("tab", { name: "Step 2: Pick rings", exact: true })
    .click();
  await page
    .getByRole("tab", { name: "Step 4: Validate", exact: true })
    .click();
  assert.equal(
    await page
      .getByRole("tab", { name: "Fit2D", exact: true })
      .getAttribute("aria-selected"),
    "true",
    "Validate retains its selected tab after switching steps",
  );
  await page.getByRole("button", { name: "Integration", exact: true }).click();
  await page.getByRole("button", { name: "Calibration", exact: true }).click();
  assert.equal(
    await page
      .getByRole("tab", { name: "Fit2D", exact: true })
      .getAttribute("aria-selected"),
    "true",
    "Validate retains its selected tab after switching modes",
  );
  await page.getByRole("tab", { name: "pyFAI", exact: true }).click();
  assert.equal(
    await page.getByLabel("Manual rotation 3", { exact: true }).isVisible(),
    true,
  );
  await verifyCalibrationSizes(page, {
    tabs: ["pyFAI", "Fit2D"],
    screenshots: artifacts,
    prefix: "validation-sidebar",
  });
  await page.getByRole("tab", { name: "pyFAI", exact: true }).click();
  const rotation = page.getByLabel("Manual rotation 1", { exact: true });
  const originalRotation = await rotation.inputValue();
  await rotation.fill("0.01");
  await page.waitForFunction(
    () =>
      [...document.querySelectorAll("button")].find(
        (button) =>
          button.getAttribute("aria-label") === "Save .poni calibration",
      )?.disabled,
  );
  await page.getByRole("tab", { name: "Fit2D", exact: true }).click();
  await page.getByRole("tab", { name: "pyFAI", exact: true }).click();
  assert.equal(await rotation.inputValue(), "0.01");
  await verifyCalibrationSizes(page, {
    tabs: ["pyFAI", "Fit2D"],
    screenshots: artifacts,
    prefix: "validation-draft",
  });
  await page.getByRole("tab", { name: "pyFAI", exact: true }).click();
  await page
    .getByRole("button", { name: "Apply geometry", exact: true })
    .click();
  await waitReady();
  assert.ok(
    Math.abs((await invoke("state")).state.geometry.rot1 - 0.01) < 1e-10,
  );
  await rotation.fill(originalRotation);
  await page
    .getByRole("button", { name: "Apply geometry", exact: true })
    .click();
  await waitReady();
  assert.ok(
    Math.abs(
      (await invoke("state")).state.geometry.rot1 - Number(originalRotation),
    ) < 1e-10,
  );

  const ringPickerChecks = [
    await verifyCalibrationRingPicker(
      page,
      (await invoke("state")).state.calibration,
    ),
    await verifyFiftyRingPicker(page, invoke, artifacts, waitReady),
  ];
  const calibrationWorkspaceChecks = await verifyCalibrationWorkspace(
    page,
    invoke,
    artifacts,
    waitReady,
  );
  const scientificFit = {
    engine: current.state.calibration.engineLabel,
    distanceMm: current.state.geometry.dist * 1000,
    rmsDegrees: current.state.calibration.rmsDegrees,
  };
  await page
    .getByRole("button", { name: "Save .poni calibration", exact: true })
    .click();
  await waitReady();
  assert.match(
    await readFile(path.join(artifacts, "calibration.poni"), "utf8"),
    /Distance/,
  );
  await page.mouse.move(10, 10);
  // Inspection is explicit and available independently of the calibration tab.
  await page.getByLabel("Pick peaks", { exact: true }).uncheck();
  // A stationary validation click links image, cake, and the current radial unit.
  const fitBox = await detector.boundingBox();
  await page.mouse.click(
    fitBox.x + fitBox.width * 0.6,
    fitBox.y + fitBox.height * 0.45,
  );
  await waitReady();
  assert.ok(
    Number(
      await page
        .getByTestId("cake-canvas")
        .getAttribute("data-linked-position"),
    ) > 0,
  );
  assert.ok(
    Number(
      await page
        .getByTestId("pattern-canvas")
        .getAttribute("data-linked-position"),
    ) > 0,
  );
  await page.mouse.move(10, 10);
  await page.screenshot({ path: path.join(artifacts, "calibration-fit.png") });
  await setInterfaceTextSize(page, true);
  await page.screenshot({
    path: path.join(artifacts, "calibration-large-text.png"),
  });
  await setInterfaceTextSize(page, false);

  await page
    .getByRole("tab", { name: "Step 2: Pick rings", exact: true })
    .click();
  await selectCalibrationRing(page, 3);
  assert.equal(await detector.getAttribute("data-active-ring"), "3");
  await page.waitForFunction(() => {
    const pixels = document
      .querySelector('[data-testid="detector-canvas"]')
      .getContext("2d")
      .getImageData(
        0,
        0,
        document.querySelector('[data-testid="detector-canvas"]').width,
        document.querySelector('[data-testid="detector-canvas"]').height,
      ).data;
    let count = 0;
    for (let i = 0; i < pixels.length; i += 4)
      // The active ring is translucent; the compact numeric label alone need
      // not contain many fully opaque yellow pixels.
      if (pixels[i] > 200 && pixels[i + 1] > 180 && pixels[i + 2] < 140)
        count++;
    return count > 20;
  });
  await page.screenshot({
    path: path.join(artifacts, "calibration-ring-selected.png"),
  });
  await page
    .getByRole("tab", { name: "Step 4: Validate", exact: true })
    .click();
  const geometryBeforeReference = (await invoke("state")).state.geometry;
  await page
    .getByLabel("Validation calibrant", { exact: true })
    .selectOption("LaB6");
  await waitReady();
  await verifyCakeCalibrantLines(await invoke("state"));
  assert.deepEqual(
    (await invoke("state")).state.geometry,
    geometryBeforeReference,
  );
  await page
    .getByLabel("Validation calibrant", { exact: true })
    .selectOption("CeO2");
  await waitReady();
  await verifyCakeMarginNavigation(page);
  await page.getByRole("button", { name: "Integration", exact: true }).click();
  await page.getByTestId("cake-canvas").waitFor({ state: "attached" });
  const integrationLayoutChecks = await verifyIntegrationLayout(
    page,
    artifacts,
  );
  const pickCount = current.state.calibration.picks.length;
  assert.equal(
    await page
      .getByRole("button", { name: "Export pattern", exact: true })
      .count(),
    0,
  );
  const navigationChecks = [
    ...(await verifyPlotNavigation(page)),
    ...(await verifyWheelCapture(page)),
  ];
  const patternBox = await page.getByTestId("pattern-canvas").boundingBox();
  await page.mouse.move(
    patternBox.x + patternBox.width / 2,
    patternBox.y + patternBox.height / 2,
  );
  await page.waitForFunction(
    () =>
      document.querySelector('[data-testid="mouse-readout"]')?.dataset.plot ===
      "pattern",
  );
  assert.equal(
    await page.locator('.app-status [data-testid="mouse-readout"]').count(),
    1,
  );
  assert.equal(
    await page.locator(".views-grid .panel-footer, .plot-readout").count(),
    0,
  );
  await page
    .getByRole("group", { name: "Integration display", exact: true })
    .getByRole("button", { name: "Cake", exact: true })
    .click();
  const cakeCanvas = page.getByTestId("cake-canvas");
  await cakeCanvas.scrollIntoViewIfNeeded();
  const cakeBox = await cakeCanvas.boundingBox();
  await page.mouse.move(
    cakeBox.x + cakeBox.width / 2,
    cakeBox.y + cakeBox.height / 2,
  );
  await page.waitForFunction(
    () =>
      document.querySelector('[data-testid="mouse-readout"]')?.dataset.plot ===
      "cake",
  );
  assert.match(
    await page.getByTestId("mouse-readout").innerText(),
    /2θ .*χ .*I /,
  );
  const afterNavigation = await invoke("state");
  assert.equal(
    afterNavigation.state.calibration.picks.length,
    pickCount,
    "Rectangle dragging and right navigation do not pick calibration peaks",
  );
  await openIntegrationSettings(page);
  await page.getByLabel("Radial coordinate").selectOption("q_A^-1");
  await waitReady();
  assert.equal(
    await page
      .getByLabel("Automatic radial binning", { exact: true })
      .isChecked(),
    true,
  );
  const automaticBins = (await invoke("state")).state.integration.actualBins;
  assert.ok(automaticBins > 0);
  assert.equal(
    await page.getByLabel("Radial bins", { exact: true }).inputValue(),
    String(automaticBins),
  );
  await page.getByLabel("Automatic radial binning", { exact: true }).uncheck();
  await page.getByLabel("Radial bins", { exact: true }).fill("0");
  await page
    .getByRole("button", { name: "Apply integration options", exact: true })
    .click();
  await page.getByRole("alert").waitFor();
  assert.equal(await page.locator('.app-status [role="alert"]').count(), 1);
  await page
    .getByRole("button", { name: "Close settings", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Dismiss error", exact: true })
    .click();
  await openIntegrationSettings(page);
  await page.getByLabel("Automatic radial binning", { exact: true }).uncheck();
  await page.getByLabel("Radial bins", { exact: true }).fill("1000");
  await page
    .getByRole("button", { name: "Apply integration options", exact: true })
    .click();
  await waitReady();
  current = await invoke("state");
  assert.equal(current.pattern.unit, "q_A^-1");
  assert.equal(
    current.cake.unit,
    "2th_deg",
    "Cake coordinates must retain their actual units",
  );
  assert.equal(current.state.bins, 1000);
  await page
    .getByRole("button", { name: "Close settings", exact: true })
    .click();
  await page.getByRole("button", { name: "Calibration", exact: true }).click();
  await verifyCakeCalibrantLines(current);
  await page.getByRole("button", { name: "Mask", exact: true }).click();
  await page.getByRole("button", { name: "Point", exact: true }).click();
  const box = await detector.boundingBox();
  await page.mouse.move(box.x + box.width * 0.55, box.y + box.height * 0.5);
  await page.keyboard.down("Shift");
  await page.mouse.down();
  await page.mouse.move(box.x + box.width * 0.6, box.y + box.height * 0.55, {
    steps: 8,
  });
  await page.mouse.up();
  await page.keyboard.up("Shift");
  await waitReady();
  current = await invoke("state");
  assert.ok(current.state.maskedPixels > 0);
  const maskedPixels = current.state.maskedPixels;
  await page.getByRole("button", { name: "Undo", exact: true }).click();
  await waitReady();
  current = await invoke("state");
  assert.equal(current.state.maskedPixels, 0);
  await page.getByRole("button", { name: "Integration", exact: true }).click();
  const exported = await invoke("export_pattern");
  assert.ok(exported.ok, exported.error);
  await page.getByRole("button", { name: "Save project", exact: true }).click();
  await waitReady();
  await page.getByRole("button", { name: "Open project", exact: true }).click();
  await waitReady();
  current = await invoke("state");
  assert.equal(current.state.bins, 1000);
  assert.equal(current.state.unit, "q_A^-1");
  await page
    .getByRole("group", { name: "Integration display", exact: true })
    .getByRole("button", { name: "Image", exact: true })
    .click();
  await selectColorMap(page, "Color map", "thermal");
  await page.mouse.move(10, 10);
  await page.screenshot({ path: path.join(artifacts, "integration.png") });
  await page.setViewportSize({ width: 1000, height: 760 });
  await page.locator("main").evaluate((el) => {
    el.scrollTop = 0;
  });
  await page.screenshot({ path: path.join(artifacts, "compact.png") });
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth > window.innerWidth,
  );
  assert.equal(overflow, false, "Minimum desktop width must not overflow");
  await setInterfaceTextSize(page, true);
  assert.equal(
    await page.evaluate(
      () => document.documentElement.scrollWidth > window.innerWidth,
    ),
    false,
  );
  await page.screenshot({
    path: path.join(artifacts, "compact-large-text.png"),
  });
  await setInterfaceTextSize(page, false);
  const integrationChecks = await verifyIntegrationControls(
    page,
    invoke,
    waitReady,
  );
  await page.screenshot({
    path: path.join(artifacts, "integration-controls.png"),
  });
  await page.getByRole("button", { name: "Calibration", exact: true }).click();
  await page
    .getByRole("tab", { name: "Step 4: Validate", exact: true })
    .click();
  for (const tab of ["Fit2D", "pyFAI"]) {
    await page.getByRole("tab", { name: tab, exact: true }).click();
    await page.reload();
    await waitReady();
    await page
      .getByRole("tab", { name: "Step 4: Validate", exact: true })
      .click();
    assert.equal(
      await page
        .getByRole("tab", { name: tab, exact: true })
        .getAttribute("aria-selected"),
      "true",
      `Validate restores ${tab} after reopening the interface`,
    );
    await page.waitForFunction(
      () => document.querySelector('[aria-label="Manual wavelength"]')?.value,
    );
    await page.getByLabel("Manual wavelength", { exact: true }).focus();
    await page.screenshot({
      path: path.join(artifacts, `validation-${tab.toLowerCase()}-focused.png`),
    });
  }
  assert.deepEqual(errors, []);
  const report = {
    integrationChecks,
    integrationLayoutChecks,
    passed: true,
    scientificFit,
    maskedPixels,
    browserErrors: errors,
    navigationChecks,
    imageControlChecks,
    detectorGeometryChecks,
    calibrationSetupChecks,
    calibrationWorkspaceChecks,
    ringPickerChecks,
    screenshots: [
      "calibration-start.png",
      "calibration-fit.png",
      "calibration-ring-selected.png",
      "calibration-large-text.png",
      "integration.png",
      "compact.png",
    ],
  };
  await writeFile(
    path.join(artifacts, "browser-smoke.json"),
    JSON.stringify(report, null, 2),
  );
  console.log(JSON.stringify(report, null, 2));
} catch (error) {
  await page.screenshot({ path: path.join(artifacts, "failure.png") });
  console.error(diagnostics.join("").slice(-5000));
  throw error;
} finally {
  await browser.close();
  host.stdin.end();
  host.kill();
}
