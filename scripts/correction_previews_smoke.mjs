import assert from "node:assert/strict";
import { mkdtemp, mkdir, writeFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { chromium, webkit } from "playwright";
import { nativeClient, root } from "./native_backend_client.mjs";
const temp = await mkdtemp(path.join(tmpdir(), "dioptas-correction-preview-"));
const out = path.join(root, "artifacts/correction-previews");
await mkdir(out, { recursive: true });
async function plane(name, fn) {
  let header = "{'descr': '<f8', 'fortran_order': False, 'shape': (24, 32), }";
  while ((10 + header.length + 1) % 64) header += " ";
  header += "\n";
  const bytes = Buffer.alloc(10 + header.length + 768 * 8);
  bytes.set(Buffer.from([147, 78, 85, 77, 80, 89, 1, 0]));
  bytes.writeUInt16LE(header.length, 8);
  bytes.write(header, 10);
  for (let i = 0; i < 768; ++i)
    bytes.writeDoubleLE(fn(i), 10 + header.length + i * 8);
  const file = path.join(temp, name + ".npy");
  await writeFile(file, bytes);
  return file;
}
const raw = await plane("raw", (i) => 100 + (i % 31)),
  flat = await plane("flat", (i) => 2 + i / 768);
const original = await plane("original", () => 3),
  response = await plane("response", (i) => 2 + i / 768);
const receipts = [];
try {
  for (const [name, engine] of [
    ["chromium", chromium],
    ["webkit", webkit],
  ]) {
    const native = nativeClient(),
      browser = await engine.launch({ headless: true });
    try {
      let failPreview = false,
        delayPreview = false;
      const commands = [],
        errors = [];
      let latestRevision = -1,
        preparedRevision = -2,
        preloadExpected = false;
      let preloadGate = null,
        releasePreload,
        heldPreloads = 0,
        discardedPreloads = 0;
      let applyAckGate = null,
        releaseApplyAck,
        heldApplyAcks = 0;
      const call = async (a, p = {}) => {
        const r = await native.invoke(a, p);
        assert.equal(r.ok, true, `${a}: ${r.error}`);
        return r;
      };
      await call("open_image", { path: raw });
      await call("manual_geometry", {
        convention: "pyfai",
        values: {
          dist: 0.03,
          poni1: 0.0012,
          poni2: 0.0016,
          pixel1: 0.0001,
          pixel2: 0.0001,
          rot1: 0.04,
          rot2: -0.03,
          rot3: 0.01,
          wavelength: 5e-11,
          polarization_factor: 0.965,
        },
      });
      await call("integration_settings", {
        bins: 48,
        cake_bins: 12,
        poisson_errors: true,
      });
      const page = await browser.newPage({
        viewport: { width: 1440, height: 900 },
      });
      page.on("pageerror", (e) => errors.push(e.message));
      await page.exposeFunction("__nativeInvoke", async (a, p = {}) => {
        commands.push([a, p]);
        if (
          a === "integration_flat_field" &&
          !p.reset &&
          p.enabled === undefined
        )
          p = { ...p, path: flat };
        if (a === "integration_transfer" && p.source && !p.reset)
          p = { ...p, path: p.source === "original" ? original : response };
        if (a === "integration_correction_preview" && failPreview) {
          failPreview = false;
          return { ok: false, error: "Injected preview transport failure" };
        }
        if (a === "integration_correction_preload" && preloadGate) {
          heldPreloads++;
          await preloadGate;
        }
        let rawResult;
        if (a === "integration_correction_preview") {
          const packet = await native.invokePacket(
            a,
            p,
            [...native.buffers.keys()].slice(-64),
          );
          const length = packet.readUInt32LE(0);
          rawResult = JSON.parse(
            packet.subarray(4, 4 + length).toString(),
          ).result;
          if (rawResult.ok)
            assert.equal(
              packet.length - 4 - length,
              0,
              "Ready Plot must use background-preloaded pixels",
            );
        } else rawResult = await native.invoke(a, p);
        if (rawResult.state) {
          latestRevision = rawResult.state.revision;
          const integration = rawResult.state.integration;
          preloadExpected =
            !!integration.flatField.filename ||
            (!!integration.transfer?.original &&
              !!integration.transfer?.response) ||
            Object.values(integration.corrections).some((c) => c.enabled);
        }
        if (a === "integration_correction_preload" && rawResult.discarded)
          discardedPreloads++;
        if (
          a === "integration_correction_preload" &&
          rawResult.ok &&
          !rawResult.discarded &&
          !rawResult.correctionPreviewPending
        )
          preparedRevision = rawResult.revision;
        const result = native.browserResult(rawResult);
        if (a === "integration_correction" && applyAckGate) {
          heldApplyAcks++;
          await applyAckGate;
        }
        if (a === "integration_correction_preview" && delayPreview) {
          delayPreview = false;
          await new Promise((resolve) => setTimeout(resolve, 450));
        }
        return result;
      });
      await page.exposeFunction("__heldPreloads", () => heldPreloads);
      await page.exposeFunction("__heldApplyAcks", () => heldApplyAcks);
      await page.exposeFunction(
        "__latestCorrectionRevision",
        () => latestRevision,
      );
      await page.exposeFunction(
        "__correctionPreloadReady",
        () => !preloadExpected || latestRevision === preparedRevision,
      );
      await page.addInitScript(() => {
        window.pywebview = {
          api: { invoke: (a, p) => window.__nativeInvoke(a, p) },
        };
      });
      await page.goto(pathToFileURL(path.join(root, "dist/index.html")).href);
      const button = (label) =>
        page.getByRole("button", { name: label, exact: true });
      await button("Integration").click();
      await page.getByRole("tab", { name: "Corrections", exact: true }).click();
      const type = (label) =>
        page
          .getByRole("navigation", { name: "Correction type" })
          .getByRole("button", { name: label, exact: true });
      const plot = () => button("Plot correction");
      const applyIsFinished = () => {
        const action = document.querySelector(".correction-plot-button");
        return action instanceof HTMLButtonElement && !action.disabled;
      };
      const preloadReady = () =>
        page.waitForFunction(
          async () => await window.__correctionPreloadReady(),
        );
      const compactAction = async () => {
        const row = page.locator(".correction-apply-row");
        const label = await row.locator(".check-row").boundingBox();
        const action = await row
          .locator(".correction-plot-button")
          .boundingBox();
        const bounds = await row.boundingBox();
        assert(label && action && bounds);
        assert(action.width < 90 && action.height >= 28);
        assert(
          Math.abs(action.y + action.height / 2 - label.y - label.height / 2) <
            2,
          "Apply and Plot must share one row",
        );
        assert(
          action.x >= label.x + label.width + 5 &&
            action.x <= label.x + label.width + 15,
          "Plot must sit beside Apply",
        );
        assert(action.x + action.width <= bounds.x + bounds.width + 1);
        assert.equal(
          await page.locator(".correction-preview-action").count(),
          0,
        );
      };
      const preview = page.getByRole("region", {
        name: "Correction map preview",
      });
      const image = page.locator(
        ".detector-panel > .detector-surface > .detector-workspace [data-testid=detector-canvas]",
      );
      const cake = page.getByTestId("cake-canvas");
      const ready = () =>
        page.waitForFunction(
          () => !document.querySelector(".workflow-status .spin"),
        );
      const attrs = (locator) =>
        locator.evaluate((el) =>
          Object.fromEntries(
            [
              "data-view-x-min",
              "data-view-x-max",
              "data-view-y-min",
              "data-view-y-max",
              "data-intensity-min",
              "data-intensity-max",
              "data-intensity-scale",
              "data-colour-map",
            ].map((k) => [k, el.getAttribute(k)]),
          ),
        );
      const science = async () => {
        const r = await call("state");
        return {
          state: r.state,
          pattern: r.pattern,
          image: r.image.bufferId,
          raw: r.rawImage.bufferId,
          cake: r.cake?.bufferId,
          mask: r.mask.bufferId,
        };
      };
      const contrast = async (locator, max) => {
        await locator
          .getByRole("button", {
            name: "Detector histogram settings",
            exact: true,
          })
          .click();
        const field = page.getByRole("spinbutton", {
          name: "Maximum intensity",
          exact: true,
        });
        await field.fill(String(max));
        await field.press("Enter");
        await button("Close detector display settings").click();
      };
      assert.equal(await plot().isEnabled(), false);
      await type("Detector absorption").click();
      assert.equal(
        await page
          .getByRole("spinbutton", { name: "Detector tilt (°)", exact: true })
          .count(),
        0,
      );
      assert.equal(
        await page
          .getByRole("spinbutton", {
            name: "Detector rotation (°)",
            exact: true,
          })
          .count(),
        0,
      );
      assert.equal(
        await page
          .getByRole("spinbutton", {
            name: "Detector thickness (µm)",
            exact: true,
          })
          .count(),
        1,
      );
      preloadGate = new Promise((resolve) => {
        releasePreload = resolve;
      });
      applyAckGate = new Promise((resolve) => {
        releaseApplyAck = resolve;
      });
      await page
        .getByRole("checkbox", {
          name: "Apply detector absorption",
          exact: true,
        })
        .check();
      await page.waitForFunction(
        async () => (await window.__heldApplyAcks()) > 0,
      );
      // A quiet queued edit has no workflow spinner. Prove that the old idle
      // check can pass before its acknowledgement and local switching cleanup.
      await ready();
      assert.equal(await plot().isEnabled(), false);
      assert.equal(
        await page.evaluate(applyIsFinished),
        false,
        "Completion must remain pending while the Apply acknowledgement is held",
      );
      const applyFinished = page.waitForFunction(applyIsFinished, null, {
        timeout: 10000,
      });
      applyAckGate = null;
      releaseApplyAck();
      // Leave background loading held: if Apply waits on it, this bounded
      // observable completion check must fail instead of releasing that gate.
      await Promise.all([
        page.waitForFunction(async () => (await window.__heldPreloads()) > 0),
        applyFinished,
      ]);
      assert.notEqual(preloadGate, null);
      assert.equal(
        await plot().isEnabled(),
        true,
        "Apply must finish while preloading is still pending",
      );
      assert.equal(await preview.count(), 0);
      const thickness = page.getByRole("spinbutton", {
        name: "Detector thickness (µm)",
        exact: true,
      });
      const previousRevision = latestRevision;
      await thickness.fill("44");
      await thickness.press("Enter");
      await ready();
      await page.waitForFunction(
        async (revision) =>
          (await window.__latestCorrectionRevision()) > revision,
        previousRevision,
      );
      preloadGate = null;
      releasePreload();
      await preloadReady();
      assert(
        discardedPreloads > 0,
        "Superseded background responses must be rejected quietly",
      );
      for (const large of [false, true]) {
        await button("Settings").click();
        await button(large ? "Larger" : "Standard").click();
        await button("Close settings").click();
        for (const width of [1000, 1440]) {
          await page.setViewportSize({ width, height: 900 });
          await page.waitForTimeout(120);
          await compactAction();
          await page.locator(".integration-tab-corrections").screenshot({
            path: path.join(
              out,
              `${name}-actions-${large ? "large" : "standard"}-${width}.png`,
            ),
          });
        }
      }
      await button("Settings").click();
      await button("Standard").click();
      await button("Close settings").click();
      await compactAction();
      const detectorBefore = await science();
      await preloadReady();
      await plot().click();
      await preview.waitFor();
      assert.match(
        await preview.innerText(),
        /Relative detector absorption efficiency/,
      );
      await button("Back from correction preview").click();
      assert.deepEqual(await science(), detectorBefore);
      await page
        .getByRole("checkbox", {
          name: "Apply detector absorption",
          exact: true,
        })
        .uncheck();
      await ready();
      for (const [tab, label, kind] of [
        ["cBN seat", "cBN seat", "cbn"],
        ["Slab", "slab self-absorption", "slab"],
        ["Cylinder", "cylinder absorption", "cylinder"],
        ["Sphere", "sphere absorption", "sphere"],
      ]) {
        await type(tab).click();
        await compactAction();
        const toggle = page.getByRole("checkbox", {
          name: `Apply ${label}`,
          exact: true,
        });
        await toggle.check();
        await ready();
        const before = await science();
        await preloadReady();
        await plot().click();
        await preview.waitFor();
        assert.equal(await preview.getAttribute("data-kind"), kind);
        await button("Back from correction preview").click();
        await preloadReady();
        await plot().click();
        await preview.waitFor();
        assert.equal(await preview.getAttribute("data-kind"), kind);
        await button("Back from correction preview").click();
        assert.deepEqual(await science(), before);
        await toggle.uncheck();
        await ready();
      }
      await type("Flat field").click();
      await compactAction();
      await button("Load flat field…").click();
      await ready();
      await page
        .getByRole("checkbox", { name: "Apply flat field", exact: true })
        .uncheck();
      await ready();
      await contrast(
        page.locator(
          ".detector-panel > .detector-surface > .detector-workspace",
        ),
        180,
      );
      await image.hover();
      await page.mouse.wheel(0, -180);
      await page.waitForTimeout(180);
      const originalView = await attrs(image),
        before = await science();
      await preloadReady();
      await plot().click();
      await preview.waitFor();
      assert.match(
        await preview.innerText(),
        /Mean-normalized flat-field response · dimensionless/,
      );
      assert.equal(await button("Save image").isEnabled(), false);
      assert.equal(
        await image.isVisible(),
        false,
        "Underlying image controls must stay hidden while the correction map is shown",
      );
      const map = preview.getByTestId("detector-canvas");
      assert.equal(await map.getAttribute("data-full-width"), "32");
      assert.equal(await map.getAttribute("data-full-height"), "24");
      const pixelCommands = commands.length;
      await map.hover();
      await page.waitForTimeout(200);
      assert.match(
        await page.getByTestId("mouse-readout").innerText(),
        /Factor/,
      );
      assert(
        commands
          .slice(pixelCommands)
          .filter(([a]) => a === "pixel")
          .every(([, p]) => p.source === "geometry"),
        "Map readouts must not sample image counts",
      );
      await page.waitForFunction(() =>
        document
          .querySelector('[data-testid="mouse-readout"]')
          ?.textContent.includes("2θ"),
      );
      await contrast(preview, 5);
      await map.hover();
      await page.mouse.wheel(0, -200);
      await page.waitForTimeout(150);
      const previewView = await attrs(map);
      await preview
        .getByRole("button", { name: "Auto intensity", exact: true })
        .click();
      await page.waitForFunction(
        () =>
          document
            .querySelector(".correction-preview [data-testid=detector-canvas]")
            ?.getAttribute("data-intensity-max") !== "5",
      );
      assert.equal(
        (await attrs(map))["data-view-x-min"],
        previewView["data-view-x-min"],
      );
      await preview.getByRole("button", { name: "Back", exact: true }).click();
      await preview.waitFor({ state: "detached" });
      assert.deepEqual(await attrs(image), originalView);
      assert.deepEqual(await science(), before);
      assert(
        !(await page
          .getByTestId("mouse-readout")
          .innerText()
          .then((t) => t.includes("Factor"))),
      );
      await button("Cake").click();
      await cake.waitFor({ state: "visible" });
      await ready();
      await cake.hover();
      await page.mouse.wheel(0, -180);
      await page.waitForTimeout(180);
      const cakeView = await attrs(cake),
        cakeBefore = await science();
      await preloadReady();
      await plot().click();
      await preview.waitFor();
      await button("Back from correction preview").click();
      await cake.waitFor({ state: "visible" });
      assert.deepEqual(await attrs(cake), cakeView);
      assert.deepEqual(await science(), cakeBefore);
      await type("Transfer").click();
      await compactAction();
      assert.equal(await plot().isEnabled(), false);
      await button("Load transfer original…").click();
      await ready();
      assert.equal(await plot().isEnabled(), false);
      await button("Load transfer response…").click();
      await ready();
      await preloadReady();
      await plot().click();
      await preview.waitFor();
      assert.match(await preview.innerText(), /response \/ original/);
      await type("Flat field").click();
      await preloadReady();
      await plot().click();
      await page.waitForFunction(
        () =>
          document.querySelector(".correction-preview")?.dataset.kind ===
          "flat",
      );
      await button("Remove flat field").click();
      await preview.waitFor({ state: "detached" });
      await ready();
      assert.equal(await plot().isEnabled(), false);
      await type("Transfer").click();
      await preloadReady();
      await plot().click();
      await preview.waitFor();
      await button("Calibration").click();
      await preview.waitFor({ state: "detached" });
      await button("Integration").click();
      await type("Transfer").click();
      delayPreview = true;
      await preloadReady();
      await plot().click();
      await button("Calibration").click();
      await ready();
      await button("Integration").click();
      assert.equal(
        await preview.count(),
        0,
        "A late map must not reopen after a mode switch",
      );
      await type("Transfer").click();
      failPreview = true;
      await preloadReady();
      await plot().click();
      await ready();
      assert.equal(await preview.count(), 0);
      assert.match(
        await page.locator(".workflow-status").innerText(),
        /Injected preview transport failure/,
      );
      await page
        .getByRole("dialog")
        .getByRole("button", { name: "OK", exact: true })
        .click();
      await button("Dismiss error").click();
      await type("Plate").click();
      assert.equal(await plot().isEnabled(), false);
      await page
        .getByRole("checkbox", { name: "Apply plate absorption", exact: true })
        .check();
      await ready();
      await preloadReady();
      await plot().click();
      await preview.waitFor();
      await page
        .getByRole("checkbox", { name: "Apply plate absorption", exact: true })
        .uncheck();
      await preview.waitFor({ state: "detached" });
      await ready();
      assert.equal(await plot().isEnabled(), false);
      await type("Transfer").click();
      await preloadReady();
      await plot().click();
      await preview.waitFor();
      await page.keyboard.press("Shift+C");
      await button("Duplicate").click();
      await ready();
      assert.equal(await preview.count(), 0);
      await preloadReady();
      await plot().click();
      await preview.waitFor();
      await page
        .getByRole("combobox", { name: "Active configuration", exact: true })
        .selectOption("0");
      await ready();
      assert.equal(await preview.count(), 0);
      await preloadReady();
      await plot().click();
      await preview.waitFor();
      await page.keyboard.press("Shift+C");
      for (const width of [1440, 1100]) {
        await page.setViewportSize({ width, height: 900 });
        await page.waitForTimeout(150);
        assert.equal(
          await page.evaluate(
            () => document.documentElement.scrollWidth > innerWidth,
          ),
          false,
        );
        const box = await preview.boundingBox();
        assert(box.width > 250 && box.height > 350);
        const back = await button("Back from correction preview").boundingBox();
        assert(back.x + back.width <= width && back.width >= 40);
        await page.screenshot({ path: path.join(out, `${name}-${width}.png`) });
      }
      assert.deepEqual(errors, []);
      receipts.push({
        browser: name,
        checks: [
          "disabled/partial references",
          "native map readouts and units",
          "background prepares/preloads pixels; ready Plot transfers metadata only",
          "delayed Apply acknowledgement rejects the old idle signal; completion does not await held preload",
          "Apply and edits stay usable during delayed preload; stale responses discarded",
          "independent histogram and zoom",
          "unchanged raw/processed/pattern/cake",
          "Cake restoration",
          "replacement/removal/disable/mode/configuration/failure cleanup",
          "late response rejection and native Auto levels",
          "compact Apply/Plot row at 1000/1440 in both text sizes; 1440/1100 preview layout",
        ],
        previewCommands: commands.filter(
          ([a]) => a === "integration_correction_preview",
        ).length,
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
  console.log(JSON.stringify(receipts, null, 2));
} finally {
  await rm(temp, { recursive: true, force: true });
}
