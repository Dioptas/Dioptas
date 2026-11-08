import assert from "node:assert/strict";
import { mkdir, writeFile, unlink } from "node:fs/promises";
import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { createServer } from "vite";
import { chromium, webkit } from "playwright";
import {
  verifyModifiedPlotNavigation,
  verifySliceContentScaling,
} from "./plot_navigation.mjs";

const desktop = fileURLToPath(new URL("../", import.meta.url));
await mkdir(new URL("../artifacts/", import.meta.url), { recursive: true });
const baselineRef = process.argv
  .find((a) => a.startsWith("--baseline="))
  ?.slice(11);
const baselineFile = new URL("../src/__render_baseline.tsx", import.meta.url);
if (baselineRef)
  await writeFile(
    baselineFile,
    execFileSync(
      "git",
      ["show", `${baselineRef}:desktop/src/PatternView.tsx`],
      { cwd: desktop },
    ),
  );
const server = await createServer({
  root: desktop,
  server: { host: "127.0.0.1", port: 0, strictPort: false },
});
await server.listen();
const browser = await (
  process.argv.includes("--webkit") ? webkit : chromium
).launch({ headless: true });
const page = await browser.newPage({
  viewport: { width: 1000, height: 700 },
  deviceScaleFactor: 1,
});
const errors = [];
page.on("pageerror", (error) => errors.push(error.message));
const report = {};
const settle = () =>
  page.evaluate(
    () =>
      new Promise((resolve) =>
        requestAnimationFrame(() => requestAnimationFrame(resolve)),
      ),
  );
try {
  await page.goto(
    `${server.resolvedUrls.local[0]}scripts/rendering_fixture.html`,
  );
  await page.waitForFunction(() => window.fixture);
  report.pixels = await page.evaluate(() => {
    const { WebGLRaster, rasterCanvas, colorsFor } = window.fixture;
    const canvas = document.createElement("canvas");
    const renderer = new WebGLRaster(canvas);
    const gl = canvas.getContext("webgl2");
    const width = 17,
      height = 11;
    const variants = [
      {
        name: "signed-invalid",
        data: Float32Array.from({ length: width * height }, (_, i) =>
          i < 3 ? [NaN, Infinity, -Infinity][i] : (i % 49) - 12.5,
        ),
        lower: -10,
        upper: 30,
      },
      {
        name: "high-intensity",
        data: Float32Array.from({ length: width * height }, (_, i) =>
          Math.pow(10, i % 13),
        ),
        lower: 0,
        upper: 1e12,
      },
      {
        name: "tiny-span",
        data: Float32Array.from(
          { length: width * height },
          (_, i) => i * 1e-10,
        ),
        lower: 1e-10,
        upper: 2e-8,
      },
      {
        name: "high-offset",
        data: Float32Array.from(
          { length: width * height },
          (_, i) => 1e6 + i / 8,
        ),
        lower: 1e6 + 0.1,
        upper: 1e6 + 0.9,
      },
      {
        name: "u8",
        data: Uint8Array.from({ length: width * height }, (_, i) => i),
        lower: 10,
        upper: 170,
      },
    ];
    const cases = [];
    let uploads = 0;
    const upload = gl.texImage2D.bind(gl);
    gl.texImage2D = (...args) => {
      uploads++;
      return upload(...args);
    };
    for (const { name, data, lower, upper } of variants) {
      const mask = Uint8Array.from(data, (_, i) => (i % 7 === 0 ? 255 : 0));
      const raster = {
        width,
        height,
        fullWidth: width,
        fullHeight: height,
        step: 1,
        dtype: data instanceof Uint8Array ? "u8" : "f32le",
        data: data.buffer,
        limits: [lower, upper],
      };
      for (const dpr of [1, 2, 1.25])
        for (const log of [false, true])
          for (const palette of ["grey", "thermal", "viridis"]) {
            const frame = {
              data,
              mask,
              width,
              height,
              colors: colorsFor(palette),
              lower,
              upper,
              log,
              maskOpacity: 0.72,
              viewport: { width: 221, height: 143, dpr },
              image: { x: 0, y: 0, width: 221, height: 143 },
              clip: { left: 0, top: 0, width: 221, height: 143 },
            };
            renderer.draw(frame);
            const gpu = new Uint8Array(canvas.width * canvas.height * 4);
            gl.readPixels(
              0,
              0,
              canvas.width,
              canvas.height,
              gl.RGBA,
              gl.UNSIGNED_BYTE,
              gpu,
            );
            const reference = document.createElement("canvas");
            reference.width = canvas.width;
            reference.height = canvas.height;
            const ctx = reference.getContext("2d");
            ctx.scale(dpr, dpr);
            ctx.translate(0, 143);
            ctx.scale(1, -1);
            ctx.imageSmoothingEnabled = false;
            ctx.drawImage(
              rasterCanvas(
                raster,
                data,
                undefined,
                mask,
                lower,
                upper,
                log,
                palette,
                0.72,
              ),
              0,
              0,
              221,
              143,
            );
            const cpu = ctx.getImageData(
              0,
              0,
              reference.width,
              reference.height,
            ).data;
            let maxError = 0,
              compared = 0;
            // Compare source pixel interiors. Fractional viewport edges and exact
            // nearest-neighbour ties can rasterize differently between the APIs.
            for (let sy = 0; sy < height; sy++)
              for (let sx = 0; sx < width; sx++) {
                const x = Math.floor((((sx + 0.5) * 221) / width) * dpr);
                const y = Math.floor(
                  (((height - sy - 0.5) * 143) / height) * dpr,
                );
                for (let c = 0; c < 4; c++) {
                  const a =
                    gpu[((canvas.height - 1 - y) * canvas.width + x) * 4 + c];
                  const b = cpu[(y * canvas.width + x) * 4 + c];
                  maxError = Math.max(maxError, Math.abs(a - b));
                  compared++;
                }
              }
            if (maxError > 1)
              throw Error(
                `${name}/${palette}/${log}/${dpr}: pixel error ${maxError}`,
              );
            cases.push({ name, dpr, log, palette, maxError, compared });
            const before = uploads;
            for (let i = 0; i < 10; i++)
              renderer.draw({
                ...frame,
                lower: -12 + i,
                upper: 40 + i,
                image: { ...frame.image, x: -i * 2 },
              });
            if (uploads !== before)
              throw Error("Navigation/intensity changes reuploaded textures");
          }
    }
    renderer.dispose();
    return { cases, uploads, uniformChangesReuseTextures: true };
  });

  await page.evaluate(() => {
    const data = Float32Array.from({ length: 64 * 32 }, (_, i) => i % 128);
    window.raster = {
      width: 64,
      height: 32,
      fullWidth: 64,
      fullHeight: 32,
      step: 1,
      dtype: "f32le",
      data: data.buffer,
      limits: [0, 127],
    };
    window.rasterProps = {
      raster: window.raster,
      log: false,
      palette: "grey",
      exportRef: { current: null },
    };
    window.paint(window.fixture.RasterView, window.rasterProps);
  });
  const detector = page.getByTestId("detector-canvas");
  await page.waitForFunction(
    () =>
      document.querySelector('[data-testid="detector-canvas"]')?.dataset
        .renderer === "webgl2",
  );
  await settle();
  await page.screenshot({ path: `${desktop}artifacts/webgl-detector.png` });
  const box = await detector.boundingBox();
  await page.mouse.move(box.x + box.width * 0.5, box.y + box.height * 0.5);
  await page.mouse.wheel(0, -250);
  await settle();
  report.navigation = await detector.evaluate((el) => ({
    squarePixels:
      Math.abs(
        +el.dataset.plotWidth /
          (+el.dataset.viewXMax - +el.dataset.viewXMin) /
          (+el.dataset.plotHeight /
            (+el.dataset.viewYMax - +el.dataset.viewYMin)) -
          1,
      ) < 1e-7,
    zoomed: +el.dataset.viewXMax - +el.dataset.viewXMin < 64,
  }));
  assert.ok(report.navigation.squarePixels && report.navigation.zoomed);
  report.modifiedNavigation = [];
  // Modified navigation must bypass picking, mask painting, ROI editing and
  // the image's ordinary double-click action (e.g. opening file information).
  for (const tool of ["pick", "mask", "roi"]) {
    await page.evaluate((tool) => {
      window.navigationActions = [];
      const record = (name) => () => window.navigationActions.push(name);
      window.paint(window.fixture.RasterView, {
        ...window.rasterProps,
        tool: tool === "roi" ? "pan" : tool,
        onPick: record("pick"),
        onInspect: record("inspect"),
        onStroke: record("stroke"),
        onImageDoubleClick: record("double-click"),
        ...(tool === "roi"
          ? { roi: [0, 32, 0, 64], onRoiChange: record("roi") }
          : {}),
      });
    }, tool);
    await settle();
    report.modifiedNavigation.push(
      `${tool}: ${await verifyModifiedPlotNavigation(page, detector)}`,
    );
    assert.deepEqual(await page.evaluate(() => window.navigationActions), []);
  }
  await page.evaluate(() =>
    window.paint(window.fixture.RasterView, window.rasterProps),
  );
  await settle();
  report.export = await page.evaluate(() => {
    const png = window.rasterProps.exportRef.current.png();
    if (!png.startsWith("iVBOR")) throw Error("Invalid image export");
    return { png: true, length: png.length };
  });
  await page.evaluate(() => {
    window.gpuContext = document
      .querySelector('[data-testid="detector-gpu"]')
      .getContext("webgl2");
    window.loss = window.gpuContext.getExtension("WEBGL_lose_context");
    window.loss.loseContext();
  });
  await page.waitForFunction(
    () =>
      document.querySelector('[data-testid="detector-canvas"]').dataset
        .renderer === "canvas2d",
  );
  await settle();
  assert.ok(
    await detector.evaluate(
      (el) => el.getContext("2d").getImageData(400, 250, 1, 1).data[3] > 0,
    ),
  );
  await page.evaluate(() => window.loss.restoreContext());
  await page.waitForFunction(
    () =>
      document.querySelector('[data-testid="detector-canvas"]').dataset
        .renderer === "webgl2",
  );
  report.contextRecovery = true;

  for (const unavailable of [true, false]) {
    await page.evaluate((unavailable) => {
      window.fixture.flushSync(() => window.fixture.root.render(null));
      const getContext = HTMLCanvasElement.prototype.getContext;
      const getParameter = WebGL2RenderingContext.prototype.getParameter;
      HTMLCanvasElement.prototype.getContext = function (type, ...args) {
        if (unavailable && type === "webgl2") return null;
        return getContext.call(this, type, ...args);
      };
      WebGL2RenderingContext.prototype.getParameter = function (parameter) {
        return parameter === this.MAX_TEXTURE_SIZE
          ? 32
          : getParameter.call(this, parameter);
      };
      window.paint(window.fixture.RasterView, window.rasterProps);
      HTMLCanvasElement.prototype.getContext = getContext;
      WebGL2RenderingContext.prototype.getParameter = getParameter;
    }, unavailable);
    await page.waitForFunction(
      () =>
        document.querySelector('[data-testid="detector-canvas"]')?.dataset
          .renderer === "canvas2d",
    );
    await settle();
    assert.ok(
      await detector.evaluate(
        (el) => el.getContext("2d").getImageData(400, 250, 1, 1).data[3] > 0,
      ),
    );
  }
  report.fallback = { unavailable: true, textureLimit: true };

  const benchmark = async (baseline = false) => {
    await page.evaluate(async (baseline) => {
      const Component = baseline
        ? (await import("/src/__render_baseline.tsx")).PatternView
        : window.fixture.PatternView;
      window.plotProps = {
        pattern: {
          x: Array.from({ length: 100000 }, (_, i) => i / 1000),
          y: Array.from(
            { length: 100000 },
            (_, i) => Math.sin(i / 30) * 10 + 30,
          ),
          unit: "2th_deg",
        },
        log: false,
      };
      window.paint(Component, window.plotProps);
    }, baseline);
    await settle();
    await settle();
    const plot = page.getByTestId("pattern-canvas");
    const b = await plot.boundingBox();
    await page.evaluate(() => {
      window.counts = { curveSegments: 0, canvasResizes: 0 };
      const original = CanvasRenderingContext2D.prototype.lineTo;
      window.originalLineTo = original;
      CanvasRenderingContext2D.prototype.lineTo = function (...args) {
        window.counts.curveSegments++;
        return original.apply(this, args);
      };
      const width = Object.getOwnPropertyDescriptor(
        HTMLCanvasElement.prototype,
        "width",
      );
      window.widthDescriptor = width;
      Object.defineProperty(HTMLCanvasElement.prototype, "width", {
        ...width,
        set(v) {
          window.counts.canvasResizes++;
          width.set.call(this, v);
        },
      });
    });
    const times = [];
    for (let i = 0; i < 30; i++) {
      times.push(
        await page.evaluate(async (i) => {
          const plot = document.querySelector('[data-testid="pattern-canvas"]');
          const b = plot.getBoundingClientRect();
          const start = performance.now();
          plot.dispatchEvent(
            new PointerEvent("pointermove", {
              bubbles: true,
              clientX: b.x + 100 + i * 15,
              clientY: b.y + 100,
            }),
          );
          await new Promise((resolve) =>
            requestAnimationFrame(() => requestAnimationFrame(resolve)),
          );
          return performance.now() - start;
        }, i),
      );
    }
    const hover = await page.evaluate(() => ({ ...window.counts }));
    await page.mouse.move(b.x + 200, b.y + 100);
    await page.mouse.down();
    await page.mouse.move(b.x + 250, b.y + 300);
    await page.mouse.up();
    await settle();
    const zoomed = await page.evaluate(() => ({ ...window.counts }));
    await page.evaluate(() => {
      CanvasRenderingContext2D.prototype.lineTo = window.originalLineTo;
      Object.defineProperty(
        HTMLCanvasElement.prototype,
        "width",
        window.widthDescriptor,
      );
    });
    times.sort((a, b) => a - b);
    return {
      hover,
      zoomAdditionalSegments: zoomed.curveSegments - hover.curveSegments,
      medianEventToSettledMs: times[15],
      p95EventToSettledMs: times[28],
    };
  };
  report.pattern = await benchmark();
  assert.ok(
    report.pattern.hover.curveSegments < 3000,
    JSON.stringify(report.pattern),
  );
  assert.equal(report.pattern.hover.canvasResizes, 0);
  assert.ok(
    report.pattern.zoomAdditionalSegments < 20000,
    JSON.stringify(report.pattern),
  );
  await page.screenshot({ path: `${desktop}artifacts/optimized-pattern.png` });
  for (const zoomMode of ["rectangle", "horizontal"]) {
    await page.evaluate((zoomMode) => {
      window.navigationActions = [];
      const record = (name) => () => window.navigationActions.push(name);
      window.paint(window.fixture.PatternView, {
        ...window.plotProps,
        zoomMode,
        editRegions: true,
        regions: [{ name: "test", min: 0, max: 100, color: "#ff9500" }],
        onRegionChange: record("region"),
        onRegionDragStart: record("region-start"),
        onRegionSelect: record("region-select"),
        onInspect: record("inspect"),
        onPick: record("pick"),
        onAutoRange: (enabled) => {
          window.navigationAutoRange = enabled;
        },
      });
    }, zoomMode);
    await settle();
    report.modifiedNavigation.push(
      `${zoomMode}: ${await verifyModifiedPlotNavigation(page, page.getByTestId("pattern-canvas"))}`,
    );
    assert.deepEqual(await page.evaluate(() => window.navigationActions), []);
    assert.equal(await page.evaluate(() => window.navigationAutoRange), true);
  }
  if (baselineRef) report.baselinePattern = await benchmark(true);
  report.sliceNavigation = await verifySliceContentScaling(page);
  assert.deepEqual(errors, []);
  await writeFile(
    `${desktop}artifacts/rendering-${process.argv.includes("--webkit") ? "webkit" : "chromium"}.json`,
    JSON.stringify(report, null, 2),
  );
  console.log(JSON.stringify(report, null, 2));
} finally {
  await browser.close();
  await server.close();
  if (baselineRef) await unlink(baselineFile);
}
