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
  await page
    .getByLabel("Phase symmetry", { exact: true })
    .selectOption("orthorhombic");
  await ready();
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
  await edit("theta0", 650);
  assert.equal(
    (await state()).thermalFields.find((f) => f.key === "theta0").value,
    650,
  );
  await page
    .getByLabel("Thermal model", { exact: true })
    .selectOption("AlphaKT");
  await ready();
  await page
    .getByLabel("thermal expansion law", { exact: true })
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
  await page.getByText("Manage EoS records", { exact: true }).click();
  await click("Duplicate as custom");
  assert.equal(
    await page.getByLabel("K₀", { exact: true }).isDisabled(),
    false,
  );
  await edit("K₀", 180);
  await edit("EoS name", "Diagnostic custom EOS");
  assert.equal((await state()).recordLabel, "Diagnostic custom EOS");
  const customReference = (await state()).reference;
  const recordSelector = page.getByLabel("Editor material record", {
    exact: true,
  });
  await recordSelector.focus();
  await recordSelector.selectOption(String(publishedReference));
  await ready();
  assert.ok(await page.getByLabel("K₀", { exact: true }).isDisabled());
  assert.ok(
    await recordSelector.evaluate((el) => el === document.activeElement),
  );
  await recordSelector.selectOption(String(customReference));
  await ready();
  assert.equal(
    Number(await page.getByLabel("K₀", { exact: true }).inputValue()),
    180,
  );
  await click("Set default");
  await click("Delete record…");
  await click("Confirm delete");
  assert.ok(await page.getByLabel("K₀", { exact: true }).isDisabled());
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
  assert.deepEqual(errors, []);
  await writeFile(
    artifacts +
      `/phase-editor-${engine === webkit ? "webkit" : "chromium"}.json`,
    JSON.stringify({ ok: true, metrics, errors }, null, 2),
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
