// Real Rust phase editing and Batch switching across compact/wide layouts.
import assert from "node:assert/strict";
import path from "node:path";
import os from "node:os";
import { mkdtemp, mkdir, writeFile, rm } from "node:fs/promises";
import { createServer } from "vite";
import { chromium, webkit } from "playwright";
import { nativeClient, root } from "./native_backend_client.mjs";
const temp = await mkdtemp(path.join(os.tmpdir(), "dioptas-responsive-"));
const artifacts = path.join(root, "desktop/artifacts/integration-responsive");
await mkdir(artifacts, { recursive: true });
const poni = path.join(temp, "geometry.poni");
await writeFile(
  poni,
  "PixelSize1: 0.0001\nPixelSize2: 0.0001\nDistance: 0.13\nPoni1: 0.0012\nPoni2: 0.0016\nRot1: 0.008\nRot2: -0.013\nRot3: 0.02\nWavelength: 5e-11\n",
);
const paths = [];
for (let row = 0; row < 6; row++) {
  let header = "{'descr': '<f8', 'fortran_order': False, 'shape': (24, 32), }";
  while ((10 + header.length + 1) % 64) header += " ";
  header += "\n";
  const bytes = Buffer.alloc(10 + header.length + 768 * 8);
  bytes.set([0x93, 0x4e, 0x55, 0x4d, 0x50, 0x59, 1, 0]);
  bytes.writeUInt16LE(header.length, 8);
  bytes.write(header, 10);
  for (let i = 0; i < 768; i++)
    bytes.writeDoubleLE(
      100 + row * 20 + (i % 32) * 2 + Math.floor(i / 32) * 3,
      10 + header.length + i * 8,
    );
  const file = path.join(temp, `scan_${row}.npy`);
  await writeFile(file, bytes);
  paths.push(file);
}
const server = await createServer({
  root: path.join(root, "desktop"),
  server: { host: "127.0.0.1", port: 0 },
});
await server.listen();
const reports = [];
try {
  for (const [name, engine] of [
    ["chromium", chromium],
    ["webkit", webkit],
  ]) {
    const native = nativeClient(),
      browser = await engine.launch({ headless: true }),
      errors = [],
      commands = [];
    const call = async (a, p = {}) => {
      const r = await native.invoke(a, p);
      assert.ok(r.ok, `${a}: ${r.error}`);
      commands.push({ a, p });
      return r;
    };
    try {
      await call("open_calibration", { path: poni });
      await call("integration_settings", { bins: 40, cake_bins: 24 });
      await call("open_image", { path: paths[0] });
      await call("batch_load", { paths });
      await call("open_image", { path: paths[0] });
      await call("integration_phase", {
        operation: "load",
        path: path.join(root, "desktop/tests/data/jcpds/mo.jcpds"),
      });
      await call("integration_phase", {
        operation: "load_database",
        material_id: "gold",
        reference: 4,
      });
      await call("integration_phase", {
        operation: "load_database",
        material_id: "platinum",
        reference: 0,
      });
      await call("integration_phase", {
        operation: "same_conditions",
        enabled: false,
      });
      const page = await browser.newPage({
        viewport: { width: 1440, height: 1000 },
      });
      page.on("pageerror", (e) => errors.push(e.message));
      await page.exposeFunction("__responsiveInvoke", async (a, p) =>
        native.browserResult(await call(a, p)),
      );
      await page.addInitScript(() => {
        window.pywebview = {
          api: { invoke: (a, p) => window.__responsiveInvoke(a, p) },
        };
        localStorage.setItem("dioptas-batch:docked", "true");
      });
      await page.goto(server.resolvedUrls.local[0]);
      const button = (n) => page.getByRole("button", { name: n, exact: true }),
        tab = (n) => page.getByRole("tab", { name: n, exact: true });
      const settle = () =>
        page.evaluate(
          () =>
            new Promise((r) =>
              requestAnimationFrame(() => requestAnimationFrame(r)),
            ),
        );
      const state = async () => (await call("state")).state;
      const waitFor = async (check) => {
        for (let i = 0; i < 100; i++) {
          if (check(await state())) {
            await page.waitForFunction(() => !document.querySelector(".spin"));
            await settle();
            return;
          }
          await page.waitForTimeout(30);
        }
        assert.fail("Native state did not reach expected value");
      };
      await button("Integration").click();
      await tab("Phase").click();
      assert.deepEqual(
        (await state()).integration.phases.map((p) => p.color),
        ["#cc8028", "#5dcc28", "#28ccae"],
        "New phase colors match Qt's first orange, green and teal",
      );
      const pressure = page.getByRole("spinbutton", {
        name: "Phase 2 pressure (GPa)",
        exact: true,
      });
      assert.equal(
        await page
          .getByRole("spinbutton", {
            name: "Phase 1 temperature (K)",
            exact: true,
          })
          .isDisabled(),
        true,
      );
      const enter = async (field, value) => {
        await field.fill(String(value));
        await field.press("Enter");
      };
      await enter(pressure, 12.345);
      await waitFor((s) => s.integration.phases[1].pressure === 12.345);
      const temperature = page.getByRole("spinbutton", {
        name: "Phase 2 temperature (K)",
        exact: true,
      });
      await enter(temperature, 1200);
      await waitFor((s) => s.integration.phases[1].temperature === 1200);

      await page.screenshot({
        path: path.join(artifacts, `${name}-steps.png`),
      });
      await enter(
        page.getByRole("spinbutton", { name: "P step", exact: true }),
        0.5,
      );
      await enter(
        page.getByRole("spinbutton", { name: "T Step", exact: true }),
        50,
      );

      await pressure.press("ArrowUp");
      await waitFor((s) => s.integration.phases[1].pressure === 12.845);
      await temperature.press("ArrowUp");
      await waitFor((s) => s.integration.phases[1].temperature === 1250);
      assert.equal(
        await page.evaluate(() =>
          sessionStorage.getItem("dioptas-phase-pressure-step"),
        ),
        "0.5",
      );
      await page
        .getByRole("checkbox", {
          name: "Apply conditions to all phases",
          exact: true,
        })
        .click();
      await waitFor((s) => s.integration.sameConditions === true);
      await enter(pressure, 20);
      await waitFor((s) =>
        s.integration.phases.every((p) => p.pressure === 20),
      );
      await page
        .getByRole("checkbox", {
          name: "Apply conditions to all phases",
          exact: true,
        })
        .click();
      await waitFor((s) => s.integration.sameConditions === false);

      const phaseOrder = (s) => s.integration.phases.map((p) => p.uid);
      const originalOrder = phaseOrder(await state());
      await page.locator(".phase-name").nth(1).click();
      await button("Move phase up").click();
      const movedOrder = [originalOrder[1], originalOrder[0], originalOrder[2]];
      await waitFor(
        (s) => JSON.stringify(phaseOrder(s)) === JSON.stringify(movedOrder),
      );
      assert.ok(await button("Move phase up").isDisabled());
      assert.match(
        await page.locator('.phase-table tr[aria-selected="true"]').innerText(),
        /Gold/,
      );
      await button("Undo").click();
      await waitFor(
        (s) => JSON.stringify(phaseOrder(s)) === JSON.stringify(originalOrder),
      );
      assert.match(
        await page.locator('.phase-table tr[aria-selected="true"]').innerText(),
        /Gold/,
      );
      await button("Redo").click();
      await waitFor(
        (s) => JSON.stringify(phaseOrder(s)) === JSON.stringify(movedOrder),
      );
      await button("Move phase down").click();
      await waitFor(
        (s) => JSON.stringify(phaseOrder(s)) === JSON.stringify(originalOrder),
      );

      const clearDialog = page.getByRole("dialog", {
        name: "Clear all phases?",
        exact: true,
      });
      const clearPhases = button("Removes all phases");
      const clearCommands = () =>
        commands.filter(
          ({ a, p }) => a === "integration_phase" && p.operation === "clear",
        ).length;
      const beforeClear = clearCommands();
      await clearPhases.click();
      await clearDialog.waitFor();
      assert.equal(
        await clearDialog
          .getByRole("button", { name: "Cancel", exact: true })
          .evaluate((el) => el === document.activeElement),
        true,
      );
      assert.equal((await state()).integration.phases.length, 3);
      await page.screenshot({
        path: path.join(artifacts, `${name}-clear-phases-confirmation.png`),
      });
      await clearDialog
        .getByRole("button", { name: "Cancel", exact: true })
        .click();
      assert.ok(
        await clearPhases.evaluate((el) => el === document.activeElement),
      );
      await clearPhases.click();
      await clearDialog.press("Escape");
      await clearDialog.waitFor({ state: "hidden" });
      assert.equal(
        clearCommands(),
        beforeClear,
        "Cancel and Escape never dispatch a clear operation",
      );
      assert.equal((await state()).integration.phases.length, 3);

      await button("As Overlay").click();
      await waitFor((s) => s.integration.overlays.length === 1);
      await tab("Overlay").click();
      await enter(
        page.getByRole("spinbutton", { name: "Scale Step", exact: true }),
        0.05,
      );
      await enter(
        page.getByRole("spinbutton", { name: "Offset Step", exact: true }),
        5,
      );
      await page
        .getByRole("spinbutton", { name: "Overlay 1 scale", exact: true })
        .press("ArrowUp");
      await waitFor(
        (s) => Math.abs(s.integration.overlays[0].scale - 1.05) < 1e-10,
      );
      await page
        .getByRole("spinbutton", { name: "Overlay 1 offset", exact: true })
        .dispatchEvent("wheel", {
          deltaY: -100,
          bubbles: true,
          cancelable: true,
        });
      await waitFor((s) => s.integration.overlays[0].offset === 5);
      await enter(
        page.getByRole("spinbutton", { name: "Overlay 1 scale", exact: true }),
        1,
      );
      await waitFor((s) => s.integration.overlays[0].scale === 1);
      await enter(
        page.getByRole("spinbutton", { name: "Overlay 1 offset", exact: true }),
        0,
      );
      await waitFor((s) => s.integration.overlays[0].offset === 0);
      const verifyOverlayLayout = async (label) => {
        await settle();
        const geometry = await page
          .locator(".qt-overlay-controls")
          .evaluate((el) => {
            const parameters = el.querySelector(".qt-overlay-parameters"),
              scroll = el.querySelector(".qt-overlay-parameter-scroll"),
              clipper =
                getComputedStyle(scroll).display === "contents"
                  ? parameters
                  : scroll,
              bounds = clipper.getBoundingClientRect(),
              table = el
                .querySelector(".qt-overlay-table-region")
                .getBoundingClientRect(),
              paramBounds = parameters.getBoundingClientRect();
            const fields = [
              ...el.querySelectorAll(".qt-overlay-parameter-scroll input"),
            ]
              .filter((input) => input.getClientRects().length)
              .map((input) => input.getBoundingClientRect());
            return {
              width: el.clientWidth,
              toolbarLayout: el.dataset.toolbarLayout,
              fields: fields.map((box) => ({
                width: box.width,
                height: box.height,
                left: box.left - bounds.left,
                right: bounds.right - box.right,
              })),
              rowHeight: el
                .querySelector('.qt-overlay-table-scroll input[type="number"]')
                .getBoundingClientRect().height,
              overflowing: [
                el,
                parameters,
                scroll,
                el.querySelector(".qt-overlay-table-scroll"),
              ]
                .filter(
                  (node) =>
                    node.clientWidth > 0 &&
                    node.scrollWidth > node.clientWidth + 1,
                )
                .map((node) => node.className),
              above: paramBounds.bottom <= table.top,
              right: paramBounds.left >= table.right,
              spacing:
                el
                  .querySelector('[aria-label="Waterfall separation"]')
                  .getClientRects().length > 0,
              spacingCaption:
                el
                  .querySelector(".qt-overlay-spacing-field > span")
                  .getClientRects().length > 0,
              labels: [
                ...el.querySelectorAll(
                  ".qt-overlay-step-controls > label > span",
                ),
              ].map((span) => span.innerText),
              waterfallIcon:
                getComputedStyle(el.querySelector(".qt-overlay-waterfall-icon"))
                  .display !== "none",
              beforeWaterfallSeparator:
                el.clientWidth <= 600
                  ? parseFloat(
                      getComputedStyle(
                        el.querySelector(".qt-overlay-waterfall-actions"),
                      ).borderLeftWidth,
                    ) > 0
                  : el
                      .querySelector(".qt-overlay-parameter-scroll > hr")
                      .getBoundingClientRect().height > 0,
              backgroundSeparator:
                el.clientWidth <= 600
                  ? getComputedStyle(
                      el.querySelector(".qt-overlay-background-action"),
                    ).borderLeftWidth
                  : getComputedStyle(
                      el.querySelector(".qt-overlay-background-action"),
                    ).borderTopWidth,
              backgroundGlyph: el.querySelector(
                ".qt-overlay-background-action svg",
              ).innerHTML,
            };
          });
        assert.deepEqual(
          geometry.overflowing,
          [],
          `Overlay containers fit without horizontal scrollbars: ${JSON.stringify(geometry)}`,
        );
        assert.ok(
          geometry.fields.every(
            (f) => f.width === 64 && f.height === geometry.rowHeight,
          ),
          "Overlay steps and spacing use compact, table-height fields",
        );
        assert.ok(
          geometry.fields.every((f) => f.left >= 6 && f.right >= 6),
          "Overlay field borders and focus outlines have padding inside their clipping pane",
        );
        assert.ok(
          geometry.width <= 600 ? geometry.above : geometry.right,
          "Overlay parameters follow the available panel width",
        );
        assert.deepEqual(geometry.labels, ["Scale", "Offset"]);
        assert.equal(
          geometry.spacing,
          !geometry.toolbarLayout.endsWith("reduced"),
          "Spacing hides before wrapping and returns when the second row has room",
        );
        assert.equal(
          geometry.spacingCaption,
          geometry.width > 600,
          "Compact spacing field has no text label",
        );
        assert.equal(
          geometry.waterfallIcon,
          geometry.width <= 600,
          "Compact Waterfall uses stacked traces",
        );
        assert.ok(
          geometry.beforeWaterfallSeparator &&
            parseFloat(geometry.backgroundSeparator) > 0,
          "Separators divide steps, waterfall and background actions",
        );
        const patternBackground = await page
          .locator(".integration-pattern-actions")
          .getByRole("button", { name: "As Bkg", exact: true })
          .locator("svg")
          .evaluate((svg) => svg.innerHTML);
        assert.equal(
          geometry.backgroundGlyph,
          patternBackground,
          "Overlay and pattern use the same background glyph",
        );
        assert.ok(
          geometry.backgroundGlyph.includes("#e77777"),
          "The background glyph has a red baseline",
        );
        await page.screenshot({
          path: path.join(artifacts, `${name}-${label}-overlay.png`),
        });
      };

      // Qt splits the task controls themselves, independently of the plot layout.
      const controls = page.locator(".integration-controls");
      const panel = (name) =>
        page.getByRole("tabpanel", { name: `${name} controls`, exact: true });
      const filename = page.getByRole("textbox", {
        name: "Image filename",
        exact: true,
      });
      const expectColumns = async (count) => {
        await page.waitForFunction(
          (count) =>
            document.querySelector(".integration-controls")?.dataset
              .controlColumns === String(count),
          count,
        );
        await settle();
      };
      for (const large of [false, true]) {
        await button("Settings").click();
        await button(large ? "Larger" : "Standard").click();
        await button("Close settings").click();
        for (const [width, columns] of [
          [2400, 2],
          [3600, 3],
        ]) {
          await page.setViewportSize({ width, height: 1000 });
          await expectColumns(columns);
          await tab("Image").click();
          await tab("Phase").click();
          assert.ok(await panel("Image").isVisible());
          assert.ok(await panel("Phase").isVisible());
          const imageBox = await panel("Image").boundingBox(),
            phaseBox = await panel("Phase").boundingBox();
          assert.ok(
            phaseBox.x >= imageBox.x + imageBox.width - 1,
            "Phase stays to the right of file controls",
          );
          assert.ok(Math.abs(imageBox.y - phaseBox.y) < 1);
          // Edits and image browsing remain available together through the real worker.
          const oldPressure = (await state()).integration.phases[1].pressure;
          await enter(pressure, oldPressure + 1);
          await waitFor(
            (s) => s.integration.phases[1].pressure === oldPressure + 1,
          );
          await button("Integration next image").click();
          await waitFor((s) => s.imagePath?.endsWith("/scan_1.npy"));
          await button("Integration previous image").click();
          await waitFor((s) => s.imagePath?.endsWith("/scan_0.npy"));
          assert.ok(await pressure.isVisible());
          for (const name of [
            "Pattern",
            "Background",
            "Corrections",
            "Image",
          ]) {
            await tab(name).click();
            assert.ok(await panel(name).isVisible());
            assert.ok(await panel("Phase").isVisible());
          }
          await tab("Overlay").click();
          assert.ok(await panel("Image").isVisible());
          assert.ok(await panel("Overlay").isVisible());
          await verifyOverlayLayout(
            `${columns}-columns-${large ? "large" : "standard"}`,
          );
          assert.equal(await panel("Phase").isVisible(), columns === 3);
          await tab("Phase").click();
          const actualFilename = await filename.inputValue();
          await filename.fill("pending-resize.npy");
          await filename.evaluate((el) => (window.__splitFilename = el));
          await page
            .getByTestId("phase-controls")
            .evaluate((el) => (window.__splitPhase = el));
          await page.screenshot({
            path: path.join(
              artifacts,
              `${name}-${columns}-columns-${large ? "large" : "standard"}.png`,
            ),
          });
          await page.setViewportSize({ width: 1440, height: 1000 });
          await expectColumns(1);
          await page.setViewportSize({ width, height: 1000 });
          await expectColumns(columns);
          assert.equal(await filename.inputValue(), "pending-resize.npy");
          assert.ok(
            await filename.evaluate((el) => el === window.__splitFilename),
          );
          assert.ok(
            await page
              .getByTestId("phase-controls")
              .evaluate((el) => el === window.__splitPhase),
          );
          await filename.fill(actualFilename);
          await button("Collapse Integration controls").click();
          assert.equal(await panel("Phase").isVisible(), false);
          await tab("Image").click();
          assert.ok(await panel("Phase").isVisible());
          const overflowing = await controls
            .locator(".integration-tabs, .integration-fieldset:not([hidden])")
            .evaluateAll((elements) =>
              elements
                .filter((el) => el.scrollWidth > el.clientWidth + 1)
                .map((el) => el.className),
            );
          assert.deepEqual(
            overflowing,
            [],
            "Visible split controls have no horizontal overflow",
          );
        }
      }
      // Text-size changes alone must update the breakpoint, without a resize.
      await page.setViewportSize({ width: 2100, height: 1000 });
      await expectColumns(1); // Larger text needs more room.
      await button("Settings").click();
      await button("Standard").click();
      await button("Close settings").click();
      await expectColumns(2);
      await page.setViewportSize({ width: 1440, height: 1000 });
      await expectColumns(1);
      await tab("Phase").click();

      assert.equal(await button("Save List").isDisabled(), true);

      // Resize without replacing scientific canvases or discarding plot zoom.
      const detector = page.getByTestId("detector-canvas"),
        pattern = page.getByTestId("pattern-canvas");
      await detector.evaluate((el) => (window.__responsiveDetector = el));
      await pattern.evaluate((el) => (window.__responsivePattern = el));
      await detector.press("+");
      await settle();
      const detectorZoom = await detector.evaluate((el) => [
        el.dataset.viewXMin,
        el.dataset.viewXMax,
        el.dataset.viewYMin,
        el.dataset.viewYMax,
      ]);
      await pattern.press("+");
      await settle();
      const zoom = await pattern.evaluate((el) => [
        el.dataset.viewXMin,
        el.dataset.viewXMax,
      ]);
      for (const large of [false, true]) {
        await button("Settings").click();
        await button(large ? "Larger" : "Standard").click();
        await button("Close settings").click();
        for (const width of [1440, 1000, 800]) {
          await page.setViewportSize({
            width,
            height: width === 1440 ? 1000 : 760,
          });
          await settle();
          const layout = await page
            .locator(".integration-layout")
            .getAttribute("data-integration-layout");
          assert.equal(layout, width === 1440 ? "right" : "top");
          const controlBox = await page
              .locator(".integration-layout > .sidebar")
              .boundingBox(),
            imageBox = await page
              .locator(".integration-left-pane")
              .boundingBox(),
            patternBox = await page.locator(".pattern-panel").boundingBox();
          if (width < 1440) {
            assert.ok(controlBox.x <= imageBox.x + 1);
            assert.ok(
              controlBox.x + controlBox.width >=
                patternBox.x + patternBox.width - 1,
            );
            assert.ok(controlBox.y + controlBox.height <= imageBox.y);
          } else {
            assert.ok(controlBox.x >= imageBox.x + imageBox.width);
          }
          const geometry = await page
            .getByTestId("phase-controls")
            .evaluate((el) => ({
              overflow: el.scrollWidth > el.clientWidth + 1,
              names: [...el.querySelectorAll(".phase-name")].map((n) => ({
                whiteSpace: getComputedStyle(n).whiteSpace,
                ellipsis: getComputedStyle(n).textOverflow,
                text: n.textContent,
              })),
              tableOverflow:
                el.querySelector(".phase-table-scroll").scrollWidth >
                el.querySelector(".phase-table-scroll").clientWidth + 1,
              fields: [
                ...el.querySelectorAll(".phase-condition-value input"),
              ].map((n) => n.getBoundingClientRect().width),
            }));
          const arrangement = await page
            .getByTestId("phase-controls")
            .evaluate((el) => {
              const box = (s) => el.querySelector(s).getBoundingClientRect();
              const table = box(".phase-table-scroll"),
                actions = box(".phase-toolbar"),
                parameters = box(".phase-parameters");
              return {
                table: { x: table.x, y: table.y, right: table.right },
                actions: {
                  x: actions.x,
                  y: actions.y,
                  right: actions.right,
                  bottom: actions.bottom,
                },
                width: el.clientWidth,
                parameters: {
                  x: parameters.x,
                  y: parameters.y,
                  bottom: parameters.bottom,
                },
                centering: [...el.querySelectorAll('input[type="color"]')].map(
                  (input) => {
                    const swatch = input.getBoundingClientRect(),
                      cell = input.closest("td").getBoundingClientRect();
                    return Math.abs(
                      swatch.y + swatch.height / 2 - cell.y - cell.height / 2,
                    );
                  },
                ),
              };
            });
          assert.ok(
            arrangement.actions.right <= arrangement.table.x,
            "Phase actions remain in the left rail at every width",
          );
          if (arrangement.width <= 600) {
            assert.ok(
              arrangement.parameters.bottom <= arrangement.table.y,
              "Narrow phase columns keep compact step controls above the table",
            );
          } else {
            assert.ok(
              arrangement.parameters.x >= arrangement.table.right,
              "Wide phase columns retain step controls on the right",
            );
          }
          assert.ok(
            arrangement.centering.every((d) => d < 1),
            "Color swatches are centered with the row text",
          );
          assert.equal(
            await page
              .getByRole("spinbutton", { name: "P step", exact: true })
              .isVisible(),
            true,
          );
          assert.equal(
            await page
              .getByRole("spinbutton", { name: "T Step", exact: true })
              .isVisible(),
            true,
          );
          assert.equal(geometry.overflow, false);
          assert.equal(geometry.tableOverflow, false);
          assert.ok(
            geometry.names.every(
              (n) => n.whiteSpace === "normal" && n.ellipsis !== "ellipsis",
            ),
          );
          assert.ok(geometry.fields.every((w) => w >= 90));
          const compactFields = await page
            .getByTestId("phase-controls")
            .evaluate((el) => {
              const fields = [
                ...el.querySelectorAll(".phase-condition-step input"),
              ].map((n) => n.getBoundingClientRect().toJSON());
              const value = el
                .querySelector(".phase-condition-value input")
                .getBoundingClientRect();
              const reference = el.querySelector(
                ".phase-selected-reference select",
              );
              const shownReference =
                reference && reference.getClientRects().length
                  ? reference.getBoundingClientRect().height
                  : null;
              const parameters = el.querySelector(".phase-parameters");
              const bounds = parameters.getBoundingClientRect();
              const inputs = [...parameters.querySelectorAll("input")].map(
                (input) => input.getBoundingClientRect(),
              );
              const parameterGeometry = {
                horizontalOverflow:
                  parameters.scrollWidth > parameters.clientWidth,
                leftPadding: Math.min(
                  ...inputs.map((box) => box.left - bounds.left),
                ),
                rightPadding: Math.min(
                  ...inputs.map((box) => bounds.right - box.right),
                ),
                applyLabel: el
                  .querySelector(".phase-apply-all")
                  .innerText.trim(),
              };
              const toolbar = el.querySelector(".phase-toolbar");
              const clear = toolbar
                .querySelector('[aria-label="Removes all phases"]')
                .getBoundingClientRect();
              const remove = toolbar
                .querySelector(
                  '[aria-label="Removes currently selected phase"]',
                )
                .getBoundingClientRect();
              return {
                fields,
                parameterGeometry,
                valueHeight: value.height,
                shownReference,
                clearance: clear.top - remove.bottom,
                listButtons: ["Save List", "Load List"].every((name) =>
                  el.querySelector(`.phase-parameters [aria-label="${name}"]`),
                ),
                separators: toolbar.querySelectorAll(".phase-clear-group hr")
                  .length,
                order: [...toolbar.querySelectorAll("button")].map((b) =>
                  b.getAttribute("aria-label"),
                ),
                railOverflow: toolbar.scrollHeight > toolbar.clientHeight + 1,
              };
            });
          assert.ok(
            compactFields.fields.every(
              (f) => f.width <= 72 && f.height === compactFields.valueHeight,
            ),
            "Step fields have compact widths and the same height as phase values",
          );
          if (compactFields.shownReference !== null)
            assert.equal(
              compactFields.shownReference,
              compactFields.valueHeight,
              "Selected reference uses the compact table control height",
            );
          assert.ok(
            compactFields.listButtons &&
              compactFields.clearance >= 8 &&
              compactFields.separators === 2,
            "Compact list actions sit with the steps; separators surround Clear All",
          );
          assert.equal(
            compactFields.parameterGeometry.horizontalOverflow,
            false,
            "The phase parameters fit without a horizontal scrollbar",
          );
          assert.ok(
            compactFields.parameterGeometry.leftPadding >= 6 &&
              compactFields.parameterGeometry.rightPadding >= 6,
            "Step and checkbox borders have padding inside the parameter pane",
          );
          assert.equal(
            compactFields.parameterGeometry.applyLabel,
            arrangement.width <= 600 ? "All" : "Apply to all",
          );
          assert.deepEqual(compactFields.order, [
            "Add phase…",
            "Browse EoS Material Database",
            "Edit selected Phase",
            "Removes currently selected phase",
            "Removes all phases",
            "Move phase up",
            "Move phase down",
          ]);
          assert.equal(
            compactFields.railOverflow,
            false,
            `The full action rail fits at ${width} (${large ? "large" : "standard"}): ${JSON.stringify(compactFields)}`,
          );

          assert.equal(
            await detector.evaluate((el) => el === window.__responsiveDetector),
            true,
          );
          assert.equal(
            await pattern.evaluate((el) => el === window.__responsivePattern),
            true,
          );
          const currentDetector = await detector.evaluate((el) =>
            [
              el.dataset.viewXMin,
              el.dataset.viewXMax,
              el.dataset.viewYMin,
              el.dataset.viewYMax,
            ].map(Number),
          );
          assert.deepEqual(
            currentDetector.slice(0, 2),
            detectorZoom.slice(0, 2).map(Number),
          );
          assert.ok(
            Math.abs(
              currentDetector[2] +
                currentDetector[3] -
                Number(detectorZoom[2]) -
                Number(detectorZoom[3]),
            ) < 1e-8,
            "Detector keeps its zoom center while adjusting height for square pixels",
          );
          assert.deepEqual(
            await pattern.evaluate((el) => [
              el.dataset.viewXMin,
              el.dataset.viewXMax,
            ]),
            zoom,
          );
          await page.screenshot({
            path: path.join(
              artifacts,
              `${name}-${width}-${large ? "large" : "standard"}-phase.png`,
            ),
          });
          await tab("Overlay").click();
          await verifyOverlayLayout(`${width}-${large ? "large" : "standard"}`);
          await tab("Phase").click();
        }
      }
      // Narrow task panels keep their action rail and move only steps above the table.
      await page.setViewportSize({ width: 1440, height: 1000 });
      const imageDivider = page.getByRole("separator", {
        name: "Image and analysis divider",
        exact: true,
      });
      await imageDivider.press("End");
      await settle();
      const compact = await page
        .getByTestId("phase-controls")
        .evaluate((el) => {
          const box = (s) => el.querySelector(s).getBoundingClientRect();
          const table = box(".phase-table-scroll"),
            rail = box(".phase-toolbar"),
            parameters = box(".phase-parameters");
          return {
            width: el.clientWidth,
            above: rail.right <= table.left && parameters.bottom <= table.top,
            overflow: el.scrollWidth > el.clientWidth + 1,
          };
        });
      assert.ok(
        compact.width < 600 && compact.above && !compact.overflow,
        "The constrained phase panel keeps left actions and compact step fields above the table",
      );
      await tab("Overlay").click();
      await verifyOverlayLayout("compact-large");
      await enter(
        page.getByRole("spinbutton", {
          name: "Waterfall separation",
          exact: true,
        }),
        7.5,
      );
      await waitFor((s) => s.integration.waterfallSeparation === 7.5);
      await page
        .locator(".qt-overlay-parameters")
        .getByRole("button", { name: "Waterfall", exact: true })
        .click();
      await waitFor((s) => s.integration.overlays[0].offset === -7.5);
      await page
        .locator(".qt-overlay-parameters")
        .getByRole("button", { name: "Reset", exact: true })
        .click();
      await waitFor((s) => s.integration.overlays[0].offset === 0);
      await page
        .getByRole("button", { name: "Auto waterfall spacing", exact: true })
        .click();
      await waitFor(
        (s) =>
          s.integration.waterfallSeparation > 0 &&
          s.integration.overlays[0].offset ===
            -s.integration.waterfallSeparation,
      );
      await page
        .locator(".qt-overlay-parameters")
        .getByRole("button", { name: "Reset", exact: true })
        .click();
      await waitFor((s) => s.integration.overlays[0].offset === 0);

      await tab("Phase").click();
      const pStep = page.getByRole("spinbutton", {
        name: "P step",
        exact: true,
      });
      await enter(pStep, 2);
      const beforeStep = (await state()).integration.phases[1].pressure;
      await pressure.press("ArrowUp");
      await waitFor((s) => s.integration.phases[1].pressure === beforeStep + 2);
      await page.screenshot({
        path: path.join(artifacts, `${name}-compact-phase.png`),
      });
      await imageDivider.press("Home");
      await settle();
      await page.setViewportSize({ width: 1000, height: 760 });
      await settle();
      // A wide phase panel keeps references in each row; a narrow right panel
      // offers the same records for the selected phase below the table.
      await page.locator(".phase-name").nth(1).click();
      await page
        .getByRole("combobox", { name: "Phase 2 reference", exact: true })
        .selectOption("3");
      await waitFor((s) => s.integration.phases[1].reference === 3);
      await page.setViewportSize({ width: 1440, height: 1000 });
      await settle();
      const selectedReference = page.getByRole("combobox", {
        name: "Selected phase reference",
        exact: true,
      });
      await selectedReference.selectOption("4");
      await waitFor((s) => s.integration.phases[1].reference === 4);
      await page.setViewportSize({ width: 1000, height: 760 });
      await settle();
      await tab("Image").click();
      await button("Batch view…").click();
      await tab("Phase").click();
      const left = page.getByRole("tablist", {
        name: "Integration left view",
        exact: true,
      });
      await left.waitFor();
      assert.equal(
        await left
          .getByRole("tab", { name: "Batch", exact: true })
          .getAttribute("aria-selected"),
        "true",
      );
      assert.equal(
        await page.locator(".integration-image-pane").getAttribute("inert"),
        "",
      );
      assert.equal(
        await page
          .getByRole("separator", {
            name: "Image and batch divider",
            exact: true,
          })
          .count(),
        0,
      );
      await page.getByTestId("batch-heatmap").waitFor();
      await page
        .getByTestId("batch-heatmap")
        .evaluate((el) => (window.__responsiveBatch = el));
      await left.getByRole("tab", { name: "Image", exact: true }).click();
      assert.equal(
        await page.locator(".integration-batch-pane").getAttribute("inert"),
        "",
      );
      assert.equal(
        await detector.evaluate((el) => el === window.__responsiveDetector),
        true,
      );
      await left
        .getByRole("tab", { name: "Image", exact: true })
        .press("ArrowRight");
      await page
        .getByRole("tablist", { name: "Batch view", exact: true })
        .getByRole("tab", { name: "Files", exact: true })
        .click();
      await button("Select batch file 3").click();
      await waitFor((s) => s.imagePath?.endsWith("/scan_2.npy"));
      await page
        .getByRole("tablist", { name: "Batch view", exact: true })
        .getByRole("tab", { name: "2D", exact: true })
        .click();
      for (const width of [1440, 1000]) {
        await page.setViewportSize({
          width,
          height: width === 1440 ? 1000 : 760,
        });
        await settle();
        assert.equal(await left.count(), width === 1440 ? 0 : 1);
        assert.equal(
          await page
            .getByRole("separator", {
              name: "Image and batch divider",
              exact: true,
            })
            .count(),
          width === 1440 ? 1 : 0,
        );
        assert.equal(
          await detector.evaluate((el) => el === window.__responsiveDetector),
          true,
        );
        await page.screenshot({
          path: path.join(artifacts, `${name}-${width}-batch.png`),
        });
      }
      // Batch layout resizing itself must retain the current heatmap instance.
      await page
        .getByTestId("batch-heatmap")
        .evaluate((el) => (window.__responsiveBatch = el));
      await left.getByRole("tab", { name: "Image", exact: true }).click();
      await left.getByRole("tab", { name: "Batch", exact: true }).click();
      await page.setViewportSize({ width: 1440, height: 1000 });
      await settle();
      assert.equal(
        await page
          .getByTestId("batch-heatmap")
          .evaluate((el) => el === window.__responsiveBatch),
        true,
      );
      await page.setViewportSize({ width: 1000, height: 760 });
      await settle();
      // Detaching the image keeps the existing Batch dock in the main workspace.
      await left.getByRole("tab", { name: "Image", exact: true }).click();
      const imagePopup = page.waitForEvent("popup");
      await button("Undock detector image").click();
      const imageChild = await imagePopup;
      imageChild.on("pageerror", (e) => errors.push(e.message));
      await imageChild.getByTestId("detector-canvas").waitFor();
      assert.equal(await left.count(), 0);
      assert.equal(
        await page.locator(".integration-batch-pane").getAttribute("inert"),
        null,
      );
      assert.ok(await page.getByTestId("batch-heatmap").isVisible());
      assert.equal(
        await page
          .getByTestId("batch-heatmap")
          .evaluate((el) => el === window.__responsiveBatch),
        true,
      );
      for (const width of [1440, 1000]) {
        await page.setViewportSize({
          width,
          height: width === 1440 ? 1000 : 760,
        });
        await page.waitForTimeout(150);
        const bounds = await page
          .locator(".integration-left-pane")
          .evaluate((pane) => {
            const p = pane.getBoundingClientRect(),
              dock = pane.querySelector(".batch-dock").getBoundingClientRect(),
              plot = pane
                .querySelector('[data-testid="batch-heatmap"]')
                .getBoundingClientRect();
            return {
              pane: p.toJSON(),
              dock: dock.toJSON(),
              plot: plot.toJSON(),
            };
          });
        await page.screenshot({
          path: path.join(
            artifacts,
            `${name}-${width}-image-detached-batch.png`,
          ),
        });
        assert.ok(
          Math.abs(bounds.dock.width - bounds.pane.width) < 2 &&
            Math.abs(bounds.dock.height - bounds.pane.height) < 2,
          `Batch does not fill the freed image pane: ${JSON.stringify(bounds)}`,
        );
        assert.ok(
          bounds.plot.width > bounds.pane.width * 0.7 &&
            bounds.plot.height > bounds.pane.height * 0.7,
        );
      }
      // Floating both views leaves only full-width task controls and pattern.
      const patternWithBatch = await page
        .locator(".pattern-panel")
        .boundingBox();
      const floatingBatch = page.waitForEvent("popup");
      await button("Detach batch").click();
      const batchChild = await floatingBatch;
      batchChild.on("pageerror", (e) => errors.push(e.message));
      await batchChild.getByTestId("batch-heatmap").waitFor();
      await page.waitForTimeout(150);
      assert.equal(
        await page.locator(".integration-left-pane").isVisible(),
        false,
      );
      assert.equal(
        await page
          .getByRole("separator", {
            name: "Image and analysis divider",
            exact: true,
          })
          .isVisible(),
        false,
      );
      const patternAlone = await page.locator(".pattern-panel").boundingBox(),
        controlsAlone = await page
          .locator(".workspace-content > .sidebar")
          .boundingBox();
      assert.ok(patternAlone.width > patternWithBatch.width * 1.5);
      assert.ok(
        Math.abs(controlsAlone.width - patternAlone.width) < 2 &&
          Math.abs(controlsAlone.x - patternAlone.x) < 2,
      );
      assert.equal(await page.getByTestId("detector-canvas").count(), 0);
      assert.equal(await page.getByTestId("batch-heatmap").count(), 0);
      await page.screenshot({
        path: path.join(artifacts, `${name}-both-views-detached.png`),
      });
      await batchChild
        .getByRole("button", { name: "Dock batch below image", exact: true })
        .click();
      await page.getByTestId("batch-heatmap").waitFor();
      await page.waitForTimeout(150);
      const refilledDock = await page.locator(".batch-dock").boundingBox(),
        refilledPane = await page
          .locator(".integration-left-pane")
          .boundingBox();
      assert.ok(Math.abs(refilledDock.height - refilledPane.height) < 2);
      await imageChild
        .getByRole("button", { name: "Dock detector image", exact: true })
        .click();
      await left.waitFor();
      await left.getByRole("tab", { name: "Batch", exact: true }).click();
      // Full-height mode temporarily overrides, rather than saves over, the
      // user's normal resized/collapsed dock preferences.
      await page.setViewportSize({ width: 1440, height: 1000 });
      await page.waitForTimeout(150);
      const batchDivider = page.getByRole("separator", {
        name: "Image and batch divider",
        exact: true,
      });
      await batchDivider.press("ArrowUp");
      const savedHeight = await page
        .locator(".batch-dock")
        .evaluate((el) => el.style.height);
      await button("Collapse batch overview").click();
      const collapsedPopup = page.waitForEvent("popup");
      await button("Undock detector image").click();
      const collapsedImage = await collapsedPopup;
      collapsedImage.on("pageerror", (e) => errors.push(e.message));
      await collapsedImage.getByTestId("detector-canvas").waitFor();
      await page.getByTestId("batch-heatmap").waitFor();
      const expandedDock = await page.locator(".batch-dock").boundingBox(),
        expandedPane = await page
          .locator(".integration-left-pane")
          .boundingBox();
      assert.ok(Math.abs(expandedDock.height - expandedPane.height) < 2);
      assert.equal(await batchDivider.count(), 0);
      assert.equal(await button("Collapse batch overview").count(), 0);
      await collapsedImage
        .getByRole("button", { name: "Dock detector image", exact: true })
        .click();
      await button("Expand batch overview").waitFor();
      await button("Expand batch overview").click();
      assert.equal(
        await page.locator(".batch-dock").evaluate((el) => el.style.height),
        savedHeight,
      );
      await page.setViewportSize({ width: 1000, height: 760 });
      await left.waitFor();
      await left.getByRole("tab", { name: "Batch", exact: true }).click();
      const popup = page.waitForEvent("popup");
      await button("Detach batch").click();
      const child = await popup;
      child.on("pageerror", (e) => errors.push(e.message));
      await child.getByTestId("batch-heatmap").waitFor();
      assert.equal(
        await left.count(),
        0,
        "Detached Batch leaves the compact image visible",
      );
      assert.equal(
        await page.locator(".integration-image-pane").getAttribute("inert"),
        null,
      );
      const closed = child.waitForEvent("close");
      await child
        .getByRole("button", { name: "Dock batch below image", exact: true })
        .click();
      await closed;
      await left.waitFor();
      assert.equal(
        await left
          .getByRole("tab", { name: "Batch", exact: true })
          .getAttribute("aria-selected"),
        "true",
      );
      assert.ok((await state()).imagePath.endsWith("/scan_2.npy"));
      await tab("Phase").click();
      await clearPhases.click();
      await clearDialog
        .getByRole("button", { name: "Clear all", exact: true })
        .click();
      await waitFor((s) => s.integration.phases.length === 0);
      assert.equal(
        clearCommands(),
        beforeClear + 1,
        "Only explicit confirmation clears phases",
      );
      assert.equal(await clearPhases.isDisabled(), true);
      assert.deepEqual(errors, []);
      reports.push({
        browser: name,
        checks:
          "Qt one/two/three control columns at both text sizes; simultaneous native pressure editing and file browsing; independent tab selections; mounted drafts across breakpoints; full-width compact controls; wide right panel; full phase names; Qt phase colors; aligned swatches; compact step/reference fields with padded borders and no parameter scrollbar; responsive Apply to all/All label; compact Overlay fields, responsive layout, padded borders and no horizontal overflow; real overlay scale/offset stepping; compact list actions beside steps; native phase reordering with stable selection and Undo/Redo; separated Clear All with Cancel/Escape/focus return and confirmed native deletion; directly accessible P/T steps; apply-all; references; Batch frame selection, keyboard switch and renderer preservation; full-height dock with detached image; full-width controls/pattern with both detached; restored dock size/collapse",
        errors,
      });
    } finally {
      await browser.close();
      await native.close();
    }
  }
  await writeFile(
    path.join(artifacts, "report.json"),
    JSON.stringify(reports, null, 2),
  );
  console.log(JSON.stringify(reports, null, 2));
} finally {
  await server.close();
  await rm(temp, { recursive: true, force: true });
}
