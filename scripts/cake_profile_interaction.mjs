import assert from "node:assert/strict";

/** Hold the pointer down while proving native profiles arrive for both edges. */
export async function checkCakeProfileWidthResize(
  page,
  profile,
  cake,
  ready,
  backpressure,
) {
  const field = page.getByLabel("Integral width", { exact: true });
  const original = Number(await field.inputValue());
  const snapshot = () =>
    cake.evaluate((el) => ({
      view: [
        el.dataset.viewXMin,
        el.dataset.viewXMax,
        el.dataset.viewYMin,
        el.dataset.viewYMax,
      ],
      linked: el.dataset.linkedPosition,
    }));
  const before = await snapshot();
  const begin = async (edge) => {
    const g = await cake.evaluate((el) => {
      const r = el.getBoundingClientRect(),
        d = el.dataset;
      return {
        x: r.x,
        y: r.y,
        left: +d.plotLeft,
        top: +d.plotTop,
        width: +d.plotWidth,
        height: +d.plotHeight,
        min: +d.viewXMin,
        max: +d.viewXMax,
        columns: +d.fullWidth,
        band: d.profileWindow.split(",").map(Number),
      };
    });
    const scale = g.width / (g.max - g.min);
    const source =
      edge === "min" ? Math.max(0, g.band[0]) : Math.min(g.columns, g.band[1]);
    const x = g.x + g.left + (source - g.min) * scale,
      y = g.y + g.top + g.height * 0.4;
    await page.mouse.move(x, y);
    assert.equal(
      await cake.evaluate((el) => getComputedStyle(el).cursor),
      "ew-resize",
    );
    await page.mouse.down();
    const start = Number(await field.inputValue());
    return async (bins) => {
      await page.mouse.move(
        x + ((edge === "max" ? 1 : -1) * (bins - start) * scale) / 2,
        y,
        { steps: 3 },
      );
      await page.waitForFunction(
        (bins) =>
          Number(
            document.querySelector('input[aria-label="Integral width"]').value,
          ) === bins,
        bins,
      );
      assert.ok(
        +(await profile.getAttribute("data-profile-row-count")) > 0,
        "The curve must remain present during width updates",
      );
      assert.equal(
        await profile.getAttribute("aria-description"),
        null,
        "No loading message during a width drag",
      );
      assert.deepEqual(
        await snapshot(),
        before,
        "Dragging an edge must not zoom or move the radial selection",
      );
    };
  };
  for (const edge of ["max", "min"]) {
    const move = await begin(edge);
    for (const bins of [7, 11]) {
      await move(bins);
      await page.waitForFunction(
        (bins) =>
          document.querySelector('[data-testid="cake-profile-canvas"]').dataset
            .profileBins === String(bins),
        bins,
      );
      assert.equal(
        await cake.getAttribute("data-profile-resizing"),
        "true",
        "The updated native profile arrived before mouse release",
      );
    }
    await page.mouse.up();
    await ready();
    await field.fill(String(original));
    await field.press("Enter");
    await ready();
  }
  // A transport stall must leave only the latest requested width queued.
  if (backpressure) {
    backpressure.hold();
    const move = await begin("max");
    await move(7);
    await backpressure.started();
    for (const bins of [9, 11, 13, 15, 17, 19, 21]) await move(bins);
    assert.equal(
      backpressure.calls(),
      1,
      "Intermediate widths must coalesce while native work is pending",
    );
    await page.mouse.up();
    backpressure.release();
    await ready();
    await page.waitForFunction(
      () =>
        document.querySelector('[data-testid="cake-profile-canvas"]').dataset
          .profileBins === "21",
    );
    assert.equal(
      backpressure.calls(),
      2,
      "Only the stalled and final widths should reach the native owner",
    );
    await field.fill(String(original));
    await field.press("Enter");
    await ready();
  }
  const move = await begin("max");
  await move(1);
  await cake.press("Escape");
  await page.mouse.up();
  await ready();
  assert.equal(
    Number(await field.inputValue()),
    original,
    "Escape restores the previous width",
  );
  assert.equal(+(await profile.getAttribute("data-profile-bins")), original);
  assert.deepEqual(await snapshot(), before);
}

/** Exercise the outer shared axis and resize handle as a user would. */
export async function checkCakeProfileInteraction(
  page,
  profile,
  cake,
  ready,
  samples,
) {
  const view = async (canvas) =>
    canvas.evaluate((el) => ({
      xMin: +el.dataset.viewXMin,
      xMax: +el.dataset.viewXMax,
      yMin: +el.dataset.viewYMin,
      yMax: +el.dataset.viewYMax,
    }));
  const geometry = async (canvas) =>
    canvas.evaluate((el) => {
      const r = el.getBoundingClientRect(),
        d = el.dataset;
      return {
        x: r.x,
        y: r.y,
        width: r.width,
        left: +d.plotLeft,
        top: +d.plotTop,
        w: +d.plotWidth,
        h: +d.plotHeight,
      };
    });
  const shared = async () => {
    const a = await view(profile),
      b = await view(cake);
    assert.equal(a.yMin, b.yMin);
    assert.equal(a.yMax, b.yMax);
  };
  const resize = page.getByRole("separator", {
    name: "Profile and cake divider",
    exact: true,
  });
  await page
    .getByRole("button", { name: "Profile rectangle zoom", exact: true })
    .click();
  await ready();
  await resize.waitFor();
  assert.equal(await cake.getAttribute("data-shows-azimuth-axis"), "false");
  assert.ok(
    (await geometry(profile)).left >= 60,
    "The shared azimuth axis is at the far left",
  );
  assert.equal((await geometry(cake)).left, 8, "No duplicate cake y axis");
  const before = { profile: await view(profile), cake: await view(cake) };
  const initial = (await geometry(profile)).width;
  await resize.focus();
  await resize.press("ArrowRight");
  await ready();
  assert.ok((await geometry(profile)).width > initial + 5);
  const box = await resize.boundingBox();
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
  await page.mouse.down();
  await page.mouse.move(box.x + box.width / 2 + 50, box.y + box.height / 2, {
    steps: 8,
  });
  await page.mouse.up();
  await ready();
  const widened = (await geometry(profile)).width;
  assert.ok(widened > initial + 35, "Dragging widens the profile");
  assert.deepEqual(
    { profile: await view(profile), cake: await view(cake) },
    before,
    "Resize preserves the scientific viewport",
  );
  const stored = await page.evaluate(() =>
    Number(localStorage.getItem("dioptas-layout:cake-profile-width")),
  );
  assert.ok(Math.abs(stored - widened) < 1.1, "Width preference persists");
  await resize.dblclick();
  await ready();
  assert.ok(
    (await geometry(profile)).width < widened - 15,
    "Double-click resets width",
  );
  await shared();
  const fit = async () => {
    await cake.press("f");
    await profile.press("f");
    await ready();
  };
  const dragAxis = async (destination, returnToProfile = false) => {
    const p = await geometry(profile),
      c = await geometry(cake);
    await page.mouse.move(p.x + p.left - 12, p.y + p.top + p.h * 0.2);
    await page.mouse.down();
    if (destination === "cake")
      await page.mouse.move(c.x + c.left + c.w * 0.6, c.y + c.top + c.h * 0.7, {
        steps: 20,
      });
    if (destination === "profile" || returnToProfile)
      await page.mouse.move(
        p.x + p.left + p.w * 0.75,
        p.y + p.top + p.h * 0.7,
        { steps: 20 },
      );
    await page.mouse.up();
    await ready();
    await shared();
  };
  await fit();
  const full = await view(cake);
  await dragAxis("profile");
  assert.ok((await view(profile)).yMax < full.yMax);
  assert.equal(
    (await view(cake)).xMax,
    full.xMax,
    "Axis drag into profile retains cake radial range",
  );
  await fit();
  await dragAxis("cake");
  assert.ok(
    (await view(cake)).xMax < full.xMax,
    "Axis drag across divider zooms cake",
  );
  assert.ok((await view(cake)).yMax < full.yMax);
  await fit();
  await dragAxis("cake", true);
  assert.equal(
    (await view(cake)).xMax,
    full.xMax,
    "Returning to profile selects its interval",
  );
  assert.ok((await view(profile)).yMax < full.yMax);
  await fit();
  const button = (name) => page.getByRole("button", { name, exact: true });
  const near = (a, b) =>
    assert.ok(
      Math.abs(a - b) < 1e-7 * Math.max(1, Math.abs(b)),
      `${a} != ${b}`,
    );
  const dragPlot = async (from, to, mouseButton = "left") => {
    const p = await geometry(profile);
    await page.mouse.move(
      p.x + p.left + p.w * from[0],
      p.y + p.top + p.h * from[1],
    );
    await page.mouse.down({ button: mouseButton });
    await page.mouse.move(
      p.x + p.left + p.w * to[0],
      p.y + p.top + p.h * to[1],
      { steps: 10 },
    );
    await page.mouse.up({ button: mouseButton });
    await ready();
    await shared();
  };
  const fullProfile = await view(profile),
    cakeRadial = await view(cake);
  // Rectangle selects both intensity and azimuth.
  await dragPlot([0.2, 0.2], [0.8, 0.8]);
  const rectangle = await view(profile);
  assert.ok(
    rectangle.xMax - rectangle.xMin < fullProfile.xMax - fullProfile.xMin,
  );
  assert.ok(
    rectangle.yMax - rectangle.yMin < fullProfile.yMax - fullProfile.yMin,
  );
  await fit();
  await button("Profile Y-range zoom").click();
  await ready();
  assert.equal(await profile.getAttribute("data-zoom-mode"), "vertical");
  assert.equal(
    await page.evaluate(() =>
      localStorage.getItem("dioptas-plot-zoom-v1:cake-profile"),
    ),
    "vertical",
  );
  await dragAxis("profile");
  assert.ok((await view(profile)).yMax < fullProfile.yMax);
  await fit();
  const assertIntensityFit = async () => {
    if (!samples) return;
    const r = await view(profile);
    const values = samples.filter(
      (v, i) =>
        v != null &&
        v !== 0 &&
        Number.isFinite(v) &&
        i + 0.5 >= r.yMin &&
        i + 0.5 <= r.yMax,
    );
    if (!values.length) {
      near(r.xMin, 0);
      near(r.xMax, 1);
      return;
    }
    const low = Math.min(...values),
      high = Math.max(...values);
    const pad = Math.max((high - low) * 0.05, Math.abs(low) * 1e-6, 1e-6);
    near(r.xMin, low - pad);
    near(r.xMax, high + pad);
  };
  // A strictly vertical drag needs no horizontal displacement.
  await dragPlot([0.5, 0.2], [0.5, 0.8]);
  const slice = await view(profile);
  assert.ok(
    slice.yMax - slice.yMin < (fullProfile.yMax - fullProfile.yMin) * 0.7,
  );
  await assertIntensityFit();
  for (const mouseButton of ["left", "right"]) {
    await dragPlot([0.25, 0.5], [0.75, 0.5], mouseButton);
    assert.deepEqual(
      await view(profile),
      slice,
      "Vertical slice ignores horizontal-only drags",
    );
  }
  await dragPlot([0.4, 0.4], [0.7, 0.55], "right");
  const panned = await view(profile);
  near(panned.yMax - panned.yMin, slice.yMax - slice.yMin);
  assert.ok(panned.yMin > slice.yMin);
  await assertIntensityFit();
  const p = await geometry(profile);
  await page.mouse.move(p.x + p.left + p.w * 0.5, p.y + p.top + p.h * 0.5);
  await page.mouse.wheel(0, -200);
  await ready();
  assert.ok(
    (await view(profile)).yMax - (await view(profile)).yMin <
      panned.yMax - panned.yMin,
  );
  await assertIntensityFit();
  const beforeKey = await view(profile);
  await profile.press("+");
  await ready();
  near(
    (await view(profile)).yMax - (await view(profile)).yMin,
    (beforeKey.yMax - beforeKey.yMin) / 2,
  );
  await assertIntensityFit();
  await profile.press("ArrowLeft");
  await ready();
  const afterArrow = await view(profile);
  await profile.press("ArrowUp");
  await ready();
  assert.ok((await view(profile)).yMin > afterArrow.yMin);
  await assertIntensityFit();
  const radialAfter = await view(cake);
  near(radialAfter.xMin, cakeRadial.xMin);
  near(radialAfter.xMax, cakeRadial.xMax);
  const beforeUnzoom = await view(profile);
  await page.mouse.click(p.x + p.left + p.w * 0.5, p.y + p.top + p.h * 0.5, {
    button: "right",
  });
  await ready();
  near(
    (await view(profile)).yMax - (await view(profile)).yMin,
    (beforeUnzoom.yMax - beforeUnzoom.yMin) * 2,
  );
  await assertIntensityFit();
  await page.mouse.dblclick(p.x + p.left + p.w * 0.5, p.y + p.top + p.h * 0.5, {
    button: "right",
  });
  await ready();
  near((await view(profile)).yMin, fullProfile.yMin);
  near((await view(profile)).yMax, fullProfile.yMax);
  await assertIntensityFit();
  await button("Profile rectangle zoom").click();
  await fit();
}
