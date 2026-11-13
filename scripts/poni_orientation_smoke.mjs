// Headless check of image orientation in the calibration Image tab: the rotate
// and flip buttons are the only orientation control, and loading a PONI file
// that records a rotated view turns the image and says so in the footer.
import assert from "node:assert/strict";
import { mkdir, mkdtemp, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { createServer } from "vite";
import { chromium, webkit } from "playwright";
import { nativeClient } from "./native_backend_client.mjs";

const desktop = fileURLToPath(new URL("../", import.meta.url));
const artifacts = path.join(desktop, "artifacts/poni-orientation");
await mkdir(artifacts, { recursive: true });
const temporary = await mkdtemp(
  path.join(tmpdir(), "dioptas-poni-orientation-"),
);

// A 40 × 60 float64 NPY image, so a quarter turn changes its shape.
const image = path.join(temporary, "wide.npy");
let header = "{'descr': '<f8', 'fortran_order': False, 'shape': (40, 60), }";
while ((10 + header.length + 1) % 64 !== 0) header += " ";
header += "\n";
const prefix = Buffer.from("\x93NUMPY\x01\x00", "latin1");
const length = Buffer.alloc(2);
length.writeUInt16LE(header.length);
const values = Buffer.alloc(40 * 60 * 8);
for (let i = 0; i < 40 * 60; i++) values.writeDoubleLE(i, i * 8);
await writeFile(
  image,
  Buffer.concat([prefix, length, Buffer.from(header, "latin1"), values]),
);
// Geometry for the rotated 60 × 40 view, recorded as such.
const calibration = path.join(temporary, "rotated.poni");
await writeFile(
  calibration,
  `# Dioptas image orientation: rotate_right
poni_version: 2.1
Detector: Detector
Detector_config: {"pixel1":0.0001,"pixel2":0.0001,"max_shape":[60,40],"orientation":3}
Distance: 0.1
Poni1: 0.002
Poni2: 0.003
Rot1: 0
Rot2: 0
Rot3: 0
Wavelength: 3e-11
`,
);

const native = nativeClient();
const invoke = native.invoke;
async function call(action, payload) {
  const result = await invoke(action, payload);
  assert.ok(result.ok, result.error);
  return result;
}
const server = await createServer({
  root: desktop,
  server: { host: "127.0.0.1", port: 0 },
});
await server.listen();
const browserName = process.argv.includes("--webkit") ? "webkit" : "chromium";
const browser = await (browserName === "webkit" ? webkit : chromium).launch({
  headless: true,
});
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
const errors = [];
page.on("pageerror", (e) => errors.push(e.message));
await page.exposeFunction("__dioptasInvoke", async (action, payload = {}) => {
  if (action === "open_calibration" && !payload.path)
    payload = { ...payload, path: calibration };
  return native.browserResult(await invoke(action, payload));
});
await page.addInitScript(() => {
  window.__orientationPending = 0;
  window.pywebview = {
    api: {
      invoke: async (action, payload) => {
        window.__orientationPending++;
        try {
          return await window.__dioptasInvoke(action, payload);
        } finally {
          window.__orientationPending--;
        }
      },
    },
  };
});
const button = (name) => page.getByRole("button", { name, exact: true });
async function ready() {
  await page.waitForFunction(
    () => !window.__orientationPending && !document.querySelector(".spin"),
  );
  await page.evaluate(
    () =>
      new Promise((resolve) =>
        requestAnimationFrame(() => requestAnimationFrame(resolve)),
      ),
  );
  assert.deepEqual(await page.getByRole("alert").allTextContents(), []);
}
const state = async () => (await call("state")).state;
const report = { browser: browserName, headless: true, checks: [] };
try {
  assert.equal((await call("__host__")).runtime, "rust");
  await call("open_image", { path: image });
  await page.goto(server.resolvedUrls.local[0]);
  await button("Rotate image +90°").waitFor({ state: "visible" });
  await ready();

  assert.equal(await page.getByLabel("Detector orientation").count(), 0);
  assert.equal(
    await page.getByRole("combobox", { name: /orientation/i }).count(),
    0,
  );
  report.checks.push("no detector orientation dropdown in the Image tab");

  await button("Rotate image +90°").click();
  await ready();
  assert.deepEqual((await state()).shape, [60, 40]);
  await button("Reset image transformations").click();
  await ready();
  assert.deepEqual((await state()).shape, [40, 60]);
  report.checks.push("rotate and reset buttons turn the image");

  await button("Load .poni").click();
  await ready();
  assert.equal(
    await page.getByRole("dialog").count(),
    0,
    "A recorded rotation turns the image instead of asking to replace it",
  );
  const loaded = await state();
  assert.equal(loaded.calibrated, true);
  assert.deepEqual(loaded.shape, [60, 40]);
  assert.deepEqual(loaded.calibration.transformations, ["rotate_matrix_p90"]);
  const footer = await page.locator("footer.app-status").textContent();
  assert.match(footer, /image orientation rotate_right from file/, footer);
  report.checks.push("loading a rotated PONI turns the image and reports it");
  await page.screenshot({
    path: path.join(artifacts, `loaded-${browserName}.png`),
  });

  assert.deepEqual(errors, []);
  await writeFile(
    path.join(artifacts, `report-${browserName}.json`),
    JSON.stringify(report, null, 2) + "\n",
  );
  console.log(JSON.stringify(report));
} catch (error) {
  await page.screenshot({
    path: path.join(artifacts, `failure-${browserName}.png`),
  });
  console.error(native.diagnostics.join("").slice(-4000));
  throw error;
} finally {
  await browser.close();
  await server.close();
  await native.close();
  await rm(temporary, { recursive: true, force: true });
}
