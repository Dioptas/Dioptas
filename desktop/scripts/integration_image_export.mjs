import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { selectIntegrationDisplay } from "./integration_display.mjs";

export async function verifyIntegrationImageExport(page, invoke, waitReady) {
  const toolbar = page.getByRole("group", {
    name: "Integration image controls",
    exact: true,
  });
  assert.equal(
    await toolbar.getByRole("button").first().getAttribute("aria-label"),
    "Save image",
  );
  for (const source of ["image", "cake"]) {
    await selectIntegrationDisplay(page, source);
    const state = (await invoke("state")).state;
    const canvas = page.getByTestId(
      source === "image" ? "detector-canvas" : "cake-canvas",
    );
    const range = () =>
      canvas.evaluate((el) => [
        el.dataset.viewXMin,
        el.dataset.viewXMax,
        el.dataset.viewYMin,
        el.dataset.viewYMax,
      ]);
    const before = await range();
    await toolbar
      .getByRole("button", { name: "Save image", exact: true })
      .click();
    await waitReady();
    const saved = await readFile(
      new URL(`../artifacts/saved-${source}.png`, import.meta.url),
    );
    assert.equal(saved.subarray(1, 4).toString(), "PNG");
    assert.equal(
      saved.readUInt32BE(16),
      2048,
      "Match Qt's 2048-pixel PNG width",
    );
    assert.ok(saved.readUInt32BE(20) > 0);
    assert.deepEqual(
      await range(),
      before,
      "Export retains the visible plot range",
    );
    assert.deepEqual(
      (await invoke("state")).state,
      state,
      "Saving does not change the scientific model",
    );
  }
  await selectIntegrationDisplay(page, "image");
  return [
    "Image/Cake save action first in toolbar; 2048-pixel PNGs and unchanged model/view",
  ];
}
