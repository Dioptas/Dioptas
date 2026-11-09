// Headless event-to-canvas and next-frame timings through the real React UI
// and Rust stdio processor. The test bridge substitutes for Tauri OS IPC;
// the final frame opportunity is not a physical-screen/scanout measurement.
import assert from "node:assert/strict";
import path from "node:path";
import { mkdir, writeFile } from "node:fs/promises";
import { pathToFileURL } from "node:url";
import { chromium, webkit } from "playwright";
import { nativeClient, root } from "./native_backend_client.mjs";
import { selectCalibrationRing } from "./calibration_ring_picker.mjs";
const args = process.argv.slice(2);
const option = (name, fallback) =>
  args.includes(name) ? args[args.indexOf(name) + 1] : fallback;
const artifacts = path.join(root, "desktop/artifacts/calibration-latency");
await mkdir(artifacts, { recursive: true });
const html = path.resolve(
  option("--ui", path.join(artifacts, "baseline-ui/index.html")),
);
const processor = path.resolve(
  option(
    "--processor",
    path.join(root, "desktop/backend/target/debug/dioptas-processor"),
  ),
);
const label = option("--label", "baseline");
const repetitions = Number(option("--repetitions", "8"));
const seeds = [
  [637, 564, 1],
  [671, 511, 2],
  [668, 703, 3],
  [350.5, 592.8, 1],
  [554.3, 367.9, 1],
];
const summary = (values) => {
  const s = [...values].sort((a, b) => a - b);
  return {
    median: s[Math.floor(s.length / 2)],
    p95: s[Math.min(s.length - 1, Math.ceil(s.length * 0.95) - 1)],
    min: s[0],
    max: s.at(-1),
  };
};
const reports = [];
for (const [browserName, type] of [
  ["chromium", chromium],
  ["webkit", webkit],
]) {
  const browser = await type.launch({ headless: true });
  try {
    for (const fixture of ["CeO2", "LaB6"]) {
      const native = nativeClient({ executable: processor });
      const page = await browser.newPage({
        viewport: { width: 1440, height: 940 },
      });
      const sent = new Set(),
        errors = [],
        calls = [];
      page.on("pageerror", (e) => errors.push(e.message));
      const call = async (action, payload = {}) => {
        const t = performance.now();
        const r = await native.invoke(action, payload);
        calls.push({ action, ms: performance.now() - t });
        assert.equal(r.ok, true, JSON.stringify(r));
        return r;
      };
      try {
        if (fixture === "CeO2") await call("example");
        else {
          await call("open_image", {
            path: path.join(root, "dioptas/tests/data/LaB6_40keV_MarCCD.tif"),
          });
          await call("calibration_setup", {
            calibrant: "LaB6",
            wavelength: 0.31,
            distance: 200,
            pixel_x: 79,
            pixel_y: 79,
          });
        }
        await page.exposeFunction("__nativeInvoke", async (action, payload) => {
          const t = performance.now();
          const response = await call(action, payload);
          const nativeMs = performance.now() - t;
          const incoming = [];
          const visit = (v) => {
            if (!v || typeof v !== "object") return;
            if (v.bufferId && !sent.has(v.bufferId)) {
              sent.add(v.bufferId);
              incoming.push([
                v.bufferId,
                native.buffers.get(v.bufferId).toString("base64"),
              ]);
            }
            for (const x of Object.values(v)) visit(x);
          };
          visit(response);
          return { response, incoming, nativeMs };
        });
        await page.addInitScript(() => {
          window.__pending = 0;
          window.__latency = null;
          window.__traces = [];
          window.__dioptasNavigationTrace = (e) => {
            window.__traces.push(e);
          };
          const buffers = new Map();
          const hydrate = (v) => {
            if (Array.isArray(v)) return v.map(hydrate);
            if (!v || typeof v !== "object") return v;
            if (v.bufferId) return { ...v, data: buffers.get(v.bufferId) };
            return Object.fromEntries(
              Object.entries(v).map(([k, x]) => [k, hydrate(x)]),
            );
          };
          window.pywebview = {
            api: {
              invoke: async (action, payload) => {
                const track = !["pixel", "progress"].includes(action);
                if (track) window.__pending++;
                const started = performance.now();
                try {
                  const { response, incoming, nativeMs } =
                    await window.__nativeInvoke(action, payload);
                  for (const [id, encoded] of incoming) {
                    const text = atob(encoded),
                      bytes = new Uint8Array(text.length);
                    for (let i = 0; i < text.length; i++)
                      bytes[i] = text.charCodeAt(i);
                    buffers.set(id, bytes.buffer);
                  }
                  if (window.__latency?.action === action) {
                    const m = window.__latency;
                    m.bridgeStartedAt = started;
                    m.responseAt = performance.now();
                    m.nativeMs = nativeMs;
                    m.expectedCount = response.state.calibration.picks.reduce(
                      (n, g) => n + g.points.length,
                      0,
                    );
                    m.science = {
                      picks: response.state.calibration.picks,
                      geometry: response.state.geometry,
                      rms: response.state.calibration.rmsDegrees,
                    };
                  }
                  return hydrate(response);
                } finally {
                  if (track) window.__pending--;
                }
              },
            },
          };
          const proto = CanvasRenderingContext2D.prototype,
            clear = proto.clearRect,
            arc = proto.arc,
            stroke = proto.stroke;
          proto.clearRect = function (...a) {
            this.__peakCount = 0;
            return clear.apply(this, a);
          };
          proto.arc = function (...a) {
            if (
              this.canvas.dataset.testid === "detector-canvas" &&
              ["#ff8c00", "#ff0000"].includes(this.fillStyle)
            )
              this.__peakCount = (this.__peakCount || 0) + 1;
            return arc.apply(this, a);
          };
          proto.stroke = function (...a) {
            const r = stroke.apply(this, a),
              m = window.__latency;
            if (
              m?.responseAt &&
              !m.drawnAt &&
              this.canvas.dataset.testid === "detector-canvas" &&
              m.expectedCount > 0 &&
              this.__peakCount === m.expectedCount
            ) {
              m.drawnAt = performance.now();
              requestAnimationFrame(() => {
                m.frameAt = performance.now();
                requestAnimationFrame(() => {
                  m.presentedBy = performance.now();
                });
              });
            }
            return r;
          };
          document.addEventListener(
            "pointerup",
            (e) => {
              const m = window.__latency;
              if (
                m?.action === "pick_peak" &&
                e.target.dataset.testid === "detector-canvas"
              )
                m.eventAt = performance.now();
            },
            true,
          );
          document.addEventListener(
            "click",
            () => {
              const m = window.__latency;
              if (m?.action === "calibrate" && !m.eventAt)
                m.eventAt = performance.now();
            },
            true,
          );
        });
        await page.goto(pathToFileURL(html).href);
        await page.getByTestId("detector-canvas").waitFor();
        const ready = async () => {
          await page.waitForFunction(
            () => window.__pending === 0 && !document.querySelector(".spin"),
          );
          await page.evaluate(
            () =>
              new Promise((r) =>
                requestAnimationFrame(() => requestAnimationFrame(r)),
              ),
          );
        };
        await ready();
        // Keep ring selection fixed between repetitions, avoiding unrelated menu work.
        await page
          .getByLabel("Automatically advance ring number", { exact: true })
          .uncheck();
        await ready();
        const samples = [];
        const begin = (action) =>
          page.evaluate((action) => {
            window.__traces = [];
            window.__latency = { action };
          }, action);
        const finish = async () => {
          await page.waitForFunction(
            () => window.__latency?.presentedBy,
            { timeout: 45000 },
            { polling: "raf" },
          );
          await ready();
          return page.evaluate(() => {
            const m = window.__latency;
            return {
              ...m,
              traces: window.__traces,
              totalMs: m.drawnAt - m.eventAt,
              eventToBridgeMs: m.bridgeStartedAt - m.eventAt,
              bridgeMs: m.responseAt - m.bridgeStartedAt,
              responseToDrawMs: m.drawnAt - m.responseAt,
              nextFrameMs: m.frameAt - m.eventAt,
              presentedByMs: m.presentedBy - m.eventAt,
            };
          });
        };
        const pick = async (x, y, ring) => {
          await selectCalibrationRing(page, ring);
          await ready();
          const canvas = page.getByTestId("detector-canvas");
          const box = await canvas.boundingBox();
          const p = await canvas.evaluate((el) => ({
            left: +el.dataset.plotLeft,
            top: +el.dataset.plotTop,
            width: +el.dataset.plotWidth,
            height: +el.dataset.plotHeight,
            x0: +el.dataset.viewXMin,
            x1: +el.dataset.viewXMax,
            y0: +el.dataset.viewYMin,
            y1: +el.dataset.viewYMax,
          }));
          await begin("pick_peak");
          await page.mouse.click(
            box.x + p.left + ((x - p.x0) / (p.x1 - p.x0)) * p.width,
            box.y + p.top + ((p.y1 - y) / (p.y1 - p.y0)) * p.height,
          );
          return finish();
        };
        const points =
          fixture === "CeO2"
            ? seeds
            : [
                [1129.4, 1179.6, 1],
                [1119.8, 1268.5, 2],
              ];
        for (let i = 0; i < repetitions; i++) {
          const [x, y, ring] = points[i % points.length];
          samples.push({
            kind: i === 0 ? "cold-pick" : "warm-pick",
            ...(await pick(x, y, ring)),
          });
        }
        if (fixture === "CeO2") {
          // Fresh five-group input for each calibration prevents repeated-fit drift.
          for (const automatic of [false, true])
            for (const numberOfRings of automatic ? [4, 15] : [4]) {
              for (let repeat = 0; repeat < 3; repeat++) {
                await page.evaluate(() =>
                  window.__dioptasNavigationProbe.run("example"),
                );
                await ready();
                for (const p of seeds) await pick(...p);
                await page.evaluate(
                  ({ automatic, numberOfRings }) =>
                    window.__dioptasNavigationProbe.run("workflow_settings", {
                      automaticRefinement: automatic,
                      numberOfRings,
                    }),
                  { automatic, numberOfRings },
                );
                await ready();
                await page
                  .getByRole("tab", { name: "Step 3: Calibrate", exact: true })
                  .click();
                await ready();
                await begin("calibrate");
                await page
                  .getByRole("button", { name: "Calibrate", exact: true })
                  .click();
                samples.push({
                  kind: automatic ? `automatic-${numberOfRings}` : "manual-fit",
                  ...(await finish()),
                });
              }
            }
        }
        assert.deepEqual(errors, []);
        const result = {
          label,
          browser: browserName,
          fixture,
          renderer: await page
            .getByTestId("detector-canvas")
            .getAttribute("data-renderer"),
          samples,
        };
        result.summary = Object.fromEntries(
          [...new Set(samples.map((s) => s.kind))].map((kind) => {
            const rows = samples.filter((s) => s.kind === kind);
            return [
              kind,
              Object.fromEntries(
                [
                  "totalMs",
                  "nativeMs",
                  "bridgeMs",
                  "responseToDrawMs",
                  "nextFrameMs",
                  "presentedByMs",
                ].map((k) => [k, summary(rows.map((s) => s[k]))]),
              ),
            ];
          }),
        );
        reports.push(result);
        console.log(
          JSON.stringify({
            label,
            browser: browserName,
            fixture,
            summary: result.summary,
          }),
        );
      } catch (error) {
        console.error(
          await page.evaluate(() => ({
            latency: window.__latency,
            traces: window.__traces,
            pending: window.__pending,
            canvas: document
              .querySelector("[data-testid=detector-canvas]")
              ?.outerHTML.slice(0, 350),
            error: document.querySelector(".app-status")?.textContent,
          })),
        );
        throw error;
      } finally {
        await page.close();
        await native.close();
      }
    }
  } finally {
    await browser.close();
  }
}
await writeFile(
  path.join(artifacts, `${label}.json`),
  JSON.stringify(
    {
      scope:
        "Headless pointer-up/click to actual final detector-marker strokes; next animation-frame opportunities also reported. Native Rust stdio, React and browser canvas are real; test bridge replaces Tauri IPC; OS compositor and physical scanout unmeasured.",
      reports,
    },
    null,
    2,
  ) + "\n",
);
