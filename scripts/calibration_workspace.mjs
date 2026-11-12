import { selectCalibrationRing } from "./calibration_ring_picker.mjs";
import assert from "node:assert/strict";
import path from "node:path";
import { readFile } from "node:fs/promises";

/** Real-model checks for calibration actions and picking independent of tabs. */
export async function verifyCalibrationWorkspace(
  page,
  invoke,
  artifacts,
  waitReady,
) {
  const project = path.join(artifacts, "calibration-workspace.dio");
  assert.ok((await invoke("save_project", { path: project })).ok);
  const restore = async () => {
    const result = await invoke("open_project", { path: project });
    assert.ok(result.ok, result.error);
    await page.reload();
    await waitReady();
  };
  const tab = (name) => page.getByRole("tab", { name, exact: true });
  const save = page.getByRole("button", {
    name: "Save .poni calibration",
    exact: true,
  });
  const ring = page.getByLabel("Current calibrant ring", { exact: true });
  const automatic = page.getByLabel("Automatically advance ring number", {
    exact: true,
  });
  const picking = page.getByLabel("Pick peaks", { exact: true });
  const pick = async (x, y) => {
    const canvas = page.getByTestId("detector-canvas");
    const box = await canvas.boundingBox();
    const view = await canvas.evaluate((el) => ({
      left: +el.dataset.plotLeft,
      top: +el.dataset.plotTop,
      width: +el.dataset.plotWidth,
      height: +el.dataset.plotHeight,
      xMin: +el.dataset.viewXMin,
      xMax: +el.dataset.viewXMax,
      yMin: +el.dataset.viewYMin,
      yMax: +el.dataset.viewYMax,
    }));
    await page.mouse.click(
      box.x +
        view.left +
        ((x - view.xMin) / (view.xMax - view.xMin)) * view.width,
      box.y +
        view.top +
        ((view.yMax - y) / (view.yMax - view.yMin)) * view.height,
    );
    await waitReady();
  };
  let savePosition;
  for (const name of [
    "Step 1: Image & setup",
    "Step 2: Pick rings",
    "Step 3: Calibrate",
    "Step 4: Validate",
  ]) {
    await restore();
    await tab(name).click();
    if (["Step 3: Calibrate", "Step 4: Validate"].includes(name)) {
      for (const action of ["Calibrate", "Refine"]) {
        const control = page.getByRole("button", { name: action, exact: true });
        assert.ok(await control.isVisible(), `${action} is visible on ${name}`);
        assert.ok(await control.isEnabled(), `${action} is enabled on ${name}`);
        assert.match(await control.getAttribute("title"), /current peaks/);
      }
    }
    await selectCalibrationRing(page, 1);
    await automatic.check();
    await waitReady();
    assert.ok(await picking.isChecked());
    assert.ok(await save.isEnabled(), `Save is available on ${name}`);
    const bounds = await save.boundingBox();
    if (savePosition)
      assert.deepEqual(
        bounds,
        savePosition,
        "Save stays in one location across tabs",
      );
    savePosition = bounds;
    await save.click();
    await waitReady();
    assert.match(
      await readFile(path.join(artifacts, "calibration.poni"), "utf8"),
      /Distance/,
    );
    const baseline = (await invoke("state")).state.calibration.picks.length;
    await pick(637, 564);
    const picked = await invoke("state");
    assert.equal(
      picked.state.calibration.picks.length,
      baseline + 1,
      `Picking works on ${name}`,
    );
    assert.equal(picked.state.calibration.picks.at(-1).ring, 1);
    assert.equal(await ring.getAttribute("data-ring"), "2");
    assert.equal(
      await tab(name).getAttribute("aria-selected"),
      "true",
      "Picking does not change tabs",
    );
    assert.ok(
      await save.isDisabled(),
      "Changed selections need refinement before saving",
    );
    await automatic.uncheck();
    await waitReady();
    await pick(671, 511);
    assert.equal(
      await ring.getAttribute("data-ring"),
      "2",
      "Manual ring selection stays fixed when Auto is off",
    );
    await picking.uncheck();
    const beforeInspection = (await invoke("state")).state.calibration.picks
      .length;
    await pick(637, 564);
    assert.equal(
      (await invoke("state")).state.calibration.picks.length,
      beforeInspection,
      "Inspection adds no peaks",
    );
  }
  await restore();
  assert.ok((await invoke("remove_pick", { index: 0 })).ok);
  await page.reload();
  await waitReady();
  const editedPicks = (await invoke("state")).state.calibration.picks;
  await page.evaluate(() => {
    window.__recalibrationInvoke = window.__dioptasInvoke;
    window.__calibrationFitRequests = [];
    window.__dioptasInvoke = (command, args) => {
      if (command === "calibrate") window.__calibrationFitRequests.push(args);
      return window.__recalibrationInvoke(command, args);
    };
  });
  await tab("Step 3: Calibrate").click();
  await page.getByLabel("Automatic refinement", { exact: true }).uncheck();
  await waitReady();
  const recalibrate = page.getByRole("button", {
    name: "Calibrate",
    exact: true,
  });
  assert.ok(
    await recalibrate.isEnabled(),
    "Calibration stays available after a fit and peak edits",
  );
  await recalibrate.click();
  await waitReady();
  assert.deepEqual(
    (await invoke("state")).state.calibration.picks,
    editedPicks,
  );
  await tab("Step 3: Calibrate").click();
  assert.ok(
    await recalibrate.isEnabled(),
    "Calibration stays available after recalibrating",
  );
  await page.getByRole("button", { name: "Refine", exact: true }).click();
  await waitReady();
  await tab("Step 4: Validate").click();
  await recalibrate.click();
  await waitReady();
  await tab("Step 4: Validate").click();
  await page.getByRole("button", { name: "Refine", exact: true }).click();
  await waitReady();
  const requests = await page.evaluate(() => window.__calibrationFitRequests);
  assert.equal(requests.length, 4);
  for (const offset of [0, 2]) {
    assert.equal(
      requests[offset].restart,
      true,
      "Calibrate initializes a fresh geometry on either tab",
    );
    assert.notEqual(
      requests[offset + 1].restart,
      true,
      "Refine continues the current geometry on either tab",
    );
  }
  await page.evaluate(() => {
    window.__dioptasInvoke = window.__recalibrationInvoke;
    delete window.__recalibrationInvoke;
    delete window.__calibrationFitRequests;
  });
  await restore();
  await tab("Step 4: Validate").click();
  await picking.uncheck();
  await tab("Step 4: Validate").focus();
  await page.keyboard.press("p");
  assert.ok(await picking.isChecked(), "P enables picking");
  assert.equal(
    await tab("Step 4: Validate").getAttribute("aria-selected"),
    "true",
    "P keeps the current calibration tab",
  );
  await page.getByRole("tab", { name: "pyFAI", exact: true }).click();
  const rotation = page.getByLabel("Manual rotation 1", { exact: true });
  const original = await rotation.inputValue();
  await rotation.fill(String(Number(original) + 0.001));
  await tab("Step 2: Pick rings").click();
  assert.ok(await save.isDisabled(), "Geometry drafts block Save on every tab");
  await tab("Step 4: Validate").click();
  assert.equal(
    await rotation.inputValue(),
    String(Number(original) + 0.001),
    "Geometry drafts survive tab changes",
  );
  await rotation.fill(original);
  await restore();
  await tab("Step 3: Calibrate").click();
  const distance = page.getByLabel("Distance constraint value", {
    exact: true,
  });
  const originalDistance = await distance.inputValue();
  await distance.fill(String(Number(originalDistance) + 1));
  await tab("Step 2: Pick rings").click();
  assert.ok(await save.isDisabled(), "Fit drafts block Save on every tab");
  await restore();
  await tab("Step 4: Validate").click();
  return "Shared ring and Auto controls, picking/inspection and Save across all four tabs; recalibration from edited peaks, separate refinement, draft protection and fixed Save position";
}
