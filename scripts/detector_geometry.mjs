import assert from "node:assert/strict";
const settle = (page) =>
  page.evaluate(
    () =>
      new Promise((resolve) =>
        requestAnimationFrame(() => requestAnimationFrame(resolve)),
      ),
  );
const range = (canvas) =>
  canvas.evaluate((el) => ({
    xMin: +el.dataset.viewXMin,
    xMax: +el.dataset.viewXMax,
    yMin: +el.dataset.viewYMin,
    yMax: +el.dataset.viewYMax,
    left: +el.dataset.plotLeft,
    top: +el.dataset.plotTop,
    width: +el.dataset.plotWidth,
    height: +el.dataset.plotHeight,
    fullWidth: +el.dataset.fullWidth,
    fullHeight: +el.dataset.fullHeight,
  }));
export async function verifyDetectorGeometry(page, invoke) {
  const canvas = page.getByTestId("detector-canvas");
  const square = async () => {
    await settle(page);
    const draw = await page.evaluate(() => window.__detectorDraw);
    assert.ok(
      draw,
      "Observe actual canvas drawing, not only advertised viewport ranges",
    );
    assert.ok(
      Math.abs(draw.sx / draw.sy - 1) < 1e-7,
      `Resizing stretched pixels: ${JSON.stringify(draw)}`,
    );
    assert.ok(draw.flippedY, "Keep the existing detector orientation");
  };
  assert.deepEqual(
    await page.evaluate(() => window.__detectorLabels),
    [],
    "No detector axes, ticks or labels",
  );
  assert.equal(
    await page
      .locator(".detector-panel")
      .evaluate((el) => getComputedStyle(el).borderTopWidth),
    "0px",
  );
  for (const viewport of [
    { width: 1180, height: 860 },
    { width: 1620, height: 800 },
    { width: 1440, height: 1000 },
  ]) {
    await page.setViewportSize(viewport);
    await square();
  }
  let box = await canvas.boundingBox(),
    view = await range(canvas);
  await page.mouse.move(
    box.x + view.left + view.width * 0.28,
    box.y + view.top + view.height * 0.28,
  );
  await page.mouse.down();
  await page.mouse.move(
    box.x + view.left + view.width * 0.72,
    box.y + view.top + view.height * 0.72,
    { steps: 6 },
  );
  await page.mouse.up();
  await settle(page);
  const zoomed = await range(canvas),
    cx = (zoomed.xMin + zoomed.xMax) / 2,
    cy = (zoomed.yMin + zoomed.yMax) / 2;
  for (const viewport of [
    { width: 1024, height: 920 },
    { width: 1620, height: 800 },
    { width: 1180, height: 860 },
    { width: 1440, height: 1000 },
  ]) {
    await page.setViewportSize(viewport);
    await square();
    const resized = await range(canvas);
    assert.ok(
      Math.abs((resized.xMin + resized.xMax) / 2 - cx) < 1e-6 &&
        Math.abs((resized.yMin + resized.yMax) / 2 - cy) < 1e-6,
      "Resize preserves the selected image centre",
    );
  }
  box = await canvas.boundingBox();
  for (let i = 0; i < 4; i++) await page.mouse.wheel(0, -180);
  await settle(page);
  await page.mouse.dblclick(box.x + box.width / 2, box.y + box.height / 2, {
    button: "right",
  });
  await settle(page);
  view = await range(canvas);
  assert.ok(
    view.xMin <= 1e-6 &&
      view.yMin <= 1e-6 &&
      view.xMax >= view.fullWidth - 1e-6 &&
      view.yMax >= view.fullHeight - 1e-6,
    "Right double-click must restore the complete image from deep zoom",
  );
  await square();
  // Display rows increase downward. Internal scientific row values are untouched.
  for (const row of [10, view.fullHeight - 11]) {
    const sx = view.width / (view.xMax - view.xMin),
      sy = view.height / (view.yMax - view.yMin),
      column = 20;
    const internalY = view.fullHeight - row - 1;
    const expected = await invoke("pixel", { x: column, y: internalY });
    await page.mouse.move(
      box.x + view.left + (column + 0.5 - view.xMin) * sx,
      box.y + view.top + (view.yMax - internalY - 0.5) * sy,
    );
    await page.waitForFunction(
      ({ row, column }) => {
        const el = document.querySelector('[data-testid="mouse-readout"]');
        return +el.dataset.pixelRow === row && +el.dataset.pixelX === column;
      },
      { row, column },
    );
    await page.waitForFunction(
      (value) =>
        document
          .querySelector('[data-testid="mouse-readout"]')
          .innerText.endsWith(
            `I ${value.toLocaleString("en-US", { maximumFractionDigits: 3 })}`,
          ),
      expected.pixel.value,
    );
  }
  await page.mouse.move(10, 10);
  return [
    "axis-free detector with top-origin pixel readout; existing orientation retained",
    "square rendered pixels through fit/zoom/window resize",
    "right double-click fully restores image bounds",
  ];
}
