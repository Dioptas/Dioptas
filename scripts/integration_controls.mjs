import assert from "node:assert/strict";
import { verifyIntegrationPatternFiles } from "./integration_pattern_files.mjs";
import { verifyIntegrationImageFiles } from "./integration_image_files.mjs";
import {
  verifyBackgroundRange,
  verifyBackgroundParameters,
} from "./integration_background_range.mjs";
import { verifyIntegrationRoi } from "./integration_roi.mjs";
import { verifyIntegrationImageExport } from "./integration_image_export.mjs";
import {
  capturePhaseGuideStrokes,
  verifyPhaseGuideStrokes,
} from "./integration_phase_guides.mjs";

const settle = (page) =>
  page.evaluate(
    () =>
      new Promise((resolve) =>
        requestAnimationFrame(() => requestAnimationFrame(resolve)),
      ),
  );

export async function openIntegrationSettings(page) {
  await page.getByRole("button", { name: "Settings", exact: true }).click();
  await page
    .getByRole("region", { name: "Settings", exact: true })
    .getByRole("tab", { name: "Integration", exact: true })
    .click();
}

/** Real-model Integration UI checks, composed with the calibration smoke harness. */
export async function verifyIntegrationControls(page, invoke, waitReady) {
  const tab = async (name) =>
    page.getByRole("tab", { name, exact: true }).click();
  const click = async (name) => {
    await page.getByRole("button", { name, exact: true }).click();
    await waitReady();
  };
  const commit = async () => {
    await page
      .locator(".integration-settings input:focus")
      .evaluateAll((els) => els.forEach((el) => el.blur()));
    await waitReady();
  };
  await page.setViewportSize({ width: 1440, height: 1000 });
  await settle(page);
  await page.getByTestId("detector-canvas").evaluate((el) => {
    window.__settingsDetector = el;
    window.__settingsDetectorRange = [
      el.dataset.viewXMin,
      el.dataset.viewXMax,
      (Number(el.dataset.viewYMin) + Number(el.dataset.viewYMax)) / 2,
    ];
  });
  await openIntegrationSettings(page);
  await page
    .getByLabel("Radial coordinate", { exact: true })
    .selectOption("2th_deg");
  await waitReady();
  await page.getByLabel("Automatic radial binning", { exact: true }).check();
  await commit();
  const automaticBins = (await invoke("state")).state.integration.actualBins;
  assert.ok(automaticBins > 0);
  assert.equal(
    await page.getByLabel("Radial bins", { exact: true }).inputValue(),
    String(automaticBins),
  );
  assert.equal(
    await page.getByLabel("Radial bins", { exact: true }).isDisabled(),
    true,
  );
  await page
    .getByLabel("Integration method", { exact: true })
    .selectOption("subpixel");
  await commit();
  const supersampledBins = (await invoke("state")).state.integration.actualBins;
  assert.notEqual(supersampledBins, automaticBins);
  assert.equal(
    await page.getByLabel("Radial bins", { exact: true }).inputValue(),
    String(supersampledBins),
  );
  await page
    .getByLabel("Integration method", { exact: true })
    .selectOption("polygon");
  await commit();
  await page.getByLabel("Automatic radial binning", { exact: true }).uncheck();
  assert.equal(
    await page.getByLabel("Radial bins", { exact: true }).inputValue(),
    String(automaticBins),
    "Manual binning starts from the current automatic count",
  );
  await page.getByLabel("Radial bins", { exact: true }).fill("360");
  await commit();
  await page.getByLabel("Cake azimuth bins", { exact: true }).fill("60");
  await commit();
  await page.getByLabel("1D azimuth full range", { exact: true }).uncheck();
  await page.getByLabel("1D azimuth minimum (°)", { exact: true }).fill("150");
  await commit();
  await page.getByLabel("1D azimuth maximum (°)", { exact: true }).fill("-150");
  await commit();
  await page.getByLabel("Calculate Poisson errors", { exact: true }).check();
  await commit();
  let current = await invoke("state");
  assert.deepEqual(current.state.integration.azimuthRange, [150, -150]);
  assert.equal(current.state.bins, 360);
  assert.equal(current.cake.height, 60);
  assert.equal(current.cake.step, 1);
  await page
    .getByRole("button", { name: "Close settings", exact: true })
    .click();
  assert.equal(
    await page.getByRole("tab", { name: "Options", exact: true }).count(),
    0,
  );
  await openIntegrationSettings(page);
  assert.equal(
    await page.getByLabel("Radial bins", { exact: true }).inputValue(),
    "360",
  );
  assert.equal(
    await page.getByLabel("Cake azimuth bins", { exact: true }).inputValue(),
    "60",
  );
  await page.getByLabel("Radial bins", { exact: true }).fill("361");
  await page.getByLabel("Radial bins", { exact: true }).press("Enter");
  await waitReady();
  assert.equal((await invoke("state")).state.bins, 361);
  assert.equal(
    await page
      .getByRole("button", { name: "Apply integration options", exact: true })
      .count(),
    0,
  );
  const settingsRegion = page.getByRole("region", {
    name: "Settings",
    exact: true,
  });
  const beforeCategory = await settingsRegion.boundingBox();
  await page.getByRole("tab", { name: "General", exact: true }).click();
  assert.deepEqual(await settingsRegion.boundingBox(), beforeCategory);
  await page
    .getByRole("tab", { name: "Keyboard shortcuts", exact: true })
    .click();
  assert.deepEqual(await settingsRegion.boundingBox(), beforeCategory);
  assert.equal(await page.getByRole("dialog").count(), 0);
  await page.getByRole("tab", { name: "Integration", exact: true }).click();
  assert.equal(
    await page.getByLabel("Radial bins", { exact: true }).inputValue(),
    "361",
  );
  await page.getByLabel("Radial bins", { exact: true }).fill("360");
  await commit();
  assert.equal(
    await page.locator(".workspace-content").evaluate((el) => el.inert),
    true,
  );
  const revision = (await invoke("state")).state.revision;
  await page.keyboard.press("b");
  assert.equal(
    await page
      .getByRole("button", { name: "Mask", exact: true })
      .getAttribute("aria-pressed"),
    "false",
  );
  await page.setViewportSize({ width: 1000, height: 760 });
  assert.equal(
    await page
      .getByRole("region", { name: "Settings", exact: true })
      .evaluate((el) => {
        const bounds = el.getBoundingClientRect();
        return (
          bounds.top >= 0 &&
          bounds.bottom <= innerHeight &&
          el.scrollWidth <= el.clientWidth
        );
      }),
    true,
  );
  await page.screenshot({
    path: new URL("../artifacts/integration-settings.png", import.meta.url)
      .pathname,
  });
  await page.keyboard.press("Escape");
  assert.equal(
    await page
      .getByRole("button", { name: "Settings", exact: true })
      .evaluate((el) => el === document.activeElement),
    true,
  );
  await page.setViewportSize({ width: 1440, height: 1000 });
  await settle(page);
  assert.equal(
    await page
      .getByTestId("detector-canvas")
      .evaluate((el) => el === window.__settingsDetector),
    true,
    "Opening Settings retains the detector renderer",
  );
  assert.deepEqual(
    await page
      .getByTestId("detector-canvas")
      .evaluate((el) => [
        el.dataset.viewXMin,
        el.dataset.viewXMax,
        (Number(el.dataset.viewYMin) + Number(el.dataset.viewYMax)) / 2,
      ]),
    await page.evaluate(() => window.__settingsDetectorRange),
    "Returning from Settings retains detector zoom",
  );
  const display = page.getByRole("group", {
    name: "Integration display",
    exact: true,
  });
  if (await display.getByRole("button", { name: "Image", exact: true }).count())
    await display.getByRole("button", { name: "Image", exact: true }).click();
  assert.equal(await page.getByTestId("cake-canvas").isVisible(), false);
  assert.equal(await page.getByTestId("detector-canvas").isVisible(), true);
  await display.getByRole("button", { name: "Cake", exact: true }).click();
  assert.equal(await page.getByTestId("detector-canvas").isVisible(), false);
  assert.equal(await page.getByTestId("cake-canvas").isVisible(), true);
  assert.equal((await invoke("state")).state.revision, revision);
  assert.equal(await page.locator(".intensity-histogram").count(), 2);
  await page.getByLabel("Cake histogram settings", { exact: true }).click();
  await page.getByLabel("Cake minimum intensity", { exact: true }).fill("10");
  await page.getByLabel("Close cake display settings", { exact: true }).click();
  await tab("Overlay");
  await click("As Overlay");
  await page.getByLabel("Cake histogram settings", { exact: true }).click();
  assert.equal(
    await page
      .getByLabel("Cake minimum intensity", { exact: true })
      .inputValue(),
    "10",
  );
  await page.getByLabel("Close cake display settings", { exact: true }).click();
  assert.equal(
    await page.getByTestId("pattern-canvas").getAttribute("data-curve-count"),
    "1",
  );
  await page.getByLabel("Overlay 1 scale", { exact: true }).fill("1.5");
  await page.getByLabel("Overlay 1 scale", { exact: true }).press("Enter");
  await waitReady();
  assert.equal(
    (await invoke("state")).state.integration.overlays[0].scale,
    1.5,
  );
  await page.getByLabel("Show overlay 1", { exact: true }).click();
  await waitReady();
  assert.equal(
    await page.getByTestId("pattern-canvas").getAttribute("data-curve-count"),
    "0",
  );
  await page.getByLabel("Show overlay 1", { exact: true }).click();
  await waitReady();
  await tab("Phase");
  await click("Add phase…");
  assert.ok(
    Number(
      await page
        .getByTestId("pattern-canvas")
        .getAttribute("data-reference-count"),
    ) > 0,
  );
  await page.getByLabel("Phase 1 pressure (GPa)", { exact: true }).fill("12");
  await page
    .getByLabel("Phase 1 pressure (GPa)", { exact: true })
    .press("Enter");
  await waitReady();
  assert.equal(
    (await invoke("state")).state.integration.phases[0].pressure,
    12,
  );
  await tab("Background");
  await verifyBackgroundParameters(page, invoke, waitReady);
  assert.equal(
    (await invoke("state")).state.integration.patternBackground.enabled,
    true,
  );
  await click("Save background…");
  await tab("Pattern");
  await click("Save pattern");
  await click("Load pattern…");
  current = await invoke("state");
  assert.ok(current.pattern.x.length > 10);
  await verifyIntegrationPatternFiles(page, invoke, waitReady);
  await tab("Image");
  await verifyIntegrationImageFiles(page, invoke, waitReady);
  if (!(await invoke("state")).state.useMask)
    await page.getByLabel("Apply detector mask", { exact: true }).click();
  await waitReady();
  assert.equal((await invoke("state")).state.useMask, true);
  await tab("Corrections");
  await page
    .getByRole("button", { name: "Detector absorption", exact: true })
    .click();
  await page.getByLabel("Apply detector absorption", { exact: true }).check();
  await waitReady();
  assert.equal(
    (await invoke("state")).state.integration.corrections.oiadac.enabled,
    true,
  );
  await openIntegrationSettings(page);
  await page.getByLabel("1D azimuth full range", { exact: true }).check();
  await commit();
  await page
    .getByRole("button", { name: "Close settings", exact: true })
    .click();
  await page.getByRole("button", { name: "Settings", exact: true }).click();
  await page.getByRole("button", { name: "Integration", exact: true }).click();
  assert.equal(
    await page.getByRole("region", { name: "Settings", exact: true }).count(),
    0,
    "Mode navigation returns directly from Settings",
  );
  await verifyIntegrationPlotTools(page, invoke, waitReady);
  await verifyIntegrationImageExport(page, invoke, waitReady);
  return [
    "Image/Cake save: PNG display exports, TIFF data and cake text",
    "Settings workspace, stable category bounds, keyboard navigation, compact layout and wrapped azimuth",
    "Qt Image/Cake switching and independent histograms",
    "overlay capture, scale, visibility and rendered curves",
    "phase loading, pressure, rendered reflections and Qt intensity-scaled image/cake strokes",
    "pattern background, save and load",
    "live background edge fitting, stable release, interior zoom and automatic numeric range edits",
    "automatic background smoothing, iterations and polynomial order; disabled settings and invalid edits",
    "shared mask, file order and detector absorption",
    "Qt plot controls: units, log/sqrt, background inspection, AA, auto/frozen axes, raw image, ROI, phase guides and cake azimuth shift",
  ];
}

async function verifyIntegrationPlotTools(page, invoke, waitReady) {
  const canvas = page.getByTestId("pattern-canvas");
  const click = async (label) => {
    await page.getByRole("button", { name: label, exact: true }).click();
    await waitReady();
  };
  const revision = (await invoke("state")).state.revision;
  if (
    (await page
      .getByRole("button", { name: "Pattern auto range", exact: true })
      .getAttribute("aria-pressed")) !== "true"
  )
    await click("Pattern auto range");
  await click("Square root pattern intensity");
  assert.equal(await canvas.getAttribute("data-intensity-scale"), "sqrt");
  await click("Logarithmic pattern intensity");
  assert.equal(await canvas.getAttribute("data-intensity-scale"), "log");
  assert.equal(
    await page
      .getByRole("button", {
        name: "Square root pattern intensity",
        exact: true,
      })
      .getAttribute("aria-pressed"),
    "false",
  );
  await click("Logarithmic pattern intensity");
  assert.equal(await canvas.getAttribute("data-intensity-scale"), "linear");
  await click("Antialias pattern");
  assert.equal(await canvas.getAttribute("data-antialias"), "false");
  await click("Antialias pattern");
  await click("Inspect pattern background");
  assert.equal(Number(await canvas.getAttribute("data-curve-count")), 2);
  await click("Inspect pattern background");
  assert.equal(
    (await invoke("state")).state.revision,
    revision,
    "Display toggles must not change scientific state",
  );
  await verifyBackgroundRange(page, invoke, waitReady);
  for (const [label, unit] of [
    ["Q", "q_A^-1"],
    ["d", "d_A"],
    ["2θ", "2th_deg"],
  ]) {
    await click(`Pattern unit ${label}`);
    assert.equal((await invoke("state")).state.unit, unit);
  }
  const bounds = () =>
    canvas.evaluate((el) => [
      el.dataset.viewXMin,
      el.dataset.viewXMax,
      el.dataset.viewYMin,
      el.dataset.viewYMax,
    ]);
  const center = await canvas.evaluate((el) => {
    const box = el.getBoundingClientRect();
    return {
      x:
        box.left +
        Number(el.dataset.plotLeft) +
        Number(el.dataset.plotWidth) / 2,
      y:
        box.top +
        Number(el.dataset.plotTop) +
        Number(el.dataset.plotHeight) / 2,
    };
  });
  const autoRangeButton = page.getByRole("button", {
    name: "Pattern auto range",
    exact: true,
  });
  await page.mouse.move(center.x, center.y);
  await page.mouse.wheel(0, -600);
  await settle(page);
  assert.equal(
    await autoRangeButton.getAttribute("aria-pressed"),
    "false",
    "Zooming disables automatic rescaling",
  );
  await page.mouse.click(center.x, center.y, { button: "right" });
  await settle(page);
  assert.equal(
    await autoRangeButton.getAttribute("aria-pressed"),
    "false",
    "A single right-click keeps automatic rescaling disabled",
  );
  const frozen = await bounds();
  await page.getByRole("tab", { name: "Overlay", exact: true }).click();
  await page.getByLabel("Overlay 1 offset", { exact: true }).fill("1000000");
  await page.getByLabel("Overlay 1 offset", { exact: true }).press("Enter");
  await waitReady();
  assert.deepEqual(
    await bounds(),
    frozen,
    "Auto range off preserves the axes across pattern changes",
  );
  // Keep this double-click separate from the preceding single right-click.
  await page.waitForTimeout(460);
  await page.mouse.dblclick(center.x, center.y, { button: "right" });
  await settle(page);
  assert.equal(
    await autoRangeButton.getAttribute("aria-pressed"),
    "true",
    "A right double-click re-enables automatic rescaling",
  );
  assert.equal(await canvas.getAttribute("data-auto-range"), "true");
  await page.waitForFunction(
    (limit) =>
      Number(
        document.querySelector('[data-testid="pattern-canvas"]').dataset
          .viewYMax,
      ) > limit,
    Number(frozen[3]) * 10,
  );
  await page.getByLabel("Overlay 1 offset", { exact: true }).fill("0");
  await page.getByLabel("Overlay 1 offset", { exact: true }).press("Enter");
  await waitReady();
  assert.ok(
    Number((await bounds())[3]) < Number(frozen[3]) * 10,
    "Automatic rescaling continues to follow subsequent pattern changes",
  );
  const display = page.getByRole("group", {
    name: "Integration display",
    exact: true,
  });
  if (await display.getByRole("button", { name: "Image", exact: true }).count())
    await display.getByRole("button", { name: "Image", exact: true }).click();
  assert.equal(
    await page
      .getByRole("button", { name: "Image autoscale", exact: true })
      .count(),
    0,
  );
  assert.equal(
    await page
      .getByRole("button", { name: "Show corrected image", exact: true })
      .count(),
    0,
    "Image background toggle is hidden without an image background",
  );
  await page.getByRole("tab", { name: "Background", exact: true }).click();
  await page
    .getByRole("navigation", { name: "Background type" })
    .getByRole("button", { name: "Image", exact: true })
    .click();
  await click("Load background…");
  await page.getByLabel("Image background scale", { exact: true }).fill("0.1");
  await page
    .getByLabel("Image background scale", { exact: true })
    .press("Enter");
  await waitReady();
  const imageBefore = (
    await page.getByTestId("detector-canvas").screenshot()
  ).toString("base64");
  await click("Show corrected image");
  const imageAfter = (
    await page.getByTestId("detector-canvas").screenshot()
  ).toString("base64");
  assert.notEqual(
    imageAfter,
    imageBefore,
    "Raw and background-subtracted detector displays differ",
  );
  await click("Show corrected image");
  await click("Remove background");
  assert.equal(
    await page
      .getByRole("button", { name: "Show corrected image", exact: true })
      .count(),
    0,
    "Removing the image background hides its display toggle",
  );
  await click("Image region of interest");
  assert.ok((await invoke("state")).state.integration.roi);
  await verifyIntegrationRoi(page, invoke, waitReady);
  await click("Image region of interest");
  assert.equal((await invoke("state")).state.integration.roi, null);
  await capturePhaseGuideStrokes(page);
  await click("Show image phases");
  await page.waitForFunction(
    () =>
      Number(
        document.querySelector('[data-testid="detector-canvas"]').dataset
          .ringCount,
      ) > 0,
  );
  await display.getByRole("button", { name: "Cake", exact: true }).click();
  const beforeShift = (await invoke("state")).state.revision;
  const shiftCake = async (value) =>
    page
      .getByLabel("Cake azimuth shift", { exact: true })
      .evaluate((el, value) => {
        Object.getOwnPropertyDescriptor(
          HTMLInputElement.prototype,
          "value",
        ).set.call(el, value);
        el.dispatchEvent(new Event("input", { bubbles: true }));
      }, value);
  await shiftCake("90");
  await page.waitForFunction(
    () =>
      Number(
        document.querySelector('[data-testid="cake-canvas"]').dataset
          .azimuthMin,
      ) < -200,
  );
  assert.ok(
    Number(
      await page.getByTestId("cake-canvas").getAttribute("data-azimuth-min"),
    ) < -200,
  );
  assert.equal((await invoke("state")).state.revision, beforeShift);
  await shiftCake("0");
  await settle(page);
  await verifyPhaseGuideStrokes(page, invoke);
  await click("Save pattern");
  await click("Show image phases");
  if (await display.getByRole("button", { name: "Image", exact: true }).count())
    await display.getByRole("button", { name: "Image", exact: true }).click();
}
