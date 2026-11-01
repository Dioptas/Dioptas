import assert from "node:assert/strict";

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
  await page.setViewportSize({ width: 1440, height: 1000 });
  const settle = () =>
    page.evaluate(
      () =>
        new Promise((resolve) =>
          requestAnimationFrame(() => requestAnimationFrame(resolve)),
        ),
    );
  await settle();
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
  await page.getByLabel("Radial bins", { exact: true }).fill("360");
  await page.getByLabel("Cake azimuth bins", { exact: true }).fill("60");
  await page.getByLabel("1D azimuth full range", { exact: true }).uncheck();
  await page.getByLabel("1D azimuth minimum (°)", { exact: true }).fill("150");
  await page.getByLabel("1D azimuth maximum (°)", { exact: true }).fill("-150");
  await page.getByLabel("Calculate Poisson errors", { exact: true }).check();
  await click("Apply integration options");
  let current = await invoke("state");
  assert.deepEqual(current.state.integration.azimuthRange, [150, -150]);
  assert.equal(current.state.bins, 360);
  assert.equal(current.cake.height, 60);
  assert.equal(current.cake.step, 1);
  const revision = current.state.revision;
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
  // Settings participates in normal keyboard navigation; the workspace is inert.
  const apply = page.getByRole("button", {
    name: "Apply integration options",
    exact: true,
  });
  await apply.focus();
  await page.keyboard.press("Shift+Tab");
  assert.equal(
    await page
      .getByLabel("Polarization factor", { exact: true })
      .evaluate((el) => el === document.activeElement),
    true,
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
  assert.equal(
    await page.locator(".workspace-content").evaluate((el) => el.inert),
    true,
  );
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
  assert.equal(
    await apply.evaluate((el) => {
      const bounds = el.getBoundingClientRect();
      return bounds.top >= 0 && bounds.bottom <= innerHeight;
    }),
    true,
    "Apply stays visible in a compact window",
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
  await settle();
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
  await click("Add pattern");
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
  await page
    .getByLabel("Subtract automatic pattern background", { exact: true })
    .check();
  await page.getByLabel("Iterations", { exact: true }).fill("10");
  await page.getByLabel("Polynomial order", { exact: true }).fill("5");
  await click("Apply pattern background");
  assert.equal(
    (await invoke("state")).state.integration.patternBackground.enabled,
    true,
  );
  await click("Save background…");
  await tab("Pattern");
  await page.getByLabel("Save background subtracted", { exact: true }).check();
  await click("Save pattern…");
  await click("Load pattern…");
  current = await invoke("state");
  assert.ok(current.pattern.x.length > 10);
  await click("Integrate image ↵");
  await tab("Image");
  await page
    .getByLabel("Image file order", { exact: true })
    .selectOption("time");
  await waitReady();
  assert.equal((await invoke("state")).state.integration.fileIteration, "time");
  if (!(await invoke("state")).state.useMask)
    await page.getByLabel("Apply detector mask", { exact: true }).click();
  await waitReady();
  assert.equal((await invoke("state")).state.useMask, true);
  await tab("Corrections");
  const group = page.locator("details.integration-group").filter({
    has: page.locator("summary", { hasText: "Oblique detector absorption" }),
  });
  await group.locator("summary").click();
  await page.getByLabel("Apply detector absorption", { exact: true }).check();
  await group
    .getByRole("button", { name: "Apply correction", exact: true })
    .click();
  await waitReady();
  assert.equal(
    (await invoke("state")).state.integration.corrections.oiadac.enabled,
    true,
  );
  await openIntegrationSettings(page);
  await page.getByLabel("1D azimuth full range", { exact: true }).check();
  await click("Apply integration options");
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
  return [
    "Settings workspace, stable category bounds, keyboard navigation, compact layout and wrapped azimuth",
    "Qt Image/Cake switching and independent histograms",
    "overlay capture, scale, visibility and rendered curves",
    "phase loading, pressure and rendered reflections",
    "pattern background, save and load",
    "shared mask, file order and detector absorption",
  ];
}
