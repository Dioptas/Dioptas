import assert from "node:assert/strict";
import { cp, mkdir, mkdtemp, rm, writeFile } from "node:fs/promises";
import { execFileSync } from "node:child_process";
import { tmpdir } from "node:os";
import path from "node:path";
import { createServer } from "vite";
import { chromium, webkit } from "playwright";
import { nativeClient, root } from "./native_backend_client.mjs";
import { runExample } from "./test_fixtures.mjs";
import { setInterfaceTextSize } from "./plot_navigation.mjs";
const desktop = root,
  artifacts = path.join(desktop, "artifacts/hdf5-master-vds");
await mkdir(artifacts, { recursive: true });
const temp = await mkdtemp(path.join(tmpdir(), "dioptas-master-vds-"));
runExample("hdf5_master_fixture", temp);
const metadata = JSON.parse(
  execFileSync(
    "cargo",
    [
      "metadata",
      "--manifest-path",
      path.join(desktop, "backend/Cargo.toml"),
      "--format-version",
      "1",
    ],
    { encoding: "utf8", maxBuffer: 32 * 1024 * 1024 },
  ),
);
const library = path.dirname(
  metadata.packages.find((p) => p.name === "dioptrin-io").manifest_path,
);
await cp(
  path.join(library, "tests/data/vds-printf"),
  path.join(temp, "printf"),
  { recursive: true },
);
const server = await createServer({
  root: desktop,
  server: { host: "127.0.0.1", port: 0 },
});
await server.listen();
const reports = [];
try {
  for (const [name, type] of [
    ["chromium", chromium],
    ["webkit", webkit],
  ]) {
    const native = nativeClient(),
      browser = await type.launch({ headless: true });
    const page = await browser.newPage({
        viewport: { width: 1440, height: 940 },
      }),
      errors = [];
    page.on("pageerror", (e) => errors.push(e.message));
    let chosenImage = path.join(temp, "eiger-master.h5"),
      chosenCompanion = path.join(temp, "parts/a.h5"),
      cancelChooser = false;
    const project = path.join(temp, `${name}.dio`),
      calls = [];
    const call = async (action, payload = {}) => {
      const r = await native.invoke(action, payload);
      assert.equal(r.ok, true, `${action}: ${r.error}`);
      return r;
    };
    const button = (name) => page.getByRole("button", { name, exact: true });
    const source = () =>
      page.getByRole("combobox", { name: "Image source", exact: true });
    const ready = async () => {
      await page.waitForFunction(
        () => !window.__sourcePending && !document.querySelector(".spin"),
      );
      await page.evaluate(
        () =>
          new Promise((r) =>
            requestAnimationFrame(() => requestAnimationFrame(r)),
          ),
      );
    };
    const state = async () => (await call("state")).state;
    const pixel = async () => (await call("pixel", { x: 0, y: 0 })).pixel.value;
    const report = { browser: name, headless: true, checks: [] };
    try {
      const host = await call("__host__");
      assert.equal(host.runtime, "rust");
      assert.equal(host.engine, "dioptrin");
      report.runtime = host.runtime;
      report.engine = host.engine;
      await call("open_image", { path: chosenImage });
      await page.exposeFunction(
        "__sourceInvoke",
        async (action, payload = {}) => {
          calls.push({ action, payload });
          if (action === "choose_hdf5_companion")
            return cancelChooser
              ? { ok: true, cancelled: true }
              : { ok: true, chosenPath: chosenCompanion };
          if (action === "open_image" && !payload.path)
            payload = { ...payload, path: chosenImage };
          if (
            ["save_project", "open_project"].includes(action) &&
            !payload.path
          )
            payload = { ...payload, path: project };
          return native.browserResult(await native.invoke(action, payload));
        },
      );
      await page.addInitScript(() => {
        window.__sourcePending = 0;
        window.pywebview = {
          api: {
            invoke: async (action, payload) => {
              window.__sourcePending++;
              try {
                return await window.__sourceInvoke(action, payload);
              } finally {
                window.__sourcePending--;
              }
            },
          },
        };
      });
      await page.goto(server.resolvedUrls.local[0]);
      await source().waitFor();
      await ready();
      assert.equal(await source().inputValue(), "");
      assert.equal((await state()).integration.frames, 4);
      await source().selectOption("/entry/data/data_000002");
      await ready();
      assert.equal(await pixel(), 30);
      await source().selectOption("");
      await ready();
      assert.equal((await state()).integration.frames, 4);
      await button("Integration").click();
      await ready();
      await page.getByRole("tab", { name: "Image", exact: true }).click();
      await ready();
      await button("Integration next frame").click();
      await ready();
      assert.equal(await pixel(), 11);
      report.checks.push(
        "standard Open and both source selectors retain automatic multi-companion Eiger order",
      );
      chosenImage = path.join(temp, "relocated.h5");
      const before = await state();
      await button("Load image…").click();
      const dialog = page.getByRole("dialog", {
        name: "HDF5 source files",
        exact: true,
      });
      await dialog.waitFor();
      await ready();
      assert.deepEqual(await state(), before);
      await page.keyboard.press("Escape");
      await dialog.waitFor({ state: "hidden" });
      assert.deepEqual(await state(), before);
      await button("Load image…").click();
      await dialog.waitFor();
      await ready();
      cancelChooser = true;
      await dialog
        .getByRole("button", { name: "Choose…", exact: true })
        .first()
        .click();
      await ready();
      assert.equal(
        await dialog.getByRole("textbox").first().inputValue(),
        "/missing/acquisition/a.h5",
      );
      cancelChooser = false;
      await dialog
        .getByRole("button", { name: "Choose…", exact: true })
        .first()
        .click();
      await ready();
      chosenCompanion = path.join(temp, "parts/b.h5");
      await dialog
        .getByRole("button", { name: "Choose…", exact: true })
        .nth(1)
        .click();
      await ready();
      await page.screenshot({
        path: path.join(artifacts, `${name}-bindings-wide.png`),
      });
      await page.setViewportSize({ width: 680, height: 650 });
      await page.screenshot({
        path: path.join(artifacts, `${name}-bindings-compact.png`),
      });
      const box = await dialog.boundingBox();
      assert(
        box.x >= 0 &&
          box.x + box.width <= 680 &&
          box.y >= 0 &&
          box.y + box.height <= 650,
      );
      await dialog
        .getByRole("button", { name: "Open image", exact: true })
        .click();
      await dialog.waitFor({ state: "hidden" });
      await ready();
      assert.equal(await pixel(), 10);
      assert.equal((await state()).integration.frames, 4);
      await page.setViewportSize({ width: 1440, height: 940 });
      await button("Integration next frame").click();
      await ready();
      assert.equal(await pixel(), 11);
      await button("Save project").click();
      await ready();
      chosenImage = path.join(temp, "raw.h5");
      await button("Load image…").click();
      await ready();
      assert.equal(await pixel(), 50);
      await button("Open project").click();
      await ready();
      assert.equal(await pixel(), 11);
      await button("Integration next frame").click();
      await ready();
      assert.equal(await pixel(), 30);
      report.checks.push(
        "missing absolute VDS choices, chooser cancel, Escape rollback, compact dialog, project and frame reconnect",
      );
      await setInterfaceTextSize(page, true);
      chosenImage = path.join(temp, "relocated.h5");
      await button("Load image…").click();
      await dialog.waitFor();
      await ready();
      await page.setViewportSize({ width: 680, height: 650 });
      await page.screenshot({
        path: path.join(artifacts, `${name}-bindings-larger.png`),
      });
      const large = await dialog.boundingBox();
      assert(
        large.x >= 0 &&
          large.x + large.width <= 680 &&
          large.y >= 0 &&
          large.y + large.height <= 650,
      );
      await dialog.getByRole("button", { name: "Cancel", exact: true }).click();
      await ready();
      await page.setViewportSize({ width: 1440, height: 940 });
      chosenImage = path.join(temp, "nested.h5");
      await button("Load image…").click();
      await ready();
      assert.equal(await pixel(), 10);
      chosenImage = path.join(temp, "raw.h5");
      await button("Load image…").click();
      await ready();
      assert.equal(await pixel(), 50);
      await button("Integration next frame").click();
      await ready();
      assert.equal(await pixel(), 51);
      report.checks.push(
        "native generic nested VDS and split external raw windows; Larger text layout",
      );
      chosenImage = path.join(temp, "printf/files-bool.h5");
      await button("Load image…").click();
      await dialog.waitFor();
      await ready();
      const blocks = dialog.getByRole("spinbutton", {
        name: "Source blocks for files-bool-%b.h5",
        exact: true,
      });
      await blocks.fill("0");
      assert.equal(
        await dialog
          .getByRole("button", { name: "Open image", exact: true })
          .isDisabled(),
        true,
      );
      await blocks.fill("2");
      await dialog
        .getByRole("button", { name: "Open image", exact: true })
        .click();
      await dialog.waitFor({ state: "hidden" });
      await ready();
      const reset = page.getByRole("dialog", {
        name: "Image dimensions changed",
        exact: true,
      });
      await reset.waitFor();
      await reset
        .getByRole("button", { name: "Open image", exact: true })
        .click();
      await ready();
      assert.equal((await state()).integration.frames, 4);
      report.checks.push(
        "explicit finite printf block count, zero rejected, detector-size confirmation retained",
      );
      assert.deepEqual(errors, []);
      report.calls = calls;
      reports.push(report);
    } finally {
      await browser.close();
      await native.close();
    }
  }
  await writeFile(
    path.join(artifacts, "receipt.json"),
    JSON.stringify(reports, null, 2) + "\n",
  );
  console.log(
    "HDF5 master/VDS workflow passed in headless Chromium and WebKit.",
  );
} finally {
  await server.close();
  await rm(temp, { recursive: true, force: true });
}
