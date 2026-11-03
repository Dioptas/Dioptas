import assert from "node:assert/strict";

/** Real-model ROI editing uses source pixels, including after plot navigation. */
export async function verifyIntegrationRoi(page, invoke, waitReady) {
  const canvas = page.getByTestId("detector-canvas");
  await canvas.evaluate((el) => {
    if (el.__roiPointerTracking) return;
    el.__roiPointerTracking = true;
    el.addEventListener("pointerdown", (event) => {
      el.__roiPointerStart = { x: event.clientX, y: event.clientY };
    });
    el.addEventListener("pointermove", (event) => {
      el.__roiPointerEnd = { x: event.clientX, y: event.clientY };
    });
  });
  const settle = () =>
    page.evaluate(
      () =>
        new Promise((resolve) =>
          requestAnimationFrame(() => requestAnimationFrame(resolve)),
        ),
    );
  const snapshot = () => invoke("state");
  const geometry = () =>
    canvas.evaluate((el) => {
      const d = el.dataset,
        b = el.getBoundingClientRect();
      const sx = +d.plotWidth / (+d.viewXMax - +d.viewXMin);
      const sy = +d.plotHeight / (+d.viewYMax - +d.viewYMin);
      return {
        sx,
        sy,
        ox: b.left + +d.plotLeft - +d.viewXMin * sx,
        yBase: b.top + +d.plotTop + +d.viewYMax * sy,
      };
    });
  const shown = () =>
    canvas
      .getAttribute("data-roi")
      .then((value) => value.split(",").map(Number));
  const range = () =>
    canvas.evaluate((el) => [
      el.dataset.viewXMin,
      el.dataset.viewXMax,
      el.dataset.viewYMin,
      el.dataset.viewYMax,
    ]);
  const point = (roi, g, x, y) => ({
    x: g.ox + (roi[2] + (roi[3] - roi[2]) * x) * g.sx,
    y: g.yBase - (roi[1] - (roi[1] - roi[0]) * y) * g.sy,
  });
  const cases = [
    ["move", 0.5, 0.5],
    ["nw", 0, 0],
    ["ne", 1, 0],
    ["sw", 0, 1],
    ["se", 1, 1],
    ["n", 0.5, 0],
    ["s", 0.5, 1],
    ["w", 0, 0.5],
    ["e", 1, 0.5],
    ["e", 1, 0.3], // Grab an edge away from its midpoint handle.
  ];
  async function edit(target, x, y) {
    const before = (await snapshot()).state.integration.roi;
    const g = await geometry(),
      p = point(before, g, x, y);
    const view = await range();
    await page.mouse.move(p.x, p.y);
    assert.equal(
      await canvas.evaluate((el) => getComputedStyle(el).cursor),
      target === "move"
        ? "grab"
        : target === "w" || target === "e"
          ? "ew-resize"
          : target === "n" || target === "s"
            ? "ns-resize"
            : target === "nw" || target === "se"
              ? "nwse-resize"
              : "nesw-resize",
    );
    await page.mouse.down();
    await page.mouse.move(p.x + 9 * g.sx, p.y + 13 * g.sy, { steps: 4 });
    await settle();
    // WebKit rounds synthetic pointer positions to screen pixels. Validate the
    // actual dispatched motion rather than the automation's fractional request.
    const motion = await canvas.evaluate((el) => ({
      x: el.__roiPointerEnd.x - el.__roiPointerStart.x,
      y: el.__roiPointerEnd.y - el.__roiPointerStart.y,
    }));
    const next = [...before],
      dx = Math.round(motion.x / g.sx),
      dy = Math.round(-motion.y / g.sy);
    if (target === "move") {
      next[0] += dy;
      next[1] += dy;
      next[2] += dx;
      next[3] += dx;
    } else {
      if (target.includes("w")) next[2] += dx;
      if (target.includes("e")) next[3] += dx;
      if (target.includes("n")) next[1] += dy;
      if (target.includes("s")) next[0] += dy;
    }

    assert.deepEqual(await shown(), next, `${target}: live pixel preview`);
    assert.deepEqual(
      (await snapshot()).state.integration.roi,
      before,
      `${target}: defer scientific integration until release`,
    );
    await page.mouse.up();
    await waitReady();
    await settle();
    assert.deepEqual(
      (await snapshot()).state.integration.roi,
      next,
      `${target}: committed source coordinates`,
    );
    assert.deepEqual(
      await range(),
      view,
      `${target}: resizing does not zoom the detector`,
    );
  }
  for (const entry of cases) await edit(...entry);

  // Escape and pointer cancellation restore the last committed region.
  for (const cancel of ["escape", "pointercancel"]) {
    const before = (await snapshot()).state.integration.roi;
    const g = await geometry(),
      p = point(before, g, 0.5, 0.5);
    await page.mouse.move(p.x, p.y);
    await page.mouse.down();
    await page.mouse.move(p.x + 14, p.y + 12);
    if (cancel === "escape") await page.keyboard.press("Escape");
    else await canvas.dispatchEvent("pointercancel", { pointerId: 1 });
    await page.mouse.up();
    await settle();
    assert.deepEqual(await shown(), before, `${cancel}: preview restored`);
    assert.deepEqual(
      (await snapshot()).state.integration.roi,
      before,
      `${cancel}: no model edit`,
    );
  }
  // Wheel zoom and right pan still work over the active ROI.
  let before = (await snapshot()).state.integration.roi;
  let g = await geometry(),
    p = point(before, g, 0.5, 0.5);
  const initialRange = await range();
  await page.mouse.move(p.x, p.y);
  await page.mouse.wheel(0, -80);
  await settle();
  assert.notDeepEqual(
    await range(),
    initialRange,
    "Wheel zoom remains available inside the ROI",
  );
  await edit("e", 1, 0.5);
  before = (await snapshot()).state.integration.roi;
  g = await geometry();
  p = point(before, g, 0.5, 0.5);
  const zoomedRange = await range();
  await page.mouse.move(p.x, p.y);
  await page.mouse.down({ button: "right" });
  await page.mouse.move(p.x + 15, p.y + 10, { steps: 4 });
  await page.mouse.up({ button: "right" });
  await settle();
  assert.notDeepEqual(
    await range(),
    zoomedRange,
    "Right drag pans inside the ROI",
  );
  assert.deepEqual(
    (await snapshot()).state.integration.roi,
    before,
    "Panning does not edit the ROI",
  );
  await page.mouse.dblclick(p.x + 15, p.y + 10, { button: "right" });
  await settle();

  // Translating beyond the detector clamps the complete region, preserving size.
  before = (await snapshot()).state.integration.roi;
  const state = (await snapshot()).state;
  g = await geometry();
  p = point(before, g, 0.5, 0.5);
  const box = await canvas.boundingBox();
  await page.mouse.move(p.x, p.y);
  await page.mouse.down();
  await page.mouse.move(box.x + 1, box.y + 1, { steps: 4 });
  await page.mouse.up();
  await waitReady();
  const clamped = (await snapshot()).state.integration.roi;
  assert.equal(clamped[2], 0);
  assert.equal(clamped[1], state.shape[0]);
  assert.equal(clamped[1] - clamped[0], before[1] - before[0]);
  assert.equal(clamped[3] - clamped[2], before[3] - before[2]);

  // An edge cannot cross the opposite edge or create an empty integration mask.
  g = await geometry();
  p = point(clamped, g, 1, 0.5);
  await page.mouse.move(p.x, p.y);
  await page.mouse.down();
  await page.mouse.move(g.ox - 20, p.y, { steps: 4 });
  await page.mouse.up();
  await waitReady();
  const narrow = (await snapshot()).state.integration.roi;
  assert.equal(narrow[3] - narrow[2], 1);
  return [
    "ROI translation, all corners and edges, live preview and release commit",
    "ROI cancellation, detector bounds, one-pixel minimum, and zoom/pan coexistence",
  ];
}
