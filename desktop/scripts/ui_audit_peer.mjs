import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import path from "node:path";

export async function verifyPeerFindings({
  page,
  ready,
  invoke,
  root,
  output,
  capture,
}) {
  const button = (name) => page.getByRole("button", { name, exact: true });
  const click = async (name) => {
    await button(name).click();
    await ready();
  };
  const tab = async (name) => {
    await page.getByRole("tab", { name, exact: true }).click();
    await ready();
  };
  await click("Calibration");
  await tab("Step 3: Calibrate");
  assert(
    await page
      .getByRole("heading", { name: "Starting values", exact: true })
      .isVisible(),
  );
  const rotation = page.getByLabel("Rotation 1 constraint value", {
    exact: true,
  });
  const original = await rotation.inputValue();
  const before = (await invoke("state")).state.calibration;
  await rotation.fill("");
  await rotation.pressSequentially("-");
  assert.equal(
    await rotation.inputValue(),
    "",
    "A partial minus is never rewritten as zero",
  );
  assert.equal(await rotation.getAttribute("aria-invalid"), "true");
  assert(await button("Calibrate").isDisabled());
  await capture("calibration-invalid-start");
  await rotation.fill("-0.0123456789012345");
  await click("Mask");
  await click("Integration");
  await click("Calibration");
  await tab("Step 3: Calibrate");
  assert.equal(
    await rotation.inputValue(),
    "-0.0123456789012345",
    "Exact fit drafts survive mode changes",
  );
  assert.deepEqual(
    (await invoke("state")).state.calibration.parameters,
    before.parameters,
  );
  await tab("Step 4: Validate");
  if (!before.fitDirty)
    assert(
      await button("Save .poni calibration").isEnabled(),
      "Unapplied fit seeds do not block saving the current geometry",
    );
  await tab("Step 3: Calibrate");
  await rotation.fill(original);
  const energy = page.getByLabel("Fit energy in kiloelectronvolts", {
    exact: true,
  });
  const energyOriginal = await energy.inputValue();
  await energy.fill("");
  assert(await button("Calibrate").isDisabled());
  assert.equal(await energy.getAttribute("aria-invalid"), "true");
  await energy.fill("5000");
  assert(
    await button("Calibrate").isDisabled(),
    "Finite out-of-range energy cannot bypass wavelength bounds",
  );
  await energy.fill(energyOriginal);
  await energy.fill(energyOriginal);
  // Restore the original wavelength text exactly, avoiding reciprocal roundoff.
  await page
    .getByLabel("Wavelength constraint value", { exact: true })
    .fill(String(before.parameters.wavelength.value));
  await click("Enter manually");
  const modal = page.getByRole("dialog", {
    name: "Enter calibration manually",
    exact: true,
  });
  await modal.getByRole("tab", { name: "pyFAI", exact: true }).click();
  const distance = modal.getByLabel("Manual distance", { exact: true });
  const distanceOriginal = await distance.inputValue();
  await distance.fill("");
  assert(
    await modal
      .getByRole("button", { name: "Apply geometry", exact: true })
      .isDisabled(),
  );
  assert.equal(await distance.getAttribute("aria-invalid"), "true");
  await capture("manual-geometry-invalid");
  await distance.fill("333.1234567890123");
  const box = await modal.boundingBox();
  await page.mouse.click(Math.max(2, box.x - 10), Math.max(2, box.y - 10));
  await ready();
  assert.equal(await modal.count(), 0, "Backdrop closes the dialog");
  await click("Enter manually");
  assert.equal(
    await distance.inputValue(),
    "333.1234567890123",
    "Backdrop dismissal retains exact shared geometry",
  );
  await page.keyboard.press("Escape");
  await ready();
  await tab("Step 4: Validate");
  assert.equal(
    await page.getByLabel("Manual distance", { exact: true }).inputValue(),
    "333.1234567890123",
  );
  const poni = page.getByLabel("Manual poni 1", { exact: true });
  assert.equal(Number(await poni.inputValue()), before.pyfai.poni1 * 1000);
  assert.equal(
    await poni
      .locator("xpath=ancestor::label[1]")
      .locator(".calibration-unit")
      .innerText(),
    "mm",
  );
  await click("Load .poni");
  const replacement = page.getByRole("dialog", {
    name: "Replace unapplied edits?",
    exact: true,
  });
  assert(
    await replacement.isVisible(),
    "Replacing a pending geometry draft requires an explicit choice",
  );
  await capture("draft-replacement-confirmation");
  await replacement
    .getByRole("button", { name: "Cancel", exact: true })
    .click();
  await ready();
  assert.equal(
    await page.getByLabel("Manual distance", { exact: true }).inputValue(),
    "333.1234567890123",
    "Cancel keeps the shared draft",
  );
  await click("Reset geometry draft");
  assert.equal(
    await page.getByLabel("Manual distance", { exact: true }).inputValue(),
    distanceOriginal,
  );
  assert.deepEqual(
    (await invoke("state")).state.calibration.pyfai,
    before.pyfai,
    "Dialog edits never changed applied geometry",
  );
  const editedPoniMm = Number(await poni.inputValue()) + 0.125;
  await poni.fill(String(editedPoniMm));
  await click("Apply geometry");
  const appliedPoni = (await invoke("state")).state.calibration.pyfai.poni1;
  assert(
    Math.abs(appliedPoni - editedPoniMm / 1000) < 1e-15,
    "Displayed mm convert to SI meters only at Apply",
  );
  await page
    .getByLabel("Manual distance", { exact: true })
    .fill("350.1234567890123");
  await tab("Step 3: Calibrate");
  await rotation.fill("-0.03141592653589793");
  await tab("Step 4: Validate");
  await click("Undo");
  assert.equal(
    await page.getByLabel("Manual distance", { exact: true }).inputValue(),
    "350.1234567890123",
    "Undo rebases untouched geometry fields and preserves the deliberate draft",
  );
  await tab("Step 3: Calibrate");
  assert.equal(
    await rotation.inputValue(),
    "-0.03141592653589793",
    "Undo also preserves exact independent fit-seed drafts",
  );
  await rotation.fill(
    String((await invoke("state")).state.calibration.parameters.rot1.value),
  );
  await tab("Step 4: Validate");
  await click("Reset geometry draft");
  assert(
    Math.abs(
      (await invoke("state")).state.calibration.pyfai.poni1 -
        before.pyfai.poni1,
    ) < 1e-15,
    "Undo restores the original PONI coordinate",
  );
  await page.getByLabel("Manual distance", { exact: true }).fill("350");
  await click("Load .poni");
  await replacement
    .getByRole("button", { name: "Load calibration", exact: true })
    .click();
  await ready();
  assert.equal(
    Number(
      await page.getByLabel("Manual distance", { exact: true }).inputValue(),
    ),
    (await invoke("state")).state.calibration.pyfai.dist * 1000,
    "Confirmed source replacement resets the draft to the loaded geometry",
  );
  // A real three-frame HDF5 exercises the model's one-based frame navigation.
  const fixture = path.join(output, "frame-navigation.h5");
  execFileSync(path.join(root, ".venv/bin/python"), [
    "-c",
    `import numpy as np, h5py, sys\nwith h5py.File(sys.argv[1],'w') as f: f.create_dataset('entry/data/data',data=np.arange(3*64*64,dtype=np.uint16).reshape(3,64,64))`,
    fixture,
  ]);
  assert.equal((await invoke("open_image", { path: fixture })).ok, true);
  await page.reload();
  await ready();
  await click("Integration");
  await tab("Image");
  const frame = page.getByLabel("Frame position (1–3)", { exact: true });
  assert.equal(await frame.inputValue(), "1");
  for (const invalid of ["", "0", "4", "1.5"]) {
    await frame.fill(invalid);
    await frame.blur();
    await ready();
    assert.equal(
      (await invoke("state")).state.integration.frame,
      1,
      "Invalid frame never reaches the model",
    );
    assert.equal(await frame.getAttribute("aria-invalid"), "true");
  }
  await capture("integration-frame-validation");
  await frame.fill("2");
  await frame.press("Enter");
  await ready();
  assert.equal((await invoke("state")).state.integration.frame, 2);
  await frame.fill("");
  await frame.press("Escape");
  assert.equal(await frame.inputValue(), "2");
  const directory = page.getByLabel("Image directory", { exact: true });
  assert.equal(
    await directory.getAttribute("title"),
    await directory.inputValue(),
  );
  assert(
    await directory.evaluate(
      (e) => e.scrollWidth <= e.clientWidth || e.scrollLeft > 0,
    ),
    "Unfocused directories reveal the useful tail",
  );
  assert.equal((await invoke("example")).ok, true);
  assert.equal(
    (
      await invoke("open_calibration", {
        path: path.join(root, "dioptas/tests/data/CeO2_Pilatus1M.poni"),
      })
    ).ok,
    true,
  );
  await page.reload();
  await ready();
  return [
    "Undo preserves exact unrelated geometry and fit-seed drafts while rebasing untouched values",
    "Unapplied fit seeds do not block saving current applied geometry",
    "Source replacement asks before discarding drafts; Cancel preserves them and confirmed loading resets them",
    "Finite energy outside the supported wavelength range blocks calibration",
    "Fit seeds retain blank/partial/signed text, expose field errors and survive modes without changing model values",
    "Manual and embedded geometry share exact session drafts through Escape/backdrop dismissal; PONI uses mm consistently",
    "Geometry validation explains invalid fields and blocks Apply before a scientific command",
    "Real multi-frame HDF5 rejects empty/out-of-range/fractional frame positions and commits valid navigation only",
    "Long directory inputs reveal the meaningful tail and retain the full path in their title",
  ];
}
