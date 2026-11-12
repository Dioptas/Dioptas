import { createServer } from "vite";
import { chromium, webkit } from "playwright";
import { writeFile } from "node:fs/promises";
import path from "node:path";
import { root as repository } from "./native_backend_client.mjs";
const root = repository;
const server = await createServer({
  root,
  server: { host: "127.0.0.1", port: 0 },
});
await server.listen();
const receipt = [];
try {
  for (const [name, engine] of [
    ["chromium", chromium],
    ["webkit", webkit],
  ]) {
    const browser = await engine.launch({ headless: true });
    try {
      const page = await browser.newPage({
        viewport: { width: 1100, height: 750 },
      });
      await page.addInitScript(() => {
        const original = WebGL2RenderingContext.prototype.bufferData;
        window.uploads = 0;
        WebGL2RenderingContext.prototype.bufferData = function (...args) {
          window.uploads++;
          return original.apply(this, args);
        };
      });
      await page.goto(
        server.resolvedUrls.local[0] + "scripts/batch_surface_harness.html",
      );
      await page.getByTestId("batch-surface").waitFor();
      await page.evaluate(() => window.setSurfacePeakFixture());
      await page
        .getByRole("button", {
          name: "Surface ranges and proportions",
          exact: true,
        })
        .click();
      await page
        .getByRole("combobox", { name: "Surface resolution", exact: true })
        .selectOption("fine");
      await page
        .getByRole("button", { name: "Close surface settings", exact: true })
        .click();
      await page.getByTestId("batch-surface").hover();
      const samples = [];
      const uploads = await page.evaluate(() => window.uploads);
      for (let i = 0; i < 8; i++) {
        const previous = await page
          .getByTestId("batch-surface")
          .getAttribute("data-zoom");
        await page.mouse.wheel(0, -45);
        await page.waitForFunction(
          (z) =>
            document.querySelector('[data-testid="batch-surface"]').dataset
              .zoom !== z,
          previous,
        );
        samples.push(
          await page
            .getByTestId("batch-surface")
            .evaluate((c) => +c.dataset.renderMs),
        );
      }
      receipt.push({
        browser: name,
        samples,
        medianMs: [...samples].sort((a, b) => a - b)[4],
        bufferUploads: (await page.evaluate(() => window.uploads)) - uploads,
      });
    } finally {
      await browser.close();
    }
  }
  console.log(JSON.stringify(receipt));
  if (process.argv[2])
    await writeFile(process.argv[2], JSON.stringify(receipt, null, 2));
} finally {
  await server.close();
}
