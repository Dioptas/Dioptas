import { setInterfaceTextSize } from "./plot_navigation.mjs";
import assert from "node:assert/strict";
import path from "node:path";

const settle = (page) =>
  page.evaluate(
    () =>
      new Promise((resolve) =>
        requestAnimationFrame(() => requestAnimationFrame(resolve)),
      ),
  );
export async function verifyIntegrationLayout(page, artifacts) {
  const box = async (selector) => page.locator(selector).boundingBox();
  const checkLayout = async () => {
    const image = await box(".detector-panel"),
      controls = await box(".sidebar"),
      pattern = await box(".pattern-panel");
    assert.ok(
      image.x + image.width <= controls.x + 1,
      "Qt image occupies the left half",
    );
    assert.ok(
      Math.abs(controls.x - pattern.x) < 1 &&
        Math.abs(controls.width - pattern.width) < 1,
      "Controls and pattern share the right column",
    );
    assert.ok(
      controls.y + controls.height <= pattern.y + 1,
      "Qt controls sit above the pattern",
    );
    assert.ok(
      image.height > controls.height + pattern.height - 50,
      "Image fills the full left column",
    );
    assert.ok(
      pattern.height >= 200 && controls.height >= 200,
      "Both right panes remain usable",
    );
    assert.equal(
      await page.evaluate(
        () => document.documentElement.scrollWidth > innerWidth,
      ),
      false,
    );
    const pixels = await page.evaluate(() => window.__detectorDraw);
    assert.ok(
      Math.abs(pixels.sx - pixels.sy) < 1e-6,
      "Detector pixels remain square after pane resizing",
    );
    return { image, controls, pattern };
  };
  await settle(page);
  const initial = await checkLayout();
  assert.ok(
    Math.abs(initial.image.width - initial.controls.width) < 30,
    "Default Qt split is approximately half image / half analysis",
  );
  await page.screenshot({
    path: path.join(artifacts, "integration-qt-layout.png"),
  });
  const horizontal = page.getByRole("separator", {
    name: "Image and analysis divider",
  });
  const vertical = page.getByRole("separator", {
    name: "Controls and pattern divider",
  });
  const dividerBox = await horizontal.boundingBox();
  await page.mouse.move(
    dividerBox.x + dividerBox.width / 2,
    dividerBox.y + dividerBox.height / 2,
  );
  await page.mouse.down();
  await page.mouse.move(
    dividerBox.x - 80,
    dividerBox.y + dividerBox.height / 2,
    { steps: 6 },
  );
  await page.mouse.up();
  await settle(page);
  assert.ok(
    (await box(".detector-panel")).width < initial.image.width - 50,
    "Qt horizontal splitter resizes both columns",
  );
  await horizontal.focus();
  await horizontal.press("Home");
  await vertical.focus();
  await vertical.press("ArrowDown");
  await settle(page);
  assert.ok(
    (await box(".sidebar")).height > initial.controls.height + 5,
    "Qt vertical splitter resizes controls above pattern",
  );
  await vertical.press("Home");
  const display = page.getByRole("group", { name: "Integration display" });
  await display.getByRole("button", { name: "Cake", exact: true }).click();
  assert.equal(await page.getByTestId("detector-canvas").isVisible(), false);
  assert.equal(await page.getByTestId("cake-canvas").isVisible(), true);
  await page.screenshot({
    path: path.join(artifacts, "integration-qt-cake.png"),
  });
  await display.getByRole("button", { name: "Image", exact: true }).click();
  await page.setViewportSize({ width: 1000, height: 760 });
  await settle(page);
  await checkLayout();
  await setInterfaceTextSize(page, true);
  await settle(page);
  await checkLayout();
  await page.screenshot({
    path: path.join(artifacts, "integration-qt-compact-large.png"),
  });
  await setInterfaceTextSize(page, false);
  await page.setViewportSize({ width: 1440, height: 1000 });
  await settle(page);
  return [
    "Qt image-left / controls-upper-right / pattern-lower-right at normal and compact sizes",
    "pointer and keyboard splitters",
    "Image/Cake share the full left pane with independent display state",
  ];
}
