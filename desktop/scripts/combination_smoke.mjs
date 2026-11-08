import assert from "node:assert/strict";
import { spawn, execFileSync } from "node:child_process";
import { createInterface } from "node:readline";
import { mkdir, mkdtemp, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { createServer } from "vite";
import { chromium, webkit } from "playwright";
import { setInterfaceTextSize } from "./plot_navigation.mjs";

const desktop = fileURLToPath(new URL("../", import.meta.url));
const root = fileURLToPath(new URL("../../", import.meta.url));
const artifacts = path.join(desktop, "artifacts/detector-combination");
await mkdir(artifacts, { recursive: true });
const temporary = await mkdtemp(path.join(tmpdir(), "dioptas-image-change-"));
const project = path.join(temporary, "detectors.dio");
const small = path.join(temporary, "small.tif");
const same = path.join(temporary, "same.tif");
execFileSync(
  path.join(root, ".venv/bin/python"),
  [
    "-c",
    "import runpy,sys; from pathlib import Path; scope=runpy.run_path('desktop/tests/test_combination.py'); scope['make_project'](Path(sys.argv[1]))",
    temporary,
  ],
  {
    cwd: root,
    env: { ...process.env, OMP_NUM_THREADS: "1", OPENBLAS_NUM_THREADS: "1" },
  },
);
const host = spawn(
  path.join(root, ".venv/bin/python"),
  ["-u", "desktop/scripts/bridge_host.py"],
  {
    cwd: root,
    env: { ...process.env, OMP_NUM_THREADS: "1", OPENBLAS_NUM_THREADS: "1" },
    stdio: ["pipe", "pipe", "pipe"],
  },
);
const pending = new Map();
let nextId = 0;
const diagnostics = [];
host.stderr.on("data", (chunk) => diagnostics.push(chunk.toString()));
createInterface({ input: host.stdout }).on("line", (line) => {
  const message = JSON.parse(line);
  const task = pending.get(message.id);
  if (task) {
    pending.delete(message.id);
    clearTimeout(task.timer);
    task.resolve(message.result);
  }
});
host.on("exit", (code) => {
  for (const task of pending.values()) {
    clearTimeout(task.timer);
    task.reject(new Error(`Bridge exited ${code}`));
  }
  pending.clear();
});
function invoke(action, payload = {}) {
  return new Promise((resolve, reject) => {
    const id = ++nextId;
    const timer = setTimeout(() => {
      pending.delete(id);
      reject(new Error(`Timed out: ${action}`));
    }, 30000);
    pending.set(id, { resolve, reject, timer });
    host.stdin.write(JSON.stringify({ id, action, payload }) + "\n");
  });
}
async function call(action, payload) {
  const result = await invoke(action, payload);
  assert.ok(result.ok, result.error);
  return result;
}
const server = await createServer({
  root: desktop,
  server: { host: "127.0.0.1", port: 0 },
});
await server.listen();
const browserName = process.argv.includes("--webkit") ? "webkit" : "chromium";
const browser = await (browserName === "webkit" ? webkit : chromium).launch({
  headless: true,
});
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
const errors = [];
page.on("pageerror", (e) => errors.push(e.message));
let selectedImage = small;
await page.exposeFunction("__dioptasInvoke", (action, payload = {}) => {
  if (action === "open_image" && !payload.path)
    payload = { ...payload, path: selectedImage };
  if (action === "open_calibration")
    payload = {
      ...payload,
      path: path.join(root, "dioptas/tests/data/CeO2_Pilatus1M.poni"),
    };
  if (action === "save_combined_pattern")
    payload = { ...payload, path: path.join(temporary, "combined.xy") };
  return invoke(action, payload);
});
await page.addInitScript(() => {
  window.__imageChangePending = 0;
  window.pywebview = {
    api: {
      invoke: async (action, payload) => {
        window.__imageChangePending++;
        try {
          return await window.__dioptasInvoke(action, payload);
        } finally {
          window.__imageChangePending--;
        }
      },
    },
  };
});
const button = (name) => page.getByRole("button", { name, exact: true });
async function ready() {
  await page.waitForFunction(
    () => !window.__imageChangePending && !document.querySelector(".spin"),
  );
  await page.evaluate(
    () =>
      new Promise((resolve) =>
        requestAnimationFrame(() => requestAnimationFrame(resolve)),
      ),
  );
  assert.deepEqual(await page.getByRole("alert").allTextContents(), []);
}
const report = {
  browser: browserName,
  headless: true,
  engine: process.argv.includes("--dioptrin") ? "dioptrin" : "pyfai",
  checks: [],
};
try {
  await call("calibration_engine", {
    engine: process.argv.includes("--dioptrin") ? "dioptrin" : "pyfai",
  });
  await call("open_project", { path: project });
  await page.goto(server.resolvedUrls.local[0]);
  await button("Integration").click();
  await ready();
  assert.equal(
    await page.getByLabel("Configuration", { exact: true }).inputValue(),
    "0",
  );
  await button("Detector histogram settings").click();
  await page.getByLabel("Image scale", { exact: true }).selectOption("log");
  await page.keyboard.press("Escape");
  await page
    .getByLabel("Lower intensity handle", { exact: true })
    .press("ArrowRight");
  const lower = await page
    .getByLabel("Lower intensity handle", { exact: true })
    .getAttribute("aria-valuenow");
  await page.getByLabel("Configuration", { exact: true }).selectOption("1");
  await ready();
  await button("Detector histogram settings").click();
  assert.equal(
    await page.getByLabel("Image scale", { exact: true }).inputValue(),
    "linear",
  );
  await page.keyboard.press("Escape");
  await page.getByLabel("Detector factor", { exact: true }).fill("2.5");
  await page.getByLabel("Detector factor", { exact: true }).press("Enter");
  await ready();
  await button("Combine patterns").click();
  await ready();
  assert.equal(
    await button("Combine patterns").getAttribute("aria-pressed"),
    "true",
  );
  await button("Combine cakes").click();
  await ready();
  const selectedBackend = (await call("state")).state.combination.backends;
  assert.equal(
    selectedBackend.cake,
    report.engine === "dioptrin" ? "Dioptrin" : "pyFAI",
  );
  assert.equal(
    selectedBackend.pattern,
    report.engine === "dioptrin" ? "Dioptrin" : "pyFAI",
  );
  await button("Save combined pattern").click();
  await ready();
  await page.getByLabel("Configuration", { exact: true }).selectOption("0");
  await ready();
  assert.equal(
    await page
      .getByLabel("Lower intensity handle", { exact: true })
      .getAttribute("aria-valuenow"),
    lower,
  );
  assert.equal(
    await button("Auto intensity").getAttribute("aria-pressed"),
    "false",
  );
  await button("Detector histogram settings").click();
  assert.equal(
    await page.getByLabel("Image scale", { exact: true }).inputValue(),
    "log",
  );
  await page.keyboard.press("Escape");
  report.checks.push(
    "independent detector scale/limits, factors, both combination switches and combined export",
  );
  for (const large of [false, true]) {
    await page.setViewportSize({ width: 1000, height: 668 });
    await setInterfaceTextSize(page, large);
    await ready();
    const layout = await page
      .locator(".configuration-combination")
      .evaluate((el) => {
        const box = el.getBoundingClientRect();
        return {
          right: box.right,
          width: innerWidth,
          overflowing: [...el.querySelectorAll("button,input,select")].some(
            (c) => {
              const r = c.getBoundingClientRect();
              return (
                r.left < box.left ||
                r.right > box.right ||
                r.bottom > box.bottom
              );
            },
          ),
        };
      });
    assert.ok(
      layout.right <= layout.width && !layout.overflowing,
      JSON.stringify(layout),
    );
    const plots = await page.locator(".detector-panel").evaluate((el) => {
      const r = el.getBoundingClientRect();
      const bar = document
        .querySelector(".configuration-combination")
        .getBoundingClientRect();
      const controls = document
        .querySelector(".integration-layout > .sidebar")
        .getBoundingClientRect();
      return {
        width: r.width,
        height: r.height,
        top: r.top,
        barBottom: bar.bottom,
        controlsRight: controls.right,
        windowWidth: innerWidth,
      };
    });
    assert.ok(
      plots.width > 290 &&
        plots.height > 300 &&
        plots.top >= plots.barBottom &&
        plots.controlsRight <= plots.windowWidth,
      JSON.stringify(plots),
    );
    await page.screenshot({
      path: path.join(
        artifacts,
        `${browserName}-${report.engine}-${large ? "large" : "normal"}.png`,
      ),
    });
  }
  await button("Cake").click();
  await button("Pattern unit Q").click();
  await ready();
  const cakeBeforeClick = (await call("state")).cake;
  assert.equal(cakeBeforeClick.unit, "q_A^-1");
  const cakeCanvas = page.getByTestId("cake-canvas");
  const dimensions = await cakeCanvas.evaluate((el) => ({
    left: Number(el.dataset.plotLeft),
    top: Number(el.dataset.plotTop),
    width: Number(el.dataset.plotWidth),
    height: Number(el.dataset.plotHeight),
    xMin: Number(el.dataset.viewXMin),
    xMax: Number(el.dataset.viewXMax),
  }));
  const sourceX = dimensions.xMin + 0.6 * (dimensions.xMax - dimensions.xMin);
  const expectedQ =
    cakeBeforeClick.radialRange[0] +
    (sourceX / cakeBeforeClick.fullWidth) *
      (cakeBeforeClick.radialRange[1] - cakeBeforeClick.radialRange[0]);
  await cakeCanvas.click({
    position: {
      x: dimensions.left + 0.6 * dimensions.width,
      y: dimensions.top + 0.5 * dimensions.height,
    },
  });
  await ready();
  const inspected = await call("state");
  const pixelQ =
    (cakeBeforeClick.radialRange[1] - cakeBeforeClick.radialRange[0]) /
    dimensions.width;
  assert.ok(
    Math.abs(inspected.linked.radial - expectedQ) <= 1.5 * pixelQ,
    JSON.stringify({ expectedQ, linked: inspected.linked, pixelQ }),
  );
  assert.ok(
    Math.abs(
      Number(await cakeCanvas.getAttribute("data-linked-position")) -
        inspected.linked.radial,
    ) < 1e-9,
  );
  await page.screenshot({
    path: path.join(artifacts, `${browserName}-${report.engine}-cake-q.png`),
  });
  report.checks.push(
    "combined Q cake display, physical click conversion and linked guide",
  );
  assert.deepEqual(errors, []);
  report.checks.push("1000 × 668 layout at both text sizes");
  await writeFile(
    path.join(artifacts, `${browserName}-${report.engine}.json`),
    JSON.stringify(report, null, 2),
  );
  console.log(JSON.stringify(report, null, 2));
} catch (e) {
  console.error(diagnostics.join("").slice(-6000));
  throw e;
} finally {
  await browser.close();
  await server.close();
  host.stdin.end();
  await new Promise((resolve) => host.once("exit", resolve));
  await rm(temporary, { recursive: true, force: true });
}
