import assert from "node:assert/strict";

/** Real-model Integration UI checks, composed with the calibration smoke harness. */
export async function verifyIntegrationControls(page, invoke, waitReady) {
  const tab = async (name) =>
    page.getByRole("tab", { name, exact: true }).click();
  const click = async (name) => {
    await page.getByRole("button", { name, exact: true }).click();
    await waitReady();
  };
  await page.setViewportSize({ width: 1440, height: 1000 });
  await tab("Options");
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
  await page.getByLabel("Configure cake display", { exact: true }).click();
  await page.getByLabel("Cake minimum intensity", { exact: true }).fill("10");
  await page.getByLabel("Close cake display settings", { exact: true }).click();
  await tab("Overlay");
  await click("Add pattern");
  await page.getByLabel("Configure cake display", { exact: true }).click();
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
  await tab("Options");
  await page.getByLabel("1D azimuth full range", { exact: true }).check();
  await click("Apply integration options");
  return [
    "Qt control groups and real integration options / wrapped azimuth",
    "Qt Image/Cake switching and independent histograms",
    "overlay capture, scale, visibility and rendered curves",
    "phase loading, pressure and rendered reflections",
    "pattern background, save and load",
    "shared mask, file order and detector absorption",
  ];
}
