import test from "node:test";
import assert from "node:assert/strict";
import {
  surfaceAxisTicks,
  surfaceAxisProjection,
  layoutSurfaceAxes,
  surfaceLabelsOverlap,
  surfaceProjectionMatrix,
} from "../src/batchSurfaceAxes.ts";
import {
  surfaceCamera,
  surfaceIntensity,
} from "../src/batchSurfaceGeometry.ts";

test("resident GPU camera matrix agrees with physical axes across rotation, stretch, zoom and pan", () => {
  for (const azimuth of [-140, 0, 45, 90, 210])
    for (const elevation of [-60, 0, 30, 90])
      for (const zoom of [0.4, 1, 3]) {
        const width = 970,
          height = 650;
        const project = surfaceAxisProjection(
          { ...surfaceCamera(), azimuth, elevation, zoom, panX: 17, panY: -11 },
          [1.4, 0.8, 1.2],
          width,
          height,
          13,
        );
        const matrix = surfaceProjectionMatrix(project, width, height);
        for (const [f, r, z] of [
          [0, 0, 0],
          [1, 1, 1],
          [0.17, 0.81, 0.42],
          [0.5, 0.5, 0.5],
        ]) {
          const p = project(f, r, z);
          const x = matrix[0] * f + matrix[4] * r + matrix[8] * z + matrix[12];
          const y = matrix[1] * f + matrix[5] * r + matrix[9] * z + matrix[13];
          const depth =
            matrix[2] * f + matrix[6] * r + matrix[10] * z + matrix[14];
          assert.ok(Math.abs(((x + 1) * width) / 2 - p.x) < 0.001);
          assert.ok(Math.abs(((1 - y) * height) / 2 - p.y) < 0.001);
          assert.ok(
            depth >= -0.981 && depth <= 0.981,
            "Camera depth contains the complete data box",
          );
        }
      }
});

test("surface radial ticks use rounded majors rather than arbitrary endpoints", () => {
  const axis = surfaceAxisTicks(0.03, 30.11, 2);
  assert.deepEqual(
    axis.ticks.map((t) => t.label),
    ["10", "20", "30"],
  );
  assert.equal(axis.annotation, null);
});
test("descending physical axes retain the original tick values and positions", () => {
  const axis = surfaceAxisTicks(25, 1, 4);
  assert.deepEqual(
    axis.ticks.map((t) => t.value),
    [5, 10, 15, 20, 25],
  );
  for (const tick of axis.ticks)
    assert.equal(tick.fraction, (tick.value - 25) / (1 - 25));
});
test("frame ticks include exact one-based range edges and never fractions", () => {
  const axis = surfaceAxisTicks(1, 1200, 2, "linear", true);
  assert.equal(axis.ticks[0].value, 1);
  assert.equal(axis.ticks.at(-1).value, 1200);
  assert.ok(axis.ticks.every((t) => Number.isInteger(t.value)));
  assert.deepEqual(surfaceAxisTicks(3, 3, 2, "linear", true).ticks, [
    { value: 3, label: "3", fraction: 0.5 },
  ]);
});
test("log labels show actual decades and positions follow the display transfer", () => {
  const axis = surfaceAxisTicks(0, 120000, 5, "log");
  assert.equal(axis.annotation, null);
  assert.deepEqual(
    axis.ticks.map((t) => t.label),
    ["0", "10", "100", "10³", "10⁴", "10⁵"],
  );
  for (const tick of axis.ticks)
    assert.equal(
      tick.fraction,
      surfaceIntensity(tick.value, [0, 120000], "log"),
    );
  for (const tick of surfaceAxisTicks(-10, 17000, 4, "sqrt").ticks)
    assert.equal(
      tick.fraction,
      surfaceIntensity(tick.value, [-10, 17000], "sqrt"),
    );
});
test("small values and large offsets have stable shared factors across tick densities", () => {
  for (const count of [2, 3, 4, 6]) {
    assert.equal(surfaceAxisTicks(-0.0007, 0.0019, count).annotation, "×10⁻³");
    const axis = surfaceAxisTicks(1e8, 1e8 + 0.004, count);
    assert.equal(axis.annotation, "×10⁻³  +1e8");
    assert.ok(axis.ticks.every((t) => t.label.length < 6));
  }
});
test("orthogonal views suppress only their geometrically collapsed axis", () => {
  for (const [view, hidden] of [
    ["Front", "frame"],
    ["Right", "radial"],
    ["Top", "intensity"],
  ]) {
    const project = surfaceAxisProjection(
      surfaceCamera(view),
      [1, 1, 1],
      800,
      500,
      14,
    );
    const axes = layoutSurfaceAxes({
      project,
      width: 800,
      height: 500,
      fontSize: 14,
      measure: (s) => s.length * 8,
      frames: [1, 1200],
      radial: [0.03, 30.11],
      radialTitle: "2θ (°)",
      limits: [0, 16259.55],
      scale: "linear",
    });
    assert.equal(axes.axes.length, 2);
    assert.ok(axes.axes.every((a) => a.kind !== hidden));
    assert.ok(
      axes.labels.some((l) => l.role === "legend" && l.text.includes("×10⁴")),
    );
  }
});
test("constant intensity ticks remain on the same plane as the surface", () => {
  const project = surfaceAxisProjection(
    surfaceCamera(),
    [1, 1, 1],
    800,
    500,
    14,
  );
  const layout = layoutSurfaceAxes({
    project,
    width: 800,
    height: 500,
    fontSize: 14,
    measure: (s) => s.length * 8,
    frames: [1, 4],
    radial: [1, 20],
    radialTitle: "d (Å)",
    limits: [5, 5],
    scale: "linear",
  });
  assert.equal(
    layout.axes.find((a) => a.kind === "intensity").ticks[0].fraction,
    0,
  );
});
test("slanted titles do not falsely hide neighboring parallel text", () => {
  const a = { x: 0, y: 0, width: 100, height: 10, angle: Math.PI / 4 };
  assert.equal(surfaceLabelsOverlap(a, { ...a, y: 30 }), false);
  assert.equal(surfaceLabelsOverlap(a, { ...a, y: 4 }), true);
});
