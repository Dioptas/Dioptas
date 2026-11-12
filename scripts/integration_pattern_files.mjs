import assert from "node:assert/strict";
import {
  mkdtemp,
  writeFile,
  realpath,
  utimes,
  access,
  rm,
} from "node:fs/promises";
import path from "node:path";
import os from "node:os";

export async function verifyIntegrationPatternFiles(page, invoke, waitReady) {
  const original = (await invoke("state")).state;
  const folder = await realpath(
    await mkdtemp(path.join(os.tmpdir(), "dioptas-pattern-files-")),
  );
  const panel = page.getByRole("tabpanel", {
    name: "Pattern controls",
    exact: true,
  });
  const file = panel.getByLabel("Pattern filename", { exact: true });
  const directory = panel.getByLabel("Pattern directory", { exact: true });
  const step = panel.getByRole("spinbutton", {
    name: "Pattern file step",
    exact: true,
  });
  const auto = panel.getByRole("checkbox", { name: "Autocreate", exact: true });
  const selectTab = (name) =>
    page.getByRole("tab", { name, exact: true }).click();
  const click = async (name) => {
    await panel.getByRole("button", { name, exact: true }).click();
    await waitReady();
  };
  try {
    await selectTab("Pattern");
    for (const [n, mtime] of [
      [1, 1000],
      [3, 2000],
      [2, 3000],
    ]) {
      const target = path.join(folder, `scan_00${n}.xy`);
      await writeFile(
        target,
        Array.from({ length: 12 }, (_, i) => `${i + 1} ${(i + 1) * n}\n`).join(
          "",
        ),
      );
      await utimes(target, mtime, mtime);
    }
    assert.equal(
      await panel
        .getByRole("button", { name: "Apply autocreate", exact: true })
        .count(),
      0,
    );
    assert.equal(
      await panel
        .getByRole("button", { name: "Save pattern…", exact: true })
        .count(),
      0,
    );
    await click("Choose pattern folder");
    assert.equal(
      await directory.inputValue(),
      (await invoke("state")).state.integration.outputDirectory,
    );
    await directory.fill(folder);
    await directory.press("Enter");
    await waitReady();
    await file.fill("scan_001.xy");
    await file.press("Enter");
    await waitReady();
    assert.equal(
      (await invoke("state")).state.integration.patternPath,
      path.join(folder, "scan_001.xy"),
    );
    await step.fill("1");
    await step.press("ArrowUp");
    assert.equal(await step.inputValue(), "2");
    await selectTab("Image");
    await selectTab("Pattern");
    assert.equal(await step.inputValue(), "2");
    await click("Integration next pattern");
    assert.equal(await file.inputValue(), "scan_003.xy");
    await click("Integration previous pattern");
    assert.equal(await file.inputValue(), "scan_001.xy");
    await step.fill("");
    await step.press("Tab");
    assert.equal(await step.inputValue(), "2");
    await step.fill("1");
    await panel
      .getByRole("combobox", { name: "Pattern file order", exact: true })
      .selectOption("time");
    await waitReady();
    await click("Integration next pattern");
    assert.equal(await file.inputValue(), "scan_003.xy");
    assert.equal(
      (await invoke("state")).state.integration.fileIteration,
      original.integration.fileIteration,
    );
    await panel
      .getByRole("combobox", { name: "Pattern file order", exact: true })
      .selectOption("number");
    await waitReady();
    await file.fill("scan_002.xy");
    await click("Load pattern…");
    assert.equal(await file.inputValue(), "scan_002.xy");
    await file.fill("unfinished edit");
    await file.press("Escape");
    assert.equal(await file.inputValue(), "scan_002.xy");
    await auto.click();
    await waitReady();
    assert.equal((await invoke("state")).state.integration.autoSave, true);
    await panel.getByRole("checkbox", { name: ".chi", exact: true }).click();
    await waitReady();
    assert.ok(
      (await invoke("state")).state.integration.formats.includes(".chi"),
    );
    await selectTab("Image");
    const imageFile = page.getByLabel("Image filename", { exact: true });
    await imageFile.fill(original.imagePath);
    await imageFile.press("Enter");
    await waitReady();
    for (const extension of [".xy", ".chi"])
      await access(
        path.join(folder, path.parse(original.imagePath).name + extension),
      );
    await selectTab("Pattern");
    assert.equal(await auto.isChecked(), true);
    await auto.click();
    await waitReady();
    assert.equal((await invoke("state")).state.integration.autoSave, false);
    await panel.getByRole("checkbox", { name: ".chi", exact: true }).click();
    await waitReady();
  } finally {
    await invoke("integration_autocreate", { enabled: false });
    await invoke("integration_settings", {
      formats: original.integration.formats,
    });
    // Keep the shared smoke session on its original image and a real output folder.
    await invoke("integration_output_directory", {
      path:
        original.integration.outputDirectory ||
        path.dirname(original.imagePath),
    });
    await selectTab("Image");
    const imageFile = page.getByLabel("Image filename", { exact: true });
    await imageFile.fill(original.imagePath);
    await imageFile.press("Enter");
    await waitReady();
    await selectTab("Pattern");
    await rm(folder, { recursive: true, force: true });
  }
  return [
    "Pattern filename/folder entry and native chooser",
    "Real step spinbox, retained step and independent name/time ordering",
    "Immediate Autocreate and format choices write real image integrations",
  ];
}
