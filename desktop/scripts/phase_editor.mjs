import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { createInterface } from "node:readline";
import { fileURLToPath } from "node:url";
import { mkdir, readFile, writeFile } from "node:fs/promises";
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
const pending = new Map();
let nextId = 0,
  logs = "";
host.stderr.on("data", (d) => (logs += d.toString()));
createInterface({ input: host.stdout }).on("line", (line) => {
  const r = JSON.parse(line);
  const p = pending.get(r.id);
  if (p) {
    clearTimeout(p.timer);
    pending.delete(r.id);
    p.resolve(r.result);
  }
});
const invoke = (action, payload = {}) =>
  new Promise((resolve, reject) => {
    const id = ++nextId;
    const timer = setTimeout(() => reject(Error(`Timeout: ${action}`)), 45000);
    pending.set(id, { resolve, reject, timer });
    host.stdin.write(JSON.stringify({ id, action, payload }) + "\n");
  });
const call = async (command, payload = {}) => {
  const r = await invoke(command, payload);
  assert.ok(r.ok, r.error);
  return r;
};
const engine = process.argv.includes("--webkit") ? webkit : chromium;
let browser;
try {
  await call("example");
  await call("open_calibration", {
    path: root + "/dioptas/tests/data/CeO2_Pilatus1M.poni",
  });
  await call("integration_settings", { bins: 120, cake_bins: 20 });
  await call("integration_phase", {
    operation: "load",
    path: root + "/dioptas/tests/data/jcpds/au_version3.jcpds",
  });
  browser = await engine.launch({ headless: true });
  const page = await browser.newPage({
    viewport: { width: 1440, height: 1000 },
  });
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.exposeFunction("__dioptasInvoke", invoke);
  await page.addInitScript(() => {
    window.__phasePending = 0;
    window.pywebview = {
      api: {
        invoke: async (a, p) => {
          window.__phasePending++;
          try {
            return await window.__dioptasInvoke(a, p);
          } finally {
            window.__phasePending--;
          }
        },
      },
    };
  });
  const ready = async () => {
    await page.waitForFunction(
      () =>
        !!document.querySelector(".app") &&
        !window.__phasePending &&
        !document.querySelector(".spin") &&
        !document.querySelector('.pe-number input[aria-busy="true"]'),
    );
  };
  const click = async (name) => {
    await page.getByRole("button", { name, exact: true }).click();
    await ready();
  };
  const edit = async (label, value, key = "Enter") => {
    const input = page.getByLabel(label, { exact: true });
    await input.fill(String(value));
    await input.press(key);
    await ready();
  };
  const state = async () =>
    (await call("integration_phase_editor", { index: 0 })).phaseEditor;
  const wheel = async (label, direction, count = 1) => {
    const input = page.getByLabel(label, { exact: true });
    const scroll = await page
      .locator(".pe-parameter-scroll:not([hidden])")
      .evaluate((el) => el.scrollTop);
    for (let i = 0; i < count; i++) {
      const prevented = await input.evaluate((el, deltaY) => {
        const event = new WheelEvent("wheel", {
          deltaY,
          bubbles: true,
          cancelable: true,
        });
        el.dispatchEvent(event);
        return event.defaultPrevented;
      }, direction * 100);
      assert.ok(prevented);
    }
    await ready();
    assert.equal(
      await page
        .locator(".pe-parameter-scroll:not([hidden])")
        .evaluate((el) => el.scrollTop),
      scroll,
    );
  };
  await page.goto("file://" + root + "/dioptas/desktop/ui/index.html");
  await click("Integration");
  await page.getByRole("tab", { name: "Phase", exact: true }).click();
  await click("Edit selected Phase");
  const dialog = page.getByRole("dialog", {
    name: "Phase Editor",
    exact: true,
  });
  await dialog.waitFor();
  assert.ok(await page.getByLabel("b₀", { exact: true }).isDisabled());
  await edit("a₀", 4.2);
  assert.equal((await state()).lattice.a0, 4.2);
  await page.getByLabel("a₀", { exact: true }).fill("invalid");
  await page.getByLabel("a₀", { exact: true }).press("Enter");
  assert.equal(
    await page.getByLabel("a₀", { exact: true }).getAttribute("aria-invalid"),
    "true",
  );
  assert.equal((await state()).lattice.a0, 4.2);
  await page
    .getByRole("tab", { name: "Equation of state", exact: true })
    .click();
  await click("Save As…");
  await page.waitForFunction(
    () => document.activeElement?.getAttribute("aria-label") === "a₀",
  );
  assert.ok(
    await dialog
      .locator("footer")
      .innerText()
      .then((text) => text.includes("Resolve the invalid value")),
  );
  await page.keyboard.press("Escape");
  assert.equal(
    await dialog.isVisible(),
    true,
    "Escape in numeric draft must restore without closing",
  );
  assert.equal(
    await page.getByLabel("a₀", { exact: true }).inputValue(),
    "4.2",
  );
  await edit("Lattice length step", 0.02);
  await page.getByLabel("a₀", { exact: true }).press("ArrowUp");
  await ready();
  assert.equal((await state()).lattice.a0, 4.22);
  await click("Decrease a₀");
  assert.equal((await state()).lattice.a0, 4.2);
  await click("Increase a₀");
  assert.equal((await state()).lattice.a0, 4.22);
  for (let burst = 0; burst < 5; burst++) {
    await wheel("a₀", -1, 3);
    assert.equal((await state()).lattice.a0, 4.28);
    await wheel("a₀", 1, 3);
    assert.equal((await state()).lattice.a0, 4.22);
  }
  await page
    .getByRole("button", { name: "Increase a₀", exact: true })
    .evaluate((button) =>
      button.dispatchEvent(
        new WheelEvent("wheel", {
          deltaY: -100,
          bubbles: true,
          cancelable: true,
        }),
      ),
    );
  await ready();
  assert.equal((await state()).lattice.a0, 4.24);
  await wheel("a₀", 1);
  assert.ok(
    await page
      .getByRole("button", { name: "Increase b₀", exact: true })
      .isDisabled(),
  );
  await page
    .getByLabel("Phase symmetry", { exact: true })
    .selectOption("triclinic");
  await ready();
  await edit("Lattice angle step", 2.5);
  await click("Decrease α₀");
  assert.equal((await state()).lattice.alpha0, 87.5);
  await click("Increase α₀");
  assert.equal((await state()).lattice.alpha0, 90);
  await wheel("α₀", 1);
  assert.equal((await state()).lattice.alpha0, 87.5);
  await wheel("α₀", -1);
  assert.equal((await state()).lattice.alpha0, 90);
  await page
    .getByLabel("Phase symmetry", { exact: true })
    .selectOption("orthorhombic");
  await ready();
  await edit("Lattice ratio step", 0.025);
  await click("Increase c/a");
  let latticeState = (await state()).lattice;
  assert.ok(Math.abs(latticeState.c0 / latticeState.a0 - 1.025) < 1e-12);
  await click("Decrease c/a");
  latticeState = (await state()).lattice;
  assert.ok(Math.abs(latticeState.c0 / latticeState.a0 - 1) < 1e-12);
  await wheel("c/a", -1);
  latticeState = (await state()).lattice;
  assert.ok(Math.abs(latticeState.c0 / latticeState.a0 - 1.025) < 1e-12);
  await wheel("c/a", 1);
  await edit("c/a", 1.5, "Tab");
  assert.equal((await state()).lattice.c0, 4.22 * 1.5);
  assert.equal(
    await page
      .getByLabel("c/b", { exact: true })
      .evaluate((el) => el === document.activeElement),
    true,
    "Tab focus survives model update",
  );
  // Fast Tab-driven edits are serialized without replacing the next draft.
  await page.getByLabel("a₀", { exact: true }).fill("4.25");
  await page.getByLabel("a₀", { exact: true }).press("Tab");
  await page.getByLabel("b₀", { exact: true }).fill("4.3");
  await page.getByLabel("b₀", { exact: true }).press("Tab");
  await ready();
  assert.equal((await state()).lattice.a0, 4.25);
  assert.equal((await state()).lattice.b0, 4.3);
  await edit("Reflection 1 intensity", -1);
  assert.equal(
    await page
      .getByLabel("Reflection 1 intensity", { exact: true })
      .getAttribute("aria-invalid"),
    "true",
  );
  await page.keyboard.press("Escape");
  await edit("Reflection 1 intensity", 3);
  assert.equal((await state()).reflections[0].intensity, 3);
  await edit("Reflection 1 intensity", 66.0396789);
  await page.getByLabel("Reflection 1 intensity", { exact: true }).blur();
  await ready();
  assert.equal(
    await page
      .getByLabel("Reflection 1 intensity", { exact: true })
      .inputValue(),
    "66.04",
  );
  await wheel("Reflection 1 intensity", -1);
  assert.equal((await state()).reflections[0].intensity, 67.0396789);
  await wheel("Reflection 1 intensity", 1);
  assert.equal((await state()).reflections[0].intensity, 66.0396789);
  await page.getByLabel("Reflection 1 intensity", { exact: true }).blur();
  await ready();
  const beforeFocus = (await call("state")).state.revision;
  await page.getByLabel("Reflection 1 intensity", { exact: true }).focus();
  assert.equal(
    await page
      .getByLabel("Reflection 1 intensity", { exact: true })
      .inputValue(),
    "66.0396789",
  );
  await page.getByLabel("Reflection 1 intensity", { exact: true }).blur();
  await ready();
  assert.equal((await state()).reflections[0].intensity, 66.0396789);
  assert.equal((await call("state")).state.revision, beforeFocus);
  const indexWidth = await page
    .locator(".pe-index-cell input")
    .first()
    .evaluate((el) => el.getBoundingClientRect().width);
  assert.ok(indexWidth <= 45, String(indexWidth));
  await page
    .getByLabel("Reflection position columns", { exact: true })
    .selectOption("all");
  await page.getByRole("button", { name: "Q₀ (Å⁻¹)", exact: true }).waitFor();
  await page.getByRole("button", { name: "2θ₀ (°)", exact: true }).waitFor();
  await page
    .getByLabel("Reflection position columns", { exact: true })
    .selectOption("d-angle");
  await edit("Reflection 1 intensity", 3);
  await click("Add");
  const count = (await state()).reflections.length;
  await page.waitForFunction(
    (label) => document.activeElement?.getAttribute("aria-label") === label,
    `Reflection ${count} h`,
  );
  await page.getByLabel(`Select reflection ${count}`, { exact: true }).check();
  await click("Delete");
  assert.equal((await state()).reflections.length, count - 1);
  await page.getByRole("button", { name: "Intensity", exact: true }).click();
  const ids = await page
    .locator('.pe-reflection-scroll tbody input[aria-label$=" intensity"]')
    .evaluateAll((fields) =>
      fields.map((f) => Number(f.getAttribute("aria-label").split(" ")[1]) - 1),
    );
  const reflectionState = await state();
  const values = ids.map((i) => reflectionState.reflections[i].intensity);
  assert.deepEqual(
    values,
    [...values].sort((a, b) => a - b),
  );
  const clipboard = await page
    .locator(".pe-reflection-scroll")
    .evaluate((el) => {
      el.focus();
      const data = new DataTransfer();
      el.dispatchEvent(
        new ClipboardEvent("copy", { bubbles: true, clipboardData: data }),
      );
      return data.getData("text/plain");
    });
  assert.equal(
    clipboard.split("\n").length,
    reflectionState.reflections.length + 1,
  );
  await click("Export table…");
  assert.ok(
    (await readFile(artifacts + "/reflections.txt", "utf8")).startsWith(
      "h\tk\tl\tIntensity",
    ),
  );
  await page
    .getByRole("tab", { name: "Equation of state", exact: true })
    .click();
  await page
    .getByLabel("Equation of state model", { exact: true })
    .selectOption("BM2Reference");
  await ready();
  await edit("P ref", 2);
  assert.equal((await state()).eosFields.find((f) => f.key === "p0").value, 2);
  await page
    .getByLabel("Equation of state model", { exact: true })
    .selectOption("BM3");
  await ready();
  await page
    .getByLabel("Thermal model", { exact: true })
    .selectOption("MieGruneisenDebye");
  await ready();
  await edit("θ₀", 650);
  assert.equal(
    (await state()).thermalFields.find((f) => f.key === "theta0").value,
    650,
  );
  await page
    .getByLabel("Thermal model", { exact: true })
    .selectOption("AlphaKT");
  await ready();
  await page
    .getByLabel("Expansion law", { exact: true })
    .selectOption("linear_temperature");
  await ready();
  await edit("α₁", "1e-8");
  assert.equal(
    (await state()).thermalFields.find((f) => f.key === "alpha1").value,
    1e-8,
  );
  await click("Save As…");
  assert.ok(
    (await readFile(artifacts + "/phase.eosmat", "utf8")).includes('"AlphaKT"'),
  );
  await page.screenshot({ path: artifacts + "/phase-editor-eos.png" });
  await click("Close");
  await dialog.waitFor({ state: "detached" });
  await page.waitForFunction(
    () =>
      document.activeElement?.getAttribute("aria-label") ===
      "Edit selected Phase",
  );
  // Load a source structure, and check exact scientific rejection feedback in the modal.
  await call("integration_phase", { operation: "clear" });
  await call("integration_phase", {
    operation: "load",
    path: root + "/dioptas/tests/data/cif/fcc.cif",
    minimum_d_spacing: 1.5,
  });
  await page.reload();
  await ready();
  await click("Integration");
  await page.getByRole("tab", { name: "Phase", exact: true }).click();
  await click("Edit selected Phase");
  const siteCount = (await state()).structure.sites.length;
  await edit("Site 1 occupancy", 0.75);
  assert.equal((await state()).structure.sites[0].occupancy, 0.75);
  await edit("Site 1 element", "Xx");
  assert.ok(
    await dialog
      .locator("footer")
      .innerText()
      .then((text) => text.includes("Edit not applied:")),
  );
  assert.notEqual(
    await page.getByLabel("Site 1 element", { exact: true }).inputValue(),
    "Xx",
  );
  await page.getByLabel("Space group", { exact: true }).fill("P 1");
  await click("Apply group");
  assert.equal((await state()).structure.spaceGroupNumber, 1);
  await click("Add atomic site…");
  await click("Choose new site element");
  await page
    .getByRole("dialog", { name: "Choose element", exact: true })
    .waitFor();
  await click("Choose Gold");
  assert.equal(
    await page.getByLabel("New site element", { exact: true }).inputValue(),
    "Au",
  );
  await click("Add site");
  assert.equal((await state()).structure.sites.length, siteCount + 1);
  await page
    .getByLabel(`Select atomic site ${siteCount + 1}`, { exact: true })
    .check();
  await click("Remove selected sites");
  assert.equal((await state()).structure.sites.length, siteCount);
  // Keep both parameter pages taller than the viewport for scrollbar checks.
  await page
    .getByRole("tab", { name: "Equation of state", exact: true })
    .click();
  await edit("K₀", 100);
  await page
    .getByLabel("Thermal model", { exact: true })
    .selectOption("AlphaKT");
  await ready();
  const metrics = [];
  await click("Close");
  for (const large of [false, true]) {
    await setInterfaceTextSize(page, large);
    await page.setViewportSize({ width: 1000, height: 668 });
    await page.getByRole("tab", { name: "Phase", exact: true }).click();
    await click("Edit selected Phase");
    for (const tab of ["Volume & structure", "Equation of state"]) {
      await page.getByRole("tab", { name: tab, exact: true }).click();
      const m = await dialog.evaluate((el) => {
        const r = el.getBoundingClientRect(),
          footer = el.querySelector("footer").getBoundingClientRect();
        const body = el.querySelector(".pe-body");
        const parameter = el.querySelector(
          ".pe-parameter-scroll:not([hidden])",
        );
        const table = el.querySelector(".pe-reflection-scroll");
        return {
          width: r.width,
          height: r.height,
          right: r.right,
          bottom: r.bottom,
          footerBottom: footer.bottom,
          bodyClient: body.clientWidth,
          bodyScroll: body.scrollWidth,
          parameterClient: parameter.clientHeight,
          parameterScroll: parameter.scrollHeight,
          parameterGutter: parameter.offsetWidth - parameter.clientWidth,
          scrollbarWidth: getComputedStyle(parameter, "::-webkit-scrollbar")
            .width,
          thumbColor: getComputedStyle(parameter, "::-webkit-scrollbar-thumb")
            .backgroundColor,
          tableClient: table.clientHeight,
          font: getComputedStyle(el.querySelector(".pe-number input")).fontSize,
          latticeInputs: [
            ...el.querySelectorAll(".pe-lattice-grid .pe-field"),
          ].map((field) => {
            const input = field.querySelector("input").getBoundingClientRect();
            return {
              x: input.x,
              width: input.width,
              unitWidth: field.querySelector(".pe-unit").getBoundingClientRect()
                .width,
            };
          }),
          parameterGaps: [
            ...el.querySelectorAll(
              ".pe-eos-fields .pe-field:not(.pe-field-choice)",
            ),
          ]
            .map((field) => {
              const label = field.firstElementChild.getBoundingClientRect();
              const value = field
                .querySelector("input")
                .getBoundingClientRect();
              return value.width > 0 ? value.left - label.right : null;
            })
            .filter((gap) => gap != null),
          parameterColumns: [
            ...el.querySelectorAll(
              ".pe-eos-fields .pe-field:not(.pe-field-choice)",
            ),
          ]
            .map((field) => {
              const label = field.firstElementChild.getBoundingClientRect();
              const input = field
                .querySelector("input")
                .getBoundingClientRect();
              const unit = field
                .querySelector(".pe-unit")
                .getBoundingClientRect();
              return {
                label: label.x,
                value: input.x,
                width: input.width,
                unit: unit.x,
              };
            })
            .filter((row) => row.width > 0),
          recordToolbar: (() => {
            const selector = el
              .querySelector('select[aria-label="Editor material record"]')
              ?.getBoundingClientRect();
            const toolbar = el
              .querySelector(".pe-record-actions")
              .getBoundingClientRect();
            return selector
              ? {
                  gap: toolbar.left - selector.right,
                  centerOffset:
                    (toolbar.top +
                      toolbar.bottom -
                      selector.top -
                      selector.bottom) /
                    2,
                  right: toolbar.right,
                  paneRight: parameter.getBoundingClientRect().right,
                }
              : null;
          })(),
        };
      });
      assert.ok(
        m.right <= 1000 && m.bottom <= 668 && m.footerBottom <= m.bottom,
        JSON.stringify(m),
      );
      assert.ok(m.bodyScroll <= m.bodyClient + 1, JSON.stringify(m));
      assert.ok(m.parameterScroll > m.parameterClient, JSON.stringify(m));
      assert.ok(m.parameterGutter >= 10, JSON.stringify(m));
      assert.ok(m.tableClient >= 120, JSON.stringify(m));
      assert.equal(m.font, large ? "16px" : "14px");
      if (tab.startsWith("Equation")) {
        if (m.recordToolbar) {
          assert.ok(
            m.recordToolbar.gap >= 0 && m.recordToolbar.gap <= 8,
            JSON.stringify(m),
          );
          assert.ok(
            Math.abs(m.recordToolbar.centerOffset) <= 1,
            JSON.stringify(m),
          );
          assert.ok(
            m.recordToolbar.right <= m.recordToolbar.paneRight + 1,
            JSON.stringify(m),
          );
        }
        assert.ok(
          await page
            .getByRole("toolbar", { name: "EoS records", exact: true })
            .isVisible(),
        );
        assert.ok(
          m.parameterGaps.every((gap) => gap >= 0 && gap <= 8),
          JSON.stringify(m),
        );
        for (const row of m.parameterColumns) {
          for (const column of ["label", "value", "width", "unit"]) {
            assert.ok(
              Math.abs(row[column] - m.parameterColumns[0][column]) < 1,
              JSON.stringify(m),
            );
          }
        }
        assert.equal(
          await page.getByText("Manage EoS records", { exact: true }).count(),
          0,
        );
      }
      if (tab.startsWith("Volume")) {
        m.latticeInputs.forEach((input, index) => {
          const column = m.latticeInputs[index % 3];
          assert.ok(Math.abs(input.x - column.x) < 1, JSON.stringify(m));
          assert.ok(
            Math.abs(input.width - column.width) < 1,
            JSON.stringify(m),
          );
          assert.ok(input.unitWidth > 0, JSON.stringify(m));
        });
      }
      metrics.push({ large, tab, ...m });
      await page.screenshot({
        path:
          artifacts +
          `/phase-editor-${large ? "large" : "normal"}-${tab.startsWith("Volume") ? "structure" : "eos"}.png`,
      });
    }
    await click("Close");
  }
  // Bundled source is immutable; the editable custom copy keeps the published record.
  await call("integration_phase", { operation: "clear" });
  const catalog = (await call("integration_phase_catalog", { query: "Au" }))
    .phaseCatalog;
  const material = catalog.find(
    (m) =>
      m.diffraction &&
      m.defaultReference >= 0 &&
      !m.references[m.defaultReference].loadError,
  );
  await call("integration_phase", {
    operation: "load_database",
    material_id: material.id,
    reference: material.defaultReference,
  });
  await page.reload();
  await ready();
  await click("Integration");
  await page.getByRole("tab", { name: "Phase", exact: true }).click();
  await click("Edit selected Phase");
  assert.ok(await page.getByLabel("a₀", { exact: true }).isDisabled());
  await page
    .getByRole("tab", { name: "Equation of state", exact: true })
    .click();
  assert.ok(await page.getByLabel("K₀", { exact: true }).isDisabled());
  const publishedReference = (await state()).reference;
  const publishedData = await state();
  assert.equal(
    await page.locator(".pe-assessment").innerText(),
    publishedData.references[publishedData.reference].assessment,
  );
  assert.ok(await page.getByLabel("EoS name", { exact: true }).isDisabled());
  assert.equal(
    await page.getByText("Parameter defaults", { exact: true }).count(),
    0,
  );
  const paneOrder = await page.locator(".pe-eos-page").evaluate((pane) => {
    const y = (selector) =>
      pane.querySelector(selector).getBoundingClientRect().top;
    return [
      y('select[aria-label="Editor material record"]'),
      y('input[aria-label="EoS name"]'),
      y('select[aria-label="Equation of state model"]'),
      y('select[aria-label="Thermal model"]'),
      y('[aria-label="Equation of state parameters"]'),
    ];
  });
  assert.ok(
    paneOrder.every((y, i) => i === 0 || y > paneOrder[i - 1]),
    JSON.stringify(paneOrder),
  );
  const sourceSelector = page.getByLabel("Editor material record", {
    exact: true,
  });
  for (const [label, tone] of [
    ["Parameter parity", "success"],
    ["Similar", "warning"],
    ["Not reproduced", "danger"],
    ["Not refittable", "neutral"],
  ]) {
    const index = publishedData.references.findIndex(
      (r) => r.assessment === label,
    );
    assert.ok(index >= 0, label);
    await sourceSelector.selectOption(String(index));
    await ready();
    assert.equal(await page.locator(".pe-assessment").innerText(), label);
    assert.equal(
      await page.locator(".pe-assessment").getAttribute("data-tone"),
      tone,
    );
  }
  await sourceSelector.selectOption(String(publishedReference));
  await ready();
  assert.ok(
    await page
      .getByRole("toolbar", { name: "EoS records", exact: true })
      .isVisible(),
  );
  assert.ok(
    await page
      .getByRole("button", { name: "Duplicate as custom", exact: true })
      .isDisabled(),
  );
  assert.ok(
    await page
      .getByRole("button", { name: "Add record", exact: true })
      .isDisabled(),
  );
  await page
    .getByRole("tab", { name: "Volume & structure", exact: true })
    .click();
  const original = await state();
  await click("Edit a copy");
  assert.equal(
    await page.getByLabel("a₀", { exact: true }).isDisabled(),
    false,
  );
  const copy = (await call("integration_phase_editor", { index: 1 }))
    .phaseEditor;
  assert.deepEqual(copy.reflections, original.reflections);
  assert.deepEqual(copy.lattice, original.lattice);
  assert.ok(copy.editable && copy.eosEditable && !copy.canReload);
  const customState = async () =>
    (await call("integration_phase_editor", { index: 1 })).phaseEditor;
  await page
    .getByRole("tab", { name: "Equation of state", exact: true })
    .click();
  await click("Duplicate as custom");
  assert.equal(
    await page.locator(".pe-assessment").innerText(),
    "Not assessed",
  );
  assert.equal(
    await page.locator(".pe-assessment").getAttribute("data-tone"),
    "neutral",
  );
  await edit("K₀", 180);
  await edit("EoS name", "Diagnostic custom EOS");
  assert.equal((await customState()).recordLabel, "Diagnostic custom EOS");
  await click("Set default");
  await click("Delete record…");
  await click("Confirm delete");
  await page
    .getByLabel("Editor material record", { exact: true })
    .selectOption(String(copy.reference));
  await ready();
  await page
    .getByRole("tab", { name: "Volume & structure", exact: true })
    .click();

  await edit("a₀", copy.lattice.a0 * 1.01);
  assert.equal((await state()).lattice.a0, original.lattice.a0);
  await edit("Material name", "My named gold material");
  await click("Save As…");
  const savedCopy = (await call("integration_phase_editor", { index: 1 }))
    .phaseEditor;
  assert.equal(savedCopy.materialName, "My named gold material");
  assert.ok(
    savedCopy.filename.endsWith("phase.eosmat") &&
      savedCopy.canSaveCurrent &&
      !savedCopy.modified,
  );
  await edit("Material name", "Updated gold material");
  await click("Save");
  const savedAgain = (await call("integration_phase_editor", { index: 1 }))
    .phaseEditor;
  assert.equal(savedAgain.materialName, "Updated gold material");
  assert.equal(savedAgain.filename, savedCopy.filename);
  assert.equal(savedAgain.modified, false);
  assert.equal(
    JSON.parse(await readFile(savedCopy.filename, "utf8")).name,
    "Updated gold material",
  );
  assert.equal(
    await page.getByLabel("Material file", { exact: true }).inputValue(),
    savedCopy.filename,
  );
  assert.ok(
    await page
      .getByRole("button", { name: "Edit a copy", exact: true })
      .evaluate((el) => !!el.closest("footer")),
  );
  await page.screenshot({
    path: artifacts + "/phase-editor-editable-copy.png",
  });
  // A copied Gold catalog must remain exportable after removing shared-data records.
  await page
    .getByRole("tab", { name: "Equation of state", exact: true })
    .click();
  let userMaterial = (await call("integration_phase_editor", { index: 1 }))
    .phaseEditor;
  const anderson = userMaterial.references.findIndex((r) =>
    /Anderson.*1989/i.test(r.label),
  );
  assert.ok(anderson >= 0);
  await page
    .getByLabel("Editor material record", { exact: true })
    .selectOption(String(anderson));
  await ready();
  await page
    .getByText("Experimental & validity ranges", { exact: true })
    .click();
  for (const [label, value] of [
    ["Experimental pressure minimum", 0],
    ["Experimental pressure maximum", 125],
    ["Experimental temperature minimum", 298],
    ["Experimental temperature maximum", 2000],
    ["Validity pressure minimum", -1],
    ["Validity pressure maximum", 150],
    ["Validity temperature minimum", 200],
    ["Validity temperature maximum", 2200],
  ])
    await page.getByLabel(label, { exact: true }).fill(String(value));
  assert.ok(
    await page.getByRole("button", { name: "Save", exact: true }).isDisabled(),
  );
  await click("Apply ranges");
  await click("Save");
  await click("Reload File");
  await page
    .getByLabel("Editor material record", { exact: true })
    .selectOption(String(anderson));
  await ready();
  assert.deepEqual(
    (await customState()).recordData.experimental_pressure_range_gpa,
    [0, 125],
  );
  assert.deepEqual(
    (await customState()).recordData.validity.temperature_k,
    [200, 2200],
  );
  await page
    .getByText("Experimental & validity ranges", { exact: true })
    .click();
  await page
    .getByLabel("Validity pressure minimum", { exact: true })
    .fill("200");
  await click("Apply ranges");
  assert.match(
    await page.locator('.pe-ranges [role="alert"]').innerText(),
    /ordered minimum/,
  );
  await click("Reset range edits");
  for (const kind of [
    "experimental pressure",
    "experimental temperature",
    "validity pressure",
    "validity temperature",
  ])
    await click(`Clear ${kind} range`);
  await click("Apply ranges");
  await click("Save");
  assert.ok(!("pressure_gpa" in (await customState()).recordData.validity));
  await page.screenshot({ path: artifacts + "/phase-editor-ranges.png" });
  // The user's Holzapfel + Anderson example includes long normalization units
  // and dimensionless fields. All rows must retain the same three columns.
  await page
    .getByLabel("Equation of state model", { exact: true })
    .selectOption("Holzapfel");
  await ready();
  await page.getByText("Material normalization data", { exact: true }).click();
  const parameterColumns = await page
    .locator(
      ".pe-parameter-scroll:not([hidden]) .pe-eos-fields .pe-field:not(.pe-field-choice)",
    )
    .evaluateAll((fields) =>
      fields
        .map((field) => {
          const input = field.querySelector("input").getBoundingClientRect();
          const unit = field.querySelector(".pe-unit").getBoundingClientRect();
          return { x: input.x, width: input.width, unit: unit.x };
        })
        .filter((row) => row.width > 0),
    );
  assert.ok(parameterColumns.length >= 8);
  for (const row of parameterColumns) {
    for (const key of ["x", "width", "unit"])
      assert.ok(
        Math.abs(row[key] - parameterColumns[0][key]) < 1,
        JSON.stringify(parameterColumns),
      );
  }
  for (const label of ["(αKₜ)ᵣ", "(∂Kₜ/∂T)ᵥ"]) {
    const input = page.getByLabel(label, { exact: true });
    assert.ok(await input.isVisible());
    assert.equal(
      await input
        .locator("xpath=ancestor::label")
        .locator(".pe-unit")
        .innerText(),
      "GPa/K",
    );
    assert.match(
      await input.getAttribute("title"),
      /reference state|constant volume/,
    );
  }
  await page
    .getByRole("group", { name: "Thermal parameters", exact: true })
    .scrollIntoViewIfNeeded();
  await page.screenshot({
    path: artifacts + "/phase-editor-thermal-symbols.png",
  });
  // Wider panes pair parameters while keeping each label/value/unit column
  // aligned. Long normalization units stay in the first column group.
  await click("Close");
  await setInterfaceTextSize(page, false);
  await page.setViewportSize({ width: 1200, height: 1000 });
  await click("Edit selected Phase");
  await page
    .getByRole("tab", { name: "Equation of state", exact: true })
    .click();
  const paired = await page
    .locator(".pe-parameter-scroll:not([hidden])")
    .evaluate((pane) => {
      const rows = [
        ...pane.querySelectorAll(
          ".pe-eos-fields .pe-field:not(.pe-field-choice)",
        ),
      ]
        .map((field) => {
          const input = field.querySelector("input").getBoundingClientRect();
          const unit = field.querySelector(".pe-unit").getBoundingClientRect();
          const label = field.firstElementChild.getBoundingClientRect();
          return {
            key: field.querySelector("input").getAttribute("aria-label"),
            y: input.y,
            x: input.x,
            width: input.width,
            unit: unit.x,
            unitRight: unit.right,
            labelRight: label.right,
          };
        })
        .filter((row) => row.width > 0);
      const selectorX = pane
        .querySelector('select[aria-label="Equation of state model"]')
        .getBoundingClientRect().x;
      return {
        rows,
        selectorX,
        width: pane.clientWidth,
        scroll: pane.scrollWidth,
        right: pane.getBoundingClientRect().right,
      };
    });
  assert.ok(paired.scroll <= paired.width + 1, JSON.stringify(paired));
  const starts = [...new Set(paired.rows.map((row) => row.x))].sort(
    (a, b) => a - b,
  );
  assert.equal(starts.length, 2, JSON.stringify(paired));
  assert.equal(paired.selectorX, starts[0], JSON.stringify(paired));
  for (const start of starts) {
    const rows = paired.rows.filter((row) => row.x === start);
    for (const row of rows) {
      assert.equal(row.width, rows[0].width);
      assert.equal(row.unit, rows[0].unit);
      assert.ok(row.x - row.labelRight <= 8);
      assert.ok(row.unitRight <= paired.right + 1, JSON.stringify(paired));
    }
  }
  const k0 = paired.rows.find((row) => row.key === "K₀");
  const kp = paired.rows.find((row) => row.key === "K₀′");
  assert.equal(k0.y, kp.y);
  assert.notEqual(k0.x, kp.x);
  await page.screenshot({
    path: artifacts + "/phase-editor-paired-parameters.png",
  });
  const mao = userMaterial.references.findIndex((r) =>
    /dewaele.*mao ruby/i.test(r.label),
  );
  assert.ok(mao >= 0);
  await page
    .getByLabel("Editor material record", { exact: true })
    .selectOption(String(mao));
  await ready();
  const countBeforeDelete = userMaterial.references.length;
  await click("Delete record…");
  const confirmRecord = page.getByRole("dialog", {
    name: "Delete EoS record?",
    exact: true,
  });
  await confirmRecord.waitFor();
  const popupBox = await confirmRecord.boundingBox();
  const deleteBox = await page
    .getByRole("button", { name: "Delete record…", exact: true })
    .boundingBox();
  assert.ok(
    Math.min(
      Math.abs(popupBox.y - deleteBox.y - deleteBox.height),
      Math.abs(deleteBox.y - popupBox.y - popupBox.height),
    ) <= 8,
    "Confirmation should be beside Delete record",
  );
  await page.keyboard.press("Escape");
  await confirmRecord.waitFor({ state: "detached" });
  assert.ok(
    await dialog.isVisible(),
    "Escape should only close the small confirmation",
  );
  assert.equal(
    (await call("integration_phase_editor", { index: 1 })).phaseEditor
      .references.length,
    countBeforeDelete,
  );
  assert.ok(
    await page
      .getByRole("button", { name: "Delete record…", exact: true })
      .evaluate((el) => el === document.activeElement),
  );
  await click("Delete record…");
  await page.screenshot({
    path: artifacts + "/phase-editor-delete-popover.png",
  });
  await click("Confirm delete");
  await click("Save");
  await click("Reload File");
  userMaterial = (await call("integration_phase_editor", { index: 1 }))
    .phaseEditor;
  assert.equal(userMaterial.references.length, countBeforeDelete - 1);
  assert.ok(
    !userMaterial.references.some((r) => /dewaele.*mao ruby/i.test(r.label)),
  );
  const horizontalChecks = [];
  for (const large of [false, true]) {
    await click("Close");
    await setInterfaceTextSize(page, large);
    for (const width of [1000, 1200, 1440]) {
      await page.setViewportSize({ width, height: 900 });
      await click("Edit selected Phase");
      await page
        .getByRole("tab", { name: "Equation of state", exact: true })
        .click();
      for (const model of [
        "AlphaKT",
        "MieGruneisenDebye",
        "Sokolova2016",
        "SoundVelocityDebyeHelmholtz",
      ]) {
        const option = page
          .getByLabel("Thermal model", { exact: true })
          .locator(`option[value="${model}"]`);
        if (await option.isDisabled()) continue;
        await page
          .getByLabel("Thermal model", { exact: true })
          .selectOption(model);
        await ready();
        const check = await page.locator(".pe-eos-page").evaluate((pane) => {
          for (const details of pane.querySelectorAll("details"))
            details.open = true;
          const width = pane.clientWidth,
            scroll = pane.scrollWidth;
          pane.scrollLeft = 9999;
          const bounds = pane.getBoundingClientRect();
          const overflow = [...pane.querySelectorAll("input, select, button")]
            .filter((el) => {
              const rect = el.getBoundingClientRect();
              return (
                rect.width > 0 &&
                (rect.left < bounds.left - 1 || rect.right > bounds.right + 1)
              );
            })
            .map((el) => el.getAttribute("aria-label") || el.textContent);
          return { width, scroll, left: pane.scrollLeft, overflow };
        });
        horizontalChecks.push({ large, width, model, ...check });
        assert.ok(
          check.scroll <= check.width + 1,
          JSON.stringify(horizontalChecks.at(-1)),
        );
        assert.equal(check.left, 0, JSON.stringify(horizontalChecks.at(-1)));
        assert.deepEqual(
          check.overflow,
          [],
          JSON.stringify(horizontalChecks.at(-1)),
        );
      }
      await click("Close");
    }
    // Reopen for the next text-size setup's Close action.
    await click("Edit selected Phase");
  }
  await page
    .getByRole("tab", { name: "Equation of state", exact: true })
    .click();
  const structureBeforeClear = userMaterial.structure.sites;
  await click("Clear all records…");
  await page
    .getByRole("dialog", { name: "Clear all EoS records?", exact: true })
    .waitFor();
  await click("Clear all records");
  await click("Save");
  await click("Reload File");
  userMaterial = (await call("integration_phase_editor", { index: 1 }))
    .phaseEditor;
  assert.deepEqual(userMaterial.references, []);
  assert.deepEqual(userMaterial.structure.sites, structureBeforeClear);
  await edit("K₀", 180);
  await edit("K₀′", 4);
  await click("Add record");
  await edit("EoS name", "New EoS after clearing");
  await click("Save");
  await click("Reload File");
  userMaterial = (await call("integration_phase_editor", { index: 1 }))
    .phaseEditor;
  assert.equal(userMaterial.references.length, 1);
  assert.equal(userMaterial.recordLabel, "New EoS after clearing");
  assert.deepEqual(errors, []);
  await writeFile(
    artifacts +
      `/phase-editor-${engine === webkit ? "webkit" : "chromium"}.json`,
    JSON.stringify({ ok: true, metrics, horizontalChecks, errors }, null, 2),
  );
  console.log(
    JSON.stringify({
      ok: true,
      engine: engine === webkit ? "webkit" : "chromium",
      checks: metrics.length,
      errors,
    }),
  );
} catch (e) {
  console.error(logs);
  throw e;
} finally {
  for (const p of pending.values()) clearTimeout(p.timer);
  await browser?.close();
  host.stdin.end();
}
