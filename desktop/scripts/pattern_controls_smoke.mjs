// Real Rust file workflows and compact Pattern layout in Chromium and WebKit.
import assert from "node:assert/strict";
import path from "node:path";
import os from "node:os";
import { mkdir, mkdtemp, writeFile, rm, realpath } from "node:fs/promises";
import { createServer } from "vite";
import { chromium, webkit } from "playwright";
import { nativeClient, root } from "./native_backend_client.mjs";
const artifacts = path.join(root, "desktop/artifacts/pattern-controls");
const temp = await realpath(
  await mkdtemp(path.join(os.tmpdir(), "dioptas-pattern-controls-")),
);
await mkdir(artifacts, { recursive: true });
for (const n of [1, 2, 3])
  await writeFile(
    path.join(temp, `long_diffraction_pattern_0000${n}.xy`),
    "1 10\n2 20\n3 15\n4 30\n",
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
      browser = await engine.launch({ headless: true });
    try {
      const page = await browser.newPage({
          viewport: { width: 1440, height: 900 },
        }),
        errors = [];
      page.on("pageerror", (e) => errors.push(e.message));
      await page.exposeFunction("__patternInvoke", async (a, p) =>
        native.browserResult(await native.invoke(a, p)),
      );
      await page.addInitScript(() => {
        window.pywebview = {
          api: { invoke: (a, p) => window.__patternInvoke(a, p) },
        };
      });
      await page.goto(server.resolvedUrls.local[0]);
      const button = (name) => page.getByRole("button", { name, exact: true });
      const tab = (name) => page.getByRole("tab", { name, exact: true });
      const field = (name) => page.getByRole("textbox", { name, exact: true });
      const check = (name) => page.getByRole("checkbox", { name, exact: true });
      const settle = () => page.waitForTimeout(150);
      await button("Integration").click();
      await tab("Pattern").click();
      await field("Pattern directory").fill(temp);
      await field("Pattern directory").press("Enter");
      await settle();
      await field("Pattern directory").fill("discarded");
      await field("Pattern directory").press("Escape");
      assert.equal(await field("Pattern directory").inputValue(), temp);
      await field("Pattern filename").fill("long_diffraction_pattern_00001.xy");
      await field("Pattern filename").press("Enter");
      await settle();
      assert.equal(
        await field("Pattern filename").inputValue(),
        "long_diffraction_pattern_00001.xy",
      );
      await field("Pattern filename").fill("discarded.xy");
      await field("Pattern filename").press("Escape");
      assert.equal(
        await field("Pattern filename").inputValue(),
        "long_diffraction_pattern_00001.xy",
      );
      await button("Integration next pattern").click();
      await settle();
      assert.equal(
        await field("Pattern filename").inputValue(),
        "long_diffraction_pattern_00002.xy",
      );
      await page
        .getByRole("combobox", { name: "Pattern file order", exact: true })
        .selectOption("time");
      await settle();
      await check(".chi").click();
      await page.waitForFunction(
        () => document.querySelector('[aria-label=".chi"]')?.checked,
      );
      await settle();
      await check("Autocreate").click();
      await settle();
      const snapshot = await native.invoke("state");
      assert.ok(snapshot.state.integration.autoSave);
      assert.ok(snapshot.state.integration.formats.includes(".chi"));
      assert.equal(snapshot.state.integration.outputDirectory, temp);
      assert.equal(snapshot.state.integration.patternFileIteration, "time");
      await check("Autocreate").click();
      await button("About Spottiness").click();
      assert.ok(
        await page.locator(".spottiness-explanation").first().isVisible(),
      );
      await button("About Spottiness").click();
      assert.equal(
        await page.locator(".spottiness-explanation").first().isVisible(),
        false,
      );
      for (const large of [false, true]) {
        await button("Settings").click();
        await button(large ? "Larger" : "Standard").click();
        await button("Close settings").click();
        for (const [label, width, squeezed] of [
          ["right", 1440, false],
          ["top", 1000, false],
          ["narrow", 1440, true],
        ]) {
          await page.setViewportSize({ width, height: 668 });
          await settle();
          if (squeezed)
            await page
              .getByRole("separator", {
                name: "Image and analysis divider",
                exact: true,
              })
              .press("End");
          await settle();
          const geometry = await page
            .locator(".integration-tab-pattern")
            .evaluate((panel) => {
              const files = panel.querySelector(".integration-pattern-files"),
                wrapper = panel.querySelector(".spottiness-pattern-controls");
              const p = panel.getBoundingClientRect(),
                b = files.getBoundingClientRect();
              return {
                width: b.width,
                height: wrapper.getBoundingClientRect().height,
                available:
                  panel.clientWidth -
                  parseFloat(getComputedStyle(panel).paddingLeft) -
                  parseFloat(getComputedStyle(panel).paddingRight),
                overflow: panel.scrollWidth > panel.clientWidth + 1,
                clipped: [...panel.querySelectorAll("button,input,select")]
                  .filter((el) => {
                    const r = el.getBoundingClientRect();
                    return (
                      r.width && (r.left < p.left - 1 || r.right > p.right + 1)
                    );
                  })
                  .map((el) => el.getAttribute("aria-label") || el.textContent),
              };
            });
          assert.ok(
            Math.abs(geometry.width - geometry.available) < 2,
            JSON.stringify(geometry),
          );
          assert.equal(geometry.overflow, false, JSON.stringify(geometry));
          assert.deepEqual(geometry.clipped, [], JSON.stringify(geometry));
          if (!large && label === "top")
            assert.ok(geometry.height <= 200, JSON.stringify(geometry));
          const p = await page
            .locator(".integration-pattern-files .integration-browse-arrow")
            .first()
            .boundingBox();
          await tab("Image").click();
          const i = await page
            .locator(
              ".integration-image-files-aligned .integration-browse-arrow",
            )
            .first()
            .boundingBox();
          assert.ok(Math.abs(p.width - i.width) < 1);
          assert.ok(Math.abs(p.height - i.height) < 1);
          await tab("Pattern").click();
          await page.screenshot({
            path: path.join(
              artifacts,
              `${name}-${large ? "larger" : "standard"}-${label}.png`,
            ),
          });
          reports.push({ engine: name, large, label, ...geometry });
          if (squeezed) {
            await page
              .getByRole("separator", {
                name: "Image and analysis divider",
                exact: true,
              })
              .press("Home");
            await settle();
          }
        }
      }
      assert.deepEqual(errors, []);
    } finally {
      await browser.close();
      native.close();
    }
  }
  console.log(JSON.stringify(reports, null, 2));
  await writeFile(
    path.join(artifacts, "report.json"),
    JSON.stringify(reports, null, 2),
  );
} finally {
  await server.close();
  await rm(temp, { recursive: true, force: true });
}
