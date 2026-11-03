import assert from "node:assert/strict";
import { test } from "node:test";
import { nearestSample, visibleSamples } from "../src/patternSamples.ts";

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
