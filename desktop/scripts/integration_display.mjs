import assert from "node:assert/strict";

/** The single switch names the other view; selecting the current view is a no-op. */
export async function selectIntegrationDisplay(page, view) {
  assert.ok(view === "image" || view === "cake");
  const layout = page.locator(".integration-layout");
  const current = await layout.getAttribute("data-integration-display");
  assert.ok(current === "image" || current === "cake");
  const button = page
    .getByRole("group", { name: "Integration display", exact: true })
    .getByRole("button");
  assert.equal(await button.count(), 1);
  assert.equal(
    await button.innerText(),
    current === "image" ? "Cake" : "Image",
  );
  if (current !== view) await button.click();
  await page
    .getByTestId(view === "image" ? "detector-canvas" : "cake-canvas")
    .waitFor();
  assert.equal(await layout.getAttribute("data-integration-display"), view);
  assert.equal(await button.innerText(), view === "image" ? "Cake" : "Image");
}
