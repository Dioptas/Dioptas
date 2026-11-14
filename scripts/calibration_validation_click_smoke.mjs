import assert from "node:assert/strict";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { chromium } from "playwright";
import { nativeClient, root } from "./native_backend_client.mjs";

// Calibration validation shows the image, cake and pattern together. A cake or
// pattern click there marks the linked green position, as in Integration.
const native = nativeClient();
const browser = await chromium.launch({ headless: true });
try {
  assert.equal((await native.invoke("example")).ok, true);
  const calibrated = await native.invoke("open_calibration", {
    path: path.join(root, "tests/data/CeO2_Pilatus1M.poni"),
  });
  assert.ok(calibrated.ok, calibrated.error);
  const page = await browser.newPage({
    viewport: { width: 1440, height: 940 },
  });
  page.setDefaultTimeout(45000);
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.exposeFunction("__nativeInvoke", async (action, payload = {}) =>
    native.browserResult(await native.invoke(action, payload)),
  );
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
  await page.goto(pathToFileURL(path.join(root, "dist/index.html")).href);
  const ready = () =>
    page.waitForFunction(
      () => window.__pending === 0 && !document.querySelector(".spin"),
    );
  await page.getByTestId("detector-canvas").waitFor();
  await ready();
  await page
    .getByRole("tab", { name: "Step 4: Validate", exact: true })
    .click();
  const picking = page.getByLabel("Pick peaks", { exact: true });
  if (await picking.isChecked()) await picking.uncheck();
  const cake = page.getByTestId("cake-canvas");
  const pattern = page.getByTestId("pattern-canvas");
  await cake.waitFor();
  await pattern.waitFor();
  await ready();
  const clickInside = async (canvas, fx, fy) => {
    const box = await canvas.boundingBox();
    const v = await canvas.evaluate((el) => ({
      left: +el.dataset.plotLeft,
      top: +el.dataset.plotTop,
      width: +el.dataset.plotWidth,
      height: +el.dataset.plotHeight,
    }));
    await page.mouse.click(
      box.x + v.left + v.width * fx,
      box.y + v.top + v.height * fy,
    );
    await ready();
  };
  const linked = (canvas) => canvas.getAttribute("data-linked-position");
  assert.equal(await linked(cake), null, "No marker before a click");

  await clickInside(cake, 0.4, 0.5);
  await page.waitForFunction(
    () =>
      document.querySelector('[data-testid="cake-canvas"]')?.dataset
        .linkedPosition != null,
  );
  const fromCake = Number(await linked(cake));
  assert.ok(Number.isFinite(fromCake), "Cake click marks the cake");
  assert.ok(
    Number.isFinite(Number(await linked(pattern))),
    "Cake click marks the pattern",
  );
  assert.notEqual(
    (await page.getByTestId("click-readout").innerText()).trim(),
    "—",
    "Cake click fills the footer click position",
  );

  await clickInside(pattern, 0.7, 0.5);
  await page.waitForFunction(
    (before) =>
      Number(
        document.querySelector('[data-testid="cake-canvas"]')?.dataset
          .linkedPosition,
      ) !== before,
    fromCake,
  );
  assert.ok(
    Number.isFinite(Number(await linked(pattern))),
    "Pattern click marks the pattern",
  );
  assert.equal(
    await page.getByTestId("click-readout").getAttribute("data-plot"),
    "pattern",
  );
  assert.deepEqual(errors, []);
  console.log(
    "Calibration validation: cake and pattern clicks mark linked green positions",
  );
} finally {
  await browser.close();
  native.close?.();
}
