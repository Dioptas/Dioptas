import { setInterfaceTextSize } from "./plot_navigation.mjs";
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { createInterface } from "node:readline";
import { mkdir, writeFile } from "node:fs/promises";
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
  const initial = await invoke("state");
  assert.equal(initial.map.points, 9);
  const popupPromise = page.waitForEvent("popup");
  await page.getByRole("button", { name: "Detach map", exact: true }).click();
  const child = await popupPromise;
  child.on("pageerror", (e) => errors.push(e.message));
  await child.locator('[data-testid="scan-map"] canvas').first().waitFor();
  await page.waitForFunction(
    () =>
      document
        .querySelector('[aria-label="Integration"]')
        .getAttribute("aria-pressed") === "true",
  );
  const scanCanvas = child.locator(
    '[data-testid="scan-map"] [data-testid="detector-canvas"]',
  );
  const scanClickChild = async (row, col) => {
    const b = await scanCanvas.boundingBox();
    const scale = Math.min(b.width / 3, b.height / 3);
    await child.mouse.click(
      b.x + (b.width - 3 * scale) / 2 + (col + 0.5) * scale,
      b.y + (b.height - 3 * scale) / 2 + (row + 0.5) * scale,
    );
  };
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
  assert.equal(selected.state.integrationDirty, false);
  assert.deepEqual(selected.map.selectedCell, [2, 2]);
  await page.screenshot({
    path: path.join(artifacts, "detached-map-integration.png"),
  });
  // Rapid map selections are retained while full Integration calculation runs.
  selectionGate = new Promise((resolve) => setTimeout(resolve, 200));
  await scanClickChild(0, 0);
  await scanClickChild(1, 1);
  await page.waitForFunction(
    (name) => document.title.includes(name),
    initial.map.labels[4],
  );
  await ready();
  assert.equal((await invoke("state")).map.selected, 4);
  assert.equal(await child.getByRole("alert").count(), 0);
  await child.getByLabel("Smooth map", { exact: true }).check();
  await child.getByLabel("Map contours", { exact: true }).check();
  await child.getByRole("button", { name: "Save PNG…", exact: true }).click();
  await page.waitForFunction(() =>
    document.querySelector(".app-status")?.textContent.includes("map.png"),
  );
  await click("Map");
  await page.getByRole("button", { name: "Show map", exact: true }).click();
  assert.equal(context.pages().length, 2, "Show map opened a duplicate window");
  await click("Map");
  assert.equal(await page.locator(".map-window-banner").count(), 1);
  // Existing ROI commands remain in Map mode, and child layer controls follow edits.
  await page.getByRole("tab", { name: "Layers", exact: true }).click();
  await page.getByRole("button", { name: "Add window", exact: true }).click();
  await ready();
  await child.getByLabel("Map layer", { exact: true }).selectOption("B");
  await page.waitForTimeout(250);
  await ready();
  assert.equal((await invoke("state")).map.active, "B");
  await child.screenshot({ path: path.join(artifacts, "detached-map.png") });
  await page.screenshot({
    path: path.join(artifacts, "detached-map-controls.png"),
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
    path: path.join(artifacts, "detached-map-compact.png"),
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
    path.join(artifacts, "map-window-smoke.json"),
    JSON.stringify(
      {
        ok: true,
        selected: 4,
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
  console.log("Detached map window checks passed");
} catch (error) {
  console.log(
    "Main UI:",
    (await page.locator("body").innerText()).slice(-2500),
  );
  for (const [index, surface] of context.pages().entries())
    await surface
      .screenshot({
        path: path.join(artifacts, `map-window-failure-${index}.png`),
      })
      .catch(() => {});
  throw error;
} finally {
  await browser.close();
  host.stdin.end();
  await writeFile(path.join(artifacts, "map-window-smoke.log"), logs.join(""));
}
