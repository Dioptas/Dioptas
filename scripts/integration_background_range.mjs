import assert from "node:assert/strict";

export async function verifyBackgroundParameters(page, invoke, waitReady) {
  const settled = async () => {
    await page.waitForFunction(
      () =>
        document.querySelector('[data-testid="pattern-canvas"]')?.dataset
          .regionUpdating === "false",
    );
    await waitReady();
  };
  const field = (label) => page.getByLabel(label, { exact: true });
  const background = async () =>
    (await invoke("state")).state.integration.patternBackground;
  assert.equal(
    await page
      .getByRole("button", { name: "Apply pattern background", exact: true })
      .count(),
    0,
  );
  await field("Subtract automatic pattern background").uncheck();
  await field("Smooth width").fill("0.15");
  await field("Iterations").fill("11");
  await field("Polynomial order").fill("4");
  await settled();
  let current = await background();
  assert.equal(current.enabled, false);
  assert.equal(current.smoothing, 0.15);
  assert.equal(current.iterations, 11);
  assert.equal(current.order, 4);
  await field("Subtract automatic pattern background").check();
  await settled();
  for (const [label, key, value] of [
    ["Smooth width", "smoothing", 0.2],
    ["Iterations", "iterations", 10],
    ["Polynomial order", "order", 5],
  ]) {
    await field(label).fill(String(value));
    await settled();
    current = await background();
    assert.equal(current[key], value, `${label} refits automatically`);
    assert.equal(current.enabled, true);
    assert.equal((await invoke("state")).pattern.backgroundCurves.length, 2);
  }
  // Empty and invalid intermediate edits stay editable and never reach science.
  const revision = (await invoke("state")).state.revision;
  await field("Iterations").fill("0");
  await field("Polynomial order").fill("2.5");
  await field("Smooth width").fill("");
  await page.waitForTimeout(120);
  assert.equal((await invoke("state")).state.revision, revision);
  await field("Iterations").fill("12");
  await field("Polynomial order").fill("6");
  await field("Smooth width").fill("0.25");
  await settled();
  current = await background();
  assert.equal(current.iterations, 12);
  assert.equal(current.order, 6);
  assert.equal(current.smoothing, 0.25);
  // Leave the original smoke's fitting settings for the following range checks.
  await field("Iterations").fill("10");
  await field("Polynomial order").fill("5");
  await settled();
}

/** Exercise the actual background model through the plot slice and sidebar. */
export async function verifyBackgroundRange(page, invoke, waitReady) {
  const canvas = page.getByTestId("pattern-canvas");
  const inspect = page.getByRole("button", {
    name: "Inspect pattern background",
    exact: true,
  });
  const region = () =>
    canvas.evaluate((el) => JSON.parse(el.dataset.regions)[0]);
  const state = async () => (await invoke("state")).state;
  const settled = async () => {
    await page.waitForFunction(
      () =>
        document.querySelector('[data-testid="pattern-canvas"]')?.dataset
          .regionUpdating === "false",
    );
    await waitReady();
  };
  const close = (actual, expected) =>
    assert.ok(
      Math.abs(actual - expected) < Math.max(1e-6, Math.abs(expected) * 1e-8),
      `${actual} ≈ ${expected}`,
    );
  const drag = async (from, to, beforeRelease) => {
    const p = await canvas.evaluate(
      (el, [from, to]) => {
        const box = el.getBoundingClientRect(),
          d = el.dataset;
        const x = (v) =>
          box.left +
          +d.plotLeft +
          ((v - +d.viewXMin) / (+d.viewXMax - +d.viewXMin)) * +d.plotWidth;
        return {
          x0: x(from),
          x1: x(to),
          y: box.top + +d.plotTop + +d.plotHeight * 0.6,
        };
      },
      [from, to],
    );
    await page.mouse.move(p.x0, p.y);
    await page.mouse.down();
    await page.mouse.move(p.x1, p.y, { steps: 5 });
    if (beforeRelease) await beforeRelease();
    await page.mouse.up();
    await settled();
  };
  await inspect.click();
  const initial = await region();
  assert.ok(
    initial && initial.max > initial.min,
    "Inspect shows a full-height background slice",
  );
  const width = initial.max - initial.min;
  const originalBackgroundPoints = (await invoke("state")).pattern
    .backgroundCurves[1].x.length;
  await page.evaluate(() => {
    const begin = CanvasRenderingContext2D.prototype.beginPath;
    const line = CanvasRenderingContext2D.prototype.lineTo;
    const stroke = CanvasRenderingContext2D.prototype.stroke;
    const counts = new WeakMap();
    CanvasRenderingContext2D.prototype.beginPath = function (...args) {
      counts.set(this, 0);
      return begin.apply(this, args);
    };
    CanvasRenderingContext2D.prototype.lineTo = function (...args) {
      counts.set(this, (counts.get(this) ?? 0) + 1);
      return line.apply(this, args);
    };
    CanvasRenderingContext2D.prototype.stroke = function (...args) {
      if (
        ["pattern-canvas", "pattern-curves"].includes(
          this.canvas.dataset.testid,
        ) &&
        this.strokeStyle === "#73bba6"
      )
        window.__backgroundDrawnPoints = counts.get(this) + 1;
      return stroke.apply(this, args);
    };
    const glDraw = WebGL2RenderingContext.prototype.drawArraysInstanced;
    WebGL2RenderingContext.prototype.drawArraysInstanced = function (...args) {
      if (this.canvas.dataset.testid === "pattern-gpu") {
        const program = this.getParameter(this.CURRENT_PROGRAM);
        const location = this.getUniformLocation(program, "color");
        const color = location && this.getUniform(program, location);
        if (
          color &&
          Math.round(color[0] * 255) === 115 &&
          Math.round(color[1] * 255) === 187 &&
          Math.round(color[2] * 255) === 166
        )
          window.__backgroundDrawnPoints = args[3] + 1;
      }
      return glDraw.apply(this, args);
    };
    window.__restoreBackgroundStrokes = () => {
      WebGL2RenderingContext.prototype.drawArraysInstanced = glDraw;
      CanvasRenderingContext2D.prototype.beginPath = begin;
      CanvasRenderingContext2D.prototype.lineTo = line;
      CanvasRenderingContext2D.prototype.stroke = stroke;
    };
  });
  const parameters = (await state()).integration.patternBackground;
  const revision = (await state()).revision;
  await drag(initial.min, initial.min + width * 0.15, async () => {
    await page.waitForFunction(
      async (revision) =>
        (await window.__dioptasInvoke("state")).state.revision > revision,
      revision,
    );
    assert.ok(
      (await state()).revision > revision,
      "The model refits before the pointer is released",
    );
    assert.ok((await region()).min > initial.min);
    await page.waitForFunction(
      (count) =>
        window.__backgroundDrawnPoints > 0 &&
        window.__backgroundDrawnPoints < count,
      originalBackgroundPoints,
    );
  });
  let current = await state();
  let selected = await region();
  close(selected.min, current.integration.patternBackground.range[0]);
  assert.ok(selected.min > initial.min + width * 0.1);
  await drag(selected.max - width * 0.002, selected.max - width * 0.15);
  selected = await region();
  assert.ok(selected.max < initial.max - width * 0.1);
  const viewBefore = await canvas.getAttribute("data-view-x-max");
  const beforeZoomRevision = (await state()).revision;
  // A diagonal drag in the slice interior zooms; it must not move the range.
  const zoom = await canvas.evaluate((el) => {
    const box = el.getBoundingClientRect(),
      d = el.dataset;
    return {
      x: box.x + +d.plotLeft,
      y: box.y + +d.plotTop,
      w: +d.plotWidth,
      h: +d.plotHeight,
    };
  });
  await page.mouse.move(zoom.x + zoom.w * 0.35, zoom.y + zoom.h * 0.3);
  await page.mouse.down();
  await page.mouse.move(zoom.x + zoom.w * 0.65, zoom.y + zoom.h * 0.75, {
    steps: 5,
  });
  await page.mouse.up();
  await waitReady();
  assert.notEqual(
    await canvas.getAttribute("data-view-x-max"),
    viewBefore,
    "Dragging inside the slice zooms",
  );
  assert.equal(
    (await state()).revision,
    beforeZoomRevision,
    "Zoom does not refit or move the background range",
  );
  close((await region()).min, selected.min);
  await page.mouse.dblclick(zoom.x + zoom.w * 0.5, zoom.y + zoom.h * 0.5, {
    button: "right",
  });
  await waitReady();
  current = await state();
  for (const key of ["smoothing", "iterations", "order"])
    assert.equal(current.integration.patternBackground[key], parameters[key]);
  await drag(selected.min, selected.min + width * 0.04, async () => {
    await page.waitForFunction(
      () =>
        document.querySelector('[data-testid="pattern-canvas"]')?.dataset
          .regionUpdating === "false",
    );
    await page.keyboard.press("Escape");
  });
  close((await region()).min, selected.min);
  close((await state()).integration.patternBackground.range[0], selected.min);

  // Record every frame while an earlier fit is still returning. Releasing must
  // never expose that earlier position or clear the optimistic final edge.
  const target = selected.min + width * 0.06;
  let releasedMin;
  await drag(selected.min, target, async () => {
    releasedMin = (await region()).min;
    await canvas.evaluate((el) => {
      window.__backgroundFrames = [];
      window.__recordBackground = true;
      const capture = () => {
        if (!window.__recordBackground) return;
        window.__backgroundFrames.push(JSON.parse(el.dataset.regions)[0].min);
        requestAnimationFrame(capture);
      };
      capture();
    });
  });
  const frames = await page.evaluate(() => {
    window.__recordBackground = false;
    return window.__backgroundFrames;
  });
  assert.ok(frames.length > 0);
  for (const min of frames) close(min, releasedMin);
  selected = await region();

  // Inspect remains editable after converting the radial coordinate, including d.
  for (const [label, unit] of [
    ["Q", "q_A^-1"],
    ["d", "d_A"],
    ["2θ", "2th_deg"],
  ]) {
    await page
      .getByRole("button", { name: `Pattern unit ${label}`, exact: true })
      .click();
    await waitReady();
    current = await state();
    assert.equal(current.unit, unit);
    selected = await region();
    close(selected.min, current.integration.patternBackground.range[0]);
    close(selected.max, current.integration.patternBackground.range[1]);
    await drag(
      selected.min,
      selected.min + (selected.max - selected.min) * 0.01,
    );
  }
  await page.getByRole("tab", { name: "Background", exact: true }).click();
  assert.equal(
    await page
      .getByLabel("Limit background range", { exact: true })
      .isChecked(),
    true,
  );
  current = await state();
  close(
    Number(
      await page.getByLabel("Background minimum", { exact: true }).inputValue(),
    ),
    current.integration.patternBackground.range[0],
  );
  const numericMin =
    current.integration.patternBackground.range[0] + width * 0.02;
  await page
    .getByLabel("Background minimum", { exact: true })
    .fill(String(numericMin));
  await settled();
  close((await state()).integration.patternBackground.range[0], numericMin);
  close((await region()).min, numericMin);
  await page.screenshot({
    path: new URL(
      "../artifacts/integration-background-range.png",
      import.meta.url,
    ).pathname,
  });
  await inspect.click();
  assert.equal(
    await canvas.getAttribute("data-regions"),
    "[]",
    "Turning Inspect off hides the slice",
  );
  assert.ok(
    (await state()).integration.patternBackground.range,
    "Hiding Inspect preserves the fitted range",
  );
  await page.getByLabel("Limit background range", { exact: true }).uncheck();
  await settled();
  await page.getByRole("tab", { name: "Image", exact: true }).click();
  await page.evaluate(() => window.__restoreBackgroundStrokes());
}
