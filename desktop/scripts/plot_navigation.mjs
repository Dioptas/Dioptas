import assert from "node:assert/strict";

export async function setInterfaceTextSize(page, large) {
  await page.getByRole("button", { name: "Settings", exact: true }).click();
  await page
    .getByRole("button", { name: large ? "Larger" : "Standard", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Close settings", exact: true })
    .click();
}

const settle = (page) =>
  page.evaluate(
    () =>
      new Promise((resolve) =>
        requestAnimationFrame(() => requestAnimationFrame(resolve)),
      ),
  );
const read = (canvas) =>
  canvas.evaluate((el) => ({
    xMin: Number(el.dataset.viewXMin),
    xMax: Number(el.dataset.viewXMax),
    yMin: Number(el.dataset.viewYMin),
    yMax: Number(el.dataset.viewYMax),
  }));
const spanX = (view) => view.xMax - view.xMin;
const spanY = (view) => view.yMax - view.yMin;
const close = (actual, expected, message) =>
  assert.ok(
    Math.abs(actual - expected) < Math.max(1e-7, Math.abs(expected) * 1e-7),
    `${message}: ${actual} vs ${expected}`,
  );
async function point(canvas, fx, fy) {
  const box = await canvas.boundingBox();
  const bounds = await canvas.evaluate((el) => ({
    left: +el.dataset.plotLeft,
    top: +el.dataset.plotTop,
    width: +el.dataset.plotWidth,
    height: +el.dataset.plotHeight,
  }));
  return {
    x: box.x + bounds.left + bounds.width * fx,
    y: box.y + bounds.top + bounds.height * fy,
  };
}
async function drag(page, canvas, from, to, button = "left") {
  const a = await point(canvas, ...from),
    b = await point(canvas, ...to);
  await page.mouse.move(a.x, a.y);
  await page.mouse.down({ button });
  await page.mouse.move(b.x, b.y, { steps: 8 });
  await page.mouse.up({ button });
  await settle(page);
}
async function restore(page, canvas) {
  const p = await point(canvas, 0.5, 0.5);
  for (let i = 0; i < 10; i++)
    await page.mouse.click(p.x, p.y, { button: "right" });
  await settle(page);
}

export async function verifyPlotNavigation(page) {
  const checks = [];
  const pattern = page.getByTestId("pattern-canvas");
  await page.getByRole("button", { name: "Settings", exact: true }).click();
  assert.equal(
    await page.getByLabel("Pattern zoom mode", { exact: true }).inputValue(),
    "horizontal",
  );
  await page
    .getByRole("button", { name: "Close settings", exact: true })
    .click();
  const patternFit = await read(pattern);
  // Preserve the original horizontal drag, including a perfectly flat gesture.
  await drag(page, pattern, [0.25, 0.65], [0.75, 0.65]);
  const horizontal = await read(pattern);
  assert.ok(
    spanX(horizontal) < spanX(patternFit) * 0.6,
    "Horizontal pattern drag zooms x without requiring a vertical movement",
  );
  assert.ok(
    spanY(horizontal) <= spanY(patternFit) * 1.01,
    "Horizontal pattern zoom keeps automatic intensity scaling",
  );
  await restore(page, pattern);
  checks.push("pattern horizontal zoom remains the default");

  for (const [id, label] of [
    ["detector-canvas", "Detector zoom mode"],
    ["cake-canvas", "Cake zoom mode"],
    ["pattern-canvas", "Pattern zoom mode"],
  ]) {
    if (await page.locator(".integration-layout").count())
      await page
        .getByRole("group", { name: "Integration display", exact: true })
        .getByRole("button", {
          name: id === "cake-canvas" ? "Cake" : "Image",
          exact: true,
        })
        .click();
    if (id === "pattern-canvas") {
      await page.getByRole("button", { name: "Settings", exact: true }).click();
      await page.getByLabel(label, { exact: true }).selectOption("rectangle");
      await page
        .getByRole("button", { name: "Close settings", exact: true })
        .click();
    } else
      assert.equal(await page.getByLabel(label, { exact: true }).count(), 0);

    const canvas = page.getByTestId(id);
    await canvas.scrollIntoViewIfNeeded();
    await settle(page);
    assert.equal(await canvas.getAttribute("data-zoom-mode"), "rectangle");
    const fit = await read(canvas);
    for (let i = 0; i < 4; i++)
      await drag(
        page,
        canvas,
        i % 2 ? [0.75, 0.75] : [0.25, 0.25],
        i % 2 ? [0.25, 0.25] : [0.75, 0.75],
      );
    const zoomed = await read(canvas);
    assert.ok(
      spanX(zoomed) < spanX(fit) / 10,
      `${id}: repeated rectangle zoom changes the visible x range`,
    );
    assert.ok(
      spanY(zoomed) < spanY(fit) / 10,
      `${id}: rectangle zoom changes the visible y range`,
    );
    await drag(page, canvas, [0.45, 0.45], [0.55, 0.55], "right");
    const panned = await read(canvas);
    close(spanX(panned), spanX(zoomed), `${id}: right-drag preserves x scale`);
    close(spanY(panned), spanY(zoomed), `${id}: right-drag preserves y scale`);
    assert.ok(
      panned.xMin < zoomed.xMin && panned.yMin > zoomed.yMin,
      `${id}: right-drag translates both axes`,
    );
    const p = await point(canvas, 0.5, 0.5);
    await page.mouse.click(p.x, p.y, { button: "right" });
    await settle(page);
    const single = await read(canvas);
    close(
      spanX(single),
      spanX(panned) * 2,
      `${id}: right-click zooms out once`,
    );
    close(
      spanY(single),
      spanY(panned) * 2,
      `${id}: right-click zooms out once on y`,
    );
    await page.mouse.dblclick(p.x, p.y, { button: "right" });
    await settle(page);
    const twice = await read(canvas);
    close(
      spanX(twice),
      spanX(fit),
      `${id}: right-double-click restores the complete fitted range`,
    );
    await restore(page, canvas);
    const restored = await read(canvas);
    close(restored.xMin, fit.xMin, `${id}: zoom-out returns to fitted x range`);
    close(restored.yMax, fit.yMax, `${id}: zoom-out returns to fitted y range`);
    checks.push(
      `${id}: rectangle zoom, right pan, single unzoom / double full fit`,
    );
  }
  await page.getByRole("button", { name: "Settings", exact: true }).click();
  await page
    .getByLabel("Pattern zoom mode", { exact: true })
    .selectOption("horizontal");
  await page
    .getByRole("button", { name: "Close settings", exact: true })
    .click();
  // Right navigation remains available in the peak-picking tool and never picks.
  const sidebar = await page.locator(".sidebar").boundingBox();
  const main = await page.locator(".workspace-content").boundingBox();
  const modes = await page
    .getByRole("navigation", { name: "Workspace modes" })
    .boundingBox();
  assert.ok(
    modes.x < main.x && main.x < sidebar.x,
    "Mode navigation is left; experiment options are right",
  );
  checks.push("Dioptas left navigation / right options layout");
  return checks;
}

export async function verifyCalibrationNavigation(page) {
  const canvas = page.getByTestId("detector-canvas");
  const initial = await read(canvas);
  // Peak picking remains active: only a stationary left click selects peaks.
  await drag(page, canvas, [0.3, 0.3], [0.7, 0.7]);
  assert.ok(spanX(await read(canvas)) < spanX(initial) * 0.5);
  await drag(page, canvas, [0.4, 0.4], [0.5, 0.5], "right");
  await restore(page, canvas);
  close(
    spanX(await read(canvas)),
    spanX(initial),
    "Calibration zoom returns to fit",
  );
}
