import assert from "node:assert/strict";
import {
  mkdtemp,
  mkdir,
  rm,
  writeFile,
  stat,
  readFile,
} from "node:fs/promises";
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
        if (action === "integration_save_pattern")
          payload = {
            ...payload,
            path: path.join(temp, `${name}-displayed.xy`),
          };
        const reply = await native.invoke(action, payload);
        assert.equal(reply.ok, true, `${action}: ${reply.error}`);
        return reply;
      };
      const host = await invoke("__host__");
      assert.equal(host.runtime, "rust");
      assert.equal(host.engine, "dioptrin");
      assert.equal(host.qtApplication, false);
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
        name: "Enable configurations",
      });
      const closeSettings = page.getByRole("button", {
        name: "Close settings",
      });
      const openConfigurations = async () => {
        await settings.click();
        assert.equal(
          await toggle.isVisible(),
          false,
          "Configurations have their own Settings tab",
        );
        assert.equal(
          await page
            .getByRole("heading", { name: "Processing", exact: true })
            .count(),
          0,
        );
        assert.equal(
          await page
            .getByRole("heading", { name: "Pattern navigation", exact: true })
            .count(),
          0,
        );
        await page
          .getByRole("tab", { name: "Configurations", exact: true })
          .click();
        assert.equal(await toggle.isVisible(), true);
        assert.equal(
          await page
            .getByRole("heading", {
              name: "Multi-detector setups",
              exact: true,
            })
            .count(),
          0,
        );
      };
      const assertBarHidden = async () => {
        assert.equal(await group.count(), 0);
        assert.equal(await page.locator(".has-configurations").count(), 0);
      };
      await page.getByTestId("detector-canvas").waitFor();
      await assertBarHidden();
      await openConfigurations();
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
      const browsing = group.getByRole("group", {
        name: "Configuration browsing",
        exact: true,
      });
      const originalPath = (await invoke("state")).state.imagePath;
      await browsing
        .getByRole("button", {
          name: "Next files in all configurations",
          exact: true,
        })
        .click();
      await page
        .getByText("No matching files for configuration browsing", {
          exact: true,
        })
        .waitFor();
      assert.equal((await invoke("state")).state.imagePath, originalPath);
      await openConfigurations();
      const browsingSettings = page.getByRole("group", {
        name: "Configuration browsing settings",
        exact: true,
      });
      assert.equal(await browsingSettings.getByRole("combobox").count(), 0);
      await browsingSettings
        .getByRole("button", { name: "Use MEC preset", exact: true })
        .click();
      assert.equal(
        await browsingSettings
          .getByRole("spinbutton", {
            name: "Filename number with folder",
            exact: true,
          })
          .inputValue(),
        "3",
      );
      const customRules = {
        "Image filename number": "2",
        "File step": "3",
        "Folder path number": "2",
        "Folder step": "2",
        "Filename number with folder": "2",
        "Filename step with folder": "5",
      };
      for (const [label, value] of Object.entries(customRules)) {
        await browsingSettings
          .getByRole("spinbutton", { name: label, exact: true })
          .fill(value);
      }
      const fileStep = browsingSettings.getByRole("spinbutton", {
        name: "File step",
        exact: true,
      });
      await fileStep.fill("0");
      await fileStep.blur();
      assert.equal(await fileStep.inputValue(), "3");
      await browsingSettings.scrollIntoViewIfNeeded();
      await page.screenshot({
        path: path.join(artifacts, `${name}-browsing-settings.png`),
      });
      await closeSettings.click();
      await browsing
        .getByRole("button", {
          name: "Next folders in all configurations",
          exact: true,
        })
        .click();
      await page.waitForFunction(() => !document.querySelector(".spin"));
      const folderCall = calls.findLast(
        ([action]) => action === "configuration_navigation",
      );
      assert.deepEqual(folderCall[1], {
        target: "folder",
        direction: 1,
        scope: "all",
        number_position: 2,
        step: 2,
        folder_number_position: 2,
        folder_filename_position: 2,
        folder_filename_step: 5,
      });
      assert.equal((await invoke("state")).state.imagePath, originalPath);
      // Combining is a configuration setting, including before Integration
      // and while a different workspace mode is selected.
      const combinePatterns = group.getByRole("button", {
        name: "Combine patterns",
        exact: true,
      });
      const combineImages = group.getByRole("button", {
        name: "Combined cake",
        exact: true,
      });
      assert.equal(await combinePatterns.isVisible(), true);
      assert.equal(await combineImages.isVisible(), true);
      assert.match(
        await combineImages.getAttribute("title"),
        /calibrated 2D cakes/,
      );
      await combinePatterns.click();
      await page.waitForFunction(() => !document.querySelector(".spin"));
      await combineImages.click();
      await page.waitForFunction(
        () =>
          document.querySelectorAll(
            '.configuration-combination button[aria-pressed="true"]',
          ).length === 2,
      );
      const fromConfigurationBar = await invoke("state");
      assert.equal(fromConfigurationBar.state.combination.patterns, true);
      assert.equal(fromConfigurationBar.state.combination.cakes, true);
      assert.ok(fromConfigurationBar.pattern && fromConfigurationBar.cake);
      await page.screenshot({
        path: path.join(
          artifacts,
          `${name}-configuration-combination-calibration.png`,
        ),
      });
      await page.getByRole("button", { name: "Mask", exact: true }).click();
      assert.equal(await combinePatterns.getAttribute("aria-pressed"), "true");
      assert.equal(await combineImages.getAttribute("aria-pressed"), "true");
      await combinePatterns.click();
      await page.waitForFunction(() => !document.querySelector(".spin"));
      await combineImages.click();
      await page.waitForFunction(
        () =>
          document.querySelectorAll(
            '.configuration-combination button[aria-pressed="true"]',
          ).length === 0,
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
      const idle = async () => {
        await page.waitForFunction(() => !document.querySelector(".spin"));
        await page
          .getByRole("button", { name: "Combine patterns", exact: true })
          .waitFor();
        await page.waitForFunction(
          () =>
            !document.querySelector(".configuration-combination button")
              ?.disabled,
        );
        await page.evaluate(
          () =>
            new Promise((resolve) =>
              requestAnimationFrame(() => requestAnimationFrame(resolve)),
            ),
        );
      };
      // Contrast belongs to the stable native configuration identity, not to
      // a list position that can change after add/remove/project restoration.
      await selector.selectOption("0");
      await idle();
      await page
        .getByRole("button", {
          name: "Detector histogram settings",
          exact: true,
        })
        .click();
      await page
        .getByRole("combobox", { name: "Image scale", exact: true })
        .selectOption("log");
      await page.keyboard.press("Escape");
      const lower = page.getByRole("slider", {
        name: "Lower intensity handle",
        exact: true,
      });
      await lower.press("ArrowRight");
      const retainedLower = await lower.getAttribute("aria-valuenow");
      await selector.selectOption("1");
      await idle();
      assert.equal(
        await page
          .getByTestId("detector-canvas")
          .getAttribute("data-intensity-scale"),
        "linear",
      );
      await selector.selectOption("0");
      await idle();
      assert.equal(await lower.getAttribute("aria-valuenow"), retainedLower);
      assert.equal(
        await page
          .getByTestId("detector-canvas")
          .getAttribute("data-intensity-scale"),
        "log",
      );
      assert.equal(
        await page
          .getByRole("button", { name: "Auto intensity", exact: true })
          .getAttribute("aria-pressed"),
        "false",
      );
      await selector.selectOption("1");
      await idle();
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
        .getByRole("button", { name: "Combined cake", exact: true })
        .click();
      await page.waitForFunction(
        () =>
          document.querySelectorAll(
            '.configuration-combination button[aria-pressed="true"]',
          ).length === 2,
      );
      const combined = await invoke("state");
      assert.equal(
        combined.state.combination.backends.pattern,
        "Dioptrin · native Rust",
      );
      assert.equal(
        combined.state.combination.backends.cake,
        "Dioptrin · native Rust",
      );
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
      await page
        .getByRole("button", { name: "Save pattern", exact: true })
        .click();
      await page.waitForFunction(() => !document.querySelector(".spin"));
      assert.equal(
        await readFile(path.join(temp, `${name}-displayed.xy`), "utf8"),
        await readFile(path.join(temp, `${name}-combined.xy`), "utf8"),
      );
      // Exercise the actual cake-click payload against the Rust child: the
      // combined cake uses Q in Q mode; individual cakes and d-mode cakes use 2θ.
      await page.getByRole("button", { name: "Cake", exact: true }).click();
      for (const combinedCake of [true, false]) {
        if (!combinedCake) {
          await page
            .getByRole("button", { name: "Combined cake", exact: true })
            .click();
          await idle();
        }
        for (const [label, patternUnit] of [
          ["2θ", "2th_deg"],
          ["Q", "q_A^-1"],
          ["d", "d_A"],
        ]) {
          await page
            .getByRole("button", { name: `Pattern unit ${label}`, exact: true })
            .click();
          await idle();
          const cakeUnit =
            combinedCake && patternUnit === "q_A^-1" ? "q_A^-1" : "2th_deg";
          const beforeClick = await invoke("state");
          assert.equal(beforeClick.state.unit, patternUnit);
          assert.equal(beforeClick.cake.unit, cakeUnit);
          const canvas = page.getByTestId("cake-canvas");
          await canvas.press("f");
          const dims = await canvas.evaluate((el) => ({
            left: +el.dataset.plotLeft,
            top: +el.dataset.plotTop,
            width: +el.dataset.plotWidth,
            height: +el.dataset.plotHeight,
          }));
          const previousCalls = calls.filter(
            ([action]) => action === "validation_position",
          ).length;
          await canvas.click({
            position: {
              x: dims.left + 0.6 * dims.width,
              y: dims.top + 0.55 * dims.height,
            },
          });
          await page.waitForFunction(
            () =>
              document.querySelector('[data-testid="cake-canvas"]')?.dataset
                .clickX != null,
          );
          await idle();
          const inspected = await invoke("state");
          const positions = calls.filter(
            ([action]) => action === "validation_position",
          );
          assert.ok(
            positions.length > previousCalls,
            "Cake click must reach native inspection",
          );
          const payload = positions.at(-1)[1];
          assert.equal(payload.unit, cakeUnit);
          const wavelength = inspected.state.geometry.wavelength * 1e10;
          const theta =
            cakeUnit === "q_A^-1"
              ? (360 / Math.PI) *
                Math.asin((payload.x * wavelength) / (4 * Math.PI))
              : payload.x;
          assert.ok(Math.abs(inspected.linked.twoTheta - theta) < 1e-10);
          assert.ok(
            Math.abs(inspected.linked.azimuth - payload.azimuth) < 1e-10,
          );
          const radial =
            patternUnit === "q_A^-1"
              ? (4 * Math.PI * Math.sin((theta * Math.PI) / 360)) / wavelength
              : patternUnit === "d_A"
                ? wavelength / (2 * Math.sin((theta * Math.PI) / 360))
                : theta;
          assert.ok(Math.abs(inspected.linked.radial - radial) < 1e-9);
          assert.ok(
            Math.abs(
              Number(await canvas.getAttribute("data-linked-position")) -
                payload.x,
            ) < 1e-9,
          );
          assert.equal(await page.getByRole("dialog").count(), 0);
        }
      }
      await page
        .getByRole("button", { name: "Combined cake", exact: true })
        .click();
      await page
        .getByRole("button", { name: "Pattern unit 2θ", exact: true })
        .click();
      await idle();
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
      await openConfigurations();
      await toggle.click();
      await page.waitForFunction(
        () =>
          document.querySelector(
            '[aria-describedby="settings-configuration-description"]',
          )?.checked === false,
      );
      await page.waitForFunction(() => !document.querySelector(".spin"));
      const disabled = await invoke("state");
      assert.equal(disabled.state.combination.patterns, false);
      assert.equal(disabled.state.combination.cakes, false);
      await closeSettings.click();
      await assertBarHidden();
      await page.reload();
      await page.getByTestId("detector-canvas").waitFor();
      await assertBarHidden();
      await page.screenshot({
        path: path.join(artifacts, `${name}-configurations-hidden.png`),
      });
      await openConfigurations();
      assert.equal(await toggle.isChecked(), false);
      for (const [label, value] of Object.entries(customRules)) {
        assert.equal(
          await browsingSettings
            .getByRole("spinbutton", { name: label, exact: true })
            .inputValue(),
          value,
        );
      }
      // The opt-in remains readable in the smallest supported workspace.
      await page.setViewportSize({ width: 1000, height: 668 });
      await page.getByRole("tab", { name: "General", exact: true }).click();
      await page.getByRole("button", { name: "Larger", exact: true }).click();
      await page
        .getByRole("tab", { name: "Configurations", exact: true })
        .click();
      await toggle.scrollIntoViewIfNeeded();
      const card = toggle.locator("xpath=ancestor::section[1]");
      const bounds = await card.boundingBox();
      const toggleBounds = await toggle.boundingBox();
      assert.ok(toggleBounds.x >= bounds.x);
      assert.ok(toggleBounds.x + toggleBounds.width <= bounds.x + bounds.width);
      await page.screenshot({
        path: path.join(artifacts, `${name}-configuration-settings-small.png`),
      });
      const folderFilename = browsingSettings.getByRole("spinbutton", {
        name: "Filename number with folder",
        exact: true,
      });
      await folderFilename.scrollIntoViewIfNeeded();
      const settingsOverflow = await browsingSettings.evaluate((el) =>
        [...el.querySelectorAll("input,select,button")].some((control) => {
          const a = control.getBoundingClientRect(),
            b = el.getBoundingClientRect();
          return a.left < b.left - 1 || a.right > b.right + 1;
        }),
      );
      assert.equal(settingsOverflow, false);
      await page.screenshot({
        path: path.join(artifacts, `${name}-browsing-settings-small.png`),
      });
      await toggle.check();
      await browsingSettings
        .getByRole("button", { name: "Reset browsing", exact: true })
        .click();
      assert.equal(
        await browsingSettings
          .getByRole("checkbox", {
            name: "Advance filename with folder",
            exact: true,
          })
          .isChecked(),
        false,
      );
      assert.equal(await folderFilename.count(), 0);
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
        runtime: host.runtime,
        engine: host.engine,
        combinationBackends: combined.state.combination.backends,
        independentConfigurationContrast: true,
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
        groupedFileFolderBrowsing: true,
        mecFolderBrowsing: true,
        configurableBrowsingRulesPersist: true,
        dedicatedConfigurationsSettings: true,
        generalOmitsProcessingAndPatternNavigation: true,
        configurationToolbarAlwaysBrowsesAll: true,
        disableConfigurationsStopsCombination: true,
        combinedPatternAndCake: true,
        individualAndCombinedCakeClicks: ["2th_deg", "q_A^-1", "d_A"],
        combinationInConfigurationBarAcrossModes: true,
        combinedPatternExport: true,
        displayedPatternExportMatchesCombined: true,
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
