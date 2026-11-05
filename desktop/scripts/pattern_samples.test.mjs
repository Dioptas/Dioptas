import {
  legendPlacement,
  legendSampleIndices,
} from "../src/legendPlacement.ts";
import assert from "node:assert/strict";
import { test } from "node:test";
import {
  nearestSample,
  visibleSamples,
  sampleInspectionOrder,
} from "../src/patternSamples.ts";

test("visible intervals preserve crossing segments, duplicates and both coordinate orders", () => {
  assert.deepEqual(visibleSamples([0, 2, 4, 6, 8], 2.5, 3.5), [1, 3]);
  assert.deepEqual(visibleSamples([8, 6, 4, 2, 0], 2.5, 3.5), [2, 4]);
  assert.deepEqual(visibleSamples([0, 2, 2, 2, 4], 2, 2, false), [1, 4]);
  assert.deepEqual(visibleSamples([0, 2, 1, 4], 2, 3), [0, 4]);
  assert.deepEqual(visibleSamples([0, NaN, 4], 2, 3), [0, 3]);
  assert.deepEqual(visibleSamples([], 2, 3), [0, 0]);
});

test("binary nearest sampling agrees with exhaustive lookup, including first-index ties", () => {
  for (const x of [
    [0, 1, 1, 2, 7, 7],
    [7, 7, 2, 1, 1, 0],
    [1, 1, 1],
    [2, 0, 5, 1],
  ]) {
    for (let v = -1; v < 9; v += 0.125) {
      const expected = x.reduce(
        (best, p, i) => (Math.abs(p - v) < Math.abs(x[best] - v) ? i : best),
        0,
      );
      assert.equal(nearestSample(x, v), expected, `${x}: ${v}`);
    }
  }
  assert.equal(nearestSample([], 1), -1);
});

test("missing coordinates do not hide later finite samples", () => {
  assert.equal(nearestSample([NaN, 4, 2], 2.1), 2);
  assert.equal(nearestSample([Infinity, 3, 2], 2.1), 2);
  assert.equal(nearestSample([NaN, Infinity], 2), -1);
});

test("keyboard inspection follows visual coordinates without changing source order", () => {
  for (const x of [
    [0, 1, 2, 3, 4],
    [4, 3, 2, 1, 0],
    [NaN, 4, 1, 3, 0, 2],
  ]) {
    const original = [...x];
    const first = [...sampleInspectionOrder(x, 1, 3, null, "first")];
    assert.deepEqual(
      first.map((i) => x[i]),
      [1, 2, 3],
    );
    const last = [...sampleInspectionOrder(x, 1, 3, null, "last")];
    assert.deepEqual(
      last.map((i) => x[i]),
      [3, 2, 1],
    );
    assert.equal(
      x[[...sampleInspectionOrder(x, 1, 3, first[1], "next")][0]],
      3,
    );
    assert.equal(
      x[[...sampleInspectionOrder(x, 1, 3, first[1], "previous")][0]],
      1,
    );
    assert.deepEqual(x, original);
  }
  assert.deepEqual([...sampleInspectionOrder([NaN], 0, 4, null, "first")], []);
});

test("legend defaults avoid occupied curves and labelled plot controls", () => {
  const bounds = { left: 20, top: 10, width: 300, height: 200 };
  const result = legendPlacement(
    bounds,
    100,
    30,
    [{ x: 280, y: 20 }],
    [{ left: 20, top: 10, width: 100, height: 40 }],
  );
  assert(
    result.top > 100,
    "The legend uses empty lower space instead of the peak/cursor labels",
  );
  assert.equal(result.align, "right");
});
test("legend candidates stay inside small plot bounds", () => {
  const bounds = { left: 3, top: 4, width: 20, height: 10 };
  const result = legendPlacement(bounds, 100, 40, [], []);
  const x = result.left - (result.align === "right" ? 20 : 0);
  assert(x >= bounds.left && x + 20 <= bounds.left + bounds.width);
  assert(
    result.top >= bounds.top && result.top + 10 <= bounds.top + bounds.height,
  );
});

test("legend placement retains a one-sample diffraction peak between regular samples", () => {
  const x = Array.from({ length: 1000 }, (_, i) => i),
    y = x.map(() => 0);
  y[137] = 9000;
  assert([...legendSampleIndices(x, y, 0, x.length)].includes(137));
  assert.equal(y[137], 9000);
  assert.equal(x[137], 137);
});

test("legend placement protects a peak rather than preferring a crowded baseline", () => {
  const bounds = { left: 0, top: 0, width: 100, height: 100 };
  const points = [
    { x: 80, y: 10, weight: 10 },
    ...Array.from({ length: 40 }, () => ({ x: 80, y: 90, weight: 0.05 })),
  ];
  const result = legendPlacement(bounds, 40, 20, points, [
    { left: 0, top: 0, width: 50, height: 100 },
  ]);
  assert(result.top > 50);
});
