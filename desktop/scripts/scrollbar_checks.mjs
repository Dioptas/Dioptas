import assert from "node:assert/strict";

/** Exercise the real scroll-container styles, including native gutter geometry. */
export async function verifyPersistentScrollbars(page, screenshotPath) {
  await page.evaluate(() => {
    const fixture = document.createElement("section");
    fixture.dataset.testid = "scrollbar-fixture";
    fixture.className = "app integration-controls";
    fixture.style.cssText =
      "position:fixed;inset:20px;z-index:9999;background:#202226;padding:20px;display:grid;grid-template-columns:repeat(3,minmax(0,1fr));align-content:start;gap:16px;overflow:auto";
    const cases = [
      ["Image tab", "integration-fieldset integration-tab-image"],
      ["Phase parameters", "phase-step-controls"],
      ["Overlay parameters", "qt-overlay-parameter-scroll"],
      ["Settings", "settings-general"],
      ["Scientific table", "data-table-scroll"],
      ["Dialog content", "ui-shortcuts-content"],
      ["Horizontal table", "data-table-scroll", "horizontal"],
      ["Both axes", "data-table-scroll", "both"],
      ["No overflow", "integration-fieldset", "none"],
    ];
    for (const [name, className, axis = "vertical"] of cases) {
      const section = document.createElement("section");
      const heading = document.createElement("h3");
      heading.textContent = name;
      section.append(heading);
      const scroller = document.createElement("div");
      scroller.className = className;
      scroller.dataset.scrollCase = name;
      scroller.dataset.axis = axis;
      scroller.style.cssText =
        "width:100%;height:120px;max-height:120px;min-height:0;margin:0;padding:6px;border:1px solid #41484f";
      if (axis === "horizontal") scroller.style.height = "48px";
      const content = document.createElement("div");
      content.style.cssText = "display:grid;gap:4px;flex-shrink:0;min-width:0";
      if (axis === "both" || axis === "horizontal") {
        content.style.width = "650px";
        content.style.minWidth = "650px";
      }
      const count = axis === "none" || axis === "horizontal" ? 1 : 10;
      for (let i = 0; i < count; i++) {
        const row = document.createElement("div");
        row.textContent = `Visible content ${i + 1}`;
        row.style.cssText =
          "height:28px;min-height:28px;border:1px solid #41484f;padding:3px;box-sizing:border-box";
        content.append(row);
      }
      if (name === "Settings") {
        const nested = document.createElement("div");
        nested.className = "data-table-scroll";
        nested.dataset.scrollCase = "Nested list";
        nested.dataset.axis = "vertical";
        nested.style.cssText =
          "height:70px;min-height:0;overflow:auto;border:1px solid #41484f";
        const rows = content.cloneNode(true);
        nested.append(rows);
        content.prepend(nested);
      }
      scroller.append(content);
      section.append(scroller);
      fixture.append(section);
    }
    document.body.append(fixture);
  });
  try {
    // Move away and leave the controls idle: visibility must not depend on hover
    // or on a recent wheel/trackpad gesture.
    await page.mouse.move(0, 0);
    await page.waitForTimeout(1200);
    const measurements = await page
      .locator("[data-scroll-case]")
      .evaluateAll((elements) =>
        elements.map((element) => {
          const style = getComputedStyle(element);
          return {
            name: element.dataset.scrollCase,
            axis: element.dataset.axis,
            vertical: element.scrollHeight > element.clientHeight,
            horizontal: element.scrollWidth > element.clientWidth,
            width:
              element.offsetWidth -
              element.clientWidth -
              parseFloat(style.borderLeftWidth) -
              parseFloat(style.borderRightWidth),
            height:
              element.offsetHeight -
              element.clientHeight -
              parseFloat(style.borderTopWidth) -
              parseFloat(style.borderBottomWidth),
            scrollbarWidth: style.scrollbarWidth,
            scrollbarColor: style.scrollbarColor,
          };
        }),
      );
    for (const item of measurements) {
      assert.equal(item.scrollbarWidth, "auto", item.name);
      assert.equal(item.scrollbarColor, "auto", item.name);
      if (["vertical", "both"].includes(item.axis)) {
        assert.equal(item.vertical, true, item.name);
        assert.equal(
          item.width,
          12,
          `${item.name}: vertical bar reserves its own space`,
        );
      }
      if (["horizontal", "both"].includes(item.axis)) {
        assert.equal(item.horizontal, true, item.name);
        assert.equal(
          item.height,
          12,
          `${item.name}: horizontal bar reserves its own space`,
        );
      }
      if (item.axis === "vertical")
        assert.equal(
          item.horizontal,
          false,
          `${item.name}: content fits inside the scrollbar`,
        );
      if (item.axis === "none") {
        assert.equal(item.vertical, false, item.name);
        assert.equal(item.horizontal, false, item.name);
      }
    }
    await page
      .getByTestId("scrollbar-fixture")
      .screenshot({ path: screenshotPath });
  } finally {
    await page
      .getByTestId("scrollbar-fixture")
      .evaluate((element) => element.remove());
  }
}
