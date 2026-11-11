// Real native Overlay UI: sweep actual splitter widths through every wrap boundary.
import assert from "node:assert/strict";
import path from "node:path";
import os from "node:os";
import { mkdtemp, mkdir, writeFile, rm } from "node:fs/promises";
import { createServer } from "vite";
import { chromium, webkit } from "playwright";
import { nativeClient, root } from "./native_backend_client.mjs";

const temp = await mkdtemp(path.join(os.tmpdir(), "dioptas-overlay-sweep-"));
const artifacts = path.join(root, "desktop/artifacts/overlay-responsive-sweep");
await mkdir(artifacts, { recursive: true });
const curve = path.join(temp, "pattern.xy");
await writeFile(
  curve,
  Array.from({ length: 101 }, (_, i) => `${i * 0.1} ${10 + (i % 11)}`).join(
    "\n",
  ),
);
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
    const native = nativeClient(),
      browser = await engine.launch({ headless: true }),
      errors = [];
    try {
      for (const [action, args] of [
        ["integration_open_pattern", { path: curve }],
        ["integration_overlay", { operation: "capture" }],
      ]) {
        const result = await native.invoke(action, args);
        assert.ok(result.ok, result.error);
      }
      const page = await browser.newPage({
        viewport: { width: 2640, height: 1000 },
      });
      page.on("pageerror", (error) => errors.push(error.message));
      await page.exposeFunction("__sweepInvoke", async (action, args) =>
        native.browserResult(await native.invoke(action, args)),
      );
      await page.addInitScript(() => {
        window.pywebview = {
          api: { invoke: (action, args) => window.__sweepInvoke(action, args) },
        };
      });
      await page.goto(server.resolvedUrls.local[0]);
      const button = (label) =>
        page.getByRole("button", { name: label, exact: true });
      await button("Integration").click();
      await page.getByRole("tab", { name: "Overlay", exact: true }).click();
      for (const text of ["Standard", "Larger"]) {
        await button("Settings").click();
        await button(text).click();
        await button("Close settings").click();
        await page.setViewportSize({ width: 2640, height: 1000 });
        await page
          .getByRole("separator", {
            name: "Image and analysis divider",
            exact: true,
          })
          .press("End");
        const transitions = [],
          samples = [];
        for (let width = 2640; width >= 1440; width -= 16) {
          await page.setViewportSize({ width, height: 1000 });
          await page.evaluate(
            () =>
              new Promise((resolve) =>
                requestAnimationFrame(() => requestAnimationFrame(resolve)),
              ),
          );
          const geometry = await page
            .locator(".qt-overlay-controls")
            .evaluate((el) => {
              const parameters = el.querySelector(".qt-overlay-parameters"),
                box = parameters.getBoundingClientRect(),
                table = el
                  .querySelector(".qt-overlay-table-region")
                  .getBoundingClientRect(),
                compact = el.clientWidth <= 600;
              const controls = [
                ...parameters.querySelectorAll("input, button"),
              ].filter((control) => control.getClientRects().length);
              const occluded = controls
                .filter((control) => {
                  const b = control.getBoundingClientRect();
                  const hit = document.elementFromPoint(
                    b.left + b.width / 2,
                    b.top + b.height / 2,
                  );
                  return (
                    !hit ||
                    !control.contains(hit) ||
                    (compact && b.bottom > table.top + 0.5) ||
                    b.top < box.top - 0.5 ||
                    b.bottom > box.bottom + 0.5
                  );
                })
                .map((control) => control.getAttribute("aria-label"));
              return {
                width: el.clientWidth,
                layout: el.dataset.toolbarLayout,
                spacing:
                  el
                    .querySelector('[aria-label="Waterfall separation"]')
                    .getClientRects().length > 0,
                overlapping: compact && box.bottom > table.top + 0.5,
                overflow:
                  parameters.scrollWidth > parameters.clientWidth + 1 ||
                  el.scrollWidth > el.clientWidth + 1,
                rows: compact
                  ? [
                      ...new Set(
                        controls.map((control) =>
                          Math.round(control.getBoundingClientRect().top),
                        ),
                      ),
                    ].length
                  : null,
                occluded,
              };
            });
          samples.push({ viewport: width, ...geometry });
          assert.deepEqual(geometry.occluded, [], JSON.stringify(geometry));
          assert.ok(
            !geometry.overlapping && !geometry.overflow,
            JSON.stringify(geometry),
          );
          if (geometry.width <= 600) {
            assert.equal(
              geometry.spacing,
              !geometry.layout.endsWith("reduced"),
              JSON.stringify(geometry),
            );
            // Inputs are 23px and buttons 25px, so compare their shared centerlines.
            const rowCount = await page
              .locator(".qt-overlay-parameters")
              .evaluate(
                (el) =>
                  new Set(
                    [...el.querySelectorAll("input, button")]
                      .filter((c) => c.getClientRects().length)
                      .map((c) =>
                        Math.round(
                          c.getBoundingClientRect().top +
                            c.getBoundingClientRect().height / 2,
                        ),
                      ),
                  ).size,
              );
            assert.equal(
              rowCount,
              geometry.layout.startsWith("two-rows") ? 2 : 1,
              JSON.stringify(geometry),
            );
            if (transitions.at(-1)?.layout !== geometry.layout) {
              transitions.push({
                width: geometry.width,
                layout: geometry.layout,
              });
              await page.screenshot({
                path: path.join(
                  artifacts,
                  `${name}-${text}-${geometry.layout}.png`,
                ),
              });
            }
          }
        }
        assert.deepEqual(
          transitions.map((t) => t.layout),
          ["single", "reduced", "two-rows"],
          JSON.stringify(transitions),
        );
        reports.push({ browser: name, text, transitions, samples });
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
    JSON.stringify(
      reports.map(({ samples, ...report }) => ({
        ...report,
        widthsChecked: samples.length,
      })),
      null,
      2,
    ),
  );
} finally {
  await server.close();
  await rm(temp, { recursive: true, force: true });
}
