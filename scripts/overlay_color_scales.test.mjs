import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import {
  overlayScaleColors,
  overlayColorContrast,
  OVERLAY_SCALE_MIN_CONTRAST,
} from "../src/overlayColorScales.ts";
const maps = JSON.parse(
  readFileSync(new URL("../src/pyqtgraph-colormaps.json", import.meta.url)),
);
const rgb = (hex) =>
  hex
    .slice(1)
    .match(/../g)
    .map((channel) => parseInt(channel, 16));
for (const name of [
  "viridis",
  "plasma",
  "magma",
  "inferno",
  "cividis",
  "turbo",
]) {
  test(`${name} overlay lines stay visible in both directions`, () => {
    const forward = overlayScaleColors(maps[name].colors, 128);
    for (const color of forward)
      assert.ok(
        overlayColorContrast(rgb(color)) >= OVERLAY_SCALE_MIN_CONTRAST - 0.02,
        color,
      );
    assert.deepEqual(
      overlayScaleColors(maps[name].colors, 128, true),
      [...forward].reverse(),
    );
    assert.ok(new Set(forward).size > 120);
    assert.equal(overlayScaleColors(maps[name].colors, 1).length, 1);
    assert.deepEqual(
      overlayScaleColors(maps[name].colors, 1, true),
      overlayScaleColors(maps[name].colors, 1),
    );
  });
}
