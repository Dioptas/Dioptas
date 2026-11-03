import assert from "node:assert/strict";
import { test } from "node:test";
import { scalePhaseLines } from "../src/phaseLineScaling.ts";

const pattern = {
  x: [0, 1, 2, 3, 4, 5],
  y: [0, 1000, 20, 80, 40, 0],
  unit: "2th_deg",
};
const line = (x, intensity, phaseIndex = 0) => ({
  x,
  intensity,
  phaseIndex,
  name: "same phase name",
  color: "#e050a0",
  hkl: [1, 1, 1],
});
const lines = [line(1, 100), line(2, 10), line(3, 20), line(4, 0)];
const view = { xMin: 0, xMax: 5, yMin: -10, yMax: 1100 };
const linear = (y) => y;

test("strongest visible phase reflection reaches the measured pattern maximum", () => {
  assert.deepEqual(
    scalePhaseLines(pattern, lines, view, linear),
    [1000, 91, 192, -10],
  );
});

test("zooming excludes the strong offscreen pattern peak and phase reflection", () => {
  const tops = scalePhaseLines(
    pattern,
    lines,
    { ...view, xMin: 1.5, xMax: 4.5 },
    linear,
  );
  assert.deepEqual(tops.slice(1), [35, 80, -10]);
});

test("vertical zoom caps the line tops at the current upper intensity limit", () => {
  const tops = scalePhaseLines(
    pattern,
    lines,
    { ...view, yMin: 10, yMax: 50 },
    linear,
  );
  assert.deepEqual(tops, [50, 14, 18, 10]);
});

test("overlay intensities do not set the phase height", () => {
  const withOverlay = { ...pattern, curves: [{ x: [2], y: [10000] }] };
  assert.deepEqual(
    scalePhaseLines(withOverlay, lines, view, linear),
    [1000, 91, 192, -10],
  );
});

test("descending d-spacing samples use the same visible-range maximum", () => {
  const descending = {
    ...pattern,
    x: [...pattern.x].reverse(),
    y: [...pattern.y].reverse(),
  };
  assert.deepEqual(
    scalePhaseLines(descending, lines, view, linear),
    [1000, 91, 192, -10],
  );
});

test("each phase normalizes independently even with identical names and colors", () => {
  const tops = scalePhaseLines(
    pattern,
    [line(1, 100), line(2, 20), line(3, 2, 1), line(4, 1, 1)],
    view,
    linear,
  );
  assert.deepEqual(tops, [1000, 192, 1000, 495]);
});

test("log and square-root scales use the displayed measured maximum", () => {
  const log = scalePhaseLines(
    pattern,
    lines,
    { ...view, yMin: 0, yMax: 4 },
    (y) => (y > 0 ? Math.log10(y) : NaN),
  );
  assert.deepEqual(log, [3, 0.3, 0.6, 0]);
  const sqrt = scalePhaseLines(
    pattern,
    lines,
    { ...view, yMin: 0, yMax: 40 },
    Math.sqrt,
  );
  assert.ok(Math.abs(sqrt[0] - Math.sqrt(1000)) < 1e-12);
  assert.ok(Math.abs(sqrt[1] - Math.sqrt(1000) * 0.1) < 1e-12);
});

test("empty ranges, invalid data and zero intensities produce finite baselines", () => {
  assert.deepEqual(
    scalePhaseLines(pattern, lines, { ...view, xMin: 6, xMax: 8 }, linear),
    [-10, -10, -10, -10],
  );
  assert.deepEqual(
    scalePhaseLines(pattern, [line(2, 0), line(3, NaN)], view, linear),
    [-10, -10],
  );
  assert.deepEqual(
    scalePhaseLines(
      { ...pattern, y: [null, NaN, Infinity, null, null, null] },
      lines,
      view,
      linear,
    ),
    [-10, -10, -10, -10],
  );
});
