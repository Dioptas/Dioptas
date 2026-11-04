import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { createInterface } from "node:readline";
import { fileURLToPath } from "node:url";
import { mkdir, writeFile } from "node:fs/promises";
import { chromium, webkit } from "playwright";
import { setInterfaceTextSize } from "./plot_navigation.mjs";

const root = fileURLToPath(new URL("../../", import.meta.url));
const artifacts = root + "/desktop/artifacts";
await mkdir(artifacts, { recursive: true });
const host = spawn(
  root + "/.venv/bin/python",
  ["-u", "desktop/scripts/bridge_host.py"],
  { cwd: root, stdio: ["pipe", "pipe", "pipe"] },
);
let nextId = 0;
const pending = new Map();
const logs = [];
host.stderr.on("data", (d) => logs.push(d.toString()));
createInterface({ input: host.stdout }).on("line", (line) => {
  try {
    const r = JSON.parse(line);
    const p = pending.get(r.id);
    if (p) {
      clearTimeout(p.timer);
      pending.delete(r.id);
      p.resolve(r.result);
    }
  } catch {
    logs.push(line);
  }
});
const invoke = (action, payload = {}) =>
  new Promise((resolve, reject) => {
    const id = ++nextId;
    const timer = setTimeout(() => {
      pending.delete(id);
      reject(Error(`Timeout: ${action}`));
    }, 45000);
    pending.set(id, { resolve, reject, timer });
    host.stdin.write(JSON.stringify({ id, action, payload }) + "\n");
  });
const call = async (action, payload = {}) => {
  const r = await invoke(action, payload);
  assert.equal(r.ok, true, r.error);
  return r;
};
let browser, page;
const errors = [];
try {
  await call("example");
  const image = (await call("state")).state.imagePath;
  await call("open_calibration", {
    path: root + "/dioptas/tests/data/CeO2_Pilatus1M.poni",
  });
  await call("integration_settings", { bins: 160, cake_bins: 30 });
  await call("integration_overlay", { operation: "capture" });
  await call("integration_overlay", {
    operation: "update",
    index: 0,
    name: "Shared overlay",
    scale: 0.5,
    offset: 10,
    color: "#55aaff",
  });
  await call("integration_phase", {
    operation: "load",
    path: root + "/dioptas/tests/data/jcpds/au_Anderson.jcpds",
  });
  await call("integration_phase", {
    operation: "update",
    index: 0,
    pressure: 12,
    temperature: 600,
    color: "#ee88cc",
  });
  await call("map_load", { paths: [image, image, image, image] });
  await call("map_grid", { rows: 2, columns: 2 });
  browser = await (
    process.argv.includes("--webkit") ? webkit : chromium
  ).launch({ headless: true });
  page = await browser.newPage({ viewport: { width: 1600, height: 1000 } });
  page.on("pageerror", (error) => errors.push(error.message));
  await page.exposeFunction("__dioptasInvoke", invoke);
  await page.addInitScript(() => {
    window.pywebview = {
      api: {
        invoke: async (action, payload) => {
          window.__pending = (window.__pending ?? 0) + 1;
          try {
            return await window.__dioptasInvoke(action, payload);
          } finally {
            window.__pending--;
          }
        },
      },
    };
  });
  const ready = async () => {
    await page.waitForFunction(
      () =>
        document.querySelector(".app") &&
        !document.querySelector(".spin") &&
        !window.__pending,
    );
    assert.deepEqual(await page.getByRole("alert").allTextContents(), []);
  };
  const click = async (name) => {
    await page.getByRole("button", { name, exact: true }).click();
    await ready();
  };
  const edit = async (label, value) => {
    const input = page.getByLabel(label, { exact: true });
    await input.fill(String(value));
    await input.press("Enter");
    await ready();
  };
  await page.goto("file://" + root + "/dioptas/desktop/ui/index.html");
  await ready();
  await click("Map");
  const canvas = page.locator(
    '.map-pattern-panel [data-testid="pattern-canvas"]',
  );
  const refs = async (curves = 1, phases = true) => {
    await canvas.waitFor();
    await page.waitForFunction(
      ({ curves, phases }) => {
        const plot = document.querySelector(
          '.map-pattern-panel [data-testid="pattern-canvas"]',
        );
        return (
          +plot?.dataset.curveCount === curves &&
          +plot?.dataset.referenceCount > 0 === phases
        );
      },
      { curves, phases },
    );
    if (phases)
      assert.ok(
        (
          await page.getByLabel("Phase legend", { exact: true }).innerText()
        ).includes("12"),
      );
  };
  await refs();
  assert.equal(
    await page
      .getByLabel("Phase legend", { exact: true })
      .locator("div")
      .first()
      .evaluate((el) => getComputedStyle(el).color),
    "rgb(238, 136, 204)",
  );
  const overlayLegend = page
    .getByLabel("Pattern legend", { exact: true })
    .locator('div[title="Shared overlay"]');
  assert.equal(
    await overlayLegend.evaluate((el) => getComputedStyle(el).color),
    "rgb(85, 170, 255)",
  );
  await page.locator('.map-file-list [role="option"]').nth(3).click();
  await ready();
  await refs();
  assert.equal((await call("state")).map.selected, 3);
  for (const unit of ["Q", "d", "2θ"]) {
    await click("Map pattern unit " + unit);
    await refs();
  }
  await page
    .getByLabel("Logarithmic map pattern intensity", { exact: true })
    .click();
  await ready();
  await refs();
  await page
    .getByLabel("Square root map pattern intensity", { exact: true })
    .click();
  await ready();
  await refs();
  await click("Integration");
  await page.getByRole("tab", { name: "Phase", exact: true }).click();
  await edit("Phase 1 pressure (GPa)", 20);
  await edit("Phase 1 temperature (K)", 800);
  await page.getByLabel("Show phase 1", { exact: true }).click();
  await ready();
  await page.getByRole("tab", { name: "Overlay", exact: true }).click();
  await edit("Overlay 1 scale", 2);
  await edit("Overlay 1 offset", 123);
  await page.getByLabel("Show overlay 1", { exact: true }).click();
  await ready();
  await page.getByLabel("Original pattern", { exact: true }).click();
  await ready();
  await click("Map");
  await refs(0, false);
  assert.equal(await canvas.getAttribute("data-original-visible"), "false");
  await page.locator('.map-file-list [role="option"]').nth(1).click();
  await ready();
  await refs(0, false);
  await click("Integration");
  await page.getByRole("tab", { name: "Overlay", exact: true }).click();
  await page.getByLabel("Show overlay 1", { exact: true }).click();
  await ready();
  await page.getByLabel("Original pattern", { exact: true }).click();
  await ready();
  await page.getByRole("tab", { name: "Phase", exact: true }).click();
  await page.getByLabel("Show phase 1", { exact: true }).click();
  await ready();
  await click("Map");
  await page.waitForFunction(
    () =>
      +document.querySelector(
        '.map-pattern-panel [data-testid="pattern-canvas"]',
      ).dataset.referenceCount > 0,
  );
  const legend = await page
    .getByLabel("Phase legend", { exact: true })
    .innerText();
  assert.ok(legend.includes("20") && legend.includes("800"), legend);
  const state = await call("state");
  assert.equal(state.state.integration.overlays[0].scale, 2);
  assert.equal(state.state.integration.overlays[0].offset, 123);
  assert.equal(await canvas.getAttribute("data-curve-count"), "1");
  await page.screenshot({ path: artifacts + "/map-shared-references.png" });
  // Detach/dock keeps references on the complete Integration plot and on Map.
  const popup = page.waitForEvent("popup");
  await page.getByRole("button", { name: "Detach map", exact: true }).click();
  const child = await popup;
  await child.locator('[data-testid="scan-map"] canvas').first().waitFor();
  await ready();
  assert.ok(await page.getByLabel("Phase legend", { exact: true }).count());
  await child.getByRole("button", { name: "Dock map", exact: true }).click();
  await canvas.waitFor();
  assert.equal(await canvas.getAttribute("data-curve-count"), "1");
  assert.deepEqual(errors, []);
  await writeFile(
    artifacts + "/map-shared-references.json",
    JSON.stringify(
      {
        ok: true,
        sharedVisibility: true,
        sharedConditions: true,
        sharedOverlayScaleOffset: true,
        units: ["2θ", "Q", "d"],
        detached: true,
        errors,
      },
      null,
      2,
    ),
  );
  console.log("Shared Map/Integration phase and overlay checks passed");
} catch (error) {
  if (page)
    await page
      .screenshot({ path: artifacts + "/map-shared-references-failure.png" })
      .catch(() => {});
  throw error;
} finally {
  await browser?.close();
  host.stdin.end();
  await writeFile(artifacts + "/map-shared-references.log", logs.join(""));
}
