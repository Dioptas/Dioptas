// Real native exports through the Batch UI. Only the OS chooser is replaced;
// native production filter routing is independently tested in batch_export.rs.
import assert from "node:assert/strict";
import {
  copyFile,
  mkdir,
  mkdtemp,
  readFile,
  readdir,
  rm,
  writeFile,
} from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { chromium, webkit } from "playwright";
import { nativeClient, root } from "./native_backend_client.mjs";
const verifyBackground = process.argv.includes("--background");
const artifacts = path.join(
  root,
  `artifacts/${verifyBackground ? "batch-background-export" : "batch-export"}`,
);
await mkdir(artifacts, { recursive: true });
const temp = await mkdtemp(path.join(tmpdir(), "dioptas-batch-export-"));
const sources = [];
for (let i = 0; i < 3; i++) {
  const file = path.join(temp, `scan_${i}.tif`);
  await copyFile(path.join(root, "tests/data/CeO2_Pilatus1M.tif"), file);
  sources.push(file);
}
const receipts = [];
try {
  for (const [name, engine] of [
    ["chromium", chromium],
    ["webkit", webkit],
  ]) {
    const native = nativeClient();
    const browser = await engine.launch({ headless: true });
    const context = await browser.newContext({
      viewport: { width: 1400, height: 950 },
      deviceScaleFactor: 2,
    });
    const errors = [],
      saves = [],
      saveResults = [];
    let cancel = false,
      selectedPath = null;
    const call = async (action, args = {}) => {
      console.log(name, action);
      const result = await native.invoke(action, args);
      assert.equal(result.ok, true, `${action}: ${result.error}`);
      return result;
    };
    try {
      if (verifyBackground) {
        const source = path.join(temp, "garnet_processed_042.nxs");
        await copyFile(
          path.join(root, "backend/tests/fixtures/batch_background_input.h5"),
          source,
        );
        await call("batch_load_data", { paths: [source] });
        await call("batch_background_extract", {
          parameters: { smoothing: 0.37, iterations: 31, order: 8 },
        });
        await call("batch_normalization_settings", {
          start: 9,
          stop: 79,
          reference: 1,
        });
        await call("batch_normalize", { enabled: true });
        await call("batch_background_extract", {
          parameters: { smoothing: 0.37, iterations: 31, order: 8 },
        });
        await call("batch_background_display", {
          range: [2, 8],
          unit: "2th_deg",
          subtract: true,
          cut: true,
        });
      } else {
        await call("open_calibration", {
          path: path.join(root, "tests/data/CeO2_Pilatus1M.poni"),
        });
        await call("integration_settings", {
          bins: 64,
          cake_bins: 16,
          poisson_errors: true,
        });
        await call("open_image", { path: sources[0] });
        await call("batch_load", {
          paths: sources,
          start: 2,
          stop: 3,
          step: 1,
        });
      }
      const before = await call("state");
      const frameCount = before.batch.entries.length;
      const binCount = before.batch.pattern.x.length;
      if (verifyBackground) {
        assert.equal(before.batch.exportBaseName, "garnet_processed_042");
        assert.equal(before.batch.normalized, true);
        assert.equal(before.batch.backgroundState.subtract, true);
        assert.equal(before.batch.backgroundState.cut, true);
        assert(before.batch.x.length < binCount);
      }
      const page = await context.newPage();
      context.on("page", (p) =>
        p.on("pageerror", (e) => errors.push(e.message)),
      );
      page.on("pageerror", (e) => errors.push(e.message));
      await page.exposeFunction("__nativeInvoke", async (action, args = {}) => {
        if (action === "integration_save_batch") {
          saves.push({
            ...args,
            png_data: args.png_data ? "captured" : undefined,
          });
          if (cancel) return { ok: true, cancelled: true };
          args = {
            ...args,
            path: selectedPath ?? path.join(temp, `${name}.${args.format}`),
          };
        }
        const result = await native.invoke(action, args);
        if (action === "integration_save_batch") saveResults.push(result);
        return native.browserResult(result);
      });
      await page.addInitScript(() => {
        window.pywebview = {
          api: {
            invoke: async (a, p) => {
              window.__pending = (window.__pending ?? 0) + 1;
              try {
                return await window.__nativeInvoke(a, p);
              } finally {
                window.__pending--;
                if (a === "integration_save_batch")
                  window.__completedBatchSaves =
                    (window.__completedBatchSaves ?? 0) + 1;
              }
            },
          },
        };
      });
      await page.goto(pathToFileURL(path.join(root, "dist/index.html")).href);
      const ready = async () => {
        await page.waitForFunction(
          () => window.__pending === 0 && !document.querySelector(".spin"),
        );
        assert.deepEqual(errors, []);
      };
      await ready();
      await page
        .getByRole("button", { name: "Integration", exact: true })
        .click();
      // Opening uses the same detached-window channel as native Batch. Its writes
      // and chooser must route back through the main session.
      let batch = context.pages().find((p) => p !== page);
      if (!batch) {
        const popup = context.waitForEvent("page");
        await page
          .getByRole("button", { name: "Batch view…", exact: true })
          .click();
        batch = await popup;
      }
      await batch.getByTestId("batch-heatmap").waitFor();
      const canvas = batch.getByTestId("batch-heatmap");
      const save = async (format) => {
        console.log(name, "Save", format);
        const expectedSaves = saves.length + 1;
        await batch
          .getByRole("button", { name: "Save batch data", exact: true })
          .click();
        const dialog = batch.getByRole("dialog", {
          name: "Save batch data",
          exact: true,
        });
        await dialog
          .getByRole("combobox", { name: "Batch export format", exact: true })
          .selectOption(format);
        await dialog
          .getByRole("button", {
            name: ["xy", "chi", "dat", "fxye"].includes(format)
              ? "Choose basename…"
              : "Choose file…",
            exact: true,
          })
          .click();
        await page.waitForFunction(
          (n) => (window.__completedBatchSaves ?? 0) >= n,
          expectedSaves,
        );
        await ready();
        await batch.waitForFunction(
          () => !document.querySelector("dialog[open]"),
        );
      };
      // Escape/Cancel never reaches the chooser or processor and returns focus.
      await batch
        .getByRole("button", { name: "Save batch data", exact: true })
        .click();
      await batch.keyboard.press("Escape");
      assert.equal(saves.length, 0);
      await batch
        .getByRole("button", { name: "Save batch data", exact: true })
        .click();
      await batch
        .getByRole("dialog", { name: "Save batch data", exact: true })
        .getByRole("button", { name: "Cancel", exact: true })
        .click();
      assert.equal(saves.length, 0);
      cancel = true;
      await save("xy");
      assert.equal(
        (await readdir(temp)).filter((f) => f.startsWith(`${name}_`)).length,
        0,
      );
      cancel = false;
      for (const format of ["h5", "csv", "xy", "chi", "dat", "fxye"])
        await save(format);
      for (const format of ["xy", "chi", "dat", "fxye"]) {
        assert(
          (
            await readFile(path.join(temp, `${name}_000.${format}`), "utf8")
          ).includes("source_frame"),
        );
        await readFile(path.join(temp, `${name}_001.${format}`));
        await readFile(
          path.join(
            temp,
            `${name}_${String(frameCount - 1).padStart(3, "0")}.${format}`,
          ),
        );
        await assert.rejects(
          readFile(
            path.join(
              temp,
              `${name}_${String(frameCount).padStart(3, "0")}.${format}`,
            ),
          ),
        );
        if (verifyBackground)
          await readFile(
            path.join(temp, `bkg_subtracted/${name}_000.${format}`),
          );
      }
      assert.equal(
        (await readFile(path.join(temp, `${name}.csv`), "utf8"))
          .trim()
          .split("\n").length,
        1 + frameCount * binCount,
      );
      // Non-default unit, scale, zoom and palette must be captured as rendered.
      if (!verifyBackground) {
        await batch
          .getByRole("button", { name: "Batch unit Q", exact: true })
          .click();
        await ready();
        await batch.waitForFunction(
          () =>
            document.querySelector('[data-testid="batch-heatmap"]')?.dataset
              .unit === "q_A^-1",
        );
      }
      await batch
        .getByRole("button", {
          name: "Square root batch intensity",
          exact: true,
        })
        .click();
      await canvas.evaluate((c) => {
        const b = c.getBoundingClientRect();
        c.dispatchEvent(
          new WheelEvent("wheel", {
            deltaY: -180,
            clientX: b.x + b.width / 2,
            clientY: b.y + b.height / 2,
            bubbles: true,
            cancelable: true,
          }),
        );
      });
      await batch.waitForTimeout(150);
      await batch
        .getByRole("button", { name: "Batch color map", exact: true })
        .click();
      await batch.getByRole("option", { name: "Viridis", exact: true }).click();
      await batch.waitForTimeout(100);
      // Compare every PNG pixel with the active canvas composited over its actual
      // plot background. Also verify axes outside the heatmap contain drawn text.
      const expected = await canvas.evaluate((c) => {
        let bg = "#191c20";
        for (let e = c; e; e = e.parentElement) {
          const v = getComputedStyle(e).backgroundColor;
          if (v && v !== "transparent" && v !== "rgba(0, 0, 0, 0)") {
            bg = v;
            break;
          }
        }
        const out = document.createElement("canvas");
        out.width = c.width;
        out.height = c.height;
        const ctx = out.getContext("2d");
        ctx.fillStyle = bg;
        ctx.fillRect(0, 0, out.width, out.height);
        ctx.drawImage(c, 0, 0);
        const bytes = ctx.getImageData(0, 0, out.width, out.height).data;
        let hash = 2166136261;
        for (const b of bytes) hash = Math.imul(hash ^ b, 16777619) >>> 0;
        const original = c
          .getContext("2d")
          .getImageData(0, 0, c.width, c.height).data;
        const y = Math.round(
          (Number(c.dataset.plotTop) + Number(c.dataset.plotHeight)) *
            devicePixelRatio +
            10,
        );
        let axisPixels = 0;
        for (let yy = y; yy < c.height; yy++)
          for (let x = 0; x < c.width; x++)
            if (original[(yy * c.width + x) * 4 + 3] > 0) axisPixels++;
        return {
          width: c.width,
          height: c.height,
          hash,
          axisPixels,
          unit: c.dataset.unit,
          scale: c.dataset.intensityScale,
          xMin: Number(c.dataset.viewXMin),
        };
      });
      assert.equal(expected.unit, verifyBackground ? "2th_deg" : "q_A^-1");
      assert.equal(expected.scale, "sqrt");
      assert(expected.xMin > 0);
      assert(expected.axisPixels > 100);
      await save("png");
      const png = await readFile(path.join(temp, `${name}.png`));
      await writeFile(path.join(artifacts, `${name}-overview.png`), png);
      const decoded = await batch.evaluate(async (base64) => {
        const blob = await (
          await fetch(`data:image/png;base64,${base64}`)
        ).blob();
        const image = await createImageBitmap(blob);
        const c = document.createElement("canvas");
        c.width = image.width;
        c.height = image.height;
        const ctx = c.getContext("2d");
        ctx.drawImage(image, 0, 0);
        const bytes = ctx.getImageData(0, 0, c.width, c.height).data;
        let hash = 2166136261;
        for (const b of bytes) hash = Math.imul(hash ^ b, 16777619) >>> 0;
        return { width: c.width, height: c.height, hash };
      }, png.toString("base64"));
      assert.deepEqual(decoded, {
        width: expected.width,
        height: expected.height,
        hash: expected.hash,
      });
      // The separately owned 3D renderer registers the same capture contract.
      await batch.getByRole("tab", { name: "3D", exact: true }).click();
      await batch.waitForFunction(
        () =>
          document.querySelector('[data-testid="batch-surface"]')?.dataset
            .renderState === "ready",
      );
      const surface = batch.getByTestId("batch-surface");
      await batch.waitForTimeout(200); // Let the first ResizeObserver render settle.
      const expectedSurface = await surface.evaluate((c) => ({
        png: c.toDataURL("image/png").split(",")[1],
        width: c.width,
        height: c.height,
      }));
      selectedPath = path.join(temp, `${name}-surface.png`);
      await save("png");
      const surfacePNG = await readFile(selectedPath);
      assert.equal(surfacePNG.readUInt32BE(16), expectedSurface.width);
      assert.equal(surfacePNG.readUInt32BE(20), expectedSurface.height);
      assert(
        surfacePNG.toString("base64") === expectedSurface.png,
        "Saved PNG must match the active 3D canvas",
      );
      assert.notDeepEqual(surfacePNG, png);
      await writeFile(path.join(artifacts, `${name}-surface.png`), surfacePNG);
      selectedPath = null;
      const original = await readFile(path.join(temp, `${name}_000.xy`));
      await save("xy"); // Existing output is an error, never a partial success.
      const failure = saveResults.at(-1);
      assert.equal(failure.ok, false);
      assert.match(failure.error, /already exists/);
      assert.equal(failure.savedPaths, undefined);
      await batch.waitForFunction(() =>
        document
          .querySelector('.detached-batch-footer [role="alert"]')
          ?.textContent?.includes("already exists"),
      );
      assert.deepEqual(
        await readFile(path.join(temp, `${name}_000.xy`)),
        original,
      );
      // Image export on Files must be unavailable, rather than saving stale view pixels.
      await batch.getByRole("tab", { name: "Files", exact: true }).click();
      await batch
        .getByRole("button", { name: "Save batch data", exact: true })
        .click();
      const dialog = batch.getByRole("dialog", {
        name: "Save batch data",
        exact: true,
      });
      await batch.screenshot({
        path: path.join(artifacts, `${name}-save-ui.png`),
      });
      assert.equal(
        await dialog.locator('option[value="png"]').evaluate((e) => e.disabled),
        true,
      );
      await dialog.getByRole("button", { name: "Cancel", exact: true }).click();
      const after = await call("state");
      assert.deepEqual(after.batch.raster, before.batch.raster);
      assert.deepEqual(after.batch.entries, before.batch.entries);
      assert.deepEqual(
        after.batch.backgroundState,
        before.batch.backgroundState,
      );
      assert.equal(after.batch.normalized, before.batch.normalized);
      assert.deepEqual(after.batch.sourceBins, before.batch.sourceBins);
      for (const saved of saves)
        assert.equal(
          saved.suggested_name,
          `${verifyBackground ? "garnet_processed_042" : "scan"}.${saved.format}`,
        );
      assert.equal(after.batch.selected, before.batch.selected);
      assert.deepEqual(after.state.geometry, before.state.geometry);
      receipts.push({
        browser: name,
        formats: saves.map((s) => s.format),
        png: decoded,
        surface: {
          width: expectedSurface.width,
          height: expectedSurface.height,
        },
        axisPixels: expected.axisPixels,
        frames: after.batch.entries.length,
        normalized: after.batch.normalized,
        background: after.batch.backgroundState,
        sourceBins: after.batch.sourceBins,
        suggestedName: saves[0].suggested_name,
        errors,
      });
    } finally {
      await browser.close();
      await native.close();
    }
  }
  await writeFile(
    path.join(artifacts, "receipt.json"),
    JSON.stringify(receipts, null, 2),
  );
  console.log(JSON.stringify(receipts, null, 2));
} finally {
  await rm(temp, { recursive: true, force: true });
}
