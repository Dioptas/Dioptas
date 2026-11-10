import assert from "node:assert/strict";
import { copyFile, mkdtemp, mkdir, rm, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { chromium, webkit } from "playwright";
import { nativeClient, root } from "./native_backend_client.mjs";

const temp = await mkdtemp(path.join(os.tmpdir(), "dioptas-batch-background-"));
const input = path.join(temp, "stored.h5");
const artifacts = path.join(root, "desktop/artifacts/batch-background");
await mkdir(artifacts, { recursive: true });
await copyFile(
  path.join(root, "desktop/backend/tests/fixtures/batch_background_input.h5"),
  input,
);
const receipts = [];
try {
  for (const [name, type] of [
    ["chromium", chromium],
    ["webkit", webkit],
  ]) {
    const native = nativeClient();
    const browser = await type.launch({ headless: true });
    const context = await browser.newContext({
      viewport: { width: 1100, height: 800 },
    });
    const commands = [],
      errors = [];
    const invoke = async (action, payload = {}) => {
      commands.push(action);
      if (action === "batch_load_data" && !payload.paths)
        payload = {
          ...payload,
          paths: [
            path.join(
              root,
              "desktop/backend/tests/fixtures/batch_background_long.h5",
            ),
          ],
        };
      const r = await native.invoke(action, payload);
      assert.equal(r.ok, true, `${action}: ${r.error}`);
      return r;
    };
    try {
      await invoke("batch_open", { path: input });
      await context.exposeFunction("__nativeInvoke", async (a, p) =>
        native.browserResult(await invoke(a, p)),
      );
      await context.addInitScript(() => {
        try {
          localStorage.setItem("dioptas-batch:open", "true");
          localStorage.setItem("dioptas-batch:docked", "true");
        } catch {}
        window.__pending = 0;
        window.pywebview = {
          api: {
            invoke: async (a, p) => {
              if (a !== "progress") window.__pending++;
              try {
                return await window.__nativeInvoke(a, p);
              } finally {
                if (a !== "progress") window.__pending--;
              }
            },
          },
        };
      });
      context.on("page", (page) =>
        page.on("pageerror", (e) => errors.push(e.message)),
      );
      const page = await context.newPage();
      page.on("pageerror", (e) => errors.push(e.message));
      const ready = () =>
        page.waitForFunction(
          () =>
            document.querySelector(".app") &&
            !document.querySelector(".spin") &&
            !window.__pending,
        );
      await page.goto(
        pathToFileURL(path.join(root, "dioptas/desktop/ui/index.html")).href,
      );
      await ready();
      await page
        .getByRole("button", { name: "Integration", exact: true })
        .click();
      const dock = page.locator(".batch-dock");
      await dock.getByTestId("batch-heatmap").waitFor();
      const options = dock.getByRole("tab", { name: "Options", exact: true });
      await options.click();
      await dock
        .getByLabel("Batch background smooth width", { exact: true })
        .fill("0.37");
      await dock
        .getByLabel("Batch background iterations", { exact: true })
        .fill("31");
      await dock
        .getByLabel("Batch background polynomial order", { exact: true })
        .fill("8");
      await dock
        .getByRole("button", { name: "Extract background", exact: true })
        .click();
      await ready();
      await dock
        .getByText("Background available for every frame.", { exact: true })
        .waitFor();
      await dock
        .getByRole("button", { name: "Background subtracted", exact: true })
        .click();
      await ready();
      await dock
        .getByLabel("Batch background range minimum", { exact: true })
        .fill("2");
      await dock
        .getByLabel("Batch background range maximum", { exact: true })
        .fill("8");
      await dock
        .getByRole("button", { name: "Apply background range", exact: true })
        .click();
      await ready();
      await dock
        .getByRole("button", { name: "Cut to background range", exact: true })
        .click();
      await ready();
      let b = (await invoke("batch_snapshot")).batch;
      assert.equal(b.backgroundState.subtract, true);
      assert.equal(b.backgroundState.cut, true);
      assert.ok(b.x.length < 97 && b.x.length > 2);
      await dock.getByRole("tab", { name: "2D", exact: true }).click();
      await dock
        .getByRole("button", { name: "Normalize batch", exact: true })
        .click();
      await ready();
      assert.equal((await invoke("batch_snapshot")).batch.normalized, true);
      await dock.getByRole("button", { name: "Original", exact: true }).click();
      await ready();
      assert.equal(
        (await invoke("batch_snapshot")).batch.backgroundState.subtract,
        false,
      );
      for (const large of [false, true]) {
        await page.evaluate((large) => {
          document.querySelector(".app").dataset.textSize = large
            ? "large"
            : "normal";
        }, large);
        await page.setViewportSize({ width: 1000, height: 700 });
        await dock.getByTestId("batch-heatmap").waitFor();
        const bounds = await dock.evaluate((el) => {
          const r = el.getBoundingClientRect();
          return [
            ...el.querySelectorAll(".batch-background-display button"),
          ].map((e) => {
            const b = e.getBoundingClientRect();
            return {
              visible: b.width > 0,
              left: b.left >= r.left - 1,
              right: b.right <= r.right + 1,
              bottom: b.bottom <= r.bottom + 1,
            };
          });
        });
        assert.ok(
          bounds.every((b) => b.visible && b.left && b.right && b.bottom),
          JSON.stringify(bounds),
        );
        await options.click();
        await dock
          .getByRole("button", { name: "Extract background", exact: true })
          .scrollIntoViewIfNeeded();
        await page.screenshot({
          path: path.join(
            artifacts,
            `${name}-${large ? "large" : "normal"}-options.png`,
          ),
        });
        await dock.getByRole("tab", { name: "2D", exact: true }).click();
      }
      const popup = context.waitForEvent("page");
      await dock
        .getByRole("button", { name: "Detach batch", exact: true })
        .click();
      const child = await popup;
      await child.getByTestId("batch-heatmap").waitFor();
      await child
        .getByRole("button", { name: "Background subtracted", exact: true })
        .click();
      await child.waitForFunction(
        () =>
          document
            .querySelector('[aria-label="Background subtracted"]')
            ?.getAttribute("aria-pressed") === "true",
      );
      assert.equal(
        (await invoke("batch_snapshot")).batch.backgroundState.subtract,
        true,
      );
      await child.screenshot({
        path: path.join(artifacts, `${name}-detached.png`),
      });
      await child
        .getByRole("button", { name: "Dock batch below image", exact: true })
        .click();
      await dock.getByTestId("batch-heatmap").waitFor();
      assert.equal(
        await dock
          .getByRole("button", { name: "Background subtracted", exact: true })
          .getAttribute("aria-pressed"),
        "true",
      );
      await dock.getByRole("tab", { name: "Options", exact: true }).click();
      await dock
        .getByLabel("Batch background iterations", { exact: true })
        .fill("0");
      assert.equal(
        await dock
          .getByRole("button", { name: "Extract background", exact: true })
          .isEnabled(),
        false,
      );
      await dock
        .getByLabel("Batch background iterations", { exact: true })
        .fill("32");
      await dock
        .getByRole("button", { name: "Apply background settings", exact: true })
        .click();
      await ready();
      await dock
        .getByText(
          "Settings changed. Extract again to update the background.",
          { exact: true },
        )
        .waitFor();
      assert.equal(
        (await invoke("batch_snapshot")).batch.backgroundState.stale,
        true,
      );
      // Reproduce the reported workflow through the actual pattern controls.
      await page.getByRole("tab", { name: "Background", exact: true }).click();
      await page
        .getByRole("navigation", { name: "Background type" })
        .getByRole("button", { name: "Pattern", exact: true })
        .click();
      await page.getByLabel("Smooth width", { exact: true }).fill("0.37");
      await page.getByLabel("Iterations", { exact: true }).fill("31");
      await page.getByLabel("Polynomial order", { exact: true }).fill("8");
      await page.waitForFunction(
        () =>
          document.querySelector('[data-testid="pattern-canvas"]')?.dataset
            .regionUpdating === "false",
      );
      await ready();
      await page
        .getByRole("checkbox", {
          name: "Subtract automatic pattern background",
          exact: true,
        })
        .check();
      await page.waitForFunction(
        () =>
          document.querySelector('[data-testid="pattern-canvas"]')?.dataset
            .regionUpdating === "false",
      );
      await ready();
      await dock
        .getByRole("button", { name: "Use pattern background", exact: true })
        .click();
      await ready();
      const inherited = (await invoke("batch_snapshot")).batch;
      assert.equal(inherited.backgroundState.subtract, true);
      assert.equal(inherited.backgroundState.patternSettings, true);
      await dock.getByRole("tab", { name: "2D", exact: true }).click();
      assert.equal(
        await dock
          .getByRole("button", { name: "Background subtracted", exact: true })
          .getAttribute("aria-pressed"),
        "true",
      );
      await page.screenshot({
        path: path.join(artifacts, `${name}-pattern-background.png`),
      });
      // New stored files keep their persisted choice. Disable the live pattern
      // subtraction before loading the long cancellation input below.
      await page
        .getByRole("checkbox", {
          name: "Subtract automatic pattern background",
          exact: true,
        })
        .uncheck();
      await ready();
      // Exercise the existing footer progress/cancel path through real UI.
      await dock
        .getByRole("button", { name: "Load raw/proc data", exact: true })
        .click();
      await ready();
      await options.click();
      const beforeCancel = (await invoke("batch_snapshot")).batch;
      await dock
        .getByLabel("Batch background smooth width", { exact: true })
        .fill("0.2");
      await dock
        .getByLabel("Batch background iterations", { exact: true })
        .fill("99999");
      await dock
        .getByLabel("Batch background polynomial order", { exact: true })
        .fill("7");
      await dock
        .getByRole("button", { name: "Extract background", exact: true })
        .click();
      await page
        .getByRole("button", { name: "Cancel processing", exact: true })
        .click();
      await ready();
      assert.deepEqual((await invoke("batch_snapshot")).batch, beforeCancel);
      assert.deepEqual(errors, []);
      receipts.push({
        browser: name,
        commands: [...new Set(commands)],
        errors,
        storedOnly: true,
        detachedRouting: true,
        footerCancellation: true,
        patternBackground: true,
      });
    } finally {
      await context.close();
      await browser.close();
      await native.close();
    }
  }
} finally {
  await rm(temp, { recursive: true, force: true });
}
await writeFile(
  path.join(artifacts, "headless.json"),
  JSON.stringify(receipts, null, 2) + "\n",
);
console.log(JSON.stringify(receipts, null, 2));
