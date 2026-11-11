// Headless Map companion workflow against the native Rust stdio processor.
import { setInterfaceTextSize } from "./plot_navigation.mjs";
import { selectIntegrationDisplay } from "./integration_display.mjs";
import { nativeClient } from "./native_backend_client.mjs";
import assert from "node:assert/strict";
import { mkdir, writeFile, readdir, readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import path from "node:path";
import { chromium, webkit } from "playwright";
const root = fileURLToPath(new URL("../../", import.meta.url));
const artifacts = path.join(root, "desktop/artifacts");
if (
  process.argv.slice(2).some((arg) => !["--webkit", "--native"].includes(arg))
)
  throw Error(
    "Map window checks use Rust only. Supported options: --webkit, --native (compatibility alias).",
  );
const engineName = process.argv.includes("--webkit") ? "webkit" : "chromium";
const runtimeName = "rust";
const evidence = path.join(artifacts, "map-window", runtimeName, engineName);
await mkdir(evidence, { recursive: true });
const native = nativeClient();
const scanFolder = path.join(root, "dioptas/tests/data/map");
const scanPaths = (await readdir(scanFolder))
  .filter((name) => name.endsWith(".tif"))
  .sort()
  .map((name) => path.join(scanFolder, name));
const logs = native.diagnostics;
async function invoke(action, payload = {}) {
  // Stand in for Tauri's file chooser; scientific commands go unchanged to Rust.
  if (action === "map_load" && !payload.paths && !payload.reintegrate)
    payload = { ...payload, paths: scanPaths };
  if (action === "map_export" && !payload.path)
    payload = {
      ...payload,
      path: path.join(evidence, payload.png_data ? "map.png" : "map.txt"),
    };
  const reply = await native.invoke(action, payload);
  assert.equal(reply.ok, true, `${action}: ${reply.error}`);
  return native.browserResult(reply);
}
const browser = await (engineName === "webkit" ? webkit : chromium).launch({
  headless: true,
});
const context = await browser.newContext({
  viewport: { width: 1600, height: 1000 },
});
const page = await context.newPage();
const errors = [];
page.on("pageerror", (e) => errors.push(e.message));
let selectionGate = null;
await page.exposeFunction("__dioptasInvoke", async (action, payload) => {
  if (action === "map_select") {
    if (selectionGate) await selectionGate;
  }
  return invoke(action, payload);
});
await page.addInitScript(() => {
  // Observe companion gestures before the main command queue executes them.
  // A second click must be accepted even while the first extraction is held.
  window.__mapSelectGestures = [];
  window.addEventListener("message", (event) => {
    const { target, message } = event.data ?? {};
    if (
      target === "map-window-main" &&
      message?.type === "request" &&
      message.command === "map_select" &&
      !message.read
    )
      window.__mapSelectGestures.push({ ...message.args });
  });
  // Browser-only bridge shim; all calls above are handled by Rust.
  window.pywebview = {
    api: {
      invoke: async (a, p) => {
        window.__pendingCommands = (window.__pendingCommands ?? 0) + 1;
        if (a === "map_select") {
          window.__mapSelectRequests ??= [];
          window.__mapSelectRequests.push({ ...p });
        }
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
try {
  assert.equal((await native.invoke("__host__")).runtime, "rust");
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
  const initial = await invoke("state");
  assert.equal(initial.map.points, 9);
  const analysisBefore = await page.locator(".map-analysis-top").boundingBox();
  const popupPromise = page.waitForEvent("popup");
  await page.getByRole("button", { name: "Detach map", exact: true }).click();
  const child = await popupPromise;
  child.on("pageerror", (e) => errors.push(e.message));
  await child.getByTestId("scan-map").getByTestId("detector-canvas").waitFor();
  await page.waitForFunction(
    () =>
      document
        .querySelector('[aria-label="Integration"]')
        .getAttribute("aria-pressed") === "true",
  );
  // Rust deliberately skips hidden cakes. Exercise regeneration while Cake is
  // actually displayed, using the same demand policy as the desktop.
  await selectIntegrationDisplay(page, "cake");
  await ready();
  const cakeBeforeSelection = (await invoke("state")).cake;
  assert.ok(
    cakeBeforeSelection,
    "Showing Cake did not request its native grid",
  );
  const scanCanvas = child.locator(
    '[data-testid="scan-map"] [data-testid="detector-canvas"]',
  );
  const scanClickChild = async (row, col) => {
    const sentBefore = await page.evaluate(
      () => window.__mapSelectGestures.length,
    );
    await child.getByLabel("Map layer", { exact: true }).waitFor();
    await child.waitForFunction(
      () => !document.querySelector('[aria-label="Map layer"]').disabled,
    );
    const point = await scanCanvas.evaluate(
      async (canvas, { row, col }) => {
        // Wait for the companion's ResizeObserver and fitted square-pixel view.
        await new Promise((resolve) =>
          requestAnimationFrame(() => requestAnimationFrame(resolve)),
        );
        const d = canvas.dataset,
          x = col + 0.5,
          y = Number(d.fullHeight) - row - 0.5;
        return {
          x:
            Number(d.plotLeft) +
            ((x - Number(d.viewXMin)) /
              (Number(d.viewXMax) - Number(d.viewXMin))) *
              Number(d.plotWidth),
          y:
            Number(d.plotTop) +
            ((Number(d.viewYMax) - y) /
              (Number(d.viewYMax) - Number(d.viewYMin))) *
              Number(d.plotHeight),
        };
      },
      { row, col },
    );
    await scanCanvas.click({ position: point });
    // Confirm the actual user gesture reached the main owner before waiting
    // on a changed title; report a missed/wrong cell at the point of failure.
    await page.waitForFunction(
      (count) => window.__mapSelectGestures.length > count,
      sentBefore,
    );
    const sent = await page.evaluate(() => window.__mapSelectGestures.at(-1));
    assert.equal(sent.row, row);
    assert.equal(sent.column, col);
  };
  // Resize before the first edge-cell click to exercise the popup layout race.
  await child.setViewportSize({ width: 960, height: 540 });
  await scanClickChild(2, 2);
  await page.waitForFunction(
    (name) => document.title.includes(name),
    initial.map.labels[8],
  );
  await ready();
  let selected = await invoke("state");
  assert.equal(selected.map.selected, 8);
  assert.ok(
    selected.cake,
    "Detached map selection did not regenerate the cake",
  );
  assert.notEqual(
    selected.cake.bufferId,
    cakeBeforeSelection.bufferId,
    "Map selection retained the previous image's cake",
  );
  assert.equal(selected.state.integrationDirty, false);
  assert.deepEqual(selected.map.selectedCell, [2, 2]);
  await page.screenshot({
    path: path.join(evidence, "detached-map-integration.png"),
  });
  // Rapid map selections are retained while full Integration calculation runs.
  let releaseSelection;
  selectionGate = new Promise((resolve) => {
    releaseSelection = resolve;
  });
  await child.setViewportSize({ width: 520, height: 700 });
  try {
    await scanClickChild(0, 0);
    await scanClickChild(1, 1);
  } finally {
    releaseSelection();
    selectionGate = null;
  }
  await page.waitForFunction(
    (name) => document.title.includes(name),
    initial.map.labels[4],
  );
  await ready();
  assert.equal((await invoke("state")).map.selected, 4);
  assert.deepEqual(
    await page.evaluate(() =>
      window.__mapSelectRequests.map(({ row, column }) => [row, column]),
    ),
    [
      [2, 2],
      [0, 0],
      [1, 1],
    ],
  );
  assert.equal(await child.getByRole("alert").count(), 0);
  await child.getByLabel("Smooth map", { exact: true }).check();
  await child.getByLabel("Map contours", { exact: true }).check();
  await child.getByRole("button", { name: "Save PNG…", exact: true }).click();
  await page.waitForFunction(() =>
    document.querySelector(".app-status")?.textContent.includes("map.png"),
  );
  assert.deepEqual(
    [...(await readFile(path.join(evidence, "map.png"))).subarray(0, 8)],
    [137, 80, 78, 71, 13, 10, 26, 10],
  );
  await click("Map");
  await page.getByRole("button", { name: "Show map", exact: true }).click();
  assert.equal(context.pages().length, 2, "Show map opened a duplicate window");
  await click("Map");
  assert.equal(await page.locator(".map-window-banner").count(), 0);
  assert.equal(await page.locator(".map-detached-placeholder").count(), 1);
  const analysisAfter = await page.locator(".map-analysis-top").boundingBox();
  assert.ok(
    Math.abs(analysisAfter.x - analysisBefore.x) < 1 &&
      Math.abs(analysisAfter.width - analysisBefore.width) < 1,
    "Detaching changed the original Map column layout",
  );
  for (const surface of [page, child]) {
    const dock = surface.getByRole("button", { name: "Dock map", exact: true });
    assert.equal((await dock.textContent()).trim(), "");
    assert.equal(await dock.locator("svg").count(), 1);
  }
  // Existing ROI commands remain in Map mode, and child layer controls follow edits.
  await page.getByRole("tab", { name: "Layers", exact: true }).click();
  await page.getByRole("button", { name: "Add window", exact: true }).click();
  await ready();
  await child.getByLabel("Map layer", { exact: true }).selectOption("B");
  await page.waitForTimeout(250);
  await ready();
  assert.equal((await invoke("state")).map.active, "B");
  await child.screenshot({ path: path.join(evidence, "detached-map.png") });
  await page.screenshot({
    path: path.join(evidence, "detached-map-controls.png"),
  });
  await child
    .getByRole("button", { name: "Map color map", exact: true })
    .click();
  await child.getByRole("option", { name: /^viridis$/i }).click();
  await child
    .getByRole("button", { name: "Map histogram settings", exact: true })
    .click();
  await child.getByLabel("Map minimum intensity", { exact: true }).fill("123");
  await child
    .getByLabel("Map minimum intensity", { exact: true })
    .press("Enter");
  await child
    .getByLabel("Map maximum intensity", { exact: true })
    .fill("456789");
  await child
    .getByLabel("Map maximum intensity", { exact: true })
    .press("Enter");
  await child
    .getByLabel("Map image scale", { exact: true })
    .selectOption("log");
  await child
    .getByRole("button", { name: "Close map display settings", exact: true })
    .click();
  await setInterfaceTextSize(page, true);
  await child.waitForFunction(
    () => document.querySelector(".app").dataset.textSize === "large",
  );
  await child.setViewportSize({ width: 460, height: 360 });
  assert.ok(
    await child.evaluate(
      () =>
        document.documentElement.scrollWidth <= innerWidth &&
        document.querySelector("footer").getBoundingClientRect().bottom <=
          innerHeight + 1,
    ),
    "Detached map overflows at its minimum size with larger text",
  );
  await child.screenshot({
    path: path.join(evidence, "detached-map-compact.png"),
  });
  await setInterfaceTextSize(page, false);
  // Window close docks the panel without discarding the scan or changing modes.
  await click("Integration");
  await child.close();
  await click("Map");
  await page.getByRole("button", { name: "Detach map", exact: true }).waitFor();
  assert.equal(
    await page.getByLabel("Smooth map", { exact: true }).isChecked(),
    true,
  );
  assert.equal(
    await page.getByLabel("Map contours", { exact: true }).isChecked(),
    true,
  );
  assert.equal(
    await page
      .getByRole("button", { name: "Map color map", exact: true })
      .getAttribute("data-color-map"),
    "viridis",
  );
  await page
    .getByRole("button", { name: "Map histogram settings", exact: true })
    .click();
  assert.equal(
    await page
      .getByLabel("Map minimum intensity", { exact: true })
      .inputValue(),
    "123",
  );
  assert.equal(
    await page
      .getByLabel("Map maximum intensity", { exact: true })
      .inputValue(),
    "456789",
  );
  assert.equal(
    await page.getByLabel("Map image scale", { exact: true }).inputValue(),
    "log",
  );
  await page
    .getByRole("button", { name: "Close map display settings", exact: true })
    .click();
  const secondPopup = page.waitForEvent("popup");
  await page.getByRole("button", { name: "Detach map", exact: true }).click();
  const second = await secondPopup;
  await second.getByLabel("Map layer", { exact: true }).waitFor();
  await second.getByRole("button", { name: "Dock map", exact: true }).click();
  await page.getByRole("button", { name: "Detach map", exact: true }).waitFor();
  assert.equal(
    await page
      .getByRole("button", { name: "Map", exact: true })
      .getAttribute("aria-pressed"),
    "true",
  );
  assert.equal((await invoke("state")).map.points, 9);
  assert.deepEqual(errors, []);
  await writeFile(
    path.join(evidence, "map-window-smoke.json"),
    JSON.stringify(
      {
        ok: true,
        browser: engineName,
        runtime: runtimeName,
        processorPid: native.child.pid,
        selected: 4,
        renderedCellCoordinates: true,
        resizedBeforeSelections: true,
        selections: await page.evaluate(() => window.__mapSelectRequests),
        cakeRegenerated: true,
        rapidSelections: true,
        dockCloseReopen: true,
        contrastPaletteRetained: true,
        minimumSizeLargeText: true,
        errors,
      },
      null,
      2,
    ),
  );
  console.log(
    `${engineName} (${runtimeName}): detached Map frame selection, rapid selections, export, contrast and dock/close/reopen passed`,
  );
} catch (error) {
  console.log(
    "Main UI:",
    (await page.locator("body").innerText()).slice(-2500),
  );
  for (const [index, surface] of context.pages().entries())
    await surface
      .screenshot({
        path: path.join(evidence, `map-window-failure-${index}.png`),
      })
      .catch(() => {});
  throw error;
} finally {
  await browser.close();
  await native.close();
  await writeFile(path.join(evidence, "map-window-smoke.log"), logs.join(""));
}
