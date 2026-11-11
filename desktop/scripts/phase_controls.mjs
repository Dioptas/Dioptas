import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { createInterface } from "node:readline";
import { fileURLToPath } from "node:url";
import { mkdir, writeFile } from "node:fs/promises";
import { chromium, webkit } from "playwright";
import { setInterfaceTextSize } from "./plot_navigation.mjs";

const root = fileURLToPath(new URL("../../", import.meta.url));
const artifacts = root + "/desktop/artifacts";
await mkdir(artifacts, { recursive: true });
const host = spawn(
  root + "/.venv/bin/python",
  ["-u", "desktop/scripts/bridge_host.py"],
  { cwd: root, stdio: ["pipe", "pipe", "pipe"] },
);
let nextId = 0;
const pending = new Map();
const logs = [];
host.stderr.on("data", (d) => logs.push(d.toString()));
createInterface({ input: host.stdout }).on("line", (line) => {
  try {
    const r = JSON.parse(line);
    const p = pending.get(r.id);
    if (p) {
      clearTimeout(p.timer);
      pending.delete(r.id);
      p.resolve(r.result);
    }
  } catch {
    logs.push(line);
  }
});
const invoke = (action, payload = {}) =>
  new Promise((resolve, reject) => {
    const id = ++nextId;
    const timer = setTimeout(() => {
      pending.delete(id);
      reject(Error(`Timeout: ${action}`));
    }, 45000);
    pending.set(id, { resolve, reject, timer });
    host.stdin.write(JSON.stringify({ id, action, payload }) + "\n");
  });
const call = async (action, payload = {}) => {
  const r = await invoke(action, payload);
  assert.equal(r.ok, true, r.error);
  return r;
};
let browser;
try {
  await call("example");
  await call("open_calibration", {
    path: root + "/dioptas/tests/data/CeO2_Pilatus1M.poni",
  });
  await call("integration_settings", { bins: 160, cake_bins: 30 });
  await call("integration_overlay", { operation: "capture" });
  browser = await (
    process.argv.includes("--webkit") ? webkit : chromium
  ).launch({ headless: true });
  const page = await browser.newPage({
    viewport: { width: 1440, height: 1000 },
  });
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  let importCif = false;
  let conditionGate = null;
  const conditionCalls = [];
  const burstCalculations = [];
  await page.exposeFunction("__dioptasInvoke", async (action, payload) => {
    const condition =
      action === "integration_phase" &&
      payload.operation === "update" &&
      typeof payload.pressure === "number";
    if (condition) {
      conditionCalls.push(payload.pressure);
      if (conditionGate) await conditionGate;
    }
    const result = await invoke(
      action,
      action === "integration_phase_files" && importCif
        ? { paths: [root + "/dioptas/tests/data/cif/fcc.cif"] }
        : payload,
    );
    if (condition)
      assert.ok(
        !("mask" in result) && !("cake" in result) && result.phaseOnly,
        "Pressure changes must not transfer detector/cake buffers",
      );
    return result;
  });
  await page.addInitScript(() => {
    window.pywebview = {
      api: { invoke: (a, p) => window.__dioptasInvoke(a, p) },
    };
  });
  const ready = async () => {
    await page.waitForFunction(
      () =>
        !!document.querySelector(".app") && !document.querySelector(".spin"),
    );
    assert.deepEqual(await page.getByRole("alert").allTextContents(), []);
  };
  const click = async (label) => {
    await page.getByRole("button", { name: label, exact: true }).click();
    await ready();
  };
  const edit = async (label, value) => {
    const input = page.getByLabel(label, { exact: true });
    await input.fill(String(value));
    await input.press("Enter");
    await ready();
  };
  await page.goto("file://" + root + "/dioptas/desktop/ui/index.html");
  // Native number inputs use the shared wheel behavior, including unfocused hover.
  const wheel = async (label, deltaY) => {
    const prevented = await page
      .getByLabel(label, { exact: true })
      .evaluate((input, deltaY) => {
        const event = new WheelEvent("wheel", {
          deltaY,
          bubbles: true,
          cancelable: true,
        });
        input.dispatchEvent(event);
        return event.defaultPrevented;
      }, deltaY);
    assert.ok(prevented, `Wheel should be consumed by ${label}`);
  };
  await page.getByRole("button", { name: "Integration", exact: true }).click();
  await ready();
  const fileStep = page.getByLabel("File step", { exact: true });
  await fileStep.waitFor();
  await wheel("File step", -100);
  assert.equal(Number(await fileStep.inputValue()), 2);
  await wheel("File step", 100);
  assert.equal(Number(await fileStep.inputValue()), 1);
  await wheel("File step", 100);
  assert.equal(
    Number(await fileStep.inputValue()),
    1,
    "Wheel must respect the lower bound",
  );
  await fileStep.hover();
  await page.mouse.wheel(0, -100);
  await page.waitForFunction(
    () => document.querySelector('input[aria-label="File step"]').value === "2",
  );
  await wheel("File step", 100);
  await fileStep.evaluate((input) => {
    for (const options of [
      { deltaY: -100, ctrlKey: true },
      { deltaY: 1, deltaX: 100 },
    ]) {
      input.dispatchEvent(
        new WheelEvent("wheel", {
          bubbles: true,
          cancelable: true,
          ...options,
        }),
      );
    }
  });
  assert.equal(
    Number(await fileStep.inputValue()),
    1,
    "Horizontal scroll and pinch must not change values",
  );
  await page.getByRole("tab", { name: "Overlay", exact: true }).click();
  const scaleStep = page.getByLabel("Scale Step", { exact: true });
  const initialScaleStep = Number(await scaleStep.inputValue());
  await scaleStep.hover();
  await page.mouse.wheel(0, -100);
  await page.waitForFunction(
    (start) =>
      Number(document.querySelector('input[aria-label="Scale Step"]').value) >
      start,
    initialScaleStep,
  );
  assert.ok(Number(await scaleStep.inputValue()) > initialScaleStep);
  await wheel("Scale Step", 100);
  assert.equal(Number(await scaleStep.inputValue()), initialScaleStep);
  const initialScale = (await call("state")).state.integration.overlays[0]
    .scale;
  await wheel("Overlay 1 scale", -100);
  await ready();
  assert.equal(
    (await call("state")).state.integration.overlays[0].scale,
    initialScale + initialScaleStep,
  );
  await wheel("Overlay 1 scale", 100);
  await ready();
  assert.equal(
    (await call("state")).state.integration.overlays[0].scale,
    initialScale,
  );
  await page.getByRole("tab", { name: "Phase", exact: true }).click();
  await click("Add phase…");
  await page.getByLabel("Phase 1 pressure (GPa)", { exact: true }).waitFor();
  assert.ok((await call("state")).pattern.phaseLines.length > 0);
  assert.equal(
    await page
      .getByLabel("Phase 1 temperature (K)", { exact: true })
      .isDisabled(),
    true,
  );
  assert.equal(
    await page.getByLabel("Phase 1 reference", { exact: true }).isDisabled(),
    true,
  );
  await click("Add phase…");
  await page.getByLabel("P step", { exact: true }).press("ArrowUp");
  assert.equal(
    await page.getByLabel("P step", { exact: true }).inputValue(),
    "2",
  );
  await page.getByLabel("P step", { exact: true }).press("ArrowUp");
  assert.equal(
    await page.getByLabel("P step", { exact: true }).inputValue(),
    "5",
  );
  await edit("P step", 2.5);
  assert.equal(
    await page
      .getByLabel("Phase 1 pressure (GPa)", { exact: true })
      .getAttribute("step"),
    "2.5",
  );
  await edit("Phase 1 pressure (GPa)", 12);
  const phaseScroll = await page
    .locator(".phase-table-scroll")
    .evaluate((el) => el.scrollTop);
  // Hold one calculation while the user wheels: only its latest successor runs.
  const burst = async (deltaY, expected) => {
    let release;
    conditionGate = new Promise((resolve) => {
      release = resolve;
    });
    const before = conditionCalls.length;
    for (let i = 0; i < 25; i++) await wheel("Phase 1 pressure (GPa)", deltaY);
    assert.equal(
      Number(
        await page
          .getByLabel("Phase 1 pressure (GPa)", { exact: true })
          .inputValue(),
      ),
      expected,
    );
    assert.ok(
      conditionCalls.length - before <= 1,
      "A wheel burst should not create a backlog of calculations",
    );
    assert.equal(
      await page.locator(".spin").count(),
      0,
      "Live phase changes must not flash the global busy state",
    );
    assert.ok(
      await page
        .getByLabel("Phase 1 pressure (GPa)", { exact: true })
        .isEnabled(),
    );
    conditionGate = null;
    release();
    for (let i = 0; i < 100; i++) {
      if (
        (await call("state")).state.integration.phases.every(
          (phase) => phase.pressure === expected,
        )
      )
        break;
      await page.waitForTimeout(20);
    }
    assert.deepEqual(
      (await call("state")).state.integration.phases.map(
        (phase) => phase.pressure,
      ),
      [expected, expected],
    );
    assert.ok(
      conditionCalls.length - before <= 2,
      "Only the in-flight and latest requested values should be calculated",
    );
    burstCalculations.push({
      notches: 25,
      calculations: conditionCalls.length - before,
      finalPressure: expected,
    });
  };
  await burst(-100, 74.5);
  assert.equal(
    await page.locator(".phase-table-scroll").evaluate((el) => el.scrollTop),
    phaseScroll,
  );
  await burst(100, 12);
  await ready();
  assert.deepEqual(
    (await call("state")).state.integration.phases.map((p) => p.pressure),
    [12, 12],
  );
  await page
    .getByLabel("Apply conditions to all phases", { exact: true })
    .click();
  await ready();
  await edit("Phase 2 pressure (GPa)", 18);
  assert.deepEqual(
    (await call("state")).state.integration.phases.map((p) => p.pressure),
    [12, 18],
  );
  await click("Toggle all phase visibility");
  assert.equal((await call("state")).pattern.phaseLines.length, 0);
  await click("Toggle all phase visibility");
  await click("Save List");
  await click("Removes all phases");
  await page
    .getByRole("dialog", { name: "Clear all phases?", exact: true })
    .getByRole("button", { name: "Clear all", exact: true })
    .click();
  await ready();
  await click("Load List");
  assert.deepEqual(
    (await call("state")).state.integration.phases.map((p) => p.pressure),
    [12, 18],
  );
  await page
    .getByRole("cell", { name: "au_version3", exact: true })
    .first()
    .click();
  await click("Edit selected Phase");
  await page
    .getByRole("dialog", { name: "Phase Editor", exact: true })
    .waitFor();
  assert.equal(await page.getByLabel("b₀", { exact: true }).isDisabled(), true);
  assert.equal(await page.getByLabel("α₀", { exact: true }).isDisabled(), true);
  await edit("a₀", 4.2);
  assert.equal(
    (await call("integration_phase_editor", { index: 0 })).phaseEditor.lattice
      .a0,
    4.2,
  );
  await edit("Reflection 1 intensity", 3);
  assert.equal(
    (await call("integration_phase_editor", { index: 0 })).phaseEditor
      .reflections[0].intensity,
    3,
  );
  await page.getByLabel("Select reflection 2", { exact: true }).check();
  const count = (await call("integration_phase_editor", { index: 0 }))
    .phaseEditor.reflections.length;
  await click("Delete");
  assert.equal(
    (await call("integration_phase_editor", { index: 0 })).phaseEditor
      .reflections.length,
    count - 1,
  );
  await click("Reload File");
  assert.notEqual(
    (await call("integration_phase_editor", { index: 0 })).phaseEditor.lattice
      .a0,
    4.2,
  );
  await page.keyboard.press("Escape");
  await page.getByRole("dialog").waitFor({ state: "detached" });
  importCif = true;
  await click("Add phase…");
  await page
    .getByRole("dialog", { name: "CIF conversion parameters", exact: true })
    .waitFor();
  await edit("Intensity Cutoff (%)", 2);
  await edit("Minimum d-spacing (Å)", 0.8);
  await click("OK");
  importCif = false;
  assert.equal((await call("state")).state.integration.phases.length, 3);
  await click("Browse EoS Material Database");
  await page
    .getByRole("dialog", { name: "EoS Material Database", exact: true })
    .waitFor();
  await page.getByLabel("Search materials", { exact: true }).fill("Au");
  await page.waitForTimeout(500);
  await ready();
  const catalog = (await call("integration_phase_catalog", { query: "Au" }))
    .phaseCatalog;
  const material = catalog.find(
    (m) =>
      m.diffraction &&
      m.defaultReference >= 0 &&
      !m.references[m.defaultReference].loadError,
  );
  await page.getByRole("cell", { name: material.name, exact: true }).click();
  await page
    .getByRole("button", { name: "Load as Phase", exact: true })
    .waitFor({ state: "visible" });
  await page.screenshot({ path: artifacts + "/phase-database.png" });
  await click("Load as Phase");
  assert.equal((await call("state")).state.integration.phases.length, 4);
  const temperature = page.getByLabel("Phase 4 temperature (K)", {
    exact: true,
  });
  assert.ok(await temperature.isEnabled());
  const initialTemperature = Number(await temperature.inputValue());
  const temperatureStep = Number(
    await page.getByLabel("T Step", { exact: true }).inputValue(),
  );
  await wheel("Phase 4 temperature (K)", -100);
  await ready();
  assert.equal(
    (await call("state")).state.integration.phases[3].temperature,
    initialTemperature + temperatureStep,
  );
  await wheel("Phase 4 temperature (K)", 100);
  await ready();
  assert.equal(
    (await call("state")).state.integration.phases[3].temperature,
    initialTemperature,
  );
  await click("Edit selected Phase");
  assert.equal(await page.getByLabel("a₀", { exact: true }).isDisabled(), true);
  assert.equal(await page.getByLabel("K₀", { exact: true }).isDisabled(), true);
  await click("Close Phase Editor");
  // Compact and larger-text layouts must scroll the table, never clip the tools.
  const layout = [];
  for (const large of [false, true]) {
    await setInterfaceTextSize(page, large);
    await page.setViewportSize({ width: 1000, height: 668 });
    await page.getByRole("tab", { name: "Phase", exact: true }).click();
    const metrics = await page.getByTestId("phase-controls").evaluate((el) => {
      const outer = el.getBoundingClientRect();
      const scroll = el.querySelector(".phase-table-scroll");
      return {
        width: outer.width,
        height: outer.height,
        tableWidth: scroll.scrollWidth,
        viewport: scroll.clientWidth,
        buttonsVisible: [
          ...el.querySelectorAll(
            ".phase-action-rail button, .phase-list-actions button",
          ),
        ].every((b) => {
          const r = b.getBoundingClientRect();
          return (
            r.left >= outer.left - 1 &&
            r.right <= outer.right + 1 &&
            r.top >= outer.top - 1 &&
            r.bottom <= outer.bottom + 1
          );
        }),
        text: getComputedStyle(el.querySelector("td input[type=number]"))
          .fontSize,
      };
    });
    assert.ok(metrics.buttonsVisible, JSON.stringify(metrics));
    assert.ok(metrics.tableWidth >= metrics.viewport);
    assert.equal(metrics.text, large ? "16px" : "14px");
    await page
      .getByLabel("Phase 4 reference", { exact: true })
      .scrollIntoViewIfNeeded();
    await page.locator(".phase-table-scroll").evaluate((el) => {
      el.scrollLeft = el.scrollWidth;
    });
    const scrollEnd = await page
      .locator(".phase-table-scroll")
      .evaluate((el) => {
        const reference = el
          .querySelector("tbody tr:last-child td:last-child select")
          .getBoundingClientRect();
        const area = el.getBoundingClientRect();
        const scrollbar =
          el.scrollHeight > el.clientHeight
            ? el.offsetWidth - el.clientWidth
            : 0;
        return reference.right <= area.right - scrollbar + 1;
      });
    assert.ok(scrollEnd);
    await page.screenshot({
      path: artifacts + `/phase-compact-${large ? "large" : "normal"}.png`,
    });
    // Compare the visible controls in independent views at the same text size.
    const readStyle = async (selector) =>
      page.locator(selector).evaluate((table) => {
        const header = table.querySelector("th:nth-child(3)");
        const input = table.querySelector(
          "tbody tr:last-child input[type=number]",
        );
        const swatch = table.querySelector(
          "tbody tr:last-child input[type=color]",
        );
        return {
          headerColor: getComputedStyle(header).backgroundColor,
          headerFont: getComputedStyle(header).fontSize,
          headerWeight: getComputedStyle(header).fontWeight,
          fieldFont: getComputedStyle(input).fontSize,
          fieldHeight: input.getBoundingClientRect().height,
          colorWidth: swatch.getBoundingClientRect().width,
          colorHeight: swatch.getBoundingClientRect().height,
        };
      });
    const phaseStyle = await readStyle(".phase-table");
    await page.getByRole("tab", { name: "Overlay", exact: true }).click();
    const overlayStyle = await readStyle(".qt-overlay-table");
    await page.locator(".qt-overlay-controls").screenshot({
      path:
        artifacts + `/shared-table-overlay-${large ? "large" : "normal"}.png`,
    });
    assert.deepEqual(
      phaseStyle,
      overlayStyle,
      "Phase and Overlay share table header, field and swatch styling",
    );
    await page
      .getByRole("button", { name: "Calibration", exact: true })
      .click();
    await page
      .getByRole("tab", { name: "Step 2: Pick rings", exact: true })
      .click();
    const peakStyle = await page
      .locator(".peak-table-headers")
      .evaluate((header) => ({
        headerColor: getComputedStyle(header).backgroundColor,
        headerFont: getComputedStyle(header).fontSize,
        headerWeight: getComputedStyle(header).fontWeight,
      }));
    await page.locator(".calibration-panel").screenshot({
      path: artifacts + `/shared-table-peaks-${large ? "large" : "normal"}.png`,
    });
    for (const key of Object.keys(peakStyle))
      assert.equal(
        peakStyle[key],
        phaseStyle[key],
        `Calibration shares ${key}`,
      );
    await page
      .getByRole("button", { name: "Integration", exact: true })
      .click();
    await ready();
    await page.getByRole("tab", { name: "Phase", exact: true }).click();
    layout.push({ ...metrics, sharedTableStyle: phaseStyle });
  }
  await page.setViewportSize({ width: 1440, height: 1000 });
  await setInterfaceTextSize(page, false);
  await page.getByRole("tab", { name: "Phase", exact: true }).click();
  await page.screenshot({ path: artifacts + "/phase-controls.png" });
  assert.ok(
    (
      await page.getByLabel("Phase legend", { exact: true }).innerText()
    ).includes("12.00 GPa"),
  );
  // New selections scroll vertically under pinned headings while retaining horizontal position.
  await call("integration_phase", {
    operation: "load",
    paths: Array(12).fill(root + "/dioptas/tests/data/jcpds/au_version3.jcpds"),
  });
  await click("Toggle all phase visibility");
  const selection = await page.getByTestId("phase-controls").evaluate((el) => {
    const table = el.querySelector("table");
    const row = table.querySelector('tr[aria-selected="true"]');
    const area = table.parentElement.getBoundingClientRect();
    const bounds = row.getBoundingClientRect();
    return {
      count: table.tBodies[0].rows.length,
      visible: bounds.bottom <= area.bottom + 1 && bounds.top >= area.top,
    };
  });
  assert.equal(selection.count, 16);
  assert.ok(selection.visible);

  assert.deepEqual(errors, []);
  await writeFile(
    artifacts +
      `/phase-controls-${process.argv.includes("--webkit") ? "webkit" : "chromium"}.json`,
    JSON.stringify(
      {
        ok: true,
        browser: process.argv.includes("--webkit") ? "WebKit" : "Chromium",
        layout,
        burstCalculations,
      },
      null,
      2,
    ),
  );
  console.log(
    "Phase controls passed: real-model imports, P/T, lists, visibility, editor, database and compact/large text layouts.",
  );
} finally {
  await browser?.close();
  host.stdin.end();
  await writeFile(artifacts + "/phase-controls.log", logs.join(""));
}
