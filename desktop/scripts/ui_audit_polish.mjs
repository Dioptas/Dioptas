import assert from "node:assert/strict";
import path from "node:path";

export async function verifyPolish({ page, ready, invoke, output }) {
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
  await tab("Step 4: Validate");
  await tab("pyFAI");
  const rotation = page.getByLabel("Manual rotation 1", { exact: true });
  const initial = await rotation.inputValue();
  const original = (await invoke("state")).state.geometry;
  await rotation.fill("0.0123456789012345");
  for (const mode of ["Integration", "Mask", "Map"]) await click(mode);
  await click("Settings");
  await page.keyboard.press("Escape");
  await ready();
  await click("Calibration");
  await tab("Step 4: Validate");
  assert.equal(
    await rotation.inputValue(),
    "0.0123456789012345",
    "Switching modes and Settings keeps the exact geometry draft",
  );
  assert(await button("Save .poni calibration").isDisabled());
  assert.deepEqual(
    (await invoke("state")).state.geometry,
    original,
    "Navigation never applies an unfinished geometry draft",
  );
  await tab("Fit2D");
  assert(
    (await page
      .getByLabel("Manual direct distance", { exact: true })
      .getAttribute("readonly")) !== null,
  );
  assert(await button("Apply geometry").isDisabled());
  await tab("pyFAI");
  await click("Reset geometry draft");
  assert.equal(await rotation.inputValue(), initial);
  assert.deepEqual(
    (await invoke("state")).state.geometry,
    original,
    "Reset changes the draft only",
  );
  const scientific = page.getByLabel("Manual rotation 3", { exact: true });
  const preview = scientific.locator("..");
  if ((await scientific.inputValue()).toLowerCase().includes("e")) {
    assert(
      await preview.locator(".scientific-number-exponent").count(),
      "Compact notation keeps its order of magnitude separate from truncated digits",
    );
  }
  await rotation.blur();
  const resting = await rotation.evaluate((element) => ({
    edge: getComputedStyle(element).borderTopColor,
    background: getComputedStyle(element).backgroundColor,
  }));
  assert.match(
    resting.edge,
    /rgba\(0, 0, 0, 0\)|transparent/,
    "Resting text inputs have no pale outline",
  );
  await rotation.focus();
  const focus = await rotation.evaluate(
    (element) => getComputedStyle(element).outlineColor,
  );
  assert.notEqual(
    focus,
    "rgba(0, 0, 0, 0)",
    "Focused input keeps a visible indicator",
  );
  await rotation.blur();
  await page.screenshot({
    path: path.join(output, "geometry-draft-restored.png"),
  });
  await click("Integration");
  await tab("Pattern");
  await ready();
  const divider = page.getByRole("separator", {
    name: "Controls and pattern divider",
    exact: true,
  });
  await divider.focus();
  const originalSplit = Number(await divider.getAttribute("aria-valuenow"));
  await page.keyboard.press("ArrowDown");
  assert(Number(await divider.getAttribute("aria-valuenow")) > originalSplit);
  await page.keyboard.press("Home");
  assert.equal(Number(await divider.getAttribute("aria-valuenow")), 38);
  await divider.blur();
  const legend = page.getByRole("group", {
    name: "Pattern legend",
    exact: true,
  });
  const canvas = page.getByTestId("pattern-canvas");
  const before = await canvas.evaluate((element) => ({
    top: Number(element.dataset.plotTop),
    range: [
      element.dataset.viewXMin,
      element.dataset.viewXMax,
      element.dataset.viewYMin,
      element.dataset.viewYMax,
    ],
  }));
  assert(before.top < 25, "No legend header takes space away from the data");
  const overlayOrdinal =
    (await invoke("state")).state.integration.overlays.length + 1;
  await click("As Overlay");
  assert.equal(
    await canvas.evaluate((element) => Number(element.dataset.plotTop)),
    before.top,
    "Adding an overlay never reserves a legend header",
  );

  await legend.focus();
  await page.keyboard.press("ArrowLeft");
  await page.keyboard.press("ArrowDown");
  assert.notEqual(await legend.getAttribute("data-legend-offset"), "0,0");
  const after = await canvas.evaluate((element) => [
    element.dataset.viewXMin,
    element.dataset.viewXMax,
    element.dataset.viewYMin,
    element.dataset.viewYMax,
  ]);
  assert.deepEqual(
    after,
    before.range,
    "Moving a legend never pans the scientific data",
  );
  await page.keyboard.press("Home");
  assert.equal(await legend.getAttribute("data-legend-offset"), "0,0");
  await legend.hover();
  await ready();
  const legendBox = await legend.boundingBox();
  await page.mouse.move(legendBox.x + 8, legendBox.y + 8);
  await page.mouse.down();
  await page.mouse.move(legendBox.x + 9, legendBox.y + 9);
  await page.mouse.up();
  assert.equal(
    await legend.getAttribute("data-manual-position"),
    "false",
    "A focus click with hand jitter does not pin the legend",
  );
  await legend.focus();
  await page.keyboard.press("ArrowLeft");
  assert.equal(
    await legend.getAttribute("data-manual-position"),
    "true",
    "An explicit keyboard move pins the position",
  );
  await page.keyboard.press("Home");
  assert.equal(
    await legend.getAttribute("data-manual-position"),
    "false",
    "Home restores automatic placement",
  );
  await legend.blur();
  await canvas.focus();
  const revision = (await invoke("state")).state.revision;
  await page.keyboard.press("Alt+Home");
  const index = Number(await canvas.getAttribute("data-keyboard-sample"));
  assert(Number.isInteger(index));
  assert.match(
    await page.locator(".plot-keyboard-reading").innerText(),
    /sample.*Intensity/,
  );
  const source = (await invoke("state")).pattern;
  assert(
    source,
    "Real model pattern is available for independent sample-value comparison",
  );
  if (source) {
    assert.equal(
      Number(await canvas.getAttribute("data-keyboard-x")),
      source.x[index],
    );
    assert.equal(
      Number(await canvas.getAttribute("data-keyboard-y")),
      source.y[index],
    );
  }
  await page.keyboard.press("Alt+ArrowRight");
  assert(
    Number(await canvas.getAttribute("data-keyboard-x")) >= source.x[index],
  );
  assert.deepEqual(
    await canvas.evaluate((element) => [
      element.dataset.viewXMin,
      element.dataset.viewXMax,
      element.dataset.viewYMin,
      element.dataset.viewYMax,
    ]),
    before.range,
    "Inspecting samples does not pan or zoom",
  );
  assert.equal(
    (await invoke("state")).state.revision,
    revision,
    "Keyboard inspection never changes scientific state",
  );
  await canvas.blur();
  await canvas.focus();
  await page.keyboard.press("Alt+ArrowRight");
  await page.waitForFunction(
    () =>
      document
        .querySelector('[data-testid="mouse-readout"]')
        ?.getAttribute("data-plot") === "pattern",
  );
  await page.screenshot({
    path: path.join(output, "keyboard-sample-inspection.png"),
  });
  const { writeFile } = await import("node:fs/promises");
  await writeFile(
    path.join(output, "keyboard-sample-inspection.aria.yml"),
    await page.locator("body").ariaSnapshot(),
  );
  await canvas.blur();
  await click("Pattern unit d");
  await canvas.focus();
  await page.keyboard.press("Alt+Home");
  const lowD = Number(await canvas.getAttribute("data-keyboard-x"));
  await page.keyboard.press("Alt+ArrowRight");
  assert(
    Number(await canvas.getAttribute("data-keyboard-x")) >= lowD,
    "Descending source coordinates still inspect left to right",
  );
  await canvas.blur();
  await click("Pattern unit 2θ");
  await tab("Overlay");
  const scale = page.getByLabel(`Overlay ${overlayOrdinal} scale`, {
    exact: true,
  });
  await scale.fill("2");
  await scale.press("Enter");
  await ready();
  await page
    .getByRole("checkbox", { name: "Original pattern", exact: true })
    .uncheck();
  await ready();
  await page
    .locator(".qt-overlay-table-scroll tr")
    .nth(overlayOrdinal - 1)
    .click();
  await ready();
  await tab("Pattern");
  await canvas.focus();
  await page.keyboard.press("Alt+Home");
  const overlayIndex = Number(
    await canvas.getAttribute("data-keyboard-sample"),
  );
  const originalPattern = (await invoke("state")).pattern;
  assert.equal(
    Number(await canvas.getAttribute("data-keyboard-y")),
    2 * originalPattern.y[overlayIndex],
    "When the original is hidden, inspection uses the visible scaled overlay",
  );
  await canvas.blur();
  await tab("Overlay");
  await page
    .getByRole("checkbox", { name: "Original pattern", exact: true })
    .check();
  await ready();
  await scale.fill("1");
  await scale.press("Enter");
  await ready();
  await tab("Pattern");

  await page.screenshot({
    path: path.join(output, "integration-overlay-legend.png"),
  });
  return [
    "Exact geometry drafts survive all modes and Settings without changing model geometry; Reset is explicit",
    "Shared pane dividers resize by keyboard and reset predictably",
    "Resting inputs are quiet; focused inputs retain a visible indicator",
    "Sample inspection follows descending axes and the visible scaled overlay when the original is hidden",
    "Keyboard sample inspection exposes real x/intensity values and announces them without changing view or scientific state",
    "Legend stays inside the plot without a reserved header; keyboard movement leaves data ranges unchanged",
  ];
}
