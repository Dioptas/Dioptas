import assert from "node:assert/strict";
const pause = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

export async function selectColorMap(page, label, name) {
  await page.getByRole("combobox", { name: label, exact: true }).click();
  await page
    .getByRole("listbox", { name: `${label} choices`, exact: true })
    .locator(`[role="option"][data-color-map="${name}"]`)
    .click();
}

export async function verifyImageControls(page, invoke, pixelRequests) {
  const canvas = page.getByTestId("detector-canvas");
  const detector = page.locator(".detector-panel");
  assert.equal(
    await detector.locator(".image-intensity").getAttribute("data-size"),
    "compact",
  );
  assert.equal(await canvas.getAttribute("data-intensity-scale"), "linear");
  assert.equal(await detector.locator(".intensity-header").count(), 0);
  await page
    .getByRole("button", { name: "Configure detector display", exact: true })
    .click();
  await page
    .getByLabel("Histogram size", { exact: true })
    .selectOption("large");
  await page
    .getByRole("button", {
      name: "Close detector display settings",
      exact: true,
    })
    .click();
  const bar = await detector.getByTestId("intensity-colour-bar").boundingBox();
  const region = await detector
    .getByTestId("intensity-selected-window")
    .boundingBox();
  assert.ok(
    region.x + region.width < bar.x,
    "Selected intensity window must stop before the colour scale",
  );
  for (const name of ["Lower intensity handle", "Upper intensity handle"]) {
    const handle = await page
      .getByRole("slider", { name, exact: true })
      .boundingBox();
    assert.ok(
      handle.x + handle.width < bar.x,
      "Boundary handles must stay inside the histogram graph",
    );
  }

  assert.equal(
    await page
      .getByRole("button", { name: "Export pattern", exact: true })
      .count(),
    0,
  );
  assert.equal(await page.locator(".views-grid .calibration-panel").count(), 0);
  assert.equal(await page.locator(".sidebar .calibration-panel").count(), 1);
  assert.equal(
    await page.locator(".detector-panel .image-intensity").count(),
    1,
  );
  assert.equal(await page.locator(".sidebar .image-intensity").count(), 0);
  assert.equal(
    await page
      .getByLabel("Current calibrant ring", { exact: true })
      .getAttribute("type"),
    "number",
  );
  await page.getByLabel("Current calibrant ring", { exact: true }).fill("3");
  assert.match(
    await page.getByTestId("active-ring").innerText(),
    /Picking ring 3/,
  );
  await page
    .getByRole("radio", { name: "Single peak search", exact: true })
    .check();
  assert.equal(
    await page
      .getByLabel("Single-peak search size", { exact: true })
      .isEnabled(),
    true,
  );
  await page
    .getByRole("radio", { name: "Automatic peak search", exact: true })
    .check();
  await page.getByLabel("Current calibrant ring", { exact: true }).fill("1");

  const original = await invoke("state");
  assert.equal(
    original.image.step,
    1,
    "The display must transfer every detector pixel",
  );
  assert.equal(original.image.width, original.image.fullWidth);
  assert.equal(original.image.height, original.image.fullHeight);
  assert.equal(
    original.mask.width,
    original.image.width,
    "Full-resolution mask aligns with full-resolution image",
  );
  assert.equal(
    original.image.histogram.finitePixels,
    original.image.fullWidth * original.image.fullHeight,
  );
  const renderedBefore = await canvas.evaluate((el) => el.toDataURL());
  const upper = await page
    .getByRole("slider", { name: "Upper intensity handle", exact: true })
    .boundingBox();
  await page.mouse.move(upper.x + upper.width / 2, upper.y + upper.height / 2);
  await page.mouse.down();
  await page.mouse.move(
    upper.x + upper.width / 2,
    upper.y + upper.height / 2 - 40,
    { steps: 6 },
  );
  await page.mouse.up();
  await pause(120);
  assert.ok(
    Number(await canvas.getAttribute("data-intensity-max")) >
      original.image.limits[1],
  );
  assert.notEqual(
    await canvas.evaluate((el) => el.toDataURL()),
    renderedBefore,
  );
  await page
    .getByRole("slider", { name: "Lower intensity handle", exact: true })
    .press("ArrowDown");
  assert.ok(
    Number(await canvas.getAttribute("data-intensity-min")) <
      original.image.limits[0],
  );
  const after = await invoke("state");
  assert.equal(
    after.image.data,
    original.image.data,
    "Contrast edits must not alter source intensities",
  );
  assert.deepEqual(after.state.geometry, original.state.geometry);
  await page
    .getByRole("button", { name: "Auto intensity", exact: true })
    .click();
  await page.waitForFunction(
    (expected) =>
      +document.querySelector('[data-testid="detector-canvas"]').dataset
        .intensityMax === expected,
    original.image.limits[1],
  );
  await page
    .getByRole("button", { name: "Configure detector display", exact: true })
    .click();
  for (const mode of ["minmax", "mean3std", "percentile"]) {
    await page
      .getByLabel("Auto intensity mode", { exact: true })
      .selectOption(mode);
    const expected = (
      await invoke("image_levels", { mode, percentile: 0.4, filter_gaps: true })
    ).levels;
    await page.waitForFunction((expected) => {
      const el = document.querySelector('[data-testid="detector-canvas"]');
      return (
        Math.abs(+el.dataset.intensityMin - expected[0]) < 1e-8 &&
        Math.abs(+el.dataset.intensityMax - expected[1]) < 1e-8
      );
    }, expected);
  }
  await page
    .getByRole("button", {
      name: "Close detector display settings",
      exact: true,
    })
    .click();
  await page.getByRole("combobox", { name: "Color map", exact: true }).click();
  const choices = page.getByRole("listbox", {
    name: "Color map choices",
    exact: true,
  });
  assert.equal(await choices.getByRole("option").count(), 16);
  assert.equal(
    await choices.locator("img").count(),
    16,
    "Every colour scale has a real ramp image",
  );
  assert.equal(
    await choices.locator('[role="group"]').count(),
    0,
    "The choices are one ungrouped list",
  );
  assert.doesNotMatch(
    await choices.innerText(),
    /CET|PAL|Preview palettes|pyqtgraph colour maps/,
  );
  await page.screenshot({
    path: new URL("../artifacts/colour-scale-picker.png", import.meta.url)
      .pathname,
  });
  await choices.locator('[data-color-map="grey"]').click();
  for (const name of [
    "viridis",
    "inferno",
    "spectrum",
    "grey_inverse",
    "jet",
    "cividis",
  ]) {
    await selectColorMap(page, "Color map", name);
    assert.notEqual(
      await canvas.evaluate((el) => el.toDataURL()),
      renderedBefore,
    );
  }
  await selectColorMap(page, "Color map", "grey");
  await page
    .getByRole("button", { name: "Configure detector display", exact: true })
    .click();
  await page
    .getByLabel("Histogram size", { exact: true })
    .selectOption("compact");
  await page
    .getByLabel("Histogram orientation", { exact: true })
    .selectOption("horizontal");
  await page
    .getByRole("button", {
      name: "Close detector display settings",
      exact: true,
    })
    .click();
  assert.equal(
    await detector.locator(".image-intensity").getAttribute("data-orientation"),
    "horizontal",
  );
  const horizontalBar = await detector
    .getByTestId("intensity-colour-bar")
    .boundingBox();
  const horizontalRegion = await detector
    .getByTestId("intensity-selected-window")
    .boundingBox();
  assert.ok(
    horizontalRegion.y > horizontalBar.y + horizontalBar.height,
    "Horizontal selection must stay below the colour scale",
  );
  const oldUpper = Number(await canvas.getAttribute("data-intensity-max"));
  const horizontalHandle = await page
    .getByRole("slider", { name: "Upper intensity handle", exact: true })
    .boundingBox();
  await page.mouse.move(
    horizontalHandle.x + horizontalHandle.width / 2,
    horizontalHandle.y + horizontalHandle.height / 2,
  );
  await page.mouse.down();
  await page.mouse.move(
    horizontalHandle.x + horizontalHandle.width / 2 + 30,
    horizontalHandle.y + horizontalHandle.height / 2,
    { steps: 5 },
  );
  await page.mouse.up();
  assert.ok(
    Number(await canvas.getAttribute("data-intensity-max")) > oldUpper,
    "Horizontal intensity handle must increase toward the right",
  );
  await page
    .getByRole("button", { name: "Auto intensity", exact: true })
    .click();
  await page.waitForFunction(
    (expected) =>
      +document.querySelector('[data-testid="detector-canvas"]').dataset
        .intensityMax === expected,
    original.image.limits[1],
  );
  await page
    .getByRole("button", { name: "Configure detector display", exact: true })
    .click();
  await page
    .getByLabel("Histogram orientation", { exact: true })
    .selectOption("vertical");
  await page
    .getByRole("button", {
      name: "Close detector display settings",
      exact: true,
    })
    .click();

  // Keep moving without a stationary pause: the former debounce produced no readout here.
  const box = await canvas.boundingBox(),
    started = performance.now();
  const readouts = new Set();
  for (let i = 0; i < 28; i++) {
    await page.mouse.move(
      box.x + box.width * (0.35 + (i / 28) * 0.3),
      box.y + box.height * (0.35 + (i / 28) * 0.3),
    );
    await pause(35);
    readouts.add(await page.getByTestId("mouse-readout").innerText());
  }
  const elapsed = performance.now() - started;
  const requests = pixelRequests.filter((request) => request.time >= started);
  assert.ok(
    readouts.size >= 5,
    `Readout froze during continuous movement: ${[...readouts]}`,
  );
  assert.ok(
    requests.length >= 4 && requests.length <= Math.ceil(elapsed / 100) + 2,
    `${requests.length} pixel reads in ${elapsed} ms`,
  );
  for (let i = 1; i < requests.length; i++)
    assert.ok(
      requests[i].time - requests[i - 1].time >= 80,
      "Pixel requests must be throttled, not queued per event",
    );
  await page.mouse.move(10, 10);
  await pause(120);
  assert.doesNotMatch(
    await page.getByTestId("mouse-readout").innerText(),
    /^x /,
    "Leaving the image clears the readout",
  );
  return [
    "Qt-style ring controls and one task panel",
    "image-side histogram drag / keyboard / auto contrast without source changes",
    "minimal bar controls; configuration dialog, horizontal / vertical layouts and independent image scales",
    `moving pixel readout: ${requests.length} reads in ${(elapsed / 1000).toFixed(2)} s`,
  ];
}

export async function verifyWheelCapture(page) {
  const checks = [];
  for (const id of ["detector-canvas", "cake-canvas", "pattern-canvas"]) {
    if (await page.locator(".integration-layout").count())
      await page
        .getByRole("group", { name: "Integration display", exact: true })
        .getByRole("button", {
          name: id === "cake-canvas" ? "Cake" : "Image",
          exact: true,
        })
        .click();
    const canvas = page.getByTestId(id);
    await canvas.scrollIntoViewIfNeeded();
    await page.evaluate(() => {
      const main = document.querySelector("main");
      main.dataset.oldPosition = main.style.position;
      main.dataset.oldOverflow = main.style.overflowY;
      main.style.position = "relative";
      main.style.overflowY = "auto";
      const spacer = document.createElement("div");
      spacer.id = "wheel-scroll-test";
      Object.assign(spacer.style, {
        position: "absolute",
        top: `${main.scrollHeight + 500}px`,
        height: "600px",
        width: "1px",
      });
      main.append(spacer);
      window.__wheelScrollStart = main.scrollTop;
      window.__wheelScrollSamples = [];
      window.__wheelScrollListener = () =>
        window.__wheelScrollSamples.push(main.scrollTop);
      main.addEventListener("scroll", window.__wheelScrollListener);
    });
    const before = await canvas.evaluate((el) => ({
      min: Number(el.dataset.viewXMin),
      max: Number(el.dataset.viewXMax),
      y: el.getBoundingClientRect().y,
    }));
    const box = await canvas.boundingBox();
    await page.mouse.move(box.x + box.width * 0.5, box.y + box.height * 0.5);
    await page.mouse.wheel(0, -180);
    await pause(150);
    const after = await canvas.evaluate((el) => ({
      min: Number(el.dataset.viewXMin),
      max: Number(el.dataset.viewXMax),
      y: el.getBoundingClientRect().y,
    }));
    assert.ok(
      after.max - after.min < (before.max - before.min) * 0.95,
      `${id}: wheel zoom must act on the plot`,
    );
    await page.mouse.wheel(0, 180);
    await pause(150);
    await page.mouse.wheel(0, 450);
    await pause(150);
    const scroll = await page.evaluate(() => {
      const main = document.querySelector("main");
      const result = {
        start: window.__wheelScrollStart,
        end: main.scrollTop,
        samples: window.__wheelScrollSamples,
      };
      main.removeEventListener("scroll", window.__wheelScrollListener);
      document.querySelector("#wheel-scroll-test").remove();
      main.style.position = main.dataset.oldPosition;
      main.style.overflowY = main.dataset.oldOverflow;
      return result;
    });
    assert.equal(
      scroll.end,
      scroll.start,
      `${id}: wheel must not scroll the workspace`,
    );
    assert.ok(
      scroll.samples.every((value) => value === scroll.start),
      `${id}: transient workspace jump: ${scroll.samples}`,
    );
    assert.equal(
      after.y,
      before.y,
      `${id}: plot position must remain fixed while zooming`,
    );
    checks.push(`${id}: wheel captured without parent scrolling`);
  }
  return checks;
}
