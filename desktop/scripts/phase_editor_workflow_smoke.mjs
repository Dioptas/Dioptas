// Full built application + isolated Rust worker. Only the OS file chooser is
// replaced with deterministic temporary paths/cancellation; edits use real UI.
import assert from "node:assert/strict";
import { mkdir, mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { chromium, webkit } from "playwright";
import { nativeClient, root } from "./native_backend_client.mjs";
const temp = await mkdtemp(path.join(tmpdir(), "dioptas-phase-workflows-"));
const artifacts = path.join(root, "desktop/artifacts/phase-editor-workflows");
await mkdir(artifacts, { recursive: true });
const receipts = [];
try {
  for (const [name, engine] of [
    ["chromium", chromium],
    ["webkit", webkit],
  ]) {
    let native = nativeClient();
    const browser = await engine.launch({ headless: true });
    const page = await browser.newPage({
      viewport: { width: 1440, height: 1000 },
    });
    page.setDefaultTimeout(10000);
    const calls = [],
      errors = [],
      steps = [];
    let phaseIndex = 0,
      stage = "setup",
      chooser = "save",
      delayEdit = false;
    const file = path.join(temp, `${name}.eosmat`);
    const alternate = path.join(temp, `${name}-copy.eosmat`);
    const invoke = async (action, payload = {}) => {
      calls.push({ action, payload: structuredClone(payload) });
      if (delayEdit && payload.operation === "editor_transaction") {
        delayEdit = false;
        await new Promise((resolve) => setTimeout(resolve, 100));
      }
      if (
        action === "integration_phase_export" &&
        !payload.path &&
        !payload.save_current
      ) {
        if (chooser === "cancel") return { ok: true, cancelled: true };
        payload = {
          ...payload,
          path: chooser === "alternate" ? alternate : file,
        };
      }
      const result = await native.invoke(action, payload);
      assert.equal(result.ok, true, `${action}: ${result.error}`);
      if (result.phaseEditor) phaseIndex = result.phaseEditor.index;
      return result;
    };
    const state = async () =>
      (await invoke("integration_phase_editor", { index: phaseIndex }))
        .phaseEditor;
    const model = async () => (await state()).recordData;
    const step = async (title, fn) => {
      stage = title;
      await fn();
      steps.push(title);
      console.log(`${name}: ${title}`);
    };
    try {
      page.on("pageerror", (e) => errors.push(e.message));
      await invoke("open_image", {
        path: path.join(root, "dioptas/tests/data/CeO2_Pilatus1M.tif"),
      });
      await invoke("open_calibration", {
        path: path.join(root, "dioptas/tests/data/CeO2_Pilatus1M.poni"),
      });
      await invoke("integration_settings", { bins: 64, cake_bins: 12 });
      const catalog = (
        await invoke("integration_phase_catalog", { query: "Au" })
      ).phaseCatalog;
      const gold = catalog.find(
        (m) =>
          m.id === "gold" &&
          m.defaultReference >= 0 &&
          !m.references[m.defaultReference].loadError,
      );
      assert(gold, "Gold source fixture must be loadable");
      await invoke("integration_phase", {
        operation: "load_database",
        material_id: gold.id,
        reference: gold.defaultReference,
      });
      const source = await state();
      await page.exposeFunction("__workflowInvoke", async (a, p) =>
        native.browserResult(await invoke(a, p)),
      );
      await page.addInitScript(() => {
        window.__workflowPending = 0;
        window.pywebview = {
          api: {
            invoke: async (a, p) => {
              window.__workflowPending++;
              try {
                return await window.__workflowInvoke(a, p);
              } finally {
                window.__workflowPending--;
              }
            },
          },
        };
      });
      await page.goto(
        pathToFileURL(path.join(root, "dioptas/desktop/ui/index.html")).href,
      );
      const ready = () =>
        page.waitForFunction(
          () =>
            document.querySelector(".app") &&
            !window.__workflowPending &&
            !document.querySelector(".spin, .pe-number input[aria-busy=true]"),
        );
      const button = (label) =>
        page.getByRole("button", { name: label, exact: true });
      const input = (label) =>
        page.getByRole("textbox", { name: label, exact: true });
      const select = (label) =>
        page.getByRole("combobox", { name: label, exact: true });
      const click = async (label) => {
        await button(label).click();
        await ready();
      };
      const pick = async (label, value) => {
        await select(label).selectOption(value);
        await ready();
      };
      const edit = async (label, value, key = "Enter") => {
        await input(label).fill(value);
        await input(label).press(key);
        await ready();
      };
      const eos = async () => {
        await page
          .getByRole("tab", { name: "Equation of state", exact: true })
          .click();
      };
      const dialog = page.getByRole("dialog", {
        name: "Phase Editor",
        exact: true,
      });
      const reopen = async () => {
        await click("Close");
        await dialog.waitFor({ state: "hidden" });
        await click("Edit selected Phase");
        await eos();
      };
      const traverseHistory = async (action, keyboard = false) => {
        await click("Close");
        await dialog.waitFor({ state: "hidden" });
        assert(
          await button(action).isEnabled(),
          `${action} should be available`,
        );
        const count = calls.length;
        if (keyboard) {
          await button(action).focus();
          await page.keyboard.press(
            action === "Undo" ? "Control+z" : "Control+Shift+z",
          );
          await ready();
        } else await click(action);
        assert(
          calls
            .slice(count)
            .some((c) => c.action.startsWith(action.toLowerCase())),
          `${action} must reach scientific history`,
        );
        await click("Edit selected Phase");
        await eos();
        return state();
      };
      const historyState = (data) => ({
        uid: data.uid,
        references: data.references,
        reference: data.reference,
        defaultReference: data.defaultReference,
        recordData: data.recordData,
        eosType: data.eosType,
        thermalSelection: data.thermalSelection,
        eosFields: data.eosFields,
        thermalFields: data.thermalFields,
        materialFields: data.materialFields,
        lattice: data.lattice,
        reflections: data.reflections,
        structure: data.structure,
      });
      const snapshotStructure = (data) => ({
        lattice: Object.fromEntries(
          ["a0", "b0", "c0", "alpha0", "beta0", "gamma0"].map((k) => [
            k,
            data.lattice[k],
          ]),
        ),
        sites: data.structure.sites,
        formula: data.structure.formula,
        reflections: data.reflections.map((r) => [
          r.h,
          r.k,
          r.l,
          r.intensity,
          r.d0,
        ]),
      });
      await ready();
      await click("Integration");
      await page.getByRole("tab", { name: "Phase", exact: true }).click();
      await click("Edit selected Phase");
      await eos();
      await step(
        "bundled record stays read-only; custom copy is independent",
        async () => {
          assert(await select("Equation of state model").isDisabled());
          assert(await button("Clear all records…").isDisabled());
          await click("Edit a copy");
          const copied = await state();
          assert.notEqual(copied.uid, source.uid);
          assert.equal(copied.editable, true);
          assert(copied.structure.sites.length > 0);
          assert.deepEqual(
            snapshotStructure(copied),
            snapshotStructure(source),
          );
        },
      );
      const structure = snapshotStructure(await state());
      await click("Save As…");
      const documentBeforeClear = JSON.parse(await readFile(file, "utf8"));
      const detectorBefore = await invoke("state");
      let beforeClear, afterClear;
      await step(
        "cancel and Escape from clear leave every record unchanged",
        async () => {
          const before = await state();
          for (const dismiss of ["Cancel", "Escape"]) {
            await click("Clear all records…");
            const confirmation = page.getByRole("dialog", {
              name: "Clear all EoS records?",
              exact: true,
            });
            await confirmation.waitFor();
            if (dismiss === "Escape") await confirmation.press("Escape");
            else
              await confirmation
                .getByRole("button", { name: "Cancel", exact: true })
                .click();
            await confirmation.waitFor({ state: "hidden" });
            assert.deepEqual((await state()).recordData, before.recordData);
            assert.deepEqual((await state()).references, before.references);
            assert(await dialog.isVisible());
          }
        },
      );
      await step(
        "clear every EOS preserves lattice, atoms and reflections",
        async () => {
          beforeClear = await state();
          await click("Clear all records…");
          await click("Clear all records");
          const empty = await state();
          afterClear = empty;
          assert.equal(empty.references.length, 0);
          assert.equal(empty.recordData, null);
          // With no selected EOS, V0 comes from the retained cubic lattice.
          assert.equal(empty.lattice.v0, empty.lattice.a0 ** 3);
          assert.deepEqual(snapshotStructure(empty), structure);
          for (const label of [
            "Delete record…",
            "Duplicate as custom",
            "Set default",
            "Clear all records…",
          ])
            assert(await button(label).isDisabled(), label);
          assert(await button("Add record").isEnabled());
        },
      );
      await step(
        "undo/redo clear-all restores every record and the selected/default EOS",
        async () => {
          const restored = await traverseHistory("Undo");
          assert.deepEqual(historyState(restored), historyState(beforeClear));
          assert(await select("Equation of state model").isEnabled());
          assert.equal(
            await select("Editor material record").inputValue(),
            String(beforeClear.reference),
          );
          // A separate export verifies every restored record, not only the selection.
          chooser = "alternate";
          await click("Save As…");
          const restoredDocument = JSON.parse(
            await readFile(alternate, "utf8"),
          );
          assert.deepEqual(
            restoredDocument.eos_records,
            documentBeforeClear.eos_records,
          );
          assert.deepEqual(
            restoredDocument.datasets,
            documentBeforeClear.datasets,
          );
          chooser = "save";
          assert.deepEqual(
            historyState(await traverseHistory("Redo")),
            historyState(afterClear),
          );
          assert(await button("Add record").isEnabled());
          assert(await button("Delete record…").isDisabled());
        },
      );
      await step(
        "keyboard undo/redo repeats clear-all without losing records or structure",
        async () => {
          for (let repeat = 0; repeat < 2; repeat++) {
            assert.deepEqual(
              historyState(await traverseHistory("Undo", true)),
              historyState(beforeClear),
            );
            assert.deepEqual(
              historyState(await traverseHistory("Redo", true)),
              historyState(afterClear),
            );
          }
        },
      );
      await step(
        "empty EOS material saves, reloads and creates valid K0=100 record",
        async () => {
          await click((await state()).canSaveCurrent ? "Save" : "Save…");
          assert.equal(
            JSON.parse(await readFile(file, "utf8")).eos_records.length,
            0,
          );
          await click("Reload File");
          assert.equal((await state()).references.length, 0);
          await click("Add record");
          assert.equal((await model()).eos.parameters.K0, 100);
          assert.equal((await state()).references.length, 1);
          assert.deepEqual(snapshotStructure(await state()), structure);
        },
      );
      await step(
        "invalid numeric drafts cannot save; Escape restores without backend edits",
        async () => {
          const before = await model();
          for (const invalid of ["", "nonsense", "Infinity", "-1"]) {
            const count = calls.length;
            await edit("K0", invalid);
            assert.equal(
              await input("K0").getAttribute("aria-invalid"),
              "true",
            );
            await click("Save");
            assert.match(
              await dialog.locator("footer [role=status]").innerText(),
              /invalid value/,
            );
            assert.equal(
              calls
                .slice(count)
                .filter((c) => c.action === "integration_phase_export").length,
              0,
            );
            assert.deepEqual(await model(), before);
            await input("K0").press("Escape");
            assert.equal(Number(await input("K0").inputValue()), 100);
          }
        },
      );
      await step(
        "zero modulus rejection rolls back; valid edits recover immediately",
        async () => {
          const before = await model();
          await edit("K0", "0");
          assert.match(
            await dialog.locator("footer [role=status]").innerText(),
            /Edit not applied/,
          );
          assert.deepEqual(await model(), before);
          assert.equal(Number(await input("K0").inputValue()), 100);
          await edit("K0", "140");
          assert.equal((await model()).eos.parameters.K0, 140);
        },
      );
      await step(
        "rapid Enter/Tab commits once; Close waits for a pending edit",
        async () => {
          const count = calls.length;
          delayEdit = true;
          await input("K0").fill("145.123456789");
          await input("K0").press("Enter");
          await input("K0").press("Tab");
          await button("Close").click();
          await dialog.waitFor({ state: "hidden" });
          await ready();
          assert.equal((await model()).eos.parameters.K0, 145.123456789);
          assert.equal(
            calls
              .slice(count)
              .filter(
                (c) =>
                  c.payload.edit_operation === "editor_parameter" &&
                  c.payload.parameter === "k0",
              ).length,
            1,
          );
          await click("Edit selected Phase");
          await eos();
          assert.equal(Number(await input("K0").inputValue()), 145.123456789);
        },
      );
      await step(
        "duplicate, switch, default and delete keep records independent",
        async () => {
          const original = await model();
          await click("Duplicate as custom");
          assert.notEqual((await model()).identifier, original.identifier);
          await edit("K0", "190");
          await click("Set default");
          const second = await state();
          assert.equal(second.defaultReference, second.reference);
          await pick("Editor material record", "0");
          assert.equal(
            (await model()).eos.parameters.K0,
            original.eos.parameters.K0,
          );
          await click("Delete record…");
          await page
            .getByRole("dialog", { name: "Delete EoS record?", exact: true })
            .getByRole("button", { name: "Cancel", exact: true })
            .click();
          assert.equal((await state()).references.length, 2);
          await pick("Editor material record", "1");
          assert.equal((await model()).eos.parameters.K0, 190);
          await click("Delete record…");
          await click("Confirm delete");
          assert.equal((await state()).references.length, 1);
          assert.equal(
            (await model()).eos.parameters.K0,
            original.eos.parameters.K0,
          );
          assert.deepEqual(snapshotStructure(await state()), structure);
        },
      );
      await step(
        "delete-last undo/redo and add-record history restore exact models",
        async () => {
          const beforeDelete = await state();
          await click("Delete record…");
          await click("Confirm delete");
          const deleted = await state();
          assert.equal(deleted.references.length, 0);
          assert.deepEqual(
            historyState(await traverseHistory("Undo")),
            historyState(beforeDelete),
          );
          // Rejected edits must not discard the redo of the deletion.
          await edit("K0", "0");
          assert.match(
            await dialog.locator("footer [role=status]").innerText(),
            /Edit not applied/,
          );
          assert.deepEqual(
            historyState(await traverseHistory("Redo")),
            historyState(deleted),
          );
          await click("Add record");
          const added = await state();
          assert.equal(added.recordData.eos.parameters.K0, 100);
          assert.deepEqual(
            historyState(await traverseHistory("Undo")),
            historyState(deleted),
          );
          assert.deepEqual(
            historyState(await traverseHistory("Undo")),
            historyState(beforeDelete),
          );
          assert.deepEqual(
            historyState(await traverseHistory("Redo")),
            historyState(deleted),
          );
          assert.deepEqual(
            historyState(await traverseHistory("Redo")),
            historyState(added),
          );
        },
      );
      await step(
        "a new edit after undoing add-record discards the obsolete redo branch",
        async () => {
          const added = await state();
          assert.equal(
            (await traverseHistory("Undo", true)).references.length,
            0,
          );
          await click("Add record");
          assert.equal((await model()).eos.parameters.K0, 100);
          await edit("K0", "125");
          await click("Close");
          await dialog.waitFor({ state: "hidden" });
          assert(await button("Redo").isDisabled());
          await click("Edit selected Phase");
          await eos();
          assert.equal((await model()).eos.parameters.K0, 125);
          assert.deepEqual(
            snapshotStructure(await state()),
            snapshotStructure(added),
          );
        },
      );
      await step(
        "delete every record individually, undo all deletions, then redo them",
        async () => {
          for (const value of [150, 175]) {
            await click("Duplicate as custom");
            await edit("K0", String(value));
          }
          await click("Set default");
          const checkpoints = [await state()];
          while ((await state()).references.length) {
            await click("Delete record…");
            await click("Confirm delete");
            checkpoints.push(await state());
          }
          assert.equal(checkpoints.length, 4);
          for (let i = checkpoints.length - 2; i >= 0; i--)
            assert.deepEqual(
              historyState(await traverseHistory("Undo")),
              historyState(checkpoints[i]),
            );
          for (let i = 1; i < checkpoints.length; i++)
            assert.deepEqual(
              historyState(await traverseHistory("Redo")),
              historyState(checkpoints[i]),
            );
          assert(await button("Add record").isEnabled());
          await click("Add record");
          assert.equal((await model()).eos.parameters.K0, 100);
        },
      );
      await step(
        "model switches update equations; unsupported models stay disabled",
        async () => {
          await page
            .getByRole("checkbox", {
              name: "Show model explanations",
              exact: true,
            })
            .check();
          for (const [value, count] of [
            ["Vinet", 3],
            ["BM3", 2],
          ]) {
            await pick("Equation of state model", value);
            assert.equal((await model()).eos.type, value);
            assert.equal(
              await page.locator("#pe-eos-model-help math").count(),
              count,
            );
          }
          const option = select("Thermal model").locator(
            'option[value="SoundVelocityDebyeHelmholtz"]',
          );
          assert(await option.evaluate((option) => option.disabled));
          assert.match(await option.getAttribute("title"), /not implemented/);
          await pick("Thermal model", "Dewaele2006");
          const before = await model();
          const beta = (await state()).thermalFields.find(
            (f) => f.key === "beta",
          );
          await edit(beta.label, "0");
          assert.deepEqual(await model(), before);
          assert.match(
            await dialog.locator("footer [role=status]").innerText(),
            /Edit not applied/,
          );
          assert.equal(
            Number(await input(beta.label).inputValue()),
            before.thermal.parameters.beta,
          );
        },
      );
      await step(
        "optional Cvmax clears to 3nR and q=0 remains usable",
        async () => {
          await pick("Thermal model", "MieGruneisenDebye");
          await edit("Cᵥ,max", "42");
          assert.equal((await model()).thermal.parameters.Cvmax, 42);
          await edit("Cᵥ,max", "", "Tab");
          assert.equal((await model()).thermal.parameters.Cvmax, undefined);
          assert.equal(await input("Cᵥ,max").inputValue(), "");
          const q = (await state()).thermalFields.find((f) => f.key === "q");
          await edit(q.label, "0");
          assert.equal((await model()).thermal.parameters.q, 0);
        },
      );
      await step(
        "double-Debye Tr/default clearing follows displayed conventions",
        async () => {
          await pick("Thermal model", "DoubleDebyeHelmholtz");
          const tr = (await state()).thermalFields.find((f) => f.key === "Tr");
          await edit(tr.label, "500");
          assert.equal((await model()).thermal.parameters.Tr, 500);
          assert.match(
            (
              await page
                .locator("#pe-thermal-model-help annotation")
                .allTextContents()
            ).join(" "),
            /F_\{\\rm ion\}\(V,T_r\)/,
          );
          await edit(tr.label, "", "Tab");
          assert.equal((await model()).thermal.parameters.Tr, undefined);
          assert(
            !(
              await page
                .locator("#pe-thermal-model-help annotation")
                .allTextContents()
            )
              .join(" ")
              .includes("F_{\\rm ion}(V,T_r)"),
          );
          for (const key of ["Ve", "alpha0", "kappa", "phi0"]) {
            const field = (await state()).thermalFields.find(
              (f) => f.key === key,
            );
            await edit(field.label, "");
            await input(field.label).press("Tab");
            await ready();
            assert.equal(
              (await model()).thermal.parameters[key],
              field.default,
            );
            assert.equal(
              Number(await input(field.label).inputValue()),
              field.default,
              `${key} must display its applied default after blur`,
            );
          }
        },
      );
      await step(
        "save cancellation, pending blur, overwrite and Save As preserve exact models",
        async () => {
          chooser = "cancel";
          const before = await state();
          await click("Save As…");
          assert.deepEqual((await state()).recordData, before.recordData);
          assert.equal((await state()).filename, before.filename);
          // Click Save while the numeric draft still has focus: blur must apply first.
          await input("K0").fill("155.987654321");
          await click("Save");
          const saved = JSON.parse(await readFile(file, "utf8"));
          assert.equal(saved.eos_records[0].eos.parameters.K0, 155.987654321);
          chooser = "alternate";
          await click("Save As…");
          assert.equal((await state()).filename, alternate);
          assert.equal(
            JSON.parse(await readFile(alternate, "utf8")).eos_records[0].eos
              .parameters.K0,
            155.987654321,
          );
          await edit("K0", "180");
          await click("Reload File");
          assert.equal((await model()).eos.parameters.K0, 155.987654321);
          await reopen();
          assert(
            await page
              .getByRole("checkbox", {
                name: "Show model explanations",
                exact: true,
              })
              .isChecked(),
          );
          assert.equal(
            await select("Thermal model").inputValue(),
            "DoubleDebyeHelmholtz",
          );
          assert.equal(Number(await input("K0").inputValue()), 155.987654321);
        },
      );
      await step(
        "phase edits preserve detector pixels, integration arrays and source material",
        async () => {
          const after = await invoke("state");
          for (const key of ["rawImage", "image", "cake"])
            assert.deepEqual(after[key], detectorBefore[key], key);
          const { phaseLines: oldLines, ...oldPattern } =
            detectorBefore.pattern;
          const { phaseLines: newLines, ...newPattern } = after.pattern;
          assert.deepEqual(
            newPattern,
            oldPattern,
            "Integrated arrays must stay unchanged",
          );
          assert.deepEqual(
            newLines.filter((p) => p.phaseIndex === 0),
            oldLines.filter((p) => p.phaseIndex === 0),
          );
          assert.notDeepEqual(
            newLines.filter((p) => p.phaseIndex === 1).map((p) => p.x),
            oldLines.filter((p) => p.phaseIndex === 1).map((p) => p.x),
            "Edited phase markers must update",
          );
          const original = (
            await invoke("integration_phase_editor", { index: 0 })
          ).phaseEditor;
          assert.deepEqual(original.recordData, source.recordData);
          assert.deepEqual(
            snapshotStructure(original),
            snapshotStructure(source),
          );
          assert.deepEqual(errors, []);
        },
      );
      await step(
        "fresh worker and app reopen reproduce the saved EOSMAT model",
        async () => {
          const saved = JSON.parse(await readFile(alternate, "utf8"));
          native.close();
          native = nativeClient();
          phaseIndex = 0;
          await invoke("open_image", {
            path: path.join(root, "dioptas/tests/data/CeO2_Pilatus1M.tif"),
          });
          await invoke("open_calibration", {
            path: path.join(root, "dioptas/tests/data/CeO2_Pilatus1M.poni"),
          });
          await invoke("integration_settings", { bins: 64, cake_bins: 12 });
          await invoke("integration_phase", {
            operation: "load",
            path: alternate,
          });
          await page.reload();
          await ready();
          await click("Integration");
          await page.getByRole("tab", { name: "Phase", exact: true }).click();
          await click("Edit selected Phase");
          await eos();
          assert.deepEqual(await model(), saved.eos_records[0]);
          assert.deepEqual(snapshotStructure(await state()), structure);
          assert.equal(
            await select("Thermal model").inputValue(),
            "DoubleDebyeHelmholtz",
          );
          assert.equal(Number(await input("K0").inputValue()), 155.987654321);
          assert(
            await page
              .getByRole("checkbox", {
                name: "Show model explanations",
                exact: true,
              })
              .isChecked(),
          );
        },
      );
      await step(
        "GUI pressure and temperature changes update the calculated volume",
        async () => {
          const initial = await state();
          await click("Close");
          const pressure = page.getByLabel("Phase 1 pressure (GPa)", {
            exact: true,
          });
          await pressure.fill("10");
          await pressure.press("Enter");
          await ready();
          const compressed = await state();
          assert.equal(compressed.pressure, 10);
          assert(compressed.lattice.v < initial.lattice.v);
          const temperature = page.getByLabel("Phase 1 temperature (K)", {
            exact: true,
          });
          await temperature.fill("900");
          await temperature.press("Enter");
          await ready();
          const heated = await state();
          assert.equal(heated.temperature, 900);
          assert(heated.lattice.v > compressed.lattice.v);
          await click("Edit selected Phase");
          assert.equal(
            Number(
              await page
                .getByLabel("Current lattice v", { exact: true })
                .inputValue(),
            ),
            heated.lattice.v,
          );
          assert.deepEqual(errors, []);
        },
      );
      await page.screenshot({
        path: path.join(artifacts, `${name}-completed.png`),
      });
      receipts.push({ name, steps, pageErrors: errors });
    } catch (error) {
      await writeFile(
        path.join(artifacts, `${name}-history-debug.json`),
        JSON.stringify(
          {
            stage,
            calls: calls.slice(-25),
            native: await native.invoke("state"),
          },
          null,
          2,
        ),
      );
      await page
        .screenshot({ path: path.join(artifacts, `${name}-failure.png`) })
        .catch(() => {});
      await writeFile(
        path.join(artifacts, `${name}-failure.html`),
        await page.content(),
      ).catch(() => {});
      throw new Error(`${name}: ${stage}: ${error.message}`, { cause: error });
    } finally {
      await browser.close();
      native.close();
    }
  }
  await writeFile(
    path.join(artifacts, "validation.json"),
    JSON.stringify(receipts, null, 2),
  );
  console.log(JSON.stringify(receipts));
} finally {
  await rm(temp, { recursive: true, force: true });
}
