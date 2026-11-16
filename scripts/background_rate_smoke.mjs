import assert from "node:assert/strict";
import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { chromium, webkit } from "playwright";
import { nativeClient, root } from "./native_backend_client.mjs";

const receipts = [];
for (const [name, browserType] of [
  ["chromium", chromium],
  ["webkit", webkit],
]) {
  const native = nativeClient();
  const browser = await browserType.launch({ headless: true });
  const call = async (action, payload = {}) => {
    const result = await native.invoke(action, payload);
    assert.equal(result.ok, true, `${action}: ${result.error}`);
    return result;
  };
  try {
    await call("manual_geometry", {
      convention: "pyfai",
      values: {
        dist: 0.2,
        poni1: 0.003,
        poni2: 0.004,
        rot1: 0,
        rot2: 0,
        rot3: 0,
        pixel1: 0.0001,
        pixel2: 0.0001,
        wavelength: 4e-11,
        polarization_factor: 0,
      },
    });
    await call("integration_settings", {
      bins: 256,
      cake_bins: 12,
      trim_zeros: false,
    });
    const source = path.join(root, "backend/tests/fixtures/combined-counts.h5");
    await call("open_image", { path: source, dataset: "/counts" });
    await call("integration_background", {
      enabled: true,
      iterations: 5,
      order: 3,
      smoothing: 0.01,
    });
    const loaded = await call("map_load", { paths: [source] });
    const page = await browser.newPage({
      viewport: { width: 1440, height: 1000 },
    });
    page.setDefaultTimeout(30000);
    const errors = [];
    page.on("pageerror", (error) => errors.push(error.message));
    await page.exposeFunction("__nativeInvoke", async (action, payload) =>
      native.browserResult(await call(action, payload)),
    );
    await page.addInitScript(() => {
      window.__pending = 0;
      window.__updates = [];
      window.pywebview = {
        api: {
          invoke: async (action, payload) => {
            const track = !["progress", "pixel"].includes(action);
            if (track) window.__pending++;
            if (
              [
                "integration_background",
                "map_roi",
                "map_refresh",
                "map_snapshot",
              ].includes(action)
            )
              window.__updates.push({
                action,
                time: performance.now(),
                payload,
              });
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
    await page.getByTestId("detector-canvas").waitFor();
    const settled = async () => {
      await page.waitForFunction(
        () =>
          window.__pending === 0 &&
          !document.querySelector(".spin") &&
          document.querySelector('[data-testid="pattern-canvas"]')?.dataset
            .regionUpdating !== "true",
      );
    };
    const drag = async (fromFraction, toFraction, steps) => {
      const canvas = page.getByTestId("pattern-canvas");
      const coordinates = await canvas.evaluate(
        (element, [from, to]) => {
          const d = element.dataset,
            box = element.getBoundingClientRect();
          const region = JSON.parse(d.regions)[0];
          const position = (value) =>
            box.left +
            +d.plotLeft +
            ((value - +d.viewXMin) / (+d.viewXMax - +d.viewXMin)) *
              +d.plotWidth;
          const width = region.max - region.min;
          return {
            x0: position(region.min + from * width),
            x1: position(region.min + to * width),
            y: box.top + +d.plotTop + +d.plotHeight * 0.6,
          };
        },
        [fromFraction, toFraction],
      );
      await page.mouse.move(coordinates.x0, coordinates.y);
      await page.mouse.down();
      await page.mouse.move(coordinates.x1, coordinates.y, { steps });
      await page.mouse.up();
      await settled();
    };
    await settled();
    await page
      .getByRole("button", { name: "Integration", exact: true })
      .click();
    await page
      .getByRole("button", { name: "Inspect pattern background", exact: true })
      .click();
    await page.waitForFunction(
      () =>
        JSON.parse(
          document.querySelector('[data-testid="pattern-canvas"]').dataset
            .regions,
        ).length > 0,
    );
    await page.evaluate(() => {
      window.__updates = [];
    });
    await drag(0, 0.15, 90);
    const patternUpdates = await page.evaluate(() =>
      window.__updates.filter((x) => x.action === "integration_background"),
    );
    assert.ok(patternUpdates.length >= 2);
    for (let i = 1; i < patternUpdates.length; i++)
      assert.ok(
        patternUpdates[i].time - patternUpdates[i - 1].time >= 32,
        "Current-pattern refits exceed 30 Hz",
      );
    assert.equal(
      await page.evaluate(
        () => window.__updates.filter((x) => x.action === "map_refresh").length,
      ),
      0,
    );
    const pending = await call("state");
    assert.equal(pending.map.backgroundPending, true);
    assert.deepEqual(pending.map.values, loaded.map.values);
    const region = await page
      .getByTestId("pattern-canvas")
      .evaluate((el) => JSON.parse(el.dataset.regions)[0]);
    assert.ok(
      Math.abs(
        pending.state.integration.patternBackground.range[0] - region.min,
      ) < 1e-9,
    );
    const x = pending.pattern.x;
    await call("map_roi", {
      op: "update",
      name: "A",
      minimum: x[Math.floor(x.length * 0.3)],
      maximum: x[Math.floor(x.length * 0.7)],
    });
    await page.getByRole("button", { name: "Map", exact: true }).click();
    await page.getByTestId("scan-map").waitFor();
    await page.waitForFunction(() =>
      window.__updates.some((x) => x.action === "map_refresh"),
    );
    await settled();
    await page.evaluate(() => {
      window.__updates = [];
    });
    await drag(0.5, 0.65, 120);
    const mapUpdates = await page.evaluate(() =>
      window.__updates.filter((x) => x.action === "map_roi"),
    );
    assert.ok(mapUpdates.length >= 2, "The map should update while dragging");
    for (let i = 1; i < mapUpdates.length; i++)
      assert.ok(
        mapUpdates[i].time - mapUpdates[i - 1].time >= 490,
        "Whole-map reductions exceed 2 Hz",
      );
    const final = await call("state");
    const window = await page
      .getByTestId("pattern-canvas")
      .evaluate((el) => JSON.parse(el.dataset.regions)[0]);
    assert.ok(
      Math.abs(final.map.rois[0].min - window.min) < 1e-9,
      "Release position was lost",
    );
    assert.deepEqual(errors, []);
    receipts.push({
      browser: name,
      patternUpdates: patternUpdates.length,
      mapUpdates: mapUpdates.length,
      patternMinIntervalMs: Math.min(
        ...patternUpdates
          .slice(1)
          .map((x, i) => x.time - patternUpdates[i].time),
      ),
      mapMinIntervalMs: Math.min(
        ...mapUpdates.slice(1).map((x, i) => x.time - mapUpdates[i].time),
      ),
      finalPositionCommitted: true,
    });
  } finally {
    await browser.close();
    await native.close();
  }
}
await mkdir(path.join(root, "artifacts/background-rate"), { recursive: true });
await writeFile(
  path.join(root, "artifacts/background-rate/receipt.json"),
  JSON.stringify(receipts, null, 2) + "\n",
);
console.log(JSON.stringify(receipts, null, 2));
