import test from "node:test";
import assert from "node:assert/strict";
import {
  surfaceSampling,
  surfaceIntensity,
  surfaceCamera,
  surfaceProject,
  surfaceBarycentric,
  surfaceResolutions,
} from "../src/batchSurfaceGeometry.ts";
import {
  sliceSurfaceTriangle,
  surfaceContourLevels,
  surfacePhaseReferences,
  surfacePhaseFrameHeights,
} from "../src/batchSurfaceGuides.ts";
import { scalePhaseReflections } from "../src/phaseLineScaling.ts";

test("phase plane heights share pattern reflection strengths and each frame's visible native maximum", () => {
  const lines = [
    {
      x: 1,
      intensity: 100,
      phaseIndex: 0,
      name: "Phase",
      color: "#fff",
      hkl: [],
    },
    {
      x: 2,
      intensity: 25,
      phaseIndex: 0,
      name: "Phase",
      color: "#fff",
      hkl: [],
    },
    {
      x: 3,
      intensity: 2,
      phaseIndex: 1,
      name: "Phase",
      color: "#fff",
      hkl: [],
    },
    {
      x: 4,
      intensity: 1,
      phaseIndex: 1,
      name: "Phase",
      color: "#fff",
      hkl: [],
    },
    {
      x: 5,
      intensity: NaN,
      phaseIndex: 1,
      name: "Phase",
      color: "#fff",
      hkl: [],
    },
  ];
  assert.deepEqual(scalePhaseReflections(lines, 1), [1, 0.25, 1, 0.5, 0]);
  const values = new Float32Array([
    999,
    10,
    80,
    5,
    30,
    999,
    999,
    2,
    20,
    4,
    10,
    999,
    NaN,
    NaN,
    NaN,
    NaN,
    NaN,
    NaN,
  ]);
  const before = new Uint8Array(values.buffer.slice(0));
  const sampling = { frames: [0, 1, 2], firstColumn: 1, lastColumn: 4 };
  for (const scale of ["linear", "log", "sqrt"]) {
    const heights = surfacePhaseFrameHeights(
      values,
      6,
      sampling,
      [0, 100],
      scale,
    );
    assert.deepEqual(heights, [
      surfaceIntensity(80, [0, 100], scale),
      surfaceIntensity(20, [0, 100], scale),
      0,
    ]);
    assert.equal(
      heights[0] * scalePhaseReflections(lines, 1)[1],
      heights[0] * 0.25,
    );
  }
  assert.deepEqual(
    surfacePhaseFrameHeights(
      values,
      6,
      { ...sampling, frames: [0, 1] },
      [10, 50],
      "linear",
    ),
    [1, 0.25],
  );
  assert.deepEqual(
    surfacePhaseFrameHeights(
      values,
      6,
      { frames: [0], firstColumn: 3, lastColumn: 4 },
      [0, 100],
      "linear",
    ),
    [0.3],
    "Radial zoom excludes offscreen strong peaks",
  );
  assert.deepEqual(new Uint8Array(values.buffer), before);
});

test("surface contour levels stay in physical intensity units across linear, log and sqrt", () => {
  assert.deepEqual(
    surfaceContourLevels([0, 100], "linear").map((t) => t.value),
    [10, 20, 30, 40, 50, 60, 70, 80, 90],
  );
  for (const scale of ["linear", "log", "sqrt"])
    for (const limits of [
      [-20, 100],
      [0, 1e6],
      [0.001, 0.009],
      [1e7, 1e7 + 10],
      [5, 5],
    ]) {
      const levels = surfaceContourLevels(limits, scale);
      assert.ok(levels.length <= 12);
      for (const level of levels) {
        assert.ok(level.fraction > 0 && level.fraction < 1);
        assert.equal(
          level.fraction,
          surfaceIntensity(level.value, limits, scale),
        );
      }
    }
});

test("phase slices follow triangle depth and clipped geometry, including exact edges and holes", () => {
  const point = (x, y, radial, z, depth) => ({
    x,
    y,
    radial,
    z,
    depth,
    intensity: z * 100,
    frame: y,
    meshIndex: 0,
  });
  const triangle = [
    point(0, 0, 5, 0, 1),
    point(10, 0, 1, 1, 5),
    point(0, 10, 5, 0.5, 3),
  ];
  const slice = sliceSurfaceTriangle(triangle, "radial", 3);
  assert.equal(slice.length, 2);
  for (const p of slice) assert.equal(p.radial, 3);
  assert.deepEqual(
    slice.map((p) => [p.x, p.y, p.depth, p.z]),
    [
      [5, 0, 3, 0.5],
      [5, 5, 4, 0.75],
    ],
  );
  assert.equal(sliceSurfaceTriangle(triangle, "radial", 5).length, 2);
  assert.equal(
    sliceSurfaceTriangle(triangle, "radial", 1),
    null,
    "single vertex is not a line",
  );
  assert.equal(sliceSurfaceTriangle(triangle, "radial", 6), null);
  assert.equal(
    sliceSurfaceTriangle(
      triangle.map((p) => ({ ...p, z: 0.5 })),
      "z",
      0.5,
    ),
    null,
    "flat plateau is not an entire contour",
  );
  assert.equal(
    sliceSurfaceTriangle(
      triangle.map((p) => ({ ...p, z: NaN })),
      "z",
      0.5,
    ),
    null,
  );
});

test("phase references retain native d spacings and colors through units, wavelength and descending ranges", () => {
  const line = {
    x: 2,
    intensity: 100,
    color: "#ff00ff",
    hkl: [1, 1, 1],
    name: "Reference",
    phaseIndex: 3,
  };
  const d = surfacePhaseReferences(
    { unit: "d_A", wavelength: null },
    [line],
    [5, 1],
  );
  assert.equal(d[0].radial, 2);
  assert.equal(d[0].color, line.color);
  assert.deepEqual(d[0].hkl, line.hkl);
  const q = surfacePhaseReferences(
    { unit: "q_A^-1", wavelength: null },
    [line],
    [0, 8],
  );
  assert.equal(q[0].radial, Math.PI);
  const angle = surfacePhaseReferences(
    { unit: "2th_deg", wavelength: 1e-10 },
    [line],
    [0, 90],
  );
  assert.ok(
    Math.abs(angle[0].radial - (Math.asin(0.25) * 360) / Math.PI) < 1e-10,
  );
  assert.deepEqual(
    surfacePhaseReferences(
      { unit: "2th_deg", wavelength: null },
      [line],
      [0, 90],
    ),
    [],
  );
  assert.deepEqual(
    surfacePhaseReferences(
      { unit: "d_A" },
      [line, { ...line, x: NaN }, { ...line, x: -2 }],
      [3, 5],
    ),
    [],
  );
  assert.equal(
    line.x,
    2,
    "display conversion never replaces the phase's stored coordinate",
  );
});

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
  for (const [resolution, budget] of Object.entries(surfaceResolutions))
    for (const rows of [1, 2, 7, 999, 1_000_000])
      for (const cols of [1, 2, 300, 30_000, 1_000_000]) {
        const s = surfaceSampling(rows, cols, null, 1, resolution);
        assert.ok(s.frames.length * s.columns.length <= budget.vertices);
        assert.ok(s.columns.length <= budget.columns);
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
test("higher detail retains native radial samples and then the complete frame grid", () => {
  const fast = surfaceSampling(64, 2048, null, 1, "fast");
  const high = surfaceSampling(64, 2048, null, 1, "high");
  const fine = surfaceSampling(64, 2048, null, 1, "fine");
  assert.ok(!fast.columns.includes(1022));
  assert.equal(high.columns.length, 2048);
  assert.ok(high.columns.includes(1022));
  assert.equal(high.frameStep, 2);
  assert.equal(fine.frameStep, 1);
  assert.equal(fine.frames.length, 64);
  assert.equal(fine.frames.length * fine.columns.length, 131072);
  assert.deepEqual(
    surfaceSampling(64, 2048, null, 7, "fine").frames,
    [0, 7, 14, 21, 28, 35, 42, 49, 56, 63],
  );
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
