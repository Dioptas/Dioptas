import assert from "node:assert/strict";
import path from "node:path";
import {
  verifyCalibrationFits,
  verifyCalibrationSizes,
} from "./calibration_layout.mjs";

export async function verifyCalibrationSetup(
  page,
  invoke,
  artifacts,
  waitReady,
) {
  const button = (name) =>
    page.getByRole(name.startsWith("Step ") ? "tab" : "button", {
      name,
      exact: true,
    });
  const pixelWidth = page.getByLabel("Pixel width in micrometres");
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
  await page.evaluate(() => {
    window.__calibrationInvokeBeforeCancel = window.__dioptasInvoke;
    window.__dioptasInvoke = (command, args) =>
      command === "open_calibration"
        ? { ok: true, cancelled: true }
        : window.__calibrationInvokeBeforeCancel(command, args);
  });
  await button("Load .poni").click();
  await waitReady();
  assert.equal(
    await button("Step 1: Image & setup").getAttribute("aria-selected"),
    "true",
    "Cancelling the calibration chooser preserves the current step",
  );
  await page.evaluate(() => {
    window.__dioptasInvoke = window.__calibrationInvokeBeforeCancel;
    delete window.__calibrationInvokeBeforeCancel;
  });
  const source = await page.locator(".setup-open-image").boundingBox();
  for (const name of ["Previous image", "Next image"]) {
    const rect = await button(name).boundingBox();
    assert.ok(
      rect.x >= source.x + source.width && rect.y < source.y + source.height,
    );
  }
  assert.equal(await page.getByRole("dialog").count(), 0);
  assert.equal(await button("Rotate image +90°").isVisible(), true);
  const shape = (await invoke("state")).state.shape;
  await button("Rotate image +90°").click();
  await waitReady();
  assert.equal(
    await button("Step 1: Image & setup").getAttribute("aria-selected"),
    "true",
    "Transforms must not submit setup",
  );
  assert.deepEqual((await invoke("state")).state.shape, [...shape].reverse());
  await button("Reset image transformations").click();
  await waitReady();
  await page.screenshot({ path: path.join(artifacts, "image-setup.png") });

  const original = (await invoke("state")).state.calibration;
  // Pixel sizes round-trip through metres in Python; allow roundoff in µm.
  const pixelTolerance = 1e-9;
  assert.equal(await button("Apply detector settings").count(), 0);
  assert.equal(
    await page.getByRole("tab", { name: "Start values", exact: true }).count(),
    0,
  );
  assert.equal(
    await page.getByLabel("Wavelength in angstroms", { exact: true }).count(),
    0,
  );
  assert.equal(
    await page.getByLabel("Starting distance in millimetres").count(),
    0,
  );
  assert.equal(await page.getByLabel("Calibrant", { exact: true }).count(), 0);
  const divider = await page.locator(".calibration-tool-divider").boundingBox();
  const reset = await button("Reset image transformations").boundingBox();
  const file = await button("Detector file").boundingBox();
  assert.ok(
    divider.y >= reset.y + reset.height && divider.y + divider.height <= file.y,
  );

  const preset = original.detectors.find((name) => /pilatus.*1m/i.test(name));
  await page.getByLabel("Detector", { exact: true }).selectOption(preset);
  await waitReady();
  assert.equal(await pixelWidth.isDisabled(), true);
  await page.getByLabel("Detector", { exact: true }).selectOption("Custom");
  await waitReady();
  await pixelWidth.fill("");
  await pixelWidth.press("Enter");
  assert.equal(
    await pixelWidth.evaluate((el) => el.validity.valueMissing),
    true,
  );
  assert.equal(
    await button("Step 1: Image & setup").getAttribute("aria-selected"),
    "true",
  );
  await pixelWidth.fill(String(Number(original.pixelX.toPrecision(7))));
  await page
    .getByLabel("Pixel height in micrometres")
    .fill(String(Number(original.pixelY.toPrecision(7))));

  assert.equal(await button("Load custom calibrant…").count(), 0);
  assert.equal(
    await page.getByLabel("Processing engine", { exact: true }).count(),
    0,
  );
  assert.equal(
    await page.getByLabel("Transparent", { exact: true }).isVisible(),
    true,
  );
  assert.equal(await button("More setup options…").count(), 0);
  assert.equal(await page.getByRole("dialog").count(), 0);
  assert.equal(await button("Load mask").isVisible(), true);
  assert.equal(await button("Save mask").count(), 0);
  const useMask = page.getByLabel("Use mask", {
    exact: true,
  });
  const originalUseMask = await useMask.isChecked();
  await useMask.click();
  await waitReady();
  assert.equal((await invoke("state")).state.useMask, !originalUseMask);
  await useMask.click();
  await waitReady();
  await button("Enter manually").click();
  const manual = page.getByRole("dialog");
  await manual.getByRole("tab", { name: "Fit2D", exact: true }).click();
  assert.equal(
    await manual.getByLabel("Manual center x", { exact: true }).isVisible(),
    true,
  );
  await page.keyboard.press("Escape");
  assert.equal(await manual.count(), 0);
  await verifyCalibrationSizes(page, {
    screenshots: artifacts,
    prefix: "image-setup",
  });
  await verifyCalibrationFits(page);
  await pixelWidth.fill(String(original.pixelX + 1));
  assert.ok(
    Math.abs(
      (await invoke("state")).state.calibration.pixelX - original.pixelX,
    ) < pixelTolerance,
    "Editing pixel width must not change the applied value before submission",
  );
  assert.equal(
    await page.getByLabel("Pick peaks", { exact: true }).isDisabled(),
    true,
  );
  await pixelWidth.press("Enter");
  await waitReady();
  assert.ok(
    Math.abs(
      (await invoke("state")).state.calibration.pixelX - (original.pixelX + 1),
    ) < pixelTolerance,
    "Submitted pixel width must match within floating-point roundoff",
  );
  assert.equal(
    await button("Step 1: Image & setup").getAttribute("aria-selected"),
    "true",
    "Automatic detector updates stay on Image",
  );
  await pixelWidth.fill(String(original.pixelX));
  await pixelWidth.press("Tab");
  await waitReady();
  assert.ok(
    Math.abs(
      (await invoke("state")).state.calibration.pixelX - original.pixelX,
    ) < pixelTolerance,
    "Restored pixel width must match within floating-point roundoff",
  );
  assert.equal(
    (await invoke("state")).state.calibration.distance,
    original.distance,
    "Image step only applies detector settings",
  );
  await button("Step 2: Pick rings").click();
  await verifyCalibrationSizes(page, {
    screenshots: artifacts,
    prefix: "pick-sidebar",
  });
  assert.equal(await button("Step 3: Calibrate").isEnabled(), true);
  await button("Step 3: Calibrate").click();
  assert.equal(await button("Calibrate").isDisabled(), true);
  assert.equal(await button("Refine").isVisible(), true);
  assert.equal(await button("Refine").isDisabled(), true);
  assert.match(
    await button("Refine").getAttribute("title"),
    /Calibrate or load a geometry first/,
  );
  await button("Step 2: Pick rings").click();
  return "Reachable controls at 1000×668 with both text sizes; automatic detector updates without navigation, pixel validation, visible transforms, inline mask controls and manual entry";
}
