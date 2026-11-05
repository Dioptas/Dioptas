// Headless integration regression against the real Python geometry and canvas paths.
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { createInterface } from "node:readline";
import { mkdir, writeFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { chromium, webkit } from "playwright";

const root = fileURLToPath(new URL("../../", import.meta.url));
const artifacts = new URL("../artifacts/", import.meta.url);
const host = spawn(
  `${root}.venv/bin/python`,
  ["-u", "desktop/scripts/bridge_host.py"],
  {
    cwd: root,
    stdio: ["pipe", "pipe", "pipe"],
  },
);
const pending = new Map(),
  diagnostics = [];
let id = 0;
host.stderr.on("data", (chunk) => diagnostics.push(chunk.toString()));
createInterface({ input: host.stdout }).on("line", (line) => {
  const response = JSON.parse(line),
    task = pending.get(response.id);
  if (!task) return;
  clearTimeout(task.timer);
  pending.delete(response.id);
  task.resolve(response.result);
});
function invoke(action, payload = {}) {
  return new Promise((resolve, reject) => {
    const key = ++id;
    const timer = setTimeout(() => {
      pending.delete(key);
      reject(Error(`Timed out: ${action}`));
    }, 45000);
    pending.set(key, { resolve, timer });
    host.stdin.write(JSON.stringify({ id: key, action, payload }) + "\n");
  });
}
const browser = await (
  process.argv.includes("--webkit") ? webkit : chromium
).launch({ headless: true });
const page = await browser.newPage({
  viewport: { width: 1440, height: 1000 },
  deviceScaleFactor: 2,
});
const errors = [],
  report = [];
page.on("pageerror", (error) => errors.push(error.message));
await page.exposeFunction("__invoke", invoke);
await page.addInitScript(() => {
  window.pywebview = {
    api: {
      invoke: async (action, payload) => {
        window.__pending = (window.__pending ?? 0) + 1;
        try {
          return await window.__invoke(action, payload);
        } finally {
          window.__pending--;
        }
      },
    },
  };
  document.addEventListener(
    "pointerup",
    (event) => {
      if (event.target.dataset.testid === "detector-canvas")
        event.target.__pointer = { x: event.clientX, y: event.clientY };
    },
    true,
  );
  const proto = CanvasRenderingContext2D.prototype;
  for (const name of ["beginPath", "moveTo", "lineTo", "stroke", "clearRect"]) {
    const original = proto[name];
    proto[name] = function (...args) {
      if (this.canvas.dataset.testid === "detector-canvas") {
        if (name === "clearRect") this.canvas.__guides = [];
        if (name === "beginPath") this.__path = [];
        if (name === "moveTo" || name === "lineTo")
          this.__path?.push([name, ...args]);
        if (name === "stroke" && this.strokeStyle === "#00ff00")
          this.canvas.__guides.push({
            width: this.lineWidth,
            path: this.__path,
          });
      }
      return original.apply(this, args);
    };
  }
});
const ready = async () => {
  await page.waitForFunction(
    () => !window.__pending && !document.querySelector(".spin"),
  );
  assert.deepEqual(await page.getByRole("alert").allTextContents(), []);
};
const detector = page.getByTestId("detector-canvas");
const screen = (x, y) =>
  detector.evaluate(
    (canvas, [x, y]) => {
      const d = canvas.dataset,
        box = canvas.getBoundingClientRect();
      return {
        x:
          box.x +
          +d.plotLeft +
          ((x - +d.viewXMin) * +d.plotWidth) / (+d.viewXMax - +d.viewXMin),
        y:
          box.y +
          +d.plotTop +
          ((+d.viewYMax - y) * +d.plotHeight) / (+d.viewYMax - +d.viewYMin),
      };
    },
    [x, y],
  );
async function checkClick(x, y) {
  const target = await screen(x, y);
  await page.mouse.click(target.x, target.y);
  await ready();
  const check = await detector.evaluate((canvas) => {
    const box = canvas.getBoundingClientRect(),
      guides = canvas.__guides,
      pointer = canvas.__pointer;
    const cross = guides.find((g) => g.width === 1.5);
    if (!cross) throw Error("No clicked cross drawn");
    const center = [
      (cross.path[0][1] + cross.path[1][1]) / 2,
      cross.path[0][2],
    ];
    let distance = Infinity;
    for (const guide of guides.filter((g) => g.width === 2)) {
      for (let i = 1; i < guide.path.length; i++) {
        const [, ax, ay] = guide.path[i - 1],
          [, bx, by] = guide.path[i];
        const dx = bx - ax,
          dy = by - ay,
          length = dx * dx + dy * dy;
        if (!length || guide.path[i][0] !== "lineTo") continue;
        const t = Math.max(
          0,
          Math.min(1, ((center[0] - ax) * dx + (center[1] - ay) * dy) / length),
        );
        distance = Math.min(
          distance,
          Math.hypot(ax + t * dx - center[0], ay + t * dy - center[1]),
        );
      }
    }
    return {
      click: [+canvas.dataset.clickX, +canvas.dataset.clickY],
      crossError: Math.hypot(
        center[0] + box.x - pointer.x,
        center[1] + box.y - pointer.y,
      ),
      contourError: distance,
      pixelsPerSourcePixel:
        +canvas.dataset.plotWidth /
        (+canvas.dataset.viewXMax - +canvas.dataset.viewXMin),
    };
  });
  // Compare with the dispatched event: WebKit quantizes synthetic coordinates.
  // Neither backend nor renderer may snap to source pixels or shift half a pixel.
  assert.ok(check.crossError < 0.1, JSON.stringify(check));
  assert.ok(check.contourError < 0.1, JSON.stringify(check));
  report.push(check);
}
try {
  for (const [action, payload] of [
    ["example", {}],
    [
      "open_calibration",
      { path: `${root}dioptas/tests/data/CeO2_Pilatus1M.poni` },
    ],
  ]) {
    const result = await invoke(action, payload);
    assert.equal(result.ok, true, result.error);
  }
  await page.goto(
    new URL("../../dioptas/desktop/ui/index.html", import.meta.url).href,
  );
  await ready();
  await page.getByRole("button", { name: "Integration", exact: true }).click();
  await ready();
  await checkClick(637.2, 564.7);
  const start = await screen(615, 545),
    end = await screen(655, 585);
  await page.mouse.move(start.x, start.y);
  await page.mouse.down();
  await page.mouse.move(end.x, end.y, { steps: 12 });
  await page.mouse.up();
  await checkClick(637.2, 564.7);
  assert.ok(
    report.at(-1).pixelsPerSourcePixel > 5,
    "Must test enlarged source pixels",
  );
  await checkClick(630.8, 560.15);
  await page.setViewportSize({ width: 1100, height: 800 });
  await page.evaluate(
    () =>
      new Promise((resolve) =>
        requestAnimationFrame(() => requestAnimationFrame(resolve)),
      ),
  );
  await checkClick(635.35, 570.85);
  assert.deepEqual(errors, []);
  await mkdir(artifacts, { recursive: true });
  await page.screenshot({
    path: fileURLToPath(new URL("linked-position.png", artifacts)),
  });
  await writeFile(
    new URL("linked-position.json", artifacts),
    JSON.stringify(report, null, 2),
  );
  console.log(JSON.stringify(report, null, 2));
} catch (error) {
  console.error(diagnostics.join(""));
  throw error;
} finally {
  for (const task of pending.values()) clearTimeout(task.timer);
  await browser.close();
  host.stdin.end();
}
