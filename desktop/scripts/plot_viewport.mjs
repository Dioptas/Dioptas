import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { createInterface } from "node:readline";
import { fileURLToPath } from "node:url";
import {
  copyFile,
  mkdir,
  mkdtemp,
  realpath,
  rm,
  writeFile,
} from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { chromium, webkit } from "playwright";

const root = fileURLToPath(new URL("../../", import.meta.url));
const artifacts = root + "/desktop/artifacts";
await mkdir(artifacts, { recursive: true });
const host = spawn(
  root + "/.venv/bin/python",
  ["-u", "desktop/scripts/bridge_host.py"],
  { cwd: root, stdio: ["pipe", "pipe", "pipe"] },
);
let nextId = 0;
const pending = new Map();
const logs = [];
host.stderr.on("data", (d) => logs.push(d.toString()));
createInterface({ input: host.stdout }).on("line", (line) => {
  try {
    const r = JSON.parse(line);
    const p = pending.get(r.id);
    if (p) {
      clearTimeout(p.timer);
      pending.delete(r.id);
      p.resolve(r.result);
    }
  } catch {
    logs.push(line);
  }
});
const invoke = (action, payload = {}) =>
  new Promise((resolve, reject) => {
    const id = ++nextId;
    const timer = setTimeout(() => {
      pending.delete(id);
      reject(Error(`Timeout: ${action}`));
    }, 45000);
    pending.set(id, { resolve, reject, timer });
    host.stdin.write(JSON.stringify({ id, action, payload }) + "\n");
  });
const call = async (action, payload = {}) => {
  const r = await invoke(action, payload);
  assert.equal(r.ok, true, r.error);
  return r;
};
let browser, page, fixtureDirectory;
const errors = [];
let lambda;
const q = (angle) => (4 * Math.PI * Math.sin((angle * Math.PI) / 360)) / lambda;
const d = (angle) => lambda / (2 * Math.sin((angle * Math.PI) / 360));
const close = (a, b, message, tol = 1e-6) =>
  assert.ok(Math.abs(a - b) < tol, `${message}: ${a} vs ${b}`);
try {
  await call("example");
  const image = (await call("state")).state.imagePath;
  await call("open_calibration", {
    path: root + "/dioptas/tests/data/CeO2_Pilatus1M.poni",
  });
  lambda = (await call("state")).state.geometry.wavelength * 1e10;
  await call("integration_settings", { bins: 160, cake_bins: 30 });
  fixtureDirectory = await realpath(
    await mkdtemp(join(tmpdir(), "dioptas-map-position-")),
  );
  const paths = [];
  for (let i = 0; i < 4; i++) {
    const path = join(fixtureDirectory, `scan_00${i + 1}.tif`);
    await copyFile(image, path);
    paths.push(path);
  }
  await call("map_load", { paths });
  await call("map_grid", { rows: 2, columns: 2 });
  await call("map_roi", { name: "A", minimum: 8, maximum: 18 });
  browser = await (
    process.argv.includes("--webkit") ? webkit : chromium
  ).launch({ headless: true });
  page = await browser.newPage({ viewport: { width: 1600, height: 1000 } });
  page.on("pageerror", (error) => errors.push(error.message));
  await page.exposeFunction("__dioptasInvoke", invoke);
  await page.addInitScript(() => {
    window.pywebview = {
      api: {
        invoke: async (a, p) => {
          window.__pending = (window.__pending ?? 0) + 1;
          try {
            return await window.__dioptasInvoke(a, p);
          } finally {
            window.__pending--;
          }
        },
      },
    };
  });
  const ready = async () => {
    await page.waitForFunction(
      () =>
        document.querySelector(".app") &&
        !document.querySelector(".spin") &&
        !window.__pending,
    );
    await page.evaluate(
      () =>
        new Promise((resolve) =>
          requestAnimationFrame(() => requestAnimationFrame(resolve)),
        ),
    );
    assert.deepEqual(await page.getByRole("alert").allTextContents(), []);
  };
  const click = async (name) => {
    await page.getByRole("button", { name, exact: true }).click();
    await ready();
  };
  const plotPoint = async (canvas, fx, fy) =>
    canvas.evaluate(
      (el, { fx, fy }) => {
        const b = el.getBoundingClientRect(),
          s = el.dataset;
        return {
          x: b.x + +s.plotLeft + fx * +s.plotWidth,
          y: b.y + +s.plotTop + fy * +s.plotHeight,
        };
      },
      { fx, fy },
    );
  const mapPattern = () =>
    page.locator('.map-pattern-panel [data-testid="pattern-canvas"]');
  const mapDetector = () =>
    page.locator('.map-detector-panel [data-testid="detector-canvas"]');
  const intPattern = () =>
    page.locator('.integration-mode [data-testid="pattern-canvas"]');
  const intDetector = () =>
    page.locator('.integration-mode [data-testid="detector-canvas"]');
  await page.goto("file://" + root + "/dioptas/desktop/ui/index.html");
  await ready();
  const read = async (canvas) =>
    canvas.evaluate((el) =>
      Object.fromEntries(
        ["xMin", "xMax", "yMin", "yMax"].map((key) => [
          key,
          +el.dataset["view" + key[0].toUpperCase() + key.slice(1)],
        ]),
      ),
    );
  const same = (a, b, message, detector = false) => {
    close(a.xMin, b.xMin, message + " xMin");
    close(a.xMax, b.xMax, message + " xMax");
    if (detector)
      close((a.yMin + a.yMax) / 2, (b.yMin + b.yMax) / 2, message + " centerY");
    else {
      close(a.yMin, b.yMin, message + " yMin");
      close(a.yMax, b.yMax, message + " yMax");
    }
  };
  const drag = async (canvas, button = "left") => {
    const a = await plotPoint(canvas, 0.35, 0.35),
      b = await plotPoint(canvas, 0.65, 0.65);
    await page.mouse.move(a.x, a.y);
    await page.mouse.down({ button });
    await page.mouse.move(b.x, b.y, { steps: 8 });
    await page.mouse.up({ button });
    await ready();
  };
  const square = async (canvas) => {
    const r = await read(canvas),
      dims = await canvas.evaluate((el) => ({
        w: +el.dataset.plotWidth,
        h: +el.dataset.plotHeight,
      }));
    close(
      dims.w / (r.xMax - r.xMin),
      dims.h / (r.yMax - r.yMin),
      "Square detector pixels",
    );
  };
  const calibrationDetector = () =>
    page.locator('.calibration-mode [data-testid="detector-canvas"]');
  const calibrationPattern = () =>
    page.locator('.calibration-mode [data-testid="pattern-canvas"]');
  const maskDetector = () =>
    page.locator('.mask-view [data-testid="detector-canvas"]');
  await click("Integration");
  await drag(intDetector());
  await drag(intDetector(), "right");
  await drag(intPattern());
  await drag(intPattern(), "right");
  let detectorRange = await read(intDetector()),
    patternRange = await read(intPattern());
  await click("Map");
  same(await read(mapDetector()), detectorRange, "Int to Map detector", true);
  same(await read(mapPattern()), patternRange, "Int to Map pattern");
  await square(mapDetector());
  await page.getByRole("button", { name: "Edit windows", exact: true }).click();
  await drag(mapDetector(), "right");
  await drag(mapPattern(), "right");
  detectorRange = await read(mapDetector());
  patternRange = await read(mapPattern());
  await click("Calibration");
  same(
    await read(calibrationDetector()),
    detectorRange,
    "Map to Calibration",
    true,
  );
  await square(calibrationDetector());
  await page
    .getByRole("tab", { name: "Step 4: Validate", exact: true })
    .click();
  await ready();
  same(
    await read(calibrationPattern()),
    patternRange,
    "Map to Calibration pattern",
  );
  await click("Mask");
  same(await read(maskDetector()), detectorRange, "Calibration to Mask", true);
  await square(maskDetector());
  await drag(maskDetector(), "right");
  detectorRange = await read(maskDetector());
  await click("Integration");
  same(await read(intDetector()), detectorRange, "Mask to Int", true);
  await square(intDetector());
  same(
    await read(intPattern()),
    patternRange,
    "Calibration through Mask to Int pattern",
  );
  await click("Map");
  await click("Map pattern unit Q");
  let range = await read(mapPattern());
  close(range.xMin, q(patternRange.xMin), "Q viewport minimum");
  close(range.xMax, q(patternRange.xMax), "Q viewport maximum");
  await click("Logarithmic map pattern intensity");
  range = await read(mapPattern());
  close(range.yMin, Math.log10(patternRange.yMin), "Log viewport minimum");
  close(range.yMax, Math.log10(patternRange.yMax), "Log viewport maximum");
  await click("Square root map pattern intensity");
  range = await read(mapPattern());
  close(
    range.yMin,
    Math.sqrt(patternRange.yMin),
    "Square-root viewport minimum",
  );
  close(
    range.yMax,
    Math.sqrt(patternRange.yMax),
    "Square-root viewport maximum",
  );
  await click("Square root map pattern intensity");
  await click("Map pattern unit d");
  range = await read(mapPattern());
  close(range.xMin, d(patternRange.xMax), "d viewport minimum");
  close(range.xMax, d(patternRange.xMin), "d viewport maximum");
  await click("Integration");
  same(
    await read(intPattern()),
    patternRange,
    "Converted viewport returns to Int",
  );
  await page.setViewportSize({ width: 1200, height: 850 });
  await ready();
  await square(intDetector());
  await click("Map");
  await page.getByRole("tab", { name: "Image", exact: true }).click();
  await ready();
  await square(mapDetector());
  same(
    await read(mapDetector()),
    detectorRange,
    "Resize and mode switch",
    true,
  );
  const popup = page.waitForEvent("popup");
  await click("Detach map");
  const child = await popup;
  await child.getByTestId("scan-map").waitFor();
  await ready();
  same(await read(intDetector()), detectorRange, "Detach detector", true);
  await child.getByRole("button", { name: "Dock map", exact: true }).click();
  await ready();
  if (!(await mapDetector().count())) {
    await page.getByRole("tab", { name: "Image", exact: true }).click();
    await ready();
  }
  same(await read(mapDetector()), detectorRange, "Dock detector", true);
  const center = await plotPoint(mapDetector(), 0.5, 0.5);
  await page.mouse.click(center.x, center.y, {
    button: "right",
    clickCount: 2,
  });
  await ready();
  const fitted = await read(mapDetector());
  assert.ok(
    fitted.xMax - fitted.xMin > detectorRange.xMax - detectorRange.xMin,
  );
  await click("Mask");
  const maskFit = await read(maskDetector());
  assert.ok(maskFit.xMax - maskFit.xMin >= 981 - 1e-6);
  assert.ok(maskFit.yMax - maskFit.yMin >= 1043 - 1e-6);
  await square(maskDetector());
  await click("Integration");
  const p = await plotPoint(intPattern(), 0.5, 0.5);
  await page.mouse.click(p.x, p.y, { button: "right", clickCount: 2 });
  await ready();
  const patternFit = await read(intPattern());
  await click("Map");
  await click("Map pattern unit 2θ");
  same(await read(mapPattern()), patternFit, "Shared pattern fit reset");
  await click("Calibration");
  await drag(calibrationPattern());
  const calibrationZoom = await read(calibrationPattern());
  await click("Integration");
  same(
    await read(intPattern()),
    calibrationZoom,
    "Calibration zoom overrides previous Integration Auto range",
  );
  await drag(intDetector());
  await page.keyboard.press("f");
  await ready();
  const fFit = await read(intDetector());
  assert.ok(fFit.xMax - fFit.xMin >= 981 - 1e-6);
  assert.ok(fFit.yMax - fFit.yMin >= 1043 - 1e-6);
  assert.deepEqual(errors, []);
  await page.screenshot({ path: artifacts + "/shared-plot-viewport.png" });
  console.log(
    "Shared detector/pattern zoom and pan checks passed across Integration, Map, Calibration, and Mask",
  );
} catch (error) {
  if (page) {
    console.log((await page.locator("body").innerText()).slice(-1400));
    await page
      .screenshot({ path: artifacts + "/shared-plot-viewport-failure.png" })
      .catch(() => {});
  }
  throw error;
} finally {
  await browser?.close();
  host.stdin.end();
  await writeFile(artifacts + "/shared-plot-viewport.log", logs.join(""));
  if (fixtureDirectory)
    await rm(fixtureDirectory, { recursive: true, force: true });
}
