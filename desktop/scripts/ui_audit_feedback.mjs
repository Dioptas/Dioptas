import assert from "node:assert/strict";
import path from "node:path";

export async function verifyDraftsAndFeedback({ page, ready, invoke, output }) {
  const button = (name) => page.getByRole("button", { name, exact: true });
  const click = async (name) => {
    await button(name).click();
    await ready();
  };
  const tab = async (name) => {
    await page.getByRole("tab", { name, exact: true }).click();
    await ready();
  };
  await click("Map settings");
  const minimum = page.getByLabel("Normalization minimum", { exact: true });
  await minimum.fill("");
  assert.equal(
    await minimum.inputValue(),
    "",
    "Exact-value reveal must not swallow a clear edit",
  );
  await minimum.fill("2");
  assert.equal(await minimum.inputValue(), "2");
  await page.keyboard.press("Escape");
  await ready();
  const original = (await invoke("state")).state;
  await click("Settings");
  await tab("Integration");
  assert(
    await button("Apply integration options").isDisabled(),
    "Unchanged options cannot be reapplied",
  );
  await page.getByLabel("Automatic radial binning", { exact: true }).uncheck();
  await page.getByLabel("Radial bins", { exact: true }).fill("777");
  await page
    .getByLabel("Radial coordinate", { exact: true })
    .selectOption("q_A^-1");
  assert.equal(
    await page.getByLabel("Radial bins", { exact: true }).inputValue(),
    "777",
    "Changing coordinate preserves the bins draft",
  );
  assert.equal(
    (await invoke("state")).state.unit,
    original.unit,
    "Coordinate is an unapplied draft until Apply",
  );
  await tab("General");
  const beforeRevision = (await invoke("state")).state.revision;
  await page
    .getByLabel("Processing engine", { exact: true })
    .selectOption("pyfai");
  await ready();
  assert((await invoke("state")).state.revision >= beforeRevision);
  await tab("Integration");
  assert.equal(
    await page.getByLabel("Radial bins", { exact: true }).inputValue(),
    "777",
    "An unrelated processing-engine response preserves the draft",
  );
  await page.keyboard.press("Escape");
  await ready();
  await click("Settings");
  await tab("Integration");
  assert.equal(
    await page.getByLabel("Radial bins", { exact: true }).inputValue(),
    "777",
    "Leaving and reopening Settings preserves pending options",
  );
  await page.getByLabel("Radial bins", { exact: true }).fill("0");
  await button("Apply integration options").click();
  assert.equal(
    (await invoke("state")).state.unit,
    original.unit,
    "Invalid bins prevent the entire settings transaction",
  );
  assert(
    await page
      .getByLabel("Radial bins", { exact: true })
      .evaluate((e) => !e.validity.valid),
  );
  await page.getByLabel("Radial bins", { exact: true }).fill("777");
  await click("Apply integration options");
  const applied = (await invoke("state")).state;
  assert.equal(applied.unit, "q_A^-1");
  assert.equal(applied.bins, 777);
  await page.getByLabel("Radial bins", { exact: true }).fill("778");
  await page.keyboard.press("Escape");
  await ready();
  await click("Integration");
  await click("Pattern unit d");
  await click("Settings");
  await tab("Integration");
  assert.equal(
    await page.getByLabel("Radial coordinate", { exact: true }).inputValue(),
    "d_A",
    "Unedited form unit rebases to the plot toggle",
  );
  assert.equal(
    await page.getByLabel("Radial bins", { exact: true }).inputValue(),
    "778",
    "Rebasing keeps the deliberate bin edit",
  );
  await click("Apply integration options");
  assert.equal(
    (await invoke("state")).state.unit,
    "d_A",
    "Applying a bin edit does not undo a newer plot-unit choice",
  );
  assert.equal((await invoke("state")).state.bins, 778);

  await page
    .getByLabel("Radial coordinate", { exact: true })
    .selectOption(original.unit);
  if (original.integration.automaticBinning)
    await page.getByLabel("Automatic radial binning", { exact: true }).check();
  else
    await page
      .getByLabel("Radial bins", { exact: true })
      .fill(String(original.bins));
  await click("Apply integration options");
  await page.keyboard.press("Escape");
  await ready();
  await click("Integration");
  await page.evaluate(() => {
    const original = window.__invoke;
    window.__invoke = (a, p) =>
      original(
        a,
        a === "open_calibration"
          ? { ...p, path: "/nonexistent/dioptas-ui-audit/missing.poni" }
          : p,
      );
    window.__restoreFeedbackInvoke = () => {
      window.__invoke = original;
    };
  });
  await page.locator(".integration-calibration-button").click();
  await page.getByRole("alert").waitFor();
  await button("View error details").click();
  const details = page.getByRole("dialog", {
    name: "Error details",
    exact: true,
  });
  assert.match(
    await details.innerText(),
    /File not found.*missing.poni/s,
    "Full real backend error is visible",
  );
  await page.screenshot({ path: path.join(output, "error-details.png") });
  await page.evaluate(() =>
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: {
        writeText: async () => {
          throw new Error("Test clipboard unavailable");
        },
      },
    }),
  );
  await details
    .getByRole("button", { name: "Copy error", exact: true })
    .click();
  await details
    .getByText(
      "Clipboard access is unavailable. Select the message above and copy it.",
      { exact: true },
    )
    .waitFor();
  await page.keyboard.press("Escape");
  assert(
    await button("View error details").evaluate(
      (e) => e === document.activeElement,
    ),
    "Error details restore focus",
  );
  await button("Dismiss error").click();
  await ready();
  await page.evaluate(() => window.__restoreFeedbackInvoke());
  await click("Integration");
  await tab("Overlay");
  const overlayRow = page.locator(".qt-overlay-table-scroll tr").first();
  await overlayRow.focus();
  await page.keyboard.press("Shift+F10");
  await page.getByRole("menu").waitFor();
  await page.keyboard.press("Escape");
  assert(
    await overlayRow.evaluate((e) => e === document.activeElement),
    "Overlay menu restores its row focus",
  );
  await page.keyboard.press("Shift+F10");
  await page.getByRole("menu").waitFor();
  await page.keyboard.press("Tab");
  assert.equal(
    await page.getByRole("menu").count(),
    0,
    "Tab dismisses the overlay menu",
  );
  await tab("Image");
  await page.evaluate(() => {
    const original = window.__invoke;
    window.__queuedActions = [];
    window.__invoke = async (action, payload) => {
      window.__queuedActions.push(action);
      if (action === "validation_position") {
        window.__holdValidation = true;
        await new Promise((resolve) => {
          window.__releaseValidation = resolve;
        });
      }
      return original(action, payload);
    };
    window.__restoreQueueInvoke = () => {
      window.__invoke = original;
    };
  });
  await page
    .getByTestId("detector-canvas")
    .click({ position: { x: 120, y: 120 } });
  await page.waitForFunction(() => window.__holdValidation === true);
  assert(await button("Undo").isEnabled());
  await button("Undo").click();
  await page.evaluate(() => window.__releaseValidation());
  await ready();
  assert.equal(
    await page.evaluate(
      () =>
        window.__queuedActions.filter((action) =>
          /^(undo|redo)_(calibration|mask)$/.test(action),
        ).length,
    ),
    1,
    "Undo queues behind a quiet inspection request instead of being discarded",
  );
  await page.evaluate(() => window.__restoreQueueInvoke());

  await click("Calibration");
  await tab("Step 4: Validate");
  await tab("pyFAI");
  const rotation = page.getByLabel("Manual rotation 1", { exact: true });
  const exact = await rotation.getAttribute("data-exact-value");
  await rotation.fill("0.01");
  assert.equal(await rotation.inputValue(), "0.01");
  assert(
    await button("Save .poni calibration").isDisabled(),
    "Unapplied geometry prevents saving",
  );
  await rotation.fill(exact);
  await rotation.blur();
  return [
    "Compact scientific numbers reveal exact text and accept empty/edited drafts without changing stored geometry",
    "Integration drafts rebase unedited fields, preserve deliberate edits and newer plot units; Apply is atomic and rejects invalid bins",
    "Overlay menu Escape restores row focus; Tab dismisses the menu",
    "Undo queues behind a quiet inspection request without losing the user action",
    "Real missing-PONI error: readable details, Escape, focus return and dismissal",
  ];
}
