import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { createInterface } from "node:readline";
import { mkdir } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { chromium, webkit } from "playwright";
import { selectIntegrationDisplay } from "./integration_display.mjs";
import { setInterfaceTextSize } from "./plot_navigation.mjs";

const root = fileURLToPath(new URL("../../", import.meta.url));
const host = spawn(
  `${root}/.venv/bin/python`,
  ["-u", "desktop/scripts/bridge_host.py"],
  { cwd: root, stdio: ["pipe", "pipe", "pipe"] },
);
let next = 0;
const pending = new Map();
const diagnostics = [];
host.stderr.on("data", (data) => diagnostics.push(String(data)));
createInterface({ input: host.stdout }).on("line", (line) => {
  const { id, result } = JSON.parse(line);
  const task = pending.get(id);
  if (task) {
    clearTimeout(task.timer);
    pending.delete(id);
    task.resolve(result);
  }
});
const invoke = (action, payload = {}) =>
  new Promise((resolve, reject) => {
    const id = ++next;
    const timer = setTimeout(() => {
      pending.delete(id);
      reject(Error(`Timeout: ${action}`));
    }, 45000);
    pending.set(id, { resolve, timer });
    host.stdin.write(JSON.stringify({ id, action, payload }) + "\n");
  });
const browser = await (
  process.argv.includes("--webkit") ? webkit : chromium
).launch({ headless: true });
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
const errors = [];
page.on("pageerror", (error) => errors.push(error.message));
await page.exposeFunction("__dioptasInvoke", invoke);
await page.addInitScript(() => {
  document.addEventListener("pointermove", (event) => {
    window.__pointer = [event.clientX, event.clientY];
  });
  window.pywebview = {
    api: {
      invoke: (command, payload) => window.__dioptasInvoke(command, payload),
    },
  };
});
const ready = async () => {
  await page.waitForFunction(() => !document.querySelector(".spin"));
  assert.deepEqual(await page.getByRole("alert").allTextContents(), []);
};
const values = () =>
  page
    .getByTestId("mouse-readout")
    .evaluate((el) =>
      ["q_A^-1", "y", "I"].map(
        (key) =>
          el.querySelector(
            `[data-unit="${key}"] .plot-coordinate-value, [data-field="${key}"] .plot-coordinate-value`,
          )?.textContent,
      ),
    );
const parse = (value) => Number(value.replaceAll(",", ""));
const near = (actual, expected, tolerance = 0.002) =>
  assert.ok(Math.abs(actual - expected) < tolerance, `${actual} ≠ ${expected}`);
async function radialReading(locator, angle, wavelength) {
  const q =
    (4 * Math.PI * Math.sin((angle * Math.PI) / 360)) / (wavelength * 1e10);
  for (const [unit, expected] of [
    ["2th_deg", angle],
    ["q_A^-1", q],
    ["d_A", (2 * Math.PI) / q],
  ]) {
    const text = await locator
      .locator(`[data-unit="${unit}"] .plot-coordinate-value`)
      .innerText();
    near(parse(text), expected, Math.max(0.011, Math.abs(expected) * 0.003));
  }
}
async function at(canvas, x, y) {
  return canvas.evaluate(
    (el, [x, y]) => {
      const d = el.dataset,
        b = el.getBoundingClientRect();
      return {
        x: b.x + +d.plotLeft + x * +d.plotWidth,
        y: b.y + +d.plotTop + y * +d.plotHeight,
      };
    },
    [x, y],
  );
}
async function move(canvas, x, y) {
  const p = await at(canvas, x, y);
  await page.mouse.move(p.x, p.y);
  await page.waitForTimeout(160);
  return p;
}
async function marker(canvas) {
  await canvas.evaluate(
    (el) =>
      new Promise((resolve) =>
        requestAnimationFrame(() => requestAnimationFrame(resolve)),
      ),
  );
  const point = await canvas.evaluate((el) => {
    const d = el.dataset,
      ctx = el.getContext("2d");
    const x =
      +d.plotLeft +
      ((+d.clickX - +d.viewXMin) / (+d.viewXMax - +d.viewXMin)) * +d.plotWidth;
    const y =
      +d.plotTop +
      ((+d.viewYMax - +d.clickY) / (+d.viewYMax - +d.viewYMin)) * +d.plotHeight;
    const pixels = ctx.getImageData(
      Math.round(x) - 9,
      Math.round(y) - 9,
      19,
      19,
    ).data;
    let green = 0;
    for (let i = 0; i < pixels.length; i += 4)
      if (pixels[i] < 90 && pixels[i + 1] > 170 && pixels[i + 2] < 90) green++;
    return { x: +d.clickX, y: +d.clickY, green };
  });
  assert.ok(Number.isFinite(point.x) && Number.isFinite(point.y));
  assert.ok(
    point.green >= 10,
    `Cross must be painted green: ${JSON.stringify(point)}`,
  );
  return point;
}
try {
  assert.equal((await invoke("example")).ok, true);
  assert.equal(
    (
      await invoke("open_calibration", {
        path: `${root}/dioptas/tests/data/CeO2_Pilatus1M.poni`,
      })
    ).ok,
    true,
  );
  await page.goto(`file://${root}/dioptas/desktop/ui/index.html`);
  await ready();
  assert.equal(await page.getByTestId("click-readout").count(), 0);
  await page.getByRole("button", { name: "Integration", exact: true }).click();
  await ready();
  await selectIntegrationDisplay(page, "image");
  const detector = page.getByTestId("detector-canvas");
  const imagePos = await move(detector, 0.6, 0.45);
  await page.waitForFunction(
    () =>
      document.querySelector('[data-testid="mouse-readout"]').dataset.plot ===
      "detector",
  );
  assert.equal(await page.locator(".plot-status-source").count(), 0);
  const snapshot = await invoke("state");
  const wavelength = snapshot.state.geometry.wavelength;
  const sampled = await page
    .getByTestId("mouse-readout")
    .evaluate((el) => ({ x: +el.dataset.pixelX, y: +el.dataset.pixelRow }));
  const pixel = (
    await invoke("pixel", {
      x: sampled.x,
      y: snapshot.image.fullHeight - 1 - sampled.y,
    })
  ).pixel;
  await radialReading(
    page.getByTestId("mouse-readout"),
    pixel.twoTheta,
    wavelength,
  );
  await page.mouse.click(imagePos.x, imagePos.y);
  await ready();
  await radialReading(
    page.getByTestId("click-readout"),
    (await invoke("state")).linked.twoTheta,
    wavelength,
  );
  const clickColour = await page
    .getByTestId("click-readout")
    .evaluate((el) => getComputedStyle(el).color.match(/\d+/g).map(Number));
  assert.ok(
    clickColour[1] > clickColour[0] && clickColour[1] > clickColour[2],
    "The clicked reading must be green",
  );
  const imageMarker = await marker(detector);
  const clickText = await page.getByTestId("click-readout").innerText();
  await move(detector, 0.4, 0.7);
  assert.equal(await page.getByTestId("click-readout").innerText(), clickText);
  await selectIntegrationDisplay(page, "cake");
  const cake = page.getByTestId("cake-canvas");
  await marker(cake);
  await page
    .getByLabel("Cake azimuth shift", { exact: true })
    .evaluate((el) => {
      Object.getOwnPropertyDescriptor(
        HTMLInputElement.prototype,
        "value",
      ).set.call(el, "90");
      el.dispatchEvent(new Event("input", { bubbles: true }));
    });
  await page.waitForFunction(
    () =>
      +document.querySelector('[data-testid="cake-canvas"]').dataset
        .azimuthMin < -200,
  );
  await marker(cake);
  const cakePos = await move(cake, 0.37, 0.44);
  await page.mouse.click(cakePos.x, cakePos.y);
  await ready();
  const selected = (await invoke("state")).linked;
  assert.ok(selected.imagePoint);
  await marker(cake);
  await selectIntegrationDisplay(page, "image");
  const projected = await marker(detector);
  near(projected.x, selected.imagePoint.x);
  near(projected.y, selected.imagePoint.y);
  assert.notEqual(projected.x, imageMarker.x);
  const radial = selected.radial;
  await page
    .getByRole("button", { name: "Pattern unit Q", exact: true })
    .click();
  await ready();
  const pattern = page.getByTestId("pattern-canvas");
  assert.notEqual(
    Number(await pattern.getAttribute("data-linked-position")),
    radial,
  );
  await marker(detector);
  for (const scale of ["linear", "log", "sqrt"]) {
    if (scale === "log")
      await page
        .getByRole("button", {
          name: "Logarithmic pattern intensity",
          exact: true,
        })
        .click();
    if (scale === "sqrt")
      await page
        .getByRole("button", {
          name: "Square root pattern intensity",
          exact: true,
        })
        .click();
    await move(pattern, 0.371, 0.25);
    const first = (await values()).map(parse);
    const bounds = await pattern.evaluate((el) => ({
      x0: +el.dataset.viewXMin,
      x1: +el.dataset.viewXMax,
      y0: +el.dataset.viewYMin,
      y1: +el.dataset.viewYMax,
      width: +el.dataset.plotWidth,
      height: +el.dataset.plotHeight,
      fx:
        (window.__pointer[0] -
          el.getBoundingClientRect().x -
          +el.dataset.plotLeft) /
        +el.dataset.plotWidth,
      fy:
        (window.__pointer[1] -
          el.getBoundingClientRect().y -
          +el.dataset.plotTop) /
        +el.dataset.plotHeight,
    }));
    const trueQ = bounds.x0 + bounds.fx * (bounds.x1 - bounds.x0);
    const angle =
      (Math.asin((trueQ * wavelength * 1e10) / (4 * Math.PI)) * 360) / Math.PI;
    await radialReading(page.getByTestId("mouse-readout"), angle, wavelength);
    near(
      first[0],
      bounds.x0 + bounds.fx * (bounds.x1 - bounds.x0),
      (bounds.x1 - bounds.x0) / bounds.width,
    );
    const y = bounds.y1 - bounds.fy * (bounds.y1 - bounds.y0);
    const expectedY = scale === "log" ? 10 ** y : scale === "sqrt" ? y ** 2 : y;
    const inverse = (value) =>
      scale === "log"
        ? 10 ** value
        : scale === "sqrt"
          ? Math.max(0, value) ** 2
          : value;
    const yStep = Math.abs(
      inverse(y + (bounds.y1 - bounds.y0) / bounds.height) - expectedY,
    );
    near(first[1], expectedY, yStep);
    if (scale === "linear" && yStep >= 1)
      assert.ok(
        Number.isInteger(first[1]),
        "A broad intensity range must show integer mouse y, without false decimal precision",
      );
    const columns = await page
      .getByTestId("mouse-readout")
      .locator(".plot-coordinate-value")
      .evaluateAll((els) => els.map((el) => el.getBoundingClientRect().x));
    const p = await move(pattern, 0.371, 0.75);
    const second = (await values()).map(parse);
    near(second[0], first[0]);
    near(second[2], first[2]);
    assert.notEqual(
      second[1],
      first[1],
      "Vertical motion must report mouse y independently of the curve",
    );
    assert.deepEqual(
      await page
        .getByTestId("mouse-readout")
        .locator(".plot-coordinate-value")
        .evaluateAll((els) => els.map((el) => el.getBoundingClientRect().x)),
      columns,
    );
    await page.mouse.click(p.x, p.y);
    await ready();
    assert.equal(
      await page.getByTestId("click-readout").getAttribute("data-plot"),
      "pattern",
    );
  }
  await page
    .getByRole("button", { name: "Square root pattern intensity", exact: true })
    .click();
  for (const [label, unit] of [
    ["2θ", "2th_deg"],
    ["Q", "q_A^-1"],
    ["d", "d_A"],
  ]) {
    await page
      .getByRole("button", { name: `Pattern unit ${label}`, exact: true })
      .click();
    await ready();
    const point = await move(pattern, 0.4, 0.5);
    const x = await pattern.evaluate((el) => {
      const d = el.dataset;
      const fraction =
        (window.__pointer[0] - el.getBoundingClientRect().x - +d.plotLeft) /
        +d.plotWidth;
      return +d.viewXMin + fraction * (+d.viewXMax - +d.viewXMin);
    });
    const angle =
      unit === "2th_deg"
        ? x
        : unit === "q_A^-1"
          ? (Math.asin((x * wavelength * 1e10) / (4 * Math.PI)) * 360) / Math.PI
          : (Math.asin((wavelength * 1e10) / (2 * x)) * 360) / Math.PI;
    await radialReading(page.getByTestId("mouse-readout"), angle, wavelength);
    await page.mouse.click(point.x, point.y);
    await ready();
    await radialReading(page.getByTestId("click-readout"), angle, wavelength);
  }
  await page
    .getByRole("button", { name: "Pattern unit 2θ", exact: true })
    .click();
  await ready();
  for (const [width, large] of [
    [1440, false],
    [1000, false],
    [1000, true],
  ]) {
    await setInterfaceTextSize(page, large);
    await page.setViewportSize({ width, height: 760 });
    await move(pattern, 0.6, 0.5);
    const layout = await page.locator(".plot-status").evaluate((el) => {
      const footer = el.closest("footer").getBoundingClientRect();
      if (footer.height !== 32) return false;
      const rows = [...el.querySelectorAll(".plot-status-line")].map((row) =>
        row.getBoundingClientRect(),
      );
      return (
        rows.every(
          (row) =>
            row.top >= footer.top &&
            row.bottom <= footer.bottom &&
            row.right <= footer.right,
        ) &&
        [...el.querySelectorAll(".plot-status-reading")].every(
          (reading) => reading.scrollWidth <= reading.clientWidth + 1,
        )
      );
    });
    assert.equal(
      layout,
      true,
      "Mouse and Click readings must fit on one footer line",
    );
    await mkdir(`${root}/desktop/artifacts`, { recursive: true });
    await page.screenshot({
      path: `${root}/desktop/artifacts/position-readout-${width}${large ? "-large" : ""}.png`,
    });
    await move(detector, 0.6, 0.5);
    const detectorLayout = await page.locator(".plot-status").evaluate((el) => {
      const right = el.closest("footer").getBoundingClientRect().right;
      return (
        [...el.querySelectorAll(".plot-status-line")].every(
          (row) => row.getBoundingClientRect().right <= right,
        ) &&
        [...el.querySelectorAll(".plot-status-reading")].every(
          (reading) => reading.scrollWidth <= reading.clientWidth + 1,
        )
      );
    });
    assert.equal(
      detectorLayout,
      true,
      "Detector x/y/I and all radial units must fit beside the clicked values",
    );
  }
  for (const mode of ["Calibration", "Mask"]) {
    await page.getByRole("button", { name: mode, exact: true }).click();
    await ready();
    assert.equal(await page.getByTestId("click-readout").count(), 0);
    assert.equal(
      await page.getByTestId("detector-canvas").getAttribute("data-click-x"),
      null,
    );
  }
  assert.deepEqual(errors, []);
  console.log(
    "PASS: simultaneous 2θ/Q/d for hover and green clicked positions in every radial unit; calibrated detector geometry; fixed columns; scale-aware precision; linked crosses and shifted cake; one-line footer at both text sizes; no click UI in Calibration/Mask.",
  );
} catch (error) {
  await page.screenshot({
    path: `${root}/desktop/artifacts/position-readout-failure.png`,
  });
  console.error(diagnostics.join("").slice(-2000));
  throw error;
} finally {
  await browser.close();
  host.stdin.end();
  await new Promise((resolve) => host.once("exit", resolve));
}
