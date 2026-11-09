import assert from "node:assert/strict";
import path from "node:path";
import { mkdir, writeFile } from "node:fs/promises";
import { pathToFileURL } from "node:url";
import { chromium, webkit } from "playwright";
import { nativeClient, root } from "./native_backend_client.mjs";
import { selectCalibrationRing } from "./calibration_ring_picker.mjs";

const artifacts = path.join(root, "desktop/artifacts/native-calibration");
await mkdir(artifacts, { recursive: true });
const blankImage = path.join(artifacts, "no-peaks.npy");
const header = Buffer.from(
  "{'descr': '<f8', 'fortran_order': False, 'shape': (32, 32), }".padEnd(117) +
    "\n",
);
const prefix = Buffer.from([0x93, 0x4e, 0x55, 0x4d, 0x50, 0x59, 1, 0, 0, 0]);
prefix.writeUInt16LE(header.length, 8);
await writeFile(
  blankImage,
  Buffer.concat([prefix, header, Buffer.alloc(32 * 32 * 8)]),
);
const receipts = [];
for (const [name, type] of [
  ["chromium", chromium],
  ["webkit", webkit],
]) {
  const native = nativeClient();
  let browser;
  const commandErrors = [],
    errors = [],
    previews = [];
  try {
    assert.equal((await native.invoke("__host__")).runtime, "rust");
    assert.equal(
      (await native.invoke("open_image", { path: blankImage })).ok,
      true,
    );
    browser = await type.launch({ headless: true });
    const page = await browser.newPage({
      viewport: { width: 1440, height: 940 },
    });
    page.setDefaultTimeout(45000);
    page.on("pageerror", (e) => errors.push(e.message));
    await page.exposeFunction(
      "__nativeInvoke",
      async (action, payload = {}) => {
        const result = await native.invoke(action, payload);
        if (!result.ok) commandErrors.push({ action, error: result.error });
        if (action === "progress" && result.progress?.calibration)
          previews.push(structuredClone(result.progress));
        return native.browserResult(result);
      },
    );
    await page.addInitScript(() => {
      window.__pending = 0;
      window.pywebview = {
        api: {
          invoke: async (action, payload) => {
            const track = !["pixel", "progress"].includes(action);
            if (track) window.__pending++;
            try {
              return await window.__nativeInvoke(action, payload);
            } finally {
              if (track) window.__pending--;
            }
          },
        },
      };
    });
    await page.goto(
      pathToFileURL(path.join(root, "dioptas/desktop/ui/index.html")).href,
    );
    const ready = async () => {
      await page.waitForFunction(() => window.__pending === 0);
      await page.waitForFunction(() => !document.querySelector(".spin"));
      // The pipe can settle before React commits the returned snapshot. Wait
      // for that render before using another controlled input.
      await page.evaluate(
        () =>
          new Promise((resolve) =>
            requestAnimationFrame(() => requestAnimationFrame(resolve)),
          ),
      );
      await page.waitForFunction(
        () => window.__pending === 0 && !document.querySelector(".spin"),
      );
      assert.deepEqual(commandErrors, []);
      assert.deepEqual(errors, []);
    };
    await page.getByTestId("detector-canvas").waitFor();
    await ready();
    const blankCanvas = page.getByTestId("detector-canvas");
    const box = await blankCanvas.boundingBox();
    // Zoom before missing a peak, so an accidental fitted-view reset is visible.
    await page.mouse.move(box.x + box.width * 0.3, box.y + box.height * 0.3);
    await page.mouse.down();
    await page.mouse.move(box.x + box.width * 0.7, box.y + box.height * 0.7, {
      steps: 8,
    });
    await page.mouse.up();
    const view = () =>
      blankCanvas.evaluate((el) => [
        el.dataset.viewXMin,
        el.dataset.viewXMax,
        el.dataset.viewYMin,
        el.dataset.viewYMax,
      ]);
    const zoomed = await view();
    const beforeMiss = (await native.invoke("state")).state;
    await page.mouse.click(box.x + box.width / 2, box.y + box.height / 2);
    const notice = page.locator('.workflow-status [role="status"]');
    await notice.filter({ hasText: "No peaks found in this area" }).waitFor();
    await ready();
    assert.deepEqual((await native.invoke("state")).state, beforeMiss);
    assert.deepEqual(await view(), zoomed);
    assert.equal(await page.getByRole("dialog").count(), 0);
    assert.equal(
      await page
        .getByRole("button", { name: "View error details", exact: true })
        .count(),
      0,
    );
    assert.equal(
      await page.locator('.workflow-status [role="alert"]').innerText(),
      "",
    );
    assert.equal(
      await page
        .getByRole("button", { name: "Current calibrant ring", exact: true })
        .getAttribute("data-ring"),
      "1",
    );
    const noticeBox = await notice.boundingBox();
    assert.ok(
      noticeBox.x > 720 && noticeBox.y > 850,
      "Missed picks use the lower-right footer",
    );
    await page.screenshot({
      path: path.join(artifacts, `${name}-missed-pick.png`),
    });
    await notice
      .filter({ hasText: "No peaks found in this area" })
      .waitFor({ state: "hidden", timeout: 7000 });
    assert.equal((await native.invoke("example")).ok, true);
    await page.reload();
    await page.getByTestId("detector-canvas").waitFor();
    await ready();
    const seeds = [
      [637, 564, 1],
      [671, 511, 2],
      [668, 703, 3],
      [350.5, 592.8, 1],
      [554.3, 367.9, 1],
    ];
    for (const [x, y, ring] of seeds) {
      await selectCalibrationRing(page, ring);
      const canvas = page.getByTestId("detector-canvas");
      const box = await canvas.boundingBox();
      const v = await canvas.evaluate((el) => ({
        left: +el.dataset.plotLeft,
        top: +el.dataset.plotTop,
        width: +el.dataset.plotWidth,
        height: +el.dataset.plotHeight,
        x0: +el.dataset.viewXMin,
        x1: +el.dataset.viewXMax,
        y0: +el.dataset.viewYMin,
        y1: +el.dataset.viewYMax,
      }));
      await page.mouse.click(
        box.x + v.left + ((x - v.x0) / (v.x1 - v.x0)) * v.width,
        box.y + v.top + ((v.y1 - y) / (v.y1 - v.y0)) * v.height,
      );
      await ready();
    }
    let snapshot = await native.invoke("state");
    assert.equal(snapshot.state.calibration.picks.length, 5);
    await page
      .getByRole("tab", { name: "Step 2: Pick rings", exact: true })
      .click();
    await page.getByRole("button", { name: "Undo", exact: true }).click();
    await ready();
    assert.equal(
      (await native.invoke("state")).state.calibration.picks.length,
      4,
    );
    await page.getByRole("button", { name: "Redo", exact: true }).click();
    await ready();
    assert.equal(
      (await native.invoke("state")).state.calibration.picks.length,
      5,
    );
    await page
      .getByRole("tab", { name: "Step 3: Calibrate", exact: true })
      .click();
    await page.getByLabel("Automatic refinement", { exact: true }).click();
    await ready();
    await page.waitForFunction(
      () =>
        document.querySelector('input[aria-label="Automatic refinement"]')
          ?.checked === false,
    );
    assert.equal(
      await page
        .getByLabel("Automatic refinement", { exact: true })
        .isChecked(),
      false,
    );
    await page.getByRole("button", { name: "Calibrate", exact: true }).click();
    await ready();
    snapshot = await native.invoke("state");
    assert.equal(snapshot.state.calibrated, true);
    assert.ok(snapshot.state.calibration.rmsDegrees < 0.05);
    assert.ok(snapshot.rings.length > 0);
    assert.equal(snapshot.state.calibration.geometrySource, "fitted");
    const manualRms = snapshot.state.calibration.rmsDegrees;
    await page
      .getByRole("tab", { name: "Step 3: Calibrate", exact: true })
      .click();
    await page.getByLabel("Automatic refinement", { exact: true }).click();
    await ready();
    await page.waitForFunction(
      () =>
        document.querySelector('input[aria-label="Automatic refinement"]')
          ?.checked === true,
    );
    assert.equal(
      await page
        .getByLabel("Automatic refinement", { exact: true })
        .isChecked(),
      true,
    );
    const rings = page.getByLabel("Number of rings", { exact: true });
    await rings.fill("4");
    await rings.press("Enter");
    await ready();
    await page.getByRole("button", { name: "Refine", exact: true }).click();
    await ready();
    snapshot = await native.invoke("state");
    assert.ok(snapshot.state.calibration.rmsDegrees < 0.05);
    assert.ok(
      new Set(snapshot.state.calibration.picks.map((p) => p.ring)).size >= 3,
    );
    assert.ok(
      previews.some(
        (p) => p.calibration.picks.length > 0 && p.calibration.rings.length > 0,
      ),
    );
    assert.equal((await native.invoke("progress")).progress.running, false);
    await page.screenshot({ path: path.join(artifacts, `${name}-fitted.png`) });
    assert.deepEqual(commandErrors, []);
    assert.deepEqual(errors, []);
    receipts.push({
      browser: name,
      missedPickNotice: true,
      source: "raw CeO2 TIFF; no reference geometry loaded",
      manualRmsDegrees: manualRms,
      automaticRmsDegrees: snapshot.state.calibration.rmsDegrees,
      groups: snapshot.state.calibration.picks.length,
      livePreviews: previews.length,
      errors,
      commandErrors,
    });
  } finally {
    await browser?.close();
    await native.close();
  }
}
await writeFile(
  path.join(artifacts, "browser-results.json"),
  JSON.stringify(receipts, null, 2) + "\n",
);
console.log(JSON.stringify(receipts, null, 2));
