import assert from "node:assert/strict";
import { EventEmitter, once } from "node:events";
import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { chromium, webkit } from "playwright";
import { nativeClient, root } from "./native_backend_client.mjs";

const out = path.join(root, "artifacts/processing-drafts");
await mkdir(out, { recursive: true });
const receipts = [];
for (const [name, engine] of [
  ["chromium", chromium],
  ["webkit", webkit],
]) {
  const native = nativeClient();
  const browser = await engine.launch({ headless: true });
  let held = null;
  let page;
  try {
    const call = async (action, payload = {}) => {
      const result = await native.invoke(action, payload);
      assert.equal(result.ok, true, `${action}: ${result.error}`);
      return result;
    };
    await call("open_image", {
      path: path.join(root, "tests/data/CeO2_Pilatus1M.tif"),
    });
    await call("open_calibration", {
      path: path.join(root, "tests/data/CeO2_Pilatus1M.poni"),
    });
    await call("integration_settings", { bins: 32, cake_bins: 8 });
    page = await browser.newPage({
      viewport: { width: 1440, height: 1000 },
    });
    const errors = [];
    page.on("pageerror", (error) => errors.push(error.message));
    await page.exposeFunction("__nativeInvoke", async (action, payload) => {
      const result = await call(action, payload);
      if (
        held &&
        action === "integration_correction" &&
        payload.kind === held.kind &&
        payload.parameters?.[held.key] === held.value
      ) {
        const gate = held;
        gate.started();
        await gate.delivery;
      }
      return native.browserResult(result);
    });
    await page.addInitScript(() => {
      window.__pending = 0;
      window.pywebview = {
        api: {
          invoke: async (action, payload) => {
            const track = !["pixel", "progress"].includes(action);
            if (track) window.__pending++;
            try {
              return await window.__nativeInvoke(action, payload);
            } finally {
              if (track) window.__pending--;
            }
          },
        },
      };
    });
    const ready = async () => {
      await page.waitForFunction(
        () =>
          document.querySelector(".app") &&
          !window.__pending &&
          !document.querySelector(".spin"),
      );
      await page.evaluate(
        () =>
          new Promise((resolve) =>
            requestAnimationFrame(() => requestAnimationFrame(resolve)),
          ),
      );
    };
    const state = async () => (await call("state")).state;
    const correction = async (kind) =>
      (await state()).integration.corrections[kind];
    const select = async (label, toggleLabel) => {
      const type = page
        .getByRole("navigation", { name: "Correction type" })
        .getByRole("button", { name: label, exact: true });
      await type.click();
      await page.waitForFunction(
        (label) =>
          [
            ...document.querySelectorAll(
              'nav[aria-label="Correction type"] button',
            ),
          ].some(
            (button) =>
              button.textContent.trim().startsWith(label) &&
              button.getAttribute("aria-pressed") === "true",
          ),
        label,
      );
      await page
        .getByRole("checkbox", { name: toggleLabel, exact: true })
        .waitFor();
    };
    const enable = async (label) => {
      const toggle = page.getByRole("checkbox", { name: label, exact: true });
      await toggle.check();
      await ready();
      await page.waitForFunction((label) => {
        const toggle = document.querySelector(`input[aria-label="${label}"]`);
        return toggle?.checked && !toggle.closest('[aria-busy="true"]');
      }, label);
    };
    const hold = (kind, key, value) => {
      let release;
      const started = new EventEmitter();
      const beginning = once(started, "started", {
        signal: AbortSignal.timeout(30_000),
      });
      beginning.catch(() => {});
      const delivery = new Promise((resolve) => (release = resolve));
      held = {
        kind,
        key,
        value,
        started: () => started.emit("started"),
        delivery,
        release,
      };
      return {
        beginning,
        release: () => {
          held = null;
          release();
        },
      };
    };
    await page.goto(pathToFileURL(path.join(root, "dist/index.html")).href);
    await ready();
    await page
      .getByRole("button", { name: "Integration", exact: true })
      .click();
    await page.getByRole("tab", { name: "Corrections", exact: true }).click();
    await select("Detector absorption", "Apply detector absorption");
    await enable("Apply detector absorption");
    const detector = page.getByRole("spinbutton", {
      name: "Detector thickness (µm)",
      exact: true,
    });
    const gate = hold("oiadac", "detector_thickness", 44);
    await detector.fill("44");
    await detector.press("Enter");
    await gate.beginning;
    assert.equal(
      (await correction("oiadac")).parameters.detector_thickness,
      44,
    );
    await detector.fill("55");
    assert.equal(
      await detector.evaluate((element) => element === document.activeElement),
      true,
    );
    gate.release();
    await ready();
    assert.equal(
      await detector.inputValue(),
      "55",
      "An older acknowledgement replaced the newer focused draft",
    );
    assert.equal(
      (await correction("oiadac")).parameters.detector_thickness,
      44,
      "Typing a draft must not commit it",
    );
    await detector.press("Enter");
    await ready();
    assert.equal(
      (await correction("oiadac")).parameters.detector_thickness,
      55,
    );
    await detector.fill("66");
    await detector.press("Escape");
    await ready();
    assert.equal(await detector.inputValue(), "55");
    assert.equal(
      (await correction("oiadac")).parameters.detector_thickness,
      55,
    );

    for (const invalid of ["", "-1"]) {
      await detector.fill(invalid);
      await detector.press("Enter");
      await ready();
      assert.equal(await detector.inputValue(), "55");
      assert.equal(
        (await correction("oiadac")).parameters.detector_thickness,
        55,
      );
    }

    // Plate and Slab share field names. Equal applied values must not allow a
    // component (or pending completion) to carry one correction's draft over.
    for (const [kind, label, toggle] of [
      ["plate", "Plate", "Apply plate absorption"],
      ["slab", "Slab", "Apply slab self-absorption"],
    ]) {
      await select(label, toggle);
      const thickness = page.getByRole("spinbutton", {
        name: "Thickness (mm)",
        exact: true,
      });
      await thickness.fill("0.3");
      await thickness.press("Enter");
      await enable(toggle);
      assert.equal((await correction(kind)).parameters.thickness, 0.3);
    }
    await select("Plate", "Apply plate absorption");
    const plateGate = hold("plate", "thickness", 0.4);
    const thickness = page.getByRole("spinbutton", {
      name: "Thickness (mm)",
      exact: true,
    });
    await thickness.fill("0.4");
    await select("Slab", "Apply slab self-absorption");
    await plateGate.beginning;
    assert.equal(
      await thickness.inputValue(),
      "0.3",
      "Plate draft leaked into the Slab field with the same parameter key",
    );
    await thickness.fill("0.5");
    plateGate.release();
    await ready();
    assert.equal(
      await thickness.inputValue(),
      "0.5",
      "Plate completion replaced a Slab draft",
    );
    assert.equal((await correction("slab")).parameters.thickness, 0.3);
    await thickness.press("Enter");
    await ready();
    assert.equal((await correction("slab")).parameters.thickness, 0.5);
    assert.equal((await correction("plate")).parameters.thickness, 0.4);
    assert.deepEqual(errors, []);
    receipts.push({
      browser: name,
      heldNumericAcknowledgement: true,
      separateCorrectionDrafts: true,
      escapeRestoresAppliedValue: true,
    });
  } catch (error) {
    await writeFile(
      path.join(out, `${name}-failure.json`),
      JSON.stringify(
        {
          error: String(error),
          text: await page
            ?.locator("body")
            .innerText()
            .catch(() => "closed"),
        },
        null,
        2,
      ),
    );
    await page
      ?.screenshot({ path: path.join(out, `${name}-failure.png`) })
      .catch(() => {});
    throw error;
  } finally {
    held?.release();
    await browser.close();
    await native.close();
  }
}
await writeFile(
  path.join(out, "headless.json"),
  JSON.stringify(receipts, null, 2) + "\n",
);
console.log(JSON.stringify(receipts, null, 2));
