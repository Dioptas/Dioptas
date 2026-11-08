import assert from "node:assert/strict";
import { spawn, execFileSync } from "node:child_process";
import { createInterface } from "node:readline";
import { mkdir, mkdtemp, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { createServer } from "vite";
import { chromium, webkit } from "playwright";
import { setInterfaceTextSize } from "./plot_navigation.mjs";

const desktop = fileURLToPath(new URL("../", import.meta.url));
const root = fileURLToPath(new URL("../../", import.meta.url));
const artifacts = path.join(desktop, "artifacts/image-change");
await mkdir(artifacts, { recursive: true });
const temporary = await mkdtemp(path.join(tmpdir(), "dioptas-image-change-"));
const small = path.join(temporary, "small.tif");
const same = path.join(temporary, "same.tif");
execFileSync(path.join(root, ".venv/bin/python"), [
  "-c",
  "from PIL import Image; import numpy as np; import sys; a=np.arange(96*128,dtype=np.uint16).reshape(96,128); [Image.fromarray(a).save(p) for p in sys.argv[1:]]",
  small,
  same,
]);
const host = spawn(
  path.join(root, ".venv/bin/python"),
  ["-u", "desktop/scripts/bridge_host.py"],
  { cwd: root, stdio: ["pipe", "pipe", "pipe"] },
);
const pending = new Map();
let nextId = 0;
const diagnostics = [];
host.stderr.on("data", (chunk) => diagnostics.push(chunk.toString()));
createInterface({ input: host.stdout }).on("line", (line) => {
  const message = JSON.parse(line);
  const task = pending.get(message.id);
  if (task) {
    pending.delete(message.id);
    clearTimeout(task.timer);
    task.resolve(message.result);
  }
});
host.on("exit", (code) => {
  for (const task of pending.values()) {
    clearTimeout(task.timer);
    task.reject(new Error(`Bridge exited ${code}`));
  }
  pending.clear();
});
function invoke(action, payload = {}) {
  return new Promise((resolve, reject) => {
    const id = ++nextId;
    const timer = setTimeout(() => {
      pending.delete(id);
      reject(new Error(`Timed out: ${action}`));
    }, 30000);
    pending.set(id, { resolve, reject, timer });
    host.stdin.write(JSON.stringify({ id, action, payload }) + "\n");
  });
}
async function call(action, payload) {
  const result = await invoke(action, payload);
  assert.ok(result.ok, result.error);
  return result;
}
const server = await createServer({
  root: desktop,
  server: { host: "127.0.0.1", port: 0 },
});
await server.listen();
const browserName = process.argv.includes("--webkit") ? "webkit" : "chromium";
const browser = await (browserName === "webkit" ? webkit : chromium).launch({
  headless: true,
});
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
const errors = [];
page.on("pageerror", (e) => errors.push(e.message));
let selectedImage = small;
await page.exposeFunction("__dioptasInvoke", (action, payload = {}) => {
  if (action === "open_image" && !payload.path)
    payload = { ...payload, path: selectedImage };
  if (action === "open_calibration")
    payload = {
      ...payload,
      path: path.join(root, "dioptas/tests/data/CeO2_Pilatus1M.poni"),
    };
  return invoke(action, payload);
});
await page.addInitScript(() => {
  window.__imageChangePending = 0;
  window.pywebview = {
    api: {
      invoke: async (action, payload) => {
        window.__imageChangePending++;
        try {
          return await window.__dioptasInvoke(action, payload);
        } finally {
          window.__imageChangePending--;
        }
      },
    },
  };
});
const button = (name) => page.getByRole("button", { name, exact: true });
async function ready() {
  await page.waitForFunction(
    () => !window.__imageChangePending && !document.querySelector(".spin"),
  );
  await page.evaluate(
    () =>
      new Promise((resolve) =>
        requestAnimationFrame(() => requestAnimationFrame(resolve)),
      ),
  );
  assert.deepEqual(await page.getByRole("alert").allTextContents(), []);
}
const report = { browser: browserName, headless: true, checks: [] };
try {
  await call("example");
  await call("open_calibration", {
    path: path.join(root, "dioptas/tests/data/CeO2_Pilatus1M.poni"),
  });
  await call("integration_settings", { bins: 100, cake_bins: 20 });
  await call("mask_stroke", { points: [[20, 30]], radius: 3 });
  const before = (await call("state")).state;
  await page.goto(server.resolvedUrls.local[0]);
  await button("Open image").waitFor({ state: "visible" });
  await ready();
  for (const large of [false, true]) {
    await page.setViewportSize({ width: 1000, height: 668 });
    await setInterfaceTextSize(page, large);
    const footerButtons = await Promise.all(
      ["Reset calibration", "Load .poni", "Enter manually"].map((name) => button(name).boundingBox()),
    );
    assert.ok(footerButtons.every((box) => box && Math.abs(box.y - footerButtons[0].y) < 1),
      "Calibration footer actions stay on one row at both text sizes");
    // Safari/WebKit does not focus buttons on pointer clicks. Exercise focus
    // restoration from a keyboard-focusable opener in both browser engines.
    await button("Open image").focus();
    await button("Open image").click();
    const dialog = page.getByRole("dialog", {
      name: "Image dimensions changed",
    });
    await dialog.waitFor({ state: "visible" });
    assert.equal(
      await button("Cancel").evaluate((el) => el === document.activeElement),
      true,
    );
    assert.deepEqual((await call("state")).state, before);
    const box = await dialog.boundingBox();
    assert.ok(
      box.x >= 0 &&
        box.y >= 0 &&
        box.x + box.width <= 1000 &&
        box.y + box.height <= 668,
    );
    await page.screenshot({
      path: path.join(
        artifacts,
        `confirm-${browserName}-${large ? "large" : "normal"}.png`,
      ),
    });
    if (large) await page.keyboard.press("Escape");
    else await button("Cancel").click();
    await dialog.waitFor({ state: "detached" });
    assert.deepEqual((await call("state")).state, before);
    await page.waitForFunction(
      () => document.activeElement?.matches(".setup-open-image"),
      undefined,
      { timeout: 2000 },
    );
    assert.equal(
      await button("Open image").evaluate(
        (el) => el === document.activeElement,
      ),
      true,
    );
  }
  report.checks.push(
    "dimensions shown before mutation",
    "Cancel and Escape preserve session and focus",
    "1000×668 at both text sizes",
  );
  await button("Open image").click();
  await button("Open and reset calibration").click();
  await page.waitForFunction(() => document.title.includes("small.tif"));
  await ready();
  let result = await call("state");
  assert.deepEqual(result.state.shape, [96, 128]);
  assert.equal(result.state.calibrated, false);
  assert.equal(result.state.maskedPixels, 0);
  assert.equal(result.pattern, null);
  assert.equal(result.cake, null);
  assert.equal(
    await page
      .getByRole("tab", { name: "Step 1: Image & setup", exact: true })
      .getAttribute("aria-selected"),
    "true",
  );
  assert.equal(await button("Save .poni calibration").isEnabled(), false);
  await page.screenshot({
    path: path.join(artifacts, `reset-${browserName}.png`),
  });
  report.checks.push(
    "accepted change opens uncalibrated and clears stale results",
  );
  await button("Load .poni").click();
  await ready();
  assert.equal((await call("state")).state.calibrated, true);
  await page
    .getByRole("tab", { name: "Step 1: Image & setup", exact: true })
    .click();
  selectedImage = same;
  await button("Open image").click();
  await page.waitForFunction(() => document.title.includes("same.tif"));
  await ready();
  assert.equal(await page.getByRole("dialog").count(), 0);
  assert.equal((await call("state")).state.calibrated, true);
  report.checks.push("same-size image retains calibration without prompting");
  await button("Reset calibration").click();
  await page
    .getByRole("dialog", { name: "Reset calibration?" })
    .waitFor({ state: "visible" });
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Reset calibration", exact: true })
    .click();
  await ready();
  result = await call("state");
  assert.equal(result.state.calibrated, false);
  assert.equal(result.state.imageName, "same.tif");
  report.checks.push("explicit reset keeps current image");
  assert.deepEqual(errors, []);
  await writeFile(
    path.join(artifacts, `report-${browserName}.json`),
    JSON.stringify(report, null, 2) + "\n",
  );
  console.log(JSON.stringify(report));
} catch (error) {
  await page.screenshot({
    path: path.join(artifacts, `failure-${browserName}.png`),
  });
  console.error(diagnostics.join("").slice(-4000));
  throw error;
} finally {
  await browser.close();
  await server.close();
  const exited = new Promise((resolve) => host.once("exit", resolve));
  host.stdin.end();
  await exited;
  await rm(temporary, { recursive: true, force: true });
}
