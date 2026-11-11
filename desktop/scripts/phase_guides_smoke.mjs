import assert from "node:assert/strict";
import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { chromium, webkit } from "playwright";
import { nativeClient, root } from "./native_backend_client.mjs";
import { createServer } from "vite";

const artifacts = path.join(root, "desktop/artifacts/phase-guides");
await mkdir(artifacts, { recursive: true });
const receipts = [];
const phaseCount = Number(process.env.DIOPTAS_GUIDE_SMOKE_PHASES ?? 1);
const server = await createServer({
  root: path.join(root, "desktop"),
  configFile: path.join(root, "desktop/vite.config.ts"),
  server: { host: "127.0.0.1", port: 0, strictPort: false },
});
await server.listen();
const url = server.resolvedUrls.local[0];
try {
  for (const [name, type] of [
    ["chromium", chromium],
    ["webkit", webkit],
  ]) {
    const native = nativeClient();
    const browser = await type.launch({ headless: true });
    try {
      let guides = [],
        guideReplies = 0;
      const invoke = async (action, payload = {}) => {
        const result = await native.invoke(action, payload);
        assert.equal(result.ok, true, `${action}: ${result.error}`);
        if (action === "integration_phase_guides") {
          guides = result.phaseGuides;
          guideReplies++;
        }
        return result;
      };
      await invoke("integration_settings", { bins: 128, cake_bins: 36 });
      await invoke("open_calibration", {
        path: path.join(root, "dioptas/tests/data/CeO2_Pilatus1M.poni"),
      });
      await invoke("open_image", {
        path: path.join(root, "dioptas/tests/data/CeO2_Pilatus1M.tif"),
      });
      for (let index = 0; index < phaseCount; index++) {
        await invoke("integration_phase", {
          operation: "load",
          path: path.join(root, "dioptas/tests/data/jcpds/mo.jcpds"),
        });
        if (phaseCount > 1)
          await invoke("integration_phase", {
            operation: "parameter",
            index,
            parameter: "a0",
            value: 3.15 * (1 + index * 0.002),
          });
      }
      await invoke("integration_phase", {
        operation: "same_conditions",
        enabled: true,
      });
      const page = await browser.newPage({
        viewport: { width: 1440, height: 1000 },
      });
      const errors = [];
      page.on("pageerror", (e) => errors.push(e.message));
      // Playwright-only relay: the production Tauri path delivers this packet
      // as ArrayBuffer directly, without base64 or a scientific HTTP service.
      await page.exposeFunction("__nativePacket", async (a, p, known) => {
        const bytes = await native.invokePacket(a, p, known);
        const header = JSON.parse(bytes.subarray(4, 4 + bytes.readUInt32LE(0)));
        assert.equal(header.result.ok, true, `${a}: ${header.result.error}`);
        if (a === "integration_phase_guides") {
          assert.equal(
            p.binary,
            true,
            "The native UI requests packed phase coordinates",
          );
          guides = header.result.phaseGuides;
          guideReplies++;
        }
        return bytes.toString("base64");
      });
      await page.addInitScript((moduleUrl) => {
        let transfer;
        window.pywebview = {
          api: {
            invoke: async (a, p) => {
              transfer ??= import(moduleUrl).then(
                ({ RasterTransfer }) =>
                  new RasterTransfer(
                    async (a, p, known) =>
                      Uint8Array.from(
                        atob(await window.__nativePacket(a, p, known)),
                        (c) => c.charCodeAt(0),
                      ).buffer,
                  ),
              );
              return (await transfer).call(a, p);
            },
          },
        };
        window.__phaseStrokes = [];
        const paths = new WeakMap();
        for (const method of ["moveTo", "lineTo"]) {
          const original = Path2D.prototype[method];
          Path2D.prototype[method] = function (...args) {
            let points = paths.get(this);
            if (!points) paths.set(this, (points = []));
            points.push(args);
            return original.apply(this, args);
          };
        }
        for (const method of ["beginPath", "moveTo", "lineTo", "stroke"]) {
          const original = CanvasRenderingContext2D.prototype[method];
          CanvasRenderingContext2D.prototype[method] = function (...args) {
            if (
              ["detector-canvas", "phase-lines-layer"].includes(
                this.canvas.dataset.testid,
              )
            ) {
              if (method === "beginPath") this.__testPoints = [];
              if (method === "moveTo" || method === "lineTo")
                this.__testPoints?.push(args);
              const points =
                method === "stroke" && args[0] instanceof Path2D
                  ? paths.get(args[0])
                  : this.__testPoints;
              if (method === "stroke" && points?.length > 5)
                window.__phaseStrokes.push({
                  color: this.strokeStyle,
                  points,
                });
            }
            return original.apply(this, args);
          };
        }
      }, new URL("src/rasterTransfer.ts", url).href);
      await page.goto(url);
      await page.waitForTimeout(500);
      const failure = page.locator(".operation-error-dialog[open]");
      if (await failure.count())
        throw Error(await failure.getByLabel("Error report").inputValue());
      await page
        .getByRole("button", { name: "Integration", exact: true })
        .click();
      await page
        .getByRole("button", { name: "Show image phases", exact: true })
        .click();
      await page.waitForFunction(
        () =>
          Number(
            document.querySelector('[data-testid="detector-canvas"]')?.dataset
              .ringCount,
          ) > 0,
      );
      await page.getByRole("tab", { name: "Phase", exact: true }).click();
      const readStrokes = () => page.evaluate(() => window.__phaseStrokes);
      const before = guides;
      assert.equal(new Set(before.map((g) => g.phaseIndex)).size, phaseCount);
      const color = before[0].color;
      await page.waitForFunction(
        (color) => window.__phaseStrokes.some((s) => s.color === color),
        color,
      );
      const previousStroke = (await readStrokes())
        .filter((s) => s.color === color)
        .at(-1);
      await page.evaluate(() => {
        window.__phaseStrokes = [];
      });
      const count = guideReplies;
      const pressure = page.getByLabel("Phase 1 pressure (GPa)", {
        exact: true,
      });
      await pressure.fill("12");
      await pressure.press("Enter");
      for (let i = 0; i < 200 && guideReplies <= count; i++)
        await page.waitForTimeout(20);
      assert.ok(
        guideReplies > count,
        "Pressure edit refreshes detector guides",
      );
      assert.notDeepEqual(guides, before, "Pressure moves detector lines");
      await page.waitForFunction(
        ({ color, previousPoints }) => {
          const last = window.__phaseStrokes
            .filter((s) => s.color === color)
            .at(-1);
          return (
            last &&
            JSON.stringify(last.points) !== JSON.stringify(previousPoints)
          );
        },
        { color, previousPoints: previousStroke.points },
      );
      const nextStroke = (await readStrokes())
        .filter((s) => s.color === color)
        .at(-1);
      assert.notDeepEqual(
        nextStroke.points,
        previousStroke.points,
        "Updated contours reach the detector canvas",
      );
      assert.equal(
        await page.getByTestId("cake-canvas").isVisible(),
        false,
        "Check stays in detector-image mode",
      );
      const opened = page.waitForEvent("popup");
      await page
        .getByRole("button", { name: "Undock detector image", exact: true })
        .first()
        .click();
      const detached = await opened;
      detached.on("pageerror", (e) => errors.push(e.message));
      await detached.waitForFunction(
        () =>
          Number(
            document.querySelector('[data-testid="detector-canvas"]')?.dataset
              .ringCount,
          ) > 0,
      );
      assert.equal(
        await detached
          .getByTestId("detector-canvas")
          .getAttribute("data-ring-count"),
        String(guides.length),
      );
      await detached.screenshot({
        path: path.join(artifacts, `${name}-detached.png`),
      });
      await detached
        .getByRole("button", { name: "Dock detector image", exact: true })
        .first()
        .click();
      assert.deepEqual(errors, []);
      await page.screenshot({ path: path.join(artifacts, `${name}.png`) });
      receipts.push({
        browser: name,
        phases: phaseCount,
        guideReplies,
        paths: guides.length,
        errors,
      });
    } finally {
      await browser.close();
      await native.close();
    }
  }
  await writeFile(
    path.join(artifacts, "report.json"),
    JSON.stringify(receipts, null, 2),
  );
  console.log(JSON.stringify(receipts, null, 2));
} finally {
  await server.close();
}
