import test from "node:test";
import assert from "node:assert/strict";
import { batchDisplayInUnit } from "../src/batchDisplay.ts";
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
