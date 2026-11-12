// Optional real-measurement display and cooperative-cancellation regression.
// Run scxrd_measured.mjs first to create a verified recipe from local data.
import assert from "node:assert/strict";
import fs from "node:fs/promises";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { chromium } from "playwright";
import { nativeClient, root } from "./native_backend_client.mjs";
const folder = path.join(root, "artifacts/scxrd-measured");
const native = nativeClient();
const browser = await chromium.launch({ headless: true });
const errors = [];
try {
  let r = await native.invoke("scxrd_file", {
    operation: "open",
    path: path.join(folder, "measured.scxrd.json"),
  });
  assert.equal(r.ok, true, r.error);
  r = await native.invoke("scxrd_run", { stage: 5 });
  assert.equal(r.scxrd.error, null);
  await native.invoke("scxrd_frame", { frame: 60 });
  const page = await browser.newPage({
    viewport: { width: 1500, height: 1000 },
  });
  page.setDefaultTimeout(45000);
  page.on("pageerror", (e) => errors.push(e.message));
  await page.exposeFunction("__nativeInvoke", async (a, p = {}) =>
    native.browserResult(await native.invoke(a, p)),
  );
  await page.addInitScript(() => {
    window.pywebview = {
      api: { invoke: (a, p) => window.__nativeInvoke(a, p) },
    };
  });
  await page.goto(pathToFileURL(path.join(root, "dist/index.html")).href);
  await page
    .getByRole("button", { name: "Single Crystal XRD", exact: true })
    .click();
  await page.getByTestId("sc-primary-action").waitFor();
  for (const tab of ["Cell", "Geometry", "Scaling"]) {
    await page.getByRole("tab", { name: tab, exact: true }).click();
    await page.evaluate(
      () =>
        new Promise((resolve) =>
          requestAnimationFrame(() => requestAnimationFrame(resolve)),
        ),
    );
    await page.screenshot({
      path: path.join(folder, `measured-${tab.toLowerCase()}.png`),
    });
  }
  await page.getByRole("tab", { name: "Background", exact: true }).click();
  await page
    .getByRole("checkbox", {
      name: "Fit omega background (arPLS)",
      exact: true,
    })
    .check();
  await page
    .getByRole("button", { name: "Apply settings", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Run background", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Stop processing", exact: true })
    .click();
  await page.getByTestId("sc-primary-action").waitFor();
  const stopped = (await native.invoke("scxrd_snapshot")).scxrd;
  assert.equal(stopped.stages[0].status, "paused");
  assert.match(stopped.error, /Stopped during/);
  assert.equal(stopped.config.background, true);
  assert.equal(stopped.frames, 144);
  assert.equal(stopped.usableReflections, 0);
  await page.screenshot({ path: path.join(folder, "measured-stopped.png") });
  assert.deepEqual(errors, []);
  await fs.writeFile(
    path.join(folder, "gui-receipt.json"),
    JSON.stringify(
      {
        ok: true,
        engine: "chromium",
        realScan: true,
        frames: 144,
        cancellation: stopped.error,
        settingsRetained: true,
        staleProductsCleared: true,
        pageErrors: errors,
      },
      null,
      2,
    ),
  );
  console.log("Measured GUI and cancellation passed");
} finally {
  await browser.close();
  await native.close();
}
