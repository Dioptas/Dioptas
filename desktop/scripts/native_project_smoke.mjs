import assert from "node:assert/strict";
import { mkdtemp, mkdir, rm, writeFile, stat } from "node:fs/promises";
import path from "node:path";
import { tmpdir } from "node:os";
import { pathToFileURL } from "node:url";
import { chromium, webkit } from "playwright";
import { nativeClient, root } from "./native_backend_client.mjs";
const artifacts = path.join(root, "desktop/artifacts/native-project");
await mkdir(artifacts, { recursive: true });
const temp = await mkdtemp(path.join(tmpdir(), "dioptas-project-ui-"));
const receipts = [];
try {
  for (const [name, type] of [
    ["chromium", chromium],
    ["webkit", webkit],
  ]) {
    const native = nativeClient();
    const browser = await type.launch({ headless: true });
    try {
      const project = path.join(temp, `${name}.dio`);
      const calls = [],
        errors = [];
      const invoke = async (action, payload = {}) => {
        calls.push([action, payload]);
        if (["save_project", "open_project"].includes(action) && !payload.path)
          payload = { ...payload, path: project };
        if (action === "save_combined_pattern")
          payload = {
            ...payload,
            path: path.join(temp, `${name}-combined.xy`),
          };
        const reply = await native.invoke(action, payload);
        assert.equal(reply.ok, true, `${action}: ${reply.error}`);
        return reply;
      };
      await invoke("open_image", {
        path: path.join(root, "dioptas/tests/data/CeO2_Pilatus1M.tif"),
      });
      await invoke("open_calibration", {
        path: path.join(root, "dioptas/tests/data/CeO2_Pilatus1M.poni"),
      });
      await invoke("integration_settings", { bins: 128, cake_bins: 36 });
      const page = await browser.newPage({
        viewport: { width: 1500, height: 1000 },
      });
      page.setDefaultTimeout(45000);
      page.on("pageerror", (e) => errors.push(e.message));
      await page.exposeFunction("__nativeInvoke", async (a, p) =>
        native.browserResult(await invoke(a, p)),
      );
      await page.addInitScript(() => {
        window.pywebview = {
          api: { invoke: (a, p) => window.__nativeInvoke(a, p) },
        };
      });
      await page.goto(
        pathToFileURL(path.join(root, "dioptas/desktop/ui/index.html")).href,
      );
      const group = page.getByRole("group", { name: "Project configurations" });
      const settings = page.getByRole("button", {
        name: "Settings",
        exact: true,
      });
      const toggle = page.getByRole("checkbox", {
        name: "Show configuration controls",
      });
      const closeSettings = page.getByRole("button", {
        name: "Close settings",
      });
      const assertBarHidden = async () => {
        assert.equal(await group.count(), 0);
        assert.equal(await page.locator(".has-configurations").count(), 0);
      };
      await page.getByTestId("detector-canvas").waitFor();
      await assertBarHidden();
      await settings.click();
      assert.equal(await toggle.isChecked(), false);
      await toggle.check();
      await page.screenshot({
        path: path.join(artifacts, `${name}-configuration-settings.png`),
      });
      // Settings fills the workspace even with the configuration preference on.
      await assertBarHidden();
      await closeSettings.click();
      await group.waitFor();
      await page.reload();
      await group.waitFor();
      const selector = group.getByRole("combobox", {
        name: "Active configuration",
      });
      await group
        .getByRole("button", { name: "Duplicate", exact: true })
        .click();
      await page.waitForFunction(
        () =>
          document.querySelector('[aria-label="Active configuration"]')
            ?.value === "1",
      );
      await group.getByRole("button", { name: "Rename", exact: true }).click();
      await group
        .getByRole("textbox", { name: "Configuration name" })
        .fill("High pressure");
      await group.getByRole("button", { name: "Apply", exact: true }).click();
      await page.waitForFunction(
        () =>
          document.querySelector('[aria-label="Active configuration"]')
            ?.selectedOptions[0]?.textContent === "High pressure",
      );
      await group.getByRole("button", { name: "Add", exact: true }).click();
      await page.waitForFunction(
        () =>
          document.querySelector('[aria-label="Active configuration"]')?.options
            .length === 3,
      );
      await group.getByRole("button", { name: "Remove", exact: true }).click();
      await page.waitForFunction(
        () =>
          document.querySelector('[aria-label="Active configuration"]')?.options
            .length === 2,
      );
      await selector.selectOption("0");
      await page.waitForFunction(
        () =>
          document.querySelector('[aria-label="Active configuration"]')
            ?.value === "0",
      );
      await page
        .getByRole("button", { name: "Save project", exact: true })
        .click();
      await page.waitForFunction(() =>
        document
          .querySelector(".navigation-project")
          ?.textContent?.endsWith(".dio"),
      );
      await group.getByRole("button", { name: "Remove", exact: true }).click();
      await page.waitForFunction(
        () =>
          document.querySelector('[aria-label="Active configuration"]')?.options
            .length === 1,
      );
      await page
        .getByRole("button", { name: "Open project", exact: true })
        .click();
      await page.waitForFunction(
        () =>
          document.querySelector('[aria-label="Active configuration"]')?.options
            .length === 2,
      );
      await selector.selectOption("1");
      await page.waitForFunction(
        () =>
          document.querySelector('[aria-label="Active configuration"]')
            ?.value === "1",
      );
      await page
        .getByRole("button", { name: "Integration", exact: true })
        .click();
      await page.waitForTimeout(300);
      await page.screenshot({
        path: path.join(artifacts, `${name}-configurations.png`),
      });
      const state = await invoke("state");
      assert.deepEqual(state.state.configurationLabels, [
        "Configuration 1",
        "High pressure",
      ]);
      assert.equal(state.state.configurationIndex, 1);
      assert.equal(state.pattern.x.length, 128);
      assert.equal(
        await page
          .getByRole("combobox", { name: "Active configuration", exact: true })
          .count(),
        1,
      );
      assert.equal(
        await page
          .getByRole("combobox", { name: "Configuration", exact: true })
          .count(),
        0,
      );
      const factor = page.getByRole("spinbutton", {
        name: "Detector factor",
        exact: true,
      });
      await factor.fill("2");
      await factor.press("Enter");
      await page
        .getByRole("button", { name: "Combine patterns", exact: true })
        .click();
      await page.waitForFunction(
        () =>
          document.querySelector(
            '.configuration-combination button[aria-pressed="true"]',
          )?.textContent === "Combine patterns",
      );
      await page
        .getByRole("button", { name: "Combine cakes", exact: true })
        .click();
      await page.waitForFunction(
        () =>
          document.querySelectorAll(
            '.configuration-combination button[aria-pressed="true"]',
          ).length === 2,
      );
      const combined = await invoke("state");
      assert.equal(combined.state.combination.factor, 2);
      assert.equal(combined.state.combination.patterns, true);
      assert.equal(combined.state.combination.cakes, true);
      assert.equal(combined.pattern.y.length, 128);
      await page
        .getByRole("button", { name: "Save combined pattern", exact: true })
        .click();
      await page.waitForFunction(() => !document.querySelector(".spin"));
      assert.ok(
        (await stat(path.join(temp, `${name}-combined.xy`))).size > 100,
      );
      await page.setViewportSize({ width: 1000, height: 668 });
      await page.screenshot({
        path: path.join(artifacts, `${name}-combined-small.png`),
      });
      const toolbar = await page
        .locator(".configuration-toolbar")
        .boundingBox();
      for (const element of await page
        .locator(
          ".configuration-toolbar button, .configuration-toolbar input, .configuration-toolbar select",
        )
        .all()) {
        const b = await element.boundingBox();
        assert.ok(
          b &&
            b.x >= toolbar.x &&
            b.x + b.width <= toolbar.x + toolbar.width + 1,
        );
      }
      await page.setViewportSize({ width: 1500, height: 1000 });
      await page.getByRole("button", { name: "Map", exact: true }).click();
      await group.waitFor();
      await page.screenshot({
        path: path.join(artifacts, `${name}-map-configurations.png`),
      });
      const configurationCalls = () =>
        calls.filter(([action]) => action === "configuration").length;
      const beforeHiding = configurationCalls();
      await settings.click();
      await toggle.uncheck();
      await closeSettings.click();
      await assertBarHidden();
      await page.reload();
      await page.getByTestId("detector-canvas").waitFor();
      await assertBarHidden();
      await page.screenshot({
        path: path.join(artifacts, `${name}-configurations-hidden.png`),
      });
      await settings.click();
      assert.equal(await toggle.isChecked(), false);
      // The opt-in remains readable in the smallest supported workspace.
      await page.setViewportSize({ width: 1000, height: 668 });
      await page.getByRole("button", { name: "Larger", exact: true }).click();
      await toggle.scrollIntoViewIfNeeded();
      const card = toggle.locator("xpath=ancestor::section[1]");
      const bounds = await card.boundingBox();
      const toggleBounds = await toggle.boundingBox();
      assert.ok(toggleBounds.x >= bounds.x);
      assert.ok(toggleBounds.x + toggleBounds.width <= bounds.x + bounds.width);
      await page.screenshot({
        path: path.join(artifacts, `${name}-configuration-settings-small.png`),
      });
      await toggle.check();
      await closeSettings.click();
      await group.waitFor();
      assert.equal(await selector.inputValue(), "1");
      assert.equal(await selector.locator("option").count(), 2);
      assert.equal(configurationCalls(), beforeHiding);
      const afterHiding = await invoke("state");
      assert.deepEqual(
        afterHiding.state.configurationLabels,
        state.state.configurationLabels,
      );
      assert.equal(afterHiding.state.configurationIndex, 1);
      assert.deepEqual(errors, []);
      receipts.push({
        browser: name,
        pythonInChild: false,
        projectControls: [
          "add",
          "duplicate",
          "rename",
          "select",
          "remove",
          "save",
          "open",
        ],
        combinedPatternAndCake: true,
        combinedPatternExport: true,
        singleConfigurationSelector: true,
        configurationLabels: state.state.configurationLabels,
        configurationPreference: {
          hiddenByDefault: true,
          persistedOnAndOff: true,
          hidingPreservesSelectionAndConfigurations: true,
          smallWindowLargeText: true,
        },
        errors,
        commands: [...new Set(calls.map(([a]) => a))],
      });
    } finally {
      await browser.close();
      await native.close();
    }
  }
} finally {
  await rm(temp, { recursive: true, force: true });
}
await writeFile(
  path.join(artifacts, "headless.json"),
  JSON.stringify(receipts, null, 2) + "\n",
);
console.log(JSON.stringify(receipts, null, 2));
