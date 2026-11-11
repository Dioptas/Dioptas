import assert from "node:assert/strict";
import path from "node:path";
import { mkdir, writeFile } from "node:fs/promises";
import { createServer } from "vite";
import { chromium, webkit } from "playwright";
import { root } from "./native_backend_client.mjs";
const artifacts = path.join(root, "desktop/artifacts/batch-surface-gpu");
await mkdir(artifacts, { recursive: true });
const server = await createServer({
  root: path.join(root, "desktop"),
  server: { host: "127.0.0.1", port: 0 },
});
await server.listen();
const receipts = [];
const ready = (page) =>
  page.waitForFunction(
    () =>
      document.querySelector('[data-testid="batch-surface"]')?.dataset
        .renderState === "ready",
  );
const details = (surface) => surface.evaluate((c) => ({ ...c.dataset }));
const checksum = (page) =>
  page.evaluate(async () =>
    Array.from(
      new Uint8Array(
        await crypto.subtle.digest("SHA-256", window.surfaceBuffer),
      ),
    ).join(","),
  );
try {
  for (const [name, engine] of [
    ["chromium", chromium],
    ["webkit", webkit],
  ]) {
    const browser = await engine.launch({ headless: true });
    const errors = [];
    try {
      const context = await browser.newContext({
        viewport: { width: 1100, height: 750 },
      });
      await context.addInitScript(() => {
        const original = HTMLCanvasElement.prototype.getContext;
        HTMLCanvasElement.prototype.getContext = function (type, ...args) {
          const result = original.call(this, type, ...args);
          if (type === "webgl2" && result) window.surfaceTestGL = result;
          return result;
        };
      });
      const page = await context.newPage();
      page.on("pageerror", (e) => errors.push(e.message));
      await page.goto(
        server.resolvedUrls.local[0] + "scripts/batch_surface_harness.html",
      );
      await ready(page);
      const surface = page.getByTestId("batch-surface");
      const initial = await details(surface);
      const gpuAvailable = await page.evaluate(() => !!window.surfaceTestGL);
      assert.equal(
        initial.renderer,
        gpuAvailable ? "webgl2" : "canvas",
        "Available GPU must draw the surface",
      );
      assert.equal(initial.resolution, "high");
      await page
        .getByRole("button", {
          name: "Surface ranges and proportions",
          exact: true,
        })
        .click();
      const select = page.getByRole("combobox", {
        name: "Surface resolution",
        exact: true,
      });
      await select.selectOption("fast");
      await page.evaluate(() => window.setSurfacePeakFixture());
      // React may still expose the preceding ready canvas after setState.
      // Hash only after the large fixture and its fast mesh have committed.
      await page.waitForFunction(
        () =>
          window.surfaceBuffer.byteLength ===
            64 * 2048 * Float32Array.BYTES_PER_ELEMENT &&
          Number(
            document.querySelector('[data-testid="batch-surface"]').dataset
              .columnStep,
          ) > 1,
      );
      await ready(page);
      const sourceHash = await checksum(page);
      const fast = await details(surface);
      assert.ok(Number(fast.vertices) <= 8192);
      assert.ok(Number(fast.columnStep) > 1);
      await page
        .getByRole("button", { name: "Close surface settings", exact: true })
        .click();
      await page.screenshot({ path: path.join(artifacts, `${name}-fast.png`) });
      await page
        .getByRole("button", {
          name: "Surface ranges and proportions",
          exact: true,
        })
        .click();
      await select.selectOption("high");
      await page.waitForFunction(
        () =>
          document.querySelector('[data-testid="batch-surface"]').dataset
            .columnStep === "1",
      );
      const high = await details(surface);
      assert.equal(Number(high.vertices), 65536);
      assert.ok(
        Number(high.sampledMaximum) > 100 * Number(fast.sampledMaximum),
        "High detail retains the narrow source peak missed by old sampling",
      );
      await select.selectOption("fine");
      await page.waitForFunction(
        () =>
          document.querySelector('[data-testid="batch-surface"]').dataset
            .vertices === "131072",
      );
      const fine = await details(surface);
      assert.equal(fine.frameStep, "1");
      assert.equal(fine.columnStep, "1");
      await page
        .getByRole("button", { name: "Close surface settings", exact: true })
        .click();
      await page.screenshot({ path: path.join(artifacts, `${name}-fine.png`) });
      const png = await page.evaluate(() => window.captureSurface());
      assert.ok(png.startsWith("iVBOR"));
      await writeFile(
        path.join(artifacts, `${name}-snapshot.png`),
        Buffer.from(png, "base64"),
      );
      const box = await surface.boundingBox();
      const anchor = JSON.parse((await details(surface)).hitSample);
      await page.mouse.move(box.x + anchor.x, box.y + anchor.y);
      // Observe every mesh transition, including any brief reduced-detail draw
      // that might already have finished by the time Playwright reads the canvas.
      await surface.evaluate((canvas) => {
        window.zoomMeshSnapshots = [];
        window.zoomMeshObserver = new MutationObserver(() =>
          window.zoomMeshSnapshots.push({ ...canvas.dataset }),
        );
        window.zoomMeshObserver.observe(canvas, {
          attributes: true,
          attributeFilter: [
            "data-vertices",
            "data-frame-step",
            "data-column-step",
          ],
        });
      });
      const beforeZoom = +(await details(surface)).zoom;
      await page.mouse.wheel(0, -180);
      await page.waitForFunction(
        (before) =>
          +document.querySelector('[data-testid="batch-surface"]').dataset
            .zoom > before,
        beforeZoom,
      );
      const zooming = await details(surface);
      assert.equal(
        zooming.vertices,
        fine.vertices,
        "Zoom keeps the selected mesh resolution",
      );
      assert.equal(
        zooming.meshUploads,
        fine.meshUploads,
        "Zoom updates the camera without uploading mesh buffers",
      );
      assert.equal(zooming.geometryReused, "true");
      const anchoredSample = JSON.parse(zooming.hitSample);
      // Native wheel events round mouse coordinates; allow subpixel motion of
      // the nearby sampled point. The camera arithmetic is checked exactly.
      assert.ok(
        Math.hypot(anchoredSample.x - anchor.x, anchoredSample.y - anchor.y) <
          0.5,
        `Off-center zoom anchor: ${JSON.stringify({ anchor, anchoredSample })}`,
      );
      const zoomImage = await surface.evaluate((canvas) => canvas.toDataURL());
      await page.waitForTimeout(250);
      assert.equal(
        await surface.evaluate((canvas) => canvas.toDataURL()),
        zoomImage,
        "Finishing zoom does not replace the rendered surface",
      );
      const zoomMeshes = await page.evaluate(() => {
        window.zoomMeshObserver.disconnect();
        return window.zoomMeshSnapshots;
      });
      for (const sample of zoomMeshes) {
        assert.equal(sample.vertices, fine.vertices);
        assert.equal(sample.frameStep, fine.frameStep);
        assert.equal(sample.columnStep, fine.columnStep);
      }
      await page.mouse.wheel(0, 120);
      await page.waitForFunction(
        (previous) =>
          document.querySelector('[data-testid="batch-surface"]').dataset
            .zoom !== previous,
        zooming.zoom,
      );
      const zoomedOut = JSON.parse((await details(surface)).hitSample);
      assert.ok(
        Math.hypot(zoomedOut.x - anchor.x, zoomedOut.y - anchor.y) < 0.5,
        "The same anchor stays fixed while zooming out",
      );
      const beforeRight = await details(surface),
        sampleBeforeRight = JSON.parse(beforeRight.hitSample);
      const clientX = Math.round(box.x + anchor.x),
        clientY = Math.round(box.y + anchor.y);
      const pointer = { x: clientX - box.x, y: clientY - box.y };
      await page.mouse.click(clientX, clientY, { button: "right" });
      const afterRight = await details(surface),
        sampleAfterRight = JSON.parse(afterRight.hitSample);
      assert.equal(+afterRight.zoom, +beforeRight.zoom / 2);
      const factor = +afterRight.zoom / +beforeRight.zoom;
      assert.ok(
        Math.hypot(
          sampleAfterRight.x -
            (pointer.x + (sampleBeforeRight.x - pointer.x) * factor),
          sampleAfterRight.y -
            (pointer.y + (sampleBeforeRight.y - pointer.y) * factor),
        ) < 1e-6,
        "Right-click zoom-out uses the same cursor anchor",
      );
      assert.equal(afterRight.meshUploads, fine.meshUploads);
      await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
      await page.mouse.down();
      await page.mouse.move(
        box.x + box.width / 2 + 45,
        box.y + box.height / 2 + 15,
        { steps: 4 },
      );
      const moving = await details(surface);
      assert.equal(
        moving.vertices,
        fine.vertices,
        "Rotation retains the selected resolution",
      );
      assert.equal(moving.geometryReused, "true");
      assert.equal(
        moving.meshUploads,
        fine.meshUploads,
        "Rotation updates only the camera projection",
      );
      await page.mouse.up();
      await page.waitForFunction(
        () =>
          document.querySelector('[data-testid="batch-surface"]').dataset
            .detail === "settled",
      );
      assert.equal(
        (await details(surface)).vertices,
        fine.vertices,
        "Requested detail stays constant after rotation",
      );
      assert.equal(
        await checksum(page),
        sourceHash,
        "Mesh quality never changes source pixels",
      );
      const uploads = +(await details(surface)).meshUploads;
      await page.mouse.down({ button: "right" });
      await page.mouse.move(
        box.x + box.width / 2 + 65,
        box.y + box.height / 2 + 35,
        { steps: 3 },
      );
      await page.mouse.up({ button: "right" });
      assert.equal(
        +(await details(surface)).meshUploads,
        uploads,
        "Panning reuses the mesh too",
      );
      const beforeLevels = await surface.evaluate((canvas) =>
        canvas.toDataURL(),
      );
      await page.evaluate(() => window.setSurfaceLimits([0, 75]));
      await page.waitForFunction(
        (n) =>
          +document.querySelector('[data-testid="batch-surface"]').dataset
            .meshUploads > n,
        uploads,
      );
      assert.notEqual(
        await surface.evaluate((canvas) => canvas.toDataURL()),
        beforeLevels,
        "Histogram limits rebuild the displayed heights",
      );
      await page.evaluate(() => window.setSurfaceLimits([0, 150]));
      await page.evaluate(() => window.setSurfaceScale("sqrt"));
      await page.waitForFunction(
        () =>
          document.querySelector('[data-testid="batch-surface"]').dataset
            .intensityScale === "sqrt",
      );
      assert.ok(+(await details(surface)).meshUploads > uploads);
      await page.evaluate(() => window.setSurfaceScale("linear"));
      const paletteUploads = +(await details(surface)).meshUploads;
      await page.evaluate(() => window.setSurfacePalette("grey"));
      await page.waitForFunction(
        () =>
          document.querySelector('[data-testid="batch-surface"]').dataset
            .palette === "grey",
      );
      assert.equal(
        +(await details(surface)).meshUploads,
        paletteUploads,
        "Changing colors retains the mesh heights",
      );
      await page.evaluate(() => window.setSurfacePalette("viridis"));
      // Picking follows GPU depth rather than the mesh's array order.
      const pick = await page.evaluate(async () => {
        const { hitBatchSurface } =
          await import("/src/batchSurfaceRenderer.ts");
        const triangle = (depth, frame) => [
          { x: 0, y: 0, depth, frame, radial: 1, z: 0.5 },
          { x: 20, y: 0, depth, frame, radial: 2, z: 0.5 },
          { x: 0, y: 20, depth, frame, radial: 3, z: 0.5 },
        ];
        return hitBatchSurface(
          {
            triangles: [triangle(5, 7), triangle(-5, 2)],
            vertices: [],
            depthSorted: false,
          },
          4,
          4,
        );
      });
      assert.equal(pick.frame, 7);
      // Tab/window remounts must release the old GPU slot as well as buffers.
      await page.evaluate(() => {
        window.previousSurfaceGL = window.surfaceTestGL;
        window.setSurfaceVisible(false);
      });
      await surface.waitFor({ state: "detached" });
      if (gpuAvailable)
        await page.waitForFunction(() =>
          window.previousSurfaceGL.isContextLost(),
        );
      await page.evaluate(() => window.setSurfaceVisible(true));
      await ready(page);
      assert.equal((await details(surface)).resolution, "fine");
      if (gpuAvailable)
        assert.equal(
          await page.evaluate(
            () => window.previousSurfaceGL === window.surfaceTestGL,
          ),
          false,
        );
      // Reopening also keeps the quality preference.
      await page.reload();
      await ready(page);
      assert.equal((await details(surface)).resolution, "fine");
      if (gpuAvailable) {
        assert.equal((await details(surface)).renderer, "webgl2");
        const lost = await page.evaluate(() => {
          const ext = window.surfaceTestGL?.getExtension("WEBGL_lose_context");
          ext?.loseContext();
          return !!ext;
        });
        if (lost) {
          await page.waitForTimeout(80);
          await page.evaluate(() => window.setSurfacePalette("grey"));
          await page.waitForFunction(
            () =>
              document.querySelector('[data-testid="batch-surface"]').dataset
                .renderer === "canvas",
          );
          assert.ok(await page.evaluate(() => window.captureSurface()));
        }
      }
      const fallback = await context.newPage();
      await fallback.addInitScript(() => {
        const original = HTMLCanvasElement.prototype.getContext;
        HTMLCanvasElement.prototype.getContext = function (type, ...args) {
          return type === "webgl2" ? null : original.call(this, type, ...args);
        };
      });
      await fallback.goto(
        server.resolvedUrls.local[0] + "scripts/batch_surface_harness.html",
      );
      await ready(fallback);
      assert.equal(
        (await details(fallback.getByTestId("batch-surface"))).renderer,
        "canvas",
      );
      assert.ok(await fallback.evaluate(() => window.captureSurface()));
      assert.deepEqual(errors, []);
      receipts.push({
        browser: name,
        gpuAvailable,
        renderer: initial.renderer,
        fastVertices: +fast.vertices,
        highVertices: +high.vertices,
        fineVertices: +fine.vertices,
        radialSamples: { fast: Math.ceil(2048 / +fast.columnStep), high: 2048 },
        fastPeak: +fast.sampledMaximum,
        highPeak: +high.sampledMaximum,
        renderMs: {
          fast: +fast.renderMs,
          high: +high.renderMs,
          fine: +fine.renderMs,
          moving: +moving.renderMs,
        },
        sourceUnchanged: true,
        errors,
      });
      await context.close();
    } finally {
      await browser.close();
    }
  }
  await writeFile(
    path.join(artifacts, "receipt.json"),
    JSON.stringify(receipts, null, 2),
  );
  console.log(JSON.stringify(receipts));
} finally {
  await server.close();
}
