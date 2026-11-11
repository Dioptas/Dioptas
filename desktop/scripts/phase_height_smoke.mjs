// Short Phase panels retain separated, reachable actions and independent table scrolling.
import assert from "node:assert/strict";
import path from "node:path";
import { mkdir, writeFile } from "node:fs/promises";
import { createServer } from "vite";
import { chromium, webkit } from "playwright";
import { nativeClient, root } from "./native_backend_client.mjs";
import { setInterfaceTextSize } from "./plot_navigation.mjs";

const artifacts = path.join(root, "desktop/artifacts/phase-height");
await mkdir(artifacts, { recursive: true });
const server = await createServer({
  root: path.join(root, "desktop"),
  server: { host: "127.0.0.1", port: 0 },
});
await server.listen();
const reports = [];
try {
  for (const [name, engine] of [
    ["chromium", chromium],
    ["webkit", webkit],
  ]) {
    const native = nativeClient();
    const browser = await engine.launch({ headless: true });
    try {
      const page = await browser.newPage({
        viewport: { width: 1000, height: 668 },
      });
      const errors = [];
      page.on("pageerror", (error) => errors.push(error.message));
      await page.exposeFunction("__phaseHeightInvoke", async (action, args) =>
        native.browserResult(await native.invoke(action, args)),
      );
      await page.addInitScript(() => {
        window.pywebview = {
          api: {
            invoke: (action, args) => window.__phaseHeightInvoke(action, args),
          },
        };
      });
      for (const count of [0, 15]) {
        if (count) {
          const result = await native.invoke("integration_phase", {
            operation: "load",
            paths: Array(count).fill(
              path.join(root, "dioptas/tests/data/jcpds/au_version3.jcpds"),
            ),
          });
          assert.ok(result.ok, result.error);
        }
        await page.goto(server.resolvedUrls.local[0]);
        await page
          .getByRole("button", { name: "Integration", exact: true })
          .click();
        await page.getByRole("tab", { name: "Phase", exact: true }).click();
        for (const large of [false, true]) {
          await setInterfaceTextSize(page, large);
          for (const width of [1000, 1440, 2600]) {
            await page.setViewportSize({ width, height: 668 });
            const divider = page.getByRole("separator", {
              name: "Controls and pattern divider",
              exact: true,
            });
            for (const height of ["Home", "End"]) {
              await divider.press(height);
              await page.evaluate(
                () =>
                  new Promise((resolve) =>
                    requestAnimationFrame(() => requestAnimationFrame(resolve)),
                  ),
              );
              const panel = page.locator(".integration-tab-phase");
              const controls = page.getByTestId("phase-controls");
              const metrics = await controls.evaluate((el) => {
                const rail = el.querySelector(".phase-toolbar");
                const buttons = [...rail.querySelectorAll("button")];
                const bounds = buttons.map((b) => b.getBoundingClientRect());
                const table = el.querySelector(".phase-table-scroll");
                const box = el.getBoundingClientRect();
                const reference = el.querySelector(".phase-selected-reference");
                const steps = el
                  .querySelector(".phase-parameters")
                  .getBoundingClientRect();
                const tableBox = table.getBoundingClientRect();
                return {
                  width: box.width,
                  height: box.height,
                  panelHeight: el.parentElement.clientHeight,
                  panelScroll: el.parentElement.scrollHeight,
                  gaps: bounds.slice(1).map((b, i) => b.top - bounds[i].bottom),
                  tableHeight: table.clientHeight,
                  tableScroll: table.scrollHeight,
                  regionsSeparated:
                    box.width > 600 ||
                    (steps.bottom <= tableBox.top + 1 &&
                      (!reference ||
                        tableBox.bottom <=
                          reference.getBoundingClientRect().top + 1)),
                };
              });
              const context = JSON.stringify({
                name,
                count,
                large,
                width,
                height,
                metrics,
              });
              assert.ok(
                metrics.gaps.every((gap) => gap >= 1),
                context,
              );
              assert.ok(metrics.regionsSeparated, context);
              assert.ok(
                metrics.height < 550,
                `Table rows must not expand the panel: ${context}`,
              );
              if (count)
                assert.ok(metrics.tableScroll > metrics.tableHeight, context);
              // Scroll each tool into view and verify its actual hit target, including disabled tools.
              const tools = controls.locator(
                ".phase-toolbar button, .phase-list-actions button",
              );
              for (const tool of await tools.all()) {
                await tool.scrollIntoViewIfNeeded();
                assert.ok(
                  await tool.evaluate((el) => {
                    const b = el.getBoundingClientRect();
                    const hit = document.elementFromPoint(
                      b.left + b.width / 2,
                      b.top + b.height / 2,
                    );
                    return hit === el || el.contains(hit);
                  }),
                  `${await tool.getAttribute("aria-label")}: ${context}`,
                );
              }
              if (width === 1000 && height === "Home") {
                await panel.evaluate((el) => {
                  el.scrollTop = 0;
                });
                await panel.screenshot({
                  path: path.join(
                    artifacts,
                    `${name}-${count}-${large ? "large" : "normal"}.png`,
                  ),
                });
              }
              reports.push({ name, count, large, width, height, ...metrics });
            }
          }
        }
      }
      assert.deepEqual(errors, []);
    } finally {
      await browser.close();
      await native.close();
    }
  }
  await writeFile(
    path.join(artifacts, "report.json"),
    JSON.stringify(reports, null, 2),
  );
  console.log(
    `Phase height checks passed: ${reports.length} layouts across Chromium/WebKit, both text sizes, empty/populated tables and splitter extremes.`,
  );
} finally {
  await server.close();
}
