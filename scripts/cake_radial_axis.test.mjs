import assert from "node:assert/strict";
import { test } from "node:test";
import {
  createCakeRadialAxis,
  cakeSourceCoordinate,
  cakeSourcePixel,
  nextCakeAxisUnit,
} from "../src/cakeRadialAxis.ts";
const near = (a, b) => assert.ok(Math.abs(a - b) < 1e-9, `${a} != ${b}`);
const q = (t, wavelength) =>
  (4 * Math.PI * Math.sin((t * Math.PI) / 360)) / (wavelength * 1e10);
const angular = { radialRange: [10, 130], fullWidth: 241, unit: "2th_deg" };

test("bin centers, not edges, are the scientific coordinates at all zoom levels", () => {
  near(cakeSourceCoordinate(angular, 0.5), 10);
  near(cakeSourceCoordinate(angular, 240.5), 130);
  for (const pixel of [-30, 0, 0.5, 27.25, 120.5, 240.5, 280])
    near(cakeSourcePixel(angular, cakeSourceCoordinate(angular, pixel)), pixel);
  const one = { ...angular, fullWidth: 1, radialRange: [30, 30] };
  near(cakeSourceCoordinate(one, 0.5), 30);
  near(cakeSourcePixel(one, 30), 0.5);
});

test("Q ticks invert the nonlinear conversion at fixed physical pixels and zoom bounds", () => {
  for (const wavelength of [0.2e-10, 0.4e-10, 1.54e-10]) {
    const axis = createCakeRadialAxis(angular, "q_A^-1", wavelength);
    for (const pixel of [0.5, 38.3, 80.5, 240.5]) {
      const expected = q(cakeSourceCoordinate(angular, pixel), wavelength);
      near(axis.atPixel(pixel), expected);
      near(axis.pixelAt(expected), pixel);
    }
    for (const [low, high] of [
      [0, 241],
      [40.25, 160.75],
      [-100, 100],
    ]) {
      const ticks = axis.ticks(low, high, 8);
      assert.ok(ticks.length > 1);
      for (const tick of ticks) {
        near(
          q(cakeSourceCoordinate(angular, tick.pixel), wavelength),
          tick.value,
        );
        assert.ok(tick.pixel >= low && tick.pixel <= high);
      }
      const bounds = axis.bounds(low, high);
      near(
        bounds[0],
        q(Math.max(0, cakeSourceCoordinate(angular, low)), wavelength),
      );
      near(bounds[1], q(cakeSourceCoordinate(angular, high), wavelength));
    }
    const ticks = axis.ticks(0, 241, 6);
    assert.ok(
      Math.abs(
        ticks[1].pixel -
          ticks[0].pixel -
          (ticks.at(-1).pixel - ticks.at(-2).pixel),
      ) > 1,
      "equal Q increments must have unequal angular pixel spacing",
    );
  }
});

test("combined Q cakes are not converted twice and can display angular ticks", () => {
  const grid = { radialRange: [1, 6], fullWidth: 301, unit: "q_A^-1" };
  const direct = createCakeRadialAxis(grid, "q_A^-1");
  near(direct.atPixel(150.5), 3.5);
  near(direct.pixelAt(3.5), 150.5);
  assert.equal(direct.note, undefined);
  for (const wavelength of [0.4e-10, 1.54e-10]) {
    const axis = createCakeRadialAxis(grid, "2th_deg", wavelength);
    for (const tick of axis.ticks(30, 275, 7))
      near(cakeSourceCoordinate(grid, tick.pixel), q(tick.value, wavelength));
    near(axis.pixelAt(axis.atPixel(150.5)), 150.5);
  }
});

test("missing/changed wavelength has an explicit source-unit fallback without changing data", () => {
  const grid = { ...angular, data: new Float32Array([1, 2, 3]).buffer };
  for (const wavelength of [undefined, 0, NaN, Infinity]) {
    const axis = createCakeRadialAxis(grid, "q_A^-1", wavelength);
    assert.equal(axis.unit, "2th_deg");
    assert.match(axis.note, /requires a wavelength/);
    near(axis.atPixel(120.5), 70);
  }
  const sourceQ = { radialRange: [1, 20], fullWidth: 100, unit: "q_A^-1" };
  const invalid = createCakeRadialAxis(sourceQ, "2th_deg", 1.54e-10);
  assert.equal(invalid.unit, "q_A^-1");
  assert.match(invalid.note, /cannot be converted/);
  assert.ok(
    createCakeRadialAxis(sourceQ, "2th_deg", 0.4e-10).unit === "2th_deg",
  );
  const before = structuredClone(grid);
  createCakeRadialAxis(grid, "q_A^-1", 0.4e-10).ticks(0, 241, 8);
  assert.deepEqual(grid, before);
});

test("d leaves the last Qt-supported cake unit selected", () => {
  assert.equal(nextCakeAxisUnit("d_A", "q_A^-1"), "q_A^-1");
  assert.equal(nextCakeAxisUnit("d_A", "2th_deg"), "2th_deg");
  assert.equal(nextCakeAxisUnit("2th_deg", "q_A^-1"), "2th_deg");
  assert.equal(nextCakeAxisUnit("q_A^-1", "2th_deg"), "q_A^-1");
});
