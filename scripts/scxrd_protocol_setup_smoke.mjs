// Fast headless regression for default protocols and switching cell models.
// Uses the analytical fixture; no scientific processing is mocked or required.
import assert from "node:assert/strict";
import fs from "node:fs/promises";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { chromium } from "playwright";
import { nativeClient, root } from "./native_backend_client.mjs";
const output = path.resolve(process.argv[2]);
await fs.mkdir(output);
const fixture = path.join(root, "artifacts/scxrd-fixture");
const paths = (await fs.readdir(fixture))
  .filter((x) => x.endsWith(".tif"))
  .sort()
  .map((x) => path.join(fixture, x));
const native = nativeClient();
const browser = await chromium.launch({ headless: true });
const errors = [];
async function invoke(a, p = {}) {
  const r = await native.invoke(a, p);
  assert.equal(r.ok, true, r.error);
  return r;
}
try {
  await invoke("scxrd_load", { paths });
  const context = await browser.newContext({
    viewport: { width: 1500, height: 1000 },
  });
  const page = await context.newPage();
  page.on("pageerror", (e) => errors.push(e.message));
  await page.exposeFunction("__nativeInvoke", async (a, p) =>
    native.browserResult(await invoke(a, p)),
  );
  await page.addInitScript(() => {
    window.pywebview = {
      api: { invoke: (a, p) => window.__nativeInvoke(a, p) },
    };
  });
  await page.goto(pathToFileURL(path.join(root, "dist/index.html")).href);
  await page
    .getByRole("button", { name: "Single Crystal", exact: true })
    .click();
  await page.getByRole("tab", { name: "Frames", exact: true }).click();
  assert.equal((await invoke("scxrd_snapshot")).scxrd.config.protocol, null);
  assert.equal(
    await page.getByLabel("Protocol first frame", { exact: true }).inputValue(),
    "1",
  );
  assert.equal(
    await page.getByLabel("Protocol last frame", { exact: true }).inputValue(),
    String(paths.length),
  );
  await page
    .getByRole("button", { name: "Inspect protocol", exact: true })
    .click();
  let inspected = JSON.parse(
    await page.getByLabel("PhaseSmith protocol document").textContent(),
  );
  assert.equal(inspected.acquisition.first_frame, 0);
  assert.equal(inspected.acquisition.last_frame_inclusive, paths.length - 1);
  await page
    .getByRole("button", { name: "Hide protocol", exact: true })
    .click();
  await page.getByLabel("Protocol first frame", { exact: true }).fill("2");
  await page.getByLabel("Protocol first frame", { exact: true }).press("Tab");
  await page
    .getByRole("button", { name: "Apply settings", exact: true })
    .click();
  let current = (await invoke("scxrd_snapshot")).scxrd;
  assert.deepEqual(current.excludedFrames, [0]);
  assert.equal(current.effectiveProtocol.acquisition.first_frame, 1);
  await page.screenshot({
    path: path.join(output, "default-effective-protocol.png"),
  });

  // Set up an existing exploratory metric and manual omission, then exercise
  // the user's actual mode-switch/reset/apply controls.
  await invoke("scxrd_settings", {
    config: {
      ...current.config,
      integration_method: "summation",
      protocol: null,
      metric: [7, 9, 11, 60, 60, 60],
    },
  });
  await invoke("scxrd_edit", { operation: "frame", index: 5 });
  await page.reload();
  await page
    .getByRole("button", { name: "Single Crystal", exact: true })
    .click();
  await page.getByRole("tab", { name: "Frames", exact: true }).click();
  await page
    .getByLabel("Single-crystal workflow", { exact: true })
    .selectOption("profile");
  await page.getByRole("tab", { name: "Geometry", exact: true }).click();
  await page
    .getByRole("button", { name: "Clear incompatible metric", exact: true })
    .waitFor();
  await page.screenshot({
    path: path.join(output, "incompatible-metric-recovery.png"),
  });
  await page
    .getByRole("button", { name: "Clear incompatible metric", exact: true })
    .click();
  for (const [label, value] of [
    ["a / Å", "7"],
    ["b / Å", "9"],
    ["c / Å", "11"],
  ]) {
    await page.getByLabel(label, { exact: true }).fill(value);
    await page.getByLabel(label, { exact: true }).press("Tab");
  }
  await page
    .getByRole("button", { name: "Apply settings", exact: true })
    .click();
  current = (await invoke("scxrd_snapshot")).scxrd;
  assert.deepEqual(current.config.metric, [7, 9, 11, 90, 90, 90]);
  assert.equal(current.config.protocol.acquisition.first_frame, 2);
  assert.equal(current.config.protocol.acquisition.last_frame_inclusive, 143);
  assert.deepEqual(current.excludedFrames, [
    0,
    1,
    ...Array.from({ length: paths.length - 144 }, (_, i) => i + 144),
  ]);
  assert.equal(current.excludedFrames.includes(5), false);
  assert.equal(current.config.integration_method, "profile");
  await page.screenshot({
    path: path.join(output, "orthorhombic-prior-applied.png"),
  });
  assert.deepEqual(errors, []);
  await fs.writeFile(
    path.join(output, "receipt.json"),
    JSON.stringify(
      {
        ok: true,
        headless: true,
        defaultEffectiveProtocol: true,
        explicitMetricRecovery: true,
        declaredRangeApplied: true,
        errors,
      },
      null,
      2,
    ),
  );
  console.log(
    "Default protocol, range editing and metric-transition recovery passed",
  );
} finally {
  await browser.close();
  await native.close();
}
