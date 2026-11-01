import assert from "node:assert/strict";
import path from "node:path";
import { setInterfaceTextSize } from "./plot_navigation.mjs";

export async function verifyCalibrationSetup(
  page,
  invoke,
  artifacts,
  waitReady,
) {
  const button = (name) => page.getByRole("button", { name, exact: true });
  const wavelength = page.getByLabel("Wavelength in angstroms", {
    exact: true,
  });
  const distance = page.getByLabel("Starting distance in millimetres");
  const more = page.locator(".setup-more-options");
  const loadedImage = (await invoke("state")).state;
  assert.equal(await page.title(), `${loadedImage.imageName} — Dioptas`);
  assert.equal(
    await page.locator(".setup-image-filename").textContent(),
    loadedImage.imageName,
  );
  assert.equal(
    await page.locator(".setup-image-filename").getAttribute("title"),
    loadedImage.imagePath,
  );

  assert.equal(
    await page
      .getByRole("heading", { name: "Detector image", exact: true })
      .count(),
    0,
  );
  const sourceBox = await page.locator(".setup-open-image").boundingBox();
  for (const name of ["Previous image", "Next image"]) {
    const navBox = await button(name).boundingBox();
    assert.ok(
      navBox.x >= sourceBox.x + sourceBox.width &&
        navBox.y < sourceBox.y + sourceBox.height,
      "Image navigation sits beside the source button",
    );
  }
  assert.equal(await more.getAttribute("open"), null);
  assert.equal(
    await page.getByLabel("Processing engine", { exact: true }).isVisible(),
    false,
  );
  assert.equal(await button("Rotate image +90°").isVisible(), false);
  assert.equal(await button("Apply setup").count(), 0);
  await button("Apply & pick rings ›").waitFor();
  await page.screenshot({ path: path.join(artifacts, "image-setup.png") });

  // Draft values survive an immediate detector change, and cannot be skipped.
  const original = (await invoke("state")).state.calibration;
  const preset = original.detectors.find((name) => /pilatus.*1m/i.test(name));
  assert.ok(preset, "Pilatus 1M preset is available");
  await wavelength.fill("0.42");
  await page.getByLabel("Detector", { exact: true }).selectOption(preset);
  await waitReady();
  assert.equal(await wavelength.inputValue(), "0.42");
  assert.equal(await button("Step 2: Pick rings").isDisabled(), true);
  await wavelength.evaluate((el) => el.blur());
  await page.keyboard.press("p");
  assert.equal(await wavelength.isVisible(), true);

  // Native form validation must keep invalid setup in view.
  await distance.fill("");
  await button("Apply & pick rings ›").click();
  assert.equal(await distance.isVisible(), true);
  assert.equal(await distance.evaluate((el) => el.validity.valueMissing), true);
  await distance.fill("200");
  await wavelength.fill("0.406626");
  await page.getByLabel("Detector", { exact: true }).selectOption("Custom");
  await waitReady();
  await page
    .getByLabel("Pixel width in micrometres")
    .fill(String(Number(original.pixelX.toPrecision(7))));
  await page
    .getByLabel("Pixel height in micrometres")
    .fill(String(Number(original.pixelY.toPrecision(7))));

  // Every optional tool remains reachable, but starts folded.
  await more.locator(":scope > summary").click();
  await page
    .getByText("Custom calibrant & processing", { exact: true })
    .click();
  assert.equal(
    await page.getByLabel("Processing engine", { exact: true }).isVisible(),
    true,
  );
  await page
    .getByText("Image orientation & detector files", { exact: true })
    .click();
  assert.equal(await button("Rotate image +90°").isVisible(), true);
  await page.getByText("Detector mask", { exact: true }).click();
  assert.equal(
    await page.getByLabel("Transparent mask overlay").isVisible(),
    true,
  );
  await page
    .getByText("Manual geometry · pyFAI / Fit2D", { exact: true })
    .click();
  assert.equal(await page.getByLabel("Geometry convention").isVisible(), true);
  await more.locator(":scope > summary").click();

  await page.setViewportSize({ width: 1000, height: 760 });
  for (const large of [false, true]) {
    await setInterfaceTextSize(page, large);
    const box = await button("Apply & pick rings ›").boundingBox();
    assert.ok(
      box && box.y >= 0 && box.y + box.height <= 760,
      "Continue stays visible",
    );
    await distance.scrollIntoViewIfNeeded();
    assert.equal(await distance.isVisible(), true);
    assert.equal(
      await page
        .locator(".sidebar-scroll")
        .evaluate((el) => el.scrollWidth <= el.clientWidth),
      true,
    );
    await page.locator(".sidebar-scroll").evaluate((el) => (el.scrollTop = 0));
    await page.screenshot({
      path: path.join(
        artifacts,
        `image-setup-compact${large ? "-large" : ""}.png`,
      ),
    });
  }
  await setInterfaceTextSize(page, false);
  await page.setViewportSize({ width: 1440, height: 1000 });

  // The fixed action applies the draft before moving to actual peak picking.
  await distance.fill("210.5");
  await button("Apply & pick rings ›").click();
  await waitReady();
  assert.equal(
    await button("Step 2: Pick rings").getAttribute("aria-pressed"),
    "true",
  );
  assert.equal((await invoke("state")).state.calibration.distance, 210.5);
  await button("Step 1: Image & setup").click();
  await distance.fill("200");
  await button("Apply & pick rings ›").click();
  await waitReady();
  assert.equal(await button("Step 3: Calibrate").isDisabled(), true);
  return "essential setup, folded tools, draft preservation, validation, apply/continue and compact/larger-text layout";
}
