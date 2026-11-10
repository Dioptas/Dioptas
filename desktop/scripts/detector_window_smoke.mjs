import assert from "node:assert/strict";
import path from "node:path";
import { mkdir, writeFile, readFile, rm } from "node:fs/promises";
import { pathToFileURL } from "node:url";
import { chromium, webkit } from "playwright";
import { nativeClient, root } from "./native_backend_client.mjs";
import { selectIntegrationDisplay } from "./integration_display.mjs";

const artifacts = path.join(root, "desktop/artifacts/detector-window");
await mkdir(artifacts, { recursive: true });
const receipts = [];
for (const [name, browserType] of [
  ["chromium", chromium],
  ["webkit", webkit],
]) {
  const native = nativeClient();
  let browser;
  try {
    assert.equal((await native.invoke("__host__")).runtime, "rust");
    await native.invoke("open_image", {
      path: path.join(root, "dioptas/tests/data/CeO2_Pilatus1M.tif"),
    });
    await native.invoke("open_calibration", {
      path: path.join(root, "dioptas/tests/data/CeO2_Pilatus1M.poni"),
    });
    browser = await browserType.launch({ headless: true });
    const context = await browser.newContext({
      viewport: { width: 1000, height: 668 },
    });
    const errors = [],
      failures = [],
      commands = [];
    const pngPath = path.join(artifacts, `${name}-detector-export.png`);
    await rm(pngPath, { force: true });
    let finishExport;
    const exported = new Promise((resolve) => {
      finishExport = resolve;
    });
    context.on("page", (p) => p.on("pageerror", (e) => errors.push(e.message)));
    await context.exposeBinding(
      "__nativeInvoke",
      async (_, command, args = {}) => {
        commands.push(command);
        if (command === "integration_save_image")
          args = { ...args, path: pngPath };
        const reply = await native.invoke(command, args);
        if (command === "integration_save_image") finishExport(reply);
        if (!reply.ok && !reply.cancelled)
          failures.push(`${command}: ${reply.error}`);
        return native.browserResult(reply);
      },
    );
    await context.addInitScript(() => {
      try {
        localStorage.setItem("dioptas-layout:configuration-controls", "true");
      } catch {}
      window.pywebview = {
        api: {
          invoke: (command, args) => window.__nativeInvoke(command, args),
        },
      };
    });
    const page = await context.newPage();
    page.setDefaultTimeout(20000);
    await page.goto(
      pathToFileURL(path.join(root, "dioptas/desktop/ui/index.html")).href,
    );
    const ready = async () => {
      await page.waitForFunction(() => !document.querySelector(".spin"));
      await page.waitForTimeout(120);
    };
    await page
      .getByRole("button", { name: "Integration", exact: true })
      .click();
    await selectIntegrationDisplay(page, "image");
    await ready();
    const before = await native.invoke("state");
    const levelsBefore = commands.filter((c) => c === "image_levels").length;
    const detach = async () => {
      const popup = page.waitForEvent("popup");
      await page
        .getByRole("button", { name: "Undock detector image", exact: true })
        .click();
      const child = await popup;
      child.setDefaultTimeout(20000);
      await child.getByTestId("detector-canvas").waitFor();
      await child.waitForTimeout(250);
      return child;
    };
    let child = await detach();
    assert.equal(await page.getByTestId("detector-canvas").count(), 0);
    assert.equal(await child.locator(".intensity-histogram").count(), 1);
    assert.equal(
      await child
        .getByTestId("detector-canvas")
        .getAttribute("data-full-width"),
      "981",
    );
    assert.equal(
      await child
        .getByTestId("detector-canvas")
        .getAttribute("data-full-height"),
      "1043",
    );
    assert.equal(
      commands.filter((c) => c === "image_levels").length,
      levelsBefore,
      "Undocking recalculated Auto levels",
    );
    await page.getByRole("button", { name: "Show detector window" }).click();
    assert.equal(
      context.pages().length,
      2,
      "Repeated open created another window",
    );
    let canvas = child.getByTestId("detector-canvas");
    const bounds = await canvas.boundingBox();
    const x = bounds.x + bounds.width * 0.48,
      y = bounds.y + bounds.height * 0.45;
    const fullRange =
      Number(await canvas.getAttribute("data-view-x-max")) -
      Number(await canvas.getAttribute("data-view-x-min"));
    await child.mouse.move(x, y);
    await child.mouse.wheel(0, -350);
    await child.waitForFunction(() => {
      const d = document.querySelector(
        '[data-testid="detector-canvas"]',
      ).dataset;
      return +d.viewXMax - +d.viewXMin < +d.fullWidth;
    });
    const zoomRange =
      Number(await canvas.getAttribute("data-view-x-max")) -
      Number(await canvas.getAttribute("data-view-x-min"));
    assert.ok(zoomRange < fullRange);
    const scale = await canvas.evaluate((c) => {
      const d = c.dataset;
      return (
        +d.plotWidth /
        (+d.viewXMax - +d.viewXMin) /
        (+d.plotHeight / (+d.viewYMax - +d.viewYMin))
      );
    });
    assert.ok(Math.abs(scale - 1) < 0.00001, "Detector pixels are not square");
    const previousX = await canvas.getAttribute("data-view-x-min");
    await child.mouse.move(x, y);
    await child.mouse.down({ button: "right" });
    await child.mouse.move(x + 35, y + 25, { steps: 5 });
    await child.mouse.up({ button: "right" });
    assert.notEqual(await canvas.getAttribute("data-view-x-min"), previousX);
    await child.mouse.move(x, y);
    await child.waitForFunction(() =>
      document
        .querySelector('[data-testid="detector-readout"]')
        .textContent.includes("I"),
    );
    await child.mouse.click(x, y);
    await child.waitForFunction(
      () =>
        document.querySelector('[data-testid="detector-canvas"]').dataset
          .clickX != null,
    );
    assert.ok((await native.invoke("state")).linked?.imagePoint);
    // Main task controls still mutate the very same session and appear remotely.
    await page
      .getByRole("button", { name: "Image region of interest", exact: true })
      .click();
    await ready();
    await child.waitForFunction(
      () =>
        !!document.querySelector('[data-testid="detector-canvas"]').dataset.roi,
    );
    const roiBefore = (await native.invoke("state")).state.integration.roi;
    assert.ok(roiBefore);
    const roi = await canvas.evaluate((c) => ({
      roi: c.dataset.roi.split(",").map(Number),
      d: { ...c.dataset },
      b: c.getBoundingClientRect().toJSON(),
    }));
    const sx = (v) =>
      roi.b.x +
      +roi.d.plotLeft +
      ((v - +roi.d.viewXMin) / (+roi.d.viewXMax - +roi.d.viewXMin)) *
        +roi.d.plotWidth;
    const sy = (v) =>
      roi.b.y +
      +roi.d.plotTop +
      ((+roi.d.viewYMax - v) / (+roi.d.viewYMax - +roi.d.viewYMin)) *
        +roi.d.plotHeight;
    // F restores full extent before moving an ROI corner.
    await canvas.click();
    await child.keyboard.press("f");
    await child.waitForTimeout(100);
    const fitted = await canvas.evaluate((c) => ({
      d: { ...c.dataset },
      b: c.getBoundingClientRect().toJSON(),
    }));
    Object.assign(roi, fitted);
    await child.mouse.move(sx(roi.roi[0]), sy(roi.roi[2]));
    await child.mouse.down();
    await child.mouse.move(sx(roi.roi[0]) + 20, sy(roi.roi[2]) - 20, {
      steps: 5,
    });
    await child.mouse.up();
    await ready();
    assert.notDeepEqual(
      (await native.invoke("state")).state.integration.roi,
      roiBefore,
      "Detached ROI edit did not reach owner",
    );
    await child
      .getByRole("button", { name: "Detector histogram settings", exact: true })
      .click();
    await child.getByLabel("Maximum intensity", { exact: true }).fill("9000");
    await child.getByLabel("Maximum intensity", { exact: true }).press("Enter");
    await child.waitForFunction(
      () =>
        document.querySelector('[data-testid="detector-canvas"]').dataset
          .intensityMax === "9000",
    );
    await child
      .getByRole("button", {
        name: "Close detector display settings",
        exact: true,
      })
      .click();
    await child
      .getByRole("button", { name: "Dock detector image", exact: true })
      .click();
    await page.getByTestId("detector-canvas").waitFor();
    assert.equal(
      await page
        .getByTestId("detector-canvas")
        .getAttribute("data-intensity-max"),
      "9000",
    );
    child = await detach();
    await child.close();
    await page.getByTestId("detector-canvas").waitFor();
    assert.equal((await native.invoke("state")).state.calibrated, true);
    child = await detach();
    canvas = child.getByTestId("detector-canvas");
    await child.evaluate(() => {
      window.addEventListener("message", (event) => {
        if (event.data?.message?.type === "presentation")
          window.__testDetectorIdentity =
            event.data.message.presentation?.identity;
        if (
          event.data?.message?.type === "response" &&
          event.data.message.id === "stale-test"
        )
          window.__staleDetectorResponse = event.data.message;
      });
    });
    await page.getByRole("button", { name: "Mask", exact: true }).click();
    await ready();
    await page.getByRole("button", { name: "Rectangle", exact: true }).click();
    await child.waitForTimeout(250);
    const maskBefore = (await native.invoke("state")).state.maskedPixels;
    const box = await child.getByTestId("detector-canvas").boundingBox();
    await child.mouse.click(
      box.x + box.width * 0.35,
      box.y + box.height * 0.35,
    );
    await child.waitForTimeout(150);
    await child.mouse.click(
      box.x + box.width * 0.45,
      box.y + box.height * 0.45,
    );
    await ready();
    assert.ok(
      (await native.invoke("state")).state.maskedPixels > maskBefore,
      "Detached mask drawing did not apply",
    );
    await page.getByRole("button", { name: "Undo", exact: true }).click();
    await ready();
    assert.equal((await native.invoke("state")).state.maskedPixels, maskBefore);
    // Point strokes and polygon keyboard completion run the existing mask owner.
    await page.getByRole("button", { name: "Polygon", exact: true }).click();
    await child.waitForTimeout(150);
    for (const [a, b] of [
      [0.2, 0.2],
      [0.3, 0.2],
      [0.25, 0.3],
    ]) {
      await child.mouse.click(box.x + box.width * a, box.y + box.height * b);
      await child.waitForTimeout(120);
    }
    await child.locator("body").press("Enter");
    await ready();
    assert.ok(
      (await native.invoke("state")).state.maskedPixels > maskBefore,
      "Polygon Enter did not forward",
    );
    await page
      .getByRole("button", { name: "Integration", exact: true })
      .click();
    await ready();

    await page.getByRole("button", { name: "Duplicate", exact: true }).click();
    await ready();
    await child.waitForTimeout(200);
    await child
      .getByRole("button", { name: "Detector histogram settings", exact: true })
      .click();
    await child.getByLabel("Maximum intensity", { exact: true }).fill("4500");
    await child.getByLabel("Maximum intensity", { exact: true }).press("Enter");
    await child
      .getByRole("button", {
        name: "Close detector display settings",
        exact: true,
      })
      .click();
    const previousIdentity = await child.evaluate(
      () => window.__testDetectorIdentity,
    );
    assert.ok(previousIdentity);
    await page
      .getByLabel("Active configuration", { exact: true })
      .selectOption("0");
    await ready();
    await child.waitForFunction(
      () =>
        document.querySelector('[data-testid="detector-canvas"]').dataset
          .intensityMax === "9000",
    );
    await child.evaluate(
      (identity) =>
        window.opener.postMessage(
          {
            detectorWindowSession: new URLSearchParams(location.search).get(
              "detector_window",
            ),
            target: "detector-window-main",
            message: {
              type: "event",
              id: "stale-test",
              identity,
              callback: "intensity.onLimits",
              args: [[0, 1]],
            },
          },
          "*",
        ),
      previousIdentity,
    );
    await child.waitForFunction(() => !!window.__staleDetectorResponse?.error);
    assert.equal(
      await canvas.getAttribute("data-intensity-max"),
      "9000",
      "A stale display event changed the new configuration",
    );
    await page
      .getByLabel("Active configuration", { exact: true })
      .selectOption("1");
    await ready();
    await child.waitForFunction(
      () =>
        document.querySelector('[data-testid="detector-canvas"]').dataset
          .intensityMax === "4500",
    );
    await page
      .getByRole("button", { name: "Calibration", exact: true })
      .click();
    await page
      .getByRole("tab", { name: "Step 2: Pick rings", exact: true })
      .click();
    await ready();
    await child.waitForTimeout(200);
    const pickCount = (await native.invoke("state")).state.calibration.picks
      .length;
    const seed = await canvas.evaluate((c) => {
      const b = c.getBoundingClientRect(),
        d = c.dataset;
      return {
        x:
          b.x +
          +d.plotLeft +
          ((637 - +d.viewXMin) / (+d.viewXMax - +d.viewXMin)) * +d.plotWidth,
        y:
          b.y +
          +d.plotTop +
          ((+d.viewYMax - 564) / (+d.viewYMax - +d.viewYMin)) * +d.plotHeight,
      };
    });
    await child.mouse.click(seed.x, seed.y);
    await ready();
    assert.ok(
      (await native.invoke("state")).state.calibration.picks.length > pickCount,
      "Detached calibration picking did not reach the original owner",
    );
    await page.getByRole("button", { name: "Map", exact: true }).click();
    await ready();
    await child.getByTestId("detector-canvas").waitFor();
    await page
      .getByRole("button", { name: "Integration", exact: true })
      .click();
    await ready();
    const dockBounds = await child
      .getByRole("button", { name: "Dock detector image", exact: true })
      .boundingBox();
    assert.ok(
      dockBounds.x >= 0 &&
        dockBounds.y >= 0 &&
        dockBounds.x + dockBounds.width <= 900 &&
        dockBounds.y + dockBounds.height <= 760,
      "Dock button is outside its window",
    );
    assert.ok(
      await child
        .locator(".app")
        .evaluate((el) => el.getBoundingClientRect().width <= innerWidth),
      "Detached layout exceeds the viewport",
    );
    await page.getByRole("button", { name: "Save image", exact: true }).click();
    let exportTimer;
    const saved = await Promise.race([
      exported,
      new Promise((_, reject) => {
        exportTimer = setTimeout(
          () => reject(Error("Detached PNG export timed out")),
          15000,
        );
      }),
    ]).finally(() => clearTimeout(exportTimer));
    assert.equal(saved.ok, true, saved.error);
    assert.deepEqual(
      [...(await readFile(pngPath)).subarray(0, 8)],
      [137, 80, 78, 71, 13, 10, 26, 10],
    );
    await child.screenshot({
      path: path.join(artifacts, `${name}-detached.png`),
    });
    const state = (await native.invoke("state")).state;
    assert.equal(state.configurationCount, 2);
    assert.equal(state.calibrated, true);
    assert.equal(state.imagePath, before.state.imagePath);
    assert.deepEqual(errors, []);
    assert.deepEqual(failures, []);
    receipts.push({
      browser: name,
      fullResolution: [981, 1043],
      squarePixels: true,
      windowReuse: true,
      closeRedocks: true,
      zoomPanReadout: true,
      linkedInspection: true,
      roi: true,
      maskAndUndo: true,
      polygonKeyboard: true,
      configurationContrast: true,
      staleInteractionRejected: true,
      calibrationPicking: true,
      detectorPngExport: true,
      sharedMapDetector: true,
      sourceCalibrated: state.calibrated,
      errors,
      failures,
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
