import assert from "node:assert/strict";
import fs from "node:fs/promises";
import path from "node:path";
import { createServer } from "vite";
import { chromium, webkit } from "playwright";
import { nativeClient, root } from "./native_backend_client.mjs";

const artifacts = path.join(root, "desktop/artifacts/batch-surface");
await fs.mkdir(artifacts, { recursive: true });
const server = await createServer({
  root: path.join(root, "desktop"),
  server: { host: "127.0.0.1", port: 0 },
});
await server.listen();
const url = server.resolvedUrls.local[0];
const waitReady = (page) =>
  page.waitForFunction(
    () =>
      document.querySelector('[data-testid="batch-surface"]')?.dataset
        .renderState === "ready",
  );
const clickSample = async (page) => {
  await page.getByTestId("batch-surface").evaluate((c) => {
    const p = JSON.parse(c.dataset.hitSample),
      b = c.getBoundingClientRect();
    c.setPointerCapture = c.releasePointerCapture = () => {};
    for (const type of ["pointerdown", "pointerup"])
      c.dispatchEvent(
        new PointerEvent(type, {
          bubbles: true,
          pointerId: 2,
          button: 0,
          clientX: b.x + p.x,
          clientY: b.y + p.y,
        }),
      );
  });
};
const receipt = [];
try {
  for (const [name, engine] of [
    ["chromium", chromium],
    ["webkit", webkit],
  ]) {
    const browser = await engine.launch({ headless: true });
    const errors = [];
    try {
      const context = await browser.newContext({
        viewport: { width: 900, height: 650 },
      });
      context.on("page", (p) =>
        p.on("pageerror", (e) => {
          errors.push(e.message);
          console.error(e.message);
        }),
      );
      const page = await context.newPage();
      await page.goto(url + "scripts/batch_surface_harness.html");
      await waitReady(page);
      const surface = page.getByTestId("batch-surface");
      assert.ok(Number(await surface.getAttribute("data-triangles")) > 0);
      assert.equal(await surface.getAttribute("data-radial-first"), "20");
      assert.equal(await surface.getAttribute("data-radial-last"), "4");
      const signatures = [];
      for (const [orientation, azimuth, elevation] of [
        ["Front", 0, 0],
        ["Right", 90, 0],
        ["Top", 0, 90],
        ["Isometric", 45, 30],
      ]) {
        await page
          .getByRole("button", {
            name: `${orientation} surface view`,
            exact: true,
          })
          .click();
        assert.equal(
          Number(await surface.getAttribute("data-azimuth")),
          azimuth,
        );
        assert.equal(
          Number(await surface.getAttribute("data-elevation")),
          elevation,
        );
        signatures.push(await surface.evaluate((c) => c.toDataURL()));
      }
      assert.equal(
        new Set(signatures).size,
        4,
        "orientation controls change rendered geometry",
      );
      await clickSample(page);
      await page.waitForFunction(() => !!window.surfaceSelection);
      const selection = await page.evaluate(() => window.surfaceSelection);
      assert.equal(selection.position.unit, "d_A");
      assert.ok(selection.selected >= 0 && selection.selected < 4);
      const png = await page.evaluate(() => window.captureSurface());
      assert.ok(png.startsWith("iVBOR"));
      const bytes = Buffer.from(png, "base64");
      assert.ok(bytes.length > 3000);
      await fs.writeFile(path.join(artifacts, `${name}-snapshot.png`), bytes);
      for (const scale of ["log", "sqrt", "linear"]) {
        await page.evaluate((scale) => window.setSurfaceScale(scale), scale);
        await page.waitForFunction(
          (scale) =>
            document.querySelector('[data-testid="batch-surface"]').dataset
              .intensityScale === scale,
          scale,
        );
      }
      await surface.focus();
      await surface.press("ArrowUp");
      await page.waitForFunction(() => window.surfaceSelection.selected > 0);
      const beforeZoom = Number(await surface.getAttribute("data-zoom"));
      await surface.hover();
      await page.mouse.wheel(0, -150);
      await page.waitForFunction(
        (before) =>
          Number(
            document.querySelector('[data-testid="batch-surface"]').dataset
              .zoom,
          ) > before,
        beforeZoom,
      );
      const zoomBeforeClick = Number(await surface.getAttribute("data-zoom"));
      await surface.click({ button: "right" });
      assert.equal(
        Number(await surface.getAttribute("data-zoom")),
        zoomBeforeClick / 2,
      );
      const rect = await surface.boundingBox();
      await page.mouse.move(rect.x + rect.width / 2, rect.y + rect.height / 2);
      await page.mouse.down();
      await page.mouse.move(
        rect.x + rect.width / 2 + 40,
        rect.y + rect.height / 2 + 30,
        { steps: 4 },
      );
      await page.mouse.up();
      assert.equal(await surface.getAttribute("data-azimuth"), "25");
      assert.equal(await surface.getAttribute("data-elevation"), "45");
      // Qt orbit(-dx, dy): dragging back reverses the rotation in both axes.
      await page.mouse.down();
      await page.mouse.move(rect.x + rect.width / 2, rect.y + rect.height / 2, {
        steps: 4,
      });
      await page.mouse.up();
      assert.equal(await surface.getAttribute("data-azimuth"), "45");
      assert.equal(await surface.getAttribute("data-elevation"), "30");
      await surface.focus();
      await surface.press("f");
      assert.equal(await surface.getAttribute("data-zoom"), "1");
      await page
        .getByRole("button", {
          name: "Surface ranges and proportions",
          exact: true,
        })
        .click();
      const minimum = page.getByRole("spinbutton", {
        name: "Surface radial minimum d (Å)",
        exact: true,
      });
      await minimum.fill("6");
      await minimum.press("Enter");
      assert.ok(Number(await surface.getAttribute("data-radial-last")) >= 6);
      await page
        .getByRole("button", { name: "Close surface settings", exact: true })
        .click();
      const selectedBeforeReset = await page.evaluate(
        () => window.surfaceSelection.selected,
      );
      await surface.hover();
      await page.mouse.wheel(0, -500);
      await page.waitForFunction(
        () =>
          Number(
            document.querySelector('[data-testid="batch-surface"]').dataset
              .zoom,
          ) > 1,
      );
      const box = await surface.boundingBox();
      await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
      await page.mouse.down({ button: "right" });
      await page.mouse.move(
        box.x + box.width / 2 + 32,
        box.y + box.height / 2 - 18,
        { steps: 4 },
      );
      await page.mouse.up({ button: "right" });
      assert.notEqual(await surface.getAttribute("data-pan-x"), "0");
      await surface.dblclick({ button: "right" });
      assert.equal(await surface.getAttribute("data-zoom"), "1");
      assert.equal(await surface.getAttribute("data-pan-x"), "0");
      assert.equal(await surface.getAttribute("data-pan-y"), "0");
      assert.equal(await surface.getAttribute("data-radial-last"), "4");
      assert.equal(await surface.getAttribute("data-frame-first"), "1");
      assert.equal(await surface.getAttribute("data-frame-last"), "4");
      assert.equal(
        await page.evaluate(() => window.surfaceSelection.selected),
        selectedBeforeReset,
      );
      await surface.hover();
      await page.mouse.wheel(0, -300);
      await page.waitForFunction(
        () =>
          Number(
            document.querySelector('[data-testid="batch-surface"]').dataset
              .zoom,
          ) > 1,
      );
      await surface.dblclick({ modifiers: ["Control"] });
      assert.equal(await surface.getAttribute("data-zoom"), "1");
      await page
        .getByRole("button", {
          name: "Surface ranges and proportions",
          exact: true,
        })
        .click();
      await page
        .getByRole("button", { name: "Reset surface and ranges", exact: true })
        .click();
      await minimum.press("Escape");
      assert.equal(
        await page
          .getByRole("button", { name: "Surface ranges and proportions" })
          .getAttribute("aria-expanded"),
        "false",
      );
      await page.evaluate(() => window.setSurfaceConstant(10));
      await page.waitForTimeout(100);
      const pixel = await surface.evaluate(async (c) => {
        const { rasterColor } = await import("/src/colorMaps.ts");
        const p = JSON.parse(c.dataset.hitSample),
          b = c.getBoundingClientRect();
        const actual = [
          ...c
            .getContext("2d")
            .getImageData(
              Math.round((p.x * c.width) / b.width),
              Math.round((p.y * c.height) / b.height),
              1,
              1,
            ).data,
        ].slice(0, 3);
        return { actual, expected: rasterColor(128 / 255, "viridis") };
      });
      assert.ok(
        pixel.actual.every((v, i) => Math.abs(v - pixel.expected[i]) < 3),
        JSON.stringify(pixel),
      );
      const colored = await surface.evaluate((c) => c.toDataURL());
      await page.evaluate(() => window.setSurfacePalette("grey"));
      await page.waitForFunction(
        () =>
          document.querySelector('[data-testid="batch-surface"]').dataset
            .palette === "grey",
      );
      assert.notEqual(await surface.evaluate((c) => c.toDataURL()), colored);
      // A large float buffer is sampled, never copied/transformed as a full matrix.
      await page.evaluate(() => window.setSurfaceFixture(1000, 1024));
      // The previous scene can still report ready before React commits the new
      // fixture. Wait for its dimensions before checking the new sampling.
      await page.waitForFunction(
        () =>
          document.querySelector('[data-testid="batch-surface"]')?.dataset
            .frameLast === "1000",
      );
      await waitReady(page);
      assert.ok(Number(await surface.getAttribute("data-vertices")) <= 65536);
      assert.ok(Number(await surface.getAttribute("data-frame-step")) > 1);
      await page.setViewportSize({ width: 420, height: 220 });
      await page.waitForTimeout(100);
      assert.ok((await surface.boundingBox()).height >= 150);
      await page.screenshot({
        path: path.join(artifacts, `${name}-compact.png`),
      });
      await page.evaluate(() => window.setSurfaceFixture(1, 5));
      await page.waitForFunction(
        () =>
          document.querySelector('[data-testid="batch-surface"]')?.dataset
            .frameLast === "1",
      );
      await waitReady(page);
      assert.equal(await surface.getAttribute("data-triangles"), "0");
      await page.evaluate(() => window.setSurfaceFixture(3, 3, true));
      await page.waitForFunction(
        () =>
          document.querySelector('[data-testid="batch-surface"]').dataset
            .renderState === "empty",
      );
      assert.equal(await page.evaluate(() => window.captureSurface()), null);
      await page.close();
      const unavailable = await context.newPage();
      await unavailable.addInitScript(() => {
        const original = HTMLCanvasElement.prototype.getContext;
        HTMLCanvasElement.prototype.getContext = function (type, ...args) {
          return type === "2d" ? null : original.call(this, type, ...args);
        };
      });
      await unavailable.goto(url + "scripts/batch_surface_harness.html");
      await unavailable.getByRole("alert").waitFor();
      assert.match(
        await unavailable.getByRole("alert").textContent(),
        /unavailable/,
      );
      assert.equal(
        await unavailable.evaluate(() => window.captureSurface()),
        null,
      );
      await unavailable.close();
      await context.close();

      // Actual native session, binary series, linked selection and dock/popup.
      const native = nativeClient();
      try {
        const call = async (action, payload = {}) => {
          const result = await native.invoke(action, {
            ...payload,
            requested_products: { cake: false, rings: false },
          });
          assert.ok(result.ok, `${action}: ${result.error}`);
          return result;
        };
        await call("open_calibration", {
          path: path.join(root, "desktop/tests/data/LaB6_40keV_MarCCD.poni"),
        });
        await call("batch_load", {
          paths: ["001", "002", "001", "002"].map((i) =>
            path.join(root, `desktop/tests/data/image_${i}.tif`),
          ),
        });
        await call("integration_phase", {
          operation: "load",
          path: path.join(root, "desktop/tests/data/jcpds/au_version3.jcpds"),
        });
        const original = await call("batch_snapshot");
        const binaryBefore = JSON.stringify(
          native.browserResult(original).batch.raster,
        );
        const appContext = await browser.newContext({
          viewport: { width: 1440, height: 1000 },
        });
        appContext.on("page", (p) =>
          p.on("pageerror", (e) => errors.push(e.message)),
        );
        await appContext.exposeFunction("__surfaceInvoke", async (a, p) =>
          native.browserResult(await call(a, p)),
        );
        await appContext.addInitScript(() => {
          window.pywebview = {
            api: { invoke: (a, p) => window.__surfaceInvoke(a, p) },
          };
          try {
            localStorage.setItem("dioptas-batch:docked", "true");
          } catch {}
        });
        const app = await appContext.newPage();
        await app.goto(url);
        await app
          .getByRole("button", { name: "Integration", exact: true })
          .click();
        await app
          .getByRole("button", { name: "Batch view…", exact: true })
          .click();
        await app.getByRole("tab", { name: "3D", exact: true }).click();
        await waitReady(app);
        const phasesToggle = app.getByRole("button", {
          name: "Show batch phases",
          exact: true,
        });
        assert.equal(
          await phasesToggle.isEnabled(),
          true,
          "Native phase references are available in 3D",
        );
        await phasesToggle.click();
        await app.waitForFunction(
          () =>
            Number(
              document.querySelector('[data-testid="batch-surface"]').dataset
                .phaseReferences,
            ) > 0,
        );
        await phasesToggle.click();
        await app.waitForFunction(
          () =>
            document.querySelector('[data-testid="batch-surface"]').dataset
              .phaseReferences === "0",
        );
        await app.getByRole("button", { name: "Options", exact: true }).click();
        await app
          .getByRole("tabpanel", { name: "Batch options", exact: true })
          .waitFor();
        await app.getByRole("button", { name: "Options", exact: true }).click();
        await waitReady(app);
        const header = await app
          .locator(".batch-series-toolbar")
          .evaluate((el) => {
            return {
              optionsNext: el
                .querySelector('[aria-label="Options"]')
                .nextElementSibling?.getAttribute("aria-label"),
              phases: el
                .querySelector('[aria-label="Show batch phases"]')
                .textContent.trim(),
            };
          });
        assert.equal(header.optionsNext, "Collapse batch overview");
        assert.equal(header.phases, "");
        const surfaceSettings = await app
          .getByRole("button", { name: "Normalize batch surface", exact: true })
          .evaluate((button) =>
            button.nextElementSibling?.getAttribute("aria-label"),
          );
        assert.equal(surfaceSettings, "Surface ranges and proportions");
        await app.mouse.move(2, 2);
        await app.waitForTimeout(150);
        const styles = await app.evaluate(() => {
          const read = (label) => {
            const style = getComputedStyle(
              document.querySelector(`[aria-label="${label}"]`),
            );
            return [
              style.backgroundColor,
              style.color,
              style.borderTopWidth,
              style.borderTopLeftRadius,
            ];
          };
          return {
            surfaceActive: read("Isometric surface view"),
            unitActive: read("Pattern unit 2θ"),
            surfaceIdle: read("Front surface view"),
            unitIdle: read("Pattern unit Q"),
          };
        });
        assert.deepEqual(styles.surfaceActive, styles.unitActive);
        assert.deepEqual(styles.surfaceIdle, styles.unitIdle);

        await app.getByTestId("batch-surface").focus();
        await app.getByTestId("batch-surface").press("End");
        await app.waitForFunction(
          () =>
            document.querySelector('[data-testid="batch-surface"]').dataset
              .selectedFrame === "4",
        );
        assert.equal((await call("state")).batch.selected, 3);
        await app.getByRole("button", { name: "Options", exact: true }).click();
        const start = app.getByRole("spinbutton", {
          name: "Batch start frame",
          exact: true,
        });
        await start.fill("2");
        await start.press("Enter");
        const step = app.getByRole("spinbutton", {
          name: "Batch frame step",
          exact: true,
        });
        await step.fill("2");
        await step.press("Enter");
        await app.getByRole("tab", { name: "3D", exact: true }).click();
        await waitReady(app);
        assert.equal(
          await app
            .getByTestId("batch-surface")
            .getAttribute("data-frame-first"),
          "2",
        );
        assert.equal(
          await app
            .getByTestId("batch-surface")
            .getAttribute("data-frame-step"),
          "2",
        );
        const popup = app.waitForEvent("popup");
        await app
          .getByRole("button", { name: "Detach batch", exact: true })
          .click();
        const child = await popup;
        await child.waitForLoadState();
        await waitReady(child);
        for (const [button, unit] of [
          ["Batch unit Q", "q_A^-1"],
          ["Batch unit d", "d_A"],
          ["Batch unit 2θ", "2th_deg"],
        ]) {
          await child
            .getByRole("button", { name: button, exact: true })
            .click();
          await child.waitForFunction(
            (unit) =>
              document.querySelector('[data-testid="batch-surface"]').dataset
                .unit === unit,
            unit,
          );
        }
        await child
          .getByRole("button", {
            name: "Logarithmic batch intensity",
            exact: true,
          })
          .click();
        assert.equal(
          await child
            .getByTestId("batch-surface")
            .getAttribute("data-intensity-scale"),
          "log",
        );
        await child
          .getByRole("button", {
            name: "Square root batch intensity",
            exact: true,
          })
          .click();
        assert.equal(
          await child
            .getByTestId("batch-surface")
            .getAttribute("data-intensity-scale"),
          "sqrt",
        );
        const normalizedBefore = await call("batch_snapshot");
        await child
          .getByRole("button", { name: "Top surface view", exact: true })
          .click();
        await child
          .getByRole("button", { name: "Normalize batch surface", exact: true })
          .click();
        await child.waitForFunction(
          () =>
            document.querySelector('[data-testid="batch-surface"]').dataset
              .normalized === "true",
        );
        await child.getByRole("tab", { name: "2D", exact: true }).click();
        await child.getByTestId("batch-heatmap").waitFor();
        await child.getByRole("tab", { name: "3D", exact: true }).click();
        await waitReady(child);
        await child
          .getByRole("button", { name: "Normalize batch surface", exact: true })
          .click();
        await child.waitForFunction(
          () =>
            document.querySelector('[data-testid="batch-surface"]').dataset
              .normalized === "false",
        );
        assert.equal(
          await child
            .getByTestId("batch-surface")
            .getAttribute("data-frame-step"),
          "2",
        );
        assert.equal(
          await child
            .getByTestId("batch-surface")
            .getAttribute("data-elevation"),
          "90",
        );
        assert.deepEqual(
          (await call("batch_snapshot")).batch.raster,
          normalizedBefore.batch.raster,
        );
        assert.equal(
          JSON.stringify(
            native.browserResult(await call("batch_snapshot")).batch.raster,
          ),
          binaryBefore,
          "display operations and normalization off preserve original matrix",
        );
        await child
          .getByRole("button", { name: "Isometric surface view", exact: true })
          .click();
        await child.setViewportSize({ width: 600, height: 360 });
        await child.waitForTimeout(150);
        await child.screenshot({
          path: path.join(artifacts, `${name}-native-series.png`),
        });
        const closed = child.waitForEvent("close");
        await child
          .getByRole("button", { name: "Dock batch below image", exact: true })
          .click();
        await closed;
        await waitReady(app);
        await app.setViewportSize({ width: 1000, height: 700 });
        await app.evaluate(
          () => (document.querySelector(".app").dataset.textSize = "large"),
        );
        await app.waitForTimeout(150);
        assert.ok(
          (await app.getByTestId("batch-surface").boundingBox()).height > 100,
        );
        await app.screenshot({
          path: path.join(artifacts, `${name}-dock.png`),
        });
        await appContext.close();
      } finally {
        await native.close();
      }
      assert.deepEqual(errors, []);
      receipt.push({
        browser: name,
        geometry: true,
        scales: true,
        units: true,
        rangeAndStride: true,
        docking: true,
        errors,
      });
    } finally {
      await browser.close();
    }
  }
  await fs.writeFile(
    path.join(artifacts, "receipt.json"),
    JSON.stringify(receipt, null, 2),
  );
  console.log(JSON.stringify(receipt));
} finally {
  await server.close();
}
