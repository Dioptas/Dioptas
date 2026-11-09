import assert from "node:assert/strict";
import { verifyIntegrationSettingsAuto } from "./integration_settings_auto.mjs";
import { mkdtemp, mkdir, copyFile, rm, writeFile } from "node:fs/promises";
import path from "node:path";
import { tmpdir } from "node:os";
import { pathToFileURL } from "node:url";
import { chromium, webkit } from "playwright";
import { nativeClient, root } from "./native_backend_client.mjs";
const artifacts = path.join(root, "desktop/artifacts/native-integration");
await mkdir(artifacts, { recursive: true });
const temp = await mkdtemp(path.join(tmpdir(), "dioptas-native-integration-"));
const paths = await Promise.all(
  [1, 2, 3].map(async (i) => {
    const p = path.join(temp, `scan_${i}.tif`);
    await copyFile(path.join(root, "dioptas/tests/data/CeO2_Pilatus1M.tif"), p);
    return p;
  }),
);
const receipts = [];
try {
  for (const [name, type] of [
    ["chromium", chromium],
    ["webkit", webkit],
  ]) {
    const native = nativeClient();
    const browser = await type.launch({ headless: true });
    try {
      const commands = [],
        errors = [];
      const invoke = async (action, payload = {}) => {
        commands.push(action);
        if (
          !["pixel", "image_levels", "integration_phase_guides"].includes(
            action,
          )
        )
          console.log(`${name}: ${action}`);
        const r = await native.invoke(action, payload);
        assert.equal(r.ok, true, `${action}: ${r.error}`);
        return r;
      };
      await invoke("open_calibration", {
        path: path.join(root, "dioptas/tests/data/CeO2_Pilatus1M.poni"),
      });
      await invoke("integration_settings", {
        bins: 128,
        cake_bins: 36,
        poisson_errors: true,
      });
      await invoke("open_image", {
        path: paths[0],
        directory: temp,
        multiple: false,
      });
      await invoke("integration_phase", {
        operation: "load",
        path: path.join(root, "dioptas/tests/data/jcpds/mo.jcpds"),
      });
      await invoke("batch_load", { paths });
      const batch = path.join(temp, `${name}.h5`);
      await invoke("integration_save_batch", { path: batch });
      await invoke("map_batch", { path: batch });
      const page = await browser.newPage({
        viewport: { width: 1500, height: 1000 },
      });
      page.setDefaultTimeout(45000);
      page.on("pageerror", (e) => errors.push(e.message));
      await page.exposeFunction("__nativeInvoke", async (a, p) =>
        native.browserResult(await invoke(a, p)),
      );
      await page.addInitScript(() => {
        window.pywebview = {
          api: { invoke: (a, p) => window.__nativeInvoke(a, p) },
        };
      });
      await page.goto(
        pathToFileURL(path.join(root, "dioptas/desktop/ui/index.html")).href,
      );
      await page
        .getByRole("button", { name: "Integration", exact: true })
        .click();
      await verifyIntegrationSettingsAuto(page, invoke);
      await page.getByRole("tab", { name: "Phase", exact: true }).click();
      await page
        .getByRole("button", {
          name: "Browse EoS Material Database",
          exact: true,
        })
        .click();
      const dialog = page.getByRole("dialog", {
        name: "EoS Material Database",
      });
      await dialog.waitFor();
      await dialog
        .getByRole("searchbox", { name: "Search materials" })
        .fill("gold");
      await dialog
        .getByRole("table", { name: "Database materials" })
        .getByText("Gold", { exact: true })
        .waitFor({ state: "visible" });
      await page.screenshot({
        path: path.join(artifacts, `${name}-native-catalog.png`),
      });
      await dialog
        .getByRole("button", { name: "Close EoS Material Database" })
        .click();
      await page
        .getByRole("button", { name: "Edit selected Phase", exact: true })
        .click();
      await page.getByRole("dialog").waitFor();
      await page.screenshot({
        path: path.join(artifacts, `${name}-native-editor.png`),
      });
      // Dismiss the scoped editor using its actual close control.
      const editor = page.getByRole("dialog");
      await editor.getByRole("button", { name: /Close.*editor/i }).click();
      await page.getByRole("button", { name: "Map", exact: true }).click();
      await page.getByTestId("scan-map").waitFor();
      await page.waitForTimeout(500);
      await page.screenshot({
        path: path.join(artifacts, `${name}-native-map.png`),
      });
      assert.deepEqual(errors, []);
      receipts.push({
        browser: name,
        runtime: "rust",
        pythonInChild: false,
        commands: [...new Set(commands)],
        errors,
      });
    } finally {
      await browser.close();
      await native.close();
    }
  }
} finally {
  await rm(temp, { recursive: true, force: true });
}
await writeFile(
  path.join(artifacts, "headless-workflow.json"),
  JSON.stringify(receipts, null, 2) + "\n",
);
console.log(JSON.stringify(receipts, null, 2));
