import assert from "node:assert/strict";
import path from "node:path";
import { mkdir, writeFile } from "node:fs/promises";
import { pathToFileURL } from "node:url";
import { chromium, webkit } from "playwright";
import { nativeClient, root } from "./native_backend_client.mjs";

const artifacts = path.join(root, "desktop/artifacts/native-mask");
await mkdir(artifacts, { recursive: true });
const receipts = [];
for (const [name, type] of [
  ["chromium", chromium],
  ["webkit", webkit],
]) {
  const native = nativeClient();
  let browser;
  const errors = [],
    commandErrors = [];
  try {
    assert.equal((await native.invoke("example")).ok, true);
    assert.equal(
      (
        await native.invoke("open_calibration", {
          path: path.join(root, "dioptas/tests/data/CeO2_Pilatus1M.poni"),
        })
      ).ok,
      true,
    );
    browser = await type.launch({ headless: true });
    const page = await browser.newPage({
      viewport: { width: 1440, height: 940 },
    });
    page.setDefaultTimeout(45000);
    page.on("pageerror", (e) => errors.push(e.message));
    await page.exposeFunction(
      "__nativeInvoke",
      async (action, payload = {}) => {
        const result = await native.invoke(action, payload);
        if (!result.ok) commandErrors.push({ action, error: result.error });
        return native.browserResult(result);
      },
    );
    await page.addInitScript(() => {
      window.__pending = 0;
      window.pywebview = {
        api: {
          invoke: async (action, payload) => {
            const track = !["pixel", "progress"].includes(action);
            if (track) window.__pending++;
            try {
              return await window.__nativeInvoke(action, payload);
            } finally {
              if (track) window.__pending--;
            }
          },
        },
      };
    });
    await page.goto(
      pathToFileURL(path.join(root, "dioptas/desktop/ui/index.html")).href,
    );
    const ready = async () => {
      await page.waitForFunction(
        () => window.__pending === 0 && !document.querySelector(".spin"),
      );
      await page.evaluate(
        () =>
          new Promise((resolve) =>
            requestAnimationFrame(() => requestAnimationFrame(resolve)),
          ),
      );
      await page.waitForFunction(
        () => window.__pending === 0 && !document.querySelector(".spin"),
      );
      assert.deepEqual(errors, []);
      assert.deepEqual(commandErrors, []);
    };
    await page.getByTestId("detector-canvas").waitFor();
    await ready();
    await page.getByRole("button", { name: "Mask", exact: true }).click();
    await ready();
    const counts = {};
    for (const plugin of ["Threshold Mask", "Cosmic Ray Mask", "Spot Mask"]) {
      await page.getByRole("checkbox", { name: plugin, exact: true }).click();
      await ready();
      const state = (await native.invoke("state")).state;
      const entry = state.maskDetails.plugins.find((p) => p.name === plugin);
      assert.equal(entry.enabled, true);
      counts[plugin] = entry.maskedPixels;
      await page
        .getByRole("button", { name: `${plugin} settings`, exact: true })
        .click();
      if (plugin === "Threshold Mask") {
        const field = page.getByLabel("Threshold Mask: Upper threshold", {
          exact: true,
        });
        await field.fill("1000");
        await field.press("Enter");
        await ready();
      } else if (plugin === "Cosmic Ray Mask") {
        const field = page.getByLabel("Cosmic Ray Mask: Window size", {
          exact: true,
        });
        await field.fill("7");
        await field.press("Enter");
        await ready();
      } else {
        await page
          .getByLabel("Spot Mask: Method", { exact: true })
          .selectOption("mean");
        await ready();
      }
      const configured = (
        await native.invoke("state")
      ).state.maskDetails.plugins.find((p) => p.name === plugin);
      assert.equal(
        configured.settings[
          plugin === "Threshold Mask"
            ? "above_value"
            : plugin === "Cosmic Ray Mask"
              ? "window_size"
              : "method"
        ],
        plugin === "Threshold Mask"
          ? 1000
          : plugin === "Cosmic Ray Mask"
            ? 7
            : "mean",
      );
    }
    const before = (await native.invoke("state")).state;
    assert.ok(before.maskedPixels > 0);
    await page
      .getByRole("button", { name: "Imprint Threshold Mask", exact: true })
      .click();
    await ready();
    const imprinted = (await native.invoke("state")).state;
    assert.equal(imprinted.maskDetails.plugins[0].enabled, false);
    await page.getByRole("button", { name: "Undo", exact: true }).click();
    await ready();
    assert.equal(
      (await native.invoke("state")).state.maskDetails.plugins[0].enabled,
      true,
    );
    assert.equal(
      (await native.invoke("state")).state.maskedPixels,
      before.maskedPixels,
    );
    await page.getByRole("button", { name: "Redo", exact: true }).click();
    await ready();
    const final = (await native.invoke("state")).state;
    assert.equal(final.maskDetails.plugins[0].enabled, false);
    // Imprinting changes Spot's excluded user pixels and therefore recomputes
    // its statistics. Redo must reproduce that post-imprint state exactly.
    assert.equal(final.maskedPixels, imprinted.maskedPixels);
    await page.screenshot({
      path: path.join(artifacts, `${name}-plugins.png`),
    });
    receipts.push({
      browser: name,
      plugins: counts,
      combinedPixels: final.maskedPixels,
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
  JSON.stringify(receipts, null, 2) + "\n",
);
console.log(JSON.stringify(receipts, null, 2));
