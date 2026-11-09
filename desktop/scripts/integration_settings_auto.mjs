import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";

/** Exercise real Rust settings through the headless UI, including unmounts. */
export async function verifyIntegrationSettingsAuto(page, invoke) {
  const field = (name) => page.getByLabel(name, { exact: true });
  const button = (name) => page.getByRole("button", { name, exact: true });
  const tab = (name) => page.getByRole("tab", { name, exact: true });
  const state = async () => (await invoke("state")).state;
  const until = async (predicate) => {
    for (let i = 0; i < 150; i++) {
      const current = await state();
      if (predicate(current)) {
        await page.waitForFunction(() => !document.querySelector(".spin"));
        return current;
      }
      await page.waitForTimeout(100);
    }
    assert.fail("Integration edit did not reach the native session");
  };
  const open = async () => {
    await button("Settings").click();
    await tab("Integration").click();
  };
  await open();
  assert.equal(await button("Apply integration options").count(), 0);
  assert.equal(await page.getByText(/Current integration:/).count(), 0);
  assert.equal(await field("Integration method").inputValue(), "polygon");
  assert.equal(await field("1D execution layout").inputValue(), "csr");
  for (const layout of ["auto", "csc", "csr"]) {
    await field("1D execution layout").selectOption(layout);
    await until((s) => s.integration.sparseLayout === layout);
    await button("Close settings").click();
    await open();
    assert.equal(await field("1D execution layout").inputValue(), layout);
  }
  await field("1D execution layout").scrollIntoViewIfNeeded();
  await page.screenshot({
    path: fileURLToPath(
      new URL("../artifacts/integration-settings-layout.png", import.meta.url),
    ),
  });
  assert.equal(await field("Subpixels per axis").count(), 0);
  await field("Calculate Poisson errors").uncheck();
  await until((s) => !s.integration.poissonErrors);
  await field("Calculate Poisson errors").check();
  await until((s) => s.integration.poissonErrors);
  await field("Radial coordinate").selectOption("q_A^-1");
  await until((s) => s.unit === "q_A^-1");
  await field("Radial bins").fill("129");
  assert.equal((await state()).bins, 128, "Typing alone does not recalculate");
  await field("Radial bins").press("Enter");
  await until((s) => s.bins === 129);
  await field("Radial bins").fill("0");
  await field("Radial bins").blur();
  await page.waitForTimeout(200);
  assert.equal(
    (await state()).bins,
    129,
    "Invalid edits retain the applied value",
  );
  assert.equal(
    await field("Radial bins").evaluate((e) => e.validity.valid),
    false,
  );
  await field("Radial bins").fill("130");
  await button("Close settings").click();
  await until((s) => s.bins === 130);
  await button("Settings").click();
  assert.equal(await tab("Integration").getAttribute("aria-selected"), "true");
  assert.equal(
    await tab("Integration").evaluate((e) => e === document.activeElement),
    true,
  );
  await tab("Keyboard shortcuts").click();
  await page.keyboard.press("Escape");
  await button("Settings").click();
  assert.equal(
    await tab("Keyboard shortcuts").getAttribute("aria-selected"),
    "true",
  );
  await button("Close settings").click();
  for (const modifier of ["Control", "Meta"]) {
    await page.getByTestId("detector-canvas").focus();
    await page.keyboard.press(`${modifier}+,`);
    await page.getByRole("region", { name: "Settings", exact: true }).waitFor();
    await tab("Integration").click();
    await field("Radial bins").focus();
    await page.keyboard.press(`${modifier}+,`);
    assert.equal(
      await page.getByRole("region", { name: "Settings", exact: true }).count(),
      0,
    );
    await page.keyboard.press(`${modifier}+,`);
    assert.equal(
      await tab("Integration").getAttribute("aria-selected"),
      "true",
    );
    await page.keyboard.press(`${modifier}+,`);
  }
  await page.keyboard.press(",");
  assert.equal(
    await page.getByRole("region", { name: "Settings", exact: true }).count(),
    0,
  );
  await open();
  await field("Radial bins").fill("131");
  await page.keyboard.press("Escape");
  await until((s) => s.bins === 131);
  await open();
  await field("Radial bins").fill("132");
  await button("Calibration").click();
  await until((s) => s.bins === 132);
  await open();
  await field("Cake azimuth bins").fill("37");
  await tab("General").click();
  await until((s) => s.integration.cakeBins === 37);
  await tab("Integration").click();
  await field("Integration method").selectOption("subpixel");
  await until((s) => s.integration.supersampling === 2);
  assert.equal(await field("Subpixels per axis").getAttribute("min"), "2");
  assert.equal(await field("Subpixels per axis").getAttribute("max"), "20");
  await page
    .getByText(/2–20 subpixels per axis \(4–400 sample positions per pixel\)/)
    .waitFor();
  await page.setViewportSize({ width: 1000, height: 760 });
  await page.screenshot({
    path: fileURLToPath(
      new URL(
        "../artifacts/integration-settings-subpixel.png",
        import.meta.url,
      ),
    ),
  });
  await page.setViewportSize({ width: 1500, height: 1000 });
  await field("Subpixels per axis").fill("3");
  await field("Subpixels per axis").press("Enter");
  await until((s) => s.integration.supersampling === 3);
  await field("Integration method").selectOption("polygon");
  await until((s) => s.integration.supersampling === 1);
  assert.equal(await field("Subpixels per axis").count(), 0);
  await page.getByText(/This method has no sampling factor/).waitFor();
  const polygon = await invoke("display_products", { cake: true });
  await field("Integration method").selectOption("pyfai_full");
  await until((s) => s.integration.method === "pyfai_full");
  assert.equal(await field("1D execution layout").isDisabled(), true);
  assert.equal(await field("Subpixels per axis").count(), 0);
  const compatible = await invoke("display_products", { cake: true });
  assert.notDeepEqual(
    compatible.pattern.y,
    polygon.pattern.y,
    "Selecting pyFAI splitting recalculates the 1D pattern",
  );
  assert.notEqual(
    compatible.cake.bufferId,
    polygon.cake.bufferId,
    "The requested cake uses the selected pyFAI splitting",
  );
  await button("Close settings").click();
  await open();
  assert.equal(await field("Integration method").inputValue(), "pyfai_full");
  await page
    .getByText(
      /pyFAI-compatible full pixel splitting for the 1D pattern and cake/,
    )
    .waitFor();
  await page.screenshot({
    path: fileURLToPath(
      new URL("../artifacts/integration-settings-pyfai.png", import.meta.url),
    ),
  });
  await field("Integration method").selectOption("polygon");
  await until((s) => s.integration.method === "polygon");
  assert.equal(await field("1D execution layout").isEnabled(), true);
  // External model updates must rebase without sending the stale form back.
  await button("Close settings").click();
  await button("Integration").click();
  await button("Pattern unit d").click();
  await until((s) => s.unit === "d_A");
  await open();
  assert.equal(await field("Radial coordinate").inputValue(), "d_A");
  await field("Radial bins").fill("133");
  await field("Radial bins").press("Enter");
  await until((s) => s.bins === 133 && s.unit === "d_A");
  await page.setViewportSize({ width: 1000, height: 760 });
  assert.equal(
    await page
      .locator(".integration-settings")
      .evaluate((e) => e.scrollWidth <= e.clientWidth),
    true,
  );
  await page.screenshot({
    path: fileURLToPath(
      new URL("../artifacts/integration-settings-auto.png", import.meta.url),
    ),
  });
  await button("Close settings").click();
  await page.setViewportSize({ width: 1500, height: 1000 });
}
