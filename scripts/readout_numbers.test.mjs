import assert from "node:assert/strict";
import { test } from "node:test";
import { coordinateValue, intensityValue } from "../src/readoutNumbers.ts";

test("a 0–1600 intensity view shows whole mouse coordinates; zoom reveals finer digits", () => {
  assert.equal(coordinateValue(957.48123, 1600 / 500), "957");
  assert.equal(coordinateValue(957.48123, 16 / 500), "957.48");
  assert.equal(coordinateValue(957.48123, 0.16 / 500), "957.4812");
});

test("angular and negative coordinates use precision justified by screen resolution", () => {
  assert.equal(coordinateValue(14.486123, 30 / 600), "14.49");
  assert.equal(coordinateValue(-67.2893, 360 / 600), "-67.3");
  assert.equal(coordinateValue(-0.000002836, 1e-8), "-2.84e-6");
});

test("large offsets retain differences visible after zooming", () => {
  const first = coordinateValue(1e9 + 12, 0.1);
  const second = coordinateValue(1e9 + 13, 0.1);
  assert.notEqual(first, second);
  assert.equal(Number(first), 1e9 + 12);
  assert.equal(Number(second), 1e9 + 13);
});

test("integer source counts stay exact and processed intensities have concise significant digits", () => {
  assert.equal(intensityValue(51746), "51,746");
  assert.equal(intensityValue(78.634198), "78.63");
  assert.equal(intensityValue(null), "—");
});
