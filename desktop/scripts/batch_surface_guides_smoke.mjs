import assert from "node:assert/strict";
import path from "node:path";
import { mkdir, writeFile } from "node:fs/promises";
import { createServer } from "vite";
import { chromium, webkit } from "playwright";
import { root } from "./native_backend_client.mjs";
const artifacts = path.join(root, "desktop/artifacts/batch-surface-guides");
await mkdir(artifacts, { recursive: true });
const server = await createServer({
  root: path.join(root, "desktop"),
  server: { host: "127.0.0.1", port: 0 },
});
await server.listen();
const url = server.resolvedUrls.local[0] + "scripts/batch_surface_harness.html";
const refs = [2.2, 4.4].map((q, i) => ({
  x: (2 * Math.PI) / q,
  intensity: i === 0 ? 100 : 25,
  name: "Reference phase",
  color: "#ff66dd",
  phaseIndex: 0,
  hkl: [i + 1, 0, 0],
}));
const ready = (page) =>
  page.waitForFunction(
    () =>
      document.querySelector('[data-testid="batch-surface"]')?.dataset
        .renderState === "ready",
  );
const state = (surface) => surface.evaluate((c) => ({ ...c.dataset }));
const image = (surface) => surface.evaluate((c) => c.toDataURL());
const hash = (page) =>
  page.evaluate(async () =>
    Array.from(
      new Uint8Array(
        await crypto.subtle.digest("SHA-256", window.surfaceBuffer),
      ),
    ).join(","),
  );
const phasePixels = (surface) =>
  surface.evaluate((c) => {
    const data = c.getContext("2d").getImageData(0, 0, c.width, c.height).data;
    let count = 0;
    for (let i = 0; i < data.length; i += 4)
      if (data[i] > 180 && data[i + 1] < 150 && data[i + 2] > 150) count++;
    return count;
  });
const receipts = [];
try {
  for (const [name, engine] of [
    ["chromium", chromium],
    ["webkit", webkit],
  ]) {
    const browser = await engine.launch({ headless: true });
    try {
      const page = await browser.newPage({
        viewport: { width: 1000, height: 680 },
        deviceScaleFactor: 2,
      });
      const errors = [];
      page.on("pageerror", (error) => errors.push(error.message));
      await page.goto(url);
      await ready(page);
      await page.evaluate(() => window.setSurfaceGuideFixture());
      await ready(page);
      const surface = page.getByTestId("batch-surface");
      const source = await hash(page),
        contours = await image(surface);
      assert.ok(JSON.parse((await state(surface)).contourLevels).length > 3);
      await page
        .getByRole("button", {
          name: "Surface ranges and proportions",
          exact: true,
        })
        .click();
      const appearance = page.getByRole("combobox", {
        name: "Surface appearance",
        exact: true,
      });
      await appearance.selectOption("plain");
      assert.deepEqual(JSON.parse((await state(surface)).contourLevels), []);
      assert.notEqual(
        await image(surface),
        contours,
        "Contours change rendered pixels",
      );
      await appearance.selectOption("contours");
      await page
        .getByRole("button", { name: "Close surface settings", exact: true })
        .click();
      await page.evaluate((refs) => window.setSurfacePhases(refs), refs);
      await page.waitForFunction(
        () =>
          document.querySelector('[data-testid="batch-surface"]').dataset
            .phaseReferences === "2",
      );
      const lines = await image(surface),
        linePixels = await phasePixels(surface);
      assert.ok(linePixels > 100, "Phase-colored curves are visible");
      assert.notEqual(lines, contours);
      await page.screenshot({
        path: path.join(artifacts, name + "-contours-lines.png"),
      });
      await page
        .getByRole("button", {
          name: "Surface ranges and proportions",
          exact: true,
        })
        .click();
      await page
        .getByRole("combobox", { name: "Surface phase guides", exact: true })
        .selectOption("planes");
      assert.equal((await state(surface)).phaseStyle, "planes");
      const heights = JSON.parse((await state(surface)).phasePlaneHeights);
      assert.equal(heights.length, 2);
      assert.ok(
        heights[0] > 0 && heights[0] < 1,
        "Strong plane is bounded by the measured pattern maximum",
      );
      assert.ok(
        Math.abs(heights[1] / heights[0] - 0.25) < 1e-8,
        "Weak plane uses its relative reflection intensity",
      );
      await page
        .getByRole("button", { name: "Close surface settings", exact: true })
        .click();
      const planes = await image(surface);
      assert.notEqual(planes, lines, "Reference planes change rendered pixels");
      await page.screenshot({
        path: path.join(artifacts, name + "-contours-planes.png"),
      });
      const guideMeshUploads = (await state(surface)).meshUploads;
      for (const orientation of ["Front", "Right", "Top", "Isometric"]) {
        await page
          .getByRole("button", {
            name: orientation + " surface view",
            exact: true,
          })
          .click();
        assert.equal((await state(surface)).phaseReferences, "2");
        assert.equal((await state(surface)).renderer, "webgl2");
        assert.equal(
          (await state(surface)).meshUploads,
          guideMeshUploads,
          "Phase-plane navigation retains the resident surface mesh",
        );
        assert.equal((await state(surface)).geometryReused, "true");
      }
      await page.evaluate(() => window.setSurfacePhases(undefined));
      await page.waitForFunction(
        () =>
          document.querySelector('[data-testid="batch-surface"]').dataset
            .phaseReferences === "0",
      );
      assert.equal(
        await phasePixels(surface),
        0,
        "Hiding phases removes their marks",
      );
      for (const scale of ["log", "sqrt", "linear"]) {
        await page.evaluate((scale) => window.setSurfaceScale(scale), scale);
        await page.waitForFunction(
          (scale) =>
            document.querySelector('[data-testid="batch-surface"]').dataset
              .intensityScale === scale,
          scale,
        );
        assert.ok(JSON.parse((await state(surface)).contourLevels).length > 0);
      }
      assert.equal(
        await hash(page),
        source,
        "Guides never change scientific samples",
      );
      await page.reload();
      await ready(page);
      await page
        .getByRole("button", {
          name: "Surface ranges and proportions",
          exact: true,
        })
        .click();
      assert.equal(
        await page
          .getByRole("combobox", { name: "Surface appearance", exact: true })
          .inputValue(),
        "contours",
      );
      assert.equal(
        await page
          .getByRole("combobox", { name: "Surface phase guides", exact: true })
          .inputValue(),
        "planes",
      );
      await page
        .getByRole("button", { name: "Close surface settings", exact: true })
        .click();
      // Test the actual GPU depth buffer with a controlled triangle and guide.
      const depth = await page.evaluate(async () => {
        const { drawSurfaceGPU, disposeSurfaceGPU } =
          await import("/src/WebGLSurface.ts");
        const target = document.createElement("canvas");
        target.width = target.height = 100;
        const vertices = [
          [5, 5],
          [95, 5],
          [50, 95],
        ].map(([x, y], meshIndex) => ({
          x,
          y,
          depth: 0,
          z: 0.5,
          meshIndex,
          frame: 0,
          radial: 0,
          intensity: 50,
        }));
        function sample(depth, planes = false, pixel = [50, 45]) {
          const a = { x: 10, y: 10, depth },
            b = { x: 90, y: 10, depth },
            c = { x: 10, y: 90, depth },
            d = { x: 90, y: 90, depth };
          const result = drawSurfaceGPU(
            target,
            vertices,
            [vertices],
            100,
            100,
            "grey",
            {
              contours: [],
              segments: planes
                ? []
                : [
                    {
                      points: [
                        { x: 30, y: 45, depth },
                        { x: 70, y: 45, depth },
                      ],
                      color: "#ff00ff",
                      width: 4,
                    },
                  ],
              planes: planes
                ? [{ points: [a, b, c, d], color: "#ff00ff", opacity: 0.3 }]
                : [],
            },
          );
          const ctx = target.getContext("2d");
          ctx.clearRect(0, 0, 100, 100);
          ctx.drawImage(result, 0, 0);
          return [...ctx.getImageData(...pixel, 1, 1).data];
        }
        const result = {
          behind: sample(-1),
          front: sample(1),
          planeBehind: sample(-1, true),
          planeFront: sample(1, true),
          planeOutside: sample(1, true, [12, 85]),
        };
        disposeSurfaceGPU(target);
        return result;
      });
      assert.ok(
        Math.abs(depth.behind[0] - depth.behind[1]) < 3,
        "A guide behind the opaque mesh is hidden",
      );
      assert.ok(
        depth.front[0] > 220 && depth.front[1] < 20 && depth.front[2] > 220,
        "A nearer guide remains visible",
      );
      assert.ok(
        Math.abs(depth.planeBehind[0] - depth.planeBehind[1]) < 3,
        "A plane behind the opaque mesh is hidden",
      );
      assert.ok(
        depth.planeFront[0] > depth.planeFront[1] + 30,
        "A nearer plane blends transparently",
      );
      assert.equal(
        depth.planeFront[3],
        255,
        "A translucent plane preserves opaque surface alpha",
      );
      assert.ok(
        depth.planeOutside[0] > 250 &&
          depth.planeOutside[1] < 5 &&
          depth.planeOutside[2] > 250 &&
          Math.abs(depth.planeOutside[3] - 77) < 2,
        "A plane outside the mesh keeps its intended hue and opacity",
      );
      const fallback = await browser.newPage({
        viewport: { width: 420, height: 500 },
      });
      await fallback.addInitScript(() => {
        const original = HTMLCanvasElement.prototype.getContext;
        HTMLCanvasElement.prototype.getContext = function (type, ...args) {
          return type === "webgl2" ? null : original.call(this, type, ...args);
        };
      });
      await fallback.goto(url);
      await ready(fallback);
      await fallback.evaluate((refs) => {
        window.setSurfaceGuideFixture();
        window.setSurfacePhases(refs);
      }, refs);
      await ready(fallback);
      const fallbackSurface = fallback.getByTestId("batch-surface");
      assert.equal((await state(fallbackSurface)).renderer, "canvas");
      assert.ok((await phasePixels(fallbackSurface)) > 20);
      assert.ok(
        JSON.parse((await state(fallbackSurface)).contourLevels).length > 0,
      );
      await fallback.screenshot({
        path: path.join(artifacts, name + "-fallback.png"),
      });
      await fallback
        .getByRole("button", {
          name: "Surface ranges and proportions",
          exact: true,
        })
        .click();
      await fallback
        .getByRole("combobox", { name: "Surface phase guides", exact: true })
        .selectOption("planes");
      assert.equal((await state(fallbackSurface)).phaseStyle, "lines");
      await fallback
        .getByText(
          "Reference planes require GPU drawing; showing surface lines.",
          { exact: true },
        )
        .waitFor();
      await fallback
        .getByRole("button", { name: "Close surface settings", exact: true })
        .click();
      await fallback.evaluate(() => {
        window.setSurfaceFixture(1, 201);
        window.setSurfacePhases([
          {
            x: 10,
            intensity: 100,
            name: "Single-frame reference",
            color: "#ff66dd",
            phaseIndex: 0,
            hkl: [1, 0, 0],
          },
        ]);
      });
      await fallback.waitForFunction(
        () =>
          document.querySelector('[data-testid="batch-surface"]').dataset
            .triangles === "0",
      );
      assert.ok(
        (await phasePixels(fallbackSurface)) > 5,
        "A single-frame batch marks phase intersections",
      );
      assert.deepEqual(errors, []);
      receipts.push({
        browser: name,
        linePixels,
        depth,
        sourceUnchanged: true,
        errors,
      });
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
