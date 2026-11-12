import assert from "node:assert/strict";
import fs from "node:fs/promises";
import path from "node:path";
import { root } from "./native_backend_client.mjs";
const fixture = JSON.parse(
  await fs.readFile(path.join(root, "artifacts/scxrd-fixture/truth.json")),
);
const result = JSON.parse(
  await fs.readFile(path.join(root, "artifacts/scxrd-native/completed.json")),
);
const errors = [];
for (const row of result.reflections.filter((r) => r.flags === 0)) {
  const t = result.tracks.find((t) => t.id === row.track);
  assert.ok(t);
  const nearest = fixture.crossings.toSorted(
    (a, b) =>
      (a[0] - t.observed[0]) ** 2 +
      (a[1] - t.observed[1]) ** 2 +
      100 * (a[2] - t.observed[2]) ** 2 -
      ((b[0] - t.observed[0]) ** 2 +
        (b[1] - t.observed[1]) ** 2 +
        100 * (b[2] - t.observed[2]) ** 2),
  )[0];
  const [x, y, omega] = nearest;
  assert.ok(Math.hypot(x - t.observed[0], y - t.observed[1]) < 0.05);
  let photons = 0;
  for (let f = 0; f < fixture.frames; f++) {
    const angle =
      fixture.omega_start + f * fixture.omega_step + fixture.exposure / 2;
    const rocking = Math.exp(-0.5 * ((angle - omega) / 0.36) ** 2);
    if (rocking < 1e-5) continue;
    for (let yy = Math.floor(y) - 4; yy <= Math.ceil(y) + 4; yy++)
      for (let xx = Math.floor(x) - 4; xx <= Math.ceil(x) + 4; xx++)
        photons += Math.round(
          3500 *
            rocking *
            Math.exp((-0.5 * ((xx - x) ** 2 + (yy - y) ** 2)) / 0.8 ** 2),
        );
  }
  const measured = row.intensity / row.correction;
  errors.push({
    track: row.track,
    photons,
    measured,
    relative: (measured - photons) / photons,
  });
}
const ordered = errors.map((e) => Math.abs(e.relative)).sort((a, b) => a - b);
const report = {
  description:
    "Integrated original photon budget against independently generated analytic Ewald/Gaussian TIFF fixture; no noise, flat background. This does not establish measured-data integration parity.",
  measurements: errors.length,
  medianAbsoluteRelativeError: ordered[Math.floor(ordered.length / 2)],
  p95AbsoluteRelativeError: ordered[Math.floor(ordered.length * 0.95)],
  maximumAbsoluteRelativeError: ordered.at(-1),
  support: {
    pixels: result.config.aperture_radius,
    degrees: result.config.omega_radius,
  },
  measurementsExcludedByQuality: result.reflectionCount - errors.length,
  errors,
};
await fs.writeFile(
  path.join(root, "artifacts/scxrd-native/flux-check.json"),
  JSON.stringify(report, null, 2),
);
assert.ok(report.p95AbsoluteRelativeError < 0.002);
assert.ok(report.maximumAbsoluteRelativeError < 0.02);
console.log(JSON.stringify({ ...report, errors: undefined }, null, 2));
