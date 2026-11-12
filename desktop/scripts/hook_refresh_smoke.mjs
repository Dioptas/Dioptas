import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import path from "node:path";
import { createServer } from "vite";
import { chromium, webkit } from "playwright";
import { nativeClient, root } from "./native_backend_client.mjs";

// Change the hook layout in memory, without editing files watched by a user's
// preview. This reproduces the Batch update that crashed App during refresh.
const desktop = path.join(root, "desktop");
const hookPath = path.join(desktop, "src/batchWindow.ts");
const updated = await readFile(hookPath, "utf8");
const previous = updated.replace(
  /const published = useRef<\{[\s\S]*?\}>\(\{ batch: undefined, base: 0, sequence: 0 \}\);/,
  "const published = { current: { batch: undefined, base: 0, sequence: 0 } };",
);
assert.notEqual(previous, updated, "Fixture must remove one hook");

for (const [name, engine] of Object.entries({ chromium, webkit })) {
  let version = 0;
  const server = await createServer({
    root: desktop,
    logLevel: "error",
    server: { host: "127.0.0.1", port: 0, watch: null },
    plugins: [
      {
        name: "batch-hook-refresh-fixture",
        enforce: "pre",
        load(id) {
          if (id === hookPath)
            return `${version ? updated : previous}\nglobalThis.__batchHookVersion = ${version};`;
        },
      },
    ],
  });
  const native = nativeClient();
  let browser;
  try {
    const opened = await native.invoke("open_image", {
      path: path.join(root, "desktop/tests/data/CeO2_Pilatus1M.tif"),
    });
    assert.equal(opened.ok, true, opened.error);
    await server.listen();
    browser = await engine.launch({ headless: true });
    const page = await browser.newPage();
    const errors = [];
    page.on("pageerror", (error) => errors.push(error.message));
    page.on("console", (message) => {
      if (message.type() === "error") errors.push(message.text());
    });
    await page.exposeFunction("__nativeInvoke", async (action, payload) =>
      native.browserResult(await native.invoke(action, payload)),
    );
    await page.addInitScript(() => {
      window.__documentToken = crypto.randomUUID();
      window.pywebview = {
        api: {
          invoke: (action, payload) => window.__nativeInvoke(action, payload),
        },
      };
    });
    await page.goto(server.resolvedUrls.local[0]);
    const canvas = page.getByTestId("detector-canvas");
    await canvas.waitFor();
    const token = await page.evaluate(() => window.__documentToken);
    const hook = server.environments.client.moduleGraph.getModuleById(hookPath);
    assert.ok(hook);
    // Layout changes must remount safely; ordinary edits must retain UI state.
    for (version of [1, 2, 0]) {
      if (version === 2)
        await page
          .getByRole("button", { name: "Settings", exact: true })
          .click();
      await server.environments.client.reloadModule(hook);
      await page.waitForFunction(
        (v) => window.__batchHookVersion === v,
        version,
      );
      // Wait for React Refresh's debounced commit, not just module evaluation.
      await page.waitForTimeout(500);
      assert.equal(await page.evaluate(() => window.__documentToken), token);
      assert.deepEqual(errors, [], `${name}: refresh must not crash App`);
      assert.equal(await page.getByRole("alert").count(), 0);
      if (version === 2) {
        await page
          .getByRole("region", { name: "Settings", exact: true })
          .waitFor();
        await page
          .getByRole("button", { name: "Close settings", exact: true })
          .click();
      }
      await page.getByRole("button", { name: "Mask", exact: true }).click();
      await page
        .getByRole("button", { name: "Integration", exact: true })
        .click();
      await canvas.waitFor();
    }
    const state = await native.invoke("state");
    assert.equal(state.state.imageName, opened.state.imageName);
    console.log(
      `${name}: hook additions/removals refresh without a crash or document reload`,
    );
  } finally {
    await browser?.close();
    await server.close();
    await native.close();
  }
}
