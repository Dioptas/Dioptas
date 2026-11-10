// Rust-backed UI regression: collapsing preserves plots, pending edits and splitter size.
import assert from "node:assert/strict";
import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";
import { createServer } from "vite";
import { chromium, webkit } from "playwright";
import { nativeClient, root } from "./native_backend_client.mjs";

const artifacts = path.join(root, "desktop/artifacts/integration-panel");
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
    const native = nativeClient(),
      browser = await engine.launch({ headless: true }),
      errors = [];
    try {
      for (const [command, payload] of [
        ["example", {}],
        [
          "open_calibration",
          { path: path.join(root, "dioptas/tests/data/CeO2_Pilatus1M.poni") },
        ],
        ["integration_settings", { bins: 256, cake_bins: 36 }],
      ]) {
        const r = await native.invoke(command, payload);
        assert.ok(r.ok, r.error);
      }
      const page = await browser.newPage({
        viewport: { width: 1440, height: 1000 },
      });
      page.on("pageerror", (e) => errors.push(e.message));
      await page.exposeFunction("__panelInvoke", async (a, p) =>
        native.browserResult(await native.invoke(a, p)),
      );
      await page.addInitScript(() => {
        window.pywebview = {
          api: { invoke: (a, p) => window.__panelInvoke(a, p) },
        };
      });
      await page.goto(server.resolvedUrls.local[0]);
      const button = (name) => page.getByRole("button", { name, exact: true }),
        tab = (name) => page.getByRole("tab", { name, exact: true });
      const expanded = () => button("Collapse Integration controls"),
        collapsed = () => button("Expand Integration controls");
      const divider = () =>
        page.getByRole("separator", {
          name: "Controls and pattern divider",
          exact: true,
        });
      const settle = () =>
        page.evaluate(
          () =>
            new Promise((r) =>
              requestAnimationFrame(() => requestAnimationFrame(r)),
            ),
        );
      const verifyTabRows = async (expected) => {
        await settle();
        const geometry = await page
          .getByRole("tablist", { name: "Integration controls", exact: true })
          .evaluate((list) => {
            const tabs = [...list.querySelectorAll('[role="tab"]')];
            const bounds = list.getBoundingClientRect();
            return {
              rows: tabs.map((tab) =>
                Math.round(tab.getBoundingClientRect().y),
              ),
              overflow: list.scrollWidth > list.clientWidth + 1,
              clipped: tabs.some((tab) => {
                const box = tab.getBoundingClientRect();
                return (
                  box.left < bounds.left - 1 ||
                  box.right > bounds.right + 1 ||
                  tab.scrollWidth > tab.clientWidth + 1
                );
              }),
              scrollMode: getComputedStyle(list).overflowX,
            };
          });
        const rows = [...new Set(geometry.rows)];
        assert.equal(
          rows.length,
          expected,
          `expected ${expected} tab rows: ${JSON.stringify(geometry)}`,
        );
        if (expected === 2)
          assert.deepEqual(
            geometry.rows.map((y) => rows.indexOf(y)),
            [0, 0, 0, 1, 1, 1],
            "tabs form two balanced rows",
          );
        assert.equal(
          geometry.overflow,
          false,
          "tab strip has no horizontal overflow",
        );
        assert.equal(geometry.clipped, false, "all six full tab labels fit");
        assert.ok(
          !["auto", "scroll"].includes(geometry.scrollMode),
          "tabs do not create a horizontal scrollbar",
        );
      };
      await button("Integration").click();
      await page.getByTestId("pattern-canvas").waitFor();
      await tab("Image").click();
      assert.equal(await expanded().getAttribute("aria-expanded"), "true");
      assert.equal(await divider().getAttribute("aria-valuenow"), "38");
      await verifyTabRows(1);
      const imageDivider = page.getByRole("separator", {
        name: "Image and analysis divider",
        exact: true,
      });
      await imageDivider.press("End");
      await verifyTabRows(2);
      await imageDivider.press("Home");
      await verifyTabRows(1);

      await page
        .getByTestId("pattern-canvas")
        .evaluate((el) => (window.__panelPattern = el));
      await page
        .getByTestId("detector-canvas")
        .evaluate((el) => (window.__panelDetector = el));
      await divider().press("Shift+ArrowDown");
      await settle();
      const plot = page.getByTestId("pattern-canvas");
      const radialRange = () =>
        plot.evaluate((el) => [el.dataset.viewXMin, el.dataset.viewXMax]);
      const fittedRange = await radialRange();
      await plot.press("+");
      await settle();
      const zoomedRange = await radialRange();
      assert.notDeepEqual(
        zoomedRange,
        fittedRange,
        "the plot is zoomed before exercising layout changes",
      );
      const storedShare = await page.evaluate(() =>
        localStorage.getItem("dioptas-layout:controls-share"),
      );
      const panel = page.locator(".integration-layout > .sidebar"),
        before = await panel.boundingBox(),
        patternBefore = await page.getByTestId("pattern-canvas").boundingBox();
      const filename = page.getByRole("textbox", {
          name: "Image filename",
          exact: true,
        }),
        actualFilename = await filename.inputValue();
      await filename.fill("pending-image.tif");
      await expanded().click();
      await settle();
      assert.equal(await divider().count(), 0);
      assert.equal(
        await page
          .getByRole("tabpanel", { name: "Image controls", exact: true })
          .isVisible(),
        false,
      );
      assert.ok(
        (await panel.boundingBox()).height < 90,
        "collapsed panel contains only its tab strip",
      );
      assert.ok(
        (await page.getByTestId("pattern-canvas").boundingBox()).height >
          patternBefore.height + 100,
      );
      await tab("Image").click();
      await settle();
      assert.equal(
        await filename.inputValue(),
        "pending-image.tif",
        "selected tab reopens without discarding the pending filename",
      );
      assert.ok(
        Math.abs((await panel.boundingBox()).height - before.height) < 1,
      );
      assert.equal(
        await page.evaluate(() =>
          localStorage.getItem("dioptas-layout:controls-share"),
        ),
        storedShare,
      );
      await filename.fill(actualFilename);
      assert.deepEqual(
        await radialRange(),
        zoomedRange,
        "collapse and restore retain the pattern radial zoom",
      );
      await plot.press("f");
      assert.equal(
        await page
          .getByTestId("pattern-canvas")
          .evaluate((el) => el === window.__panelPattern),
        true,
      );
      assert.equal(
        await page
          .getByTestId("detector-canvas")
          .evaluate((el) => el === window.__panelDetector),
        true,
      );
      for (const large of [false, true]) {
        await button("Settings").click();
        await button(large ? "Larger" : "Standard").click();
        await button("Close settings").click();
        for (const viewport of [
          { width: 1440, height: 1000 },
          { width: 1000, height: 760 },
        ]) {
          await page.setViewportSize(viewport);
          await verifyTabRows(1);
          for (const label of [
            "Image",
            "Pattern",
            "Overlay",
            "Phase",
            "Background",
            "Corrections",
          ]) {
            await expanded().click();
            await tab(label).click();
            assert.equal(
              await page
                .getByRole("tabpanel", {
                  name: `${label} controls`,
                  exact: true,
                })
                .isVisible(),
              true,
            );
            assert.equal(
              await tab(label).getAttribute("aria-selected"),
              "true",
            );
          }
          await page.screenshot({
            path: path.join(
              artifacts,
              `${name}-${viewport.width}-${large ? "large" : "standard"}-expanded.png`,
            ),
          });
          await expanded().click();
          await verifyTabRows(1);
          const box = await collapsed().boundingBox();
          assert.ok(
            box &&
              box.x >= 0 &&
              box.x + box.width <= viewport.width &&
              box.y + box.height < viewport.height,
          );
          await page.screenshot({
            path: path.join(
              artifacts,
              `${name}-${viewport.width}-${large ? "large" : "standard"}-collapsed.png`,
            ),
          });
          await collapsed().press("Enter");
          assert.equal(
            await page
              .getByRole("tabpanel", {
                name: "Corrections controls",
                exact: true,
              })
              .isVisible(),
            true,
          );
          await expanded().click();
          await tab("Corrections").press("Home");
          assert.equal(
            await page
              .getByRole("tabpanel", { name: "Image controls", exact: true })
              .isVisible(),
            true,
          );
        }
      }
      await expanded().click();
      await button("As Overlay").click();
      await page.waitForFunction(() => !document.querySelector(".spin"));
      assert.equal(
        await collapsed().isVisible(),
        true,
        "capturing an overlay retains the current panel layout",
      );
      await tab("Overlay").click();
      assert.equal(
        await page
          .getByRole("tabpanel", { name: "Overlay controls", exact: true })
          .isVisible(),
        true,
      );
      await expanded().click();
      await button("Mask").click();
      await button("Integration").click();
      assert.equal(
        await collapsed().isVisible(),
        true,
        "mode switching retains the local collapsed state",
      );
      await page.reload();
      await button("Integration").click();
      assert.equal(
        await expanded().isVisible(),
        true,
        "a fresh session keeps the expanded default",
      );
      assert.equal(
        await page.evaluate(() =>
          localStorage.getItem("dioptas-layout:controls-share"),
        ),
        storedShare,
      );
      assert.deepEqual(errors, []);
      reports.push({
        browser: name,
        checks:
          "one/two balanced rows without scrollbars, panel resizing, all tabs, selected-tab reopen, keyboard, splitter size, pending edits, plot identity/zoom, overlay capture, mode switches, fresh-session default",
        errors,
      });
    } finally {
      await browser.close();
      await native.close();
    }
  }
} finally {
  await server.close();
}
await writeFile(
  path.join(artifacts, "results.json"),
  JSON.stringify(reports, null, 2) + "\n",
);
console.log(JSON.stringify(reports, null, 2));
