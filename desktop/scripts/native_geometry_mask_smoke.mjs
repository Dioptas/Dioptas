import assert from "node:assert/strict";
import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { chromium, webkit } from "playwright";
import { nativeClient, root } from "./native_backend_client.mjs";
const artifacts = path.join(root, "desktop/artifacts/native-geometry-mask");
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
      pathToFileURL(path.join(root, "desktop/dist/index.html")).href,
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
    const before = await invoke("state");
    for (const label of [
      "Rotate image +90°",
      "Flip image horizontally",
      "Flip image vertically",
      "Rotate image −90°",
      "Reset image transformations",
    ]) {
      await button(label).click();
      await ready();
    }
    const reset = await invoke("state");
    assert.deepEqual(reset.state.shape, before.state.shape);
    assert.equal(reset.rawImage.bufferId, before.rawImage.bufferId);
    await button("Rotate image +90°").click();
    await ready();
    await button("Undo").click();
    await ready();
    assert.equal(
      (await invoke("state")).rawImage.bufferId,
      before.rawImage.bufferId,
    );
    await button("Redo").click();
    await ready();
    assert.deepEqual((await invoke("state")).state.shape, [981, 1043]);
    await button("Mask").click();
    await ready();
    const click = async (x, y) => {
      const p = await page.getByTestId("detector-canvas").evaluate(
        (el, { x, y }) => {
          const b = el.getBoundingClientRect(),
            d = el.dataset;
          return {
            x:
              b.x +
              +d.plotLeft +
              ((x - +d.viewXMin) / (+d.viewXMax - +d.viewXMin)) * +d.plotWidth,
            y:
              b.y +
              +d.plotTop +
              ((+d.viewYMax - y) / (+d.viewYMax - +d.viewYMin)) * +d.plotHeight,
          };
        },
        { x, y },
      );
      await page.mouse.click(p.x, p.y);
    };
    for (const [shape, points] of [
      [
        "Rectangle",
        [
          [100, 150],
          [200, 240],
        ],
      ],
      [
        "Circle",
        [
          [400, 400],
          [440, 400],
        ],
      ],
      [
        "Polygon",
        [
          [200, 400],
          [250, 450],
          [180, 480],
        ],
      ],
      [
        "Arc",
        [
          [500, 300],
          [550, 350],
          [500, 400],
          [560, 350],
        ],
      ],
    ]) {
      await button(shape).click();
      for (const p of points) await click(...p);
      if (shape === "Polygon") {
        assert.equal(
          await page
            .getByTestId("detector-canvas")
            .evaluate((el) => el === document.activeElement),
          true,
          "Drawing focuses the canvas before keyboard polygon completion",
        );
        await page.keyboard.press("Enter");
      }
      await ready();
    }
    assert.ok((await invoke("state")).state.maskedPixels > 0);
    const originalMask = (await invoke("state")).mask.bufferId;
    await button("Grow").click();
    await ready();
    await button("Undo").click();
    await ready();
    assert.equal((await invoke("state")).mask.bufferId, originalMask);
    await button("Redo").click();
    await ready();
    for (const label of ["Shrink", "Invert", "Clear"]) {
      await button(label).click();
      await ready();
    }
    assert.equal((await invoke("state")).state.maskedPixels, 0);
    await page
      .getByRole("spinbutton", { name: "Above threshold counts" })
      .fill("500");
    await button("Above Thresh").click();
    await ready();
    await page.getByRole("radio", { name: "Unmask", exact: true }).check();
    await page
      .getByRole("spinbutton", { name: "Below threshold counts" })
      .fill("600");
    await button("Below Thresh").click();
    await ready();
    await button("Calibration").click();
    await ready();
    await button("Reset image transformations").click();
    await ready();
    await invoke("open_calibration", {
      path: path.join(root, "desktop/tests/data/CeO2_Pilatus1M.poni"),
    });
    // Refresh through the app before exercising the calibrated range controls.
    await page.reload();
    await page.getByTestId("detector-canvas").waitFor();
    await ready();
    await button("Mask").click();
    await ready();
    await page
      .getByRole("spinbutton", { name: "Mask range minimum" })
      .fill("10");
    await page
      .getByRole("spinbutton", { name: "Mask range maximum" })
      .fill("15");
    await button("Inside").click();
    await ready();
    await page.screenshot({
      path: path.join(artifacts, `${name}-geometric-masks.png`),
    });
    for (const operation of [
      "rectangle",
      "circle",
      "polygon",
      "arc",
      "grow",
      "shrink",
      "invert",
      "clear",
      "above",
      "below",
      "range",
    ]) {
      assert.ok(
        commands.some(
          ([a, p]) => a === "mask_edit" && p.operation === operation,
        ),
        operation,
      );
    }
    assert.deepEqual(errors, []);
    receipts.push({
      browser: name,
      errors,
      transforms: 5,
      maskOperations: 11,
      history: "actual Undo/Redo controls",
      pythonInChild: false,
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
