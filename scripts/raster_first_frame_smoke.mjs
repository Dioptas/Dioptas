import assert from "node:assert/strict";
import { mkdir, writeFile } from "node:fs/promises";
import { createServer } from "vite";
import { chromium, webkit } from "playwright";

const root = new URL("../", import.meta.url).pathname;
const server = await createServer({
  root,
  server: { host: "127.0.0.1", port: 0, strictPort: false },
});
await server.listen();
const reports = [];
try {
  for (const [engine, browserType] of Object.entries({ chromium, webkit })) {
    const browser = await browserType.launch({ headless: true });
    try {
      for (const software of [false, true]) {
        const page = await browser.newPage({
          viewport: { width: 1200, height: 900 },
          deviceScaleFactor: 2,
        });
        const errors = [];
        page.on("pageerror", (error) => errors.push(error.message));
        await page.addInitScript((software) => {
          const original = HTMLCanvasElement.prototype.getContext;
          HTMLCanvasElement.prototype.getContext = function (kind, ...args) {
            return software && kind === "webgl2"
              ? null
              : original.call(this, kind, ...args);
          };
          window.rasterDraws = [];
          for (const [prototype, method] of [
            [CanvasRenderingContext2D.prototype, "drawImage"],
            [WebGL2RenderingContext.prototype, "drawArrays"],
          ]) {
            const draw = prototype[method];
            prototype[method] = function (...args) {
              if (
                this.canvas.dataset.testid?.endsWith("-canvas") ||
                this.canvas.dataset.testid?.endsWith("-gpu")
              ) {
                const rect = this.canvas.getBoundingClientRect();
                window.rasterDraws.push({
                  method,
                  bitmap: [this.canvas.width, this.canvas.height],
                  expected: [
                    Math.round(rect.width * devicePixelRatio),
                    Math.round(rect.height * devicePixelRatio),
                  ],
                });
              }
              return draw.apply(this, args);
            };
          }
        }, software);
        await page.goto(
          `${server.resolvedUrls.local[0]}scripts/rendering_fixture.html`,
        );
        await page.waitForFunction(() => window.fixture);
        const result = await page.evaluate(async (software) => {
          const { React, RasterView, flushSync, root } = window.fixture;
          const host = document.getElementById("fixture");
          const data = Float32Array.from(
            { length: 32 * 64 },
            (_, i) => i % 255,
          );
          const raster = {
            width: 32,
            height: 64,
            fullWidth: 32,
            fullHeight: 64,
            step: 1,
            dtype: "f32le",
            data: data.buffer,
            limits: [0, 255],
            radialRange: [0, 30],
            azimuthRange: [-180, 180],
            unit: "2th_deg",
          };
          const frames = [];
          const tick = () =>
            new Promise((resolve) => requestAnimationFrame(resolve));
          const checkFrame = (name, cake) => {
            const canvas = host.querySelector(
              `[data-testid="${cake ? "cake" : "detector"}-canvas"]`,
            );
            const rect = canvas.getBoundingClientRect();
            if (!rect.width || !rect.height) return;
            const bitmap = [canvas.width, canvas.height];
            const expected = [
              Math.round(rect.width * devicePixelRatio),
              Math.round(rect.height * devicePixelRatio),
            ];
            if (JSON.stringify(bitmap) !== JSON.stringify(expected))
              throw Error(`${name}: painted ${bitmap} into ${expected}`);
            if (canvas.dataset.renderer !== (software ? "canvas2d" : "webgl2"))
              throw Error(
                `${name}: first frame used ${canvas.dataset.renderer}`,
              );
            if (!cake) {
              const width = Number(canvas.dataset.plotWidth),
                height = Number(canvas.dataset.plotHeight);
              if (
                Math.abs(width - rect.width) > 0.01 ||
                Math.abs(height - rect.height) > 0.01
              )
                throw Error(
                  `${name}: first frame retained the previous projection`,
                );
            }
            frames.push({ name, bitmap, renderer: canvas.dataset.renderer });
          };
          const scenarios = [
            // Fresh canvases at the sizes/layouts used by single- and multi-image modes.
            ["detector mount", 934, 830, false, true],
            ["mask remount", 962, 868, false, true],
            ["calibration remount", 934, 830, false, true],
            ["integration retained canvas", 610, 700, false, false],
            ["map remount", 412.5, 330.5, false, true],
            ["cake remount", 580, 390, true, true],
            ["detached detector", 813.5, 611.5, false, true],
            ["single-crystal detector", 820, 730, false, true],
          ];
          for (const [name, width, height, cake, remount] of scenarios) {
            if (remount) flushSync(() => root.render(null));
            window.rasterDraws = [];
            host.style.width = `${width}px`;
            host.style.height = `${height}px`;
            flushSync(() =>
              root.render(
                React.createElement(RasterView, {
                  raster,
                  log: false,
                  palette: "grey",
                  cake,
                }),
              ),
            );
            // Inspect every browser frame starting with the first opportunity to paint.
            for (let i = 0; i < 3; i++) {
              await tick();
              checkFrame(name, cake);
            }
            if (
              !software &&
              window.rasterDraws.some((d) => d.method === "drawImage")
            )
              throw Error(
                `${name}: flashed the software image before GPU rendering`,
              );
            if (
              remount &&
              window.rasterDraws.some(
                (d) => JSON.stringify(d.bitmap) !== JSON.stringify(d.expected),
              )
            )
              throw Error(`${name}: drew an image at a provisional size`);
          }
          flushSync(() => root.render(null));
          host.style.display = "none";
          window.rasterDraws = [];
          flushSync(() =>
            root.render(
              React.createElement(RasterView, {
                raster,
                log: false,
                palette: "grey",
              }),
            ),
          );
          await tick();
          if (window.rasterDraws.length)
            throw Error("Hidden image drew a provisional frame");
          host.style.display = "flex";
          flushSync(() =>
            root.render(
              React.createElement(RasterView, {
                raster,
                log: false,
                palette: "thermal",
              }),
            ),
          );
          for (let i = 0; i < 3; i++) {
            await tick();
            checkFrame("revealed retained canvas", false);
          }
          // A parent can resize without rerendering RasterView (a divider,
          // histogram or native window). Check in the first observer delivery,
          // before paint, rather than giving React another animation frame.
          await new Promise((resolve, reject) => {
            const observer = new ResizeObserver(() => {
              observer.disconnect();
              try {
                checkFrame("external container resize", false);
                resolve();
              } catch (error) {
                reject(error);
              }
            });
            observer.observe(host.querySelector(".raster-container"));
            host.style.height = "514.5px";
          });
          return frames;
        }, software);
        assert.equal(result.length, 28);
        assert.deepEqual(errors, []);
        reports.push({
          engine,
          renderer: software ? "canvas2d" : "webgl2",
          frames: result,
        });
        console.log(
          `${engine} ${software ? "Canvas" : "WebGL"}: all first frames sized correctly`,
        );
        await page.close();
      }
    } finally {
      await browser.close();
    }
  }
  await mkdir(new URL("../artifacts/", import.meta.url), { recursive: true });
  await writeFile(
    new URL("../artifacts/raster-first-frame.json", import.meta.url),
    JSON.stringify(reports, null, 2),
  );
} finally {
  await server.close();
}
