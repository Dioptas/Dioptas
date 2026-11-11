import assert from "node:assert/strict";
import { mkdir, writeFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { createServer } from "vite";
import { chromium, webkit } from "playwright";
import { nativeClient, root } from "./native_backend_client.mjs";
const artifacts = new URL(
  "../artifacts/dac-thermal-pressure/",
  import.meta.url,
);
await mkdir(artifacts, { recursive: true });
const server = await createServer({
  root: fileURLToPath(new URL("../", import.meta.url)),
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
      const errors = [];
      const calls = [];
      const call = async (action, args = {}) => {
        const r = await native.invoke(action, args);
        assert.equal(r.ok, true, `${action}: ${r.error}`);
        return r;
      };
      await call("open_image", {
        path: root + "/dioptas/tests/data/CeO2_Pilatus1M.tif",
      });
      await call("open_calibration", {
        path: root + "/dioptas/tests/data/CeO2_Pilatus1M.poni",
      });
      await call("integration_settings", { bins: 128, cake_bins: 24 });
      await call("integration_phase", {
        operation: "load_database",
        material_id: "gold",
        reference: 4,
      });
      await call("integration_phase", {
        operation: "update",
        index: 0,
        pressure: 40,
        temperature: 2000,
      });
      const volume = async () =>
        (await call("integration_phase_editor", { index: 0 })).phaseEditor
          .lattice.v;
      const initial = await volume();
      const page = await browser.newPage({
        viewport: { width: 1280, height: 800 },
      });
      page.on("pageerror", (e) => errors.push(e.message));
      await page.exposeFunction("__nativeInvoke", async (a, p) => {
        calls.push([a, p]);
        return native.browserResult(await call(a, p));
      });
      await page.addInitScript(() => {
        window.pywebview = {
          api: { invoke: (a, p) => window.__nativeInvoke(a, p) },
        };
      });
      await page.goto(server.resolvedUrls.local[0]);
      const ready = async () => {
        await page.waitForFunction(
          () =>
            document.querySelector(".app") && !document.querySelector(".spin"),
        );
      };
      await ready();
      await page
        .getByRole("button", { name: "Integration", exact: true })
        .click();
      await ready();
      await page.getByRole("button", { name: "Settings", exact: true }).click();
      await page.getByRole("tab", { name: "Phase", exact: true }).click();
      const enabled = page.getByRole("checkbox", {
        name: "DAC thermal pressure",
        exact: true,
      });
      const factor = page.getByRole("spinbutton", {
        name: "DAC thermal-pressure fraction",
      });
      assert.equal(await enabled.isChecked(), false);
      assert.equal(await factor.isDisabled(), true);
      assert.equal(await factor.inputValue(), "0.25");
      await enabled.click();
      await page.waitForFunction(
        () =>
          document.querySelector('[aria-label="DAC thermal pressure"]').checked,
      );
      await ready();
      assert.equal(await enabled.isChecked(), true);
      assert.ok((await volume()) < initial);
      const quarter = await volume();
      await factor.fill("0.4");
      await factor.press("Enter");
      await ready();
      await page.waitForFunction(
        () =>
          document.querySelector('[aria-label="DAC thermal-pressure fraction"]')
            .value === "0.4",
      );
      assert.ok((await volume()) < quarter);
      await factor.fill("1");
      await factor.press("Enter");
      assert.equal(await factor.inputValue(), "0.4");
      await enabled.click();
      await page.waitForFunction(
        () =>
          !document.querySelector('[aria-label="DAC thermal pressure"]')
            .checked,
      );
      await ready();
      assert.equal(await factor.isDisabled(), true);
      assert.equal(await factor.inputValue(), "0.4");
      assert.equal(await volume(), initial);
      await enabled.click();
      await page.waitForFunction(
        () =>
          document.querySelector('[aria-label="DAC thermal pressure"]').checked,
      );
      await ready();
      assert.ok((await volume()) < quarter);
      const group = page.getByRole("group", {
        name: "DAC thermal pressure settings",
      });
      assert.match(await group.innerText(), /dimensionless/);
      assert.match(await group.innerText(), /cold\/reference P₀/);
      for (const width of [1280, 1000]) {
        await page.setViewportSize({ width, height: 800 });
        await page.waitForTimeout(150);
        await page.screenshot({
          path: fileURLToPath(new URL(`${name}-${width}.png`, artifacts)),
        });
        const bounds = await group.boundingBox();
        assert.ok(
          bounds.x >= 0 && bounds.x + bounds.width <= width,
          JSON.stringify({ width, bounds }),
        );
        const f = await factor.boundingBox();
        assert.ok(
          f.x >= bounds.x && f.x + f.width <= bounds.x + bounds.width + 1,
        );
        await page.screenshot({
          path: fileURLToPath(new URL(`${name}-${width}.png`, artifacts)),
        });
      }
      await page.getByRole("tab", { name: "General", exact: true }).click();
      await page.getByRole("button", { name: "Larger", exact: true }).click();
      await page.getByRole("tab", { name: "Phase", exact: true }).click();
      const largeBounds = await factor.boundingBox();
      assert.ok(largeBounds.x + largeBounds.width <= 1000);
      await page.screenshot({ path: fileURLToPath(new URL(`${name}-larger.png`, artifacts)) });
      await page.getByRole("button", { name: "Close settings" }).click();
      await ready();
      await page.getByRole("tab", { name: "Phase", exact: true }).click();
      assert.equal(
        await page
          .getByRole("checkbox", { name: "DAC thermal pressure", exact: true })
          .count(),
        0,
        "Control belongs in Settings",
      );
      assert.equal(
        await page
          .getByRole("columnheader", { name: "P₀ (GPa)", exact: true })
          .count(),
        1,
      );
      assert.deepEqual(errors, []);
      receipts.push({
        browser: name,
        initialVolume: initial,
        defaultConfinedVolume: quarter,
        factor: 0.4,
        commands: calls.filter(([a]) => a === "integration_phase"),
      });
    } finally {
      await browser.close();
      native.close();
    }
  }
  await writeFile(
    new URL("receipt.json", artifacts),
    JSON.stringify(receipts, null, 2) + "\n",
  );
  console.log(JSON.stringify(receipts, null, 2));
} finally {
  await server.close();
}
