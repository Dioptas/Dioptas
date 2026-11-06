import test from "node:test";
import assert from "node:assert/strict";
import {
  batchDisplayInUnit,
  batchNormalizationRegion,
} from "../src/batchDisplay.ts";
import { batchRadialBin } from "../src/batchPlot.ts";
test("batch markers project into nonuniform ascending and descending radial axes", () => {
  assert.equal(batchRadialBin(15, [10, 20, 40]), 1);
  assert.equal(batchRadialBin(30, [40, 20, 10]), 1);
  assert.equal(batchRadialBin(10, [40, 20, 10]), 2.5);
  assert.equal(batchRadialBin(10, [10]), 0.5);
  assert.equal(batchRadialBin(50, [10, 20, 40]), null);
});
test("linked batch coordinates convert without replacing the intensity matrix or columns", () => {
  const raster = { data: new Float32Array([1, 2, 3, 4]) };
  const original = { x: [10, 20], unit: "2th_deg", wavelength: 1e-10, raster };
  const converted = batchDisplayInUnit(original, "q_A^-1");
  assert.deepEqual(
    converted.x,
    original.x.map((v) => 4 * Math.PI * Math.sin((v * Math.PI) / 360)),
  );
  assert.equal(converted.raster, raster);
  assert.deepEqual(original.x, [10, 20]);
});
test("stored reciprocal axes link without inventing a wavelength", () => {
  const original = { x: [1, 2, 3], unit: "q_A^-1", wavelength: null };
  assert.deepEqual(batchDisplayInUnit(original, "d_A").x, [
    2 * Math.PI,
    Math.PI,
    (2 * Math.PI) / 3,
  ]);
  assert.equal(batchDisplayInUnit(original, "2th_deg"), original);
});
test("unreachable angular conversion keeps all source columns and their valid axis", () => {
  const original = { x: [1, 100], unit: "q_A^-1", wavelength: 1e-10 };
  assert.equal(batchDisplayInUnit(original, "2th_deg"), original);
});

test("normalization limits follow the shown axis and keep the stored physical region", () => {
  const original = {
    unit: "d_A",
    wavelength: null,
    normalizationRegion: { minimum: 2, maximum: 4, unit: "q_A^-1" },
  };
  assert.deepEqual(batchNormalizationRegion(original), {
    minimum: Math.PI / 2,
    maximum: Math.PI,
    unit: "d_A",
  });
  assert.deepEqual(original.normalizationRegion, {
    minimum: 2,
    maximum: 4,
    unit: "q_A^-1",
  });
  assert.equal(
    batchNormalizationRegion({ ...original, unit: "2th_deg" }),
    null,
  );
});
