// Headless packaged-processor check; never opens an application window.
import assert from "node:assert/strict";
import { cp, mkdtemp, realpath, rm, mkdir, writeFile } from "node:fs/promises";
import path from "node:path";
import os from "node:os";
import { inspectStandalone } from "./inspect_standalone.mjs";
import { nativeClient, root } from "./native_backend_client.mjs";
const application =
  process.argv[2] ??
  path.join(
    root,
    "desktop/src-tauri/target/debug/bundle/macos/Dioptas Desktop.app",
  );
const inspection = await inspectStandalone(application);
const directory = await realpath(
  await mkdtemp(path.join(os.tmpdir(), "dioptas-packaged-processor-")),
);
let native;
try {
  const app = path.join(directory, "Relocated Dioptas.app");
  await cp(application, app, { recursive: true });
  const profile = `(version 1) (allow default)\n(deny file-read* (subpath ${JSON.stringify(root)}))\n(deny process-exec (regex #".*/[Pp]ython[^/]*$"))\n`;
  native = nativeClient({
    command: "/usr/bin/sandbox-exec",
    args: ["-p", profile, path.join(app, "Contents/MacOS/dioptas-processor")],
    cwd: directory,
  });
  const call = async (a, p = {}) => {
    const r = await native.invoke(a, p);
    assert.equal(r.ok, true, `${a}: ${r.error}`);
    return r;
  };
  assert.equal((await call("__host__")).runtime, "rust");
  await call("example");
  await call("open_calibration", {
    path: path.join(
      app,
      "Contents/Resources/dioptas/examples/CeO2_Pilatus1M.poni",
    ),
  });
  await call("integration_settings", { bins: 128, cake_bins: 24, poisson_errors: true });
  for (const kind of ["cylinder", "sphere"]) {
    const corrected = await call("integration_correction", {
      kind, enabled: true, parameters: { radius: 0.2, beam_width: 0.12 },
      material: { mode: "formula", formula: "SiO2", density: 2.2 },
      ...(kind === "cylinder" ? {
        parameters: { radius: 0.2, beam_width: 0.12, axis_tilt: 35, axis_rotation: 23, wall_thickness: 0.02 },
        container: { enabled: true, material: { mode: "formula", formula: "SiO2", density: 2.23 } },
      } : {}),
    });
    assert.ok(corrected.state.integration.corrections[kind].parameters.absorption_coefficient > 0);
    assert.ok(corrected.pattern.sigma.some((v) => v > 0));
    assert.ok(corrected.pattern.y.every(Number.isFinite));
  }
  await call("configuration", { operation: "duplicate" });
  const result = await call("combination_settings", {
    patterns: true,
    cakes: true,
  });
  assert.equal(result.pattern.y.length, 128);
  assert.equal(result.cake.height, 24);
  const project = path.join(directory, "portable.dio");
  await call("save_project", { path: project });
  const restored = await call("open_project", { path: project });
  assert.equal(restored.state.configurationCount, 2);
  assert.equal(restored.state.combination.patterns, true);
  assert.deepEqual(restored.pattern, result.pattern);
  assert.equal(restored.state.integration.corrections.cylinder.container.enabled, true);
  assert.equal(restored.state.integration.corrections.sphere.material.mode, "formula");
  await call("save_combined_pattern", {
    path: path.join(directory, "portable.xy"),
  });
  const report = {
    headless: true,
    relocated: true,
    sourceCheckoutDenied: true,
    pythonUnavailable: true,
    combinedPatternAndCake: true,
    projectRoundtrip: true,
    cylinderSphereAndCapillary: true,
    materialLookup: true,
    countingStd: true,
    inspection,
  };
  const artifacts = path.join(root, "desktop/artifacts/standalone");
  await mkdir(artifacts, { recursive: true });
  await writeFile(
    path.join(artifacts, "processor-headless.json"),
    JSON.stringify(report, null, 2) + "\n",
  );
  console.log(JSON.stringify(report));
} finally {
  await native?.close();
  await rm(directory, { recursive: true, force: true });
}
