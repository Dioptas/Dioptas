import { selectCalibrationRing } from "./calibration_ring_picker.mjs";
import assert from "node:assert/strict";
import { selectIntegrationDisplay } from "./integration_display.mjs";
const pause = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

export async function selectColorMap(page, label, name) {
  await page.getByRole("button", { name: label, exact: true }).click();
  await page
    .getByRole("listbox", { name: `${label} choices`, exact: true })
    .locator(`[role="option"][data-color-map="${name}"]`)
    .click();
  assert.equal(
    await page
      .getByRole("button", { name: label, exact: true })
      .evaluate((el) => getComputedStyle(el).outlineStyle),
    "none",
    "Choosing a colour map with the mouse must not leave a selection outline",
  );
}

export async function verifyImageControls(page, invoke, pixelRequests) {
  const canvas = page.getByTestId("detector-canvas");
  const detector = page.locator(".detector-panel");
  const autoButton = page.getByRole("button", {
    name: "Auto intensity",
    exact: true,
  });
  assert.equal(await autoButton.getAttribute("aria-pressed"), "true");
  assert.equal(
    await detector.locator(".image-intensity").getAttribute("data-size"),
    "compact",
  );
  assert.equal(await canvas.getAttribute("data-intensity-scale"), "linear");
  assert.equal(await detector.locator(".intensity-header").count(), 0);
  await detector.getByTestId("intensity-histogram").click({ button: "right" });
  assert.equal(await page.getByRole("dialog").count(), 0);
  await page
    .getByRole("button", { name: "Detector histogram settings", exact: true })
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
      .getAttribute("aria-haspopup"),
    "listbox",
  );
  await selectCalibrationRing(page, 3);
  assert.equal(
    await page
      .getByLabel("Current calibrant ring", { exact: true })
      .getAttribute("data-ring"),
    "3",
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
  await selectCalibrationRing(page, 1);

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
  const renderedBefore = (await canvas.screenshot()).toString("base64");
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
  assert.equal(await autoButton.getAttribute("aria-pressed"), "false");
  assert.ok(
    Number(await canvas.getAttribute("data-intensity-max")) >
      original.image.limits[1],
  );
  assert.notEqual(
    (await canvas.screenshot()).toString("base64"),
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
  const histogram = detector.getByTestId("intensity-histogram");
  const [dataMin, dataMax] = [
    original.image.histogram.edges[0],
    original.image.histogram.edges.at(-1),
  ];
  for (const orientation of ["horizontal", "vertical"]) {
    const resetRange = async () => {
      await page
        .getByRole("button", {
          name: "Detector histogram settings",
          exact: true,
        })
        .click();
      await page
        .getByLabel("Histogram orientation", { exact: true })
        .selectOption(orientation);
      await page
        .getByLabel("Minimum intensity", { exact: true })
        .fill(String(dataMin));
      await page
        .getByLabel("Maximum intensity", { exact: true })
        .fill(String(dataMax));
      await page
        .getByRole("button", {
          name: "Close detector display settings",
          exact: true,
        })
        .click();
    };
    const dragTo = async (target, beyond, kind) => {
      const box = await target.boundingBox();
      const graph = await histogram.boundingBox();
      const x = box.x + box.width / 2,
        y = box.y + box.height / 2;
      await page.mouse.move(x, y);
      assert.equal(await histogram.getAttribute("data-active-target"), kind);
      assert.equal(
        await histogram.evaluate((el) => getComputedStyle(el).cursor),
        kind === "window"
          ? "grab"
          : orientation === "horizontal"
            ? "ew-resize"
            : "ns-resize",
      );
      if (kind === "window") {
        assert.equal(
          await histogram
            .locator(".intensity-window-feedback")
            .evaluate((el) => getComputedStyle(el).fill),
          "rgba(255, 149, 0, 0.05)",
          "Hovering the middle subtly tints the whole selected range",
        );
      } else {
        assert.equal(
          await target
            .locator(".intensity-handle-line")
            .evaluate((el) => getComputedStyle(el).stroke),
          "rgb(255, 179, 71)",
          "Only the endpoint that will move is highlighted",
        );
        assert.equal(
          await histogram
            .locator('.intensity-handle[data-active="true"]')
            .count(),
          1,
        );
      }
      await page.screenshot({
        path: `artifacts/histogram-${orientation}-${kind}-hover.png`,
      });
      await page.mouse.down();
      await page.mouse.move(
        orientation === "horizontal"
          ? beyond === "max"
            ? graph.x + graph.width + 20
            : graph.x - 20
          : x,
        orientation === "vertical"
          ? beyond === "max"
            ? graph.y - 20
            : graph.y + graph.height + 20
          : y,
        { steps: 8 },
      );
      assert.equal(
        await histogram.getAttribute("data-active-target"),
        kind,
        "The dragged target stays highlighted outside the histogram",
      );
      if (kind === "window")
        assert.equal(
          await histogram.evaluate((el) => getComputedStyle(el).cursor),
          "grabbing",
        );
      await page.mouse.up();
      await page.mouse.move(graph.x - 30, graph.y - 30);
      assert.equal(await histogram.getAttribute("data-active-target"), null);
    };
    for (const [kind, direction] of [
      ["Upper", "max"],
      ["Lower", "min"],
    ]) {
      await resetRange();
      await dragTo(
        page.getByRole("slider", {
          name: `${kind} intensity handle`,
          exact: true,
        }),
        direction,
        direction,
      );
      const limit = Number(
        await canvas.getAttribute(`data-intensity-${direction}`),
      );
      assert.ok(
        direction === "max" ? limit > dataMax : limit < dataMin,
        `${orientation}: ${kind} handle must extend beyond the source histogram`,
      );
    }
    await resetRange();
    const width = Math.asinh(dataMax) - Math.asinh(dataMin);
    await dragTo(
      detector.getByTestId("intensity-selected-window"),
      "max",
      "window",
    );
    const low = Number(await canvas.getAttribute("data-intensity-min"));
    const high = Number(await canvas.getAttribute("data-intensity-max"));
    assert.ok(
      high > dataMax,
      `${orientation}: the whole region must move beyond the source histogram`,
    );
    assert.ok(
      Math.abs(Math.asinh(high) - Math.asinh(low) - width) < 1e-8,
      "Moving the region preserves its width on the histogram axis",
    );
    await resetRange();
    await page
      .getByRole("slider", { name: "Lower intensity handle", exact: true })
      .press("ArrowDown");
    assert.ok(
      Number(await canvas.getAttribute("data-intensity-min")) < dataMin,
      "Keyboard controls can also extend beyond the data range",
    );
  }
  await page
    .getByRole("button", { name: "Auto intensity", exact: true })
    .click();
  await page.waitForFunction(
    (expected) =>
      +document.querySelector('[data-testid="detector-canvas"]').dataset
        .intensityMax === expected,
    original.image.limits[1],
  );
  assert.equal(await autoButton.getAttribute("aria-pressed"), "true");
  await page
    .getByRole("button", { name: "Detector histogram settings", exact: true })
    .click();
  for (const mode of ["minmax", "mean3std", "percentile"]) {
    await page
      .getByLabel("Auto intensity mode", { exact: true })
      .selectOption(mode);
    const expected = (
      await invoke("image_levels", { mode, percentile: 2.5, filter_gaps: true })
    ).levels;
    await page.waitForFunction((expected) => {
      const el = document.querySelector('[data-testid="detector-canvas"]');
      return (
        Math.abs(+el.dataset.intensityMin - expected[0]) < 1e-8 &&
        Math.abs(+el.dataset.intensityMax - expected[1]) < 1e-8
      );
    }, expected);
    assert.equal(await autoButton.getAttribute("aria-pressed"), "true");
  }
  await page.getByLabel("Maximum intensity", { exact: true }).fill("1000");
  await page.getByLabel("Maximum intensity", { exact: true }).press("Enter");
  assert.equal(await autoButton.getAttribute("aria-pressed"), "false");
  await page.getByLabel("Image scale", { exact: true }).selectOption("log");
  await page
    .getByRole("button", {
      name: "Close detector display settings",
      exact: true,
    })
    .click();
  await autoButton.click();
  assert.equal(await autoButton.getAttribute("aria-pressed"), "true");
  await page
    .getByRole("button", { name: "Detector histogram settings", exact: true })
    .click();
  await page.getByLabel("Image scale", { exact: true }).selectOption("linear");
  assert.equal(await autoButton.getAttribute("aria-pressed"), "false");
  await page
    .getByRole("button", {
      name: "Close detector display settings",
      exact: true,
    })
    .click();
  await page.getByRole("button", { name: "Color map", exact: true }).click();
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
      (await canvas.screenshot()).toString("base64"),
      renderedBefore,
    );
  }
  await selectColorMap(page, "Color map", "grey");
  await page
    .getByRole("button", { name: "Detector histogram settings", exact: true })
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
    .getByRole("button", { name: "Detector histogram settings", exact: true })
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

  // Keep moving without a stationary pause: completed samples must stay visible
  // until their replacements arrive, including across the footer throttle.
  const box = await canvas.boundingBox();
  await page.mouse.move(box.x + box.width * 0.35, box.y + box.height * 0.35);
  await page.waitForFunction(() => {
    const el = document.querySelector('[data-testid="mouse-readout"]');
    return el?.dataset.plot === "detector" && /I [-\d]/.test(el.textContent);
  });
  const started = performance.now();
  const readouts = new Set();
  for (let i = 0; i < 28; i++) {
    await page.mouse.move(
      box.x + box.width * (0.35 + (i / 28) * 0.3),
      box.y + box.height * (0.35 + (i / 28) * 0.3),
    );
    await pause(35);
    readouts.add(await page.getByTestId("mouse-readout").innerText());
  }
  assert.ok(
    [...readouts].every((reading) => !/I\s*—/.test(reading)),
    "Moving over finite pixels must not replace completed intensities with a pending placeholder",
  );
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
      await selectIntegrationDisplay(
        page,
        id === "cake-canvas" ? "cake" : "image",
      );
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
