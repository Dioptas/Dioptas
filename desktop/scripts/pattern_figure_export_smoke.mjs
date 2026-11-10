import assert from "node:assert/strict";
import { mkdir, writeFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { createServer } from "vite";
import { Resvg } from "@resvg/resvg-js";
import { chromium, webkit } from "playwright";

const desktop = fileURLToPath(new URL("../", import.meta.url));
const artifacts = new URL(
  "../artifacts/pattern-figure-export/",
  import.meta.url,
);
await mkdir(artifacts, { recursive: true });
const server = await createServer({
  root: desktop,
  server: { host: "127.0.0.1", port: 0 },
});
await server.listen();
const receipts = [];
try {
  for (const [name, engine] of [
    ["chromium", chromium],
    ["webkit", webkit],
  ]) {
    const browser = await engine.launch({ headless: true });
    try {
      const page = await browser.newPage({
        viewport: { width: 1000, height: 668 },
        deviceScaleFactor: 2,
      });
      const errors = [];
      page.on("pageerror", (error) => errors.push(error.message));
      await page.goto(
        `${server.resolvedUrls.local[0]}scripts/rendering_fixture.html`,
      );
      await page.waitForFunction(() => window.fixture);
      for (const unit of ["2th_deg", "q_A^-1", "d_A"]) {
        for (const scale of ["linear", "log", "sqrt"]) {
          await page.evaluate(
            ({ unit, scale }) => {
              const { React, PatternView } = window.fixture;
              const angle = Array.from(
                { length: 2001 },
                (_, i) => 3 + i * 0.02,
              );
              const q = (a) =>
                (4 * Math.PI * Math.sin((a * Math.PI) / 360)) / 0.4;
              const x = angle.map((a) =>
                unit === "d_A"
                  ? (2 * Math.PI) / q(a)
                  : unit === "q_A^-1"
                    ? q(a)
                    : a,
              );
              const y = angle.map((a, i) =>
                i % 157 === 0
                  ? null
                  : 10 +
                    1000 * Math.exp(-(((a - 19) / 0.3) ** 2)) +
                    100 * Math.exp(-(((a - 27) / 0.5) ** 2)),
              );
              window.props = {
                pattern: { x, y, unit, name: "Measured" },
                log: scale === "log",
                sqrt: scale === "sqrt",
                patternColor: "#ffffff",
                antialias: true,
                compact: true,
                curves: [
                  {
                    x,
                    y: y.map((v) => (v === null ? null : v * 0.8)),
                    color: "#ff9500",
                    selected: true,
                  },
                ],
                referenceLines: [19, 27, 42].map((a, i) => ({
                  x:
                    unit === "d_A"
                      ? (2 * Math.PI) / q(a)
                      : unit === "q_A^-1"
                        ? q(a)
                        : a,
                  name: "CeO₂ & <reference>",
                  color: "#55cc88",
                  intensity: 100 / (i + 1),
                  phaseIndex: 0,
                })),
                overlayLegend: [
                  { name: "Measured", color: "#ffffff" },
                  { name: "Overlay & <comparison>", color: "#ff9500" },
                ],
                exportRef: { current: null },
                curveRenderer: "webgl2",
              };
              window.beforeArrays = JSON.stringify(window.props);
              window.paint(PatternView, window.props);
            },
            { unit, scale },
          );
          await page.waitForTimeout(60);
          // Exercise a real zoom and dragged legend before capture.
          const plot = page.getByTestId("pattern-canvas");
          const box = await plot.boundingBox();
          const zoom = await plot.evaluate((element) => {
            const d = element.dataset;
            const positions = window.props.referenceLines
              .slice(0, 2)
              .map((line) => line.x);
            const low = Math.min(...positions),
              high = Math.max(...positions),
              pad = (high - low) * 0.4;
            const pixel = (x) =>
              Number(d.plotLeft) +
              ((x - Number(d.viewXMin)) /
                (Number(d.viewXMax) - Number(d.viewXMin))) *
                Number(d.plotWidth);
            return [pixel(low - pad), pixel(high + pad)];
          });
          await page.mouse.move(box.x + zoom[0], box.y + box.height * 0.12);
          await page.mouse.down();
          await page.mouse.move(box.x + zoom[1], box.y + box.height * 0.87);
          await page.mouse.up();
          const legend = page.getByRole("group", {
            name: "Pattern legend",
            exact: true,
          });
          await legend.focus();
          await legend.press("ArrowLeft");
          await page.mouse.move(950, 630);
          const result = await page.evaluate(async () => {
            const props = window.props;
            const view = document.querySelector(
              '[data-testid="pattern-canvas"]',
            ).dataset;
            const before = JSON.stringify({
              pattern: props.pattern,
              curves: props.curves,
              referenceLines: props.referenceLines,
            });
            const capture = props.exportRef.current.capture();
            // Capture the live layers synchronously while the export's fresh GPU
            // drawing buffer is still available. Compare outside DOM legends.
            const element = document.querySelector(".pattern-container");
            const origin = element.getBoundingClientRect();
            const expected = document.createElement("canvas");
            expected.width = Math.round(origin.width * 2);
            expected.height = Math.round(origin.height * 2);
            const expectedContext = expected.getContext("2d");
            expectedContext.fillStyle =
              getComputedStyle(element)
                .getPropertyValue("--ui-workspace")
                .trim() || "#101518";
            expectedContext.fillRect(0, 0, expected.width, expected.height);
            for (const layer of element.querySelectorAll("canvas")) {
              if (getComputedStyle(layer).visibility !== "hidden")
                expectedContext.drawImage(layer, 0, 0);
            }
            const expectedPixels = expectedContext.getImageData(
              0,
              0,
              expected.width,
              expected.height,
            ).data;
            const legendBoxes = [
              ...element.querySelectorAll(".plot-legend"),
            ].map((legend) => {
              const rect = legend.getBoundingClientRect();
              return {
                x0: (rect.left - origin.left - 3) * 2,
                x1: (rect.right - origin.left + 3) * 2,
                y0: (rect.top - origin.top - 3) * 2,
                y1: (rect.bottom - origin.top + 3) * 2,
              };
            });
            if (
              before !==
              JSON.stringify({
                pattern: props.pattern,
                curves: props.curves,
                referenceLines: props.referenceLines,
              })
            )
              throw Error("Export mutated scientific arrays");
            const xml = new DOMParser().parseFromString(
              capture.svg_data,
              "image/svg+xml",
            );
            if (xml.querySelector("parsererror, image, foreignObject"))
              throw Error("Invalid or raster SVG");
            if (xml.querySelectorAll('path[stroke="#55cc88"]').length < 2)
              throw Error("Missing visible phase lines");
            if (
              !xml.querySelector("path") ||
              !capture.svg_data.includes("CeO₂ &amp; &lt;reference&gt;")
            )
              throw Error("Missing vector references/legend");
            const load = async (src) => {
              const img = new Image();
              img.src = src;
              await img.decode();
              const canvas = document.createElement("canvas");
              canvas.width = Math.round(
                Number(xml.documentElement.getAttribute("width")) * 2,
              );
              canvas.height = Math.round(
                Number(xml.documentElement.getAttribute("height")) * 2,
              );
              canvas
                .getContext("2d")
                .drawImage(img, 0, 0, canvas.width, canvas.height);
              return {
                canvas,
                pixels: canvas
                  .getContext("2d")
                  .getImageData(0, 0, canvas.width, canvas.height).data,
                width: img.naturalWidth,
                height: img.naturalHeight,
              };
            };
            const png = await load(`data:image/png;base64,${capture.png_data}`);
            const url = URL.createObjectURL(
              new Blob([capture.svg_data], { type: "image/svg+xml" }),
            );
            const svg = await load(url);
            URL.revokeObjectURL(url);
            let pixelDiff = 0;
            let diff = 0,
              opaque = 0,
              white = 0,
              orange = 0,
              green = 0;
            for (let i = 0; i < png.pixels.length; i += 4) {
              const [r, g, b, a] = png.pixels.slice(i, i + 4);
              const px = (i / 4) % expected.width,
                py = Math.floor(i / 4 / expected.width);
              if (
                !legendBoxes.some(
                  (box) =>
                    px >= box.x0 &&
                    px <= box.x1 &&
                    py >= box.y0 &&
                    py <= box.y1,
                )
              ) {
                pixelDiff = Math.max(
                  pixelDiff,
                  ...[0, 1, 2, 3].map((channel) =>
                    Math.abs(
                      png.pixels[i + channel] - expectedPixels[i + channel],
                    ),
                  ),
                );
              }
              diff +=
                Math.abs(r - svg.pixels[i]) +
                Math.abs(g - svg.pixels[i + 1]) +
                Math.abs(b - svg.pixels[i + 2]);
              if (a === 255) opaque++;
              if (r > 200 && g > 200 && b > 200) white++;
              if (r > 180 && g > 65 && g < 200 && b < 100) orange++;
              if (g > r * 1.2 && g > b * 1.1 && g > 100) green++;
            }
            return {
              ...capture,
              pixelDiff,
              width: png.width,
              height: png.height,
              cssWidth: svg.width,
              cssHeight: svg.height,
              diff: diff / ((png.pixels.length / 4) * 3),
              opaque,
              white,
              orange,
              green,
              view: { xMin: view.viewXMin, xMax: view.viewXMax },
              renderer: view.curveRenderer,
            };
          });
          assert.equal(
            result.pixelDiff,
            0,
            "PNG differs from the displayed renderer pixels",
          );
          assert.equal(result.width, result.cssWidth * 2);
          assert.equal(result.height, result.cssHeight * 2);
          assert.equal(result.opaque, result.width * result.height);
          assert(
            result.white > 100 && result.orange > 100 && result.green > 100,
            JSON.stringify(result),
          );
          assert(
            result.diff < 3,
            `PNG vs independently loaded SVG mean channel diff ${result.diff}`,
          );
          const prefix = `${name}-${unit.replaceAll(/[^\w]/g, "")}-${scale}`;
          const independent = new Resvg(result.svg_data, {
            fitTo: { mode: "width", value: result.width },
          }).render();
          assert.equal(independent.width, result.width);
          assert.equal(independent.height, result.height);
          let independentGreen = 0,
            independentOrange = 0;
          const pixels = independent.pixels;
          for (let i = 0; i < pixels.length; i += 4) {
            if (
              pixels[i + 1] > pixels[i] * 1.2 &&
              pixels[i + 1] > pixels[i + 2] * 1.1 &&
              pixels[i + 1] > 100
            )
              independentGreen++;
            if (
              pixels[i] > 180 &&
              pixels[i + 1] > 65 &&
              pixels[i + 1] < 200 &&
              pixels[i + 2] < 100
            )
              independentOrange++;
          }
          assert(
            independentGreen > 100 && independentOrange > 100,
            "Independent SVG lost curve/reference colors",
          );
          await writeFile(
            new URL(`${prefix}-resvg.png`, artifacts),
            independent.asPng(),
          );
          await writeFile(new URL(`${prefix}.svg`, artifacts), result.svg_data);
          await writeFile(
            new URL(`${prefix}.png`, artifacts),
            Buffer.from(result.png_data, "base64"),
          );
          const { png_data, svg_data, ...receipt } = result;
          receipts.push({
            name,
            unit,
            scale,
            svgBytes: svg_data.length,
            ...receipt,
          });
        }
      }
      // Hidden measured curve, fallback pixels, and larger text still export correctly.
      await page.evaluate(() => {
        document.documentElement.dataset.textSize = "large";
        window.props = {
          ...window.props,
          showPattern: false,
          antialias: false,
          curveRenderer: "canvas2d",
        };
        window.paint(window.fixture.PatternView, window.props);
      });
      await page.waitForTimeout(60);
      const fallback = await page.evaluate(() =>
        window.props.exportRef.current.capture(),
      );
      assert(!fallback.svg_data.includes('stroke="#ffffff"'));
      assert(fallback.svg_data.length < 64 * 1024 * 1024);
      await page.screenshot({
        path: fileURLToPath(new URL(`${name}-compact.png`, artifacts)),
      });
      assert.deepEqual(errors, []);
    } finally {
      await browser.close();
    }
  }
  await writeFile(
    new URL("rendering.json", artifacts),
    JSON.stringify(receipts, null, 2),
  );
  console.log(
    JSON.stringify(
      receipts.map(({ name, unit, scale, diff, svgBytes, renderer }) => ({
        name,
        unit,
        scale,
        diff,
        svgBytes,
        renderer,
      })),
      null,
      2,
    ),
  );
} finally {
  await server.close();
}
