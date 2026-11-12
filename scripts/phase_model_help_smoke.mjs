import assert from "node:assert/strict";
import { mkdir, writeFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { createServer } from "vite";
import { chromium, webkit } from "playwright";
import { nativeClient, root } from "./native_backend_client.mjs";
const desktop = fileURLToPath(new URL("../", import.meta.url));
const artifacts = new URL("../artifacts/phase-model-help/", import.meta.url);
await mkdir(artifacts, { recursive: true });
const server = await createServer({
  root: desktop,
  server: { host: "127.0.0.1", port: 0 },
});
await server.listen();
const receipts = [];
try {
  for (const [name, engine] of [
    ["chromium", chromium],
    ["webkit", webkit],
  ]) {
    const native = nativeClient();
    const browser = await engine.launch({ headless: true });
    try {
      const invoke = async (action, args) => {
        const response = await native.invoke(action, args);
        assert(response.ok, response.error);
        return native.browserResult(response);
      };
      await invoke("integration_phase", {
        operation: "load",
        path: root + "/tests/data/jcpds/mo.jcpds",
      });
      await invoke("integration_phase", {
        operation: "editor_record",
        index: 0,
        action: "add",
      });
      await invoke("integration_phase", {
        operation: "editor_thermal_type",
        index: 0,
        value: "MieGruneisenDebye",
      });
      const data = (await invoke("integration_phase_editor", { index: 0 }))
        .phaseEditor;
      const page = await browser.newPage({
        viewport: { width: 1440, height: 1000 },
      });
      const errors = [];
      page.on("pageerror", (error) => errors.push(error.message));
      await page.exposeFunction("__modelInvoke", invoke);
      await page.goto(
        `${server.resolvedUrls.local[0]}scripts/rendering_fixture.html`,
      );
      await page.waitForFunction(() => window.fixture);
      const mappings = await page.evaluate(async (data) => {
        await import("/src/integrationPhaseControls.css");
        const { PhaseEditor } = await import("/src/PhaseEditor.tsx");
        const { modelHelp, choiceHelp } =
          await import("/src/phaseModelHelp.ts");
        const { phaseParameterHelp } =
          await import("/src/phaseParameterHelp.ts");
        const generated = (await import("/src/phaseEquations.generated.json"))
          .default;
        for (const expressions of Object.values(generated))
          for (const equation of expressions) {
            const xml = new DOMParser().parseFromString(
              equation.math,
              "application/xml",
            );
            if (xml.querySelector("parsererror") || !xml.querySelector("math"))
              throw Error("Invalid generated MathML");
          }
        const schema = await (
          await fetch("/backend/resources/phase-editor-schema.json")
        ).json();
        const urls = new Set();
        let choices = 0,
          parameters = 0,
          modelsWithEquations = 0;
        for (const [kind, models] of [
          ["eos", schema.eos],
          ["thermal", schema.thermal],
        ])
          for (const [name, spec] of Object.entries(models)) {
            const help = modelHelp(kind, name);
            if (help.description.startsWith("See the model definition"))
              throw Error(`Missing model help: ${name}`);
            urls.add(help.url);
            if (name === "SoundVelocityDebyeHelmholtz") {
              if (help.equations?.length)
                throw Error("Unsupported model has equations");
            } else {
              if (!help.equations?.length)
                throw Error(`Missing model equations: ${name}`);
              modelsWithEquations++;
            }
            const numericFields =
              kind === "thermal"
                ? spec.fields.filter((f) => !f.choices.length)
                : spec.map((key) => ({
                    key:
                      {
                        K0: "k0",
                        K0_prime: "k0p0",
                        K0_double_prime: "k0pp0",
                        P0: "p0",
                        Z: "z",
                      }[key] ?? key,
                    label: key,
                    unit: "",
                  }));
            for (const field of numericFields) {
              const help = phaseParameterHelp(field, {
                eosType: kind === "eos" ? name : "BM3",
                thermalType: kind === "thermal" ? name : "none",
                fields: spec.fields ?? [],
                blankAllowed: field.required === false,
              });
              if (
                !help.description ||
                help.description.startsWith("Coefficient used by")
              )
                throw Error(
                  `Missing parameter explanation: ${name}/${field.key}`,
                );
              if (!help.note.includes("Units:"))
                throw Error("Parameter units missing");
              urls.add(help.url);
              parameters++;
            }
            for (const field of spec.fields ?? [])
              for (const value of field.choices ?? []) {
                const help = choiceHelp(field.key, value);
                if (!help)
                  throw Error(`Missing choice help: ${field.key}/${value}`);
                urls.add(help.url);
                choices++;
                for (const equation of help.equations ?? []) {
                  const xml = new DOMParser().parseFromString(
                    equation.math,
                    "application/xml",
                  );
                  if (
                    xml.querySelector("parsererror") ||
                    xml.documentElement.localName !== "math"
                  )
                    throw Error("Invalid MathML");
                }
              }
          }
        // Regression checks for source-audit findings and configuration-dependent help.
        const mathText = (help) =>
          new DOMParser().parseFromString(
            `<div>${(help.equations ?? []).map((e) => e.math).join("")}</div>`,
            "application/xml",
          ).documentElement.textContent;
        const dewaele = modelHelp("thermal", "Dewaele2006", {
          thermal_pressure_reference: "absolute_zero",
          zero_point_pressure: "included",
        });
        if (!mathText(dewaele).includes("ZP"))
          throw Error("Missing zero-point pressure equation");
        const omitted = modelHelp("thermal", "Dewaele2006", {
          thermal_pressure_reference: "absolute_zero",
        });
        if (mathText(omitted).includes("ZP"))
          throw Error("Incorrect zero-point pressure addition");
        for (const model of ["Dewaele2006", "DorogokupetsOganov2007"]) {
          if (mathText(modelHelp("thermal", model)).includes("β=0"))
            throw Error("Unsupported beta=0 limit");
        }
        if (!mathText(modelHelp("thermal", "alphakt")).includes("selected"))
          throw Error("Legacy correction must use selected EOS");
        const { React } = window.fixture;
        function Editor({ initial = data }) {
          const [value, setValue] = React.useState(initial);
          window.editorHelpData = value;
          window.setHelpEditorData = setValue;
          return React.createElement(PhaseEditor, {
            data: value,
            ready: true,
            onData: setValue,
            onClose() {},
            run: async (action, args, message, callback) => {
              window.modelPending = (window.modelPending ?? 0) + 1;
              try {
                callback?.(await window.__modelInvoke(action, args));
              } finally {
                window.modelPending--;
              }
            },
          });
        }
        document.getElementById("fixture").classList.add("app");
        window.paint(Editor, {});
        window.remountHelpEditor = () =>
          window.paint(Editor, {
            key: crypto.randomUUID(),
            initial: window.editorHelpData,
          });
        return { choices, parameters, modelsWithEquations, urls: [...urls] };
      }, data);
      const ready = () => page.waitForFunction(() => !window.modelPending);
      await page
        .getByRole("tab", { name: "Equation of state", exact: true })
        .click();
      const select = (label) =>
        page.getByRole("combobox", { name: label, exact: true });
      const lawHelp = page.locator("#pe-choice-debye_temperature_law-help");
      const explanations = page.getByRole("checkbox", {
        name: "Show model explanations",
        exact: true,
      });
      assert.equal(
        await explanations.isChecked(),
        false,
        "Model explanations should start collapsed",
      );
      assert.equal(await page.locator(".pe-model-help math").count(), 0);
      assert.equal(
        await lawHelp.getByRole("link").count(),
        1,
        "Manual links must remain available when explanations are hidden",
      );
      await page
        .getByText(
          "High-temperature molar Cᵥ limit. Blank = 3nR; n = atoms per formula unit.",
          { exact: true },
        )
        .waitFor();
      assert.match(
        await page.getByLabel("Cᵥ,max", { exact: true }).getAttribute("title"),
        /blank uses default 3nR/,
      );
      assert(
        await page
          .getByRole("button", { name: "Save…", exact: true })
          .isVisible(),
      );
      const beforeToggle = await page.evaluate(() =>
        JSON.stringify(window.editorHelpData),
      );
      await explanations.check();
      assert.equal(
        await page.evaluate(() => JSON.stringify(window.editorHelpData)),
        beforeToggle,
        "Help visibility must not edit model parameters",
      );
      const cvHelp = page.locator("#pe-choice-Cvmax-help");
      assert.equal(await cvHelp.locator("math").count(), 2);
      assert.match(await cvHelp.innerText(), /constant volume/);
      assert.match(await cvHelp.innerText(), /3nR/);
      await explanations.uncheck();
      assert.equal(await lawHelp.locator("math").count(), 0);
      assert.equal(await cvHelp.getByRole("link").count(), 0);
      await explanations.check();
      assert.equal(
        await page.locator("#pe-choice-k0-help .pe-model-help").count(),
        1,
      );
      assert.match(
        await page.locator("#pe-choice-gamma0-help").innerText(),
        /couples vibrational energy/,
      );
      assert.match(
        await page.locator("#pe-choice-theta0-help").innerText(),
        /energy scale/,
      );
      await select("Equation of state model").selectOption("Vinet");
      await ready();
      await page
        .locator("#pe-eos-model-help")
        .getByText("Vinet", { exact: true })
        .waitFor();
      assert.equal(await page.locator("#pe-eos-model-help math").count(), 3);
      assert.match(
        await page
          .locator("#pe-eos-model-help annotation")
          .allTextContents()
          .then((items) => items.join(" ")),
        /exp/,
      );
      await select("Equation of state model").selectOption("BM3");
      await ready();
      await page
        .locator("#pe-eos-model-help")
        .getByText("BM3", { exact: true })
        .waitFor();
      assert.equal(await page.locator("#pe-eos-model-help math").count(), 2);
      // Plain fields must leave both their value and ordinary scrolling untouched.
      const plainK = page.getByLabel("K0", { exact: true });
      const beforeWheel = await page.evaluate(() =>
        JSON.stringify(window.editorHelpData),
      );
      for (const label of ["K0", "γ₀", "Reflection 1 intensity"]) {
        const field = page.getByRole("textbox", { name: label, exact: true });
        const before = await field.inputValue();
        for (const focus of [false, true]) {
          if (focus) await field.focus();
          const consumed = await field.evaluate((el) => {
            const event = new WheelEvent("wheel", {
              deltaY: 120,
              bubbles: true,
              cancelable: true,
            });
            el.dispatchEvent(event);
            return event.defaultPrevented;
          });
          assert.equal(consumed, false, `${label} must allow scrolling`);
          assert.equal(await field.inputValue(), before);
        }
      }
      assert.equal(
        await page.evaluate(() => JSON.stringify(window.editorHelpData)),
        beforeWheel,
      );
      await plainK.scrollIntoViewIfNeeded();
      await plainK.focus();
      await plainK.hover();
      const scrollTop = await page
        .locator(".pe-eos-page")
        .evaluate((el) => el.scrollTop);
      await page.mouse.wheel(0, 180);
      await page.waitForFunction(
        (top) => document.querySelector(".pe-eos-page").scrollTop > top,
        scrollTop,
      );
      assert.equal(
        await page.evaluate(() => JSON.stringify(window.editorHelpData)),
        beforeWheel,
      );
      await page
        .getByRole("tab", { name: "Volume & structure", exact: true })
        .click();
      const spin = page.getByLabel("a₀", { exact: true });
      const originalA = Number(await spin.inputValue());
      for (const [delta, expected] of [
        [-100, originalA + 0.01],
        [100, originalA],
      ]) {
        const consumed = await spin.evaluate((el, deltaY) => {
          const event = new WheelEvent("wheel", {
            deltaY,
            bubbles: true,
            cancelable: true,
          });
          el.dispatchEvent(event);
          return event.defaultPrevented;
        }, delta);
        assert.equal(consumed, true, "Visible spinboxes retain wheel stepping");
        await page.waitForFunction(
          (expected) =>
            Math.abs(window.editorHelpData.lattice.a0 - expected) < 1e-8,
          expected,
        );
        await ready();
      }
      await page
        .getByRole("tab", { name: "Equation of state", exact: true })
        .click();
      await lawHelp
        .getByText("Integrated Grüneisen law", { exact: true })
        .waitFor();
      assert.equal(await lawHelp.locator("math").count(), 3);
      assert.match(await lawHelp.textContent(), /q = 0|default Debye/);
      await select("Debye temperature law").selectOption("variable_exponent");
      await lawHelp
        .getByText("Variable-exponent law", { exact: true })
        .waitFor();
      await ready();
      assert.match(
        await lawHelp.textContent(),
        /not the logarithmic derivative/,
      );
      assert.equal(
        await lawHelp.locator("a").getAttribute("href"),
        "https://peritheos.readthedocs.io/en/latest/equation-reference/#variable-exponent-debye-temperature-law",
      );
      assert.equal(
        (await page.evaluate(() => window.editorHelpData)).thermalFields.find(
          (f) => f.key === "debye_temperature_law",
        ).value,
        "variable_exponent",
      );
      for (const size of ["normal", "large"]) {
        await page.evaluate((size) => {
          document.querySelector(".app").dataset.textSize = size;
        }, size);
        await lawHelp.scrollIntoViewIfNeeded();
        assert(
          await lawHelp
            .locator("math")
            .first()
            .evaluate((el) => el.getBoundingClientRect().height > 12),
        );
        assert(
          await page
            .locator(".pe-eos-page")
            .evaluate((el) => el.scrollWidth <= el.clientWidth + 1),
        );
        await page.screenshot({
          path: fileURLToPath(new URL(`${name}-${size}-debye.png`, artifacts)),
        });
      }
      // A native link invokes only the host browser launcher, preserving drafts/data.
      const beforeLink = await page.evaluate(() =>
        JSON.stringify(window.editorHelpData),
      );
      await page.evaluate(() => {
        window.isTauri = true;
        window.__TAURI_INTERNALS__ = {
          invoke: async (command, args) => {
            window.manualCall = { command, args };
          },
        };
      });
      await lawHelp.getByRole("link").click();
      assert.deepEqual(await page.evaluate(() => window.manualCall), {
        command: "open_peritheos_manual",
        args: { url: await lawHelp.locator("a").getAttribute("href") },
      });
      assert.equal(
        await page.evaluate(() => JSON.stringify(window.editorHelpData)),
        beforeLink,
      );
      await page.evaluate(() => {
        window.__TAURI_INTERNALS__.invoke = async () => {
          throw Error("Browser launch failed");
        };
      });
      await lawHelp.getByRole("link").click();
      await lawHelp
        .getByRole("alert")
        .filter({ hasText: "Browser launch failed" })
        .waitFor();
      await page.evaluate(() => {
        window.isTauri = false;
        delete window.__TAURI_INTERNALS__;
      });
      // Choice help tracks successful model edits and the selected reference convention.
      await select("Pressure reference").selectOption("absolute_zero");
      await ready();
      await page
        .locator("#pe-choice-thermal_pressure_reference-help")
        .getByText("Absolute-zero cold curve", { exact: true })
        .waitFor();
      await select("Thermal model").selectOption("Dewaele2006");
      await ready();
      const zeroPoint = page.getByLabel("Zero-point pressure", { exact: true });
      await zeroPoint.waitFor();
      assert.equal(await zeroPoint.inputValue(), "omitted");
      assert.equal(await zeroPoint.getAttribute("readonly"), "");
      await select("Thermal model").selectOption("AlphaKT");
      await ready();
      await select("Expansion law").selectOption(
        "linear_reference_temperature",
      );
      await ready();
      await page
        .locator("#pe-choice-thermal_expansion_law-help")
        .getByText("Linear from reference temperature", { exact: true })
        .waitFor();
      await select("Reference volume law").selectOption("berman");
      await ready();
      await page.getByText(/Edit not applied:/).waitFor();
      assert.equal(
        await select("Reference volume law").inputValue(),
        "integrated_expansivity",
      );
      assert.equal(
        await page
          .locator("#pe-choice-reference_volume_law-help")
          .getByText("Integrated expansivity", { exact: true })
          .count(),
        1,
        "Rejected edits must retain help for the accepted law",
      );
      await select("Expansion law").selectOption("linear_temperature");
      await ready();
      await select("Reference volume law").selectOption("berman");
      await ready();
      await page
        .locator("#pe-choice-reference_volume_law-help")
        .getByText("Berman reference volume", { exact: true })
        .waitFor();
      await page.getByLabel("∂K₀/∂T", { exact: true }).fill("0");
      await page.keyboard.press("Tab");
      await ready();
      await select("Bulk modulus law").selectOption("reciprocal_cubic");
      await ready();
      const cubic = page.locator("#pe-choice-bulk_modulus_law-help");
      await cubic
        .getByText("Cubic reciprocal bulk modulus", { exact: true })
        .waitFor();
      assert.equal(await cubic.locator("math").count(), 2);
      assert.equal(
        await page
          .locator("#pe-choice-thermal_expansion_law-help math")
          .count(),
        0,
        "Direct volume laws must not display an unused standalone expansivity equation",
      );
      await cubic.scrollIntoViewIfNeeded();
      await page.screenshot({
        path: fileURLToPath(new URL(`${name}-alpha-laws.png`, artifacts)),
      });
      await page.evaluate(() =>
        window.setHelpEditorData({
          ...window.editorHelpData,
          eosEditable: false,
        }),
      );
      await page.waitForFunction(
        () => document.querySelector('[aria-label="Thermal model"]').disabled,
      );
      assert(
        await cubic.getByRole("link").isVisible(),
        "Read-only records must retain documentation access",
      );
      await page.evaluate(() => window.remountHelpEditor());
      await page
        .getByRole("tab", { name: "Equation of state", exact: true })
        .click();
      assert.equal(
        await explanations.isChecked(),
        true,
        "Explanation preference must survive reopening the editor",
      );
      await explanations.uncheck();
      await page.evaluate(() => window.remountHelpEditor());
      await page
        .getByRole("tab", { name: "Equation of state", exact: true })
        .click();
      assert.equal(await explanations.isChecked(), false);
      assert.deepEqual(errors, []);
      receipts.push({
        name,
        ...mappings,
        nativeLinkPreservesEditor: true,
        equationsRendered: true,
        liveChoices: true,
        rememberedHelpToggle: true,
        cvmaxExplained: true,
        allParametersExplained: true,
        wheelOnlyOnSpinboxes: true,
      });
    } finally {
      await browser.close();
      await native.close();
    }
  }
  await writeFile(
    new URL("validation.json", artifacts),
    JSON.stringify(receipts, null, 2),
  );
  console.log(
    JSON.stringify(
      receipts.map(({ urls, ...receipt }) => ({
        ...receipt,
        manualSections: urls.length,
      })),
    ),
  );
} finally {
  await server.close();
}
