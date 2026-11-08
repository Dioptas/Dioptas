import assert from "node:assert/strict";
import { mkdir, mkdtemp, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { build } from "vite";
import react from "@vitejs/plugin-react";
import { viteSingleFile } from "vite-plugin-singlefile";
import { chromium, webkit } from "playwright";

const desktop = fileURLToPath(new URL("../", import.meta.url));
const artifacts = new URL("../artifacts/ui-components/", import.meta.url);
await mkdir(artifacts, { recursive: true });
// Bundle like the desktop host, including static stylesheet loading.
const bundle = await mkdtemp(path.join(tmpdir(), "dioptas-ui-components-"));
await build({
  configFile: false,
  root: desktop,
  plugins: [react(), viteSingleFile()],
  logLevel: "error",
  build: {
    outDir: bundle,
    emptyOutDir: true,
    rollupOptions: { input: path.join(desktop, "scripts/ui_fixture.html") },
  },
});
const reports = [];
try {
  for (const [name, engine] of Object.entries({ chromium, webkit })) {
    const browser = await engine.launch({ headless: true });
    try {
      const page = await browser.newPage({
        viewport: { width: 1280, height: 950 },
      });
      const errors = [];
      page.on("pageerror", (error) => errors.push(error.message));
      await page.goto(
        pathToFileURL(path.join(bundle, "scripts/ui_fixture.html")).href,
      );
      await page.waitForFunction(() => window.uiFixture);
      for (const large of [false, true]) {
        await page.evaluate((large) => window.uiFixture.render(large), large);
        const neutral = async (locator) => {
          const styles = await locator.evaluateAll((elements) =>
            elements.map((element) => {
              const style = getComputedStyle(element);
              return {
                label: element.getAttribute("aria-label"),
                type: element.type,
                disabled: element.disabled,
                background: style.backgroundColor,
                border: style.borderTopColor,
                radius: style.borderTopLeftRadius,
                scheme: style.colorScheme,
                font: style.fontSize,
              };
            }),
          );
          assert.ok(styles.length);
          for (const style of styles) {
            assert.equal(
              style.background,
              style.disabled ? "rgb(32, 34, 38)" : "rgb(20, 23, 27)",
              JSON.stringify(style),
            );
            assert.equal(style.border, "rgb(65, 72, 79)");
            assert.equal(style.radius, "5px");
            assert.equal(style.scheme, "dark");
          }
          return styles;
        };
        await neutral(
          page.locator(
            '[data-field-set] :is(input:not([type="checkbox"]), select, textarea), .data-table :is(input:not([readonly]):not([type="color"]), select)',
          ),
        );
        assert.equal(
          await page
            .getByLabel("Readonly table value")
            .evaluate((el) => getComputedStyle(el).backgroundColor),
          "rgba(0, 0, 0, 0)",
        );
        const checkbox = page.getByLabel("Panel checkbox");
        await checkbox.uncheck();
        assert.equal(await checkbox.isChecked(), false);
        await checkbox.check();
        assert.equal(await checkbox.isChecked(), true);
        await page.getByLabel("Panel dropdown").selectOption("log");
        assert.equal(
          await page.getByLabel("Panel dropdown").inputValue(),
          "log",
        );
        await page
          .getByRole("button", { name: "Focus input ref", exact: true })
          .click();
        assert.equal(
          await page
            .getByLabel("Ref target")
            .evaluate((el) => document.activeElement === el),
          true,
        );
        assert.equal(
          await page
            .getByLabel("Ref target")
            .evaluate((el) => getComputedStyle(el).outlineColor),
          "rgb(135, 147, 159)",
        );
        await page
          .getByRole("button", { name: "Open popup", exact: true })
          .click();
        const popup = page.getByRole("dialog", { name: "Popup", exact: true });
        await neutral(
          popup.locator('input:not([type="checkbox"]), select, textarea'),
        );
        assert.equal(
          await popup.evaluate((el) => getComputedStyle(el).backgroundColor),
          "rgb(32, 34, 38)",
        );
        await popup.getByRole("button", { name: "Close popup" }).click();
        await page
          .getByRole("button", { name: "Open dialog", exact: true })
          .focus();
        await page
          .getByRole("button", { name: "Open dialog", exact: true })
          .press("Enter");
        const dialog = page.getByRole("dialog", {
          name: "Fixture dialog",
          exact: true,
        });
        assert.equal(
          await page
            .getByLabel("Dialog autofocus")
            .evaluate((el) => document.activeElement === el),
          true,
        );
        await neutral(
          dialog.locator(
            '[data-field-set] :is(input:not([type="checkbox"]), select, textarea)',
          ),
        );
        await dialog
          .getByRole("button", { name: "Open nested dialog" })
          .focus();
        await dialog
          .getByRole("button", { name: "Open nested dialog" })
          .press("Enter");
        assert.equal(
          await page
            .getByLabel("Nested autofocus")
            .evaluate((el) => document.activeElement === el),
          true,
        );
        await page.keyboard.press("Escape");
        await page
          .getByRole("dialog", { name: "Nested dialog", exact: true })
          .waitFor({ state: "detached" });
        assert.equal(await dialog.isVisible(), true);
        assert.equal(
          await dialog
            .getByRole("button", { name: "Open nested dialog" })
            .evaluate((el) => document.activeElement === el),
          true,
        );
        await dialog
          .getByRole("heading", { name: "Dialog", exact: true })
          .click();
        assert.equal(
          await dialog.isVisible(),
          true,
          "Clicking dialog padding/content must not dismiss it",
        );
        await page.screenshot({
          path: fileURLToPath(
            new URL(`${name}-${large ? "large" : "normal"}.png`, artifacts),
          ),
        });
        await page.keyboard.press("Escape");
        await dialog.waitFor({ state: "detached" });
        assert.equal(
          await page
            .getByRole("button", { name: "Open dialog", exact: true })
            .evaluate((el) => document.activeElement === el),
          true,
        );
        await page
          .getByRole("button", { name: "Open dialog", exact: true })
          .focus();
        await page
          .getByRole("button", { name: "Open dialog", exact: true })
          .press("Enter");
        await page.mouse.click(2, 2);
        await dialog.waitFor({ state: "detached" });
        await page
          .getByRole("button", { name: "Open dialog", exact: true })
          .focus();
        await page
          .getByRole("button", { name: "Open dialog", exact: true })
          .press("Enter");
        await dialog
          .getByRole("button", { name: "Imperative close", exact: true })
          .click();
        await dialog.waitFor({ state: "detached" });
        const submissions = await page.evaluate(
          () => window.uiFixture.report.submits,
        );
        await page.getByRole("button", { name: "Submit native form" }).click();
        assert.equal(
          await page.evaluate(() => window.uiFixture.report.submits),
          submissions + 1,
        );
        const number = page.getByLabel("Validated number", { exact: true });
        await number.fill("-2");
        await number.press("Enter");
        assert.equal(await number.getAttribute("aria-invalid"), "true");
        await number.press("Escape");
        assert.equal(await number.inputValue(), "2");
        await number.fill("3.5");
        await number.press("Enter");
        await page.waitForFunction(
          () => window.uiFixture.report.commits.at(-1) === 3.5,
        );
        assert.equal(await number.getAttribute("aria-invalid"), "false");
        await page.getByRole("heading", { name: "Panel", exact: true }).hover();
        assert.equal(
          await page
            .getByLabel("Rectangle zoom", { exact: true })
            .evaluate((el) => getComputedStyle(el).backgroundColor),
          "rgba(0, 0, 0, 0)",
        );
        await page
          .getByRole("button", { name: "Show histogram", exact: true })
          .click();
        await page
          .getByRole("button", {
            name: "Detector histogram settings",
            exact: true,
          })
          .click();
        const histogram = page.getByRole("dialog", {
          name: "Detector display settings",
          exact: true,
        });
        assert.equal(await histogram.evaluate((el) => el.tagName), "DIALOG");
        await neutral(
          histogram.locator('input:not([type="checkbox"]), select'),
        );
        await histogram
          .getByLabel("Image scale", { exact: true })
          .selectOption("log");
        assert.equal(
          await histogram
            .getByLabel("Image scale", { exact: true })
            .inputValue(),
          "log",
        );
        await page.screenshot({
          path: fileURLToPath(
            new URL(
              `${name}-histogram-${large ? "large" : "normal"}.png`,
              artifacts,
            ),
          ),
        });
        await page.keyboard.press("Escape");
        await histogram.waitFor({ state: "detached" });
        await page
          .getByRole("button", {
            name: "Detector histogram settings",
            exact: true,
          })
          .click();
        await page.mouse.click(2, 2);
        await histogram.waitFor({ state: "detached" });
      }
      assert.deepEqual(errors, []);
      reports.push({
        browser: name,
        passed: true,
        checks: [
          "shared field/surface colors at both text sizes",
          "table and detached-editor fields",
          "portals",
          "checkbox and select input",
          "forwarded refs and focus",
          "native form submit",
          "controlled and nested dialogs",
          "Escape/backdrop dismissal and restored focus",
          "scientific draft validation/commit/cancel",
          "transparent plot selectors",
          "native histogram settings dialog, display edits, Escape and backdrop dismissal",
        ],
      });
      console.log(
        `${name}: shared controls, fields, dialogs, portals and scientific edits passed`,
      );
    } finally {
      await browser.close();
    }
  }
  await writeFile(
    new URL("report.json", artifacts),
    JSON.stringify(reports, null, 2),
  );
} finally {
  await rm(bundle, { recursive: true, force: true });
}
