import assert from "node:assert/strict";
import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { chromium, webkit } from "playwright";
import { nativeClient, root } from "./native_backend_client.mjs";
const artifacts = path.join(root, "desktop/artifacts/native-lacosmic");
await mkdir(artifacts, { recursive: true });
const receipts = [];
for (const [name, type] of [
  ["chromium", chromium],
  ["webkit", webkit],
]) {
  const native = nativeClient(),
    browser = await type.launch({ headless: true });
  const errors = [],
    cosmicReplies = [],
    progress = [];
  const call = async (a, p = {}) => {
    const r = await native.invoke(a, p);
    assert.equal(r.ok, true, `${a}: ${r.error}`);
    return r;
  };
  try {
    await call("example");
    const page = await browser.newPage({
      viewport: { width: 1440, height: 1000 },
    });
    page.setDefaultTimeout(45000);
    page.on("pageerror", (e) => errors.push(e.message));
    await page.exposeFunction("__nativeInvoke", async (a, p) => {
      const r = await call(a, p);
      if (a === "mask_edit" && p.operation === "cosmic") cosmicReplies.push(r);
      if (a === "progress" && r.progress?.label === "Cosmic removal")
        progress.push(r.progress);
      return native.browserResult(r);
    });
    await page.addInitScript(() => {
      window.__pending = 0;
      window.__secondCosmicPass = false;
      window.pywebview = {
        api: {
          invoke: async (a, p) => {
            const track = !["progress", "pixel"].includes(a);
            if (track) window.__pending++;
            try {
              const r = await window.__nativeInvoke(a, p);
              if (
                a === "progress" &&
                r.progress?.label === "Cosmic removal" &&
                r.progress.running &&
                r.progress.current === 1
              )
                window.__secondCosmicPass = true;
              return r;
            } finally {
              if (track) window.__pending--;
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
        () => window.__pending === 0 && !document.querySelector(".spin"),
      );
      await page.evaluate(
        () =>
          new Promise((r) =>
            requestAnimationFrame(() => requestAnimationFrame(r)),
          ),
      );
      assert.deepEqual(errors, []);
    };
    await page.getByTestId("detector-canvas").waitFor();
    await ready();
    await page.getByRole("button", { name: "Mask", exact: true }).click();
    await ready();
    const before = await call("state");
    const cosmic = page.getByRole("button", {
      name: "Cosmic Removal",
      exact: true,
    });
    await cosmic.click();
    await ready();
    const after = await call("state");
    assert.equal(after.state.maskedPixels, 81991);
    assert.equal(after.image.bufferId, before.image.bufferId);
    assert.equal(after.rawImage.bufferId, before.rawImage.bufferId);
    assert.deepEqual(after.state.calibration, before.state.calibration);
    await page.getByRole("button", { name: "Undo", exact: true }).click();
    await ready();
    assert.equal((await call("state")).state.maskedPixels, 0);
    await page.getByRole("button", { name: "Redo", exact: true }).click();
    await ready();
    assert.equal((await call("state")).mask.bufferId, after.mask.bufferId);
    await page.screenshot({
      path: path.join(artifacts, `${name}-cosmic-removal.png`),
    });
    const baseline = await call("state");
    await page.evaluate(() => (window.__secondCosmicPass = false));
    await cosmic.click();
    await page.waitForFunction(() => window.__secondCosmicPass);
    await page
      .getByRole("button", { name: "Cancel mask processing", exact: true })
      .click();
    await ready();
    assert.equal(cosmicReplies.at(-1).cancelled, true);
    assert.deepEqual(await call("state"), baseline);
    assert.ok(
      progress.some((p) => p.current === 0) &&
        progress.some((p) => p.current === 1),
    );
    assert.deepEqual(errors, []);
    receipts.push({
      browser: name,
      maskedPixels: after.state.maskedPixels,
      history: "Undo/Redo",
      cancellation: "actual Cancel in second pass",
      sourceImagesUnchanged: true,
      errors,
    });
  } finally {
    await browser.close();
    await native.close();
  }
}
await writeFile(
  path.join(artifacts, "headless.json"),
  JSON.stringify(receipts, null, 2) + "\n",
);
console.log(JSON.stringify(receipts, null, 2));
