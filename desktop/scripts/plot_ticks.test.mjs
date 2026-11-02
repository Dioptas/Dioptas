import assert from "node:assert/strict";
import { test } from "node:test";
import { linearAxisTicks, linearTicks, logTicks } from "../src/plotTicks.ts";

test("linear ticks use rounded multiples within irregular view limits", () => {
  assert.deepEqual(
    linearTicks(1.37, 27.91, 5).map((t) => t.value),
    [5, 10, 15, 20, 25],
  );
  assert.deepEqual(
    linearTicks(-3.2, 7.7, 4).map((t) => t.value),
    [-2.5, 0, 2.5, 5, 7.5],
  );
  assert.deepEqual(
    linearTicks(0.031, 0.089, 4).map((t) => t.label),
    ["0.04", "0.06", "0.08"],
  );
});

test("large and small intensities have distinct compact labels through zoom", () => {
  for (const [min, max] of [
    [0, 5600000],
    [1e9, 1e9 + 1000],
    [0.0000013, 0.0000028],
  ]) {
    const ticks = linearTicks(min, max, 5);
    assert.ok(ticks.length >= 2);
    assert.equal(new Set(ticks.map((t) => t.label)).size, ticks.length);
    for (const tick of ticks) {
      assert.ok(tick.value >= min && tick.value <= max);
      assert.ok(
        Math.abs(Number(tick.label) - tick.value) <=
          Math.abs(tick.value) * 1e-12,
      );
    }
  }
});

test("log ticks use powers of ten, then 1/2/5 and rounded values at closer zoom", () => {
  const wide = logTicks(-1.2, 6.8, 5);
  assert.ok(wide.length >= 2);
  assert.ok(wide.every((tick) => Number.isInteger(tick.value)));
  const medium = logTicks(1, 3, 8);
  assert.deepEqual(
    medium.map((t) => t.label),
    ["10", "20", "50", "100", "200", "500", "1000"],
  );
  const narrow = logTicks(Math.log10(120), Math.log10(160), 4);
  assert.ok(narrow.length >= 3);
  assert.ok(narrow.every((t) => Number(t.label) % 10 === 0));
});

test("invalid and degenerate ranges do not produce ticks", () => {
  for (const ticks of [linearTicks(1, 1), linearTicks(NaN, 3), logTicks(2, 1)])
    assert.deepEqual(ticks, []);
});

test("axis labels factor out small powers of ten", () => {
  const axis = linearAxisTicks(0.00001, 0.00005, 4);
  assert.equal(axis.annotation, "×10⁻⁵");
  assert.deepEqual(
    axis.ticks.map((tick) => tick.label),
    ["1", "2", "3", "4", "5"],
  );
});

test("axis offsets and scales preserve original tick coordinates and precision", () => {
  for (const [min, max] of [
    [123.45601, 123.45605],
    [-179.45605, -179.45601],
    [1e9, 1e9 + 1000],
    [0, 5e6],
    [-0.00005, -0.00001],
  ]) {
    const original = linearTicks(min, max, 5);
    const axis = linearAxisTicks(min, max, 5);
    assert.ok(axis.annotation);
    assert.deepEqual(
      axis.ticks.map((tick) => tick.value),
      original.map((tick) => tick.value),
    );
    assert.equal(
      new Set(axis.ticks.map((tick) => tick.label)).size,
      axis.ticks.length,
    );
    for (const tick of axis.ticks) {
      assert.ok(tick.label.length <= 5, `Compact tick: ${tick.label}`);
      const reconstructed = axis.offset + axis.scale * Number(tick.label);
      assert.ok(
        Math.abs(reconstructed - tick.value) <
          Math.max(1e-15, Math.abs(tick.value) * 1e-13),
      );
    }
  }
});

test("ordinary axis labels stay familiar without annotations", () => {
  const axis = linearAxisTicks(-180, 180, 6);
  assert.equal(axis.annotation, null);
  assert.equal(axis.offset, 0);
  assert.equal(axis.scale, 1);
  assert.deepEqual(axis.ticks, linearTicks(-180, 180, 6));
  assert.deepEqual(linearAxisTicks(1, 1).ticks, []);
});
