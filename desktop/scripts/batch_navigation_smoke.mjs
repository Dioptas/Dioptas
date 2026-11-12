import assert from "node:assert/strict";
import path from "node:path";
import { createServer } from "vite";
import { chromium, webkit } from "playwright";
import { nativeClient, root } from "./native_backend_client.mjs";

// Real Rust data and real popup notifications, without a native test window.
const server = await createServer({
  root: path.join(root, "desktop"),
  server: { host: "127.0.0.1", port: 0 },
});
await server.listen();
try {
  for (const [name, engine] of [
    ["chromium", chromium],
    ["webkit", webkit],
  ]) {
    const native = nativeClient();
    const browser = await engine.launch({ headless: true });
    const requests = [],
      errors = [];
    const call = async (action, payload = {}) => {
      requests.push(action);
      // Resolve the file chooser only in this test adapter.
      if (action === "batch_load_data")
        payload = {
          paths: [path.join(root, "desktop/tests/data/image_001.tif")],
        };
      const result = await native.invoke(action, {
        ...payload,
        requested_products: { cake: false, rings: false },
      });
      assert.ok(result.ok, `${action}: ${result.error}`);
      return result;
    };
    try {
      await call("open_calibration", {
        path: path.join(root, "desktop/tests/data/LaB6_40keV_MarCCD.poni"),
      });
      await call("batch_load", {
        paths: ["001", "002"].map((i) =>
          path.join(root, `desktop/tests/data/image_${i}.tif`),
        ),
      });
      const context = await browser.newContext({
        viewport: { width: 1440, height: 1000 },
      });
      context.on("page", (p) =>
        p.on("pageerror", (e) => errors.push(e.message)),
      );
      await context.exposeFunction("__batchInvoke", async (a, p) =>
        native.browserResult(await call(a, p)),
      );
      await context.addInitScript(() => {
        window.pywebview = {
          api: { invoke: (a, p) => window.__batchInvoke(a, p) },
        };
        try {
          localStorage.setItem("dioptas-batch:docked", "true");
        } catch {
          /* about:blank before popup navigation */
        }
      });
      const page = await context.newPage();
      await page.goto(server.resolvedUrls.local[0]);
      await page
        .getByRole("button", { name: "Integration", exact: true })
        .click();
      await page
        .getByRole("button", { name: "Batch view…", exact: true })
        .click();
      await page
        .getByRole("button", { name: "Detach batch", exact: true })
        .waitFor();
      const popup = page.waitForEvent("popup");
      await page
        .getByRole("button", { name: "Detach batch", exact: true })
        .click();
      const child = await popup;
      await child.getByTestId("batch-heatmap").waitFor();
      const selected = (index) =>
        child.waitForFunction(
          (i) =>
            document.querySelector(".batch-series-panel")?.dataset
              .selectedFrame === String(i),
          index,
        );
      await selected(0);
      // Let initial readiness settle before measuring requests for each edit.
      await child.waitForTimeout(100);
      for (const index of [1, 0, 1]) {
        const before = requests.filter((a) => a === "batch_snapshot").length;
        await child.getByTestId("batch-heatmap").evaluate((c, index) => {
          const b = c.getBoundingClientRect(),
            d = c.dataset;
          const x = b.x + Number(d.plotLeft) + Number(d.plotWidth) / 2;
          const y =
            b.y +
            Number(d.plotTop) +
            Number(d.plotHeight) *
              (1 -
                (index + 0.5 - Number(d.viewYMin)) /
                  (Number(d.viewYMax) - Number(d.viewYMin)));
          c.setPointerCapture = c.releasePointerCapture = () => {};
          for (const type of ["pointerdown", "pointerup"])
            c.dispatchEvent(
              new PointerEvent(type, {
                bubbles: true,
                pointerId: 9,
                button: 0,
                buttons: type === "pointerdown" ? 1 : 0,
                clientX: x,
                clientY: y,
              }),
            );
        }, index);
        await selected(index);
        await child.waitForTimeout(100);
        assert.equal(
          requests.filter((a) => a === "batch_snapshot").length - before,
          0,
          "Selection reuses the main result without a snapshot",
        );
        assert.equal((await call("state")).batch.selected, index);
      }
      let snapshots = requests.filter((a) => a === "batch_snapshot").length;
      await child
        .getByRole("button", { name: "Batch unit Q", exact: true })
        .click();
      await child.waitForFunction(
        () =>
          document
            .querySelector('[aria-label="Batch unit Q"]')
            ?.getAttribute("aria-pressed") === "true",
      );
      await child.waitForTimeout(100);
      assert.equal(
        requests.filter((a) => a === "batch_snapshot").length - snapshots,
        1,
        "Axis changes refresh the full child model once",
      );
      snapshots = requests.filter((a) => a === "batch_snapshot").length;
      await child
        .getByRole("button", { name: "Load raw/proc data", exact: true })
        .click();
      await child.waitForFunction(() =>
        document
          .querySelector(".detached-batch-footer")
          ?.textContent.includes("Frame 1 of 1"),
      );
      await selected(0);
      await child.waitForTimeout(100);
      assert.equal(
        requests.filter((a) => a === "batch_snapshot").length - snapshots,
        1,
        "Replacing the series refreshes the full child model once",
      );
      const closed = child.waitForEvent("close");
      await child
        .getByRole("button", { name: "Dock batch below image", exact: true })
        .click();
      await closed;
      await page.getByTestId("batch-heatmap").waitFor();
      assert.deepEqual(errors, []);
      console.log(
        JSON.stringify({
          browser: name,
          runtime: "rust",
          selections: 3,
          snapshotsPerSelection: 0,
          docked: true,
          errors,
        }),
      );
    } finally {
      await browser.close();
      await native.close();
    }
  }
} finally {
  await server.close();
}
