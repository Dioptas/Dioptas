import assert from "node:assert/strict";
import { test } from "node:test";
import { patternPositionInUnit } from "../src/linkedPosition.ts";
test("shared markers use physical 2θ regardless of Integration's current radial unit", () => {
  const linked = { twoTheta: 60, radial: 999, contours: [] };
  assert.equal(patternPositionInUnit(linked, undefined, "2th_deg", 1e-10), 60);
  assert.ok(
    Math.abs(
      patternPositionInUnit(linked, undefined, "q_A^-1", 1e-10) - 2 * Math.PI,
    ) < 1e-12,
  );
  assert.ok(
    Math.abs(patternPositionInUnit(linked, undefined, "d_A", 1e-10) - 1) <
      1e-12,
  );
});
test("uncalibrated stored patterns keep local markers without inventing a detector angle", () => {
  const local = { x: 2 * Math.PI, unit: "q_A^-1" };
  assert.ok(Math.abs(patternPositionInUnit(null, local, "d_A") - 1) < 1e-12);
  assert.equal(patternPositionInUnit(null, local, "2th_deg"), undefined);
  assert.equal(patternPositionInUnit(null, undefined, "q_A^-1"), undefined);
});
