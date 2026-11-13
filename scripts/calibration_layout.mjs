import assert from "node:assert/strict";
import { setInterfaceTextSize } from "./plot_navigation.mjs";

export async function verifyCalibrationFits(page) {
  await page.evaluate(
    () =>
      new Promise((resolve) =>
        requestAnimationFrame(() => requestAnimationFrame(resolve)),
      ),
  );
  const navigation = page.getByRole("tablist", {
    name: "Calibration sections",
    exact: true,
  });
  const tabs = await navigation.getByRole("tab").all();
  assert.equal(tabs.length, 4);
  const navigationBounds = await navigation.boundingBox();
  const panelBounds = await page
    .locator(".calibration-task-panel")
    .boundingBox();
  const contentBounds = await page
    .locator("#calibration-task-content")
    .boundingBox();
  assert.ok(
    navigationBounds.x >= panelBounds.x &&
      navigationBounds.x + navigationBounds.width <=
        panelBounds.x + panelBounds.width + 1 &&
      navigationBounds.y >= panelBounds.y &&
      navigationBounds.y + navigationBounds.height <= contentBounds.y + 1,
    "Calibration sections stay at the top of the right panel, above its controls",
  );
  for (const tab of tabs) {
    const bounds = await tab.boundingBox();
    assert.ok(
      bounds.y >= navigationBounds.y &&
        bounds.y + bounds.height <=
          navigationBounds.y + navigationBounds.height + 1,
    );
    assert.ok(await tab.evaluate((el) => el.scrollWidth <= el.clientWidth));
  }
  const ringControls = page.getByRole("group", {
    name: "Ring picking",
    exact: true,
  });
  const ringBounds = await ringControls.boundingBox();
  assert.ok(
    Math.abs(ringBounds.y - panelBounds.y) <= 1 &&
      ringBounds.y + ringBounds.height <= navigationBounds.y + 1,
    "Ring picking stays above every calibration tab",
  );
  assert.equal(
    await ringControls
      .getByLabel("Current calibrant ring", { exact: true })
      .count(),
    1,
  );
  assert.ok(
    await ringControls
      .getByLabel("Automatically advance ring number", { exact: true })
      .isVisible(),
  );
  assert.ok(
    await page
      .getByRole("button", { name: "Save .poni calibration", exact: true })
      .isVisible(),
  );
  assert.equal(
    await page
      .locator(".calibration-task-footer")
      .getByRole("button", { name: /^(‹ Back|Next:)/ })
      .count(),
    0,
  );
  for (const button of await page
    .locator(".calibration-main-action button")
    .all()) {
    const bounds = await button.boundingBox();
    assert.ok(
      bounds.x >= panelBounds.x &&
        bounds.x + bounds.width <= panelBounds.x + panelBounds.width + 1,
    );
    assert.ok(
      await button.evaluate((el) => el.scrollWidth <= el.clientWidth),
      "Calibration actions fit at both text sizes",
    );
  }
  const result = await page
    .locator(".calibration-task-panel .sidebar-scroll")
    .evaluate((body) => {
      const bounds = body.getBoundingClientRect();
      const scrolls = getComputedStyle(body).overflowY === "auto";
      const clipped = [
        ...body.querySelectorAll(
          "input, select, button, .control-note, .no-peaks, .pick-position",
        ),
      ]
        .filter((el) => {
          if (el.closest("dialog") || !el.getClientRects().length) return false;
          const rect = el.getBoundingClientRect();
          const list = el
            .closest(".peak-list, .calibration-fit-controls")
            ?.getBoundingClientRect();
          if (list || scrolls) {
            const horizontalBounds = list ?? bounds;
            return (
              rect.left < horizontalBounds.left - 1 ||
              rect.right > horizontalBounds.right + 1
            );
          }
          return (
            rect.bottom > bounds.bottom + 1 ||
            rect.top < bounds.top - 1 ||
            rect.left < bounds.left - 1 ||
            rect.right > bounds.right + 1
          );
        })
        .map((el) => el.getAttribute("aria-label") || el.textContent.trim());
      return {
        scrolls,
        scrollbarWidth: body.offsetWidth - body.clientWidth,
        verticalOverflow: body.scrollHeight - body.clientHeight,
        horizontalOverflow: body.scrollWidth - body.clientWidth,
        clipped,
      };
    });
  if (!result.scrolls)
    assert.ok(result.verticalOverflow <= 1, JSON.stringify(result));
  else if (result.verticalOverflow > 1)
    assert.ok(
      result.scrollbarWidth > 0,
      "Overflowing setup/geometry forms have a visible scrollbar",
    );
  assert.ok(result.horizontalOverflow <= 1, JSON.stringify(result));
  assert.deepEqual(
    result.clipped,
    [],
    "Calibration forms and peak rows remain reachable without horizontal clipping",
  );
  const fitControls = page.locator(".calibration-fit-controls");
  if (await fitControls.count()) {
    const scroll = await fitControls.evaluate((el) => ({
      overflow: el.scrollHeight - el.clientHeight,
      scrollbarWidth: el.offsetWidth - el.clientWidth,
    }));
    if (scroll.overflow > 1)
      assert.ok(
        scroll.scrollbarWidth > 0,
        "Overflowing fit controls show a scrollbar without hovering or scrolling",
      );
    const footer = page.locator(".calibration-task-footer");
    const before = await footer.boundingBox();
    const bottomControl = fitControls.locator("input, select, button").last();
    await bottomControl.scrollIntoViewIfNeeded();
    assert.deepEqual(
      await footer.boundingBox(),
      before,
      "Calibrate stays fixed while fit parameters/refinement scroll",
    );
    await fitControls.evaluate((el) => {
      el.scrollTop = 0;
    });
  }
}

export async function verifyCalibrationSizes(
  page,
  { tabs = [], screenshots, prefix, expectedGroups },
) {
  for (const large of [false, true]) {
    await page.setViewportSize({ width: 1000, height: 668 });
    await setInterfaceTextSize(page, large);
    for (const tab of tabs) {
      await page.getByRole("tab", { name: tab, exact: true }).click();
      await verifyCalibrationFits(page);
      if (screenshots)
        await page.screenshot({
          path: `${screenshots}/${prefix}-${tab.replaceAll(" ", "-")}${large ? "-large" : ""}.png`,
        });
    }
    if (expectedGroups) {
      const list = page.getByRole("region", { name: "Picked peak groups" });
      const header = page.locator(".peak-table-headers");
      const actions = page.getByRole("button", {
        name: "Clear calibration peaks",
        exact: true,
      });
      const headerBefore = await header.boundingBox();
      const actionsBefore = await actions.boundingBox();
      assert.equal(await page.locator(".peak-row").count(), expectedGroups);
      assert.equal(
        await page
          .getByRole("button", { name: "Next peak page", exact: true })
          .count(),
        0,
      );
      const groups = await list.evaluate((container) => {
        const labels = [];
        for (const row of container.querySelectorAll(".peak-row")) {
          const header = container.querySelector(".peak-table-headers");
          container.scrollTop +=
            row.getBoundingClientRect().top -
            header.getBoundingClientRect().bottom;
          const bounds = container.getBoundingClientRect();
          const rect = row.getBoundingClientRect();
          if (
            rect.top >= header.getBoundingClientRect().bottom - 1 &&
            rect.bottom <= bounds.bottom + 1
          )
            labels.push(
              row.querySelector(".ring-input").getAttribute("aria-label"),
            );
        }
        return labels;
      });
      assert.equal(
        new Set(groups).size,
        expectedGroups,
        "Every peak group remains reachable through the scrollable table",
      );
      assert.deepEqual(
        await header.boundingBox(),
        headerBefore,
        "Column headers stay fixed while rows scroll",
      );
      assert.deepEqual(
        await actions.boundingBox(),
        actionsBefore,
        "Table toolbar stays fixed while rows scroll",
      );
      await list.evaluate((el) => {
        el.scrollTop = 0;
      });
      const listBounds = await list.boundingBox();
      await page.mouse.move(
        listBounds.x + listBounds.width / 2,
        listBounds.y + listBounds.height / 2,
      );
      await page.mouse.wheel(0, 300);
      await page.waitForFunction(
        () => document.querySelector(".peak-list").scrollTop > 0,
      );
      await verifyCalibrationFits(page);
      // Select an offscreen group without native focus scrolling, exercising
      // the application's automatic reveal of a newly selected group.
      const first = page.getByLabel("Select peak group 1", { exact: true });
      const wasChecked = await first.isChecked();
      if (wasChecked) await first.evaluate((el) => el.click());
      await first.evaluate((el) => el.click());
      await page.waitForFunction(
        () => document.querySelector(".peak-list").scrollTop < 1,
      );
      if (!wasChecked) await first.uncheck();
    }
    if (!tabs.length) {
      await verifyCalibrationFits(page);
      if (screenshots)
        await page.screenshot({
          path: `${screenshots}/${prefix}${large ? "-large" : ""}.png`,
        });
    }
  }
  await setInterfaceTextSize(page, false);
  await page.setViewportSize({ width: 1440, height: 1000 });
}
