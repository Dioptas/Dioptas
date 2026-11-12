// Replace only the OS chooser. Exercise the real Save button, display capture,
// native stdio writer and errors without opening a native window.
import assert from "node:assert/strict";
import { mkdir, mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { chromium, webkit } from "playwright";
import { nativeClient, root } from "./native_backend_client.mjs";
const artifacts = path.join(root, "artifacts/pattern-figure-export");
await mkdir(artifacts, { recursive: true });
const temp = await mkdtemp(path.join(tmpdir(), "dioptas-pattern-figure-"));
const receipts = [];
try {
  for (const [name, engine] of [
    ["chromium", chromium],
    ["webkit", webkit],
  ]) {
    const native = nativeClient();
    const browser = await engine.launch({ headless: true });
    try {
      const call = async (action, args = {}) => {
        const result = await native.invoke(action, args);
        assert.equal(result.ok, true, `${action}: ${result.error}`);
        return result;
      };
      await call("open_calibration", {
        path: path.join(root, "tests/data/CeO2_Pilatus1M.poni"),
      });
      await call("integration_settings", {
        bins: 256,
        cake_bins: 16,
        poisson_errors: true,
      });
      await call("open_image", {
        path: path.join(root, "tests/data/CeO2_Pilatus1M.tif"),
      });
      await call("integration_overlay", { operation: "capture" });
      const page = await browser.newPage({
        viewport: { width: 1000, height: 668 },
        deviceScaleFactor: 2,
      });
      const errors = [],
        saves = [];
      page.on("pageerror", (e) => errors.push(e.message));
      let selected = null,
        cancel = false;
      await page.exposeFunction("__nativeInvoke", async (action, args = {}) => {
        if (action === "integration_save_pattern") {
          if (!args.format) {
            assert.equal(args.png_data, undefined);
            assert.equal(args.svg_data, undefined);
          } else {
            assert(
              args.png_data?.length > 100 || args.svg_data?.startsWith("<svg"),
            );
            if (args.path) assert.equal(args.path, selected);
          }
          if (cancel) {
            saves.push({ cancelled: true });
            return { ok: true, cancelled: true };
          }
          args = { ...args, path: selected };
        }
        const result = await native.invoke(action, args);
        if (action === "integration_save_pattern")
          saves.push({ selected, result });
        return native.browserResult(result);
      });
      await page.addInitScript(() => {
        window.__pending = 0;
        window.__completedSaves = 0;
        window.pywebview = {
          api: {
            invoke: async (a, p) => {
              const track = !["progress", "pixel"].includes(a);
              if (track) window.__pending++;
              try {
                const result = await window.__nativeInvoke(a, p);
                if (a === "integration_save_pattern") window.__completedSaves++;
                return result;
              } finally {
                if (track) window.__pending--;
              }
            },
          },
        };
      });
      await page.goto(pathToFileURL(path.join(root, "dist/index.html")).href);
      const ready = () =>
        page.waitForFunction(
          () => window.__pending === 0 && !document.querySelector(".spin"),
        );
      await page.getByTestId("detector-canvas").waitFor();
      await ready();
      await page
        .getByRole("button", { name: "Integration", exact: true })
        .click();
      await page.getByTestId("pattern-canvas").waitFor();
      await ready();
      const save = page.getByRole("button", {
        name: "Save pattern",
        exact: true,
      });
      const imageButton = page.getByRole("button", {
        name: "Export pattern figure",
        exact: true,
      });
      assert.equal(
        await imageButton.evaluate((el) =>
          el.previousElementSibling?.getAttribute("aria-label"),
        ),
        "Save pattern",
      );
      const iconBounds = await imageButton.boundingBox(),
        saveBounds = await save.boundingBox();
      assert(
        iconBounds.x > saveBounds.x &&
          Math.abs(iconBounds.y - saveBounds.y) < 2,
        "The image icon must sit immediately right of Save",
      );
      const saveOnce = async () => {
        const count = await page.evaluate(() => window.__completedSaves);
        const figure = /\.(png|svg)$/i.test(selected);
        if (figure) {
          await page
            .getByRole("button", { name: "Export pattern figure", exact: true })
            .click();
          const editor = page.getByRole("dialog", {
            name: "Export pattern figure",
            exact: true,
          });
          await editor.waitFor();
          await editor
            .getByRole("combobox", { name: "Figure file format", exact: true })
            .selectOption(
              selected.toLowerCase().endsWith(".png") ? "png" : "svg",
            );
          await editor
            .getByRole("button", { name: "Save figure", exact: true })
            .click();
        } else await save.click();
        await page.waitForFunction(
          (count) => window.__completedSaves > count,
          count,
        );
        await ready();
        if (
          /\.(png|svg)$/i.test(selected) &&
          (cancel || saves.at(-1)?.result?.ok)
        ) {
          await page
            .getByRole("button", { name: "Close figure editor", exact: true })
            .click();
        }
      };
      const dimensions = await save.evaluate((element) => {
        const rect = element.getBoundingClientRect();
        return {
          left: rect.left,
          right: rect.right,
          top: rect.top,
          bottom: rect.bottom,
        };
      });
      assert(
        dimensions.left >= 0 &&
          dimensions.right <= 1000 &&
          dimensions.bottom <= 668,
      );
      // Numerical data saves never request or send figure buffers.
      for (const extension of ["xy", "xye", "chi", "dat", "fxye"]) {
        selected = path.join(temp, `${name} with spaces.${extension}`);
        await saveOnce();
        assert.equal(
          saves.at(-1).result.ok,
          true,
          JSON.stringify(saves.at(-1)),
        );
        const independent = path.join(temp, `${name}-direct.${extension}`);
        await call("integration_save_pattern", {
          path: independent,
          subtract_background: true,
        });
        assert.equal(
          (await readFile(selected, "utf8")).replaceAll(selected, "FILENAME"),
          (await readFile(independent, "utf8")).replaceAll(
            independent,
            "FILENAME",
          ),
        );
      }
      await page
        .getByRole("button", { name: "Pattern unit Q", exact: true })
        .click();
      await ready();
      await page
        .getByRole("button", {
          name: "Logarithmic pattern intensity",
          exact: true,
        })
        .click();
      await ready();
      const plot = page.getByTestId("pattern-canvas");
      const box = await plot.boundingBox();
      await page.mouse.move(box.x + box.width * 0.3, box.y + 20);
      await page.mouse.down();
      await page.mouse.move(box.x + box.width * 0.9, box.y + box.height * 0.8);
      await page.mouse.up();
      await page.mouse.move(40, 620);
      const beforeFigures = await call("state");
      for (const extension of ["png", "svg"]) {
        selected = path.join(temp, `${name}.${extension}`);
        await saveOnce();
        assert.equal(saves.at(-1).result.ok, true);
        const bytes = await readFile(selected);
        if (extension === "png") {
          assert.equal(bytes.subarray(1, 4).toString(), "PNG");
          assert.equal(bytes.readUInt32BE(16), Math.round((180 / 25.4) * 300));
          assert.equal(bytes.readUInt32BE(20), Math.round((115 / 25.4) * 300));
        } else {
          assert.match(bytes.toString(), /Q \(Å⁻¹\)/);
          assert(!bytes.toString().includes("<image"));
        }
        await writeFile(
          path.join(artifacts, `${name}-native.${extension}`),
          bytes,
        );
      }
      cancel = true;
      await saveOnce();
      cancel = false;
      assert.equal(saves.at(-1).cancelled, true);
      selected = path.join(temp, "missing-parent", `${name}.svg`);
      await saveOnce();
      assert.equal(saves.at(-1).result.ok, false);
      const dialog = page.getByRole("dialog", {
        name: "An error occurred",
        exact: true,
      });
      await dialog.waitFor();
      await dialog.getByRole("button", { name: "OK", exact: true }).click();
      await page
        .getByRole("button", { name: "Close figure editor", exact: true })
        .click();
      selected = path.join(temp, `${name}-retry.svg`);
      await saveOnce();
      assert.equal(saves.at(-1).result.ok, true);
      const after = await call("state");
      // Changing displayed units changes radial coordinates intentionally; saves
      // do not change intensities, overlay arrays or processing settings.
      assert.deepEqual(after.pattern.y, beforeFigures.pattern.y);
      assert.deepEqual(
        after.state.integration.overlays,
        beforeFigures.state.integration.overlays,
      );
      assert.deepEqual(
        after.state.integration.patternBackground,
        beforeFigures.state.integration.patternBackground,
      );
      for (const textSize of ["standard", "large"]) {
        await page.evaluate((value) => {
          document.querySelector(".app").dataset.textSize =
            value === "large" ? "large" : "normal";
        }, textSize);
        await page.screenshot({
          path: path.join(artifacts, `${name}-save-${textSize}.png`),
        });
        const bounds = await save.boundingBox();
        assert(
          bounds.x >= 0 &&
            bounds.x + bounds.width <= 1000 &&
            bounds.y + bounds.height <= 668,
        );
      }
      assert.deepEqual(errors, []);
      receipts.push({
        name,
        formats: 7,
        chooserCancelled: true,
        errorRetry: true,
        compact: [1000, 668],
      });
    } finally {
      await browser.close();
      await native.close();
    }
  }
  await writeFile(
    path.join(artifacts, "save-workflow.json"),
    JSON.stringify(receipts, null, 2),
  );
  console.log(JSON.stringify(receipts));
} finally {
  await rm(temp, { recursive: true, force: true });
}
