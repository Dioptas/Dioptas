import assert from "node:assert/strict";
import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { chromium, webkit } from "playwright";
import { nativeClient, root } from "./native_backend_client.mjs";

const artifacts = path.join(root, "desktop/artifacts/processing-workers");
await mkdir(artifacts, { recursive: true });
const receipts = [];
for (const [name, type] of [
  ["chromium", chromium],
  ["webkit", webkit],
]) {
  const native = nativeClient();
  const browser = await type.launch({ headless: true });
  const errors = [];
  const commands = [];
  const call = async (action, payload = {}) => {
    commands.push(action);
    const r = await native.invoke(action, payload);
    assert.equal(r.ok, true, `${action}: ${r.error}`);
    return r;
  };
  try {
    const context = await browser.newContext({
      viewport: { width: 1000, height: 700 },
    });
    await context.exposeFunction("__nativeInvoke", async (a, p) =>
      native.browserResult(await call(a, p)),
    );
    await context.addInitScript(() => {
      window.__pending = 0;
      window.pywebview = {
        api: {
          invoke: async (a, p) => {
            window.__pending++;
            try {
              return await window.__nativeInvoke(a, p);
            } finally {
              window.__pending--;
            }
          },
        },
      };
    });
    const page = await context.newPage();
    page.on("pageerror", (e) => errors.push(e.message));
    const url = pathToFileURL(
      path.join(root, "dioptas/desktop/ui/index.html"),
    ).href;
    const ready = () =>
      page.waitForFunction(
        () =>
          document.querySelector(".app") &&
          !document.querySelector(".spin") &&
          !window.__pending,
      );
    const workers = () =>
      page.getByLabel("Processing workers", { exact: true });
    await page.goto(url);
    await ready();
    // Mask mode exercises the command path that ordinarily adds deferred
    // integration payloads; resource preferences must not receive that flag.
    await page.getByRole("button", { name: "Mask", exact: true }).click();
    await page.getByRole("button", { name: "Settings", exact: true }).click();
    await workers().selectOption("1");
    await ready();
    assert.equal((await call("state")).state.processingWorkers.effective, 1);
    const available = (await call("state")).state.processingWorkers.available;
    const count = Math.min(4, available);
    await workers().selectOption(String(count));
    await ready();
    assert.equal(
      (await call("state")).state.processingWorkers.effective,
      count,
    );
    assert.equal(
      await page.evaluate(() =>
        localStorage.getItem("dioptas-processing-workers"),
      ),
      String(count),
    );
    await page.screenshot({ path: path.join(artifacts, `${name}-manual.png`) });
    await call("processing_workers", { workers: 1 });
    await page.reload();
    await ready();
    await page.getByRole("button", { name: "Settings", exact: true }).click();
    await page.waitForFunction(
      (count) =>
        document.querySelector('[aria-label="Processing workers"]')?.value ===
          String(count) && !window.__pending,
      count,
    );
    assert.equal(
      (await call("state")).state.processingWorkers.requested,
      count,
    );
    assert.equal(await workers().inputValue(), String(count));
    await page
      .getByRole("button", { name: "Use default", exact: true })
      .click();
    await ready();
    const automatic = (await call("state")).state.processingWorkers;
    assert.equal(automatic.requested, null);
    assert.equal(automatic.effective, automatic.automatic);
    assert.equal(await workers().inputValue(), "auto");
    assert.equal(
      await page.evaluate(() =>
        localStorage.getItem("dioptas-processing-workers"),
      ),
      "null",
    );
    await page.evaluate(() => {
      document.querySelector(".app").dataset.textSize = "large";
    });
    await workers().scrollIntoViewIfNeeded();
    await page.screenshot({
      path: path.join(artifacts, `${name}-default-large.png`),
    });
    assert.deepEqual(errors, []);
    receipts.push({
      browser: name,
      available,
      manualWorkers: count,
      automaticWorkers: automatic.effective,
      persistedAcrossReload: true,
      resetToDefault: true,
      errors,
      settingsCalls: commands.filter((c) => c === "processing_workers").length,
    });
  } finally {
    await browser.close();
    await native.close();
  }
}
await writeFile(
  path.join(artifacts, "receipt.json"),
  `${JSON.stringify(receipts, null, 2)}\n`,
);
console.log(JSON.stringify(receipts, null, 2));
