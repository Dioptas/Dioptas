// Real Rust stdio timings and exact scientific comparisons against a saved
// pre-optimization processor. No GUI windows or user session are involved.
// DIOPTAS_MASSIF_BASELINE=/absolute/path/to/old/dioptas-processor node scripts/massif_performance.mjs
import assert from "node:assert/strict";
import path from "node:path";
import { mkdir, writeFile } from "node:fs/promises";
import { nativeClient, root } from "./native_backend_client.mjs";

const seeds = [
  [637, 564, 1],
  [671, 511, 2],
  [668, 703, 3],
  [350.5, 592.8, 1],
  [554.3, 367.9, 1],
];
const fixtures = [
  { name: "CeO2", shape: [1043, 981], seeds, repeats: 3, fit: true },
  {
    name: "LaB6",
    shape: [2048, 2048],
    repeats: 2,
    seeds: [
      [1129.4, 1179.6, 1],
      [1119.8, 1268.5, 2],
    ],
    path: path.join(root, "tests/data/LaB6_40keV_MarCCD.tif"),
    setup: {
      calibrant: "LaB6",
      wavelength: 0.31,
      distance: 200,
      pixel_x: 79,
      pixel_y: 79,
    },
  },
];
const artifacts = path.join(root, "artifacts/massif-performance");
await mkdir(artifacts, { recursive: true });

async function measure(executable, fixture) {
  const native = nativeClient(executable ? { executable } : {});
  const call = async (action, payload = {}) => {
    const result = await native.invoke(action, payload);
    assert.equal(result.ok, true, `${action}: ${JSON.stringify(result)}`);
    return result;
  };
  const picks = [],
    times = [],
    fits = [];
  try {
    // Replacing the source must force a cold search, even for the same file.
    for (let repeat = 0; repeat < fixture.repeats; repeat++) {
      if (fixture.path) {
        await call("open_image", { path: fixture.path });
        await call("calibration_setup", fixture.setup);
        await call("clear_peaks");
      } else await call("example");
      for (const [index, [x, y, ring]] of fixture.seeds.entries()) {
        const start = performance.now();
        const result = await call("pick_peak", { x, y, ring });
        times.push({
          repeat,
          cold: index === 0,
          ms: performance.now() - start,
        });
        picks.push(result.state.calibration.picks.at(-1));
      }
      if (repeat === 0 && fixture.fit) {
        for (const automatic of [false, true]) {
          await call("workflow_settings", { numberOfRings: 4 });
          const result = await call("calibrate", { automatic });
          assert.ok(result.state.calibration.rmsDegrees < 0.05);
          fits.push({
            automatic,
            geometry: result.state.geometry,
            rmsDegrees: result.state.calibration.rmsDegrees,
            picks: result.state.calibration.picks,
          });
        }
      }
    }
    return { times, picks, fits };
  } finally {
    await native.close();
  }
}

const summarize = (result) =>
  Object.fromEntries(
    [true, false].map((cold) => {
      const values = result.times
        .filter((t) => t.cold === cold)
        .map((t) => t.ms)
        .sort((a, b) => a - b);
      return [
        cold ? "coldMs" : "warmMs",
        {
          min: values[0],
          median: values[Math.floor(values.length / 2)],
          max: values.at(-1),
        },
      ];
    }),
  );
const results = [];
for (const fixture of fixtures) {
  const baseline = process.env.DIOPTAS_MASSIF_BASELINE
    ? await measure(process.env.DIOPTAS_MASSIF_BASELINE, fixture)
    : undefined;
  const optimized = await measure(undefined, fixture);
  if (baseline) {
    assert.deepEqual(
      optimized.picks,
      baseline.picks,
      "All picked coordinates and their order remain exact",
    );
    assert.deepEqual(
      optimized.fits,
      baseline.fits,
      "Manual/automatic fit geometry, RMS and refined picks remain exact",
    );
  }
  const summary = {
    source: fixture.name,
    shape: fixture.shape,
    timingScope:
      "optimized development build; stdio request/response, excluding GUI redraw",
    baseline: baseline && summarize(baseline),
    optimized: summarize(optimized),
    exactComparison: baseline
      ? { pickedGroups: optimized.picks.length, fits: optimized.fits.length }
      : null,
    rmsDegrees: optimized.fits.map((f) => ({
      automatic: f.automatic,
      rms: f.rmsDegrees,
    })),
  };
  results.push({ summary, baseline, optimized });
}
await writeFile(
  path.join(artifacts, "results.json"),
  JSON.stringify(results, null, 2) + "\n",
);
console.log(
  JSON.stringify(
    results.map((r) => r.summary),
    null,
    2,
  ),
);
