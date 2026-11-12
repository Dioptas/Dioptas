// Optional local-data regression: recipe replay, protocol interaction and Stop.
// Usage: node scripts/scxrd_protocol_gui.mjs RECIPE NEW_OUTPUT_DIRECTORY
import assert from "node:assert/strict";
import fs from "node:fs/promises";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { chromium } from "playwright";
import AxeBuilder from "@axe-core/playwright";
import { nativeClient, root } from "./native_backend_client.mjs";

const recipe = path.resolve(process.argv[2]);
const fresh = process.env.DIOPTAS_SCXRD_FRESH_SETUP === "1";
const source = process.env.DIOPTAS_SCXRD_MEASURED_DIR;
const folder = path.resolve(process.argv[3]);
await fs.mkdir(folder); // Preserve earlier evidence.
const native = nativeClient({ timeoutMs: 600000 });
const browser = await chromium.launch({ headless: true });
const errors = [],
  layouts = [],
  accessibility = [];
const calls = [];
const verified = {};
async function invoke(action, payload = {}) {
  const r = await native.invoke(action, payload);
  assert.equal(r.ok, true, r.error);
  return r;
}
try {
  let replay;
  async function archive(replay) {
    assert.equal(replay.scxrd.error, null, replay.scxrd.error);
    assert.equal(replay.scxrd.usableReflections, 4125);
    assert.ok(
      Math.abs(replay.scxrd.scaling.rInt - 0.03936486775018062) < 1e-10,
    );
    await fs.writeFile(
      path.join(folder, "replay.json"),
      JSON.stringify(replay.scxrd, null, 2),
    );
    const rows = [];
    for (let offset = 0; offset < replay.scxrd.reflectionCount; offset += 200)
      rows.push(
        ...(await invoke("scxrd_table", { kind: "reflections", offset })).scxrd
          .reflections,
      );
    await fs.writeFile(
      path.join(folder, "reduction.json"),
      JSON.stringify({ ...replay.scxrd, reflections: rows }),
    );
    await invoke("scxrd_file", {
      operation: "audit",
      path: path.join(folder, "stages.npz"),
    });
    const search = await invoke("scxrd_run", { stage: 6 });
    assert.equal(search.scxrd.error, null, search.scxrd.error);
    await fs.writeFile(
      path.join(folder, "search.json"),
      JSON.stringify(search.scxrd.structure, null, 2),
    );
    assert.ok(
      search.scxrd.structure.r1 < 0.05,
      "Matched optimized protocol should recover its candidate",
    );
    await invoke("scxrd_file", {
      operation: "cif",
      path: path.join(folder, "candidate.cif"),
    });
    await invoke("scxrd_table", { kind: "reflections", offset: 0 });
    await invoke("scxrd_file", {
      operation: "save",
      path: path.join(folder, "verified.scxrd.json"),
    });
  }
  if (!fresh) {
    await invoke("scxrd_file", { operation: "open", path: recipe });
    replay = await invoke("scxrd_run", { stage: 5 });
    await archive(replay);
    await invoke("scxrd_frame", { frame: 60 });
  }
  const context = await browser.newContext({
    viewport: { width: 1500, height: 1000 },
  });
  const page = await context.newPage();
  page.setDefaultTimeout(45000);
  page.on("pageerror", (e) => errors.push(e.message));
  await page.exposeFunction("__nativeInvoke", async (action, payload = {}) => {
    calls.push({ action, payload });
    if (fresh && action === "scxrd_load" && !payload.path)
      payload = { ...payload, path: path.join(source, "eiger_0000.h5") };
    if (
      fresh &&
      action === "scxrd_file" &&
      payload.operation === "calibration" &&
      !payload.path
    )
      payload = {
        ...payload,
        path: path.join(source, "CeO2_20240620_1849_dioptas.poni"),
      };

    if (
      action === "scxrd_file" &&
      !payload.path &&
      payload.operation === "protocol_save"
    )
      payload = {
        ...payload,
        path: path.join(folder, "effective-protocol.json"),
      };
    return native.browserResult(await invoke(action, payload));
  });
  await page.addInitScript(() => {
    window.pywebview = {
      api: {
        invoke: async (a, p) => {
          const r = await window.__nativeInvoke(a, p);
          if (a === "scxrd_file") window.__scLastFile = p.operation;
          if (a === "scxrd_table" && p.filter) window.__scLastFilter = p.filter;
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
  await page.getByTestId("sc-primary-action").waitFor();
  if (fresh) {
    assert.ok(source, "DIOPTAS_SCXRD_MEASURED_DIR is required for fresh setup");
    const panel = page.getByRole("complementary", {
      name: "Single-crystal workflow controls",
    });
    await panel
      .getByRole("button", { name: "Load frames…", exact: true })
      .click();
    await page.getByLabel("Rotation frame", { exact: true }).waitFor();
    await page
      .getByRole("button", { name: "Use bundled v29", exact: true })
      .click();
    await page
      .getByRole("button", { name: "Load .poni…", exact: true })
      .click();
    await page.getByRole("tab", { name: "Geometry", exact: true }).click();
    for (const [label, value] of [
      ["a / Å", "8.8101"],
      ["b / Å", "5.1824"],
      ["c / Å", "18.2288"],
    ]) {
      await page.getByLabel(label, { exact: true }).fill(value);
      await page.getByLabel(label, { exact: true }).press("Tab");
    }
    await page.screenshot({
      path: path.join(folder, "fresh-supplied-cell.png"),
    });
    await page
      .getByRole("button", { name: "Apply settings", exact: true })
      .click();
    await page.getByRole("tab", { name: "Scaling", exact: true }).click();
    await page
      .getByLabel("Supplied space-group number / 1–230", { exact: true })
      .fill("61");
    await page
      .getByLabel("Supplied space-group number / 1–230", { exact: true })
      .press("Tab");
    await page
      .getByRole("button", { name: "Apply settings", exact: true })
      .click();
    await page.getByRole("tab", { name: "Structure", exact: true }).click();
    await page.getByPlaceholder("Mg Si O", { exact: true }).fill("Mg Si O");
    await page
      .getByRole("button", { name: "Apply settings", exact: true })
      .click();
    await page.getByRole("tab", { name: "Background", exact: true }).click();
    await page.getByLabel("DAC half opening / °", { exact: true }).fill("36");
    await page.getByLabel("DAC half opening / °", { exact: true }).press("Tab");
    await page
      .getByRole("button", { name: "Apply settings", exact: true })
      .click();
    await page.getByRole("tab", { name: "Frames", exact: true }).click();
    await page
      .getByRole("button", { name: "Inspect protocol", exact: true })
      .click();
    const inspected = JSON.parse(
      await page.getByLabel("PhaseSmith protocol document").textContent(),
    );
    assert.equal(inspected.shadow_mask.geometric.half_opening_degrees, 36);
    verified.inspectedOpening36 = true;
    await fs.writeFile(
      path.join(folder, "inspected-opening36.json"),
      JSON.stringify(inspected, null, 2),
    );
    await page
      .getByRole("button", { name: "Hide protocol", exact: true })
      .click();
    await page.getByRole("tab", { name: "Background", exact: true }).click();
    await page.getByLabel("DAC half opening / °", { exact: true }).fill("35");
    await page.getByLabel("DAC half opening / °", { exact: true }).press("Tab");
    await page
      .getByRole("button", { name: "Apply settings", exact: true })
      .click();
    await page.getByRole("tab", { name: "Frames", exact: true }).click();
    await page
      .getByRole("checkbox", {
        name: "Keep lossless intermediate stage outputs",
        exact: true,
      })
      .check();
    await page
      .getByRole("checkbox", {
        name: "I checked the frame order, angles, axis, count gain and cell-shadow assumptions.",
        exact: true,
      })
      .check();
    await page
      .getByRole("button", { name: "Apply settings", exact: true })
      .click();
    await page
      .getByRole("button", { name: "Run to next decision", exact: true })
      .click();
    await page
      .getByRole("tab", { name: "Structure", exact: true, selected: true })
      .waitFor({ timeout: 600000 });
    replay = await invoke("scxrd_snapshot");
    await archive(replay);
    await page.getByLabel("Rotation frame", { exact: true }).fill("61");
    await page.getByLabel("Rotation frame", { exact: true }).press("Enter");
  }

  await page.getByRole("tab", { name: "Frames", exact: true }).click();
  assert.equal(
    await page.getByLabel("Protocol first frame", { exact: true }).inputValue(),
    "3",
  );
  assert.equal(
    await page.getByLabel("Protocol last frame", { exact: true }).inputValue(),
    "144",
  );
  await page
    .getByRole("button", { name: "Inspect protocol", exact: true })
    .click();
  await page.getByLabel("PhaseSmith protocol document").waitFor();
  assert.match(
    await page.getByLabel("PhaseSmith protocol document").textContent(),
    /orthorhombic-rotation-v1/,
  );
  await page.screenshot({ path: path.join(folder, "protocol-inspection.png") });
  await page
    .getByRole("button", { name: "Hide protocol", exact: true })
    .click();
  assert.equal(
    await page.getByLabel("Gain / photons/count", { exact: true }).isDisabled(),
    true,
  );
  await page
    .getByRole("button", { name: "Save effective protocol…", exact: true })
    .click();
  await page.waitForFunction(
    () =>
      !document.querySelector('[data-testid="sc-primary-action"]')?.disabled,
  );
  await page.waitForFunction(() => window.__scLastFile === "protocol_save");
  const saved = JSON.parse(
    await fs.readFile(path.join(folder, "effective-protocol.json")),
  );
  assert.equal(saved.acquisition.first_frame, 2);
  assert.equal(saved.acquisition.last_frame_inclusive, 143);
  await page
    .getByRole("button", { name: "Inspect protocol", exact: true })
    .click();
  assert.deepEqual(
    JSON.parse(
      await page.getByLabel("PhaseSmith protocol document").textContent(),
    ),
    saved,
  );
  verified.savedProtocolEqualsInspected = true;

  await page
    .getByRole("button", { name: "Hide protocol", exact: true })
    .click();

  // Protocol replacement is undoable and must restore the actual native products.
  await page
    .getByRole("button", { name: "Use bundled v29", exact: true })
    .click();
  await page.waitForFunction(() => window.__scLastFile === "protocol_builtin");
  await page
    .getByRole("button", { name: "Undo single-crystal edit", exact: true })
    .click();
  await page.waitForFunction(
    () =>
      !document.querySelector('[data-testid="sc-primary-action"]')?.disabled,
  );
  const restored = (await invoke("scxrd_snapshot")).scxrd;
  assert.equal(restored.usableReflections, 4125);
  assert.equal(restored.config.confirmed, true);
  assert.equal(restored.scaling.rInt, replay.scxrd.scaling.rInt);
  assert.equal(
    restored.structure.r1,
    JSON.parse(await fs.readFile(path.join(folder, "search.json"))).r1,
  );
  verified.protocolUndoRestoresReductionAndCandidate = true;

  await page.getByRole("tab", { name: "Intensities", exact: true }).click();
  async function qualityFilter(value) {
    await page
      .getByLabel("Observation quality filter", { exact: true })
      .selectOption(value);
    await page.waitForFunction(
      (value) => window.__scLastFilter === value,
      value,
    );
  }
  await qualityFilter("usable");
  let shown = (await invoke("scxrd_snapshot")).scxrd;
  assert.equal(shown.reflectionFilteredCount, 4125);
  assert.ok(shown.reflections.every((r) => r.native_use));
  await page.screenshot({
    path: path.join(folder, "native-usable-observations.png"),
  });
  await page
    .getByRole("group", { name: "reflections pages", exact: true })
    .getByRole("button", { name: "Next", exact: true })
    .click();
  shown = (await invoke("scxrd_snapshot")).scxrd;
  assert.equal(shown.reflectionOffset, 200);
  assert.ok(shown.reflections.every((r) => r.native_use));
  await qualityFilter("excluded");
  shown = (await invoke("scxrd_snapshot")).scxrd;
  assert.equal(shown.reflectionFilteredCount, 3152);
  assert.ok(shown.reflections.every((r) => !r.native_use));
  verified.observationFiltersAndPaging = true;
  await qualityFilter("usable");
  for (const [size, width, height] of [
    ["wide", 1500, 1000],
    ["compact", 1100, 760],
    ["large", 1900, 1100],
  ]) {
    await page.setViewportSize({ width, height });
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
      await page.evaluate(
        () =>
          new Promise((resolve) =>
            requestAnimationFrame(() => requestAnimationFrame(resolve)),
          ),
      );
      await page.screenshot({
        path: path.join(folder, `${size}-${tab.toLowerCase()}.png`),
      });
      const action = await page.getByTestId("sc-primary-action").boundingBox();
      assert.ok(
        action && action.y + action.height <= height,
        `${size}/${tab}: main action visible`,
      );
      assert.equal(
        await page
          .locator(".sc-panel")
          .evaluate((e) => e.scrollWidth > e.clientWidth + 1),
        false,
      );
      layouts.push({ size, tab });
      if (size === "wide") {
        const check = await new AxeBuilder({ page })
          .include(".sc-workspace")
          .withTags(["wcag2a", "wcag2aa"])
          .analyze();
        assert.deepEqual(check.violations, [], tab);
        accessibility.push({ tab, violations: check.violations });
      }
    }
  }
  await page.getByRole("tab", { name: "Intensities", exact: true }).click();
  await qualityFilter("excluded");
  const reason = page
    .getByRole("cell", { name: /masked \/ shadowed pixels/ })
    .first();
  await reason.scrollIntoViewIfNeeded();
  await reason.locator("summary").click();

  assert.ok(!(await reason.textContent()).includes("flags 41234"));
  await page.screenshot({
    path: path.join(folder, "native-quality-reasons.png"),
  });
  await qualityFilter("usable");
  await page
    .getByRole("button", { name: "Clear stage and later results", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Run intensities", exact: true })
    .click();
  if (fresh)
    await page
      .locator(".sc-working")
      .getByText(/completed shadow_masks/)
      .waitFor({ timeout: 180000 });
  await page
    .getByRole("button", {
      name: "Stop single-crystal processing",
      exact: true,
    })
    .click();
  await page.getByTestId("sc-primary-action").waitFor();
  const stopped = (await invoke("scxrd_snapshot")).scxrd;
  assert.equal(stopped.stages[4].status, "paused");
  assert.notEqual(stopped.stages[5].status, "complete");
  assert.equal(stopped.usableReflections, 0);
  assert.equal(stopped.frames, 144);
  assert.equal(stopped.config.integration_method, "profile");
  assert.deepEqual(stopped.config.protocol, restored.config.protocol);
  assert.equal(stopped.config.confirmed, true);
  await page.screenshot({ path: path.join(folder, "protocol-stopped.png") });
  await page
    .getByRole("button", { name: "Undo single-crystal edit", exact: true })
    .click();
  const recovered = (await invoke("scxrd_snapshot")).scxrd;
  assert.equal(recovered.usableReflections, 4125);
  assert.equal(recovered.scaling.rInt, replay.scxrd.scaling.rInt);
  assert.equal(recovered.structure.r1, restored.structure.r1);
  verified.undoAfterStopRestoresPriorReductionAndCandidate = true;
  await page.screenshot({
    path: path.join(folder, "recovered-after-stop.png"),
  });
  assert.deepEqual(errors, []);
  await fs.writeFile(
    path.join(folder, "gui-receipt.json"),
    JSON.stringify(
      {
        ok: true,
        headless: true,
        engine: "chromium",
        verified,
        stoppedAfterCompletedMaskCheckpoint: fresh,
        freshSetup: fresh,
        source: fresh ? source : null,
        replayedRecipe: fresh ? null : recipe,
        rInt: replay.scxrd.scaling.rInt,
        used: 4125,
        layouts,
        accessibility,
        errors,
        cancellation: stopped.error,
        calls,
      },
      null,
      2,
    ),
  );
  console.log(
    "Measured protocol replay, layouts, accessibility, undo and cancellation passed",
  );
} finally {
  await browser.close();
  await native.close();
}
