import assert from "node:assert/strict";
import path from "node:path";
import { writeFile } from "node:fs/promises";
import { setInterfaceTextSize } from "./plot_navigation.mjs";

export async function selectCalibrationRing(page, ring) {
  await page
    .getByRole("button", { name: "Current calibrant ring", exact: true })
    .click();
  await page
    .getByRole("listbox", { name: "Calibrant rings", exact: true })
    .locator(`[role="option"][data-ring="${ring}"]`)
    .click();
}

export async function verifyCalibrationRingPicker(
  page,
  calibration,
  artifacts,
) {
  const trigger = page.getByRole("button", {
    name: "Current calibrant ring",
    exact: true,
  });
  const previous = page.getByRole("button", {
    name: "Previous calibrant ring",
    exact: true,
  });
  const next = page.getByRole("button", {
    name: "Next calibrant ring",
    exact: true,
  });
  const menu = page.getByRole("listbox", {
    name: "Calibrant rings",
    exact: true,
  });
  await selectCalibrationRing(page, calibration.rings[0].ring);
  assert.ok(await previous.isDisabled());
  await next.click();
  assert.equal(
    await trigger.getAttribute("data-ring"),
    String(calibration.rings[1].ring),
  );
  await previous.click();
  await trigger.click();
  assert.equal(
    await menu.getByRole("option").count(),
    calibration.rings.length,
  );
  for (const ring of calibration.rings) {
    const count = calibration.picks
      .filter((p) => p.ring === ring.ring)
      .reduce((total, pick) => total + pick.points.length, 0);
    assert.equal(
      await menu
        .locator(`[data-ring="${ring.ring}"] .calibration-ring-point-count`)
        .textContent(),
      String(count),
    );
  }
  await page.keyboard.press("End");
  await page.keyboard.press("Enter");
  assert.ok(await next.isDisabled());
  const last = calibration.rings.at(-1).ring;
  assert.equal(await trigger.getAttribute("data-ring"), String(last));
  await trigger.click();
  const selected = menu.locator('[aria-selected="true"]');
  assert.ok(
    await selected.evaluate((el) => {
      const rect = el.getBoundingClientRect();
      const list = el.parentElement.getBoundingClientRect();
      return rect.top >= list.top && rect.bottom <= list.bottom + 1;
    }),
    "Menu opens with the current ring in view",
  );
  await page.keyboard.press("Home");
  await page.keyboard.type(
    String(
      calibration.rings.find((entry) => entry.ring === 50)?.ring ??
        calibration.rings[Math.min(11, calibration.rings.length - 1)].ring,
    ),
  );
  await page.keyboard.press("Enter");
  assert.equal(
    await trigger.getAttribute("data-ring"),
    String(
      calibration.rings.find((entry) => entry.ring === 50)?.ring ??
        calibration.rings[Math.min(11, calibration.rings.length - 1)].ring,
    ),
  );
  await trigger.click();
  await page.keyboard.press("Escape");
  assert.equal(await menu.count(), 0);
  assert.ok(await trigger.evaluate((el) => el === document.activeElement));
  await page.keyboard.press("Enter");
  assert.equal(
    await menu.count(),
    1,
    "Enter opens the picker without starting integration",
  );
  await page.keyboard.press("Tab");
  assert.equal(await menu.count(), 0);
  assert.ok(
    await page
      .getByLabel("Automatically advance ring number", { exact: true })
      .evaluate((el) => el === document.activeElement),
  );
  await trigger.click();
  await page.locator(".app-status").click();
  assert.equal(await menu.count(), 0, "Outside click closes the menu");
  await page
    .getByRole("tab", { name: "Step 2: Pick rings", exact: true })
    .click();
  assert.equal(await menu.count(), 0, "Outside click closes the menu");
  const row = page.locator(".peak-row").first();
  const rowRing = calibration.picks[0].ring;
  await row.locator(".ring-input").click();
  assert.equal(await trigger.getAttribute("data-ring"), String(rowRing));
  assert.ok(await row.getByRole("checkbox").isChecked());
  assert.equal(await row.getAttribute("data-selected"), "true");
  assert.equal(
    await page.getByTestId("detector-canvas").getAttribute("data-active-ring"),
    String(rowRing),
  );
  await next.click();
  await row.focus();
  await page.keyboard.press("Enter");
  assert.equal(await trigger.getAttribute("data-ring"), String(rowRing));
  assert.ok(await row.getByRole("checkbox").isChecked());
  const otherRing = calibration.picks.find(
    (pick) => pick.ring !== rowRing,
  ).ring;
  await selectCalibrationRing(page, otherRing);
  const rows = page.locator(".peak-row");
  for (let i = 0; i < calibration.picks.length; i++)
    assert.equal(
      await rows.nth(i).getByRole("checkbox").isChecked(),
      calibration.picks[i].ring === otherRing,
      "Choosing a ring selects its groups in the table",
    );
  return "Ring menu point totals, stepping, bounds, keyboard jumps, dismissal and two-way peak-table selection";
}

/** Synthetic spacing fixture exercises menu scale only; no geometry is fitted. */
export async function verifyFiftyRingPicker(
  page,
  invoke,
  artifacts,
  waitReady,
) {
  const baseline = path.join(artifacts, "ring-picker-baseline.dio");
  const spacings = path.join(artifacts, "ring-picker-50.D");
  assert.ok((await invoke("save_project", { path: baseline })).ok);
  await writeFile(
    spacings,
    "# UI-only 50-ring spacing fixture\n" +
      Array.from({ length: 50 }, (_, i) => String(5 / Math.sqrt(i + 1))).join(
        "\n",
      ) +
      "\n",
  );
  try {
    const result = await invoke("open_calibrant", { path: spacings });
    assert.ok(result.ok, result.error);
    assert.equal(result.state.calibration.rings.length, 50);
    await page.reload();
    await waitReady();
    await page
      .getByRole("tab", { name: "Step 2: Pick rings", exact: true })
      .click();
    const trigger = page.getByRole("button", {
      name: "Current calibrant ring",
      exact: true,
    });
    const menu = page.getByRole("listbox", {
      name: "Calibrant rings",
      exact: true,
    });
    const viewport = page.viewportSize();
    await page.setViewportSize({ width: 1000, height: 668 });
    for (const large of [false, true]) {
      await setInterfaceTextSize(page, large);
      await trigger.click();
      await page.keyboard.type("50");
      await page.keyboard.press("Enter");
      assert.equal(
        await trigger.getAttribute("data-ring"),
        "50",
        "Typing 50 selects ring 50",
      );
      assert.ok(
        await page
          .getByRole("button", { name: "Next calibrant ring", exact: true })
          .isDisabled(),
      );
      await trigger.click();
      assert.equal(await menu.getByRole("option").count(), 50);
      const selectedBounds = await menu
        .locator('[aria-selected="true"]')
        .boundingBox();
      const bounds = await menu.boundingBox();
      assert.ok(
        selectedBounds.y >= bounds.y &&
          selectedBounds.y + selectedBounds.height <=
            bounds.y + bounds.height + 1,
      );
      const dimensions = await menu.evaluate((el) => ({
        height: el.clientHeight,
        total: el.scrollHeight,
      }));
      assert.ok(
        dimensions.total > dimensions.height,
        "Long ring lists scroll inside the menu",
      );
      const panel = await page.locator(".calibration-task-panel").boundingBox();
      assert.ok(
        bounds.x >= panel.x && bounds.x + bounds.width <= panel.x + panel.width,
      );
      assert.ok(bounds.y + bounds.height <= 668);
      for (const button of await page
        .locator(".calibration-ring-navigation button")
        .all())
        assert.ok(
          await button.evaluate((el) => el.scrollWidth <= el.clientWidth),
          "Ring controls remain readable",
        );
      await page.screenshot({
        path: path.join(
          artifacts,
          `ring-picker-${large ? "large" : "standard"}.png`,
        ),
      });
      await page.keyboard.press("Escape");
    }
    await setInterfaceTextSize(page, false);
    await page.setViewportSize(viewport);
  } finally {
    assert.ok((await invoke("open_project", { path: baseline })).ok);
    await page.reload();
    await waitReady();
  }
  return "50-ring menu, multi-digit jumps and scrolling at both text sizes";
}
