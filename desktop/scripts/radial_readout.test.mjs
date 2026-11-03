import assert from "node:assert/strict";
import { test } from "node:test";
import { radialValues, radialFields } from "../src/radialReadout.ts";

test("2θ, Q and d agree for a 1 Å wavelength, regardless of the active unit", () => {
  for (const [unit, x] of [
    ["2th_deg", 60],
    ["q_A^-1", 2 * Math.PI],
    ["d_A", 1],
  ]) {
    const values = radialValues(x, unit, 1e-10);
    assert.ok(Math.abs(values["2th_deg"] - 60) < 1e-12);
    assert.ok(Math.abs(values["q_A^-1"] - 2 * Math.PI) < 1e-12);
    assert.ok(Math.abs(values.d_A - 1) < 1e-12);
    assert.deepEqual(
      radialFields(x, unit, 1e-10).map((f) => f.unit),
      ["2th_deg", "q_A^-1", "d_A"],
    );
  }
});

test("changing wavelength changes Q and d at a fixed angle", () => {
  const values = radialValues(60, "2th_deg", 2e-10);
  assert.ok(Math.abs(values["q_A^-1"] - Math.PI) < 1e-12);
  assert.ok(Math.abs(values.d_A - 2) < 1e-12);
});

test("reciprocal units remain available without inventing a wavelength", () => {
  assert.equal(radialValues(2 * Math.PI, "q_A^-1").d_A, 1);
  assert.equal(radialValues(1, "d_A")["q_A^-1"], 2 * Math.PI);
  assert.equal(radialValues(1, "d_A")["2th_deg"], null);
  assert.equal(radialValues(60, "2th_deg")["q_A^-1"], null);
});

test("unreachable angles are unavailable, and zero angle has infinite d spacing", () => {
  assert.equal(radialValues(20, "q_A^-1", 1e-10)["2th_deg"], null);
  assert.equal(radialFields(0, "2th_deg", 1e-10)[2].value, "∞");
});

test("converted precision improves when zooming, rather than keeping arbitrary decimals", () => {
  const wide = radialFields(30.123456, "2th_deg", 0.406626e-10, 1);
  const zoomed = radialFields(30.123456, "2th_deg", 0.406626e-10, 0.0001);
  assert.equal(wide[0].value, "30");
  assert.equal(zoomed[0].value, "30.1235");
  for (const i of [1, 2])
    assert.ok(zoomed[i].value.length > wide[i].value.length);
});
