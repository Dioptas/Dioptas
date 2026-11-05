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
  {
    cwd: root,
    env: { ...process.env, OMP_NUM_THREADS: "2" },
    stdio: ["pipe", "pipe", "pipe"],
  },
);
let identifier = 0;
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
    payload = {
      ...payload,
      paths: Array(6).fill(
        path.join(root, "dioptas/tests/data/CeO2_Pilatus1M.tif"),
      ),
    };
  requests.push({ action, payload });
  return new Promise((resolve, reject) => {
    const id = ++identifier,
      timer = setTimeout(() => reject(Error(`Timed out ${action}`)), 45000);
    pending.set(id, { resolve, timer });
    host.stdin.write(JSON.stringify({ id, action, payload }) + "\n");
  });
}
const engine = process.argv.includes("--webkit") ? webkit : chromium;
const browser = await engine.launch({ headless: true });
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
  await click("Integration");
  await click("Load image…");
  assert.equal(
    await page
      .getByRole("button", { name: "Batch", exact: true })
      .getAttribute("aria-pressed"),
    "true",
  );
  assert.equal((await invoke("state")).batch.entries.length, 6);
  assert.equal(
    await page.locator(".batch-layout .intensity-histogram").count(),
    2,
  );
  await click("Next batch pattern");
  assert.equal((await invoke("state")).batch.selected, 1);
  await click("Select batch pattern 5");
  assert.equal((await invoke("state")).batch.selected, 4);
  const canvas = page.getByTestId("batch-heatmap");
  let box = await canvas.boundingBox();
  await page.mouse.click(
    box.x + 100,
    box.y + 12 + ((box.height - 58) * 2.5) / 6,
  );
  await ready();
  assert.equal((await invoke("state")).batch.selected, 2);
  await canvas.focus();
  await page.keyboard.press("ArrowDown");
  await ready();
  assert.equal((await invoke("state")).batch.selected, 3);
  const wheel = await canvas.evaluate((c) => {
    const e = new WheelEvent("wheel", {
      deltaY: -140,
      clientX: c.getBoundingClientRect().x + 120,
      clientY: c.getBoundingClientRect().y + 120,
      bubbles: true,
      cancelable: true,
    });
    c.dispatchEvent(e);
    return e.defaultPrevented;
  });
  assert.equal(wheel, true);
  await page.keyboard.press("f");
  box = await canvas.boundingBox();
  await page.mouse.move(box.x + 90, box.y + 80);
  await page.mouse.down();
  await page.mouse.move(box.x + 200, box.y + 180, { steps: 5 });
  await page.mouse.up();
  await ready();
  assert.equal((await invoke("state")).batch.selected, 3);
  await page.keyboard.press("f");
  await page.getByLabel("Filter batch files").fill("nonsense");
  assert.equal(
    await page.getByRole("button", { name: /Select batch pattern/ }).count(),
    0,
  );
  await page.getByLabel("Filter batch files").fill("");
  await page.getByText("Normalization", { exact: true }).click();
  await click("Normalize");
  assert.equal((await invoke("state")).batch.normalized, true);
  await click("Restore original");
  await page.getByLabel("Stride", { exact: true }).fill("2");
  await click("Reintegrate range");
  assert.equal((await invoke("state")).batch.entries.length, 3);
  await click("Save batch…");
  await click("Open processed batch…");
  assert.equal((await invoke("state")).batch.entries.length, 3);
  await click("Expand overview");
  assert.equal(await page.locator(".batch-detector-panel").count(), 0);
  await click("Show detector / pattern");
  await page.screenshot({ path: path.join(artifacts, "batch-workspace.png") });
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
      .locator(".batch-layout section")
      .evaluateAll((nodes) =>
        nodes.map((n) => {
          const b = n.getBoundingClientRect();
          return { width: b.width, height: b.height, right: b.right };
        }),
      );
    assert(
      boxes.every((b) => b.width > 100 && b.height > 80 && b.right <= 1000),
      JSON.stringify(boxes),
    );
    assert.equal(
      await page.locator(".batch-layout .intensity-histogram").count(),
      2,
    );
  }
  await page.screenshot({
    path: path.join(artifacts, "batch-workspace-small.png"),
  });
  await click("Calibration");
  await click("Integration");
  await click("Batch processing…");
  assert.equal(await canvas.count(), 1);
  assert.deepEqual(errors, []);
  await writeFile(
    path.join(
      artifacts,
      `batch-smoke${engine === webkit ? "-webkit" : ""}.json`,
    ),
    JSON.stringify(
      {
        ok: true,
        requests: requests.map((r) => r.action),
        consoleErrors: errors,
      },
      null,
      2,
    ),
  );
  console.log("Batch UI smoke passed");
} finally {
  await browser.close();
  host.stdin.end();
  await writeFile(path.join(artifacts, "batch-smoke.log"), logs.join(""));
}
