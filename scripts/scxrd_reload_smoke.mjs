import assert from "node:assert/strict";
import { readFile, mkdtemp, copyFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { createServer } from "vite";
import { chromium, webkit } from "playwright";
import { nativeClient, root } from "./native_backend_client.mjs";

// Only the Tauri event subscription is adapted for a headless browser. The App,
// reload callback, snapshot application and both Rust processors are real.
const hook = path.join(root, "src/useBackendReload.ts");
const source = await readFile(hook, "utf8");
const adapted = source
  .replace(
    'import { isTauri } from "@tauri-apps/api/core";',
    "const isTauri = () => true;",
  )
  .replace(
    'import { listen } from "@tauri-apps/api/event";',
    "async function listen<T>(_: string, callback: (event: {payload:T}) => void) { window.__reloadTestEvent = callback; return () => {}; }",
  );
assert.notEqual(adapted, source);
const server = await createServer({
  root,
  logLevel: "error",
  server: { host: "127.0.0.1", port: 0, watch: null },
  plugins: [
    {
      name: "headless-reload-events",
      enforce: "pre",
      load(id) {
        if (id === hook) return adapted;
      },
    },
  ],
});
const fixture = await mkdtemp(path.join(tmpdir(), "scxrd-reload-ui-"));
const frames = [];
for (let i = 0; i < 3; i++) {
  const frame = path.join(fixture, `frame_${i}.tif`);
  await copyFile(path.join(root, "tests/data/CeO2_Pilatus1M.tif"), frame);
  frames.push(frame);
}
try {
  await server.listen();
  for (const [name, engine] of Object.entries({ chromium, webkit })) {
    const loaded = nativeClient(),
      empty = nativeClient();
    let active = loaded;
    const browser = await engine.launch({ headless: true });
    try {
      const result = await loaded.invoke("scxrd_load", { paths: frames });
      assert.equal(result.ok, true, result.error);
      const page = await browser.newPage();
      const errors = [];
      page.on("pageerror", (e) => errors.push(e.message));
      await page.exposeFunction("__nativeInvoke", async (action, payload) =>
        active.browserResult(await active.invoke(action, payload)),
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
      await page
        .getByRole("button", { name: "Single Crystal XRD", exact: true })
        .click();
      await page.getByTestId("detector-canvas").waitFor();
      await page.waitForFunction(() => !!window.__reloadTestEvent);
      const token = await page.evaluate(() => window.__documentToken);
      await page.evaluate(() =>
        window.__reloadTestEvent({
          payload: { phase: "ready", message: "Session restored" },
        }),
      );
      await page.getByTestId("detector-canvas").waitFor();
      // Model a session already lost by the previous version's unsafe swap.
      active = empty;
      await page.evaluate(() =>
        window.__reloadTestEvent({
          payload: {
            phase: "error",
            message: "Backend update refused; current session retained",
          },
        }),
      );
      await page.locator(".sc-empty").waitFor();
      await page
        .getByText(
          "An earlier backend update lost the loaded rotation scan. Open the frames again to continue; your original files are unchanged.",
          { exact: true },
        )
        .waitFor();
      assert.equal(await page.getByTestId("detector-canvas").count(), 0);
      assert.equal(
        await page.evaluate(() => window.__documentToken),
        token,
        "reconciliation must not reload the page",
      );
      assert.equal(
        (await loaded.invoke("scxrd_snapshot")).scxrd.frames,
        3,
        "test retains the original processor",
      );
      assert.deepEqual(errors, [], `${name}: no page failures`);
      console.log(
        `${name}: App clears a stale SC image after a refused update and displays reload guidance without remounting`,
      );
    } finally {
      await browser.close();
      loaded.close();
      empty.close();
    }
  }
} finally {
  await server.close();
  await rm(fixture, { recursive: true, force: true });
}
