import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { createInterface } from "node:readline";
import { mkdir, writeFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import path from "node:path";
import { chromium, webkit } from "playwright";
const root = fileURLToPath(new URL("../", import.meta.url));
const artifacts = path.join(root, "artifacts");
await mkdir(artifacts, { recursive: true });
const host = spawn(process.execPath, ["scripts/bridge_host.mjs"], {
  cwd: root,
  stdio: ["pipe", "pipe", "pipe"],
});
let identifier = 0;
const pending = new Map(),
  logs = [],
  requests = [];
host.stderr.on("data", (b) => logs.push(b.toString()));
createInterface({ input: host.stdout }).on("line", (line) => {
  const message = JSON.parse(line),
    task = pending.get(message.id);
  if (task) {
    clearTimeout(task.timer);
    pending.delete(message.id);
    task.resolve(message.result);
  }
});
function invoke(action, payload = {}) {
  requests.push(action);
  return new Promise((resolve, reject) => {
    const id = ++identifier;
    const timer = setTimeout(() => reject(Error(`Timed out ${action}`)), 45000);
    pending.set(id, { resolve, timer });
    host.stdin.write(JSON.stringify({ id, action, payload }) + "\n");
  });
}
const browser = await (
  process.argv.includes("--webkit") ? webkit : chromium
).launch({ headless: true });
const page = await browser.newPage({ viewport: { width: 1600, height: 1000 } });
const errors = [];
page.on("pageerror", (e) => errors.push(e.message));
let nextOpenPath = null;
let levelsGate = null;
let levelsStarted = 0;
const autoReplies = [];
await page.exposeFunction("__dioptasInvoke", async (action, payload) => {
  if (action === "open_image" && nextOpenPath)
    payload = { ...payload, path: nextOpenPath };
  if (action === "image_levels") {
    levelsStarted++;
    if (levelsGate) await levelsGate;
  }
  const result = await invoke(action, payload);
  if (action === "image_levels") autoReplies.push({ result, args: payload });
  return result;
});
await page.addInitScript(() => {
  window.pywebview = {
    api: {
      invoke: async (a, p) => {
        window.__pendingCommands = (window.__pendingCommands ?? 0) + 1;
        try {
          return await window.__dioptasInvoke(a, p);
        } finally {
          window.__pendingCommands--;
        }
      },
    },
  };
});
await page.addInitScript((canvasOnly) => {
  const settings = {
    detector: { mode: "percentile", percentile: 7, filter_gaps: true },
    "multi-detector": { mode: "mean3std", percentile: 2.5, filter_gaps: true },
    "mask-detector": { mode: "minmax", percentile: 2.5, filter_gaps: false },
    "map-detector": { mode: "percentile", percentile: 5, filter_gaps: false },
  };
  for (const [name, auto] of Object.entries(settings))
    localStorage.setItem(
      `dioptas-auto-levels-v1:${name}`,
      JSON.stringify(auto),
    );
  if (canvasOnly) {
    const original = HTMLCanvasElement.prototype.getContext;
    HTMLCanvasElement.prototype.getContext = function (kind, ...args) {
      return kind === "webgl2" ? null : original.call(this, kind, ...args);
    };
  }
}, process.argv.includes("--canvas"));
const ready = async () => {
  await page.waitForFunction(
    () =>
      !document.querySelector(".spin") &&
      !window.__pendingCommands &&
      !document.querySelector('.map-layers[aria-busy="true"]'),
  );
  assert.equal(
    await page.getByRole("alert").count(),
    0,
    JSON.stringify(await page.getByRole("alert").allTextContents()),
  );
};
const click = async (name) => {
  await page.getByRole("button", { name, exact: true }).first().click();
  await ready();
};
try {
  assert.equal((await invoke("example")).ok, true);
  assert.equal(
    (
      await invoke("open_calibration", {
        path: path.join(root, "tests/data/CeO2_Pilatus1M.poni"),
      })
    ).ok,
    true,
  );
  await page.goto("file://" + path.join(root, "dist/index.html"));
  await ready();
  await click("Map");
  await page
    .locator(".map-controls")
    .getByRole("button", { name: "Load images…", exact: true })
    .click();
  await ready();
  let state = await invoke("state");
  assert.equal(state.map.points, 9);
  assert.equal(
    await page.locator(".map-layout .intensity-histogram").count(),
    2,
  );
  for (const panel of [".map-scan-panel", ".map-detector-panel"])
    assert.equal(
      await page
        .locator(panel + " .image-intensity")
        .getAttribute("data-orientation"),
      "horizontal",
    );
  await page.waitForTimeout(300);
  await page.evaluate(() => {
    window.__draws = [];
    const record = (canvas, operation, args) => {
      const panel = canvas.closest?.(
        ".map-scan-panel,.map-detector-panel,.map-pattern-panel,.detector-panel,.pattern-panel",
      );
      if (panel)
        window.__draws.push({
          time: performance.now(),
          panel: panel.className,
          canvas: canvas.dataset.testid,
          operation,
          args,
        });
    };
    for (const [prototype, methods] of [
      [CanvasRenderingContext2D.prototype, ["clearRect", "drawImage"]],
      [WebGL2RenderingContext.prototype, ["drawArrays", "texImage2D"]],
    ])
      for (const method of methods) {
        const original = prototype[method];
        prototype[method] = function (...args) {
          record(
            this.canvas,
            method,
            method === "texImage2D" ? args.slice(3, 5) : [],
          );
          return original.apply(this, args);
        };
      }
    const observer = new MutationObserver((changes) => {
      for (const change of changes) {
        if (change.target instanceof HTMLCanvasElement)
          record(change.target, "attribute", [
            change.attributeName,
            change.target.getAttribute(change.attributeName),
          ]);
      }
    });
    observer.observe(document.querySelector("main"), {
      subtree: true,
      attributes: true,
      attributeOldValue: true,
    });
  });
  const samples = [];
  const detector = () =>
    page.locator('main [data-testid="detector-canvas"]').last();
  async function measure(mode, select, expectedSource = "detector") {
    await ready();
    await page.waitForTimeout(100);
    const before = requests.length;
    const repliesBefore = autoReplies.length;
    const previousLevels = await detector().evaluate((el) => [
      el.dataset.intensityMin,
      el.dataset.intensityMax,
    ]);
    await page.evaluate(() => {
      window.__draws = [];
    });
    let release;
    levelsGate = new Promise((resolve) => {
      release = resolve;
    });
    const started = levelsStarted;
    await select();
    await page.waitForFunction(() => window.__pendingCommands > 0);
    const deadline = Date.now() + 10000;
    while (levelsStarted === started && Date.now() < deadline)
      await new Promise((resolve) => setTimeout(resolve, 10));
    assert.equal(levelsStarted, started + 1, `${mode}: Auto request missing`);
    // Keep the previous detector pixels and limits until source-precision Auto finishes.
    await page.waitForTimeout(100);
    assert.deepEqual(
      await detector().evaluate((el) => [
        el.dataset.intensityMin,
        el.dataset.intensityMax,
      ]),
      previousLevels,
    );
    assert.equal(
      await page.evaluate(
        () =>
          window.__draws.filter(
            (d) => d.canvas === "detector-gpu" && d.operation === "drawArrays",
          ).length,
      ),
      0,
    );
    levelsGate = null;
    release();
    await ready();
    await page.waitForTimeout(100);
    const draws = await page.evaluate(() => window.__draws);
    const counts = {};
    for (const d of draws) {
      const key = d.panel + "/" + d.canvas + "/" + d.operation;
      counts[key] = (counts[key] ?? 0) + 1;
    }
    const detectorDraws = draws.filter(
      (d) =>
        !d.panel.includes("map-scan-panel") &&
        d.canvas === "detector-gpu" &&
        d.operation === "drawArrays",
    );
    assert.equal(
      draws.filter(
        (d) =>
          !d.panel.includes("map-scan-panel") &&
          d.canvas === "detector-canvas" &&
          d.operation === "clearRect",
      ).length,
      1,
      `${mode}: detector annotation layer repainted unnecessarily`,
    );
    if (mode === "Map") {
      assert.equal(
        draws.filter(
          (d) =>
            d.panel.includes("map-scan-panel") &&
            d.canvas === "detector-canvas" &&
            d.operation === "clearRect",
        ).length,
        1,
      );
      assert.equal(
        draws.filter(
          (d) =>
            d.panel.includes("map-scan-panel") && d.operation === "texImage2D",
        ).length,
        0,
      );
    }
    if (!process.argv.includes("--canvas"))
      assert.equal(
        detectorDraws.length,
        1,
        `${mode}: ${JSON.stringify(counts)}`,
      );
    else
      assert.equal(
        draws.filter(
          (d) =>
            !d.panel.includes("map-scan-panel") &&
            d.canvas === "detector-canvas" &&
            d.operation === "drawImage",
        ).length,
        1,
        `${mode}: ${JSON.stringify(counts)}`,
      );
    const actual = await detector().evaluate((el) => [
      Number(el.dataset.intensityMin),
      Number(el.dataset.intensityMax),
    ]);
    assert.deepEqual(
      actual,
      autoReplies
        .filter((r) => (r.args.source ?? "detector") === expectedSource)
        .at(-1).result.levels,
      `${mode}: final contrast differs from Python Auto`,
    );
    assert.equal(
      autoReplies
        .slice(repliesBefore)
        .filter((r) => (r.args.source ?? "detector") === expectedSource).length,
      1,
      `${mode}: repeated Auto request`,
    );
    const entry = {
      mode,
      requests: requests.slice(before),
      counts,
      levels: actual,
      expectedSource,
    };
    samples.push(entry);
    console.log(JSON.stringify(entry));
  }
  const points = page
    .getByRole("listbox", { name: "Scan arrangement" })
    .getByRole("option");
  for (const index of [1, 2, 3])
    await measure("Map", () => points.nth(index).click());
  const files = [
    "Fe3O4C_M1_map_6_P1_E1_001.tif",
    "Fe3O4C_M1_map_7_P1_E1_001.tif",
  ];
  for (const mode of ["Calibration", "Mask", "Integration"]) {
    await click(mode);
    for (const filename of files) {
      if (filename === files[1]) {
        await detector().evaluate((el) => {
          const box = el.getBoundingClientRect();
          el.dispatchEvent(
            new WheelEvent("wheel", {
              bubbles: true,
              cancelable: true,
              deltaY: -150,
              clientX: box.x + box.width / 2,
              clientY: box.y + box.height / 2,
            }),
          );
        });
      }
      nextOpenPath = path.join(root, "tests/data/map", filename);
      await measure(mode, async () => {
        await page.evaluate(() => document.activeElement?.blur());
        await page.keyboard.press("Control+o");
      });
    }
  }
  assert.equal(
    (
      await invoke("integration_image_background", {
        path: path.join(root, "tests/data/map", files[0]),
      })
    ).ok,
    true,
  );
  nextOpenPath = path.join(root, "tests/data/map", files[0]);
  await page.evaluate(() => document.activeElement?.blur());
  await page.keyboard.press("Control+o");
  await ready();
  await page
    .getByRole("button", { name: "Show corrected image", exact: true })
    .click();
  await ready();
  nextOpenPath = path.join(root, "tests/data/map", files[1]);
  await measure(
    "Integration raw",
    async () => {
      await page.evaluate(() => document.activeElement?.blur());
      await page.keyboard.press("Control+o");
    },
    "raw_detector",
  );
  assert.deepEqual(errors, []);
  await writeFile(
    path.join(
      artifacts,
      `detector-redraw-${process.argv.includes("--webkit") ? "webkit" : "chromium"}${process.argv.includes("--canvas") ? "-canvas" : ""}.json`,
    ),
    JSON.stringify(samples, null, 2),
  );
  console.log("Detector redraw checks passed");
} catch (error) {
  await page.screenshot({
    path: path.join(artifacts, "detector-redraw-failure.png"),
    fullPage: true,
  });
  throw error;
} finally {
  await browser.close();
  host.stdin.end();
  await writeFile(path.join(artifacts, "detector-redraw.log"), logs.join(""));
}
