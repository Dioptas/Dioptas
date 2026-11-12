import assert from "node:assert/strict";
import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { chromium, webkit } from "playwright";
import { nativeClient, root } from "./native_backend_client.mjs";
import { selectIntegrationDisplay } from "./integration_display.mjs";
const artifacts = path.join(root, "desktop/artifacts/map-detector-independent");
await mkdir(artifacts, { recursive: true });
const receipts = [];
for (const [name, type] of [
  ["chromium", chromium],
  ["webkit", webkit],
]) {
  const native = nativeClient();
  let browser;
  try {
    for (const [action, payload] of [
      [
        "open_image",
        { path: path.join(root, "desktop/tests/data/CeO2_Pilatus1M.tif") },
      ],
      [
        "open_calibration",
        { path: path.join(root, "desktop/tests/data/CeO2_Pilatus1M.poni") },
      ],
      [
        "map_load",
        { paths: [path.join(root, "desktop/tests/data/CeO2_Pilatus1M.tif")] },
      ],
    ]) {
      const r = await native.invoke(action, payload);
      assert(r.ok, r.error);
    }
    browser = await type.launch({ headless: true });
    const context = await browser.newContext({
      viewport: { width: 1440, height: 1000 },
    });
    const errors = [];
    context.on("page", (p) => p.on("pageerror", (e) => errors.push(e.message)));
    await context.exposeBinding(
      "__nativeInvoke",
      async (_, action, payload = {}) =>
        native.browserResult(await native.invoke(action, payload)),
    );
    await context.addInitScript(() => {
      window.pywebview = {
        api: {
          invoke: (action, payload) => window.__nativeInvoke(action, payload),
        },
      };
    });
    const page = await context.newPage();
    page.setDefaultTimeout(20000);
    await page.goto(
      pathToFileURL(path.join(root, "desktop/dist/index.html")).href,
    );
    const ready = async () => {
      await page.waitForFunction(() => !document.querySelector(".spin"));
      await page.waitForTimeout(300);
    };
    await page
      .getByRole("button", { name: "Integration", exact: true })
      .click();
    await selectIntegrationDisplay(page, "image");
    await ready();
    const popup = page.waitForEvent("popup");
    await page
      .getByRole("button", { name: "Undock detector image", exact: true })
      .click();
    const child = await popup;
    await child.getByTestId("detector-canvas").waitFor();
    await child.waitForTimeout(300);
    const range = (c) =>
      c.evaluate((el) => [+el.dataset.viewXMin, +el.dataset.viewXMax]);
    const integrationRange = await range(child.getByTestId("detector-canvas"));
    await page.getByRole("button", { name: "Map", exact: true }).click();
    await ready();
    const canvas = page
      .locator(".map-detector-panel")
      .getByTestId("detector-canvas");
    const tab = page.getByRole("tab", { name: "Image", exact: true });
    if (!(await canvas.isVisible()) && (await tab.isVisible()))
      await tab.click();
    await canvas.waitFor({ state: "visible" });
    await page.waitForTimeout(300);
    assert.equal(
      await page
        .locator(".map-detector-panel")
        .getByRole("button", { name: "Undock detector image", exact: true })
        .count(),
      0,
    );
    assert.equal(
      await page
        .locator(".map-detector-panel .detector-detached-placeholder")
        .count(),
      0,
    );
    const before = await range(canvas);
    const box = await canvas.boundingBox();
    await page.screenshot({
      path: path.join(artifacts, `${name}-embedded.png`),
    });
    await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
    await page.mouse.wheel(0, -350);
    await page.waitForFunction((before) => {
      const c = document.querySelector(
        '.map-detector-panel [data-testid="detector-canvas"]',
      );
      return +c.dataset.viewXMax - +c.dataset.viewXMin < before * 0.95;
    }, before[1] - before[0]);
    const zoom = await range(canvas);
    await page
      .getByRole("button", { name: "Integration", exact: true })
      .click();
    await ready();
    await child.getByTestId("detector-canvas").waitFor();
    const returned = await range(child.getByTestId("detector-canvas"));
    returned.forEach((v, i) =>
      assert(Math.abs(v - integrationRange[i]) < 1e-6),
    );
    await page.getByRole("button", { name: "Map", exact: true }).click();
    await ready();
    if (!(await canvas.isVisible()) && (await tab.isVisible()))
      await tab.click();
    await canvas.waitFor({ state: "visible" });
    await page.waitForTimeout(300);
    const restored = await range(canvas);
    restored.forEach((v, i) =>
      assert(Math.abs(v - zoom[i]) < 1e-6, JSON.stringify({ zoom, restored })),
    );
    await child.close();
    await page.waitForTimeout(300);
    assert(await canvas.isVisible());
    const after = await range(canvas);
    after.forEach((v, i) => assert(Math.abs(v - zoom[i]) < 1e-6));
    assert.deepEqual(errors, []);
    receipts.push({
      browser: name,
      headless: true,
      embedded: true,
      noDetachAction: true,
      independentZoom: true,
      closeIntegrationWindowPreservesMap: true,
    });
  } finally {
    await browser?.close();
    await native.close();
  }
}
await writeFile(
  path.join(artifacts, "receipt.json"),
  JSON.stringify(receipts, null, 2),
);
console.log(JSON.stringify(receipts));
