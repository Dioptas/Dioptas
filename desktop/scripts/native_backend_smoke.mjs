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
    const productRequests = [];
    page.on("pageerror", (error) => {
      errors.push(error.message);
      console.error(`${name}: ${error.stack}`);
    });
    await page.exposeFunction(
      "__nativeInvoke",
      async (action, payload = {}) => {
        productRequests.push({ action, products: payload.requested_products });
        if (action === "open_image" && !payload.path)
          payload.path = path.join(
            root,
            "desktop/tests/data/CeO2_Pilatus1M.tif",
          );
        if (action === "open_calibration" && !payload.path)
          payload.path = path.join(
            root,
            "desktop/tests/data/CeO2_Pilatus1M.poni",
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
      pathToFileURL(path.join(root, "desktop/dist/index.html")).href,
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
    const beforeReload = (await native.invoke("integration_diagnostics"))
      .integrationDiagnostics.cakeIntegrations;
    // Loading a PONI opens calibration Validation, which legitimately shows a
    // cake. Reload through Integration's real filename editor with Cake hidden.
    await page.getByLabel("Image filename", { exact: true }).press("Enter");
    await page.waitForFunction(() => !document.querySelector(".spin"));
    assert.equal(
      productRequests.findLast((r) => r.action === "open_image").products.cake,
      false,
    );
    assert.deepEqual(errors, []);
    assert.deepEqual(commandErrors, []);
    let snapshot = await native.invoke("state");
    assert.equal(snapshot.state.calibrated, true);
    assert.equal(snapshot.state.integration.trimZeros, true);
    assert.ok(
      snapshot.pattern.x.length > 0 && snapshot.pattern.x.length <= 1000,
    );
    assert.notEqual(snapshot.pattern.y[0], 0);
    assert.notEqual(snapshot.pattern.y.at(-1), 0);
    assert.equal(snapshot.cake, null, "Hidden cake should not be calculated");
    assert.equal(
      (await native.invoke("integration_diagnostics")).integrationDiagnostics
        .cakeIntegrations,
      beforeReload,
    );
    await page.screenshot({
      path: path.join(artifacts, `${name}-integration.png`),
    });
    const detector = await page
      .locator('[data-testid="detector-canvas"]')
      .boundingBox();
    assert.ok(detector && detector.width > 200 && detector.height > 200);
    await selectIntegrationDisplay(page, "cake");
    await page.getByTestId("cake-canvas").waitFor({ state: "visible" });
    snapshot = await native.invoke("state");
    assert.equal(snapshot.cake.width, 1000);
    assert.equal(snapshot.cake.height, 360);
    assert.equal(
      (await native.invoke("integration_diagnostics")).integrationDiagnostics
        .cakeIntegrations,
      beforeReload + 1,
    );
    const storedPattern = snapshot.pattern;
    await selectIntegrationDisplay(page, "image");
    await selectIntegrationDisplay(page, "cake");
    assert.equal(
      (await native.invoke("integration_diagnostics")).integrationDiagnostics
        .cakeIntegrations,
      beforeReload + 1,
    );
    assert.deepEqual((await native.invoke("state")).pattern, storedPattern);
    await page
      .getByRole("button", { name: "Calibration", exact: true })
      .click();
    await page.waitForFunction(
      () =>
        Number(
          document.querySelector('[data-testid="detector-canvas"]')?.dataset
            .ringCount,
        ) > 0,
    );
    await page.getByLabel("Show calibrant lines", { exact: true }).uncheck();
    await page.waitForFunction(
      () =>
        document.querySelector('[data-testid="detector-canvas"]')?.dataset
          .ringCount === "0",
    );
    await page.getByLabel("Show calibrant lines", { exact: true }).check();
    await page.waitForFunction(
      () =>
        Number(
          document.querySelector('[data-testid="detector-canvas"]')?.dataset
            .ringCount,
        ) > 0,
    );
    assert.equal(
      (await native.invoke("integration_diagnostics")).integrationDiagnostics
        .cakeIntegrations,
      beforeReload + 1,
    );
    await page.screenshot({ path: path.join(artifacts, `${name}-cake.png`) });
    await page.getByRole("button", { name: "Settings", exact: true }).click();
    await page
      .getByRole("region", { name: "Settings", exact: true })
      .getByRole("tab", { name: "Integration", exact: true })
      .click();
    const trim = page.getByLabel("Trim leading and trailing zeros", {
      exact: true,
    });
    assert.equal(await trim.isChecked(), true);
    for (const enabled of [false, true]) {
      await trim.setChecked(enabled);
      const apply = page.getByRole("button", {
        name: "Apply integration options",
        exact: true,
      });
      if (await apply.count()) await apply.click();
      await page.waitForFunction(
        async (enabled) =>
          (await window.pywebview.api.invoke("state", {})).state.integration
            .trimZeros === enabled,
        enabled,
      );
    }
    await page
      .getByRole("button", { name: "Close settings", exact: true })
      .click();
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
