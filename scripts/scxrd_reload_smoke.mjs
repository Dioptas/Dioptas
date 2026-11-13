import assert from "node:assert/strict";
import { readFile, mkdtemp, copyFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { createServer } from "vite";
import { chromium, webkit } from "playwright";
import { nativeClient, root } from "./native_backend_client.mjs";
import { lostCrystalScanMessage } from "../src/backendReloadSnapshot.ts";

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
    let holdSnapshot = false,
      releaseSnapshot;
    const browser = await engine.launch({ headless: true });
    try {
      const result = await loaded.invoke("scxrd_load", { paths: frames });
      assert.equal(result.ok, true, result.error);
      const page = await browser.newPage();
      const errors = [];
      page.on("pageerror", (e) => errors.push(e.message));
      await page.exposeFunction("__nativeInvoke", async (action, payload) => {
        const processor = active;
        const result = processor.browserResult(
          await processor.invoke(action, payload),
        );
        if (action === "scxrd_snapshot" && holdSnapshot) {
          holdSnapshot = false;
          return new Promise((resolve) => {
            releaseSnapshot = () => resolve(result);
          });
        }
        return result;
      });
      await page.addInitScript(() => {
        window.__documentToken = crypto.randomUUID();
        window.__scSnapshotReplies = 0;
        window.pywebview = {
          api: {
            invoke: async (action, payload) => {
              const result = await window.__nativeInvoke(action, payload);
              if (action === "scxrd_snapshot") window.__scSnapshotReplies++;
              return result;
            },
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
      const beforeReady = await page.evaluate(() => window.__scSnapshotReplies);
      await page.evaluate(() =>
        window.__reloadTestEvent({
          payload: { phase: "ready", message: "Session restored" },
        }),
      );
      await page.waitForFunction(
        (n) => window.__scSnapshotReplies > n,
        beforeReady,
      );
      await page.waitForTimeout(50);
      await page.getByTestId("detector-canvas").waitFor();
      assert.equal(await page.locator(".sc-empty").count(), 0);
      const beforeRefusal = await page.evaluate(
        () => window.__scSnapshotReplies,
      );
      const refusal =
        "Save your SCXRD recipe, then restart to update the backend.";
      await page.evaluate(
        (message) =>
          window.__reloadTestEvent({ payload: { phase: "error", message } }),
        "Backend update failed; current session retained. " + refusal,
      );
      await page.waitForFunction(
        (n) => window.__scSnapshotReplies > n,
        beforeRefusal,
      );
      await page.getByRole("alert").filter({ hasText: refusal }).waitFor();
      await page.getByTestId("detector-canvas").waitFor();
      await page.evaluate(() =>
        window.__reloadTestEvent({
          payload: { phase: "building", message: "Rebuilding Rust backend…" },
        }),
      );
      await page
        .getByRole("status")
        .filter({ hasText: "Rebuilding Rust backend…" })
        .waitFor();
      assert.equal(
        await page.getByRole("alert").filter({ hasText: refusal }).count(),
        0,
        "a newer build clears the previous update-owned failure",
      );
      // Hold a stale empty-worker snapshot, then let a newer successful update
      // finish first. The late empty snapshot must not clear the restored scan.
      active = empty;
      holdSnapshot = true;
      await page.evaluate(() =>
        window.__reloadTestEvent({
          payload: { phase: "error", message: "Old failed update" },
        }),
      );
      for (let i = 0; i < 100 && !releaseSnapshot; i++)
        await page.waitForTimeout(10);
      assert.ok(releaseSnapshot, "the old snapshot is held in flight");
      active = loaded;
      const beforeNewReady = await page.evaluate(
        () => window.__scSnapshotReplies,
      );
      await page.evaluate(() =>
        window.__reloadTestEvent({
          payload: { phase: "ready", message: "New worker restored" },
        }),
      );
      await page.waitForFunction(
        (n) => window.__scSnapshotReplies > n,
        beforeNewReady,
      );
      const beforeLate = await page.evaluate(() => window.__scSnapshotReplies);
      releaseSnapshot();
      await page.waitForFunction(
        (n) => window.__scSnapshotReplies > n,
        beforeLate,
      );
      await page.waitForTimeout(80);
      await page.getByTestId("detector-canvas").waitFor();
      assert.equal(
        await page.locator(".sc-empty").count(),
        0,
        "late snapshot cannot clear a restored scan",
      );
      assert.equal(
        await page
          .getByRole("alert")
          .filter({ hasText: lostCrystalScanMessage })
          .count(),
        0,
      );
      const beforeFailure = await page.evaluate(
        () => window.__scSnapshotReplies,
      );
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
      await page.waitForFunction(
        (n) => window.__scSnapshotReplies > n,
        beforeFailure,
      );
      await page.locator(".sc-empty").waitFor();
      const guidance = page
        .getByRole("alert")
        .filter({ hasText: lostCrystalScanMessage });
      await guidance.waitFor();
      assert.equal(
        await page.getByRole("dialog").count(),
        0,
        "update guidance must not interrupt with a modal",
      );
      await page.waitForTimeout(4700);
      await guidance.waitFor();
      await page
        .getByRole("button", { name: "View error details", exact: true })
        .click();
      const details = page.getByRole("dialog", {
        name: "Error details",
        exact: true,
      });
      await details
        .getByText(lostCrystalScanMessage, { exact: true })
        .waitFor();
      await page.keyboard.press("Escape");
      await page
        .getByRole("button", {
          name: "Dismiss scan recovery message",
          exact: true,
        })
        .waitFor();
      assert.equal(await page.getByTestId("detector-canvas").count(), 0);
      await page.evaluate(() =>
        window.__reloadTestEvent({
          payload: {
            phase: "building",
            message: "Building while recovery is pending…",
          },
        }),
      );
      await page
        .getByRole("status")
        .filter({ hasText: "Building while recovery is pending…" })
        .waitFor();
      await page.evaluate(() =>
        window.__reloadTestEvent({
          payload: { phase: "error", message: "Another update refused" },
        }),
      );
      await guidance.waitFor();
      active = loaded;
      const beforeRecovery = await page.evaluate(
        () => window.__scSnapshotReplies,
      );
      await page.evaluate(() =>
        window.__reloadTestEvent({
          payload: { phase: "ready", message: "Scan restored" },
        }),
      );
      await page.waitForFunction(
        (n) => window.__scSnapshotReplies > n,
        beforeRecovery,
      );
      await page.getByTestId("detector-canvas").waitFor();
      await guidance.waitFor({ state: "hidden" });
      await page.evaluate(
        (message) =>
          window.__reloadTestEvent({ payload: { phase: "error", message } }),
        refusal,
      );
      await page
        .getByRole("button", { name: "Dismiss update message", exact: true })
        .click();
      await page
        .getByRole("alert")
        .filter({ hasText: refusal })
        .waitFor({ state: "hidden" });
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
