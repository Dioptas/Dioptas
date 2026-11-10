// Real Rust session + headless browsers; no scientific stub or Python runtime.
import assert from "node:assert/strict";
import path from "node:path";
import os from "node:os";
import { mkdtemp, mkdir, writeFile, readFile, rm } from "node:fs/promises";
import { createServer } from "vite";
import { chromium, webkit } from "playwright";
import { nativeClient, root } from "./native_backend_client.mjs";
const temp = await mkdtemp(path.join(os.tmpdir(), "dioptas-cake-axis-"));
const artifacts = path.join(root, "desktop/artifacts/cake-q-axis");
await mkdir(artifacts, { recursive: true });
const ponis = [];
for (const wavelength of [4e-11, 8e-11]) {
  const poni = path.join(temp, `geometry-${wavelength}.poni`);
  await writeFile(
    poni,
    `PixelSize1: 0.0001\nPixelSize2: 0.0001\nDistance: 0.005\nPoni1: 0.003\nPoni2: 0.004\nRot1: 0\nRot2: 0\nRot3: 0\nWavelength: ${wavelength}\n`,
  );
  ponis.push(poni);
}
const server = await createServer({
  root: path.join(root, "desktop"),
  server: { host: "127.0.0.1", port: 0 },
});
await server.listen();
const reports = [];
const near = (a, b, tolerance = 1e-7) =>
  assert.ok(Math.abs(a - b) < tolerance, `${a} != ${b}`);
try {
  for (const [name, engine] of [
    ["chromium", chromium],
    ["webkit", webkit],
  ]) {
    const native = nativeClient(),
      browser = await engine.launch({ headless: true }),
      errors = [],
      calls = [];
    const project = path.join(temp, `${name}.dio`),
      csv = path.join(temp, `${name}.csv`);
    let latestCake;
    const call = async (a, p = {}) => {
      if (["save_project", "open_project"].includes(a) && !p.path)
        p = { ...p, path: project };
      if (a === "integration_save_image" && !p.path)
        p = { ...p, path: path.join(temp, `${name}-cake.png`) };
      const r = await native.invoke(a, p);
      assert.ok(r.ok, `${a}: ${r.error}`);
      calls.push({ a, p });
      if (r.cake) latestCake = r.cake;
      return r;
    };
    try {
      await call("open_calibration", { path: ponis[0] });
      await call("integration_settings", {
        bins: 241,
        cake_bins: 48,
        trim_zeros: false,
      });
      await call("open_image", {
        path: path.join(
          root,
          "desktop/backend/tests/fixtures/combined-counts.h5",
        ),
        dataset: "/counts",
      });
      const page = await browser.newPage({
        viewport: { width: 1440, height: 1000 },
      });
      page.setDefaultTimeout(20000);
      page.on("pageerror", (e) => errors.push(e.message));
      await page.exposeFunction("__nativeInvoke", async (a, p) =>
        native.browserResult(await call(a, p)),
      );
      await page.addInitScript(() => {
        window.pywebview = {
          api: { invoke: (a, p) => window.__nativeInvoke(a, p) },
        };
        const clear = CanvasRenderingContext2D.prototype.clearRect,
          fill = CanvasRenderingContext2D.prototype.fillText;
        CanvasRenderingContext2D.prototype.clearRect = function (...args) {
          if (this.canvas.dataset.testid === "cake-canvas")
            window.__cakeLabels = [];
          return clear.apply(this, args);
        };
        CanvasRenderingContext2D.prototype.fillText = function (
          text,
          x,
          y,
          ...rest
        ) {
          if (this.canvas.dataset.testid === "cake-canvas")
            (window.__cakeLabels ??= []).push({ text, x, y });
          return fill.call(this, text, x, y, ...rest);
        };
      });
      await page.goto(server.resolvedUrls.local[0]);
      const button = (label) =>
        page.getByRole("button", { name: label, exact: true });
      await button("Integration").click();
      await button("Cake").click();
      const canvas = page.getByTestId("cake-canvas");
      await canvas.waitFor();
      const settle = async () => {
        await page.waitForFunction(
          () =>
            !document.querySelector('[aria-label="Pattern unit Q"]')?.disabled,
        );
        await page.evaluate(
          () =>
            new Promise((r) =>
              requestAnimationFrame(() => requestAnimationFrame(r)),
            ),
        );
      };
      const data = () =>
        canvas.evaluate((el) => ({
          ...el.dataset,
          box: {
            x: el.getBoundingClientRect().x,
            y: el.getBoundingClientRect().y,
          },
        }));
      const view = (d) =>
        ["viewXMin", "viewXMax", "viewYMin", "viewYMax"].map((k) =>
          Number(d[k]),
        );
      const sourceAt = (grid, pixel) =>
        grid.radialRange[0] +
        ((pixel - 0.5) / (grid.fullWidth - 1)) *
          (grid.radialRange[1] - grid.radialRange[0]);
      const validateTicks = async (wavelength) => {
        const d = await data(),
          ticks = JSON.parse(d.radialAxisTicks);
        assert.ok(ticks.length >= 2);
        const display = (source) =>
          d.radialDisplayUnit === latestCake.unit
            ? source
            : d.radialDisplayUnit === "q_A^-1"
              ? (4 * Math.PI * Math.sin((source * Math.PI) / 360)) /
                (wavelength * 1e10)
              : (360 / Math.PI) *
                Math.asin((source * wavelength * 1e10) / (4 * Math.PI));
        for (const tick of ticks)
          near(display(sourceAt(latestCake, tick.pixel)), tick.value);
        const labels = await page.evaluate(() => window.__cakeLabels);
        const plotBottom = Number(d.plotTop) + Number(d.plotHeight);
        const rendered = labels.filter(
          (l) =>
            l.y > plotBottom &&
            l.x >= Number(d.plotLeft) &&
            Number.isFinite(Number(l.text.replace("−", "-"))),
        );
        assert.ok(
          rendered.length >= 2,
          "actual canvas draws numeric radial labels",
        );
        for (const label of rendered) {
          const pixel =
            Number(d.viewXMin) +
            ((label.x - Number(d.plotLeft)) / Number(d.plotWidth)) *
              (Number(d.viewXMax) - Number(d.viewXMin));
          near(
            Number(label.text.replace("−", "-")),
            display(sourceAt(latestCake, pixel)),
            1e-5,
          );
        }
        return d;
      };
      await settle();
      assert.equal((await data()).radialDisplayUnit, "2th_deg");
      const original = latestCake.bufferId;
      let d = await data();
      await page.mouse.move(
        d.box.x + Number(d.plotLeft) + Number(d.plotWidth) * 0.2,
        d.box.y + Number(d.plotTop) + Number(d.plotHeight) * 0.2,
      );
      await page.mouse.down();
      await page.mouse.move(
        d.box.x + Number(d.plotLeft) + Number(d.plotWidth) * 0.8,
        d.box.y + Number(d.plotTop) + Number(d.plotHeight) * 0.8,
        { steps: 8 },
      );
      await page.mouse.up();
      const zoom = view(await data());
      assert.ok(zoom[0] > 0);
      const count = (await call("integration_diagnostics"))
        .integrationDiagnostics.cakeIntegrations;
      for (const unit of ["Q", "d", "2θ", "Q"]) {
        await button(`Pattern unit ${unit}`).click();
        await settle();
        d = await validateTicks(4e-11);
        assert.equal(d.radialDisplayUnit, unit === "2θ" ? "2th_deg" : "q_A^-1");
        assert.deepEqual(view(d), zoom);
        assert.equal(latestCake.bufferId, original);
        assert.equal(
          (await call("integration_diagnostics")).integrationDiagnostics
            .cakeIntegrations,
          count,
        );
      }
      d = await data();
      const px =
        Number(d.viewXMin) + 0.43 * (Number(d.viewXMax) - Number(d.viewXMin));
      await page.mouse.click(
        d.box.x + Number(d.plotLeft) + Number(d.plotWidth) * 0.43,
        d.box.y + Number(d.plotTop) + Number(d.plotHeight) * 0.5,
      );
      await page.waitForFunction(
        () =>
          document.querySelector('[data-testid="cake-canvas"]')?.dataset
            .clickX !== undefined,
      );
      await settle();
      const clicked = calls.filter((c) => c.a === "validation_position").at(-1);
      assert.equal(clicked.p.unit, "2th_deg");
      near(clicked.p.x, sourceAt(latestCake, px), 0.05);
      assert.equal(latestCake.bufferId, original);
      assert.ok(Number.isFinite(Number((await data()).clickX)));
      await page.screenshot({
        path: path.join(artifacts, `${name}-zoom-q-click.png`),
      });
      const cakeLimits = [
        (await data()).intensityMin,
        (await data()).intensityMax,
      ];
      await button("Image").click();
      await page.getByTestId("detector-canvas").waitFor();
      await button("Detector histogram settings").click();
      await page
        .getByRole("combobox", { name: "Image scale", exact: true })
        .selectOption("log");
      await page.keyboard.press("Escape");
      assert.equal(
        await page
          .getByTestId("detector-canvas")
          .getAttribute("data-intensity-scale"),
        "log",
      );
      await button("Cake").click();
      await settle();
      assert.equal((await data()).intensityScale, "linear");
      assert.deepEqual(
        [(await data()).intensityMin, (await data()).intensityMax],
        cakeLimits,
      );
      await button("Settings").click();
      await page
        .getByRole("tab", { name: "Configurations", exact: true })
        .click();
      await page
        .getByRole("checkbox", { name: "Enable configurations" })
        .check();
      await button("Close settings").click();
      const group = page.getByRole("group", { name: "Project configurations" });
      await group
        .getByRole("button", { name: "Duplicate", exact: true })
        .click();
      await settle();
      await button("Combined cake").click();
      await settle();
      assert.equal(latestCake.unit, "q_A^-1");
      const combined = latestCake.bufferId;
      await button("Pattern unit 2θ").click();
      await settle();
      assert.equal(latestCake.bufferId, combined);
      assert.equal(latestCake.unit, "q_A^-1");
      await validateTicks(4e-11);
      await button("Pattern unit Q").click();
      await settle();
      await validateTicks(4e-11);
      await page.screenshot({
        path: path.join(artifacts, `${name}-combined-source-q.png`),
      });
      await call("open_calibration", { path: ponis[1] });
      await page.reload();
      await button("Integration").click();
      if (await button("Cake").isVisible()) await button("Cake").click();
      await canvas.waitFor();
      await settle();
      await validateTicks(8e-11);
      for (const large of [false, true]) {
        await button("Settings").click();
        await page.getByRole("tab", { name: "General", exact: true }).click();
        await button(large ? "Larger" : "Standard").click();
        await button("Close settings").click();
        await page.setViewportSize({ width: 1000, height: 668 });
        await settle();
        d = await validateTicks(8e-11);
        assert.ok(Number(d.plotWidth) > 100 && Number(d.plotHeight) > 70);
        const labels = await page.evaluate(() => window.__cakeLabels),
          size = await canvas.boundingBox();
        const title = labels.find((l) => l.text === "Q (Å⁻¹)");
        assert.ok(title);
        assert.ok(title.x > 0 && title.x < size.width && title.y < size.height);
        await page.screenshot({
          path: path.join(
            artifacts,
            `${name}-compact-${large ? "large" : "standard"}.png`,
          ),
        });
      }
      await call("integration_save_image", { path: csv, source: "cake" });
      const header = (await readFile(csv, "utf8"))
        .split("\n")[0]
        .split(",")
        .map(Number);
      near(header[1], latestCake.radialRange[0], 0.00051);
      await button("Save image").click();
      await settle();
      const png = await readFile(path.join(temp, `${name}-cake.png`));
      assert.equal(png.readUInt32BE(16), 2048);
      assert.ok(png.length > 1000);
      await button("Save project").click();
      await settle();
      await button("Open project").click();
      await settle();
      await validateTicks(8e-11);
      assert.equal(errors.length, 0, errors.join("\n"));
      reports.push({
        browser: name,
        individualBufferReused: true,
        combinedSourceUnit: "q_A^-1",
        sourceClicks: true,
        zoomPreserved: true,
        wavelengths: [0.4, 0.8],
        compactTextSizes: 2,
        errors,
      });
    } finally {
      await browser.close();
      await native.close();
    }
  }
  await writeFile(
    path.join(artifacts, "report.json"),
    JSON.stringify(reports, null, 2),
  );
  console.log(JSON.stringify(reports, null, 2));
} finally {
  await server.close();
  await rm(temp, { recursive: true, force: true });
}
