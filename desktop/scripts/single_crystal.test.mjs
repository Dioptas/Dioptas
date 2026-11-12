import assert from "node:assert/strict";
import { test } from "node:test";
import {
  crystalDefaults,
  crystalConfigError,
} from "../src/singleCrystalDomain.ts";
import { crystalPixelReading } from "../src/singleCrystalReadout.ts";
test("SC readout preserves top-down detector rows and uses its own wavelength", () => {
  const data = {
    shape: [256, 256],
    config: crystalDefaults,
    frame: 4,
    geometry: { wavelength: 1 },
  };
  const top = crystalPixelReading(
    data,
    { x: 3, y: 255 },
    { value: 123, twoTheta: 60 },
  );
  const bottom = crystalPixelReading(
    data,
    { x: 3, y: 0 },
    { value: 123, twoTheta: 60 },
  );
  assert.equal(top.fields[1].value, "0");
  assert.equal(bottom.fields[1].value, "255");
  assert.equal(top.fields[2].value, "123");
  assert.equal(top.fields.find((f) => f.label === "d").value, "1");
  assert.equal(top.fields.find((f) => f.label === "ω").value, "0.450°");
});
test("SC drafts report all bounded kernel inputs and degenerate metrics", () => {
  assert.equal(crystalConfigError(crystalDefaults), null);
  for (const patch of [
    { smoothness: 0 },
    { link_radius: 100 },
    { tolerance: 0 },
    { polarization: 2 },
    { saturation: 0 },
    { omega_start: 1e6 },
    { min_pixels: 1.2 },
    { metric: [1, 1, 1, 1, 1, 179] },
  ])
    assert.notEqual(crystalConfigError({ ...crystalDefaults, ...patch }), null);
});
