import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { createInterface } from "node:readline";
import { copyFile, mkdir, mkdtemp, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { fileURLToPath } from "node:url";
import path from "node:path";
import { chromium, webkit } from "playwright";
import { selectIntegrationDisplay } from "./integration_display.mjs";
const root = fileURLToPath(new URL("../../", import.meta.url));
const artifacts = path.join(root, "desktop/artifacts");
await mkdir(artifacts, { recursive: true });
const temporary = await mkdtemp(path.join(tmpdir(), "dioptas-batch-window-"));
const paths = [];
for (let i = 0; i < 6; i++) {
  const file = path.join(temporary, `series_${i + 1}.tif`);
  await copyFile(
    path.join(root, "dioptas/tests/data/CeO2_Pilatus1M.tif"),
    file,
  );
  paths.push(file);
}
const host = spawn(
  path.join(root, ".venv/bin/python"),
  ["-u", "desktop/scripts/bridge_host.py"],
  {
    cwd: root,
    env: {
      ...process.env,
      OMP_NUM_THREADS: "2",
      DIOPTAS_CUSTOM_COMMANDS_FILE: path.join(temporary, "commands.json"),
    },
    stdio: ["pipe", "pipe", "pipe"],
  },
);
let identifier = 0;
let processed = false;
const pending = new Map(),
  logs = [],
  requests = [];
host.stderr.on("data", (b) => logs.push(b.toString()));
createInterface({ input: host.stdout }).on("line", (line) => {
  const m = JSON.parse(line),
    task = pending.get(m.id);
  if (task) {
    clearTimeout(task.timer);
    pending.delete(m.id);
    task.resolve(m.result);
  }
});
function invoke(action, payload = {}) {
  if (action === "open_image" && payload.multiple && !payload.paths)
    payload = { ...payload, paths };
  if (action === "batch_load_data" && processed)
    payload = { paths: [path.join(artifacts, "batch.h5")] };
  requests.push(action);
  return new Promise((resolve, reject) => {
    const id = ++identifier,
      timer = setTimeout(() => reject(Error(`Timed out ${action}`)), 45000);
    pending.set(id, { resolve, timer });
    host.stdin.write(JSON.stringify({ id, action, payload }) + "\n");
  });
}
const engine = process.argv.includes("--webkit") ? webkit : chromium;
const browser = await engine.launch({ headless: true });
const context = await browser.newContext({
  viewport: { width: 1600, height: 1000 },
});
const page = await context.newPage();
const errors = [];
context.on("page", (p) => p.on("pageerror", (e) => errors.push(e.message)));
page.on("pageerror", (e) => errors.push(e.message));
await page.exposeFunction("__dioptasInvoke", invoke);
await page.addInitScript(() => {
  window.pywebview = {
    api: { invoke: (a, p) => window.__dioptasInvoke(a, p) },
  };
});
const ready = async () => {
  await page.waitForFunction(
    () => document.querySelector(".app") && !document.querySelector(".spin"),
  );
  assert.deepEqual(await page.getByRole("alert").allTextContents(), []);
};
const click = async (p, name) => {
  await p.getByRole("button", { name, exact: true }).click();
};
const selected = async (p, n) => {
  await p.waitForFunction((n) => {
    const input = document.querySelector('[aria-label="Selected batch frame"]');
    return input && input.value === String(n - 1) && !input.disabled;
  }, n);
  await ready();
  assert.equal((await invoke("state")).batch.selected, n - 1);
};
const readRange = (p) =>
  p
    .getByTestId("batch-heatmap")
    .evaluate((c) => [
      +c.dataset.viewXMin,
      +c.dataset.viewXMax,
      +c.dataset.viewYMin,
      +c.dataset.viewYMax,
    ]);
const sameRange = (a, b) =>
  a.forEach((x, i) => assert(Math.abs(x - b[i]) < 1e-5, `${a} vs ${b}`));
let child;
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
  assert.equal(
    await page.getByRole("button", { name: "Batch", exact: true }).count(),
    0,
  );
  await click(page, "Integration");
  const opened = context.waitForEvent("page");
  await click(page, "Load image…");
  child = await opened;
  await child.waitForLoadState();
  await selected(child, 1);
  assert.equal(
    await page
      .getByRole("button", { name: "Integration", exact: true })
      .getAttribute("aria-pressed"),
    "true",
  );
  assert.equal(await child.locator(".intensity-histogram").count(), 1);
  assert.equal(await child.getByTestId("detector-canvas").count(), 0);
  await click(child, "Next batch frame");
  await selected(child, 2);
  let state = await invoke("state");
  assert.equal(state.state.imageName, "series_2.tif");
  assert(state.cake && state.pattern);
  assert.equal(await page.getByTestId("cake-canvas").count(), 1);
  await selectIntegrationDisplay(page, "cake");
  assert(await page.getByTestId("cake-canvas").isVisible());
  const canvas = child.getByTestId("batch-heatmap"),
    b = await canvas.boundingBox();
  await child.mouse.click(b.x + 100, b.y + 12 + ((b.height - 58) * 4.5) / 6);
  await selected(child, 5);
  state = await invoke("state");
  assert.equal(state.state.imageName, "series_5.tif");
  assert(state.cake);
  // Qt Files/2D grouping, normalization popup, and bottom range navigation.
  await child.getByRole("tab", { name: "Files", exact: true }).click();
  assert.equal(
    await child
      .getByRole("columnheader", { name: "Raw file name", exact: true })
      .count(),
    1,
  );
  assert.equal(
    await child
      .getByRole("columnheader", { name: "N images", exact: true })
      .count(),
    1,
  );
  await click(child, "Select batch file 2");
  await selected(child, 3);
  await child.getByRole("tab", { name: "2D", exact: true }).click();
  await click(child, "Normalization settings");
  const dialog = child.getByRole("dialog", {
    name: "Normalization settings",
    exact: true,
  });
  await dialog.getByLabel("First normalization bin", { exact: true }).fill("0");
  await dialog.getByLabel("Last normalization bin", { exact: true }).fill("99");
  await dialog
    .getByLabel("Normalization reference frame", { exact: true })
    .fill("1");
  await click(child, "Apply");
  await child.waitForTimeout(100);
  await ready();
  await click(child, "Normalization settings");
  await dialog
    .getByLabel("First normalization bin", { exact: true })
    .fill("20");
  await click(child, "Cancel");
  await click(child, "Normalize batch");
  await child.waitForFunction(
    () =>
      document
        .querySelector('[aria-label="Normalize batch"]')
        ?.getAttribute("aria-pressed") === "true",
  );
  assert.equal((await invoke("state")).batch.normalized, true);
  assert.deepEqual((await invoke("state")).batch.normalizationRange, [0, 100]);
  await click(child, "Normalize batch");
  await child.waitForFunction(
    () =>
      document
        .querySelector('[aria-label="Normalize batch"]')
        ?.getAttribute("aria-pressed") === "false",
  );
  // Unit/scale buttons keep stored arrays intact and use the recorded wavelength.
  await click(child, "Batch unit Q");
  await child.waitForFunction(
    () =>
      document
        .querySelector('[aria-label="Batch unit Q"]')
        ?.getAttribute("aria-pressed") === "true",
  );
  assert.equal((await invoke("state")).pattern.unit, "q_A^-1");
  await click(child, "Batch unit 2θ");
  await child.waitForFunction(
    () =>
      document
        .querySelector('[aria-label="Batch unit 2θ"]')
        ?.getAttribute("aria-pressed") === "true",
  );
  await child.getByRole("button", { name: "√", exact: true }).click();
  await child.getByRole("button", { name: "lin", exact: true }).click();
  await child.getByRole("tab", { name: "Files", exact: true }).click();
  await child.getByLabel("Batch frame step", { exact: true }).fill("2");
  await click(child, "Integrate");
  await child.waitForFunction(() =>
    document
      .querySelector(".batch-frame-number")
      ?.textContent.includes("(3/6)"),
  );
  await selected(child, 1);
  assert.equal((await invoke("state")).batch.entries.length, 3);
  await click(child, "Save batch data");
  await child.waitForTimeout(200);
  await ready();
  // Source contrast and overview zoom survive docking across webviews.
  await click(child, "Batch histogram settings");
  await child.getByLabel("Batch minimum intensity", { exact: true }).fill("10");
  await child
    .getByLabel("Batch minimum intensity", { exact: true })
    .press("Enter");
  await click(child, "Close batch display settings");
  const wheel = await canvas.evaluate((c) => {
    const b = c.getBoundingClientRect(),
      e = new WheelEvent("wheel", {
        deltaY: -140,
        clientX: b.x + 120,
        clientY: b.y + 120,
        bubbles: true,
        cancelable: true,
      });
    c.dispatchEvent(e);
    return e.defaultPrevented;
  });
  assert.equal(wheel, true);
  await child.waitForTimeout(80);
  const range = await readRange(child);
  const display = await child.evaluate(() =>
    JSON.parse(localStorage.getItem("dioptas-batch:display")),
  );
  assert.equal(display.limits[0], 10);
  await child.screenshot({ path: path.join(artifacts, "batch-window.png") });
  await click(child, "Dock batch below image");
  await child.waitForEvent("close");
  child = null;
  const dock = page.locator(".batch-dock");
  await dock.waitFor();
  await selected(page, 1);
  assert.equal(
    await dock.locator(".image-intensity").getAttribute("data-orientation"),
    "vertical",
  );
  assert.equal(
    await dock.getByLabel("Batch start frame", { exact: true }).isVisible(),
    false,
  );
  assert.equal(
    await dock
      .getByRole("button", { name: "Normalize batch", exact: true })
      .isVisible(),
    false,
  );
  sameRange(await readRange(page), range);
  await dock.getByRole("tab", { name: "Options", exact: true }).click();
  assert(
    await dock.getByLabel("Batch start frame", { exact: true }).isVisible(),
  );
  assert(
    await dock
      .getByRole("button", { name: "Normalize batch", exact: true })
      .isVisible(),
  );
  await dock.getByLabel("Batch frame step", { exact: true }).fill("2");
  await dock.getByRole("button", { name: "Batch unit Q", exact: true }).click();
  await ready();
  assert.equal((await invoke("state")).pattern.unit, "q_A^-1");
  assert.equal(
    await dock
      .getByRole("tab", { name: "Options", exact: true })
      .getAttribute("aria-selected"),
    "true",
  );
  await dock
    .getByRole("button", { name: "Batch unit 2θ", exact: true })
    .click();
  await ready();
  await dock.getByRole("tab", { name: "2D", exact: true }).click();
  sameRange(await readRange(page), range);
  await dock.getByRole("tab", { name: "Options", exact: true }).click();
  assert.equal(
    await dock.getByLabel("Batch frame step", { exact: true }).inputValue(),
    "2",
  );
  await dock.getByLabel("Batch frame step", { exact: true }).fill("1");
  await dock.getByRole("tab", { name: "2D", exact: true }).click();
  assert.equal(
    await page.evaluate(
      () => JSON.parse(localStorage.getItem("dioptas-batch:display")).limits[0],
    ),
    10,
  );
  const image = await page.locator(".cake-panel").boundingBox(),
    dockBox = await dock.boundingBox(),
    controls = await page.locator(".integration-controls").boundingBox(),
    pattern = await page.locator(".pattern-panel").boundingBox();
  assert(dockBox.y >= image.y + image.height - 1);
  assert(dockBox.x < controls.x && dockBox.x + dockBox.width <= controls.x);
  assert(pattern.x >= dockBox.x + dockBox.width);
  await click(page, "Next batch frame");
  await selected(page, 2);
  assert.equal((await invoke("state")).state.imageName, "series_3.tif");
  assert((await invoke("state")).cake);
  const divider = page.getByRole("separator", {
    name: "Image and batch divider",
    exact: true,
  });
  await divider.focus();
  await divider.press("ArrowUp");
  assert((await dock.boundingBox()).height > dockBox.height);
  const beforeDrag = await dock.boundingBox();
  const beforeImage = await page.locator(".cake-panel").boundingBox();
  const beforePlot = await dock.getByTestId("batch-heatmap").boundingBox();
  const handle = await divider.boundingBox();
  await page.mouse.move(
    handle.x + handle.width / 2,
    handle.y + handle.height / 2,
  );
  await page.mouse.down();
  await page.mouse.move(
    handle.x + handle.width / 2,
    handle.y + handle.height / 2 - 50,
  );
  await page.mouse.up();
  await page.waitForTimeout(100);
  assert((await dock.boundingBox()).height > beforeDrag.height + 40);
  assert(
    (await page.locator(".cake-panel").boundingBox()).height <
      beforeImage.height - 40,
  );
  assert(
    (await dock.getByTestId("batch-heatmap").boundingBox()).height >
      beforePlot.height + 40,
  );
  await divider.dblclick();
  await click(page, "Collapse batch overview");
  assert((await dock.boundingBox()).height < 50);
  await click(page, "Expand batch overview");
  await page.waitForFunction(() => {
    const c = document.querySelector('[data-testid="batch-heatmap"]');
    return c?.width > 200 && c?.height > 100;
  });
  await page.waitForTimeout(80);
  await page.screenshot({ path: path.join(artifacts, "batch-docked.png") });
  for (const large of [false, true]) {
    await page.setViewportSize({ width: 1000, height: 700 });
    await page
      .locator(".app")
      .evaluate(
        (app, big) =>
          app.setAttribute("data-text-size", big ? "large" : "normal"),
        large,
      );
    await page.waitForTimeout(100);
    const boxes = await page
      .locator(
        ".integration-left-pane,.batch-dock,.integration-controls,.pattern-panel",
      )
      .evaluateAll((nodes) =>
        nodes.map((n) => {
          const b = n.getBoundingClientRect();
          return {
            x: b.x,
            y: b.y,
            width: b.width,
            height: b.height,
            right: b.right,
            bottom: b.bottom,
          };
        }),
      );
    assert(
      boxes.every(
        (b) =>
          b.width > 100 &&
          b.height > 90 &&
          b.x >= 0 &&
          b.right <= 1000 &&
          b.bottom <= 700,
      ),
      JSON.stringify(boxes),
    );
    await dock.getByRole("tab", { name: "Options", exact: true }).click();
    const optionBounds = await dock
      .locator(".batch-settings-content")
      .boundingBox();
    for (const label of [
      "Batch start frame",
      "Batch stop frame",
      "Batch frame step",
    ]) {
      const field = await dock.getByLabel(label, { exact: true }).boundingBox();
      assert(
        field.x >= optionBounds.x &&
          field.x + field.width <= optionBounds.x + optionBounds.width,
      );
      assert(
        field.y >= optionBounds.y &&
          field.y + field.height <= optionBounds.y + optionBounds.height,
      );
    }
    if (large)
      await page.screenshot({
        path: path.join(artifacts, "batch-docked-options.png"),
      });
    await dock.getByRole("tab", { name: "2D", exact: true }).click();
  }
  await page.screenshot({
    path: path.join(artifacts, "batch-docked-small.png"),
  });
  const compactPlot = await dock.getByTestId("batch-heatmap").boundingBox();
  assert(compactPlot.height - 58 >= 150, JSON.stringify(compactPlot));
  await click(page, "Hide batch view");
  assert.equal(await dock.count(), 0);
  assert.equal((await invoke("state")).batch.entries.length, 3);
  await click(page, "Batch view…");
  await dock.waitFor();
  const reopened = context.waitForEvent("page");
  await click(page, "Detach batch");
  child = await reopened;
  await child.waitForLoadState();
  await selected(child, 2);
  assert.equal(await dock.count(), 0);
  sameRange(await readRange(child), range);
  await child.close();
  child = null;
  await page.waitForTimeout(500);
  const again = context.waitForEvent("page");
  await click(page, "Batch view…");
  child = await again;
  await child.waitForLoadState();
  await selected(child, 2);
  // A stored-only series must clear stale detector/cake pixels in Integration.
  for (const file of paths) await rm(file);
  processed = true;
  await click(child, "Load raw/proc data");
  await selected(child, 1);
  state = await invoke("state");
  assert.equal(state.state.hasImage, false);
  assert.equal(state.cake, null);
  assert.equal(await page.getByTestId("detector-canvas").count(), 0);
  assert.equal(await page.getByTestId("cake-canvas").count(), 0);
  assert.equal(await page.getByTestId("pattern-canvas").count(), 1);
  assert.deepEqual(errors, []);
  await writeFile(
    path.join(
      artifacts,
      `batch-smoke${engine === webkit ? "-webkit" : ""}.json`,
    ),
    JSON.stringify(
      {
        ok: true,
        companionWindow: true,
        lowerLeftDock: true,
        linkedCake: true,
        preservedDisplay: true,
        requests,
        consoleErrors: errors,
      },
      null,
      2,
    ),
  );
  console.log("Batch companion/dock smoke passed");
} catch (e) {
  await page
    .screenshot({ path: path.join(artifacts, "batch-failure-main.png") })
    .catch(() => {});
  if (child)
    await child
      .screenshot({ path: path.join(artifacts, "batch-failure-window.png") })
      .catch(() => {});
  throw e;
} finally {
  await browser.close();
  host.stdin.end();
  await writeFile(path.join(artifacts, "batch-smoke.log"), logs.join(""));
  await rm(temporary, { recursive: true, force: true });
}
