import assert from "node:assert/strict";
import { setInterfaceTextSize } from "./plot_navigation.mjs";

export async function verifyCalibrationFits(page) {
  await page.evaluate(
    () =>
      new Promise((resolve) =>
        requestAnimationFrame(() => requestAnimationFrame(resolve)),
      ),
  );
  const result = await page
    .locator(".calibration-task-panel .sidebar-scroll")
    .evaluate((body) => {
      const bounds = body.getBoundingClientRect();
      const clipped = [
        ...body.querySelectorAll(
          "input, select, button, .control-note, .no-peaks, .pick-position",
        ),
      ]
        .filter((el) => {
          if (el.closest("dialog") || !el.getClientRects().length) return false;
          const rect = el.getBoundingClientRect();
          const list = el.closest(".peak-list")?.getBoundingClientRect();
          if (
            list &&
            (rect.bottom > list.bottom + 1 || rect.top < list.top - 1)
          )
            return true;
          return (
            rect.bottom > bounds.bottom + 1 ||
            rect.top < bounds.top - 1 ||
            rect.left < bounds.left - 1 ||
            rect.right > bounds.right + 1
          );
        })
        .map((el) => el.getAttribute("aria-label") || el.textContent.trim());
      return {
        verticalOverflow: body.scrollHeight - body.clientHeight,
        horizontalOverflow: body.scrollWidth - body.clientWidth,
        clipped,
      };
    });
  assert.ok(result.verticalOverflow <= 1, JSON.stringify(result));
  assert.ok(result.horizontalOverflow <= 1, JSON.stringify(result));
  assert.deepEqual(
    result.clipped,
    [],
    "Every calibration control must fit without scrolling",
  );
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
      const previous = page.getByRole("button", {
        name: "Previous peak page",
        exact: true,
      });
      const next = page.getByRole("button", {
        name: "Next peak page",
        exact: true,
      });
      while (await previous.isEnabled()) await previous.click();
      const groups = new Set();
      for (;;) {
        await verifyCalibrationFits(page);
        for (const label of await page
          .locator(".peak-row .ring-input")
          .evaluateAll((inputs) =>
            inputs.map((input) => input.getAttribute("aria-label")),
          ))
          groups.add(label);
        assert.equal(
          await page.locator(".peak-row .pick-position").first().isVisible(),
          true,
        );
        if (await next.isDisabled()) break;
        await next.click();
      }
      assert.equal(
        groups.size,
        expectedGroups,
        "Every peak group remains reachable through pagination",
      );
      while (await previous.isEnabled()) await previous.click();
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
