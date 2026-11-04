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
const errors = [],
  requests = [];
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
  await page.exposeFunction("__dioptasInvoke", async (action, payload) => {
    requests.push({ action, payload });
    return invoke(action, payload);
  });
  await page.addInitScript(() => {
    document.addEventListener(
      "pointerup",
      (event) => {
        const el = event.target;
        if (el.dataset?.testid !== "pattern-canvas") return;
        const box = el.getBoundingClientRect(),
          s = el.dataset;
        el.__clickedX =
          +s.viewXMin +
          ((event.clientX - box.x - +s.plotLeft) / +s.plotWidth) *
            (+s.viewXMax - +s.viewXMin);
      },
      true,
    );
    window.pywebview = {
      api: {
        invoke: async (a, p) => {
          if (a === "map_select")
            window.__selectionCount = (window.__selectionCount ?? 0) + 1;
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
  const clickPlot = async (canvas, fx, fy) => {
    const p = await plotPoint(canvas, fx, fy);
    await page.mouse.click(p.x, p.y);
    await ready();
  };
  const clickX = async (canvas, x) => {
    const range = await canvas.evaluate((el) => ({
      min: +el.dataset.viewXMin,
      max: +el.dataset.viewXMax,
    }));
    await clickPlot(canvas, (x - range.min) / (range.max - range.min), 0.45);
    return canvas.evaluate((el) => el.__clickedX);
  };
  const position = async (canvas) =>
    Number(await canvas.getAttribute("data-linked-position"));
  const green = async (canvas) => {
    await page.waitForFunction(
      (el) => {
        const { data } = el
          .getContext("2d")
          .getImageData(0, 0, el.width, el.height);
        let count = 0;
        for (let i = 0; i < data.length; i += 4)
          if (
            data[i] < 60 &&
            data[i + 1] > 180 &&
            data[i + 2] < 60 &&
            data[i + 3] > 40
          )
            count++;
        return count > 5;
      },
      await canvas.elementHandle(),
    );
  };
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
  await click("Integration");
  await clickPlot(intDetector(), 0.65, 0.55);
  const first = (await call("state")).linked;
  assert.ok(first?.contours.length);
  close(
    await position(intPattern()),
    first.twoTheta,
    "Integration detector to pattern",
  );
  await click("Map");
  close(
    await position(mapPattern()),
    first.twoTheta,
    "Integration to Map marker",
  );
  await green(mapPattern());
  await green(mapDetector());
  await clickPlot(mapDetector(), 0.25, 0.6);
  const second = (await call("state")).linked;
  close(
    await position(mapPattern()),
    second.twoTheta,
    "Map detector to pattern",
  );
  assert.notEqual(second.twoTheta, first.twoTheta);
  const detectorReading = (
    await page.getByTestId("click-readout").innerText()
  ).split("χ")[0];
  const options = () =>
    page.getByRole("listbox", { name: "Scan arrangement" }).getByRole("option");
  await options().nth(1).click();
  await ready();
  let selected = await call("state");
  assert.equal(selected.map.selected, 1);
  assert.equal(selected.state.imagePath, paths[1]);
  close(
    selected.linked.twoTheta,
    second.twoTheta,
    "Detector click survives a new image",
  );
  close(selected.linked.azimuth, second.azimuth, "Clicked azimuth retained");
  assert.equal(
    (await page.getByTestId("click-readout").innerText()).split("χ")[0],
    detectorReading,
  );
  close(
    await position(mapPattern()),
    second.twoTheta,
    "Marker survives a map point change",
  );
  await green(mapDetector());
  await green(mapPattern());
  await click("Integration");
  close(
    await position(intPattern()),
    second.twoTheta,
    "Map to Integration marker",
  );
  await green(intPattern());
  await green(intDetector());
  await click("Map");
  // Clicking inside an editable ROI still inspects, without changing the window.
  const before = (await call("state")).map.rois[0];
  await clickX(mapPattern(), 12);
  close(
    (await call("state")).linked.twoTheta,
    12,
    "Map pattern to detector",
    0.08,
  );
  await green(mapDetector());
  const after = (await call("state")).map.rois[0];
  close(after.min, before.min, "ROI minimum retained");
  close(after.max, before.max, "ROI maximum retained");
  await click("Map pattern unit Q");
  close(
    await position(mapPattern()),
    q((await call("state")).linked.twoTheta),
    "Map Q marker",
  );
  await clickX(mapPattern(), q(12.5));
  close(
    (await call("state")).linked.twoTheta,
    12.5,
    "Map Q click physical angle",
    0.08,
  );
  await click("Map pattern unit d");
  close(
    await position(mapPattern()),
    d((await call("state")).linked.twoTheta),
    "Map d marker",
  );
  const patternReading = (await page.getByTestId("click-readout").innerText()).split("χ")[0];
  const patternAngle = (await call("state")).linked.twoTheta;
  // Queue rapid selections to verify each restored contour belongs to the final image.
  await options().evaluateAll((rows) => {
    rows[2].click();
    rows[3].click();
  });
  await ready();
  selected = await call("state");
  assert.equal(selected.map.selected, 3);
  assert.equal(selected.state.imagePath, paths[3]);
  close(
    selected.linked.twoTheta,
    patternAngle,
    "Pattern click survives queued map selections",
  );
  close(
    await position(mapPattern()),
    d(patternAngle),
    "d marker retained on another point",
  );
  assert.equal(
    (await page.getByTestId("click-readout").innerText()).split("χ")[0],
    patternReading,
  );
  // A real ROI drag edits only the window; it must not move the inspection marker.
  const old = (await call("state")).linked.twoTheta;
  const count = requests.filter(
    (r) => r.action === "validation_position",
  ).length;
  const range = await mapPattern().evaluate((el) => ({
    min: +el.dataset.viewXMin,
    max: +el.dataset.viewXMax,
  }));
  const center = (d(8) + d(18)) / 2;
  const p = await plotPoint(
    mapPattern(),
    (center - range.min) / (range.max - range.min),
    0.45,
  );
  await page.mouse.move(p.x, p.y);
  await page.mouse.down();
  await page.mouse.move(p.x + 15, p.y, { steps: 6 });
  await page.mouse.up();
  await ready();
  assert.equal(
    requests.filter((r) => r.action === "validation_position").length,
    count,
  );
  close(
    (await call("state")).linked.twoTheta,
    old,
    "ROI drag preserves inspection",
  );
  await click("Integration");
  await click("Pattern unit Q");
  await click("Map");
  await click("Map pattern unit d");
  // WebKit quantizes synthetic pointer coordinates. On a wide d axis,
  // compare the physical angle with the actual dispatched position.
  const clickedD = await clickX(mapPattern(), d(13));
  close(
    (await call("state")).linked.twoTheta,
    (360 / Math.PI) * Math.asin(lambda / (2 * clickedD)),
    "Map d click with Integration in Q",
  );
  await click("Integration");
  const marked = (await call("state")).linked;
  close(
    await position(intPattern()),
    q(marked.twoTheta),
    "Shared marker after Integration unit change",
  );
  const reading = await page.getByTestId("click-readout").innerText();
  assert.ok(
    reading.includes("2θ") && reading.includes("Q") && reading.includes("d"),
    reading,
  );
  await click("Map");
  const popup = page.waitForEvent("popup");
  await page.getByRole("button", { name: "Detach map", exact: true }).click();
  const child = await popup;
  await child.locator('[data-testid="scan-map"] canvas').first().waitFor();
  await ready();
  close(
    await position(intPattern()),
    q(marked.twoTheta),
    "Detach retains marker",
  );
  const childCanvas = child.locator(
    '[data-testid="scan-map"] [data-testid="detector-canvas"]',
  );
  const cell = await plotPoint(childCanvas, 0.25, 0.25);
  const priorSelections = await page.evaluate(
    () => window.__selectionCount ?? 0,
  );
  await child.mouse.click(cell.x, cell.y);
  await page.waitForFunction(
    (before) => window.__selectionCount > before,
    priorSelections,
  );
  await ready();
  selected = await call("state");
  assert.notEqual(
    selected.map.selected,
    3,
    "Detached map selects another image",
  );
  close(
    selected.linked.twoTheta,
    marked.twoTheta,
    "Detached selection retains marker",
  );
  close(
    selected.linked.azimuth,
    marked.azimuth,
    "Detached selection retains azimuth",
  );
  close(
    await position(intPattern()),
    q(marked.twoTheta),
    "Integration keeps marker after detached map selection",
  );
  await child.getByRole("button", { name: "Dock map", exact: true }).click();
  await ready();
  close(
    await position(mapPattern()),
    q(marked.twoTheta),
    "Dock retains marker",
  );
  await green(mapPattern());
  await green(mapDetector());
  await page.screenshot({ path: artifacts + "/map-linked-position.png" });
  await click("Integration");
  await page.getByRole("tab", { name: "Image", exact: true }).click();
  await page.getByLabel("Image filename", { exact: true }).fill(image);
  await page.getByLabel("Image filename", { exact: true }).press("Enter");
  await ready();
  assert.equal(
    (await call("state")).linked,
    null,
    "Unrelated image loading still clears the old position",
  );
  assert.equal(await page.getByTestId("click-readout").innerText(), "—");
  assert.equal(await intPattern().getAttribute("data-linked-position"), null);
  assert.deepEqual(errors, []);
  await writeFile(
    artifacts + "/map-linked-position.json",
    JSON.stringify(
      {
        ok: true,
        sharedDetectorPattern: true,
        modeSwitch: true,
        pointSelection: true,
        clickedReadoutRetained: true,
        radialUnits: true,
        roiClickAndDrag: true,
        detached: true,
        errors,
      },
      null,
      2,
    ),
  );
  console.log(
    "Linked Map/Integration detector and pattern position checks passed",
  );
} catch (error) {
  if (page) {
    console.log((await page.locator("body").innerText()).slice(-1800));
    await page
      .screenshot({ path: artifacts + "/map-linked-position-failure.png" })
      .catch(() => {});
  }
  throw error;
} finally {
  await browser?.close();
  host.stdin.end();
  await writeFile(artifacts + "/map-linked-position.log", logs.join(""));
  if (fixtureDirectory)
    await rm(fixtureDirectory, { recursive: true, force: true });
}
