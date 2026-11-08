import assert from "node:assert/strict";
import { mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { createServer } from "vite";
import { chromium, webkit } from "playwright";

const desktop = fileURLToPath(new URL("../", import.meta.url));
// Refresh a disposable copy so the test never edits a user's live preview.
const fixture = await mkdtemp(path.join(desktop, "scripts/.legend-test-"));
const relative = path.relative(desktop, fixture);
const component = path.join(fixture, "PlotLegend.tsx");
const source = (
  await readFile(path.join(desktop, "src/PlotLegend.tsx"), "utf8")
).replace('"./plotLegend.css"', '"/src/plotLegend.css"');
await writeFile(component, source);
await writeFile(
  path.join(fixture, "index.html"),
  `
<div id="root"></div><script type="module" src="./fixture.tsx"></script>`,
);
await writeFile(
  path.join(fixture, "fixture.tsx"),
  `
import React, { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { flushSync } from "react-dom";
import { PlotLegend } from "./PlotLegend";
import "/src/style.css";
const root = createRoot(document.getElementById("root"));
const defaults = {
  label: "Pattern legend", entries: [{name: "Captured pattern with a very long acquisition filename ".repeat(8), color: "orange"}],
  left: 799, top: 20, width: 720, height: 200,
  bounds: { left: 70, top: 15, width: 730, height: 400 },
};
window.paint = (props = {}) => flushSync(() => root.render(
  <StrictMode><div style={{position:"relative",width:800,height:450}}>
    <PlotLegend {...defaults} {...props} />
  </div></StrictMode>
));
window.paint();
`,
);
const server = await createServer({
  root: desktop,
  server: { host: "127.0.0.1", port: 0, strictPort: false },
});
try {
  await server.listen();
  for (const [name, engine] of Object.entries({ chromium, webkit })) {
    const browser = await engine.launch({ headless: true });
    try {
      const page = await browser.newPage();
      const errors = [];
      page.on("pageerror", (error) => errors.push(error.message));
      page.on("console", (message) => {
        if (message.type() === "error") errors.push(message.text());
      });
      await page.goto(`${server.resolvedUrls.local[0]}${relative}/index.html`);
      const legend = page.getByRole("group", { name: "Pattern legend" });
      await legend.waitFor();
      const initial = await legend.boundingBox();
      assert.ok(initial.x >= 70 && initial.x + initial.width <= 800);
      // React Refresh re-runs layout effects, even with unchanged dependencies.
      // Exercise the same refresh path shown in the reported crash stack.
      const refresh = async (token) => {
        const refreshed = page.waitForEvent("console", {
          predicate: (message) =>
            message.text().includes("hot updated:") &&
            message.text().includes("PlotLegend.tsx"),
          timeout: 10000,
        });
        await writeFile(
          component,
          source.replace(
            "aria-label={label}",
            `aria-label={label} data-refresh-token="${token}"`,
          ),
        );
        await refreshed;
        await page.waitForFunction(
          (token) =>
            document
              .querySelector("[data-refresh-token]")
              ?.getAttribute("data-refresh-token") === token,
          token,
          { timeout: 5000 },
        );
        await page.evaluate(
          () =>
            new Promise((resolve) =>
              requestAnimationFrame(() => requestAnimationFrame(resolve)),
            ),
        );
      };
      await refresh(`${name}-auto`);
      assert.deepEqual(errors, [], `${name}: live refresh must not crash`);
      await legend.waitFor();
      const afterRefresh = await legend.boundingBox();
      assert.ok(
        Math.abs(afterRefresh.x - initial.x) < 1,
        `${name}: refresh must preserve automatic placement`,
      );
      assert.ok(
        Math.abs(afterRefresh.width - initial.width) < 1,
        `${name}: position must not feed back into measured width`,
      );
      // Keyboard positioning must survive data changes and another refresh.
      await legend.focus();
      await legend.press("ArrowLeft");
      assert.equal(await legend.getAttribute("data-manual-position"), "true");
      const moved = await legend.boundingBox();
      await refresh(`${name}-manual`);
      assert.equal(await legend.getAttribute("data-manual-position"), "true");
      assert.ok(Math.abs((await legend.boundingBox()).x - moved.x) < 1);
      assert.ok(Math.abs(moved.x - (initial.x - 5)) < 1);
      await page.evaluate(() =>
        window.paint({
          entries: [
            { name: "Captured pattern", color: "orange" },
            { name: "Second capture", color: "green" },
          ],
        }),
      );
      assert.ok(Math.abs((await legend.boundingBox()).x - moved.x) < 1);
      await legend.press("Home");
      assert.equal(await legend.getAttribute("data-manual-position"), "false");
      await page.evaluate(() =>
        window.paint({
          left: 310,
          width: 200,
          bounds: { left: 70, top: 15, width: 250, height: 100 },
        }),
      );
      const resized = await legend.boundingBox();
      assert.ok(resized.x >= 70 && resized.x + resized.width <= 320);
      const beforeDrag = await legend.boundingBox();
      await page.mouse.move(beforeDrag.x + 10, beforeDrag.y + 10);
      await page.mouse.down();
      await page.mouse.move(beforeDrag.x + 30, beforeDrag.y + 25, { steps: 5 });
      await page.mouse.up();
      assert.equal(await legend.getAttribute("data-manual-position"), "true");
      await legend.press("Escape");
      assert.equal(await legend.getAttribute("data-manual-position"), "false");
      // Empty/nonempty transitions must also install the resize observer.
      await page.evaluate(() => window.paint({ entries: [] }));
      assert.equal(await legend.count(), 0);
      await page.evaluate(() => window.paint());
      await legend.waitFor();
      assert.deepEqual(errors, []);
      console.log(
        `${name}: legend live refresh, positioning, data changes and bounds passed`,
      );
    } finally {
      await browser.close();
    }
  }
} finally {
  await server.close();
  await rm(fixture, { recursive: true, force: true });
}
