import { createHash } from "node:crypto";
// Reproducible, real-model design review. Never opens a visible window.
import assert from "node:assert/strict";
import { spawn, execFileSync } from "node:child_process";
import { createInterface } from "node:readline";
import { mkdir, copyFile, writeFile, readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import path from "node:path";
import { chromium, webkit } from "playwright";
import AxeBuilder from "@axe-core/playwright";

const root = fileURLToPath(new URL("../../", import.meta.url));
const uiPath =
  process.argv.find((x) => x.startsWith("--ui="))?.slice(5) ??
  path.join(root, "dioptas/desktop/ui/index.html");
const stage =
  process.argv.find((x) => x.startsWith("--stage="))?.split("=")[1] ?? "after";
const output = path.join(root, "desktop/artifacts/ui-audit", stage);
await mkdir(output, { recursive: true });
// Reset only this run's private action fixture; never user settings.
await writeFile(
  path.join(output, "commands.json"),
  JSON.stringify({ version: 1, commands: [] }),
);
await copyFile(
  path.join(root, "dioptas/tests/data/CeO2_Pilatus1M.poni"),
  path.join(root, "desktop/artifacts/calibration.poni"),
);
const host = spawn(
  path.join(root, ".venv/bin/python"),
  ["-u", "desktop/scripts/bridge_host.py"],
  {
    cwd: root,
    env: {
      ...process.env,
      OMP_NUM_THREADS: "2",
      DIOPTAS_TEST_RANDOM_SEED: "0",
      DIOPTAS_CUSTOM_COMMANDS_FILE: path.join(output, "commands.json"),
    },
    stdio: ["pipe", "pipe", "pipe"],
  },
);
let id = 0;
const pending = new Map(),
  logs = [],
  errors = [],
  checks = [],
  inventory = [],
  requests = [];
let fittedEvidence = null;
let failure = null;
const uiSha256 = createHash("sha256")
  .update(await readFile(uiPath))
  .digest("hex");
host.stderr.on("data", (b) => logs.push(b.toString()));
createInterface({ input: host.stdout }).on("line", (line) => {
  const m = JSON.parse(line),
    task = pending.get(m.id);
  if (task) {
    clearTimeout(task.timer);
    pending.delete(m.id);
    task.resolve(m.result);
  }
});
function invoke(action, payload = {}) {
  if (action === "open_calibration" && !payload.path)
    payload = {
      ...payload,
      path: path.join(root, "dioptas/tests/data/CeO2_Pilatus1M.poni"),
    };
  requests.push({ action, payload });
  return new Promise((resolve, reject) => {
    const identifier = ++id;
    const timer = setTimeout(() => reject(Error(`Timed out ${action}`)), 60000);
    pending.set(identifier, { resolve, timer });
    host.stdin.write(
      JSON.stringify({ id: identifier, action, payload }) + "\n",
    );
  });
}
const browser = await (
  process.argv.includes("--webkit") ? webkit : chromium
).launch({ headless: true });
const context = await browser.newContext({
  viewport: { width: 1440, height: 1000 },
  deviceScaleFactor: 1,
});
const page = await context.newPage();
page.on("pageerror", (e) => errors.push(e.message));
await page.exposeFunction("__invoke", invoke);
await page.addInitScript(() => {
  window.__pending = 0;
  window.pywebview = {
    api: {
      invoke: async (a, p) => {
        window.__pending++;
        try {
          return await window.__invoke(a, p);
        } finally {
          window.__pending--;
        }
      },
    },
  };
});
const ready = async () => {
  await page.waitForFunction(
    () =>
      document.querySelector(".app") &&
      !document.querySelector(".spin") &&
      !window.__pending,
    undefined,
    { timeout: 60000 },
  );
  await page.evaluate(
    () =>
      new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r))),
  );
  assert.deepEqual(await page.getByRole("alert").allTextContents(), []);
};
const click = async (name) => {
  await page.getByRole("button", { name, exact: true }).click();
  await ready();
};
const tab = async (name) => {
  await page.getByRole("tab", { name, exact: true }).click();
  await ready();
};
const capture = async (name, target = page) => {
  await ready();
  await target.mouse.move(2, 2);
  await target.screenshot({ path: path.join(output, `${name}.png`) });
  await writeFile(
    path.join(output, `${name}.aria.yml`),
    await target.locator("body").ariaSnapshot(),
  );
  const accessibility = await new AxeBuilder({ page: target })
    .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
    .analyze();
  const expandedPopupRelations = await target
    .locator('[aria-haspopup][aria-expanded="true"][aria-controls]')
    .evaluateAll((elements) =>
      elements.map((element) => ({
        trigger:
          element.getAttribute("aria-label") ?? element.textContent?.trim(),
        ids: (element.getAttribute("aria-controls") ?? "")
          .trim()
          .split(/\s+/)
          .map((id) => ({
            id,
            exists: !!document.getElementById(id),
            role:
              document.getElementById(id)?.getAttribute("role") ??
              document.getElementById(id)?.tagName.toLowerCase(),
          })),
      })),
    );
  if (stage !== "before")
    assert(
      expandedPopupRelations.every((relation) =>
        relation.ids.every((target) => target.exists),
      ),
      "Expanded popup controllers reference existing targets",
    );
  const toolbarReachability = await target
    .locator("body:not(:has(dialog[open])) .batch-series-toolbar button")
    .evaluateAll((buttons) =>
      buttons
        .filter(
          (button) =>
            button.getClientRects().length &&
            !button.closest('[inert], [aria-hidden="true"]'),
        )
        .map((button) => {
          const rect = button.getBoundingClientRect();
          let clipped =
            rect.left < 0 ||
            rect.top < 0 ||
            rect.right > innerWidth ||
            rect.bottom > innerHeight;
          for (
            let parent = button.parentElement;
            parent;
            parent = parent.parentElement
          ) {
            const style = getComputedStyle(parent),
              box = parent.getBoundingClientRect();
            if (style.display === "contents" || !parent.getClientRects().length)
              continue;
            if (/(hidden|auto|scroll|clip)/.test(style.overflowX))
              clipped ||=
                rect.left < box.left - 1 || rect.right > box.right + 1;
            if (/(hidden|auto|scroll|clip)/.test(style.overflowY))
              clipped ||=
                rect.top < box.top - 1 || rect.bottom > box.bottom + 1;
          }
          const hit = document.elementFromPoint(
            rect.left + rect.width / 2,
            rect.top + rect.height / 2,
          );
          return {
            name:
              button.getAttribute("aria-label") ?? button.textContent.trim(),
            clipped,
            hit: hit === button || button.contains(hit),
          };
        }),
    );
  if (stage !== "before")
    assert(
      toolbarReachability.every((item) => !item.clipped && item.hit),
      `${name}: Batch toolbar controls must be reachable: ${JSON.stringify(toolbarReachability.filter((item) => item.clipped || !item.hit))}`,
    );
  const batchAxisLabels = await target
    .locator("canvas[data-y-axis-label]")
    .evaluateAll((nodes) =>
      nodes.filter(node => node.getClientRects().length && !node.closest('[inert], [aria-hidden="true"]')).map((node) => ({
        label: node.dataset.yAxisLabel,
        width: Number(node.dataset.yAxisLabelWidth),
        available: Number(node.dataset.yAxisAvailable),
      })),
    );
  if (stage !== "before")
    assert(
      batchAxisLabels.every((axis) => axis.width <= axis.available + 1),
      `${name}: Batch axis title fits its available height`,
    );
  inventory.push({
    name,
    batchAxisLabels,
    toolbarReachability,
    expandedPopupRelations,
    manualAccessibilityChecks: accessibility.incomplete.map((v) => ({
      id: v.id,
      nodes: v.nodes.length,
      details: v.nodes.map((node) => ({
        target: node.target,
        summary: node.failureSummary,
      })),
    })),
    accessibility: accessibility.violations.map((v) => ({
      id: v.id,
      impact: v.impact,
      description: v.description,
      nodes: v.nodes.map((n) => ({
        target: n.target,
        summary: n.failureSummary,
      })),
    })),
    plotTypography: await target
      .locator("[data-plot-font-size]")
      .evaluateAll((elements) =>
        elements.map((element) => ({
          plot: element.dataset.testid,
          pixels: Number(element.dataset.plotFontSize),
        })),
      ),
    patternRenderers: await target
      .getByTestId("pattern-canvas")
      .evaluateAll((canvases) =>
        canvases.map((canvas) => ({
          requested: canvas.dataset.requestedCurveRenderer,
          actual: canvas.dataset.curveRenderer,
        })),
      ),
    controls: await target
      .locator("button,input,select,textarea")
      .evaluateAll((els) =>
        els
          .filter((e) => e.getClientRects().length)
          .map((e) => ({
            tag: e.tagName,
            label:
              e.getAttribute("aria-label") ||
              e.textContent.trim() ||
              e.labels?.[0]?.textContent.trim(),
            disabled: e.disabled,
            readOnly: e.readOnly ?? false,
          })),
      ),
    overflow: await target.evaluate(
      () => document.documentElement.scrollWidth > innerWidth,
    ),
  });
  if (stage !== "before")
    assert.equal(
      inventory.at(-1).overflow,
      false,
      `${name}: horizontal document overflow`,
    );
};
try {
  assert.equal((await invoke("example")).ok, true);
  await page.goto("file://" + uiPath);
  if (process.argv.includes("--focus=peer")) {
    await click("Load .poni");
    const { verifyPeerFindings } = await import("./ui_audit_peer.mjs");
    checks.push(
      ...(await verifyPeerFindings({
        page,
        ready,
        invoke,
        root,
        output,
        capture,
      })),
    );
  } else if (process.argv.includes("--focus=polish")) {
    await click("Load .poni");
    const { verifyPolish } = await import("./ui_audit_polish.mjs");
    checks.push(...(await verifyPolish({ page, ready, invoke, output })));
    await capture("polish-current");
  } else {
    await capture("calibration-image");
    await tab("Step 2: Pick rings");
    await capture("calibration-peaks");
    await tab("Step 3: Calibrate");
    await capture("calibration-fit");
    await click("Enter manually");
    await capture("manual-geometry");
    await page.keyboard.press("Escape");
    for (const [x, y, ring] of [
      [637, 564, 1],
      [671, 511, 2],
      [668, 703, 3],
      [350.5, 592.8, 1],
      [554.3, 367.9, 1],
    ])
      assert.equal((await invoke("pick_peak", { x, y, ring })).ok, true);
    const fitResult = await invoke("calibrate", { automatic: false });
    assert.equal(fitResult.ok, true);
    fittedEvidence = {
      fixture: "CeO2_Pilatus1M.tif",
      geometry: fitResult.state.geometry,
      rmsDegrees: fitResult.state.calibration.rmsDegrees,
      points: fitResult.state.calibration.picks.reduce(
        (n, g) => n + g.points.length,
        0,
      ),
      note: "Fit from measured-image peak seeds; no saved PONI supplied to the fit.",
    };
    await page.reload();
    await ready();
    await tab("Step 4: Validate");
    await capture("calibration-fitted");
    if (stage !== "before") {
      const fit = (await invoke("state")).state.calibration;
      await click("Enter manually");
      const manual = page.getByRole("dialog", {
        name: "Enter calibration manually",
        exact: true,
      });
      assert(
        await manual
          .getByRole("button", { name: "Apply geometry", exact: true })
          .isDisabled(),
      );
      const distance = manual.getByLabel("Manual distance", { exact: true });
      const exactDistance = await distance.inputValue();
      assert.equal(Number(exactDistance), fit.pyfai.dist * 1e3);
      await distance.fill(String(Number(exactDistance) + 0.001));
      await manual.getByRole("tab", { name: "Fit2D", exact: true }).click();
      assert(
        (await manual
          .getByLabel("Manual direct distance", { exact: true })
          .getAttribute("readonly")) !== null,
      );
      assert(
        await manual
          .getByRole("button", { name: "Apply geometry", exact: true })
          .isDisabled(),
      );
      await manual.getByRole("tab", { name: "pyFAI", exact: true }).click();
      assert.equal(
        Number(await distance.inputValue()),
        Number(exactDistance) + 0.001,
        "Comparing conventions preserves the pending draft",
      );
      await manual
        .getByRole("button", { name: "Reset geometry draft", exact: true })
        .click();
      assert.equal(await distance.inputValue(), exactDistance);
      assert(
        await manual
          .getByRole("button", { name: "Apply geometry", exact: true })
          .isDisabled(),
      );
      await page.keyboard.press("Escape");
      await ready();
      const unchanged = (await invoke("state")).state.calibration;
      assert.equal(unchanged.rmsDegrees, fit.rmsDegrees);
      assert.equal(unchanged.geometrySource, "fitted");
      checks.push(
        "Manual geometry keeps exact values, prevents no-op provenance loss and preserves drafts during convention comparisons",
      );
      await click("Mask");
      await click("Invert");
      await click("Calibration");
      await click("Undo");
      const restored = (await invoke("state")).state.calibration;
      assert.equal(
        restored.rmsDegrees,
        fit.rmsDegrees,
        "Undo of a mask from Calibration preserves the fitted RMS",
      );
      assert.equal(restored.fitDirty, fit.fitDirty);
      checks.push(
        "Shared history chooses the action path: mask Undo in Calibration preserves fit diagnostics",
      );
    }
    await click("Load .poni");
    await tab("Step 4: Validate");
    await capture("calibration-validate");
    await click("Detector histogram settings");
    await capture("detector-display");
    if (stage !== "before") {
      const d = page.getByRole("dialog", { name: "Detector display settings" });
      assert(
        await d.evaluate((e) => e.contains(document.activeElement)),
        "Histogram dialog receives focus",
      );
      const focusable = d.locator("button,input,select");
      await focusable.last().focus();
      await page.keyboard.press("Tab");
      assert(
        await d.evaluate((e) => e.contains(document.activeElement)),
        "Tab stays in histogram dialog",
      );
      await focusable.first().focus();
      await page.keyboard.press("Shift+Tab");
      assert(
        await focusable.last().evaluate((e) => e === document.activeElement),
        "Shift+Tab wraps to the last dialog control",
      );
      checks.push(
        "Native modal histogram: initial focus, Tab and Shift+Tab containment",
      );
    }
    await page.keyboard.press("Escape");
    await ready();
    if (stage !== "before") {
      assert(
        await page
          .getByRole("button", { name: "Detector histogram settings" })
          .evaluate((e) => document.activeElement === e),
        "Dialog returns focus to trigger",
      );
      checks.push("Histogram Escape and focus restoration");
    }
    await click("Mask");
    await capture("mask");
    await click("Integration");
    for (const t of [
      "Image",
      "Pattern",
      "Overlay",
      "Phase",
      "Background",
      "Corrections",
    ]) {
      await tab(t);
      await capture("integration-" + t.toLowerCase());
    }
    await tab("Overlay");
    await click("As Overlay");
    await capture("integration-overlay-populated");
    await click("Clear overlays");
    await capture("integration-overlay-confirm");
    await page.keyboard.press("Escape");
    await ready();
    if (stage !== "before") {
      assert(
        await page
          .getByRole("button", { name: "Clear overlays", exact: true })
          .evaluate((e) => e === document.activeElement),
      );
      checks.push(
        "Destructive overlay confirmation: Escape cancels and restores trigger focus",
      );
    }
    await click("Color overlays by scale");
    await capture("integration-overlay-colors");
    await page.keyboard.press("Escape");
    await ready();
    await tab("Phase");
    await click("Add phase…");
    await click("Edit selected Phase");
    await capture("phase-editor");
    await page.keyboard.press("Escape");
    await ready();
    await click("Browse EoS Material Database");
    await page.waitForFunction(
      () =>
        document
          .querySelector(".phase-database-result-count")
          ?.textContent.trim() !== "…",
    );
    await capture("phase-database");
    await page.keyboard.press("Escape");
    await ready();
    await click("Settings");
    for (const t of [
      "General",
      "Integration",
      "Keyboard shortcuts",
      "Custom actions",
    ]) {
      await tab(t);
      await capture("settings-" + t.toLowerCase().replaceAll(" ", "-"));
    }
    await click("Add action");
    await page.getByLabel("Button name", { exact: true }).fill("Inspect");
    await page
      .getByLabel("Program or executable script", { exact: true })
      .fill("/usr/bin/true");
    await click("Save action");
    await page
      .locator(".custom-command-edit")
      .filter({ hasText: "Inspect" })
      .click();
    await capture("settings-custom-action-editor");
    await page.getByRole("button", { name: /^Change action icon:/ }).click();
    await capture("settings-custom-action-icons");
    await page.keyboard.press("Escape");
    await page.keyboard.press("Escape");
    await ready();
    await tab("Image");
    const series = path.join(output, "series");
    await mkdir(series, { recursive: true });
    execFileSync(path.join(root, ".venv/bin/python"), [
      "-c",
      `import sys,pathlib,fabio
+data=fabio.open(sys.argv[1]).data.astype('float32')
+for i in range(6): fabio.tifimage.TifImage(data=data*(i+1)).write(str(pathlib.Path(sys.argv[2])/f'series_{i+1}.tif'))`.replaceAll(
        "\n+",
        "\n",
      ),
      path.join(root, "dioptas/tests/data/CeO2_Pilatus1M.tif"),
      series,
    ]);
    const paths = Array.from({ length: 6 }, (_, i) =>
      path.join(series, `series_${i + 1}.tif`),
    );
    await page.evaluate((paths) => {
      const original = window.__invoke;
      window.__invoke = (a, p) =>
        original(a, a === "open_image" && p?.multiple ? { ...p, paths } : p);
    }, paths);
    const popupPromise = context.waitForEvent("page");
    await click("Load image…");
    const child = await popupPromise;
    await child.waitForLoadState();
    await child.getByTestId("batch-heatmap").waitFor();
    await child.waitForFunction(
      () =>
        document
          .querySelector('[aria-label="Batch series"]')
          ?.getAttribute("aria-busy") === "false",
    );
    await capture("batch-detached", child);
    if (stage !== "before") {
      const overview = child.getByTestId("batch-heatmap");
      await overview.focus();
      for (const [key, index] of [
        ["ArrowUp", 1],
        ["ArrowDown", 0],
        ["End", 5],
        ["Home", 0],
      ]) {
        await child.keyboard.press(key);
        await child.waitForFunction(
          (index) =>
            document.querySelector('[aria-label="Batch series"]')?.dataset
              .selectedFrame === String(index) &&
            document
              .querySelector('[aria-label="Batch series"]')
              ?.getAttribute("aria-busy") === "false",
          index,
        );
        assert.equal((await invoke("state")).batch.selected, index);
      }
      await child.keyboard.press("f");
      checks.push(
        "Batch overview: ↑/↓/Home/End select actual frames; F restores view",
      );
    }
    await child.getByRole("tab", { name: "Files", exact: true }).click();
    await capture("batch-files", child);
    await child.getByRole("tab", { name: "2D", exact: true }).click();
    await child
      .getByRole("button", { name: "Normalization settings", exact: true })
      .click();
    await capture("batch-normalization", child);
    await child.keyboard.press("Escape");
    await child
      .getByRole("button", { name: "Dock batch below image", exact: true })
      .click();
    await ready();
    await page.locator(".batch-docked").waitFor();
    await capture("batch-docked");
    if (stage !== "before") {
      const view = await page
        .locator(".batch-docked .batch-2d-view")
        .boundingBox();
      const image = await page
        .locator(".batch-docked .batch-overview-image")
        .boundingBox();
      assert(
        image.width >= view.width - 8,
        "Docked Batch fills the width alongside its independent histogram",
      );
      checks.push(
        "Batch heatmap fills the dock; quantitative legend sits below the plot",
      );
    }

    if (stage !== "before") {
      const batchTabs = page.getByRole("tablist", {
        name: "Batch view",
        exact: true,
      });
      await batchTabs.getByRole("tab", { name: "2D", exact: true }).focus();
      await page.keyboard.press("ArrowRight");
      assert.equal(
        await batchTabs
          .getByRole("tab", { name: "Options", exact: true })
          .getAttribute("aria-selected"),
        "true",
      );
      assert(
        await batchTabs
          .getByRole("tab", { name: "Options", exact: true })
          .evaluate((e) => e === document.activeElement),
      );
      checks.push("Batch tabs: arrows and actual roving focus");
    }
    await click("Map");
    await click("Load map calibration");
    await page
      .locator(".map-controls")
      .getByRole("button", { name: "Load images…", exact: true })
      .click();
    await ready();
    for (const t of ["Points", "Grid", "Layers"]) {
      await tab(t);
      await capture("map-" + t.toLowerCase());
    }
    await tab("Points");
    await click("Map settings");
    await capture("map-settings");
    await page.keyboard.press("Escape");
    await ready();
    for (const large of [false, true]) {
      await page.setViewportSize({ width: 1000, height: 760 });
      await click("Settings");
      await tab("General");
      await click(large ? "Larger" : "Standard");
      await page.keyboard.press("Escape");
      await capture("map-compact" + (large ? "-large" : ""));
      if (stage !== "before") {
        const range = await page
          .locator(".color-scale-range")
          .evaluate((element) => {
            const children = [...element.children].map((child) =>
              child.getBoundingClientRect(),
            );
            return children.map((rect) => ({
              x: rect.x,
              y: rect.y,
              width: rect.width,
              height: rect.height,
            }));
          });
        assert(
          range[0].x < range[1].x &&
            range[2].x >= range[1].x + range[1].width - 1,
        );
        assert(
          Math.abs(
            range[0].y +
              range[0].height / 2 -
              (range[2].y + range[2].height / 2),
          ) < 2,
          "Low and high limits remain beside their color-bar ends",
        );
      }
      const suffix = large ? "-large" : "";
      await click("Calibration");
      await tab("Step 4: Validate");
      await capture("calibration-compact" + suffix);
      await click("Enter manually");
      await capture("manual-geometry-compact" + suffix);
      await page.keyboard.press("Escape");
      await click("Mask");
      await capture("mask-compact" + suffix);
      await click("Integration");
      await tab("Image");
      await capture("integration-compact" + suffix);
      await tab("Phase");
      await click("Edit selected Phase");
      await capture("phase-editor-compact" + suffix);
      await page.keyboard.press("Escape");
      await ready();
      await tab("Image");
      const dock = page.locator(".batch-docked");
      await dock.getByRole("tab", { name: "Options", exact: true }).click();
      await dock
        .getByRole("button", { name: "Normalization settings", exact: true })
        .click();
      await capture("batch-normalization-compact" + suffix);
      const popup = page.getByRole("dialog", {
        name: "Normalization settings",
        exact: true,
      });
      const popupBox = await popup.boundingBox();
      if (stage !== "before")
        assert(
          popupBox.x >= 0 &&
            popupBox.y >= 0 &&
            popupBox.x + popupBox.width <= 1001 &&
            popupBox.y + popupBox.height <= 761,
          "Normalization popup remains inside compact viewport",
        );
      await page.keyboard.press("Escape");
      await dock.getByRole("tab", { name: "2D", exact: true }).click();
      await capture("batch-compact" + suffix);
      if (stage !== "before") {
        const fonts = await page
          .locator("[data-plot-font-size]")
          .evaluateAll((elements) =>
            elements.map((element) => Number(element.dataset.plotFontSize)),
          );
        assert(
          fonts.length && fonts.every((size) => size === (large ? 16 : 14)),
          "Canvas labels follow the selected text size",
        );
      }
      await click("Settings");
      await tab("Custom actions");
      await page
        .locator(".custom-command-edit")
        .filter({ hasText: "Inspect" })
        .click();
      await capture("settings-actions-compact" + suffix);
      await page.getByRole("button", { name: /^Change action icon:/ }).click();
      await capture("settings-icons-compact" + suffix);
      await page.keyboard.press("Escape");
      await page.keyboard.press("Escape");
      await click("Map");
    }
    if (stage !== "before") {
      checks.push(
        "All modes, editors, action menus and Batch normalization fit 1000×760 at both text sizes; canvas labels switch from 14 to 16 px",
      );
      checks.push("Compact Map color limits stay beside their color-bar ends");
      await page.setViewportSize({ width: 1440, height: 1000 });
      await click("Keyboard shortcuts and gestures");
      await capture("shortcut-help");
      await page.keyboard.press("Escape");
      const { verifyDraftsAndFeedback } =
        await import("./ui_audit_feedback.mjs");
      checks.push(
        ...(await verifyDraftsAndFeedback({ page, ready, invoke, output })),
      );
      const { verifyShortcuts } = await import("./ui_audit_keyboard.mjs");
      checks.push(
        ...(await verifyShortcuts({ page, ready, invoke, requests, root })),
      );
      const { verifyPeerFindings } = await import("./ui_audit_peer.mjs");
      checks.push(
        ...(await verifyPeerFindings({
          page,
          ready,
          invoke,
          root,
          output,
          capture,
        })),
      );
      const { verifyPolish } = await import("./ui_audit_polish.mjs");
      checks.push(...(await verifyPolish({ page, ready, invoke, output })));
    }
  }
  assert.deepEqual(errors, []);
} catch (error) {
  failure = {
    message: error instanceof Error ? error.message : String(error),
    stack: error instanceof Error ? error.stack : undefined,
  };
  await page
    .screenshot({ path: path.join(output, "failure.png") })
    .catch(() => {});
  await page
    .locator("body")
    .ariaSnapshot()
    .then((value) => writeFile(path.join(output, "failure.aria.yml"), value))
    .catch(() => {});
  throw error;
} finally {
  await writeFile(
    path.join(output, "report.json"),
    JSON.stringify(
      {
        stage,
        completed: failure === null,
        failure,
        peakSearchRandomSeed: 0,
        uiSha256,
        baselineRef: "b418d66b",
        fittedEvidence,
        checks,
        inventory,
        errors,
      },
      null,
      2,
    ),
  );
  await writeFile(path.join(output, "host.log"), logs.join(""));
  await browser.close();
  host.stdin.end();
  for (const p of pending.values()) clearTimeout(p.timer);
}
console.log(
  JSON.stringify({ stage, screenshots: inventory.length, checks, errors }),
);
