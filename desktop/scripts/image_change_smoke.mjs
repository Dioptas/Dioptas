import assert from "node:assert/strict";
import { mkdir, mkdtemp, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { createServer } from "vite";
import { chromium, webkit } from "playwright";
import { version } from "./release_config.mjs";
import { nativeClient } from "./native_backend_client.mjs";
import { setInterfaceTextSize } from "./plot_navigation.mjs";

const desktop = fileURLToPath(new URL("../", import.meta.url));
const root = fileURLToPath(new URL("../../", import.meta.url));
const artifacts = path.join(desktop, "artifacts/image-change");
await mkdir(artifacts, { recursive: true });
const temporary = await mkdtemp(path.join(tmpdir(), "dioptas-image-change-"));
const small = path.join(temporary, "small.edf");
const same = path.join(temporary, "same.edf");
const largeImage = path.join(root, "desktop/tests/data/CeO2_Pilatus1M.tif");
const legacyCalibration = path.join(
  root,
  "desktop/tests/data/CeO2_Pilatus1M.poni",
);
const largeCalibration = path.join(temporary, "large.poni");
await writeFile(
  largeCalibration,
  `poni_version: 2.1
Detector: Detector
Detector_config: {"pixel1":0.0001,"pixel2":0.0001,"max_shape":[1043,981],"orientation":3}
Distance: 0.2
Poni1: 0.04
Poni2: 0.04
Rot1: 0
Rot2: 0
Rot3: 0
Wavelength: 5e-11
`,
);
const native = nativeClient();
const diagnostics = native.diagnostics;
const invoke = native.invoke;
const header = Buffer.alloc(512, 32);
Buffer.from(
  "{\nHeaderID = EH:000001:000000:000000;\nImage = 1;\nByteOrder = LowByteFirst;\nDataType = UnsignedShort;\nDim_1 = 128;\nDim_2 = 96;\nSize = 24576;\n",
).copy(header);
Buffer.from("}\n").copy(header, 510);
const pixels = Buffer.alloc(96 * 128 * 2);
for (let i = 0; i < 96 * 128; i++) pixels.writeUInt16LE(i + 1, i * 2);
for (const file of [small, same])
  await writeFile(file, Buffer.concat([header, pixels]));
async function call(action, payload) {
  const result = await invoke(action, payload);
  assert.ok(result.ok, result.error);
  return result;
}
const server = await createServer({
  root: desktop,
  server: { host: "127.0.0.1", port: 0 },
});
await server.listen();
const browserName = process.argv.includes("--webkit") ? "webkit" : "chromium";
const browser = await (browserName === "webkit" ? webkit : chromium).launch({
  headless: true,
});
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
const errors = [];
page.on("pageerror", (e) => errors.push(e.message));
let selectedImage = small;
let selectedCalibration = legacyCalibration;
await page.exposeFunction("__dioptasInvoke", async (action, payload = {}) => {
  if (action === "open_image" && !payload.path)
    payload = { ...payload, path: selectedImage };
  if (action === "open_calibration" && !payload.path)
    payload = {
      ...payload,
      path: selectedCalibration,
    };
  const result = await invoke(action, payload);
  if (!result.ok) console.error(action, JSON.stringify(result));
  return native.browserResult(result);
});
await page.addInitScript(() => {
  window.__imageChangePending = 0;
  window.pywebview = {
    api: {
      invoke: async (action, payload) => {
        window.__imageChangePending++;
        try {
          return await window.__dioptasInvoke(action, payload);
        } finally {
          window.__imageChangePending--;
        }
      },
    },
  };
});
const button = (name) => page.getByRole("button", { name, exact: true });
async function ready() {
  await page.waitForFunction(
    () => !window.__imageChangePending && !document.querySelector(".spin"),
  );
  await page.evaluate(
    () =>
      new Promise((resolve) =>
        requestAnimationFrame(() => requestAnimationFrame(resolve)),
      ),
  );
  assert.deepEqual(await page.getByRole("alert").allTextContents(), []);
}
const report = { browser: browserName, headless: true, checks: [] };
try {
  assert.equal((await call("__host__")).runtime, "rust");
  await call("example");
  await call("open_calibration", {
    path: path.join(root, "desktop/tests/data/CeO2_Pilatus1M.poni"),
  });
  await call("integration_settings", { bins: 100, cake_bins: 20 });
  await call("mask_stroke", { points: [[20, 30]], radius: 3 });
  const before = (await call("state")).state;
  await page.goto(server.resolvedUrls.local[0]);
  await button("Open image").waitFor({ state: "visible" });
  await ready();
  for (const large of [false, true]) {
    await page.setViewportSize({ width: 1000, height: 668 });
    await setInterfaceTextSize(page, large);
    const footerButtons = await Promise.all(
      ["Reset calibration", "Load .poni", "Enter manually"].map((name) =>
        button(name).boundingBox(),
      ),
    );
    assert.ok(
      footerButtons.every(
        (box) => box && Math.abs(box.y - footerButtons[0].y) < 1,
      ),
      "Calibration footer actions stay on one row at both text sizes",
    );
    // Safari/WebKit does not focus buttons on pointer clicks. Exercise focus
    // restoration from a keyboard-focusable opener in both browser engines.
    await button("Open image").focus();
    await button("Open image").click();
    const dialog = page.getByRole("dialog", {
      name: "Image dimensions changed",
    });
    await dialog.waitFor({ state: "visible" });
    assert.equal(
      await button("Cancel").evaluate((el) => el === document.activeElement),
      true,
    );
    assert.deepEqual((await call("state")).state, before);
    const box = await dialog.boundingBox();
    assert.ok(
      box.x >= 0 &&
        box.y >= 0 &&
        box.x + box.width <= 1000 &&
        box.y + box.height <= 668,
    );
    await page.screenshot({
      path: path.join(
        artifacts,
        `confirm-${browserName}-${large ? "large" : "normal"}.png`,
      ),
    });
    if (large) await page.keyboard.press("Escape");
    else await button("Cancel").click();
    await dialog.waitFor({ state: "detached" });
    assert.deepEqual((await call("state")).state, before);
    await page.waitForFunction(
      () => document.activeElement?.matches(".setup-open-image"),
      undefined,
      { timeout: 2000 },
    );
    assert.equal(
      await button("Open image").evaluate(
        (el) => el === document.activeElement,
      ),
      true,
    );
  }
  report.checks.push(
    "dimensions shown before mutation",
    "Cancel and Escape preserve session and focus",
    "1000×668 at both text sizes",
  );
  await button("Open image").click();
  await button("Open and reset calibration").click();
  await page.waitForFunction(
    (version) =>
      document.title.startsWith(`Dioptas ${version} — `) &&
      document.title.includes("small.edf"),
    version,
  );
  await ready();
  let result = await call("state");
  assert.deepEqual(result.state.shape, [96, 128]);
  assert.equal(result.state.calibrated, false);
  assert.equal(result.state.maskedPixels, 0);
  assert.equal(result.pattern, null);
  assert.equal(result.cake, null);
  assert.equal(
    await page
      .getByRole("tab", { name: "Step 1: Image & setup", exact: true })
      .getAttribute("aria-selected"),
    "true",
  );
  assert.equal(await button("Save .poni calibration").isEnabled(), false);
  await page.screenshot({
    path: path.join(artifacts, `reset-${browserName}.png`),
  });
  report.checks.push(
    "accepted change opens uncalibrated and clears stale results",
  );
  await button("Load .poni").click();
  await ready();
  assert.equal((await call("state")).state.calibrated, true);
  await page
    .getByRole("tab", { name: "Step 1: Image & setup", exact: true })
    .click();
  selectedImage = same;
  await button("Open image").click();
  await page.waitForFunction(
    (version) =>
      document.title.startsWith(`Dioptas ${version} — `) &&
      document.title.includes("same.edf"),
    version,
  );
  await ready();
  assert.equal(await page.getByRole("dialog").count(), 0);
  assert.equal((await call("state")).state.calibrated, true);
  report.checks.push("same-size image retains calibration without prompting");
  // A dimension-bearing calibration can be selected before its new image.
  selectedCalibration = largeCalibration;
  const current = (await call("state")).state;
  for (const large of [false, true]) {
    await setInterfaceTextSize(page, large);
    await button("Load .poni").focus();
    await button("Load .poni").click();
    const dialog = page.getByRole("dialog", {
      name: "Calibration uses a different detector",
    });
    await dialog.waitFor({ state: "visible" });
    assert.deepEqual((await call("state")).state, current);
    const box = await dialog.boundingBox();
    assert.ok(
      box.x >= 0 &&
        box.y >= 0 &&
        box.x + box.width <= 1000 &&
        box.y + box.height <= 668,
    );
    await page.screenshot({
      path: path.join(
        artifacts,
        `calibration-first-${browserName}-${large ? "large" : "normal"}.png`,
      ),
    });
    await page.keyboard.press("Escape");
    await dialog.waitFor({ state: "detached" });
    assert.deepEqual((await call("state")).state, current);
    await page.waitForFunction(() =>
      document.activeElement?.textContent?.includes("Load .poni"),
    );
  }
  await button("Load .poni").click();
  await button("Load calibration and clear image").click();
  await ready();
  result = await call("state");
  assert.equal(result.state.hasImage, false);
  assert.equal(result.state.calibrated, true);
  assert.equal(result.state.calibrationName, "large.poni");
  assert.equal(result.pattern, null);
  assert.equal(result.cake, null);
  selectedImage = largeImage;
  await button("Open image").click();
  await ready();
  result = await call("state");
  assert.equal(result.state.calibrationName, "large.poni");
  assert.equal(result.state.calibrated, true);
  assert.deepEqual(result.state.shape, [1043, 981]);
  assert.equal(await page.getByRole("dialog").count(), 0);
  assert.ok(result.pattern?.y.length);
  report.checks.push(
    "calibration-first Cancel/Escape, clear stale image, matching image integrates",
  );
  // A legacy calibration without dimensions needs an explicit keep choice.
  selectedCalibration = legacyCalibration;
  await button("Load .poni").click();
  await ready();
  selectedImage = same;
  await page.keyboard.press("ControlOrMeta+o");
  await button("Open with current calibration").click();
  await ready();
  result = await call("state");
  assert.equal(result.state.calibrated, true);
  assert.equal(result.state.calibrationName, path.basename(legacyCalibration));
  assert.deepEqual(result.state.shape, [96, 128]);
  assert.deepEqual(result.state.calibration.transformations, []);
  report.checks.push(
    "legacy calibration can be kept explicitly across dimension change",
  );
  await button("Reset calibration").click();
  await page
    .getByRole("dialog", { name: "Reset calibration?" })
    .waitFor({ state: "visible" });
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Reset calibration", exact: true })
    .click();
  await ready();
  result = await call("state");
  assert.equal(result.state.calibrated, false);
  assert.equal(result.state.imageName, "same.edf");
  report.checks.push("explicit reset keeps current image");
  // Loading through the shared shortcut must retain every workspace, including
  // the selected calibration tab, even when accepting a detector-size reset.
  for (const mode of ["Integration", "Map", "Mask", "Calibration"]) {
    await button(mode).click();
    const calibrationTab = page.getByRole("tab", {
      name: "Step 2: Pick rings",
      exact: true,
    });
    if (mode === "Calibration") {
      await page
        .getByRole("tab", { name: "Step 3: Calibrate", exact: true })
        .click();
      await page
        .getByLabel("Distance constraint value", { exact: true })
        .fill("321.5");
      await calibrationTab.click();
    }
    selectedImage =
      mode === "Integration" || mode === "Mask"
        ? path.join(root, "desktop/tests/data/CeO2_Pilatus1M.tif")
        : small;
    const beforeSizeChange = (await call("state")).state;
    await page.keyboard.press("ControlOrMeta+o");
    const sizeNotice = page.getByRole("dialog", {
      name: "Image dimensions changed",
      exact: true,
    });
    await sizeNotice.waitFor({ state: "visible" });
    assert.ok(
      (await sizeNotice.textContent()).includes("No calibration is loaded"),
    );
    assert.equal(
      await sizeNotice
        .getByRole("button", {
          name: "Open and reset calibration",
          exact: true,
        })
        .count(),
      0,
    );
    assert.deepEqual((await call("state")).state, beforeSizeChange);
    if (mode === "Integration") {
      await page.keyboard.press("Escape");
      await sizeNotice.waitFor({ state: "detached" });
      assert.deepEqual((await call("state")).state, beforeSizeChange);
      await page.keyboard.press("ControlOrMeta+o");
      await sizeNotice.waitFor({ state: "visible" });
    }
    await sizeNotice
      .getByRole("button", { name: "Open image", exact: true })
      .click();
    await ready();
    assert.equal(await page.getByRole("dialog").count(), 0);
    assert.equal(await button(mode).getAttribute("aria-pressed"), "true");
    result = await call("state");
    assert.equal(result.state.imageName, path.basename(selectedImage));
    assert.equal(result.state.calibrated, false);
    assert.equal(result.state.maskedPixels, 0);
    if (mode === "Calibration")
      assert.equal(await calibrationTab.getAttribute("aria-selected"), "true");
    assert.deepEqual(result.state.calibration.transformations, []);
    report.checks.push(
      `uncalibrated size change explains coordinate-only reset in ${mode}`,
    );
    if (mode === "Calibration") {
      await page
        .getByRole("tab", { name: "Step 3: Calibrate", exact: true })
        .click();
      assert.equal(
        await page
          .getByLabel("Distance constraint value", { exact: true })
          .inputValue(),
        "321.5",
      );
      report.checks.push(
        "unapplied fit starting value survives uncalibrated size change",
      );
    }
  }
  assert.deepEqual(errors, []);
  await writeFile(
    path.join(artifacts, `report-${browserName}.json`),
    JSON.stringify(report, null, 2) + "\n",
  );
  console.log(JSON.stringify(report));
} catch (error) {
  await page.screenshot({
    path: path.join(artifacts, `failure-${browserName}.png`),
  });
  console.error(diagnostics.join("").slice(-4000));
  throw error;
} finally {
  await browser.close();
  await server.close();
  await native.close();
  await rm(temporary, { recursive: true, force: true });
}
