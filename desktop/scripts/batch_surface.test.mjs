import test from "node:test";
import assert from "node:assert/strict";
import {
  surfaceSampling,
  surfaceIntensity,
  surfaceCamera,
  surfaceProject,
  surfaceBarycentric,
  SURFACE_VERTEX_LIMIT,
  SURFACE_COLUMN_LIMIT,
} from "../src/batchSurfaceGeometry.ts";

test("Qt inclusive frame range and stride retain source indices", () => {
  const sample = surfaceSampling(
    20,
    5,
    { xMin: 1, xMax: 4, yMin: 3, yMax: 15 },
    4,
  );
  assert.deepEqual(sample.frames, [3, 7, 11]);
  assert.deepEqual(sample.columns, [1, 2, 3]);
  assert.equal(sample.lastRow, 14);
});
test("large surfaces stay bounded, including a one-frame long radial axis", () => {
  for (const rows of [1, 2, 7, 999, 1_000_000])
    for (const cols of [1, 2, 300, 30_000, 1_000_000]) {
      const s = surfaceSampling(rows, cols, null, 1);
      assert.ok(s.frames.length * s.columns.length <= SURFACE_VERTEX_LIMIT);
      assert.ok(s.columns.length <= SURFACE_COLUMN_LIMIT);
      assert.equal(s.columns[0], 0);
      assert.equal(s.columns.at(-1), cols - 1);
      assert.ok(
        s.frameStep >= Math.max(1, Math.floor((rows * cols) / 500_000)),
      );
      assert.ok(s.frames.every((v, i) => v === i * s.frameStep && v < rows));
    }
});
test("display transfer agrees with 2D, including clipping and negative sqrt", () => {
  assert.equal(surfaceIntensity(15, [10, 20], "linear"), 0.5);
  assert.equal(surfaceIntensity(5, [1, 9], "log"), Math.log(5) / Math.log(9));
  assert.equal(surfaceIntensity(4, [0, 16], "sqrt"), 0.5);
  assert.equal(surfaceIntensity(-2, [-5, 16], "sqrt"), 0);
  assert.equal(surfaceIntensity(-5, [-10, 0], "linear"), 0.5);
  assert.equal(surfaceIntensity(500, [1, 10], "log"), 1);
  assert.ok(Number.isNaN(surfaceIntensity(NaN, [0, 1], "linear")));
  assert.ok(Number.isFinite(surfaceIntensity(5, [5, 5], "linear")));
});
test("surface display functions do not change source samples", () => {
  const data = new Float32Array([-10, 0, 5, 20, NaN]);
  const before = new Uint8Array(data.buffer.slice(0));
  for (const scale of ["linear", "log", "sqrt"])
    for (const value of data) surfaceIntensity(value, [-5, 10], scale);
  surfaceSampling(1, data.length, null, 5);
  assert.deepEqual(new Uint8Array(data.buffer), before);
});
test("Qt orientation conventions expose radial in front, frame at right and no height in top", () => {
  const project = (f, r, z, v) =>
    surfaceProject(f, r, z, surfaceCamera(v), 800, 600);
  assert.equal(project(0, 0, 0, "Front").x, project(1, 0, 0, "Front").x);
  assert.ok(project(0, 1, 0, "Front").x > project(0, 0, 0, "Front").x);
  assert.ok(project(1, 0, 0, "Right").x < project(0, 0, 0, "Right").x);
  assert.ok(
    Math.abs(project(0, 0, 0, "Top").y - project(0, 0, 1, "Top").y) < 1e-10,
  );
  assert.ok(project(0, 0, 1, "Isometric").y < project(0, 0, 0, "Isometric").y);
});
test("projected triangle picking rejects outside and collapsed faces", () => {
  const a = { x: 0, y: 0 },
    b = { x: 10, y: 0 },
    c = { x: 0, y: 10 };
  assert.deepEqual(surfaceBarycentric(2, 3, a, b, c), [0.5, 0.2, 0.3]);
  assert.equal(surfaceBarycentric(8, 8, a, b, c), null);
  assert.equal(surfaceBarycentric(2, 3, a, a, a), null);
});
