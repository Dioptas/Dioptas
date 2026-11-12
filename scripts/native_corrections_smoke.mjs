import assert from "node:assert/strict";
import { mkdtemp, mkdir, writeFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { chromium, webkit } from "playwright";
import { nativeClient, root } from "./native_backend_client.mjs";

const temp = await mkdtemp(path.join(tmpdir(), "dioptas-corrections-"));
const out = path.join(root, "artifacts/native-corrections");
await mkdir(out, { recursive: true });
async function plane(name, value) {
  let header = "{'descr': '<f8', 'fortran_order': False, 'shape': (24, 32), }";
  while ((10 + header.length + 1) % 64) header += " ";
  header += "\n";
  const bytes = Buffer.alloc(10 + header.length + 768 * 8);
  bytes.set(Buffer.from([147, 78, 85, 77, 80, 89, 1, 0]));
  bytes.writeUInt16LE(header.length, 8);
  bytes.write(header, 10);
  for (let i = 0; i < 768; i++)
    bytes.writeDoubleLE(value, 10 + header.length + i * 8);
  const file = path.join(temp, name + ".npy");
  await writeFile(file, bytes);
  return file;
}
const files = {
  raw: await plane("counts", 100),
  original: await plane("original", 3),
  response: await plane("response", 2),
  background: await plane("background", 4),
};
const receipts = [];
try {
  for (const [name, engine] of [
    ["chromium", chromium],
    ["webkit", webkit],
  ]) {
    const native = nativeClient();
    const browser = await engine.launch({ headless: true });
    try {
      const project = path.join(temp, name + ".dio");
      const errors = [],
        commands = [],
        results = [];
      let releasePlateAck,
        heldPlateAcks = 0;
      const plateAckGate = new Promise((resolve) => {
        releasePlateAck = resolve;
      });
      const invoke = async (action, payload = {}) => {
        commands.push([action, payload]);
        if (
          action === "integration_transfer" &&
          payload.source &&
          !payload.path &&
          !payload.reset
        )
          payload = { ...payload, path: files[payload.source] };
        if (
          action === "integration_image_background" &&
          !payload.path &&
          payload.scale === undefined &&
          payload.offset === undefined &&
          payload.poisson === undefined &&
          !payload.reset
        )
          payload = { path: files.background };
        if (["save_project", "open_project"].includes(action))
          payload = { ...payload, path: project };
        const r = await native.invoke(action, payload);
        results.push({
          action,
          payload,
          ok: r.ok,
          error: r.error,
          cancelled: r.cancelled,
          revision: r.state?.revision,
        });
        assert.equal(r.ok, true, `${action}: ${r.error}`);
        if (
          action === "integration_correction" &&
          payload.kind === "plate" &&
          payload.enabled &&
          heldPlateAcks === 0
        ) {
          heldPlateAcks++;
          await plateAckGate;
        }
        return r;
      };
      await invoke("open_image", { path: files.raw });
      await invoke("manual_geometry", {
        convention: "pyfai",
        values: {
          dist: 0.13,
          poni1: 0.0012,
          poni2: 0.0016,
          pixel1: 0.0001,
          pixel2: 0.0001,
          rot1: 0,
          rot2: 0,
          rot3: 0,
          wavelength: 5e-11,
          polarization_factor: 0.965,
        },
      });
      await invoke("integration_settings", {
        bins: 48,
        cake_bins: 12,
        poisson_errors: true,
      });
      const page = await browser.newPage({
        viewport: { width: 1440, height: 900 },
      });
      page.on("pageerror", (e) => errors.push(e.message));
      await page.exposeFunction("__nativeInvoke", async (a, p) =>
        native.browserResult(await invoke(a, p)),
      );
      await page.addInitScript(() => {
        window.pywebview = {
          api: { invoke: (a, p) => window.__nativeInvoke(a, p) },
        };
      });
      await page.goto(pathToFileURL(path.join(root, "dist/index.html")).href);
      await page
        .getByRole("button", { name: "Integration", exact: true })
        .click();
      await page.getByRole("tab", { name: "Background", exact: true }).click();
      await page
        .getByRole("navigation", { name: "Background type" })
        .getByRole("button", { name: "Image", exact: true })
        .click();
      await page
        .getByRole("button", { name: "Load background…", exact: true })
        .click();
      const backgroundNoise = page.getByRole("checkbox", {
        name: "Include background counting noise",
      });
      await backgroundNoise.uncheck();
      await page.waitForFunction(() => !document.querySelector(".spin"));
      await page.getByRole("tab", { name: "Corrections", exact: true }).click();
      const type = (label) =>
        page
          .getByRole("navigation", { name: "Correction type" })
          .getByRole("button", { name: label, exact: true });
      const selectedType = (label) =>
        page
          .getByRole("navigation", { name: "Correction type" })
          .getByRole("button", { name: label, exact: true, pressed: true });
      const selectType = async (label, clicked) => {
        await type(label).click();
        clicked?.();
        await selectedType(label).waitFor();
      };
      const state = async () => (await native.invoke("state")).state;
      const wait = async (predicate) => {
        let last;
        for (let i = 0; i < 100; i++) {
          last = await state();
          if (predicate(last)) return;
          await page.waitForTimeout(50);
        }
        const diagnostic = {
          browser: name,
          expected: String(predicate),
          corrections: last.integration.corrections,
          recentCommands: commands.slice(-20),
          recentResults: results.slice(-20),
          heldPlateAcks,
          fields: await page
            .locator(".integration-tab-corrections input")
            .evaluateAll((fields) =>
              fields.map((field) => ({
                label: field.getAttribute("aria-label"),
                value: field.value,
                checked: field.checked,
                disabled: field.disabled,
                focused: field === document.activeElement,
              })),
            ),
          status: await page.locator(".workflow-status").allTextContents(),
          errors,
        };
        await writeFile(
          path.join(out, `${name}-failure.json`),
          JSON.stringify(diagnostic, null, 2),
        );
        throw Error(
          `Native state did not reach expected correction settings: ${JSON.stringify(diagnostic)}`,
        );
      };
      await selectType("Transfer");
      assert.equal(
        await page
          .getByRole("checkbox", { name: "Apply transfer correction" })
          .isEnabled(),
        false,
      );
      for (const source of ["original", "response"]) {
        await page
          .getByRole("button", {
            name: `Load transfer ${source}…`,
            exact: true,
          })
          .click();
        await wait((s) => !!s.integration.transfer[source]);
      }
      await page
        .getByRole("checkbox", { name: "Apply transfer correction" })
        .check();
      await wait((s) => s.integration.transfer.enabled);
      for (const [kind, label] of [
        ["plate", "Plate"],
        ["slab", "Slab"],
      ]) {
        if (kind === "slab") {
          // Deliver this tab click only after proving the preceding pane still
          // exposes the same Thickness label. A click alone is not a pane commit.
          await page.evaluate(() => {
            const hold = (event) => {
              const button = event.target.closest?.(
                'button[aria-label="Slab"]',
              );
              if (!button?.closest('[aria-label="Correction type"]')) return;
              event.preventDefault();
              event.stopImmediatePropagation();
              window.__heldCorrectionNavigation = true;
              window.__releaseCorrectionNavigation = () => {
                window.removeEventListener("click", hold, true);
                button.click();
              };
            };
            window.addEventListener("click", hold, true);
          });
          let reportClick,
            navigationCompleted = false;
          const clickCompleted = new Promise((resolve) => {
            reportClick = resolve;
          });
          const navigation = selectType(label, reportClick).then(() => {
            navigationCompleted = true;
          });
          await clickCompleted;
          // This round trip follows the completed click, so a click-only helper
          // has also settled its promise before the held-navigation assertion.
          await page.waitForFunction(() => window.__heldCorrectionNavigation);
          assert.equal(
            navigationCompleted,
            false,
            "Tab selection must remain pending until the requested pane commits",
          );
          assert.equal(await selectedType(label).count(), 0);
          assert.equal(await selectedType("Plate").count(), 1);
          assert.equal(
            await page.getByLabel("Thickness (mm)", { exact: true }).count(),
            1,
          );
          await page.evaluate(() => window.__releaseCorrectionNavigation());
          await navigation;
        } else await selectType(label);
        const apply = page.getByRole("checkbox", {
          name:
            kind === "plate"
              ? "Apply plate absorption"
              : "Apply slab self-absorption",
          exact: true,
        });
        await apply.waitFor();
        const thickness = page.getByLabel("Thickness (mm)", { exact: true });
        await thickness.fill("0.3");
        await thickness.press("Enter");
        if (kind === "slab") {
          assert.equal(heldPlateAcks, 1);
          releasePlateAck();
        }
        await apply.check();
        await wait(
          (s) =>
            s.integration.corrections[kind].enabled &&
            s.integration.corrections[kind].parameters.thickness === 0.3,
        );
      }
      await page
        .getByLabel("Attenuation source", { exact: true })
        .selectOption("formula");
      await wait(
        (s) => s.integration.corrections.slab.material.mode === "formula",
      );
      const formula = page.getByLabel("Formula or material", { exact: true });
      await formula.fill("SiO2");
      await formula.press("Enter");
      const density = page.getByLabel("Density (g/cm³)", { exact: true });
      await density.fill("2.2");
      await density.press("Enter");
      await wait(
        (s) =>
          s.integration.corrections.slab.material.formula === "SiO2" &&
          s.integration.corrections.slab.material.density === 2.2,
      );
      for (const [kind, label] of [
        ["cylinder", "Cylinder"],
        ["sphere", "Sphere"],
      ]) {
        await selectType(label);
        for (const [name, value] of [
          ["Radius (mm)", "0.2"],
          ["Beam width (mm)", "0.12"],
        ]) {
          const field = page.getByLabel(name, { exact: true });
          await field.fill(value);
          await field.press("Enter");
        }
        await page
          .getByRole("checkbox", {
            name: `Apply ${kind} absorption`,
            exact: true,
          })
          .check();
        await wait(
          (s) =>
            s.integration.corrections[kind].enabled &&
            s.integration.corrections[kind].parameters.beam_width === 0.12,
        );
        await page
          .getByLabel("Attenuation source", { exact: true })
          .selectOption("formula");
        await wait(
          (s) => s.integration.corrections[kind].material.mode === "formula",
        );
        if (kind === "cylinder") {
          await page
            .getByRole("checkbox", {
              name: "Correct capillary wall",
              exact: true,
            })
            .check();
          await wait(
            (s) => s.integration.corrections.cylinder.container.enabled,
          );
          await page
            .getByLabel("Container Attenuation source", { exact: true })
            .selectOption("formula");
          await wait(
            (s) =>
              s.integration.corrections.cylinder.container.material.mode ===
              "formula",
          );
          const wall = page.getByLabel("Wall thickness (mm)", { exact: true });
          await wall.fill("0.03");
          await wall.press("Enter");
          await wait(
            (s) =>
              s.integration.corrections.cylinder.parameters.wall_thickness ===
              0.03,
          );
        }
      }
      await page
        .getByRole("button", { name: "Save project", exact: true })
        .click();
      await page.waitForFunction(() =>
        document
          .querySelector(".navigation-project")
          ?.textContent?.endsWith(".dio"),
      );
      const before = (await invoke("state")).pattern;
      await selectType("Transfer");
      await page
        .getByRole("checkbox", { name: "Apply transfer correction" })
        .uncheck();
      await wait((s) => !s.integration.transfer.enabled);
      await page
        .getByRole("button", { name: "Open project", exact: true })
        .click();
      await wait((s) => s.integration.transfer.enabled);
      assert.deepEqual((await invoke("state")).pattern, before);
      for (const width of [1440, 1100]) {
        await page.setViewportSize({ width, height: 900 });
        for (const label of [
          "Transfer",
          "Plate",
          "Slab",
          "Cylinder",
          "Sphere",
        ]) {
          await selectType(label);
          assert.equal(
            await page
              .locator(".integration-tab-corrections")
              .getByRole("checkbox")
              .count(),
            label === "Cylinder" ? 2 : 1,
            `${label}: expected apply controls after navigation/reopening`,
          );
          const sizes = await page
            .locator(".integration-tab-corrections")
            .evaluate((el) => ({
              width: el.clientWidth,
              scroll: el.scrollWidth,
            }));
          assert.ok(
            sizes.scroll <= sizes.width + 1,
            `${label} fits at ${width}`,
          );
          if (label === "Cylinder") {
            await page
              .getByLabel("Container Formula or material", { exact: true })
              .scrollIntoViewIfNeeded();
            await page.screenshot({
              path: path.join(out, `${name}-${width}-capillary.png`),
            });
          }
        }
        await page.screenshot({ path: path.join(out, `${name}-${width}.png`) });
      }
      assert.deepEqual(errors, []);
      assert.ok(
        commands.some(
          ([a, p]) => a === "integration_transfer" && p.source === "original",
        ),
      );
      receipts.push({
        browser: name,
        layouts: [1440, 1100],
        corrections: ["transfer", "plate", "slab", "cylinder", "sphere"],
        delayedPlateAcknowledgement: true,
        delayedSlabNavigation: true,
        projectRoundtrip: true,
      });
    } finally {
      await browser.close();
      await native.close();
    }
  }
  await writeFile(
    path.join(out, "receipt.json"),
    JSON.stringify(receipts, null, 2) + "\n",
  );
  console.log(JSON.stringify(receipts));
} finally {
  await rm(temp, { recursive: true, force: true });
}
