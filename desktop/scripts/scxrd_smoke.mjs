import assert from "node:assert/strict";
import fs from "node:fs/promises";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { chromium, webkit } from "playwright";
import AxeBuilder from "@axe-core/playwright";
import { nativeClient, root } from "./native_backend_client.mjs";
const folder = path.join(root, "desktop/artifacts/scxrd-gui");
await fs.mkdir(folder, { recursive: true });
const fixture = path.join(root, "desktop/artifacts/scxrd-fixture");
const files = (await fs.readdir(fixture))
  .filter((f) => f.endsWith(".tif"))
  .sort()
  .map((f) => path.join(fixture, f));
const reports = [];
for (const [engine, type] of Object.entries({ chromium, webkit })) {
  const native = nativeClient();
  const browser = await type.launch({ headless: true });
  const errors = [];
  const calls = [];
  const axeChecks = [];
  let page;
  try {
    const context = await browser.newContext({
      viewport: { width: 1500, height: 1000 },
    });
    page = await context.newPage();
    page.setDefaultTimeout(45000);
    page.on("pageerror", (e) => errors.push(e.message));
    await page.exposeFunction(
      "__nativeInvoke",
      async (action, payload = {}) => {
        calls.push({ action, payload });
        if (action === "scxrd_load" && !payload.paths)
          payload = { ...payload, paths: files };
        if (
          action === "scxrd_file" &&
          !payload.path &&
          payload.operation !== "use_calibration"
        )
          payload = {
            ...payload,
            path:
              payload.operation === "calibration"
                ? path.join(fixture, "detector.poni")
                : path.join(folder, `${engine}.scxrd.json`),
          };
        const r = await native.invoke(action, payload);
        return native.browserResult(r);
      },
    );
    await page.addInitScript(() => {
      window.pywebview = {
        api: {
          invoke: async (a, p) => {
            const r = await window.__nativeInvoke(a, p);
            if (a === "scxrd_levels") window.__lastScLevelMode = p.mode;
            return r;
          },
        },
      };
    });
    await page.goto(
      pathToFileURL(path.join(root, "dioptas/desktop/ui/index.html")).href,
    );
    await page
      .getByRole("button", { name: "Single Crystal XRD", exact: true })
      .click();
    await page.locator(".sc-empty").waitFor();
    await page.waitForFunction(
      () => document.querySelector(".sc-empty button")?.disabled === false,
    );
    await page.getByTestId("sc-primary-action").waitFor();
    await page.screenshot({ path: path.join(folder, `${engine}-empty.png`) });
    const panel = page.getByRole("complementary", {
      name: "Single-crystal workflow controls",
    });
    await panel
      .getByRole("button", { name: "Load frames…", exact: true })
      .click();
    await page.getByLabel("Rotation frame", { exact: true }).waitFor();
    await page
      .getByLabel("Single-crystal workflow", { exact: true })
      .selectOption("summation");
    await page.getByLabel("First exposure start").fill("");
    await page.getByLabel("First exposure start").pressSequentially("-40");
    assert.equal(
      await page.getByLabel("First exposure start").inputValue(),
      "-40",
    );
    await page.getByLabel("Rotation step", { exact: false }).fill("0.5");
    await page.getByLabel("Exposure width").fill("0.5");
    await page
      .getByRole("checkbox", {
        name: "I checked the frame order, angles, axis and count gain.",
      })
      .check();
    await page
      .getByRole("button", { name: "Apply settings", exact: true })
      .click();
    await page
      .getByRole("button", { name: "Load .poni…", exact: true })
      .click();
    await page.getByRole("tab", { name: "Peaks", exact: true }).click();
    await page.getByRole("button", { name: "Run peaks", exact: true }).click();
    await page
      .getByRole("tab", { name: "Cell", exact: true, selected: true })
      .waitFor();
    await page.getByRole("button", { name: "Run cell", exact: true }).click();
    await page
      .getByRole("button", { name: "Select cell 1", exact: true })
      .waitFor();
    await page
      .getByRole("button", { name: "Select cell 1", exact: true })
      .isEnabled();
    await page.getByTestId("sc-primary-action").waitFor();
    await page.screenshot({
      path: path.join(folder, `${engine}-cell-decision.png`),
    });
    await page
      .getByRole("button", { name: "Select cell 1", exact: true })
      .click();
    await page
      .getByRole("button", { name: "Run to next decision", exact: true })
      .click();
    await page
      .getByRole("tab", { name: "Structure", exact: true, selected: true })
      .waitFor();
    const snap = await native.invoke("scxrd_snapshot", {});
    assert.equal(snap.scxrd.error, null);
    assert.ok(snap.scxrd.usableReflections > 25);
    assert.ok(snap.scxrd.scaling?.families > 0);
    await page.getByRole("tab", { name: "Peaks", exact: true }).click();
    await page
      .getByRole("button", { name: "Inspect track 1", exact: true })
      .click();
    const beforeFrame = (await native.invoke("scxrd_snapshot")).scxrd.frame;
    await page
      .getByRole("button", { name: "Next rotation frame", exact: true })
      .click();
    await page.waitForFunction(
      () =>
        Number(document.querySelector('[aria-label="Rotation frame"]').value) >
        1,
    );
    // Unapplied scientific settings remain a draft across mode switches.
    await page.getByLabel("Peak threshold").fill("6");
    await page
      .getByRole("button", { name: "Integration", exact: true })
      .click();
    await page
      .getByRole("button", { name: "Single Crystal XRD", exact: true })
      .click();
    assert.equal(await page.getByLabel("Peak threshold").inputValue(), "6");
    await page
      .getByRole("button", { name: "Reset draft", exact: true })
      .click();
    // Private SC history, explicit exclusion and keyboard frame navigation.
    await page.getByRole("tab", { name: "Peaks", exact: true }).click();
    await page
      .getByRole("checkbox", { name: "Exclude track 1", exact: true })
      .check();
    await page.waitForFunction(
      () =>
        document.querySelector('[aria-label="Undo single-crystal edit"]')
          ?.disabled === false,
    );
    await page
      .getByRole("button", { name: "Undo single-crystal edit", exact: true })
      .click();
    await page.waitForFunction(
      () =>
        document.querySelector('[aria-label="Exclude track 1"]')?.checked ===
        false,
    );
    const keyFrame = (await native.invoke("scxrd_snapshot")).scxrd.frame;
    await page.locator(".sc-content").focus();
    await page.keyboard.press("PageDown");
    await page.waitForFunction(
      (value) =>
        Number(
          document.querySelector('[aria-label="Rotation frame"]').value,
        ) === value,
      keyFrame + 2,
    );
    const canvas = page.getByTestId("detector-canvas");
    const canvasBox = await canvas.boundingBox();
    const pixelCalls = calls.filter((c) => c.action === "pixel").length;
    await page.mouse.move(
      canvasBox.x + canvasBox.width * 0.51,
      canvasBox.y + canvasBox.height * 0.51,
    );
    await page.waitForFunction(() =>
      document
        .querySelector('[data-testid="mouse-readout"]')
        ?.textContent?.includes("ω"),
    );
    assert.equal(
      calls.filter((c) => c.action === "pixel").length,
      pixelCalls,
      "SC hover never samples the powder image",
    );
    await page
      .getByRole("button", { name: "Detector histogram settings", exact: true })
      .click();
    await page
      .getByLabel("Auto intensity mode", { exact: true })
      .selectOption("minmax");
    await page.waitForFunction(() => window.__lastScLevelMode === "minmax");
    // Restore the normal robust display after exercising min/max controls.
    await page
      .getByLabel("Auto intensity mode", { exact: true })
      .selectOption("percentile");
    await page.keyboard.press("Escape");
    await page.getByRole("tab", { name: "Background", exact: true }).click();
    await page
      .getByRole("button", { name: "Pick two corners on image", exact: true })
      .click();
    await page.mouse.click(
      canvasBox.x + canvasBox.width * 0.35,
      canvasBox.y + canvasBox.height * 0.35,
    );
    await page
      .getByText("Click the opposite corner.", { exact: false })
      .waitFor();
    await page.keyboard.press("Escape");
    await page
      .getByRole("button", { name: "Pick two corners on image", exact: true })
      .waitFor();
    await page
      .getByRole("button", { name: "Pick two corners on image", exact: true })
      .click();
    await page.mouse.click(
      canvasBox.x + canvasBox.width * 0.35,
      canvasBox.y + canvasBox.height * 0.35,
    );
    await page.mouse.move(
      canvasBox.x + canvasBox.width * 0.45,
      canvasBox.y + canvasBox.height * 0.45,
    );
    await page.screenshot({
      path: path.join(folder, `${engine}-mask-preview.png`),
    });
    await page.mouse.click(
      canvasBox.x + canvasBox.width * 0.45,
      canvasBox.y + canvasBox.height * 0.45,
    );
    await page
      .getByRole("button", { name: "Remove region 1", exact: true })
      .waitFor();
    await page
      .getByRole("button", { name: "Undo single-crystal edit", exact: true })
      .click();
    await page.waitForFunction(
      () => !document.querySelector('[aria-label="Remove region 1"]'),
    );
    await page
      .getByRole("button", { name: "Finish region picking", exact: true })
      .click();
    for (const [size, width, height, large] of [
      ["wide", 1500, 1000, false],
      ["compact", 1050, 760, false],
      ["large", 1100, 850, true],
    ]) {
      await page.setViewportSize({ width, height });
      await page.evaluate(
        (large) =>
          document
            .querySelector(".app")
            .setAttribute("data-text-size", large ? "large" : "normal"),
        large,
      );
      for (const tab of [
        "Frames",
        "Background",
        "Peaks",
        "Cell",
        "Geometry",
        "Intensities",
        "Scaling",
        "Structure",
        "Export",
      ]) {
        await page.getByRole("tab", { name: tab, exact: true }).click();
        await page.locator(".sc-content").evaluate((e) => (e.scrollTop = 0));
        await page.waitForFunction(
          (name) =>
            document.querySelector(".sc-steps [aria-selected=true]")
              ?.textContent === name,
          tab,
        );
        await page.evaluate(
          () =>
            new Promise((r) =>
              requestAnimationFrame(() => requestAnimationFrame(r)),
            ),
        );
        await page.screenshot({
          path: path.join(folder, `${engine}-${size}-${tab.toLowerCase()}.png`),
        });
        const box = await page.locator(".sc-panel").boundingBox();
        assert.ok(
          box && box.x + box.width <= width + 1 && box.y + box.height <= height,
          "Panel remains in workspace",
        );
        const action = await page
          .getByTestId("sc-primary-action")
          .boundingBox();
        assert.ok(
          action && action.y + action.height <= height,
          "Primary action is reachable",
        );
        if (size === "wide") {
          const tables = await page
            .locator(".sc-content table")
            .evaluateAll((tables) =>
              tables.map((table) => ({
                headers: table.querySelectorAll("thead th").length,
                rows: [...table.querySelectorAll("tbody tr")].map(
                  (row) => row.children.length,
                ),
              })),
            );
          for (const table of tables)
            assert.ok(
              table.rows.every((cells) => cells === table.headers),
              `${engine}/${tab}: every data cell has a corresponding column header`,
            );
          const check = await new AxeBuilder({ page })
            .include(".sc-workspace")
            .withTags(["wcag2a", "wcag2aa"])
            .analyze();
          axeChecks.push({ tab, violations: check.violations });
          assert.deepEqual(
            check.violations,
            [],
            `${engine}/${tab}: no WCAG A/AA violations`,
          );
        }
        const overflow = await page
          .locator(".sc-panel")
          .evaluate((e) => e.scrollWidth > e.clientWidth + 1);
        assert.equal(
          overflow,
          false,
          `${engine}/${size}/${tab}: no outer horizontal overflow`,
        );
      }
    }
    await page.getByRole("tab", { name: "Export", exact: true }).click();
    await page.getByTestId("sc-primary-action").click();
    await page.waitForFunction(
      () =>
        document.querySelector('[data-testid="sc-primary-action"]')
          ?.disabled === false,
    );
    assert.ok(
      (await fs.stat(path.join(folder, `${engine}.scxrd.json`))).size > 0,
    );
    await page.getByRole("tab", { name: "Structure", exact: true }).click();
    await page.getByPlaceholder("Mg Si O", { exact: true }).fill("Si");
    await page.getByLabel("Search budget", { exact: false }).fill("2");
    await page
      .getByRole("button", { name: "Apply settings", exact: true })
      .click();
    await page
      .getByRole("button", { name: "Run to next decision", exact: true })
      .click();
    await page.getByText("Candidate R1", { exact: true }).waitFor();
    await page.getByTestId("sc-primary-action").waitFor();
    const candidate = (await native.invoke("scxrd_snapshot")).scxrd.structure;
    assert.equal(candidate.mode, "isotropic");
    assert.ok(Number.isFinite(candidate.r1));
    await page.screenshot({
      path: path.join(folder, `${engine}-structure-candidate.png`),
    });
    const accessibility = await new AxeBuilder({ page })
      .include(".sc-workspace")
      .withTags(["wcag2a", "wcag2aa"])
      .analyze();
    await fs.writeFile(
      path.join(folder, `${engine}-axe.json`),
      JSON.stringify(accessibility.violations, null, 2),
    );
    await fs.writeFile(
      path.join(folder, `${engine}-axe-stages.json`),
      JSON.stringify(axeChecks, null, 2),
    );
    assert.deepEqual(errors, []);
    reports.push({
      engine,
      ok: true,
      frames: snap.scxrd.frames,
      tracks: snap.scxrd.trackCount,
      reflections: snap.scxrd.usableReflections,
      tabLayouts: 27,
      accessibilityStages: axeChecks.length,
      accessibilityViolations: accessibility.violations.map((v) => ({
        id: v.id,
        impact: v.impact,
        nodes: v.nodes.length,
      })),
      draftPreserved: true,
    });
  } catch (error) {
    if (page) {
      await page.screenshot({
        path: path.join(folder, `${engine}-failure.png`),
      });
      const report = page.getByText("Error report and recent steps", {
        exact: true,
      });
      if (await report.count()) await report.click();
      await fs.writeFile(
        path.join(folder, `${engine}-failure.txt`),
        await page.locator("body").innerText(),
      );
    }
    throw error;
  } finally {
    await browser.close();
    await native.close();
    await fs.writeFile(
      path.join(folder, `${engine}-calls.json`),
      JSON.stringify(calls, null, 2),
    );
  }
}
await fs.writeFile(
  path.join(folder, "report.json"),
  JSON.stringify(reports, null, 2),
);
console.log(JSON.stringify(reports, null, 2));
