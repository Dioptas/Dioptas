import assert from "node:assert/strict";
import { mkdtemp, copyFile, rm, realpath } from "node:fs/promises";
import path from "node:path";
import os from "node:os";

/** Real-model file entry, native stepper and incoming-folder workflow. */
export async function verifyIntegrationImageFiles(page, invoke, waitReady) {
  const original = (await invoke("state")).state;
  const folder = await realpath(
    await mkdtemp(path.join(os.tmpdir(), "dioptas-image-files-")),
  );
  const panel = page.getByRole("tabpanel", {
    name: "Image controls",
    exact: true,
  });
  const filename = panel.getByLabel("Image filename", { exact: true });
  const location = panel.getByLabel("Image location", { exact: true });
  const auto = panel.getByRole("checkbox", {
    name: "Autoprocess",
    exact: true,
  });
  const step = panel.getByRole("spinbutton", {
    name: "File step",
    exact: true,
  });
  const source = original.imagePath;
  try {
    assert.equal(
      await panel
        .getByRole("button", { name: "Load mask…", exact: true })
        .count(),
      0,
    );
    assert.equal(
      await panel
        .getByRole("button", { name: "Integrate folder…", exact: true })
        .count(),
      0,
    );
    await step.fill("1");
    await step.press("ArrowUp");
    assert.equal(await step.inputValue(), "2");
    await step.press("ArrowDown");
    assert.equal(await step.inputValue(), "1");
    await step.fill("");
    await step.press("Tab");
    assert.equal(await step.inputValue(), "1");
    await step.fill("0");
    await step.press("Enter");
    assert.equal(await step.inputValue(), "1");
    const aligned = await step.evaluate((input) => {
      const range = document.createRange();
      range.selectNodeContents(input.parentElement.firstChild);
      const text = range.getBoundingClientRect(),
        box = input.getBoundingClientRect();
      return (
        box.left - text.right >= 4 &&
        box.left - text.right <= 7 &&
        Math.abs(text.y + text.height / 2 - box.y - box.height / 2) < 2
      );
    });
    assert.ok(
      aligned,
      "Step label sits directly beside the spinbox and shares its vertical center",
    );
    await panel
      .getByRole("button", { name: "Choose image folder", exact: true })
      .click();
    await waitReady();
    assert.ok(
      (await location.textContent()).includes(
        (await invoke("state")).state.integration.imageDirectory,
      ),
    );
    await copyFile(source, path.join(folder, "acquisition_001.tif"));
    await filename.fill(path.join(folder, "acquisition_001.tif"));
    await filename.press("Enter");
    await waitReady();
    assert.equal(
      (await invoke("state")).state.integration.imageDirectory,
      folder,
    );
    await filename.fill("acquisition_001.tif");
    await filename.press("Enter");
    await waitReady();
    assert.equal(
      (await invoke("state")).state.imagePath,
      path.join(folder, "acquisition_001.tif"),
    );
    for (const name of ["By Time", "By Name"]) {
      await panel
        .getByRole("combobox", { name: "Image file order", exact: true })
        .selectOption(name === "By Time" ? "time" : "number");
      await waitReady();
      assert.equal(
        (await invoke("state")).state.integration.fileIteration,
        name === "By Time" ? "time" : "number",
      );
    }
    await auto.click();
    await waitReady();
    assert.equal(await auto.isChecked(), true);
    await copyFile(source, path.join(folder, "acquisition_002.tif"));
    await page.waitForFunction(
      () =>
        document.querySelector('[aria-label="Image filename"]').value ===
        "acquisition_002.tif",
      null,
      { timeout: 15000 },
    );
    await waitReady();
    const processed = await invoke("state");
    assert.equal(processed.state.imageName, "acquisition_002.tif");
    assert.ok(processed.pattern.x.length > 10);
    await auto.click();
    await waitReady();
    assert.equal(await auto.isChecked(), false);
    await copyFile(source, path.join(folder, "acquisition_003.tif"));
    await filename.fill("acquisition_003.tif");
    await panel
      .getByRole("button", { name: "Load image…", exact: true })
      .click();
    await waitReady();
    assert.equal(
      (await invoke("state")).state.imageName,
      "acquisition_003.tif",
    );
    await filename.fill("unfinished edit");
    await filename.press("Escape");
    assert.equal(await filename.inputValue(), "acquisition_003.tif");
  } finally {
    // Restore the shared smoke session before removing only this test's files.
    await invoke("integration_autoprocess", { enabled: false });
    await filename.fill(source);
    await filename.press("Enter");
    await waitReady();
    await rm(folder, { recursive: true, force: true });
  }
  return [
    "Real spinbox and aligned label",
    "Folder chooser and exact filename loading via Enter/Load",
    "Autoprocess loads and integrates new files; disable and Escape work",
  ];
}
