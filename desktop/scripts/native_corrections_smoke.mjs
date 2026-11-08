import assert from "node:assert/strict";
import { mkdtemp, mkdir, writeFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { chromium, webkit } from "playwright";
import { nativeClient, root } from "./native_backend_client.mjs";

const temp = await mkdtemp(path.join(tmpdir(), "dioptas-corrections-"));
const out = path.join(root, "desktop/artifacts/native-corrections");
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
        commands = [];
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
        assert.equal(r.ok, true, `${action}: ${r.error}`);
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
      await page.goto(
        pathToFileURL(path.join(root, "dioptas/desktop/ui/index.html")).href,
      );
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
      const state = async () => (await native.invoke("state")).state;
      const wait = async (predicate) => {
        for (let i = 0; i < 100; i++) {
          if (predicate(await state())) return;
          await page.waitForTimeout(50);
        }
        throw Error("Native state did not reach expected correction settings");
      };
      await type("Transfer").click();
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
        await type(label).click();
        const thickness = page.getByLabel("Thickness (mm)", { exact: true });
        await thickness.fill("0.3");
        await thickness.press("Enter");
        await page
          .getByRole("checkbox", {
            name:
              kind === "plate"
                ? "Apply plate absorption"
                : "Apply slab self-absorption",
          })
          .check();
        await wait(
          (s) =>
            s.integration.corrections[kind].enabled &&
            s.integration.corrections[kind].parameters.thickness === 0.3,
        );
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
      await type("Transfer").click();
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
        for (const label of ["Transfer", "Plate", "Slab"]) {
          await type(label).click();
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
        corrections: ["transfer", "plate", "slab"],
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
