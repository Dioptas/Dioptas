import assert from "node:assert/strict";
import path from "node:path";
import { mkdir, writeFile } from "node:fs/promises";
import { createServer } from "vite";
import { chromium, webkit } from "playwright";
import { root } from "./native_backend_client.mjs";
import { surfaceIntensity } from "../src/batchSurfaceGeometry.ts";

const artifacts = path.join(root, "artifacts/batch-surface-axes");
await mkdir(artifacts, { recursive: true });
const server = await createServer({
  root,
  server: { host: "127.0.0.1", port: 0 },
});
await server.listen();
const receipts = [];
const overlaps = (a, b) => {
  const corners = (l) =>
    [-1, 1].flatMap((x) =>
      [-1, 1].map((y) => ({
        x:
          l.x +
          ((x * l.width) / 2) * Math.cos(l.angle) -
          ((y * l.height) / 2) * Math.sin(l.angle),
        y:
          l.y +
          ((x * l.width) / 2) * Math.sin(l.angle) +
          ((y * l.height) / 2) * Math.cos(l.angle),
      })),
    );
  const ac = corners(a),
    bc = corners(b);
  return ![a.angle, a.angle + Math.PI / 2, b.angle, b.angle + Math.PI / 2].some(
    (angle) => {
      const project = (p) => p.x * Math.cos(angle) + p.y * Math.sin(angle);
      const ap = ac.map(project),
        bp = bc.map(project);
      return (
        Math.max(...ap) <= Math.min(...bp) || Math.max(...bp) <= Math.min(...ap)
      );
    },
  );
};
function checkLayout(layout, width, height, minimumTicks = 1) {
  for (const label of layout.labels) {
    const b = label.bounds;
    assert.ok(
      b.left >= 0 && b.right <= width && b.top >= 0 && b.bottom <= height,
      `Clipped ${label.axis} ${label.text}`,
    );
    assert.equal(
      layout.labels.some((other) => other !== label && overlaps(label, other)),
      false,
      `Overlapping ${label.text}`,
    );
    if (label.axis === "legend") continue;
    const axis = layout.axes.find((a) => a.kind === label.axis),
      [nx, ny] = axis.normal;
    const textExtent =
      (Math.abs(nx * Math.cos(label.angle) + ny * Math.sin(label.angle)) *
        label.width) /
        2 +
      (Math.abs(-nx * Math.sin(label.angle) + ny * Math.cos(label.angle)) *
        label.height) /
        2;
    assert.ok(
      layout.box.every(
        (p) => nx * (label.x - p.x) + ny * (label.y - p.y) >= textExtent - 0.01,
      ),
      `Label crosses image: ${label.text}`,
    );
  }
  for (const axis of layout.axes) {
    assert.ok(
      layout.labels.some((l) => l.axis === axis.kind && l.role === "title"),
      `Missing ${axis.kind} title at ${width}×${height}: ${axis.title}`,
    );
    const visible = layout.labels.filter(
      (l) => l.axis === axis.kind && l.role === "tick",
    );
    assert.ok(
      visible.length >= minimumTicks,
      `No readable ${axis.kind} ticks: ${JSON.stringify(layout)}`,
    );
    assert.ok(
      visible.every((t) => t.text.length < 10),
      "Tick values use compact precision and shared factors",
    );
    if (axis.kind === "frame")
      assert.ok(
        axis.ticks.every((t) => Number.isInteger(t.value)),
        "Frame ticks are integers",
      );
  }
}
try {
  for (const [name, engine] of [
    ["chromium", chromium],
    ["webkit", webkit],
  ]) {
    const browser = await engine.launch({ headless: true });
    const errors = [];
    try {
      const page = await browser.newPage({
        viewport: { width: 1000, height: 650 },
      });
      page.on("pageerror", (e) => errors.push(e.message));
      await page.goto(
        server.resolvedUrls.local[0] + "scripts/batch_surface_harness.html",
      );
      const surface = page.getByTestId("batch-surface");
      await surface.waitFor();
      let layouts = 0;
      for (const [unit, scale, limits, x] of [
        [
          "2th_deg",
          "linear",
          [0, 16259.55],
          Array.from({ length: 65 }, (_, i) => 0.03 + i * 0.47),
        ],
        [
          "q_A^-1",
          "log",
          [0, 120000],
          Array.from({ length: 65 }, (_, i) => 0.2 + i * 0.09),
        ],
        [
          "d_A",
          "sqrt",
          [-10, 17000],
          Array.from({ length: 65 }, (_, i) => 25 / (1 + i * 0.15)),
        ],
        [
          "q_A^-1",
          "linear",
          [-0.0007, 0.0019],
          Array.from({ length: 65 }, (_, i) => 1e-5 + i * 2e-6),
        ],
        [
          "2th_deg",
          "linear",
          [1e8, 1e8 + 0.004],
          Array.from({ length: 65 }, (_, i) => 20 + i * 0.00001),
        ],
      ]) {
        await page.evaluate((options) => window.setSurfaceAxisCase(options), {
          unit,
          scale,
          limits,
          x,
          rows: 1200,
        });
        await page.waitForFunction(
          (unit) =>
            document.querySelector('[data-testid="batch-surface"]').dataset
              .unit === unit,
          unit,
        );
        for (const [width, height, large] of [
          [1000, 650, false],
          [600, 360, false],
          [420, 220, false],
          [420, 260, true],
        ]) {
          await page.setViewportSize({ width, height });
          await page
            .locator(".app")
            .evaluate(
              (el, large) => (el.dataset.textSize = large ? "large" : "normal"),
              large,
            );
          for (const orientation of ["Isometric", "Front", "Right", "Top"]) {
            await page
              .getByRole("button", {
                name: `${orientation} surface view`,
                exact: true,
              })
              .click();
            await page.waitForTimeout(25);
            const { layout, size } = await surface.evaluate((c) => ({
              layout: JSON.parse(c.dataset.axisLayout),
              size: { width: c.clientWidth, height: c.clientHeight },
            }));
            assert.equal(
              layout.axes.length,
              orientation === "Isometric" ? 3 : 2,
            );
            checkLayout(layout, size.width, size.height, width > 800 ? 2 : 1);
            for (const axis of layout.axes) {
              if (axis.kind !== "intensity") continue;
              for (const tick of axis.ticks)
                assert.ok(
                  Math.abs(
                    tick.fraction - surfaceIntensity(tick.value, limits, scale),
                  ) < 1e-9,
                );
            }
            layouts++;
            if (
              (unit === "2th_deg" && scale === "linear" && limits[0] === 0) ||
              (width === 600 && orientation === "Isometric")
            )
              await page.screenshot({
                path: path.join(
                  artifacts,
                  `${name}-${unit}-${scale}-${limits[0]}-${width}-${height}-${orientation}.png`,
                ),
              });
          }
        }
      }
      // Rotate freely into the opposite quadrant: labels stay outside the
      // surface and remain separate as the visible silhouette changes.
      await page
        .getByRole("button", { name: "Isometric surface view", exact: true })
        .click();
      const box = await surface.boundingBox();
      await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
      await page.mouse.down();
      await page.mouse.move(
        box.x + box.width / 2 - 220,
        box.y + box.height / 2 + 30,
        { steps: 8 },
      );
      await page.mouse.up();
      const rotated = await surface.evaluate((c) =>
        JSON.parse(c.dataset.axisLayout),
      );
      checkLayout(rotated, box.width, box.height);
      assert.deepEqual(errors, []);
      receipts.push({
        browser: name,
        layouts,
        roundedTicks: true,
        outsideImage: true,
        nonoverlapping: true,
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
