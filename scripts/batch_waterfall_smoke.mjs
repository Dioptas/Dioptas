import assert from "node:assert/strict";
import path from "node:path";
import os from "node:os";
import { mkdtemp, writeFile, readFile, rm, mkdir } from "node:fs/promises";
import { createServer } from "vite";
import { chromium, webkit } from "playwright";
import { nativeClient, root } from "./native_backend_client.mjs";
const temp = await mkdtemp(path.join(os.tmpdir(), "dioptas-waterfall-"));
const artifacts = path.join(root, "artifacts/batch-waterfall");
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
  root,
  server: { host: "127.0.0.1", port: 0 },
});
await server.listen();
try {
  for (const [name, engine] of [
    ["chromium", chromium],
    ["webkit", webkit],
  ]) {
    const native = nativeClient(),
      browser = await engine.launch({ headless: true }),
      requests = [],
      errors = [];
    let completed = 0,
      overlayCompleted = 0;
    const call = async (action, payload = {}) => {
      requests.push({ action, payload });
      if (action === "batch_load_data") payload = { paths };
      const r = await native.invoke(action, {
        ...payload,
        requested_products: { cake: false, rings: false },
      });
      assert.equal(r.ok, true, `${action}: ${r.error}`);
      if (action === "batch_waterfall") completed++;
      if (action === "integration_overlay") overlayCompleted++;
      return r;
    };
    try {
      await call("open_calibration", { path: poni });
      await call("integration_settings", { bins: 40, trim_zeros: false });
      await call("batch_load", { paths });
      const context = await browser.newContext({
        viewport: { width: 1440, height: 1000 },
      });
      await context.exposeFunction("__waterfallCompleted", () => completed);
      await context.exposeFunction(
        "__overlayCompleted",
        () => overlayCompleted,
      );
      context.on("page", (p) =>
        p.on("pageerror", (e) => errors.push(e.message)),
      );
      await context.exposeFunction("__waterfallInvoke", async (a, p) =>
        native.browserResult(await call(a, p)),
      );
      await context.addInitScript(() => {
        window.pywebview = {
          api: { invoke: (a, p) => window.__waterfallInvoke(a, p) },
        };
        try {
          localStorage.setItem("dioptas-batch:docked", "true");
        } catch {}
      });
      const page = await context.newPage();
      await page.goto(server.resolvedUrls.local[0]);
      await page
        .getByRole("button", { name: "Integration", exact: true })
        .click();
      await page
        .getByRole("button", { name: "Batch view…", exact: true })
        .click();
      const canvas = page.getByTestId("batch-heatmap");
      await canvas.waitFor();
      const count = () =>
        requests.filter((r) => r.action === "batch_waterfall").length;
      const point = async (c, x, y) =>
        c.evaluate(
          (c, [x, y]) => {
            const b = c.getBoundingClientRect(),
              d = c.dataset;
            return {
              x: b.x + Number(d.plotLeft) + x * Number(d.plotWidth),
              y: b.y + Number(d.plotTop) + (1 - y) * Number(d.plotHeight),
            };
          },
          [x, y],
        );
      const drag = async (p, c, a, b, button = "left") => {
        const from = await point(c, ...a),
          to = await point(c, ...b);
        await p.mouse.move(from.x, from.y);
        await p.mouse.down({ button });
        await p.mouse.move(to.x, to.y, { steps: 8 });
        await p.mouse.up({ button });
      };
      const settled = (p) =>
        p.waitForFunction(
          () =>
            !document.querySelector('.batch-series-panel[aria-busy="true"]'),
        );
      const waitAction = async (_page, n) => {
        const deadline = Date.now() + 30000;
        while (completed < n) {
          assert.ok(
            Date.now() < deadline,
            `Timed out waiting for waterfall ${n}`,
          );
          await new Promise((resolve) => setTimeout(resolve, 20));
        }
      };
      const initial = await canvas.getAttribute("data-view-x-max");
      await page
        .getByRole("button", { name: "Batch waterfall", exact: true })
        .click();
      await drag(page, canvas, [0.9, 0.95], [0.1, 0.1]);
      await page
        .getByRole("tabpanel", { name: "Overlay controls", exact: true })
        .waitFor();
      await settled(page);
      await waitAction(page, 1);
      assert.equal(count(), 1);
      assert.equal(await canvas.getAttribute("data-view-x-max"), initial);
      let state = await call("state");
      assert.equal(state.state.integration.overlays.length, 5);
      assert.deepEqual(
        state.state.integration.overlays.map((o) => o.batchSource.row),
        [0, 1, 2, 3, 4],
      );
      const generatedSpacing = state.state.integration.waterfallSeparation;
      assert.ok(generatedSpacing > 0 && generatedSpacing !== 100);
      assert.deepEqual(
        state.state.integration.overlays.map((o) => o.offset),
        [5, 4, 3, 2, 1].map((i) => -i * generatedSpacing),
      );
      const first = state.pattern.curves;
      assert.equal(
        await page
          .getByRole("button", { name: "Auto waterfall spacing", exact: true })
          .innerText(),
        "A",
      );
      // Both supported layouts are intentional: a stacked wide-panel rail and
      // a compact toolbar. Test their containment rather than assuming one row.
      for (const compact of [false, true]) {
        for (const large of [false, true]) {
          const layout = await page
            .locator(".qt-overlay-waterfall-actions")
            .evaluate(
              async (row, { large, compact }) => {
                const host = document.querySelector("[data-text-size]"),
                  previous = host.getAttribute("data-text-size");
                const panel = row.closest(".integration-tab-overlay");
                const previousStyle = panel.style.cssText;
                if (compact) panel.style.maxWidth = "550px";
                host.setAttribute("data-text-size", large ? "large" : "normal");
                await new Promise((resolve) =>
                  requestAnimationFrame(() => requestAnimationFrame(resolve)),
                );
                const buttons = [...row.querySelectorAll("button")],
                  bounds = row.getBoundingClientRect();
                const result = buttons.map((button) => {
                  const r = button.getBoundingClientRect(),
                    range = document.createRange();
                  range.selectNodeContents(button);
                  return {
                    left: r.left,
                    right: r.right,
                    y: r.y,
                    height: r.height,
                    width: r.width,
                    textWidth: range.getBoundingClientRect().width,
                  };
                });
                const measuredCompact =
                  getComputedStyle(row).gridTemplateColumns.split(" ").length >
                  2;
                host.setAttribute("data-text-size", previous);
                panel.style.cssText = previousStyle;
                return {
                  buttons: result,
                  compact: measuredCompact,
                  left: bounds.left,
                  right: bounds.right,
                };
              },
              { large, compact },
            );
          assert.equal(layout.compact, compact);
          assert.equal(layout.buttons.length, 3);
          assert.ok(
            layout.buttons.every(
              (b) =>
                (!layout.compact || Math.abs(b.y - layout.buttons[0].y) < 1) &&
                b.left >= layout.left - 1 &&
                b.right <= layout.right + 1,
            ),
          );
          assert.ok(
            layout.buttons[0].width >= layout.buttons[0].textWidth + 8,
            `Waterfall text fits beside A and Reset: ${JSON.stringify({ large, ...layout })}`,
          );
        }
      }
      const spacing = page.getByRole("spinbutton", {
        name: "Waterfall separation",
        exact: true,
      });
      assert.equal(Number(await spacing.inputValue()), generatedSpacing);
      // Auto uses each curve's mean above its own minimum, then gives each
      // nonflat curve equal weight; constant offsets do not change spacing.
      const signals = state.pattern.curves.flatMap((curve) => {
        const values = curve.y.filter(Number.isFinite);
        const minimum = Math.min(...values);
        return minimum < Math.max(...values)
          ? [values.reduce((sum, y) => sum + y - minimum, 0) / values.length]
          : [];
      });
      const range =
        (signals.reduce((sum, signal) => sum + signal, 0) / signals.length) *
        0.1;
      const base = 10 ** Math.floor(Math.log10(range));
      const expectedSpacing =
        base * [1, 2, 5, 10].find((v) => v >= range / base);
      assert.equal(generatedSpacing, expectedSpacing);
      await page
        .getByRole("button", { name: "Auto waterfall spacing", exact: true })
        .click();
      await page.waitForFunction(
        async () => (await window.__overlayCompleted()) >= 1,
      );
      state = await call("state");
      assert.equal(
        state.state.integration.waterfallSeparation,
        expectedSpacing,
      );
      assert.deepEqual(
        state.state.integration.overlays.map((o) => o.offset),
        [5, 4, 3, 2, 1].map((i) => -i * expectedSpacing),
      );
      assert.ok(state.state.integration.overlays.every((o) => o.scale === 1));
      await spacing.fill("100");
      await spacing.press("Enter");
      await page
        .getByRole("button", { name: "Waterfall", exact: true })
        .click();
      await page.waitForFunction(
        async () => (await window.__overlayCompleted()) >= 3,
      );
      state = await call("state");
      assert.deepEqual(
        state.state.integration.overlays.map((o) => o.offset),
        [-500, -400, -300, -200, -100],
      );
      await drag(page, canvas, [0.1, 0.1], [0.9, 0.95]);
      await settled(page);
      await waitAction(page, 2);
      assert.equal(count(), 2);
      state = await call("state");
      assert.deepEqual(state.pattern.curves, first);
      await page.getByRole("button", { name: "Options", exact: true }).click();
      const step = page.getByRole("spinbutton", {
        name: "Batch frame step",
        exact: true,
      });
      await step.fill("2");
      await step.press("Enter");
      await settled(page);
      await waitAction(page, 3);
      assert.equal(count(), 3);
      state = await call("state");
      assert.deepEqual(
        state.state.integration.overlays.map((o) => o.batchSource.row),
        [0, 2, 4],
      );
      await page.getByRole("tab", { name: "2D", exact: true }).click();
      // A replacement with the same files/count retains the visible Step.
      // The tool cancels its old region but must not secretly reset that stride.
      const replacement = await readFile(paths[0]);
      const headerLength = replacement.readUInt16LE(8);
      for (let i = 10 + headerLength; i < replacement.length; i += 8)
        replacement.writeDoubleLE(replacement.readDoubleLE(i) + 200, i);
      await writeFile(paths[0], replacement);
      await page
        .getByRole("button", { name: "Load raw/proc data", exact: true })
        .click();
      await canvas.waitFor();
      await page.waitForFunction(
        () =>
          document
            .querySelector('[data-testid="batch-heatmap"]')
            ?.getAttribute("data-waterfall-active") === "false",
      );
      await page.getByRole("button", { name: "Options", exact: true }).click();
      assert.equal(await step.inputValue(), "2");
      await page.getByRole("tab", { name: "2D", exact: true }).click();
      await page
        .getByRole("button", { name: "Batch waterfall", exact: true })
        .click();
      await drag(page, canvas, [0.1, 0.1], [0.9, 0.95]);
      await waitAction(page, 4);
      assert.deepEqual(
        (await call("state")).state.integration.overlays.map(
          (o) => o.batchSource.row,
        ),
        [0, 2, 4],
      );
      const start = await point(canvas, 0.15, 0.15),
        end = await point(canvas, 0.8, 0.8);
      await page.mouse.move(start.x, start.y);
      await page.mouse.down();
      await page.mouse.move(end.x, end.y, { steps: 6 });
      await canvas.press("Escape");
      await page.mouse.up();
      assert.equal(count(), 4);
      assert.equal(await canvas.getAttribute("data-waterfall-active"), "false");
      await page
        .getByRole("button", { name: "Batch waterfall", exact: true })
        .click();
      await page.mouse.move(start.x, start.y);
      await page.mouse.down();
      await page.mouse.move(end.x, end.y, { steps: 6 });
      await canvas.dispatchEvent("pointercancel", { pointerId: 1 });
      await page.mouse.up();
      assert.equal(count(), 4);
      await canvas.press("Escape");
      await drag(page, canvas, [0.15, 0.15], [0.8, 0.8]);
      assert.ok(
        Number(await canvas.getAttribute("data-view-x-max")) < Number(initial),
      );
      const beforePan = await canvas.getAttribute("data-view-x-min");
      await drag(page, canvas, [0.4, 0.4], [0.55, 0.5], "right");
      assert.notEqual(await canvas.getAttribute("data-view-x-min"), beforePan);
      const middle = await point(canvas, 0.5, 0.5);
      await page.mouse.move(middle.x, middle.y);
      await page.mouse.wheel(0, -150);
      await canvas.press("f");
      assert.equal(await canvas.getAttribute("data-view-x-max"), initial);
      assert.equal(count(), 4);
      const popup = page.waitForEvent("popup");
      await page
        .getByRole("button", { name: "Detach batch", exact: true })
        .click();
      const child = await popup;
      const childCanvas = child.getByTestId("batch-heatmap");
      await childCanvas.waitFor();
      await child
        .getByRole("button", { name: "Batch waterfall", exact: true })
        .click();
      await drag(child, childCanvas, [0.1, 0.1], [0.9, 0.95]);
      await settled(child);
      await waitAction(child, 5);
      assert.equal(count(), 5);
      // Detaching retains the visible requested stride of 2.
      assert.equal((await call("state")).state.integration.overlays.length, 3);
      await page.screenshot({ path: path.join(artifacts, `${name}-main.png`) });
      await child.screenshot({
        path: path.join(artifacts, `${name}-detached.png`),
      });
      const closed = child.waitForEvent("close");
      await child
        .getByRole("button", { name: "Dock batch below image", exact: true })
        .click();
      await closed;
      await page.getByTestId("batch-heatmap").waitFor();
      assert.deepEqual(errors, []);
      console.log(
        JSON.stringify({
          browser: name,
          runtime: "rust",
          rectangleActions: count(),
          cancelled: 2,
          stepRegenerated: true,
          detached: true,
          errors,
        }),
      );
    } finally {
      await browser.close();
      await native.close();
    }
  }
} finally {
  await server.close();
  await rm(temp, { recursive: true, force: true });
}
