// Native gates are used locally and by CI; frozen independent reference data
// is exercised by Rust tests without a Python environment.
import { spawnSync } from "node:child_process";
import { appendFileSync, mkdirSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";
import {
  markdownSummary,
  seconds,
  textSummary,
  timingReport,
} from "./native_gate_timings.mjs";

const root = fileURLToPath(new URL("../../", import.meta.url));
const desktop = path.join(root, "desktop");
const flags = process.argv.slice(2);
const allowed = ["--processor", "--ui", "--host"];
if (flags.some((f) => !allowed.includes(f)))
  throw Error(`Use ${allowed.join(", ")}`);
const selected = new Set(flags.length ? flags : ["--processor", "--ui"]);
const artifacts = path.join(desktop, "artifacts/ci-native");
mkdirSync(artifacts, { recursive: true });
// Every step's wall time goes to the console, timings.json (latest run),
// timings-<flags>.json (kept when one CI job runs several gates) and, in
// GitHub Actions, the job summary. A failed run reports the steps so far.
const started = performance.now();
const steps = [];
let reported = false;
function report(status) {
  if (reported) return;
  reported = true;
  const timings = timingReport({
    steps,
    status,
    flags: [...selected],
    totalSeconds: (performance.now() - started) / 1000,
  });
  const json = `${JSON.stringify(timings, null, 2)}\n`;
  writeFileSync(path.join(artifacts, "timings.json"), json);
  const label = [...selected].map((f) => f.slice(2)).join("-");
  writeFileSync(path.join(artifacts, `timings-${label}.json`), json);
  console.log(`\n${textSummary(timings)}`);
  if (process.env.GITHUB_STEP_SUMMARY)
    appendFileSync(process.env.GITHUB_STEP_SUMMARY, markdownSummary(timings));
}
// Errors outside a step (for example a missing reference interpreter).
process.on("exit", (code) => report(code === 0 ? "passed" : "failed"));
function run(name, command, args, cwd = desktop) {
  const commandLine = `${command} ${args.join(" ")}`;
  console.log(`\n[${name}] ${commandLine}`);
  const start = performance.now();
  const r = spawnSync(command, args, {
    cwd,
    env: process.env,
    encoding: "utf8",
    timeout: 20 * 60 * 1000,
    maxBuffer: 128 * 1024 * 1024,
  });
  const elapsed = (performance.now() - start) / 1000;
  const failed = r.status !== 0 || r.error;
  steps.push({
    name,
    command: commandLine,
    cwd: path.relative(root, cwd) || ".",
    seconds: elapsed,
    status: failed ? "failed" : "passed",
    exitCode: r.status,
    signal: r.signal,
  });
  const output = `${r.stdout ?? ""}${r.stderr ?? ""}${r.error ? `\n${r.error.stack}` : ""}`;
  writeFileSync(path.join(artifacts, `${name}.log`), output);
  if (failed) {
    process.stderr.write(output.slice(-16000));
    report("failed");
    throw Error(
      `${name} failed (${r.status ?? r.signal}) after ${seconds(elapsed)} s; see desktop/artifacts/ci-native/${name}.log`,
    );
  }
  console.log(`${name}: passed in ${seconds(elapsed)} s`);
}
const node = (name, script, ...args) =>
  run(name, process.execPath, ["scripts/" + script, ...args]);
// Every gate checks the shared boundary, including processor-only CI jobs that
// do not install frontend dependencies.
node("glib-security-backport", "check_glib_backport.mjs");
node("native-contract-generation", "generate_native_contracts.mjs", "--check");
if (selected.has("--processor")) {
  run("rust-format", "cargo", [
    "fmt",
    "--manifest-path",
    "backend/Cargo.toml",
    "--",
    "--check",
  ]);
  // Keep the portable core healthy as native-only helpers evolve. Clippy and
  // library tests cannot replace the processor executable used by later gates.
  run("rust-core-clippy", "cargo", [
    "clippy",
    "--locked",
    "--manifest-path",
    "backend/Cargo.toml",
    "--no-default-features",
    "--all-targets",
    "--",
    "-D",
    "warnings",
  ]);
  run("rust-core-tests", "cargo", [
    "test",
    "--locked",
    "--manifest-path",
    "backend/Cargo.toml",
    "--no-default-features",
    "--lib",
  ]);
  run("rust-clippy", "cargo", [
    "clippy",
    "--locked",
    "--manifest-path",
    "backend/Cargo.toml",
    "--all-features",
    "--all-targets",
    "--",
    "-D",
    "warnings",
  ]);
  run("rust-tests", "cargo", [
    "test",
    "--locked",
    "--manifest-path",
    "backend/Cargo.toml",
    "--all-features",
  ]);
  // Tests can build diagnostic executables; stage the normal processor last.
  run("rust-build", "cargo", [
    "build",
    "--locked",
    "--manifest-path",
    "backend/Cargo.toml",
    "--all-features",
  ]);
}
if (selected.has("--ui")) {
  run("native-test-fixtures", "cargo", [
    "build",
    "--locked",
    "--manifest-path",
    "backend/Cargo.toml",
    "--example",
    "test_fixtures",
  ]);
  node("functional-coverage-map", "functional_coverage.mjs");
  run("frontend-unit", "npm", ["test"]);
  run("frontend-build", "npm", ["run", "build"]);
  for (const script of [
    "hook_refresh_smoke",
    "ui_components",
    "app_update_smoke",
    "native_backend_smoke",
    "native_custom_actions_smoke",
    "native_calibration_smoke",
    "native_mask_smoke",
    "native_integration_workflow_smoke",
    "overlay_command_order_smoke",
    "phase_editor_workflow_smoke",
    "pattern_figure_export_smoke",
    "pattern_figure_save_smoke",
    "pattern_figure_editor_smoke",
    "spottiness_smoke",
    "batch_waterfall_smoke",
    "batch_surface_smoke",
    "batch_surface_gpu_smoke",
    "batch_surface_guides_smoke",
    "batch_surface_axes_smoke",
    "batch_export_smoke",
    "batch_background_smoke",
    "processing_workers_smoke",
    "native_corrections_smoke",
    "correction_previews_smoke",
    "processing_drafts_smoke",
    "metadata_products_smoke",
    "native_project_smoke",
    "session_recovery_smoke",
    "dac_thermal_pressure_smoke",
    "native_geometry_mask_smoke",
    "native_detector_smoke",
    "native_lacosmic_smoke",
    "native_file_errors_smoke",
    "native_map_progress_smoke",
    "image_change_smoke",
    "hdf5_sources_smoke",
    "hdf5_master_vds_smoke",
    "detector_window_smoke",
    "map_detector_independence_smoke",
    "detector_source_smoke",
    "companion_windows_smoke",
  ])
    node(script, `${script}.mjs`);
  node("batch_background_export", "batch_export_smoke.mjs", "--background");
  node("image_change_webkit", "image_change_smoke.mjs", "--webkit");
  run("native-transport", process.execPath, [
    "--test",
    "scripts/native_calibration_transport.test.mjs",
    "scripts/native_mask_transport.test.mjs",
    "scripts/native_geometry_mask_transport.test.mjs",
    "scripts/native_lacosmic_transport.test.mjs",
    "scripts/native_integration_transport.test.mjs",
    "scripts/native_project_transport.test.mjs",
    "scripts/batch_background_transport.test.mjs",
  ]);
}
if (selected.has("--host")) {
  run("release-config", "npm", ["run", "test:release-config"]);
  run("host-prepare", "npm", ["run", "backend:prepare", "--", "--debug"]);
  run("host-frontend", "npm", ["run", "build"]);
  run("host-tests", "cargo", [
    "test",
    "--locked",
    "--manifest-path",
    "src-tauri/Cargo.toml",
  ]);
}
report("passed");
