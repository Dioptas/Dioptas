import assert from "node:assert/strict";
import path from "node:path";
import { mkdir, writeFile } from "node:fs/promises";
import { pathToFileURL } from "node:url";
import { chromium, webkit } from "playwright";
import { nativeClient, root } from "./native_backend_client.mjs";
import { selectIntegrationDisplay } from "./integration_display.mjs";

const artifacts = path.join(root, "desktop/artifacts/native-backend");
await mkdir(artifacts, { recursive: true });
const results = [];
for (const [name, type] of [
  ["chromium", chromium],
  ["webkit", webkit],
]) {
  const native = nativeClient();
  let browser;
  try {
    const host = await native.invoke("__host__");
    assert.equal(host.runtime, "rust");
    assert.equal(
      host.engine,
      "dioptrin",
      "Build the native worker with --features dioptrin for this integration smoke",
    );
    browser = await type.launch({ headless: true });
    const page = await browser.newPage({
      viewport: { width: 1440, height: 940 },
    });
    page.setDefaultTimeout(30000);
    const errors = [];
    const commandErrors = [];
    page.on("pageerror", (error) => {
      errors.push(error.message);
      console.error(`${name}: ${error.stack}`);
    });
    await page.exposeFunction(
      "__nativeInvoke",
      async (action, payload = {}) => {
        if (action === "open_image" && !payload.path)
          payload.path = path.join(
            root,
            "dioptas/tests/data/CeO2_Pilatus1M.tif",
          );
        if (action === "open_calibration" && !payload.path)
          payload.path = path.join(
            root,
            "dioptas/tests/data/CeO2_Pilatus1M.poni",
          );
        const reply = await native.invoke(action, payload);
        if (!reply.ok) commandErrors.push({ action, error: reply.error });
        return native.browserResult(reply);
      },
    );
    await page.addInitScript(() => {
      window.pywebview = {
        api: {
          invoke: (action, payload) => window.__nativeInvoke(action, payload),
        },
      };
    });
    await page.goto(
      pathToFileURL(path.join(root, "dioptas/desktop/ui/index.html")).href,
    );
    await page.getByRole("button", { name: "Open image", exact: true }).click();
    await page.waitForFunction(
      () =>
        document.querySelector('[data-testid="detector-canvas"]')?.dataset
          .fullWidth === "981",
    );
    await page.getByRole("button", { name: /Load \.poni/ }).click();
    await page.waitForFunction(
      () => !!document.querySelector('[data-testid="pattern-canvas"]'),
    );
    await page
      .getByRole("button", { name: "Integration", exact: true })
      .click();
    await page.waitForTimeout(250);
    assert.deepEqual(errors, []);
    assert.deepEqual(commandErrors, []);
    const snapshot = await native.invoke("state");
    assert.equal(snapshot.state.calibrated, true);
    assert.equal(snapshot.pattern.x.length, 1000);
    assert.equal(snapshot.cake.width, 1000);
    assert.equal(snapshot.cake.height, 360);
    await page.screenshot({
      path: path.join(artifacts, `${name}-integration.png`),
    });
    const detector = await page
      .locator('[data-testid="detector-canvas"]')
      .boundingBox();
    assert.ok(detector && detector.width > 200 && detector.height > 200);
    await selectIntegrationDisplay(page, "cake");
    await page.screenshot({ path: path.join(artifacts, `${name}-cake.png`) });
    assert.deepEqual(errors, []);
    assert.deepEqual(commandErrors, []);
    results.push({
      browser: name,
      runtime: host.runtime,
      engine: host.engine,
      shape: snapshot.state.shape,
      patternBins: snapshot.pattern.x.length,
      cakeShape: [snapshot.cake.height, snapshot.cake.width],
      errors,
      commandErrors,
    });
  } finally {
    await browser?.close();
    await native.close();
  }
}
await writeFile(
  path.join(artifacts, "browser-results.json"),
  JSON.stringify(results, null, 2) + "\n",
);
console.log(JSON.stringify(results, null, 2));
