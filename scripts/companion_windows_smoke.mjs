// All companions open together, real user gestures and one Rust stdio owner.
import assert from "node:assert/strict";
import { mkdir, readdir, writeFile } from "node:fs/promises";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { chromium, webkit } from "playwright";
import { nativeClient, root } from "./native_backend_client.mjs";

const artifacts = path.join(root, "artifacts/companion-windows");
await mkdir(artifacts, { recursive: true });
const folder = path.join(root, "tests/data/map");
const paths = (await readdir(folder))
  .filter((file) => file.endsWith(".tif"))
  .sort()
  .map((file) => path.join(folder, file));
assert.equal(paths.length, 9);
const receipts = [];
for (const [name, engine] of [
  ["chromium", chromium],
  ["webkit", webkit],
]) {
  const native = nativeClient();
  let browser;
  const errors = [],
    failures = [],
    commands = [],
    steps = [];
  const call = async (command, args = {}) => {
    commands.push(command);
    const reply = await native.invoke(command, args);
    if (!reply.ok && !reply.cancelled)
      failures.push(`${command}: ${reply.error}`);
    assert.equal(reply.ok, true, `${command}: ${reply.error}`);
    return reply;
  };
  try {
    assert.equal((await native.invoke("__host__")).runtime, "rust");
    await call("open_calibration", {
      path: path.join(root, "tests/data/CeO2_Pilatus1M.poni"),
    });
    await call("integration_settings", { bins: 256, cake_bins: 72 });
    await call("batch_load", { paths });
    await call("map_load", { paths });
    browser = await engine.launch({ headless: true });
    const context = await browser.newContext({
      viewport: { width: 1440, height: 1000 },
    });
    context.on("page", (page) =>
      page.on("pageerror", (error) => errors.push(error.message)),
    );
    await context.exposeBinding(
      "__nativeInvoke",
      async (_, command, args = {}) =>
        native.browserResult(await call(command, args)),
    );
    await context.addInitScript(() => {
      window.__companionPending = 0;
      window.pywebview = {
        api: {
          invoke: async (command, args) => {
            window.__companionPending++;
            try {
              return await window.__nativeInvoke(command, args);
            } finally {
              window.__companionPending--;
            }
          },
        },
      };
    });
    const main = await context.newPage();
    main.setDefaultTimeout(20000);
    await main.addInitScript(() =>
      localStorage.setItem("dioptas-batch:docked", "false"),
    );
    await main.goto(pathToFileURL(path.join(root, "dist/index.html")).href);
    const ready = async () => {
      await main.evaluate(
        () =>
          new Promise((resolve) =>
            requestAnimationFrame(() => requestAnimationFrame(resolve)),
          ),
      );
      await main.waitForFunction(
        () => !window.__companionPending && !document.querySelector(".spin"),
      );
    };
    await main
      .getByRole("button", { name: "Integration", exact: true })
      .click();
    await ready();
    const batchPopup = main.waitForEvent("popup");
    await main
      .getByRole("button", { name: "Batch view…", exact: true })
      .click();
    let batch = await batchPopup;
    batch.setDefaultTimeout(20000);
    await batch.getByTestId("batch-heatmap").waitFor();
    await main.getByRole("button", { name: "Map", exact: true }).click();
    const mapPopup = main.waitForEvent("popup");
    await main.getByRole("button", { name: "Detach map", exact: true }).click();
    let map = await mapPopup;
    map.setDefaultTimeout(20000);
    await map.getByTestId("scan-map").waitFor();
    await main
      .getByRole("button", { name: "Undock detector image", exact: true })
      .waitFor();
    const imagePopup = main.waitForEvent("popup");
    await main
      .getByRole("button", { name: "Undock detector image", exact: true })
      .click();
    let image = await imagePopup;
    image.setDefaultTimeout(20000);
    await image.getByTestId("detector-canvas").waitFor();
    await ready();
    let batchFrame = 0,
      mapFrame = 0,
      imageKind = "image";
    const fields = () =>
      main
        .getByTestId("click-readout")
        .locator("[data-field]")
        .allTextContents();
    const close = (actual, expected, label) =>
      assert.ok(
        Math.abs(actual - expected) < 1e-7,
        `${label}: ${actual} vs ${expected}`,
      );
    const linkedValue = (position, unit, wavelength) => {
      if (unit === "2th_deg") return position.twoTheta;
      const q =
        (4 * Math.PI * Math.sin((position.twoTheta * Math.PI) / 360)) /
        (wavelength * 1e10);
      return unit === "q_A^-1" ? q : (2 * Math.PI) / q;
    };
    const check = async (step, { retainedFrom, changedFrom } = {}) => {
      await ready();
      const state = await call("state");
      assert.ok(state.linked, `${step}: missing shared inspection`);
      const surfaces = new Set([main, image, batch, map]);
      assert.deepEqual(
        new Set(context.pages()),
        surfaces,
        `${step}: a companion closed or duplicated`,
      );
      if (retainedFrom) {
        close(
          state.linked.twoTheta,
          retainedFrom.linked.twoTheta,
          `${step}: radial bookmark lost`,
        );
        close(
          state.linked.azimuth,
          retainedFrom.linked.azimuth,
          `${step}: azimuth bookmark lost`,
        );
      }
      if (changedFrom)
        assert.ok(
          Math.abs(state.linked.twoTheta - changedFrom.linked.twoTheta) > 1e-3,
          `${step}: click did not change the physical radial position`,
        );
      assert.equal(
        state.batch.selected,
        batchFrame,
        `${step}: wrong Batch frame`,
      );
      assert.equal(state.map.selected, mapFrame, `${step}: wrong Map cell`);
      const expected = await fields();
      assert.ok(
        expected.length >= 3,
        `${step}: missing main click coordinates`,
      );
      for (const [page, id] of [
        [image, "detector-click-readout"],
        [batch, "batch-click-readout"],
        [map, "map-click-readout"],
      ]) {
        if (page === main) continue;
        await page.getByTestId(id).waitFor();
        await page.waitForFunction(
          ({ id, expected }) =>
            JSON.stringify(
              [
                ...document.querySelectorAll(
                  `[data-testid="${id}"] [data-field]`,
                ),
              ].map((element) => element.textContent),
            ) === JSON.stringify(expected),
          { id, expected },
        );
      }
      // A selected stored Map pattern can use a different axis unit from the
      // Integration settings. Compare the same physical position in that axis.
      let patternUnit = state.pattern.unit;
      if (map === main) {
        patternUnit = null;
        for (const [label, unit] of [
          ["2θ", "2th_deg"],
          ["Q", "q_A^-1"],
          ["d", "d_A"],
        ])
          if (
            (await main
              .getByRole("button", {
                name: `Map pattern unit ${label}`,
                exact: true,
              })
              .getAttribute("aria-pressed")) === "true"
          )
            patternUnit = unit;
        assert.ok(patternUnit, `${step}: missing active Map pattern unit`);
      }
      await main.waitForFunction(
        (radial) =>
          Math.abs(
            Number(
              document.querySelector('[data-testid="pattern-canvas"]').dataset
                .linkedPosition,
            ) - radial,
          ) < 1e-7,
        linkedValue(state.linked, patternUnit, state.state.geometry.wavelength),
      );
      const batchUnit = await batch
        .getByTestId("batch-heatmap")
        .getAttribute("data-unit");
      await batch.waitForFunction(
        (radial) =>
          Math.abs(
            Number(
              document.querySelector('[data-testid="batch-heatmap"]').dataset
                .linkedPosition,
            ) - radial,
          ) < 1e-7,
        linkedValue(state.linked, batchUnit, state.state.geometry.wavelength),
      );
      await batch.waitForFunction(
        (selected) =>
          document.querySelector(".batch-series-panel").dataset
            .selectedFrame === String(selected),
        batchFrame,
      );
      await map.waitForFunction(
        (cell) =>
          document.querySelector('[data-testid="scan-map"]').dataset
            .selectedCell === cell,
        state.map.selectedCell.join(","),
      );
      // Map's detector stays embedded; docking Map must not redirect its
      // image into the Integration companion. All readouts above stay linked.
      const activeImagePage = map === main ? main : image;
      const activeImageKind = map === main ? "image" : imageKind;
      const activeImageSelector =
        map === main
          ? '.map-detector-panel [data-testid="detector-canvas"]'
          : `[data-testid="${activeImageKind === "image" ? "detector" : "cake"}-canvas"]`;
      const activeCanvas = activeImagePage.locator(activeImageSelector);
      if (map === main && !(await activeCanvas.isVisible()))
        await main.getByRole("tab", { name: "Image", exact: true }).click();
      await activeCanvas.waitFor();
      if (activeImageKind === "image") {
        assert.ok(
          state.linked.imagePoint,
          `${step}: no projected detector point`,
        );
        await activeImagePage.waitForFunction(
          ({ point, selector }) => {
            const d = document.querySelector(selector).dataset;
            return (
              Math.abs(Number(d.clickX) - point.x) < 1e-7 &&
              Math.abs(Number(d.clickY) - point.y) < 1e-7 &&
              Number(d.ringCount) > 0
            );
          },
          { point: state.linked.imagePoint, selector: activeImageSelector },
        );
      } else {
        assert.equal(state.cake.unit, "2th_deg");
        const cake = state.cake,
          p = state.linked;
        await activeImagePage.waitForFunction(
          (point) => {
            const d = document.querySelector(
              '[data-testid="cake-canvas"]',
            ).dataset;
            return (
              Math.abs(Number(d.clickX) - point.x) < 1e-7 &&
              Math.abs(Number(d.clickY) - point.y) < 1e-7
            );
          },
          {
            x:
              0.5 +
              ((p.twoTheta - cake.radialRange[0]) /
                (cake.radialRange[1] - cake.radialRange[0])) *
                (cake.fullWidth - 1),
            y:
              ((p.azimuth - cake.azimuthRange[0]) /
                (cake.azimuthRange[1] - cake.azimuthRange[0])) *
              cake.fullHeight,
          },
        );
      }
      for (const page of [main, image, batch, map])
        assert.deepEqual(
          (await page.getByRole("alert").allTextContents())
            .map((text) => text.trim())
            .filter(Boolean),
          [],
          `${step}: visible application error`,
        );
      steps.push({
        step,
        unit: state.state.unit,
        patternUnit,
        radial: state.linked.radial,
        twoTheta: state.linked.twoTheta,
        azimuth: state.linked.azimuth,
        batchFrame,
        mapFrame,
        fields: expected,
        detached: {
          detector: image !== main,
          batch: batch !== main,
          map: map !== main,
        },
      });
      return state;
    };
    const clickImage = async (fraction = 0.65) => {
      const canvas = image.getByTestId("detector-canvas");
      const point = await canvas.evaluate((el, fraction) => {
        const d = el.dataset;
        return {
          x:
            +d.plotLeft +
            ((+d.fullWidth * fraction - +d.viewXMin) /
              (+d.viewXMax - +d.viewXMin)) *
              +d.plotWidth,
          y:
            +d.plotTop +
            ((+d.viewYMax - +d.fullHeight * 0.6) /
              (+d.viewYMax - +d.viewYMin)) *
              +d.plotHeight,
        };
      }, fraction);
      await canvas.click({ position: point });
    };
    const clickPattern = async (fraction) => {
      const canvas = main.getByTestId("pattern-canvas");
      const point = await canvas.evaluate(
        (el, f) => ({
          x: +el.dataset.plotLeft + +el.dataset.plotWidth * f,
          y: +el.dataset.plotTop + +el.dataset.plotHeight * 0.5,
        }),
        fraction,
      );
      await canvas.click({ position: point });
    };
    const clickBatch = async (frame, fraction) => {
      const canvas = batch.getByTestId("batch-heatmap");
      const point = await canvas.evaluate(
        (el, { frame, fraction }) => {
          const d = el.dataset;
          return {
            x: +d.plotLeft + +d.plotWidth * fraction,
            y:
              +d.plotTop +
              ((+d.viewYMax - frame - 0.5) / (+d.viewYMax - +d.viewYMin)) *
                +d.plotHeight,
          };
        },
        { frame, fraction },
      );
      await canvas.click({ position: point });
      batchFrame = frame;
      await batch.waitForFunction(
        (frame) =>
          document.querySelector(".batch-series-panel").dataset
            .selectedFrame === String(frame),
        frame,
      );
    };
    const clickMap = async (row, col) => {
      const canvas = map.getByTestId("scan-map").getByTestId("detector-canvas");
      const point = await canvas.evaluate(
        (el, { row, col }) => {
          const d = el.dataset,
            y = +d.fullHeight - row - 0.5;
          return {
            x:
              +d.plotLeft +
              ((col + 0.5 - +d.viewXMin) / (+d.viewXMax - +d.viewXMin)) *
                +d.plotWidth,
            y:
              +d.plotTop +
              ((+d.viewYMax - y) / (+d.viewYMax - +d.viewYMin)) * +d.plotHeight,
          };
        },
        { row, col },
      );
      await canvas.click({ position: point });
      mapFrame = row * 3 + col;
      await map.waitForFunction(
        (cell) =>
          document.querySelector('[data-testid="scan-map"]').dataset
            .selectedCell === cell,
        `${row},${col}`,
      );
    };
    await clickImage();
    await check("image click, all three detached");
    await clickPattern(0.42);
    const patternSelection = await check("pattern click, all three detached");
    await clickBatch(1, 0.46);
    const batchSelection = await check(
      "Batch frame/radial click, all three detached",
    );
    assert.ok(
      Math.abs(batchSelection.linked.radial - patternSelection.linked.radial) >
        1e-3,
    );
    await clickMap(2, 1);
    const mapSelection = await check("Map cell click retains radial position");
    close(
      mapSelection.linked.twoTheta,
      batchSelection.linked.twoTheta,
      "Map click changed radial bookmark",
    );
    await image.getByRole("button", { name: "Cake", exact: true }).click();
    imageKind = "cake";
    const cakeCanvas = image.getByTestId("cake-canvas");
    await cakeCanvas.waitFor();
    await ready();
    const clickCake = async (fraction) => {
      const canvas = image.getByTestId("cake-canvas");
      const point = await canvas.evaluate(
        (el, f) => ({
          x: +el.dataset.plotLeft + +el.dataset.plotWidth * f,
          y: +el.dataset.plotTop + +el.dataset.plotHeight * 0.4,
        }),
        fraction,
      );
      await canvas.click({ position: point });
    };
    await clickCake(0.37);
    await check("detached cake click with Batch and Map open");
    await clickPattern(0.48);
    await check("pattern updates detached cake, Batch and Map");
    await main
      .getByRole("button", { name: "Pattern unit Q", exact: true })
      .click();
    await ready();
    await clickPattern(0.41);
    await check("Q pattern click reaches all companions");
    await clickBatch(3, 0.55);
    const qBatch = await check("Q Batch click reaches pattern and companions");
    await clickMap(0, 2);
    const qMap = await check(
      "Map selection retains Q bookmark in all companions",
    );
    close(
      qMap.linked.twoTheta,
      qBatch.linked.twoTheta,
      "Q bookmark changed on Map selection",
    );
    await image.getByRole("button", { name: "Image", exact: true }).click();
    imageKind = "image";
    await image.getByTestId("detector-canvas").waitFor();
    await ready();
    await clickImage();
    await check("image click updates all companions in Q");
    // Recreate each companion twice. The others stay open to catch a reconnect
    // losing the shared bookmark or publishing stale state back to its owner.
    for (const [cycle, unit] of ["2θ", "Q"].entries()) {
      await main
        .getByRole("button", { name: `Pattern unit ${unit}`, exact: true })
        .click();
      await ready();
      if (cycle === 1) {
        await image.getByRole("button", { name: "Cake", exact: true }).click();
        imageKind = "cake";
        await image.getByTestId("cake-canvas").waitFor();
      }
      const prefix = `${unit} docking cycle`;
      let before = await check(`${prefix}: baseline`);
      const dock = async (page, button) => {
        const closed = page.waitForEvent("close");
        await page.getByRole("button", { name: button, exact: true }).click();
        await closed;
      };
      const detach = async (button, testId) => {
        const popup = main.waitForEvent("popup");
        await main.getByRole("button", { name: button, exact: true }).click();
        const page = await popup;
        page.setDefaultTimeout(20000);
        await page.getByTestId(testId).waitFor();
        return page;
      };
      await dock(image, "Dock detector image");
      image = main;
      before = await check(`${prefix}: detector docked`, {
        retainedFrom: before,
      });
      await clickPattern(0.36);
      before = await check(`${prefix}: pattern to docked detector`, {
        changedFrom: before,
      });
      if (imageKind === "cake") await clickCake(0.44);
      else await clickImage(0.58);
      before = await check(`${prefix}: docked detector to companions`, {
        changedFrom: before,
      });
      image = await detach(
        "Undock detector image",
        `${imageKind === "cake" ? "cake" : "detector"}-canvas`,
      );
      before = await check(`${prefix}: detector detached again`, {
        retainedFrom: before,
      });
      if (imageKind === "cake") await clickCake(0.39);
      else await clickImage(0.68);
      before = await check(`${prefix}: reopened detector click`, {
        changedFrom: before,
      });

      await dock(batch, "Dock batch below image");
      batch = main;
      before = await check(`${prefix}: Batch docked`, { retainedFrom: before });
      await clickPattern(0.34);
      before = await check(`${prefix}: pattern to docked Batch`, {
        changedFrom: before,
      });
      await clickBatch(4 + cycle, 0.47);
      before = await check(`${prefix}: docked Batch to companions`, {
        changedFrom: before,
      });
      batch = await detach("Detach batch", "batch-heatmap");
      before = await check(`${prefix}: Batch detached again`, {
        retainedFrom: before,
      });
      await clickBatch(6 + cycle, 0.52);
      before = await check(`${prefix}: reopened Batch click`, {
        changedFrom: before,
      });

      await dock(map, "Dock map");
      map = main;
      before = await check(`${prefix}: Map docked`, { retainedFrom: before });
      await clickPattern(0.38);
      before = await check(`${prefix}: pattern to docked Map`, {
        changedFrom: before,
      });
      await clickMap(1, cycle);
      before = await check(`${prefix}: docked Map retains bookmark`, {
        retainedFrom: before,
      });
      map = await detach("Detach map", "scan-map");
      before = await check(`${prefix}: Map detached again`, {
        retainedFrom: before,
      });
      await clickMap(2, cycle);
      await check(`${prefix}: reopened Map retains bookmark`, {
        retainedFrom: before,
      });
    }
    assert.equal(native.child.exitCode, null);
    assert.deepEqual(errors, []);
    assert.deepEqual(failures, []);
    for (const [label, page] of [
      ["main", main],
      ["detector", image],
      ["batch", batch],
      ["map", map],
    ])
      await page.screenshot({
        path: path.join(artifacts, `${name}-${label}.png`),
      });
    const receipt = {
      browser: name,
      runtime: "rust",
      processorPid: native.child.pid,
      simultaneousCompanions: 3,
      allClickReadoutsMatch: true,
      dockingCyclesPerCompanion: 2,
      steps,
      errors,
      failures,
      commands,
    };
    receipts.push(receipt);
    await writeFile(
      path.join(artifacts, `${name}.json`),
      JSON.stringify(receipt, null, 2) + "\n",
    );
    console.log(
      `${name}: all three Rust-backed companions share click state across ${steps.length} checks`,
    );
  } catch (error) {
    const snapshot = await native.invoke("state").catch(() => ({}));
    const diagnostics = {
      linked: snapshot.linked,
      unit: snapshot.state?.unit,
      patternUnit: snapshot.pattern?.unit,
      pages: await Promise.all(
        (browser?.contexts().flatMap((c) => c.pages()) ?? []).map(
          async (page) => ({
            url: page.url(),
            plots: await page
              .locator(
                '[data-testid="pattern-canvas"], [data-testid="detector-canvas"], [data-testid="cake-canvas"], [data-testid="batch-heatmap"]',
              )
              .evaluateAll((els) => els.map((el) => ({ ...el.dataset })))
              .catch(() => []),
          }),
        ),
      ),
    };
    await writeFile(
      path.join(artifacts, `${name}-failure.json`),
      JSON.stringify(
        {
          error: String(error),
          stack: error.stack,
          diagnostics,
          errors,
          failures,
          commands,
          steps,
        },
        null,
        2,
      ) + "\n",
    );
    for (const [index, page] of (
      browser?.contexts().flatMap((context) => context.pages()) ?? []
    ).entries())
      await page
        .screenshot({
          path: path.join(artifacts, `${name}-failure-${index}.png`),
        })
        .catch(() => {});
    throw error;
  } finally {
    await browser?.close();
    await native.close();
  }
}
await writeFile(
  path.join(artifacts, "results.json"),
  JSON.stringify(receipts, null, 2) + "\n",
);
