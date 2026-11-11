import assert from "node:assert/strict";
import { mkdtemp, mkdir, readFile, writeFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { chromium, webkit } from "playwright";
import { nativeClient, root } from "./native_backend_client.mjs";
import { nativeEditorEvents } from "./phase_metadata_native_events.mjs";
const temp = await mkdtemp(path.join(tmpdir(), "dioptas-eos-metadata-"));
const artifacts = path.join(root, "desktop/artifacts/phase-metadata");
await mkdir(artifacts, { recursive: true });
const receipts = [];
try {
  for (const [engineName, engine] of [
    ["chromium", chromium],
    ["webkit", webkit],
  ]) {
    const native = nativeClient();
    const browser = await engine.launch({ headless: true });
    try {
      const file = path.join(temp, `${engineName}.eosmat`),
        project = path.join(temp, `${engineName}.dio`);
      const calls = [],
        errors = [];
      let rejectNext = false;
      const invoke = async (action, payload = {}) => {
        calls.push([action, payload]);
        if (rejectNext && payload.edit_operation === "editor_metadata") {
          rejectNext = false;
          return { ok: false, error: "Injected metadata storage failure" };
        }
        if (action === "integration_phase_export" && !payload.path)
          payload = { ...payload, path: file };
        const result = await native.invoke(action, payload);
        assert.equal(result.ok, true, `${action}: ${result.error}`);
        return result;
      };
      const editState = async () =>
        (await invoke("integration_phase_editor", { index: 0 })).phaseEditor;
      await invoke("open_image", {
        path: path.join(root, "dioptas/tests/data/CeO2_Pilatus1M.tif"),
      });
      await invoke("open_calibration", {
        path: path.join(root, "dioptas/tests/data/CeO2_Pilatus1M.poni"),
      });
      await invoke("integration_settings", { bins: 64, cake_bins: 12 });
      await invoke("integration_phase", {
        operation: "load",
        path: path.join(root, "dioptas/tests/data/jcpds/mo.jcpds"),
      });
      await invoke("integration_phase", {
        operation: "editor_record",
        index: 0,
        action: "add",
      });
      await invoke("integration_phase", {
        operation: "editor_thermal_type",
        index: 0,
        value: "AlphaKT",
      });
      await invoke("integration_phase_export", { index: 0, path: file });
      const document = JSON.parse(await readFile(file, "utf8"));
      document.eos_records[0].reference = {
        authors: [
          "A very long first author with a compound surname",
          "Another author",
          "Third author",
        ],
        year: 2025,
        source:
          "Journal of Mineral Physics and High Pressure Experimental Methods",
        volume: "123",
        locator: "e123456789",
        doi: "10.0000/a-very-long-doi-to-exercise-wrapping",
        title:
          "A realistic long citation about high-pressure properties, experimental limitations, and source-record attribution",
        unknown: { value: "keep" },
      };
      document.eos_records[0].unknown = { nullable: null, list: [1, "keep"] };
      await writeFile(file, JSON.stringify(document));
      await invoke("integration_phase", { operation: "reload", index: 0 });
      await invoke("integration_phase", {
        operation: "editor_record",
        index: 0,
        action: "duplicate",
      });
      const original = await editState(),
        first = JSON.parse(JSON.stringify(document.eos_records[0]));
      const page = await browser.newPage({
        viewport: { width: 1440, height: 1000 },
      });
      page.on("pageerror", (e) => errors.push(e.message));
      await page.exposeFunction("__metadataInvoke", async (a, p) =>
        native.browserResult(await invoke(a, p)),
      );
      await page.addInitScript(() => {
        window.__metadataPending = 0;
        window.pywebview = {
          api: {
            invoke: async (a, p) => {
              window.__metadataPending++;
              try {
                return await window.__metadataInvoke(a, p);
              } finally {
                window.__metadataPending--;
              }
            },
          },
        };
      });
      await page.goto(
        pathToFileURL(path.join(root, "dioptas/desktop/ui/index.html")).href,
      );
      const ready = async () =>
        page.waitForFunction(
          () =>
            document.querySelector(".app") &&
            !window.__metadataPending &&
            !document.querySelector(".spin"),
        );
      const click = async (name) => {
        await page.getByRole("button", { name, exact: true }).click();
        await ready();
      };
      await click("Integration");
      await page.getByRole("tab", { name: "Phase", exact: true }).click();
      await click("Edit selected Phase");
      const dialog = page.getByRole("dialog", {
        name: "Phase Editor",
        exact: true,
      });
      await dialog.waitFor();
      await page
        .getByRole("tab", { name: "Equation of state", exact: true })
        .click();
      const metadata = page.locator(".pe-metadata");
      await metadata.locator(":scope > summary").click();
      const input = (label) => page.getByLabel(label, { exact: true });
      await input("Authors (separate with semicolons)").fill(
        "Smith, A.; Jones, B.",
      );
      await input("Year").fill("2026");
      await input("Journal / source").fill("Updated Journal");
      await input("DOI").fill("10.0000/updated");
      await page
        .getByText("Source lists the first author as et al.", { exact: true })
        .check();
      await metadata
        .getByText("Volume, pages and reference details", { exact: true })
        .click();
      for (const [label, value] of [
        ["Volume", "42"],
        ["Pages / article locator", "e123"],
        ["Reference details", "As printed; no uncertainty confidence assumed"],
      ])
        await input(label).fill(value);
      await metadata
        .getByText("Reported uncertainties & fixed parameters", { exact: true })
        .click();
      await input("eos K0 reported uncertainty").fill("1.25");
      await input("eos K0 publication fixed").check();
      await input("thermal alpha0 reported uncertainty").fill("1e-7");
      await input("thermal alpha0 publication fixed").check();
      await metadata
        .getByText("Experimental & validity ranges", { exact: true })
        .click();
      for (const [label, value] of [
        ["Experimental pressure minimum", "0"],
        ["Experimental pressure maximum", "125"],
        ["Experimental temperature minimum", "298"],
        ["Experimental temperature maximum", "2000"],
        ["Validity pressure minimum", "-1"],
        ["Validity pressure maximum", "150"],
        ["Validity temperature minimum", "200"],
        ["Validity temperature maximum", "2200"],
      ])
        await input(label).fill(value);
      await input("Record notes").fill(
        "Sample details\nPublished fit convention retained.",
      );
      assert.ok(await input("Editor material record").isDisabled());
      assert.ok(await input("Equation of state model").isDisabled());
      assert.ok(
        await page
          .getByRole("button", { name: "Save", exact: true })
          .isDisabled(),
      );
      await click("Close");
      assert.ok(await dialog.isVisible());
      assert.match(
        await dialog.locator("footer [role=status]").innerText(),
        /Apply or cancel/,
      );
      // Invalid fields focus the exact field and preserve the entire draft.
      await input("Year").fill("2026.5");
      await click("Apply publication edits");
      assert.match(await metadata.getByRole("alert").innerText(), /integer/);
      await page.waitForFunction(
        () => document.activeElement?.getAttribute("aria-label") === "Year",
      );
      await input("Year").fill("2026");
      await input("Experimental pressure maximum").fill("");
      await click("Apply publication edits");
      assert.match(
        await metadata.getByRole("alert").innerText(),
        /ordered minimum/,
      );
      await input("Experimental pressure maximum").fill("125");
      const before = await editState(),
        stateBefore = await invoke("state");
      rejectNext = true;
      await click("Apply publication edits");
      assert.match(
        await metadata.getByRole("alert").innerText(),
        /Draft retained/,
      );
      assert.equal(
        await input("Record notes").inputValue(),
        "Sample details\nPublished fit convention retained.",
      );
      assert.deepEqual((await editState()).recordData, before.recordData);
      await page
        .locator(".operation-error-dialog")
        .getByRole("button", { name: "OK", exact: true })
        .click();
      await input("Record notes").press("Control+Enter");
      await ready();
      await page.waitForFunction(
        () =>
          document.querySelector(".pe-metadata-actions [role=status]")
            ?.textContent === "No pending edits",
      );
      const after = await editState(),
        r = after.recordData;
      assert.deepEqual(r.reference.authors, ["Smith, A.", "Jones, B."]);
      assert.equal(r.reference.authors_truncated, true);
      assert.equal(r.reference.year, 2026);
      assert.equal(r.reference.volume, "42");
      assert.equal(r.reference.locator, "e123");
      assert.equal(r.reference.doi, "10.0000/updated");
      assert.equal(r.parameter_errors.K0, 1.25);
      assert.ok(r.fixed_parameters.includes("K0"));
      assert.equal(r.thermal.parameter_errors.alpha0, 1e-7);
      assert.ok(r.thermal.fixed_parameters.includes("alpha0"));
      assert.deepEqual(r.reference.unknown, { value: "keep" });
      assert.deepEqual(r.unknown, original.recordData.unknown);
      assert.deepEqual(r.eos, original.recordData.eos);
      assert.deepEqual(
        r.thermal.parameters,
        original.recordData.thermal.parameters,
      );
      const stateAfter = await invoke("state");
      for (const key of ["rawImage", "image", "cake", "pattern"])
        assert.deepEqual(stateAfter[key], stateBefore[key], key);
      await click("Save");
      await click("Reload File");
      await input("Editor material record").selectOption("1");
      await ready();
      assert.deepEqual((await editState()).recordData, r);
      assert.deepEqual(
        JSON.parse(await readFile(file, "utf8")).eos_records[0],
        first,
      );
      await invoke("save_project", { path: project });
      await invoke("open_project", { path: project });
      assert.deepEqual((await editState()).recordData, r);
      // Close/reopen obtains the live record after a project reset.
      await click("Close");
      await click("Edit selected Phase");
      await page
        .getByRole("tab", { name: "Equation of state", exact: true })
        .click();
      await page.locator(".pe-metadata > summary").click();
      await input("Record notes").fill("Local draft");
      const current = await editState();
      await invoke("integration_phase", {
        operation: "editor_transaction",
        edit_operation: "editor_metadata",
        editor_uid: current.uid,
        record_index: current.reference,
        expected_record_token: current.recordToken,
        changes: { notes: "Concurrent edit" },
      });
      await click("Apply publication edits");
      assert.equal(await input("Record notes").inputValue(), "Local draft");
      assert.match(await metadata.innerText(), /record changed|Draft retained/);
      await click("Cancel publication edits");
      await page.waitForFunction(
        () =>
          document.querySelector('textarea[aria-label="Record notes"]')
            ?.value === "Concurrent edit",
      );
      // Exercise clear semantics, including a partial citation without a fabricated author/year.
      for (const label of [
        "Authors (separate with semicolons)",
        "Year",
        "DOI",
        "Record notes",
        "Reference temperature",
      ])
        await input(label).fill("");
      await metadata
        .getByText("Reported uncertainties & fixed parameters", { exact: true })
        .click();
      await input("eos K0 reported uncertainty").fill("");
      await input("eos K0 publication fixed").uncheck();
      await click("Apply publication edits");
      assert.equal((await editState()).recordData.parameter_errors.K0, null);
      assert.equal((await editState()).recordData.reference.year, undefined);
      // Layout checks include long citations, every disclosure, compact and larger text.
      const layout = [];
      for (const large of [false, true])
        for (const width of [900, 1000, 1440]) {
          await page.setViewportSize({ width, height: 900 });
          await page
            .locator(".app")
            .evaluate(
              (el, large) => (el.dataset.textSize = large ? "large" : "normal"),
              large,
            );
          await metadata.evaluate((el) => {
            el.open = true;
            for (const d of el.querySelectorAll("details")) d.open = true;
          });
          const check = await metadata.evaluate((el) => {
            const bounds = el.getBoundingClientRect();
            return {
              width: el.clientWidth,
              scroll: el.scrollWidth,
              overflow: [...el.querySelectorAll("input,textarea,button")]
                .filter((n) => {
                  const b = n.getBoundingClientRect();
                  return (
                    b.width &&
                    (b.left < bounds.left - 1 || b.right > bounds.right + 1)
                  );
                })
                .map((n) => n.getAttribute("aria-label") || n.textContent),
            };
          });
          layout.push({ large, width, ...check });
          assert.ok(
            check.scroll <= check.width + 1,
            JSON.stringify(layout.at(-1)),
          );
          assert.deepEqual(check.overflow, []);
          await metadata.scrollIntoViewIfNeeded();
          await page.screenshot({
            path: path.join(
              artifacts,
              `${engineName}-${width}-${large ? "large" : "normal"}.png`,
            ),
          });
        }
      assert.deepEqual(errors, []);
      const nativeEvents = await nativeEditorEvents(
        browser,
        native,
        (await editState()).uid,
      );
      receipts.push({
        nativeEvents,
        engine: engineName,
        layout,
        calls: calls.length,
        errors,
      });
    } finally {
      await browser.close();
      await native.close();
    }
  }
  await writeFile(
    path.join(artifacts, "receipt.json"),
    JSON.stringify(receipts, null, 2),
  );
  console.log(JSON.stringify({ ok: true, receipts }));
} finally {
  await rm(temp, { recursive: true, force: true });
}
