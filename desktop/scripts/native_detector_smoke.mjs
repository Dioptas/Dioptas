import assert from "node:assert/strict";
import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { chromium, webkit } from "playwright";
import { nativeClient, root } from "./native_backend_client.mjs";
const artifacts = path.join(root, "desktop/artifacts/native-detectors");
await mkdir(artifacts, { recursive: true });
const receipts = [];
for (const [name, type] of [
  ["chromium", chromium],
  ["webkit", webkit],
]) {
  const native = nativeClient();
  const browser = await type.launch({ headless: true });
  const errors = [],
    commands = [];
  const invoke = async (a, p = {}) => {
    const r = await native.invoke(a, p);
    assert.equal(r.ok, true, `${a}: ${r.error}`);
    return r;
  };
  try {
    await invoke("example");
    const page = await browser.newPage({
      viewport: { width: 1440, height: 1000 },
    });
    page.setDefaultTimeout(45000);
    page.on("pageerror", (e) => errors.push(e.message));
    await page.exposeFunction("__nativeInvoke", async (a, p) => {
      commands.push([a, p]);
      return native.browserResult(await invoke(a, p));
    });
    await page.addInitScript(() => {
      window.__pending = 0;
      window.pywebview = {
        api: {
          invoke: async (a, p) => {
            const tracked = !["progress", "pixel"].includes(a);
            if (tracked) window.__pending++;
            try {
              return await window.__nativeInvoke(a, p);
            } finally {
              if (tracked) window.__pending--;
            }
          },
        },
      };
    });
    await page.goto(
      pathToFileURL(path.join(root, "dioptas/desktop/ui/index.html")).href,
    );
    const ready = async () => {
      await page.waitForFunction(
        () =>
          window.__pending === 0 &&
          !document.querySelector('.spin,.mask-view[aria-busy="true"]'),
      );
      await page.evaluate(
        () =>
          new Promise((r) =>
            requestAnimationFrame(() => requestAnimationFrame(r)),
          ),
      );
      assert.deepEqual(errors, []);
    };
    const button = (name) => page.getByRole("button", { name, exact: true });
    await page.getByTestId("detector-canvas").waitFor();
    await ready();
    const detector = page.getByLabel("Detector", { exact: true });
    assert.equal(await detector.locator("option").count(), 110);
    await detector.selectOption({ label: "Pilatus 1M" });
    await ready();
    assert.equal(
      (await invoke("state")).state.calibration.detector,
      "Pilatus 1M",
    );
    await page
      .getByLabel("Detector orientation", { exact: true })
      .selectOption("2");
    await ready();
    assert.equal(
      (await invoke("state")).state.calibration.detectorOrientation,
      2,
    );
    await button("Undo").click();
    await ready();
    assert.equal(
      (await invoke("state")).state.calibration.detectorOrientation,
      3,
    );
    await button("Redo").click();
    await ready();
    assert.equal(
      (await invoke("state")).state.calibration.detectorOrientation,
      2,
    );
    await button("Enter manually").click();
    await ready();
    const dialog = page.getByRole("dialog");
    await dialog.getByRole("tab", { name: "Fit2D", exact: true }).click();
    await ready();
    const center = dialog.getByLabel("Manual center x", { exact: true });
    await center.fill("450");
    await dialog
      .getByRole("button", { name: "Apply geometry", exact: true })
      .click();
    await ready();
    assert.ok(
      Math.abs((await invoke("state")).state.calibration.fit2d.centerX - 450) <
        1e-8,
    );
    assert.ok(
      commands.some(
        ([a, p]) => a === "manual_geometry" && p.convention === "fit2d",
      ),
    );
    assert.deepEqual(errors, []);
    await page.screenshot({ path: path.join(artifacts, `${name}.png`) });
    receipts.push({
      browser: name,
      detectors: 110,
      orientationUndoRedo: true,
      fit2d: true,
    });
  } finally {
    await browser.close();
    await native.close();
  }
}
await writeFile(
  path.join(artifacts, "receipt.json"),
  JSON.stringify(receipts, null, 2) + "\n",
);
console.log(JSON.stringify(receipts, null, 2));
