import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
import { selectIntegrationDisplay } from "./integration_display.mjs";

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
const close = (actual, expected, message, tolerance = 0) =>
  assert.ok(
    Math.abs(actual - expected) <
      Math.max(tolerance, 1e-7, Math.abs(expected) * 1e-7),
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

export async function verifyModifiedPlotNavigation(page, canvas) {
  const id = await canvas.getAttribute("data-testid");
  const horizontal =
    (await canvas.getAttribute("data-zoom-mode")) === "horizontal";
  await restore(page, canvas);
  const fit = await read(canvas);
  const p = await point(canvas, 0.5, 0.5);
  for (const modifier of ["Control", "Meta"]) {
    await page.mouse.move(p.x, p.y);
    await page.mouse.wheel(0, -1000);
    await settle(page);
    const zoomed = await read(canvas);
    assert.ok(spanX(zoomed) < spanX(fit) / 3);
    await page.keyboard.down(modifier);
    try {
      await drag(page, canvas, [0.5, 0.5], [0.55, 0.55]);
      const panned = await read(canvas);
      close(spanX(panned), spanX(zoomed), `${id}: ${modifier}-drag x scale`);
      assert.ok(panned.xMin < zoomed.xMin, `${id}: ${modifier}-drag pans x`);
      if (horizontal) {
        await drag(page, canvas, [0.5, 0.4], [0.5, 0.6]);
        assert.deepEqual(
          await read(canvas),
          panned,
          `${id}: slice mode ignores vertical pan`,
        );
      } else {
        close(spanY(panned), spanY(zoomed), `${id}: ${modifier}-drag y scale`);
        assert.ok(panned.yMin > zoomed.yMin, `${id}: ${modifier}-drag pans y`);
      }
      await page.mouse.click(p.x, p.y);
      await settle(page);
      const single = await read(canvas);
      close(
        spanX(single),
        spanX(panned) * 2,
        `${id}: ${modifier}-click unzooms`,
      );
      // A pan separates the single click from the following double-click.
      await drag(page, canvas, [0.5, 0.5], [0.55, 0.55]);
      await page.mouse.dblclick(p.x, p.y);
      await settle(page);
      assert.deepEqual(
        await read(canvas),
        fit,
        `${id}: ${modifier}-double-click restores the complete fitted view`,
      );
    } finally {
      await page.keyboard.up(modifier);
    }
  }
  return `${id}: Ctrl/Command click unzoom, double-click fit and drag pan`;
}

export async function verifyCakeMarginNavigation(page) {
  return verifyRectangleMarginNavigation(page, "cake-canvas");
}

/** Isolated rendering fixture: verify slice navigation against known content. */
export async function verifySliceContentScaling(page) {
  await page.evaluate(() => {
    window.sliceRange = { xMin: 20, xMax: 70, yMin: -500, yMax: 1e5 };
    const x = Array.from({ length: 101 }, (_, i) => i);
    window.sliceProps = {
      pattern: { x, y: x.map((v) => 10 + v * v), unit: "2th_deg" },
      curves: [{ x, y: x.map((v) => 100 + v * 2), color: "#fff" }],
      log: false,
      zoomMode: "horizontal",
      autoRange: false,
      onAutoRange: () => {},
      viewport: {
        key: "slice-test",
        read: () => window.sliceRange,
        write: (range) => {
          window.sliceRange = range;
        },
      },
    };
    window.paint(window.fixture.PatternView, window.sliceProps);
  });
  await settle(page);
  const canvas = page.getByTestId("pattern-canvas");
  const checkContent = async () => {
    const view = await read(canvas);
    const expected = await page.evaluate(({ xMin, xMax }) => {
      const props = window.sliceProps;
      const values = [props.pattern, ...props.curves].flatMap((curve) =>
        curve.y
          .filter((y, i) => curve.x[i] >= xMin && curve.x[i] <= xMax)
          .map((y) =>
            props.log ? Math.log10(y) : props.sqrt ? Math.sqrt(y) : y,
          ),
      );
      const low = Math.min(...values),
        high = Math.max(...values);
      const padding = (high - low) * 0.04;
      return { yMin: low - padding, yMax: high + padding };
    }, view);
    close(view.yMin, expected.yMin, "Slice fits the visible content minimum");
    close(view.yMax, expected.yMax, "Slice fits the visible content maximum");
    return view;
  };
  await checkContent();
  await drag(page, canvas, [0.25, 0.2], [0.75, 0.8]);
  const zoomed = await checkContent();
  close(
    spanX(zoomed),
    25,
    "Slice selection ignores vertical displacement",
    0.1,
  );
  await drag(page, canvas, [0.6, 0.2], [0.4, 0.8], "right");
  const panned = await checkContent();
  close(spanX(panned), spanX(zoomed), "Slice pan preserves x scale");
  assert.ok(panned.xMin > zoomed.xMin);
  await drag(page, canvas, [0.5, 0.2], [0.5, 0.8], "right");
  assert.deepEqual(
    await read(canvas),
    panned,
    "Slice ignores vertical-only pan",
  );
  for (const scale of ["linear", "log", "sqrt"]) {
    await page.evaluate((scale) => {
      const props = window.sliceProps;
      props.pattern = {
        ...props.pattern,
        y: props.pattern.y.map((v) => v * 2),
      };
      props.log = scale === "log";
      props.sqrt = scale === "sqrt";
      window.paint(window.fixture.PatternView, props);
    }, scale);
    await settle(page);
    const updated = await checkContent();
    close(
      updated.xMin,
      panned.xMin,
      "Data/scale updates preserve slice x minimum",
    );
    close(
      updated.xMax,
      panned.xMax,
      "Data/scale updates preserve slice x maximum",
    );
  }
  await page.evaluate(() =>
    window.paint(window.fixture.RasterView, {
      ...window.rasterProps,
      raster: {
        ...window.rasterProps.raster,
        radialRange: [0, 100],
        azimuthRange: [-180, 180],
        unit: "2th_deg",
      },
      cake: true,
      zoomMode: "horizontal",
    }),
  );
  await settle(page);
  const cake = page.getByTestId("cake-canvas");
  const fit = await read(cake);
  await drag(page, cake, [0.25, 0.2], [0.75, 0.8]);
  await drag(page, cake, [0.6, 0.2], [0.4, 0.8], "right");
  const cakePan = await read(cake);
  close(cakePan.yMin, fit.yMin, "Slice cake pan preserves azimuth minimum");
  close(cakePan.yMax, fit.yMax, "Slice cake pan preserves azimuth maximum");
  return "Slice drags and pans only horizontally; pattern y follows visible curves and data/scale updates; cake azimuth stays fixed";
}

async function verifyRectangleMarginNavigation(page, id) {
  const canvas = page.getByTestId(id);
  await restore(page, canvas);
  const fit = await read(canvas);
  const { width, height, left, top, right, bottom } = await canvas.evaluate(
    (el) => ({
      width: +el.dataset.plotWidth,
      height: +el.dataset.plotHeight,
      left: +el.dataset.plotLeft,
      top: +el.dataset.plotTop,
      right: el.clientWidth - +el.dataset.plotLeft - +el.dataset.plotWidth,
      bottom: el.clientHeight - +el.dataset.plotTop - +el.dataset.plotHeight,
    }),
  );
  const mx = 10 / width,
    my = 10 / height,
    axisLeft = Math.min(10, left / 2) / width,
    axisTop = Math.min(10, top / 2) / height,
    axisRight = Math.min(10, right / 2) / width,
    axisBottom = Math.min(10, bottom / 2) / height;
  // Compact plots can end at the canvas edge; start margin gestures only in
  // existing gutters. Pointer capture still covers releases beyond any edge.
  for (const [name, from, to] of [
    ...(left > 1 ? [["left axis", [-axisLeft, 0.2], [0.65, 0.75]]] : []),
    ...(top > 1 ? [["above image", [0.2, -axisTop], [0.75, 0.65]]] : []),
    ...(bottom > 1
      ? [["bottom axis", [0.2, 1 + axisBottom], [0.75, 0.35]]]
      : []),
    ...(right > 1
      ? [["right margin", [1 + axisRight, 0.2], [0.35, 0.75]]]
      : []),
    ...(left > 1 && top > 1
      ? [["outside corner", [-axisLeft, -axisTop], [0.65, 0.75]]]
      : []),
    ["release outside", [0.25, 0.3], [1 + mx, 1 + my]],
  ]) {
    await drag(page, canvas, from, to);
    const selected = await read(canvas);
    const clamp = (v) => Math.max(0, Math.min(1, v));
    const [x1, y1] = from.map(clamp),
      [x2, y2] = to.map(clamp);
    close(
      selected.xMin,
      fit.xMin + Math.min(x1, x2) * spanX(fit),
      `${name}: clipped x minimum`,
      (spanX(fit) / width) * 0.01,
    );
    close(
      selected.xMax,
      fit.xMin + Math.max(x1, x2) * spanX(fit),
      `${name}: clipped x maximum`,
      (spanX(fit) / width) * 0.01,
    );
    close(
      selected.yMin,
      fit.yMax - Math.max(y1, y2) * spanY(fit),
      `${name}: clipped y minimum`,
      (spanY(fit) / height) * 0.01,
    );
    close(
      selected.yMax,
      fit.yMax - Math.min(y1, y2) * spanY(fit),
      `${name}: clipped y maximum`,
      (spanY(fit) / height) * 0.01,
    );
    await restore(page, canvas);
  }
  // Check inert margins while zoomed so an accidental fit reset also fails.
  await drag(page, canvas, [0.2, 0.25], [0.8, 0.75]);
  const zoomed = await read(canvas);
  const linked = await canvas.getAttribute("data-linked-position");
  for (const [from, to] of [
    ...(left > 1
      ? [
          [
            [-axisLeft, 0.2],
            [-axisLeft / 2, 0.8],
          ],
        ]
      : []),
    ...(top > 1
      ? [
          [
            [0.2, -axisTop],
            [0.8, -axisTop / 2],
          ],
        ]
      : []),
    ...(bottom > 1
      ? [
          [
            [0.2, 1 + axisBottom],
            [0.8, 1 + axisBottom / 2],
          ],
        ]
      : []),
    ...(right > 1
      ? [
          [
            [1 + axisRight, 0.2],
            [1 + axisRight / 2, 0.8],
          ],
        ]
      : []),
  ]) {
    await drag(page, canvas, from, to);
    assert.deepEqual(
      await read(canvas),
      zoomed,
      `${id}: drag entirely outside plot does nothing`,
    );
  }
  const margin = await point(canvas, -mx, 0.5);
  await page.mouse.click(margin.x, margin.y);
  await settle(page);
  assert.deepEqual(
    await read(canvas),
    zoomed,
    `${id}: margin click preserves zoom`,
  );
  assert.equal(
    await canvas.getAttribute("data-linked-position"),
    linked,
    `${id}: margin gestures do not inspect radial positions`,
  );
  await restore(page, canvas);
  return [
    `${id}: rectangle drags start on axes/margins, clip to plot, and ignore outside-only gestures`,
  ];
}

async function verifyCompactAxisLabels(page, id) {
  const canvas = page.getByTestId(id);
  await canvas.evaluate((el) => {
    const axes =
      el.parentElement.querySelector('[data-testid="pattern-axes"]') ?? el;
    el.__axisText = [];
    const contexts = [...new Set([axes.getContext("2d"), el.getContext("2d")])];
    const restore = contexts.map((context, index) => {
      const fillText = context.fillText,
        scale = context.scale;
      context.scale = function (...args) {
        if (index === 0 && this.getTransform().isIdentity) el.__axisText = [];
        return scale.apply(this, args);
      };
      context.fillText = function (text, x, y, ...args) {
        const metrics = this.measureText(text),
          transform = this.getTransform();
        const corners = [
          [
            x - metrics.actualBoundingBoxLeft,
            y - metrics.actualBoundingBoxAscent,
          ],
          [
            x + metrics.actualBoundingBoxRight,
            y - metrics.actualBoundingBoxAscent,
          ],
          [
            x - metrics.actualBoundingBoxLeft,
            y + metrics.actualBoundingBoxDescent,
          ],
          [
            x + metrics.actualBoundingBoxRight,
            y + metrics.actualBoundingBoxDescent,
          ],
        ].map(([px, py]) => new DOMPoint(px, py).matrixTransform(transform));
        el.__axisText.push({
          text,
          x,
          y,
          left: Math.min(...corners.map((p) => p.x)) / devicePixelRatio,
          right: Math.max(...corners.map((p) => p.x)) / devicePixelRatio,
          top: Math.min(...corners.map((p) => p.y)) / devicePixelRatio,
          bottom: Math.max(...corners.map((p) => p.y)) / devicePixelRatio,
        });
        return fillText.call(this, text, x, y, ...args);
      };
      return () => {
        context.fillText = fillText;
        context.scale = scale;
      };
    });
    el.__restoreAxisCapture = () => restore.forEach((callback) => callback());
  });
  try {
    for (let i = 0; i < 14; i++) {
      await drag(page, canvas, [0.2, 0.1], [0.8, 0.3]);
      if (
        i >= 7 &&
        (await canvas.evaluate((el) =>
          el.__axisText.some((t) => t.text.includes("×10")),
        ))
      )
        break;
    }
    const rendered = await canvas.evaluate((el) => {
      const left = +el.dataset.plotLeft,
        top = +el.dataset.plotTop;
      return {
        width: el.clientWidth,
        plotLeft: left,
        plotTop: top,
        title: el.__axisText.find(
          (t) => t.text === "Azimuth (°)" || t.text === "Intensity (a.u.)",
        ),
        ticks: el.__axisText.filter(
          (t) =>
            t.x < left &&
            t.x >= left - 16 &&
            t.y >= top &&
            Number.isFinite(Number(t.text)),
        ),
        annotation: el.__axisText.find((t) => t.text.includes("×10")),
      };
    });
    assert.ok(
      rendered.annotation,
      `${id}: close zoom factors out a power of ten`,
    );
    assert.ok(rendered.title && rendered.ticks.length >= 2);
    assert.ok(
      rendered.annotation.top >= 0 &&
        rendered.annotation.bottom < rendered.plotTop,
    );
    assert.ok(
      rendered.annotation.left >= rendered.plotLeft &&
        rendered.annotation.right <= rendered.width,
    );
    for (const tick of rendered.ticks) {
      assert.ok(
        tick.left >= rendered.title.right + 6,
        `${id}: tick ${tick.text} clears the rotated title`,
      );
      assert.ok(
        tick.left >= 0 && tick.right < rendered.plotLeft,
        `${id}: tick stays inside its axis margin`,
      );
      assert.ok(
        tick.text.length <= 5,
        `${id}: close-zoom tick is compact: ${tick.text}`,
      );
    }
    await canvas.screenshot({
      path: fileURLToPath(
        new URL(`../artifacts/${id}-compact-axis.png`, import.meta.url),
      ),
    });
  } finally {
    await canvas.evaluate((el) => el.__restoreAxisCapture());
    await restore(page, canvas);
  }
  return [
    `${id}: scaled/offset ticks stay inside the axis margin and clear the rotated title at deep zoom`,
  ];
}

export async function verifyPlotNavigation(page) {
  const checks = [];
  const pattern = page.getByTestId("pattern-canvas");
  await page.getByRole("button", { name: "Settings", exact: true }).click();
  assert.equal(
    await page.getByLabel("Pattern zoom mode", { exact: true }).count(),
    0,
  );
  assert.equal(await pattern.getAttribute("data-zoom-mode"), "rectangle");
  await page
    .getByRole("button", { name: "Close settings", exact: true })
    .click();
  const patternFit = await read(pattern);
  const patternControls = page.locator(".pattern-container");
  assert.deepEqual(
    await patternControls.getByRole("button").allTextContents(),
    ["", ""],
    "Plot zoom selectors stay icon-only alongside Qt pattern-name legends",
  );
  // Exercise the complete app cascade, including the shared button selected styles.
  for (const name of ["Pattern rectangle zoom", "Pattern X-range zoom"]) {
    const button = patternControls.getByRole("button", { name, exact: true });
    await page.mouse.move(0, 0);
    await page.waitForTimeout(150);
    const idle = await button.evaluate((el) => {
      const style = getComputedStyle(el);
      return {
        background: style.backgroundColor,
        image: style.backgroundImage,
        shadow: style.boxShadow,
        radius: style.borderRadius,
      };
    });
    assert.deepEqual(
      idle,
      {
        background: "rgba(0, 0, 0, 0)",
        image: "none",
        shadow: "none",
        radius: "1px",
      },
      `${name}: only the icon is visible at rest`,
    );
    await button.hover();
    await page.waitForTimeout(150);
    assert.notEqual(
      await button.evaluate((el) => getComputedStyle(el).backgroundColor),
      "rgba(0, 0, 0, 0)",
      `${name}: hovering reveals the button background`,
    );
  }
  await page.mouse.move(0, 0);
  assert.equal(
    await patternControls
      .getByRole("button", { name: "Pattern rectangle zoom", exact: true })
      .getAttribute("aria-pressed"),
    "true",
  );
  await patternControls
    .getByRole("button", { name: "Pattern X-range zoom", exact: true })
    .click();
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
  const horizontalPoint = await point(pattern, 0.5, 0.5);
  await page.mouse.click(horizontalPoint.x, horizontalPoint.y, {
    button: "right",
  });
  await settle(page);
  const expanded = await read(pattern);
  close(
    spanX(expanded),
    spanX(patternFit),
    "X-range right-click restores the full x span regardless of intensity span",
  );
  close(
    expanded.yMin,
    patternFit.yMin,
    "X-range right-click refits the intensity minimum",
  );
  close(
    expanded.yMax,
    patternFit.yMax,
    "X-range right-click refits the intensity maximum",
  );
  await restore(page, pattern);
  checks.push(
    "icon-only plot selectors default to rectangle; X-range zoom-out refits both intensity limits",
  );

  for (const [id, label] of [
    ["detector-canvas", "Detector zoom mode"],
    ["cake-canvas", "Cake zoom mode"],
    ["pattern-canvas", "Pattern zoom mode"],
  ]) {
    if (await page.locator(".integration-layout").count())
      await selectIntegrationDisplay(
        page,
        id === "cake-canvas" ? "cake" : "image",
      );
    if (id === "pattern-canvas") {
      await patternControls
        .getByRole("button", { name: "Pattern rectangle zoom", exact: true })
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
    checks.push(await verifyModifiedPlotNavigation(page, canvas));
    if (id === "cake-canvas" || id === "pattern-canvas") {
      checks.push(...(await verifyRectangleMarginNavigation(page, id)));
      checks.push(...(await verifyCompactAxisLabels(page, id)));
    }
  }
  await patternControls
    .getByRole("button", { name: "Pattern rectangle zoom", exact: true })
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
  await page
    .getByRole("slider", { name: "Lower intensity handle", exact: true })
    .press("ArrowDown");
  await page
    .getByRole("slider", { name: "Upper intensity handle", exact: true })
    .press("ArrowUp");
  const intensity = () =>
    canvas.evaluate((el) => [el.dataset.intensityMin, el.dataset.intensityMax]);
  const manualLimits = await intensity();
  // Peak picking remains active: only a stationary left click selects peaks.
  await drag(page, canvas, [0.3, 0.3], [0.7, 0.7]);
  assert.ok(spanX(await read(canvas)) < spanX(initial) * 0.5);
  const zoomed = await read(canvas);
  // A missed pick is a normal notice and must preserve the current view.
  await page.evaluate(() => {
    window.__doubleClickInvoke = window.__dioptasInvoke;
    window.__doubleClickPicks = 0;
    window.__doubleClickFail = true;
    window.__dioptasInvoke = async (command, args) => {
      if (command === "pick_peak") {
        window.__doubleClickPicks++;
        return window.__doubleClickFail
          ? {
              ok: false,
              error:
                "No peak found here. Click on a bright ring, or try single-peak mode.",
            }
          : { ok: true };
      }
      const result = await window.__doubleClickInvoke(command, args);
      return result;
    };
  });
  try {
    const p = await point(canvas, 0.5, 0.5);
    await page.mouse.dblclick(p.x, p.y);
    await page.waitForFunction(() => window.__doubleClickPicks > 0);
    await page.waitForFunction(() => !document.querySelector(".spin"));
    await settle(page);
    assert.match(
      await page.locator('.workflow-status [role="status"]').innerText(),
      /No peaks found in this area/,
    );
    assert.equal(
      await page
        .getByRole("button", { name: "View error details", exact: true })
        .count(),
      0,
    );
    assert.deepEqual(
      await read(canvas),
      zoomed,
      "Left double-click preserves the image view after a failed peak pick",
    );
    assert.deepEqual(
      await intensity(),
      manualLimits,
      "Failed peak picking preserves manual intensity limits during recovery",
    );
    assert.equal(
      await page
        .getByRole("button", { name: "Auto intensity", exact: true })
        .getAttribute("aria-pressed"),
      "false",
    );
    await page.evaluate(() => {
      window.__doubleClickFail = false;
    });
    await page.mouse.dblclick(p.x, p.y);
    await settle(page);
    assert.deepEqual(
      await read(canvas),
      zoomed,
      "Left double-click preserves the image view after a successful pick",
    );
    assert.deepEqual(
      await intensity(),
      manualLimits,
      "Successful peak picking preserves manual intensity limits",
    );
  } finally {
    await page.evaluate(() => {
      window.__dioptasInvoke = window.__doubleClickInvoke;
      delete window.__doubleClickInvoke;
      delete window.__doubleClickPicks;
      delete window.__doubleClickFail;
    });
  }
  await page
    .getByRole("button", { name: "Auto intensity", exact: true })
    .click();
  await settle(page);
  await drag(page, canvas, [0.4, 0.4], [0.5, 0.5], "right");
  await restore(page, canvas);
  close(
    spanX(await read(canvas)),
    spanX(initial),
    "Calibration zoom returns to fit",
  );
}
