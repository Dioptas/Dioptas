// Compare the preceding canvas point replay against cached paths/layers using
// real native contours. Timings are headless Canvas2D, not screen scanout.
import assert from "node:assert/strict";
import path from "node:path";
import { mkdir, writeFile } from "node:fs/promises";
import { chromium, webkit } from "playwright";
import { createServer } from "vite";
import { nativeClient, root } from "./native_backend_client.mjs";
const artifacts = path.join(root, "artifacts/phase-guides/rendering");
await mkdir(artifacts, { recursive: true });
const native = nativeClient();
const call = async (a, p = {}) => {
  const r = await native.invoke(a, p);
  assert.equal(r.ok, true, r.error);
  return r;
};
const server = await createServer({
  configFile: false,
  root,
  server: { host: "127.0.0.1", port: 0 },
  plugins: [
    {
      name: "phase-test-page",
      configureServer(s) {
        s.middlewares.use("/phase-test", (_, res) => {
          res.setHeader("Content-Type", "text/html");
          res.end(
            "<!doctype html><html><body style='margin:0;background:#101518;color:white'></body></html>",
          );
        });
      },
    },
  ],
});
const receipts = [];
const applyAll = process.argv.includes("--all");
try {
  await call("integration_settings", { bins: 128, cake_bins: 36 });
  await call("integration_phase", {
    operation: "same_conditions",
    enabled: false,
  });
  await call("open_calibration", {
    path: path.join(root, "tests/data/CeO2_Pilatus1M.poni"),
  });
  await call("open_image", {
    path: path.join(root, "tests/data/CeO2_Pilatus1M.tif"),
  });
  for (let index = 0; index < 20; index++) {
    await call("integration_phase", {
      operation: "load",
      path: path.join(
        root,
        "tests/data/jcpds",
        ["mo.jcpds", "au_version3.jcpds", "pt.jcpds"][index % 3],
      ),
    });
    await call("integration_phase", {
      operation: "parameter",
      index,
      parameter: "a0",
      value: [3.15, 4.08, 3.92][index % 3] * (1 + index * 0.002),
    });
    await call("integration_phase", {
      operation: "update",
      index,
      pressure: index * 2 + 0.25,
    });
  }
  const legacy = (await call("integration_phase_guides")).phaseGuides;
  const packet = (
    await native.invokePacket("integration_phase_guides", { binary: true })
  ).toString("base64");
  await call("integration_phase", {
    operation: "same_conditions",
    enabled: applyAll,
  });
  await call("integration_phase", {
    operation: "update",
    index: 0,
    pressure: 12,
  });
  const changed = (
    await native.invokePacket("integration_phase_guides", { binary: true })
  ).toString("base64");
  const known = new Set(
    JSON.parse(
      Buffer.from(changed, "base64").subarray(
        4,
        4 + Buffer.from(changed, "base64").readUInt32LE(0),
      ),
    ).buffers.map((b) => b.id),
  );
  const edits = [];
  for (const pressure of [0, 1, 2, 3, 4, 5, 4, 3, 2, 1, 0]) {
    await call("integration_phase", {
      operation: "update",
      index: 0,
      pressure,
    });
    const bytes = await native.invokePacket(
      "integration_phase_guides",
      { binary: true },
      [...known].slice(-64),
    );
    const header = JSON.parse(bytes.subarray(4, 4 + bytes.readUInt32LE(0)));
    assert.equal(header.result.ok, true, header.result.error);
    for (const b of header.buffers) known.add(b.id);
    edits.push(bytes.toString("base64"));
  }
  await server.listen();
  const url = server.resolvedUrls.local[0];
  for (const [name, type] of [
    ["chromium", chromium],
    ["webkit", webkit],
  ]) {
    const browser = await type.launch({ headless: true });
    try {
      const page = await browser.newPage({
        viewport: { width: 1650, height: 600 },
      });
      await page.goto(url + "phase-test");
      const report = await page.evaluate(
        async ({ url, legacy, packet, changed, edits, applyAll }) => {
          const { PhaseGuidePainter } = await import(
            new URL("src/PhaseGuidePainter.ts", url).href
          );
          const { RasterTransfer } = await import(
            new URL("src/rasterTransfer.ts", url).href
          );
          const binary = (text) =>
            Uint8Array.from(atob(text), (c) => c.charCodeAt(0)).buffer;
          let frame = binary(packet);
          const transfer = new RasterTransfer(async () => frame);
          const packed = (await transfer.call("guides")).phaseGuides;
          let pathCommands = 0,
            layerStrokes = 0;
          const line = Path2D.prototype.lineTo,
            stroke = CanvasRenderingContext2D.prototype.stroke;
          Path2D.prototype.lineTo = function (...args) {
            pathCommands++;
            return line.apply(this, args);
          };
          CanvasRenderingContext2D.prototype.stroke = function (...args) {
            if (this.canvas.dataset.testid === "phase-lines-layer")
              layerStrokes++;
            return stroke.apply(this, args);
          };
          const canvases = [
            document.createElement("canvas"),
            document.createElement("canvas"),
          ];
          for (const c of canvases) {
            c.style.width = "800px";
            c.style.height = "520px";
            document.body.append(c);
          }
          const contexts = canvases.map((c) => c.getContext("2d"));
          const painter = new PhaseGuidePainter();
          const base = {
            width: 800,
            height: 520,
            dpr: 1,
            left: 10,
            top: 10,
            plotWidth: 780,
            plotHeight: 500,
            sx: 0.43,
            sy: 0.43,
            ox: 190,
            oy: 10,
            fullHeight: 1043,
          };
          const clear = (ctx, p) => {
            const c = ctx.canvas,
              w = Math.round(p.width * p.dpr),
              h = Math.round(p.height * p.dpr);
            if (c.width !== w) c.width = w;
            if (c.height !== h) c.height = h;
            ctx.setTransform(p.dpr, 0, 0, p.dpr, 0, 0);
            ctx.fillStyle = "#101518";
            ctx.fillRect(0, 0, p.width, p.height);
          };
          const oldDraw = (rings, p) => {
            const ctx = contexts[0];
            clear(ctx, p);
            ctx.save();
            ctx.beginPath();
            ctx.rect(p.left, p.top, p.plotWidth, p.plotHeight);
            ctx.clip();
            ctx.setLineDash([]);
            for (const r of rings) {
              ctx.beginPath();
              r.points.forEach(([x, y], i) => {
                const px = p.ox + x * p.sx,
                  py = p.oy + (p.fullHeight - y) * p.sy;
                if (i) ctx.lineTo(px, py);
                else ctx.moveTo(px, py);
              });
              ctx.strokeStyle = r.color;
              ctx.lineWidth = r.lineWidth;
              ctx.globalAlpha = r.opacity;
              ctx.stroke();
            }
            ctx.restore();
          };
          const newDraw = (rings, p, exporting = false) => {
            clear(contexts[1], p);
            if (exporting) {
              contexts[1].save();
              contexts[1].beginPath();
              contexts[1].rect(p.left, p.top, p.plotWidth, p.plotHeight);
              contexts[1].clip();
            }
            painter.draw(contexts[1], rings, p, exporting);
            if (exporting) contexts[1].restore();
          };
          const compare = (rings, packed, p, exporting = false) => {
            oldDraw(rings, p);
            newDraw(packed, p, exporting);
            const a = contexts[0].getImageData(
                0,
                0,
                canvases[0].width,
                canvases[0].height,
              ).data,
              b = contexts[1].getImageData(
                0,
                0,
                canvases[1].width,
                canvases[1].height,
              ).data;
            let total = 0,
              max = 0,
              large = 0;
            for (let i = 0; i < a.length; i += 4) {
              let diff = 0;
              for (let c = 0; c < 3; c++) {
                const d = Math.abs(a[i + c] - b[i + c]);
                total += d;
                diff = Math.max(diff, d);
                max = Math.max(max, d);
              }
              if (diff > 4) large++;
            }
            return {
              dpr: p.dpr,
              exporting,
              meanError: total / ((a.length / 4) * 3),
              maxError: max,
              fractionAboveFour: large / (a.length / 4),
            };
          };
          const cases = [];
          for (const p of [
            base,
            { ...base, dpr: 2 },
            { ...base, dpr: 2.56 },
            { ...base, dpr: 2, sx: 1.1, sy: 1.1, ox: -80, oy: -160 },
          ])
            cases.push(compare(legacy, packed, p, p.dpr === 2.56));
          newDraw(packed, base);
          const before = pathCommands,
            strokes = layerStrokes;
          const med = (a) =>
            a.toSorted((a, b) => a - b)[Math.floor(a.length / 2)];
          const oldTimes = [],
            newTimes = [];
          for (let i = 0; i < 30; i++) {
            let t = performance.now();
            oldDraw(legacy, base);
            contexts[0].getImageData(0, 0, 1, 1);
            oldTimes.push(performance.now() - t);
            t = performance.now();
            newDraw(packed, base);
            contexts[1].getImageData(0, 0, 1, 1);
            newTimes.push(performance.now() - t);
          }
          const repeatedCommands = pathCommands - before,
            repeatedStrokes = layerStrokes - strokes;
          // New metadata with retained coordinates must keep both native paths
          // and the complete layer. Style edits repaint without rebuilding paths.
          const metadata = (await transfer.call("guides")).phaseGuides;
          newDraw(metadata, base);
          const metadataCommands = pathCommands - before;
          const styled = metadata.map((r) =>
            r.phaseIndex === 0 ? { ...r, color: "#ffbb11" } : r,
          );
          const legacyStyled = legacy.map((r) =>
            r.phaseIndex === 0 ? { ...r, color: "#ffbb11" } : r,
          );
          cases.push(compare(legacyStyled, styled, base));
          const styleCommands = pathCommands - before;
          frame = binary(changed);
          const edited = (await transfer.call("guides")).phaseGuides;
          const start = pathCommands;
          newDraw(edited, base);
          const editedCommands = pathCommands - start;
          const editedPhasePoints = edited
            .filter((r) => applyAll || r.phaseIndex === 0)
            .reduce((n, r) => n + r.points.length - 1, 0);
          newDraw(edited, { ...base, dpr: 2.56 }, true);
          const png = canvases[1].toDataURL("image/png");
          const oldEditTimes = [],
            newEditTimes = [];
          for (const edit of edits) {
            frame = binary(edit);
            const current = (await transfer.call("guides")).phaseGuides;
            const { forEachPoint } = await import(
              new URL("src/phaseGuidePoints.ts", url).href
            );
            const expanded = current.map((r) => {
              const points = [];
              forEachPoint(r.points, (x, y) => points.push([x, y]));
              return { ...r, points };
            });
            let t = performance.now();
            oldDraw(expanded, base);
            contexts[0].getImageData(0, 0, 1, 1);
            oldEditTimes.push(performance.now() - t);
            t = performance.now();
            newDraw(current, base);
            contexts[1].getImageData(0, 0, 1, 1);
            newEditTimes.push(performance.now() - t);
          }
          compare(legacy, packed, base);
          Path2D.prototype.lineTo = line;
          CanvasRenderingContext2D.prototype.stroke = stroke;
          return {
            phases: 20,
            applyAll,
            paths: packed.length,
            oldRedrawMs: med(oldTimes),
            cachedRedrawMs: med(newTimes),
            oldEditPaintMs: med(oldEditTimes),
            cachedEditPaintMs: med(newEditTimes),
            repeatedCommands,
            repeatedStrokes,
            metadataCommands,
            styleCommands,
            editedCommands,
            editedPhasePoints,
            pngBytes: png.length,
            cases,
          };
        },
        { url, legacy, packet, changed, edits, applyAll },
      );
      assert.equal(report.repeatedCommands, 0);
      assert.equal(report.repeatedStrokes, 0);
      assert.equal(report.metadataCommands, 0);
      assert.equal(report.styleCommands, 0);
      assert.equal(report.editedCommands, report.editedPhasePoints);
      assert.ok(report.pngBytes > 10000);
      for (const c of report.cases) {
        if (c.exporting)
          assert.equal(
            c.maxError,
            0,
            "Vector-path PNG exports retain the preceding pixels",
          );
        assert.ok(c.meanError < 0.15, JSON.stringify(c));
        assert.ok(c.fractionAboveFour < 0.001, JSON.stringify(c));
      }
      await page.screenshot({ path: path.join(artifacts, `${name}.png`) });
      receipts.push({ browser: name, ...report });
    } finally {
      await browser.close();
    }
  }
  await writeFile(
    path.join(artifacts, "report.json"),
    JSON.stringify(receipts, null, 2),
  );
  console.log(JSON.stringify(receipts, null, 2));
} finally {
  await server.close();
  await native.close();
}
