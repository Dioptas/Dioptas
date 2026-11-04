import assert from "node:assert/strict";
import { test } from "node:test";
import { mapPatternInUnit } from "../src/mapPattern.ts";
const pattern = {
  x: [30, 60, 90],
  y: [10, 20, 30],
  unit: "2th_deg",
  curves: [{ name: "reference", color: "#ff8800", x: [60], y: [50] }],
  phaseLines: [
    {
      name: "Au 20 GPa",
      color: "#ff00ff",
      x: 60,
      intensity: 100,
      hkl: [1, 1, 1],
      phaseIndex: 0,
    },
  ],
};
test("Map converts measured points, overlays and phase lines together without altering source data", () => {
  const original = structuredClone(pattern);
  const q = mapPatternInUnit(pattern, "q_A^-1", 1e-10);
  assert.ok(Math.abs(q.x[1] - 2 * Math.PI) < 1e-12);
  assert.ok(Math.abs(q.curves[0].x[0] - 2 * Math.PI) < 1e-12);
  assert.ok(Math.abs(q.phaseLines[0].x - 2 * Math.PI) < 1e-12);
  const d = mapPatternInUnit(q, "d_A", 1e-10);
  assert.ok(Math.abs(d.x[1] - 1) < 1e-12);
  assert.ok(Math.abs(d.curves[0].x[0] - 1) < 1e-12);
  assert.ok(Math.abs(d.phaseLines[0].x - 1) < 1e-12);
  assert.deepEqual(d.curves[0].y, [50]);
  assert.equal(d.curves[0].name, "reference");
  assert.deepEqual(d.phaseLines[0].hkl, [1, 1, 1]);
  assert.deepEqual(pattern, original);
  assert.equal(mapPatternInUnit(pattern, "2th_deg", 1e-10), pattern);
});
test("Map discards unreachable angular positions and retains descending d-spacing order", () => {
  const input = {
    ...pattern,
    unit: "q_A^-1",
    x: [2 * Math.PI, 20],
    y: [10, 20],
    curves: [{ ...pattern.curves[0], x: [2 * Math.PI, 20], y: [50, null] }],
    phaseLines: [{ ...pattern.phaseLines[0], x: 20 }],
  };
  const angle = mapPatternInUnit(input, "2th_deg", 1e-10);
  assert.equal(angle.x.length, 1);
  assert.deepEqual(angle.curves[0].y, [50]);
  assert.deepEqual(angle.phaseLines, []);
  const d = mapPatternInUnit(pattern, "d_A", 1e-10);
  assert.ok(d.x[0] > d.x[1] && d.x[1] > d.x[2]);
});
