import { testFixture } from "./test_fixtures.mjs";
import assert from "node:assert/strict";
import { mkdtemp, mkdir, rm, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { chromium, webkit } from "playwright";
import { nativeClient, root } from "./native_backend_client.mjs";
const artifacts = path.join(root, "desktop/artifacts/native-map-progress");
await mkdir(artifacts, { recursive: true });
const temp = await mkdtemp(path.join(os.tmpdir(), "dioptas-map-progress-"));
const source = path.join(temp, "scan.h5");
// Keep real native work long enough for progress polling in fast kernels.
const frameCount = 8192;
testFixture("series", source, "bitshuffle-lz4", frameCount);
const receipts = [];
try {
  for (const [name, type] of [
    ["chromium", chromium],
    ["webkit", webkit],
  ]) {
    const native = nativeClient();
    const browser = await type.launch({ headless: true });
    const errors = [],
      observed = [],
      rates = [];
    const call = async (a, p = {}) => {
      const r = await native.invoke(a, p);
      assert.equal(r.ok, true, `${a}: ${r.error}`);
      return r;
    };
    try {
      await call("manual_geometry", {
        convention: "pyfai",
        values: {
          dist: 0.13,
          poni1: 0.0192,
          poni2: 0.0224,
          rot1: 0.008,
          rot2: -0.013,
          rot3: 0.02,
          pixel1: 0.0001,
          pixel2: 0.0001,
          wavelength: 0.5e-10,
          polarization_factor: 0.965,
        },
      });
      await call("integration_settings", {
        bins: 128,
        cake_bins: 24,
        trim_zeros: false,
        method: process.env.DIOPTAS_MAP_TEST_METHOD ?? "polygon",
      });
      await call("open_image", { path: source, dataset: "frames" });
      // Seed a finished map and a non-default layer before loading again.
      await call("map_load", { paths: [source] });
      await call("map_roi", {
        op: "update",
        name: "A",
        minimum: 1.1,
        maximum: 2.3,
        reduction: "mean",
        background: false,
      });
      const before = await call("map_expression", {
        name: "Signal",
        expression: "A*2+3",
      });
      const page = await browser.newPage({
        viewport: { width: 1440, height: 1000 },
      });
      page.setDefaultTimeout(45000);
      page.on("pageerror", (e) => errors.push(e.message));
      await page.exposeFunction("__nativeInvoke", async (a, p) => {
        const r = await call(
          a,
          a === "map_load" ? { ...p, paths: [source] } : p,
        );
        if (a === "progress" && r.progress?.mapPreview)
          observed.push(r.progress.mapPreview);
        if (a === "progress" && r.progress?.current > 0 && r.progress.fps > 0) {
          assert.ok(
            Math.abs(
              r.progress.fps * r.progress.elapsedSeconds - r.progress.current,
            ) < 1e-8,
          );
          rates.push(r.progress.fps);
        }
        return native.browserResult(r);
      });
      await page.addInitScript(() => {
        window.__pending = 0;
        window.pywebview = {
          api: {
            invoke: async (a, p) => {
              const track = !["progress", "pixel"].includes(a);
              if (track) window.__pending++;
              try {
                return await window.__nativeInvoke(a, p);
              } finally {
                if (track) window.__pending--;
              }
            },
          },
        };
      });
      await page.goto(
        pathToFileURL(path.join(root, "desktop/dist/index.html")).href,
      );
      await page.getByTestId("detector-canvas").waitFor();
      const ready = () =>
        page.waitForFunction(
          () => window.__pending === 0 && !document.querySelector(".spin"),
        );
      await ready();
      await page.getByRole("button", { name: "Map", exact: true }).click();
      await page.getByTestId("scan-map").waitFor();
      // Fresh detector views filter gaps; the map heatmap keeps its separate
      // default. An intentional change must survive a page/app restart.
      const detectorSettings = () =>
        page.getByRole("button", {
          name: "Detector histogram settings",
          exact: true,
        });
      const gapFilter = () =>
        page.getByRole("checkbox", {
          name: "Filter detector gaps",
          exact: true,
        });
      await detectorSettings().click();
      assert.equal(await gapFilter().isChecked(), true);
      await page.waitForFunction(
        () =>
          JSON.parse(
            localStorage.getItem("dioptas-auto-levels-v1:map") || "null",
          )?.filter_gaps === false,
      );
      await gapFilter().uncheck();
      await page.waitForFunction(
        () =>
          JSON.parse(
            localStorage.getItem("dioptas-auto-levels-v1:map-detector") ||
              "null",
          )?.filter_gaps === false,
      );
      await page.keyboard.press("Escape");
      await page.reload();
      await page.getByTestId("detector-canvas").waitFor();
      await ready();
      await page.getByRole("button", { name: "Map", exact: true }).click();
      await detectorSettings().click();
      assert.equal(await gapFilter().isChecked(), false);
      await gapFilter().check();
      await page.waitForFunction(
        () =>
          JSON.parse(
            localStorage.getItem("dioptas-auto-levels-v1:map-detector") ||
              "null",
          )?.filter_gaps === true,
      );
      await page.keyboard.press("Escape");
      await page.reload();
      await page.getByTestId("detector-canvas").waitFor();
      await ready();
      await page.getByRole("button", { name: "Map", exact: true }).click();
      await detectorSettings().click();
      assert.equal(await gapFilter().isChecked(), true);
      await page.keyboard.press("Escape");
      await page
        .getByRole("button", { name: "Load images…", exact: true })
        .click();
      await page.getByTestId("scan-map-progress").waitFor();
      await page.waitForFunction(() =>
        document
          .querySelector(".workflow-status")
          ?.textContent.includes("images/s"),
      );
      assert.match(
        await page.getByRole("status").first().innerText(),
        /Preview of layer Signal/,
      );
      await page.screenshot({
        path: path.join(artifacts, `${name}-loading.png`),
      });
      await ready();
      await page.getByTestId("scan-map").waitFor();
      const after = await call("state");
      for (const key of ["rois", "expressions", "active", "values"])
        assert.deepEqual(after.map[key], before.map[key]);
      assert.ok(observed.some((p) => p.completed > 0 && p.completed < p.total));
      const snapshot = observed.find(
        (p) => p.completed > 0 && p.completed < p.total,
      );
      const raw = native.buffers.get(snapshot.raster.bufferId);
      const pixels = new Float32Array(
        raw.buffer,
        raw.byteOffset,
        raw.length / 4,
      );
      assert.equal(
        [...pixels].filter(Number.isFinite).length,
        snapshot.completed,
      );
      const finalRaw = native.buffers.get(after.map.raster.bufferId);
      const finalPixels = new Float32Array(
        finalRaw.buffer,
        finalRaw.byteOffset,
        finalRaw.length / 4,
      );
      for (let i = 0; i < pixels.length; i++)
        if (Number.isFinite(pixels[i])) assert.equal(pixels[i], finalPixels[i]);
      const popup = page.waitForEvent("popup");
      await page
        .getByRole("button", { name: "Detach map", exact: true })
        .click();
      const detached = await popup;
      detached.on("pageerror", (e) => errors.push(e.message));
      await detached.getByTestId("scan-map").waitFor();
      await page.getByRole("button", { name: "Map", exact: true }).click();
      await page
        .getByRole("button", { name: "Load images…", exact: true })
        .click();
      await detached.getByTestId("scan-map-progress").waitFor();
      await detached.waitForFunction(() =>
        document
          .querySelector(".detached-map-footer")
          ?.textContent.includes("images/s"),
      );
      await detached.screenshot({
        path: path.join(artifacts, `${name}-detached-loading.png`),
      });
      await ready();
      await detached.getByTestId("scan-map").waitFor();
      assert.deepEqual(errors, []);
      receipts.push({
        browser: name,
        partialMapWhileBusy: true,
        blankUnfinishedCells: true,
        previewEqualsFinishedCells: true,
        regionsAndExpressionPreserved: true,
        detachedPreview: true,
        liveRateDisplayed: rates.length > 0,
        completed: frameCount,
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
  path.join(artifacts, "receipt.json"),
  JSON.stringify(receipts, null, 2) + "\n",
);
console.log(JSON.stringify(receipts, null, 2));
