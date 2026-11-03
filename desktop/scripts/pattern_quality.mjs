import assert from "node:assert/strict";
import { createServer } from "vite";
import { webkit } from "playwright";
import { mkdir, writeFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
const desktop = fileURLToPath(new URL("../", import.meta.url));
await mkdir(`${desktop}artifacts`, { recursive: true });
const server = await createServer({
  root: desktop,
  cacheDir: `${desktop}node_modules/.vite-pattern-quality`,
  server: { host: "127.0.0.1", port: 0, hmr: false },
});
await server.listen();
const browser = await webkit.launch({ headless: true });
try {
  const page = await browser.newPage({
    viewport: { width: 1100, height: 700 },
  });
  await page.goto(
    `${server.resolvedUrls.local[0]}scripts/rendering_fixture.html`,
  );
  await page.waitForFunction(() => window.fixture);
  const results = await page.evaluate(async () => {
    const { WebGLPattern } = await import("/src/WebGLPattern.ts");
    const plot = { left: 20, top: 10, width: 480, height: 220 },
      size = { width: 520, height: 240, dpr: 1 };
    const fixtures = [];
    const x = Array.from({ length: 2000 }, (_, i) => (i / 1999) * 10);
    const y = x.map(
      (v) =>
        2 +
        Math.sin(v * 3) * 0.3 +
        8 * Math.exp(-(((v - 3) / 0.03) ** 2)) +
        5 * Math.exp(-(((v - 6) / 0.01) ** 2)),
    );
    fixtures.push({
      name: "narrow-peaks",
      x,
      y,
      scale: "linear",
      view: { xMin: 0, xMax: 10, yMin: 0, yMax: 12 },
    });
    const gaps = y.map((v, i) => (i > 800 && i < 1100 ? null : v));
    fixtures.push({
      name: "gaps",
      x,
      y: gaps,
      scale: "linear",
      view: { xMin: 0, xMax: 10, yMin: 0, yMax: 12 },
    });
    fixtures.push({
      name: "descending",
      x: [...x].reverse(),
      y: [...gaps].reverse(),
      scale: "linear",
      view: { xMin: 2, xMax: 8, yMin: 0, yMax: 12 },
    });
    fixtures.push({
      name: "unordered",
      x: [0, 4, 2, 8, 6, 10],
      y: [1, 8, 2, 9, 1, 5],
      scale: "linear",
      view: { xMin: 1, xMax: 9, yMin: 0, yMax: 12 },
    });
    fixtures.push({
      name: "log-with-nonpositive",
      x,
      y: y.map((v, i) => (i > 800 && i < 1100 ? (i % 2 ? -1 : 0) : v)),
      scale: "log",
      view: { xMin: 0, xMax: 10, yMin: -0.2, yMax: 1.2 },
    });
    fixtures.push({
      name: "sqrt",
      x,
      y: y.map((v) => v - 2.5),
      scale: "sqrt",
      view: { xMin: 0, xMax: 10, yMin: 0, yMax: 3 },
    });
    fixtures.push({
      name: "large-offset-deep-zoom",
      x: x.map((v) => 1e9 + v * 1e-5),
      y: y.map((v) => 1e8 + v),
      scale: "linear",
      view: { xMin: 1e9 + 2e-5, xMax: 1e9 + 7e-5, yMin: 1e8, yMax: 1e8 + 12 },
    });
    const reports = [];
    for (const dpr of [1, 2])
      for (const f of fixtures) {
        size.dpr = dpr;
        const canvas = document.createElement("canvas"),
          gpu = new WebGLPattern(canvas);
        const frame = {
          curves: [{ x: f.x, y: f.y, color: "#ffffff", width: 1.4 }],
          scale: f.scale,
          view: f.view,
          bounds: plot,
          size: { ...size },
        };
        gpu.draw(frame);
        const gl = canvas.getContext("webgl2"),
          pixels = new Uint8Array(canvas.width * canvas.height * 4);
        gl.readPixels(
          0,
          0,
          canvas.width,
          canvas.height,
          gl.RGBA,
          gl.UNSIGNED_BYTE,
          pixels,
        );
        const gpuMask = new Uint8Array(canvas.width * canvas.height);
        for (let y = 0; y < canvas.height; y++)
          for (let x = 0; x < canvas.width; x++)
            gpuMask[y * canvas.width + x] =
              pixels[((canvas.height - 1 - y) * canvas.width + x) * 4 + 3] >= 64
                ? 1
                : 0;
        const cpu = document.createElement("canvas");
        cpu.width = canvas.width;
        cpu.height = canvas.height;
        const ctx = cpu.getContext("2d");
        ctx.scale(dpr, dpr);
        ctx.save();
        ctx.beginPath();
        ctx.rect(plot.left, plot.top, plot.width, plot.height);
        ctx.clip();
        ctx.strokeStyle = "#fff";
        ctx.lineWidth = 1.4;
        ctx.beginPath();
        let previous = false;
        for (let i = 0; i < f.x.length; i++) {
          const x = f.x[i],
            source = f.y[i];
          if (
            !Number.isFinite(x) ||
            source === null ||
            !Number.isFinite(source) ||
            (f.scale === "log" && source <= 0)
          ) {
            previous = false;
            continue;
          }
          const y =
            f.scale === "log"
              ? Math.log10(Math.max(1e-6, source))
              : f.scale === "sqrt"
                ? Math.sqrt(Math.max(0, source))
                : source;
          const px =
            plot.left +
            ((x - f.view.xMin) / (f.view.xMax - f.view.xMin)) * plot.width;
          const py =
            plot.top +
            plot.height -
            ((y - f.view.yMin) / (f.view.yMax - f.view.yMin)) * plot.height;
          if (previous) ctx.lineTo(px, py);
          else ctx.moveTo(px, py);
          previous = true;
        }
        ctx.stroke();
        ctx.restore();
        const reference = ctx.getImageData(0, 0, cpu.width, cpu.height).data,
          cpuMask = Uint8Array.from({ length: gpuMask.length }, (_, i) =>
            reference[i * 4 + 3] >= 64 ? 1 : 0,
          );
        const distance = (from, to) => {
          let misses = 0,
            total = 0;
          const radius = 2 * dpr;
          for (let i = 0; i < from.length; i++)
            if (from[i]) {
              total++;
              const x = i % cpu.width,
                y = Math.floor(i / cpu.width);
              let match = false;
              for (let dy = -radius; dy <= radius && !match; dy++)
                for (let dx = -radius; dx <= radius; dx++)
                  if (
                    x + dx >= 0 &&
                    x + dx < cpu.width &&
                    y + dy >= 0 &&
                    y + dy < cpu.height &&
                    to[(y + dy) * cpu.width + x + dx]
                  ) {
                    match = true;
                    break;
                  }
              if (!match) misses++;
            }
          return { misses, total };
        };
        const forward = distance(gpuMask, cpuMask),
          backward = distance(cpuMask, gpuMask);
        if (
          forward.misses > Math.max(2, forward.total * 0.001) ||
          backward.misses > Math.max(2, backward.total * 0.001)
        )
          throw Error(
            `${f.name}/${dpr}: unmatched curve pixels ${JSON.stringify({ forward, backward })}`,
          );
        const uploads = gpu.stats.uploads;
        gpu.draw({
          ...frame,
          view: {
            ...frame.view,
            xMin: frame.view.xMin + (frame.view.xMax - frame.view.xMin) * 0.01,
          },
        });
        if (gpu.stats.uploads !== uploads)
          throw Error("Panning reuploaded vertices");
        reports.push({
          fixture: f.name,
          dpr,
          forward,
          backward,
          navigationUploads: 0,
        });
        if (dpr === 1 && f.name === "narrow-peaks") {
          const out = document.createElement("canvas");
          out.width = canvas.width;
          out.height = canvas.height;
          const o = out.getContext("2d"),
            image = o.createImageData(canvas.width, canvas.height);
          for (let y = 0; y < canvas.height; y++)
            image.data.set(
              pixels.subarray(
                (canvas.height - 1 - y) * canvas.width * 4,
                (canvas.height - y) * canvas.width * 4,
              ),
              y * canvas.width * 4,
            );
          o.putImageData(image, 0, 0);
          window.__qualityImages = {
            gpu: out.toDataURL(),
            canvas: cpu.toDataURL(),
          };
        }
        gpu.dispose();
      }
    return reports;
  });
  await writeFile(
    `${desktop}artifacts/pattern-quality.json`,
    JSON.stringify(results, null, 2),
  );
  const images = await page.evaluate(() => window.__qualityImages);
  for (const [name, url] of Object.entries(images))
    await writeFile(
      `${desktop}artifacts/pattern-quality-${name}.png`,
      Buffer.from(url.split(",")[1], "base64"),
    );
  console.log(
    `PASS ${results.length} curve geometry cases (2 CSS-pixel tolerance; no vertex uploads during navigation)`,
  );
  // Exercise the integrated component, including loss/restoration and fallback.
  await page.evaluate(() => {
    window.__patternProps = {
      pattern: { x: [0, 1, 2, 3], y: [1, 3, 2, 4], unit: "2th_deg" },
      log: false,
    };
    window.paint(window.fixture.PatternView, window.__patternProps);
  });
  await page.waitForFunction(
    () =>
      document.querySelector('[data-testid="pattern-canvas"]')?.dataset
        .curveRenderer === "webgl2",
  );
  await page.evaluate(() => {
    window.__loss = document
      .querySelector('[data-testid="pattern-gpu"]')
      .getContext("webgl2")
      .getExtension("WEBGL_lose_context");
    window.__loss.loseContext();
  });
  await page.waitForFunction(
    () =>
      document.querySelector('[data-testid="pattern-canvas"]')?.dataset
        .curveRenderer === "canvas2d",
  );
  await page.evaluate(() => window.__loss.restoreContext());
  await page.waitForFunction(
    () =>
      document.querySelector('[data-testid="pattern-canvas"]')?.dataset
        .curveRenderer === "webgl2",
  );
  console.log("PASS integrated pattern context loss/recovery");
  for (const [props, expected] of [
    [{ antialias: false }, "canvas2d"],
    [{ antialias: true }, "webgl2"],
    [{ curveRenderer: "canvas2d" }, "canvas2d"],
    [{ curveRenderer: "webgl2" }, "webgl2"],
  ]) {
    await page.evaluate(
      (props) =>
        window.paint(window.fixture.PatternView, {
          ...window.__patternProps,
          ...props,
        }),
      props,
    );
    await page.waitForFunction(
      (expected) =>
        document.querySelector('[data-testid="pattern-canvas"]')?.dataset
          .curveRenderer === expected,
      expected,
    );
  }
  console.log("PASS pixel-line mode and renderer switching");
  // Simulate absent GPU support in a fresh view; the original curve must paint.
  await page.evaluate(() => {
    window.fixture.flushSync(() => window.fixture.root.render(null));
    const original = HTMLCanvasElement.prototype.getContext;
    HTMLCanvasElement.prototype.getContext = function (type, ...args) {
      return type === "webgl2" ? null : original.call(this, type, ...args);
    };
    window.paint(window.fixture.PatternView, window.__patternProps);
    HTMLCanvasElement.prototype.getContext = original;
  });
  await page.waitForFunction(
    () =>
      document.querySelector('[data-testid="pattern-canvas"]')?.dataset
        .curveRenderer === "canvas2d",
  );
  assert.ok(
    await page.getByTestId("pattern-canvas").evaluate((el) => {
      const d = el.dataset,
        scale = el.width / el.clientWidth;
      const pixels = el
        .getContext("2d")
        .getImageData(
          Math.ceil(Number(d.plotLeft) * scale),
          Math.ceil(Number(d.plotTop) * scale),
          Math.max(1, Math.floor(Number(d.plotWidth) * scale) - 1),
          Math.max(1, Math.floor(Number(d.plotHeight) * scale) - 1),
        ).data;
      return pixels.some((value, index) => index % 4 === 3 && value > 0);
    }),
  );
  console.log("PASS unavailable GPU fallback paints the pattern");
  await page.evaluate(async () => {
    const { WebGLPattern } = await import("/src/WebGLPattern.ts");
    const element = document.createElement("canvas"),
      renderer = new WebGLPattern(element),
      gl = element.getContext("webgl2");
    const create = gl.createBuffer.bind(gl),
      remove = gl.deleteBuffer.bind(gl),
      live = new Set();
    gl.createBuffer = () => {
      const b = create();
      if (b) live.add(b);
      return b;
    };
    gl.deleteBuffer = (b) => {
      live.delete(b);
      remove(b);
    };
    for (let i = 0; i < 5; i++) {
      let failed = false;
      try {
        renderer.draw({
          curves: [
            { x: [0, 1], y: [i, i + 1], color: "#fff", width: 1.4 },
            { x: [0, 1e300], y: [1, 2], color: "#fff", width: 1.4 },
          ],
          scale: "linear",
          view: { xMin: 0, xMax: 1, yMin: 0, yMax: 6 },
          bounds: { left: 0, top: 0, width: 100, height: 100 },
          size: { width: 100, height: 100, dpr: 1 },
        });
      } catch {
        failed = true;
      }
      if (!failed || live.size !== 1)
        throw Error(`Partial-frame buffer retention: ${live.size}`);
    }
    renderer.dispose();
    if (live.size) throw Error("GPU buffers survived disposal");
  });
  console.log("PASS GPU buffers stay bounded across partial-frame failures");
} finally {
  await browser.close();
  await server.close();
}
