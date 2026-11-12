import assert from "node:assert/strict";
import path from "node:path";
import { mkdir, writeFile, readFile, rm } from "node:fs/promises";
import { pathToFileURL } from "node:url";
import { chromium, webkit } from "playwright";
import { nativeClient, root } from "./native_backend_client.mjs";
import { selectIntegrationDisplay } from "./integration_display.mjs";
import { setInterfaceTextSize } from "./plot_navigation.mjs";

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
      commands = [],
      positions = [];
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
        if (command === "validation_position")
          positions.push(structuredClone(args));

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
      await page.waitForTimeout(150);
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
    const patternBefore = await page.locator(".pattern-panel").boundingBox();
    const toolbarBefore = page.getByRole("group", {
      name: "Integration image controls",
      exact: true,
    });
    const placement = await toolbarBefore.evaluate((el) => {
      const b = el.getBoundingClientRect(),
        button = el
          .querySelector('[aria-label="Undock detector image"]')
          .getBoundingClientRect();
      return {
        left: b.left,
        controlsLeft: el
          .querySelector(".image-toolbar-primary")
          .getBoundingClientRect().left,
        right: b.right,
        buttonRight: button.right,
        bottom: b.bottom,
        buttonBottom: button.bottom,
        rows: [...el.querySelectorAll(".image-toolbar-group")].map(
          (n) => n.getBoundingClientRect().y,
        ),
      };
    });
    assert.ok(
      Math.abs(placement.right - placement.buttonRight) < 4 &&
        Math.abs(placement.bottom - placement.buttonBottom) < 4,
      "Undock is not at the lower-right of the image bar",
    );
    assert.ok(
      Math.abs(placement.controlsLeft - placement.left) < 2,
      "Image controls must start at the left of the bar",
    );
    assert.ok(
      new Set(placement.rows).size <= 2,
      "Image toolbar uses more than two rows",
    );
    await page.screenshot({
      path: path.join(artifacts, `${name}-docked-toolbar.png`),
    });
    let child = await detach();
    const patternDetached = await page.locator(".pattern-panel").boundingBox();
    assert.ok(
      patternDetached.width > patternBefore.width * 1.5,
      "Detaching did not release the image's width for the pattern",
    );
    assert.equal(
      await page
        .getByRole("group", { name: "Integration image controls", exact: true })
        .count(),
      0,
    );
    for (const label of [
      "Save image",
      "Image region of interest",
      "Show image phases",
      "Dock detector image",
    ])
      assert.equal(
        await child
          .getByRole("button", { name: label, exact: true })
          .isVisible(),
        true,
      );
    assert.equal(
      await child
        .getByRole("button", { name: "Azimuthal profile", exact: true })
        .count(),
      0,
    );
    for (const label of ["Apply detector mask", "Integration transparent mask"])
      assert.equal(
        await child
          .getByRole("checkbox", { name: label, exact: true })
          .isVisible(),
        true,
      );

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
    const maskFlag = (await native.invoke("state")).state.useMask;
    await child
      .getByRole("checkbox", { name: "Apply detector mask", exact: true })
      .click();
    await ready();
    assert.equal((await native.invoke("state")).state.useMask, !maskFlag);
    await child
      .getByRole("checkbox", { name: "Apply detector mask", exact: true })
      .click();
    await ready();
    const transparent = (await native.invoke("state")).state.transparentMask;
    await child
      .getByRole("checkbox", {
        name: "Integration transparent mask",
        exact: true,
      })
      .click();
    await ready();
    assert.equal(
      (await native.invoke("state")).state.transparentMask,
      !transparent,
    );
    await child
      .getByRole("checkbox", {
        name: "Integration transparent mask",
        exact: true,
      })
      .click();
    await ready();
    await child.getByRole("button", { name: "Cake", exact: true }).click();
    await child.getByTestId("cake-canvas").waitFor();
    assert.equal(await child.getByTestId("detector-canvas").count(), 0);
    await child.getByTestId("cake-canvas").hover();
    await child.waitForFunction(() =>
      document.querySelector('[data-testid="detector-readout"] [data-field]'),
    );
    await page.waitForFunction(
      () =>
        !document.querySelector('[data-testid="mouse-readout"]').dataset.plot,
    );

    // The complete bar stays within two rows with the window action last,
    // including the additional cake shift controls and larger interface text.
    for (const large of [false, true]) {
      await setInterfaceTextSize(page, large);
      await child.waitForFunction(
        (large) =>
          document.querySelector(".app").dataset.textSize ===
          (large ? "large" : "normal"),
        large,
      );
      for (const width of [420, 520]) {
        await child.setViewportSize({ width, height: 550 });
        await child.waitForTimeout(100);
        const layout = await child
          .getByRole("group", {
            name: "Integration image controls",
            exact: true,
          })
          .evaluate((el) => {
            const bar = el.getBoundingClientRect(),
              dock = el
                .querySelector('[aria-label="Dock detector image"]')
                .getBoundingClientRect();
            return {
              rows: [...el.querySelectorAll(".image-toolbar-group")].map(
                (g) => g.getBoundingClientRect().y,
              ),
              left: [...el.querySelectorAll(".image-toolbar-group")].every(
                (g) => Math.abs(g.getBoundingClientRect().left - bar.left) < 2,
              ),
              right: bar.right - dock.right,
              bottom: bar.bottom - dock.bottom,
              visible: [...el.querySelectorAll("button,input")].every((b) => {
                const r = b.getBoundingClientRect();
                return (
                  r.left >= 0 &&
                  r.right <= innerWidth &&
                  r.bottom <= innerHeight
                );
              }),
              overflow: document.documentElement.scrollWidth > innerWidth,
            };
          });
        assert.ok(
          new Set(layout.rows).size <= 2 &&
            layout.left &&
            layout.visible &&
            !layout.overflow,
          JSON.stringify({ width, large, layout }),
        );
        assert.ok(Math.abs(layout.right) < 4 && Math.abs(layout.bottom) < 4);
        if (width === 420)
          await child.screenshot({
            path: path.join(
              artifacts,
              `${name}-${large ? "larger" : "standard"}-cake-tools.png`,
            ),
          });
      }
    }
    await setInterfaceTextSize(page, false);
    await child.setViewportSize({ width: 900, height: 760 });
    await child.getByRole("button", { name: "Image", exact: true }).click();
    await child.getByTestId("detector-canvas").waitFor();
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
    await page.waitForFunction(
      () =>
        !document.querySelector('[data-testid="mouse-readout"]').dataset.plot,
    );
    assert.equal(
      await page.getByTestId("mouse-readout").locator("[data-field]").count(),
      0,
    );
    await child.mouse.click(x, y);
    await child.waitForFunction(
      () =>
        document.querySelector('[data-testid="detector-canvas"]').dataset
          .clickX != null,
    );
    assert.ok((await native.invoke("state")).linked?.imagePoint);
    await page.getByTestId("click-readout").waitFor();
    await child.getByTestId("detector-click-readout").waitFor();
    const clickedFields = await child
      .getByTestId("detector-click-readout")
      .locator("[data-field]")
      .allTextContents();
    assert.ok(clickedFields.length > 0);
    assert.deepEqual(
      await page
        .getByTestId("click-readout")
        .locator("[data-field]")
        .allTextContents(),
      clickedFields,
    );
    await page.getByTestId("pattern-canvas").hover();
    await page.waitForFunction(
      () =>
        document.querySelector('[data-testid="mouse-readout"]').dataset.plot ===
        "pattern",
    );
    assert.deepEqual(
      await page
        .getByTestId("click-readout")
        .locator("[data-field]")
        .allTextContents(),
      clickedFields,
      "The main window must retain the selected position while inspecting the pattern",
    );

    // One shared physical selection: image -> pattern, pattern -> image, then
    // image -> pattern again. Exercise user gestures, not direct model writes.
    const patternCanvas = page.getByTestId("pattern-canvas");
    const firstImageSelection = (await native.invoke("state")).linked;
    await page.waitForFunction(
      (radial) =>
        Math.abs(
          Number(
            document.querySelector('[data-testid="pattern-canvas"]').dataset
              .linkedPosition,
          ) - radial,
        ) < 1e-8,
      firstImageSelection.radial,
    );
    const patternPoint = await patternCanvas.evaluate((el) => ({
      x: Number(el.dataset.plotLeft) + Number(el.dataset.plotWidth) * 0.32,
      y: Number(el.dataset.plotTop) + Number(el.dataset.plotHeight) * 0.5,
    }));
    await patternCanvas.click({ position: patternPoint });
    await ready();
    const patternSelection = (await native.invoke("state")).linked;
    assert.equal(positions.at(-1).source, "pattern");
    assert.ok(Math.abs(patternSelection.radial - positions.at(-1).x) < 1e-8);
    assert.ok(
      Math.abs(patternSelection.radial - firstImageSelection.radial) > 1e-3,
    );
    assert.ok(
      patternSelection.imagePoint,
      "Pattern click did not project back onto the detector",
    );
    await child.waitForFunction((point) => {
      const d = document.querySelector(
        '[data-testid="detector-canvas"]',
      ).dataset;
      return (
        Math.abs(Number(d.clickX) - point.x) < 1e-8 &&
        Math.abs(Number(d.clickY) - point.y) < 1e-8 &&
        Number(d.ringCount) > 0
      );
    }, patternSelection.imagePoint);
    const patternFields = await page
      .getByTestId("click-readout")
      .locator("[data-field]")
      .allTextContents();
    assert.notDeepEqual(
      patternFields,
      clickedFields,
      "Pattern click left the previous click readout unchanged",
    );
    await child.waitForFunction(
      (fields) =>
        JSON.stringify(
          [
            ...document.querySelectorAll(
              '[data-testid="detector-click-readout"] [data-field]',
            ),
          ].map((el) => el.textContent),
        ) === JSON.stringify(fields),
      patternFields,
    );
    await child.mouse.click(x + 18, y - 14);
    await ready();
    const secondImageSelection = (await native.invoke("state")).linked;
    assert.equal(positions.at(-1).source, "image");
    assert.ok(
      Math.abs(secondImageSelection.radial - patternSelection.radial) > 1e-3,
    );
    await page.waitForFunction(
      (radial) =>
        Math.abs(
          Number(
            document.querySelector('[data-testid="pattern-canvas"]').dataset
              .linkedPosition,
          ) - radial,
        ) < 1e-8,
      secondImageSelection.radial,
    );
    const imageFields = await page
      .getByTestId("click-readout")
      .locator("[data-field]")
      .allTextContents();
    assert.notDeepEqual(
      imageFields,
      patternFields,
      "Image click left the pattern's click position unchanged",
    );
    await child.waitForFunction(
      (fields) =>
        JSON.stringify(
          [
            ...document.querySelectorAll(
              '[data-testid="detector-click-readout"] [data-field]',
            ),
          ].map((el) => el.textContent),
        ) === JSON.stringify(fields),
      imageFields,
    );
    assert.deepEqual((await native.invoke("state")).linked.imagePoint, {
      x: positions.at(-1).x,
      y: positions.at(-1).y,
    });

    // The detached cake shares the same selection, including when its radial
    // labels display Q while its immutable scientific grid remains in 2theta.
    await child.getByRole("button", { name: "Cake", exact: true }).click();
    const cakeCanvas = child.getByTestId("cake-canvas");
    await cakeCanvas.waitFor();
    await ready();
    const sharedCakeClick = async () => {
      const fields = await page
        .getByTestId("click-readout")
        .locator("[data-field]")
        .allTextContents();
      assert.ok(fields.length > 0);
      await child.waitForFunction(
        (expected) =>
          JSON.stringify(
            [
              ...document.querySelectorAll(
                '[data-testid="detector-click-readout"] [data-field]',
              ),
            ].map((el) => el.textContent),
          ) === JSON.stringify(expected),
        fields,
      );
      return fields;
    };
    for (const unit of ["2th_deg", "q_A^-1"]) {
      if (unit === "q_A^-1") {
        await page
          .getByRole("button", { name: "Pattern unit Q", exact: true })
          .click();
        await ready();
      }
      await cakeCanvas.waitFor();
      await child.waitForFunction(
        (unit) =>
          document.querySelector('[data-testid="cake-canvas"]').dataset
            .radialDisplayUnit === unit,
        unit,
      );
      const beforeCake = (await native.invoke("state")).linked;
      const cakePoint = await cakeCanvas.evaluate((el) => ({
        x: Number(el.dataset.plotLeft) + Number(el.dataset.plotWidth) * 0.38,
        y: Number(el.dataset.plotTop) + Number(el.dataset.plotHeight) * 0.35,
      }));
      await cakeCanvas.click({ position: cakePoint });
      await ready();
      const cakeState = await native.invoke("state"),
        cakeSelection = cakeState.linked;
      assert.equal(cakeState.state.unit, unit);
      assert.equal(positions.at(-1).source, "cake");
      assert.equal(positions.at(-1).unit, "2th_deg");
      assert.ok(Math.abs(cakeSelection.twoTheta - positions.at(-1).x) < 1e-8);
      assert.ok(
        Math.abs(cakeSelection.azimuth - positions.at(-1).azimuth) < 1e-8,
      );
      assert.ok(
        Math.abs(cakeSelection.twoTheta - beforeCake.twoTheta) > 1e-3 ||
          Math.abs(cakeSelection.azimuth - beforeCake.azimuth) > 1e-3,
      );
      await page.waitForFunction(
        (radial) =>
          Math.abs(
            Number(
              document.querySelector('[data-testid="pattern-canvas"]').dataset
                .linkedPosition,
            ) - radial,
          ) < 1e-8,
        cakeSelection.radial,
      );
      const cakeFields = await sharedCakeClick();
      const nextPatternPoint = await patternCanvas.evaluate((el) => ({
        x: Number(el.dataset.plotLeft) + Number(el.dataset.plotWidth) * 0.57,
        y: Number(el.dataset.plotTop) + Number(el.dataset.plotHeight) * 0.5,
      }));
      await patternCanvas.click({ position: nextPatternPoint });
      await ready();
      const fromPattern = await native.invoke("state"),
        selectedCake = fromPattern.cake,
        linkedCake = fromPattern.linked;
      assert.equal(positions.at(-1).source, "pattern");
      assert.ok(Math.abs(linkedCake.radial - positions.at(-1).x) < 1e-8);
      assert.ok(Math.abs(linkedCake.radial - cakeSelection.radial) > 1e-3);
      assert.ok(
        Math.abs(linkedCake.azimuth - cakeSelection.azimuth) < 1e-8,
        "Pattern click lost the selected cake azimuth",
      );
      assert.equal(selectedCake.unit, "2th_deg");
      const expectedCakePoint = {
        x:
          0.5 +
          ((linkedCake.twoTheta - selectedCake.radialRange[0]) /
            (selectedCake.radialRange[1] - selectedCake.radialRange[0])) *
            (selectedCake.fullWidth - 1),
        y:
          ((linkedCake.azimuth - selectedCake.azimuthRange[0]) /
            (selectedCake.azimuthRange[1] - selectedCake.azimuthRange[0])) *
          selectedCake.fullHeight,
        radial: linkedCake.twoTheta,
      };
      await child.waitForFunction((point) => {
        const d = document.querySelector('[data-testid="cake-canvas"]').dataset;
        return (
          Math.abs(Number(d.clickX) - point.x) < 1e-8 &&
          Math.abs(Number(d.clickY) - point.y) < 1e-8 &&
          Math.abs(Number(d.linkedPosition) - point.radial) < 1e-8
        );
      }, expectedCakePoint);
      assert.notDeepEqual(
        await sharedCakeClick(),
        cakeFields,
        "Pattern click left the cake's click readout unchanged",
      );
    }
    await page
      .getByRole("button", { name: "Pattern unit 2θ", exact: true })
      .click();
    await ready();
    await child.getByRole("button", { name: "Image", exact: true }).click();
    await child.getByTestId("detector-canvas").waitFor();
    await ready();

    // Main task controls still mutate the very same session and appear remotely.
    await child
      .getByRole("button", { name: "Image region of interest", exact: true })
      .click();
    await ready();
    await child.waitForFunction(
      () =>
        !!document.querySelector('[data-testid="detector-canvas"]').dataset
          .roi &&
        !document.querySelector('[aria-label="Image region of interest"]')
          .disabled,
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
    await canvas.focus();
    await child.keyboard.press("f");
    await child.waitForTimeout(100);
    const fitted = await canvas.evaluate((c) => ({
      d: { ...c.dataset },
      b: c.getBoundingClientRect().toJSON(),
    }));
    Object.assign(roi, fitted);
    await child.mouse.move(sx(roi.roi[2]), sy(roi.roi[0]));
    await child.mouse.down();
    await child.mouse.move(sx(roi.roi[2]) + 20, sy(roi.roi[0]) - 20, {
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
    await child.getByRole("button", { name: "Cake", exact: true }).click();
    await child.getByTestId("cake-canvas").waitFor();
    await child
      .getByRole("button", { name: "Cake histogram settings", exact: true })
      .click();
    await child
      .getByLabel("Cake maximum intensity", { exact: true })
      .fill("4500");
    await child
      .getByLabel("Cake maximum intensity", { exact: true })
      .press("Enter");
    await child
      .getByRole("button", {
        name: "Close cake display settings",
        exact: true,
      })
      .click();
    await child.getByRole("button", { name: "Image", exact: true }).click();
    await child.getByTestId("detector-canvas").waitFor();
    assert.equal(
      await child
        .getByTestId("detector-canvas")
        .getAttribute("data-intensity-max"),
      "9000",
    );
    await child.getByRole("button", { name: "Cake", exact: true }).click();
    await child.getByTestId("cake-canvas").waitFor();
    assert.equal(
      await child.getByTestId("cake-canvas").getAttribute("data-intensity-max"),
      "4500",
    );
    await child.getByRole("button", { name: "Image", exact: true }).click();
    await child.getByTestId("detector-canvas").waitFor();
    await child
      .getByRole("button", { name: "Dock detector image", exact: true })
      .click();
    await page.getByTestId("detector-canvas").waitFor();
    await page.getByTestId("detector-canvas").hover();
    await page.waitForFunction(
      () =>
        document.querySelector('[data-testid="mouse-readout"]').dataset.plot ===
        "detector",
    );
    const patternRedocked = await page.locator(".pattern-panel").boundingBox();
    assert.ok(
      Math.abs(patternRedocked.width - patternBefore.width) < 2,
      "Docking did not restore the saved image/pattern split",
    );
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
    await page
      .getByRole("button", { name: "Integration", exact: true })
      .click();
    await ready();
    await child.getByTestId("detector-canvas").waitFor();
    await page.getByRole("button", { name: "Map", exact: true }).click();
    await ready();
    const mapCanvas = page
      .locator(".map-detector-panel")
      .getByTestId("detector-canvas");
    const imageTab = page.getByRole("tab", { name: "Image", exact: true });
    if (!(await mapCanvas.isVisible()) && (await imageTab.isVisible()))
      await imageTab.click();
    await mapCanvas.waitFor({ state: "visible" });
    assert.equal(
      await page
        .locator(".map-detector-panel .detector-detached-placeholder")
        .count(),
      0,
    );
    assert.equal(
      await page
        .locator(".map-detector-panel")
        .getByRole("button", { name: "Undock detector image", exact: true })
        .count(),
      0,
    );
    await child.close();
    await page.waitForTimeout(300);
    assert.equal(
      await mapCanvas.isVisible(),
      true,
      "Closing Integration's detector window removed Map's image",
    );
    await page.screenshot({
      path: path.join(artifacts, `${name}-map-embedded.png`),
    });
    await page
      .getByRole("button", { name: "Integration", exact: true })
      .click();
    await ready();
    child = await detach();
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
    await child
      .getByRole("button", { name: "Save image", exact: true })
      .click();
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
      patternToDetachedImageClick: true,
      detachedImageToPatternClick: true,
      detachedCakeToPatternClick: true,
      patternToDetachedCakeClick: true,
      detachedCakeClickUnits: ["2th_deg", "q_A^-1"],
      roi: true,
      maskAndUndo: true,
      polygonKeyboard: true,
      configurationContrast: true,
      staleInteractionRejected: true,
      calibrationPicking: true,
      detectorPngExport: true,
      completeDetachedToolbar: true,
      readoutsStayWithTheirWindow: true,
      runtime: "rust",
      processorPid: native.child.pid,
      patternUsesFreedImageSpace: true,
      detachedCakeSwitch: true,
      independentEmbeddedMapDetector: true,
      mapDetectorCannotDetach: true,
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
