import assert from "node:assert/strict";
import { createServer } from "vite";
import { chromium } from "playwright";

// Exercise the real PatternView and canvas drawing without a processing server.
const fixture = {
  x: [0, 1, 2, 3, 4, 5],
  y: [0, 1000, 20, 80, 40, 0],
  unit: "2th_deg",
  phaseLines: [
    { x: 1, intensity: 100, phaseIndex: 0, color: "#e050a0" },
    { x: 2, intensity: 10, phaseIndex: 0, color: "#e050a0" },
    { x: 3, intensity: 20, phaseIndex: 0, color: "#e050a0" },
    { x: 4, intensity: 1, phaseIndex: 1, color: "#50b8ff" },
  ].map((line) => ({ ...line, name: "phase", hkl: [1, 1, 1] })),
};
const server = await createServer({
  server: { host: "127.0.0.1", port: 0, open: false },
  plugins: [
    {
      name: "phase-scaling-fixture",
      resolveId(id) {
        if (id === "virtual:phase-scaling") return id;
      },
      load(id) {
        if (id === "virtual:phase-scaling")
          return `
        import React from "react";
        import { createRoot } from "react-dom/client";
        import { PatternView } from "/src/PatternView.tsx";
        const pattern = ${JSON.stringify(fixture)};
        const root = createRoot(document.getElementById("root"));
        window.renderPattern = (scale = "linear", zoomMode = "rectangle") =>
          root.render(React.createElement(PatternView, { pattern,
            referenceLines: pattern.phaseLines, log: scale === "log",
            sqrt: scale === "sqrt", zoomMode }));
        window.renderPattern();`;
      },
      configureServer(server) {
        server.middlewares.use("/__phase_scaling", async (_req, res) => {
          res.setHeader("Content-Type", "text/html");
          res.end(
            await server.transformIndexHtml(
              "/__phase_scaling",
              `
          <html><head><style>body { background: #222; margin: 0; }
          #root, .pattern-container { width: 900px; height: 450px; }</style></head>
          <body><div id="root"></div><script type="module"
          src="/@id/virtual:phase-scaling"></script></body></html>`,
            ),
          );
        });
      },
    },
  ],
});
let browser;
try {
  await server.listen();
  browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  const errors = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.addInitScript(() => {
    const proto = CanvasRenderingContext2D.prototype;
    for (const method of ["scale", "beginPath", "moveTo", "lineTo", "stroke"]) {
      const original = proto[method];
      proto[method] = function (...args) {
        if (this.canvas.dataset.testid === "pattern-canvas") {
          if (method === "scale") window.phaseStrokes = [];
          if (method === "beginPath") this.phasePath = [];
          if (method === "moveTo" || method === "lineTo")
            this.phasePath.push(args);
          if (
            method === "stroke" &&
            ["#e050a0", "#50b8ff"].includes(this.strokeStyle)
          )
            window.phaseStrokes.push({
              color: this.strokeStyle,
              path: this.phasePath,
            });
        }
        return original.apply(this, args);
      };
    }
  });
  await page.goto(`${server.resolvedUrls.local[0]}__phase_scaling`);
  const canvas = page.getByTestId("pattern-canvas");
  await canvas.waitFor();
  const settle = () =>
    page.evaluate(
      () =>
        new Promise((resolve) =>
          requestAnimationFrame(() => requestAnimationFrame(resolve)),
        ),
    );
  const verify = async (scale = "linear") => {
    await settle();
    const data = await canvas.evaluate((el) => ({
      ...el.dataset,
      strokes: window.phaseStrokes,
    }));
    const transform = (v) =>
      scale === "log" ? Math.log10(v) : scale === "sqrt" ? Math.sqrt(v) : v;
    const maximum = Math.min(
      +data.viewYMax,
      Math.max(
        ...fixture.y
          .filter(
            (y, i) =>
              fixture.x[i] > +data.viewXMin &&
              fixture.x[i] < +data.viewXMax &&
              (scale !== "log" || y > 0),
          )
          .map(transform),
      ),
    );
    for (const color of ["#e050a0", "#50b8ff"]) {
      const strokes = data.strokes.filter((s) => s.color === color);
      assert.ok(strokes.length > 0);
      const top = Math.min(...strokes.map((s) => s.path[1][1]));
      const expected =
        +data.plotTop +
        +data.plotHeight *
          (1 -
            Math.max(0, maximum - +data.viewYMin) /
              (+data.viewYMax - +data.viewYMin));
      assert.ok(
        Math.abs(top - expected) < 1e-6,
        `${scale}: strongest phase line meets measured maximum`,
      );
    }
    return data;
  };
  const initial = await verify();
  const drag = async (button, x0, y0, x1, y1) => {
    await page.mouse.move(x0, y0);
    await page.mouse.down({ button });
    await page.mouse.move(x1, y1, { steps: 8 });
    await page.mouse.up({ button });
  };
  const px = (x) => +initial.plotLeft + (x / 5) * +initial.plotWidth;
  await drag(
    "left",
    px(1.5),
    +initial.plotTop + 20,
    px(4.5),
    +initial.plotTop + +initial.plotHeight - 20,
  );
  await verify();
  await drag("right", px(2.5), 220, px(2.5) + 20, 240);
  await verify();
  await page.mouse.wheel(0, -50);
  await verify();
  await canvas.dblclick({ button: "right", position: { x: 450, y: 220 } });
  await verify();
  for (const scale of ["log", "sqrt"]) {
    await page.evaluate((scale) => window.renderPattern(scale), scale);
    await verify(scale);
  }
  await page.evaluate(() => window.renderPattern("linear", "horizontal"));
  await settle();
  await drag("left", px(1.5), 180, px(4.5), 220);
  await verify();
  assert.deepEqual(errors, []);
  console.log(
    "Phase line canvas checks passed: fit, rectangle and X-range zoom, pan, wheel, reset, log and sqrt.",
  );
} finally {
  await browser?.close();
  await server.close();
}
