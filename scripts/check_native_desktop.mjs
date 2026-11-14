// Native gates are used locally and by CI; frozen independent reference data
// is exercised by Rust tests without a Python environment.
import { spawn, spawnSync } from "node:child_process";
import { appendFileSync, existsSync, mkdirSync, writeFileSync } from "node:fs";
import { availableParallelism } from "node:os";
import { fileURLToPath } from "node:url";
import path from "node:path";
import {
  coverageRequested,
  gateSwitch,
  markdownSummary,
  runPool,
  seconds,
  shardTasks,
  textSummary,
  timingReport,
  uiJobs,
  uiShard,
} from "./native_gate_timings.mjs";

const root = fileURLToPath(new URL("../", import.meta.url));
const desktop = root;
const flags = process.argv.slice(2);
const allowed = ["--processor", "--ui", "--host"];
if (flags.some((f) => !allowed.includes(f)))
  throw Error(`Use ${allowed.join(", ")}`);
const selected = new Set(flags.length ? flags : ["--processor", "--ui"]);
const artifacts = path.join(desktop, "artifacts/ci-native");
// DIOPTAS_GATE_COVERAGE=1 (set by CI on Linux only) runs the all-features
// tests once under cargo-llvm-cov, writing artifacts/coverage, instead
// of an uninstrumented run followed by a second instrumented build and run.
// Those tests then only run instrumented. Local runs stay uninstrumented.
const coverage =
  coverageRequested(process.env.DIOPTAS_GATE_COVERAGE) &&
  selected.has("--processor");
// DIOPTAS_GATE_CORE_TESTS=0 (set by CI on pull requests) skips the library
// tests of the build without features. They need a second full compile of the
// processor for a few seconds of tests that the all-features run repeats; CI
// runs them on develop, and the build without features is still linted.
const coreTests = gateSwitch(
  "DIOPTAS_GATE_CORE_TESTS",
  process.env.DIOPTAS_GATE_CORE_TESTS,
  true,
);
// DIOPTAS_GATE_PREBUILT=1 (set by CI's UI jobs) takes the processor and the
// test-fixture helper from target/debug as another job built them, instead of
// compiling them here.
const prebuilt = gateSwitch(
  "DIOPTAS_GATE_PREBUILT",
  process.env.DIOPTAS_GATE_PREBUILT,
  false,
);
// DIOPTAS_GATE_UI_KEEP_GOING=1 (set by CI) runs every UI check even after
// one has failed, so that a single run shows all failures.
const keepGoing = gateSwitch(
  "DIOPTAS_GATE_UI_KEEP_GOING",
  process.env.DIOPTAS_GATE_UI_KEEP_GOING,
  false,
);
const shard = uiShard(process.env.DIOPTAS_GATE_UI_SHARD);
const jobs = uiJobs(process.env.DIOPTAS_GATE_UI_JOBS, availableParallelism());
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
    coverage,
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
const stepTimeout = 20 * 60 * 1000;
// Records one finished step; returns the error to throw when it failed.
function finish(name, commandLine, cwd, start, r) {
  const elapsed = (performance.now() - start) / 1000;
  const failed = r.status !== 0 || r.error;
  steps.push({
    name,
    command: commandLine,
    cwd: path.relative(root, cwd) || ".",
    seconds: elapsed,
    status: r.stopped ? "stopped" : failed ? "failed" : "passed",
    exitCode: r.status,
    signal: r.signal,
  });
  const output = `${r.output}${r.error ? `\n${r.error.stack}` : ""}`;
  writeFileSync(path.join(artifacts, `${name}.log`), output);
  if (r.stopped) return undefined;
  if (!failed) {
    console.log(`${name}: passed in ${seconds(elapsed)} s`);
    return undefined;
  }
  process.stderr.write(output.slice(-16000));
  return Error(
    `${name} failed (${r.status ?? r.signal}) after ${seconds(elapsed)} s; see artifacts/ci-native/${name}.log`,
  );
}
function run(name, command, args, cwd = desktop) {
  const commandLine = `${command} ${args.join(" ")}`;
  console.log(`\n[${name}] ${commandLine}`);
  const start = performance.now();
  const r = spawnSync(command, args, {
    cwd,
    env: process.env,
    encoding: "utf8",
    timeout: stepTimeout,
    maxBuffer: 128 * 1024 * 1024,
  });
  const error = finish(name, commandLine, cwd, start, {
    ...r,
    output: `${r.stdout ?? ""}${r.stderr ?? ""}`,
  });
  if (error) {
    report("failed");
    throw error;
  }
}
const node = (name, script, ...args) =>
  run(name, process.execPath, ["scripts/" + script, ...args]);
// The same step without blocking, for checks that run side by side. Each
// child leads its own process group so that stopping it also stops the
// browsers and processors it started.
// After the first failure the checks still running are stopped and reported
// as "stopped" rather than as failures of their own.
const group = process.platform !== "win32";
const active = new Set();
let stopping = false;
function stopActive() {
  stopping = true;
  for (const child of active) stop(child);
}
function stop(child) {
  try {
    if (group) process.kill(-child.pid, "SIGKILL");
    else child.kill("SIGKILL");
  } catch {
    /* Already gone. */
  }
}
// The process groups do not receive the terminal's interrupt themselves.
for (const signal of ["SIGINT", "SIGTERM"])
  process.on(signal, () => {
    stopActive();
    process.exit(1);
  });
function runAsync(name, command, args, env = {}, cwd = desktop) {
  const commandLine = `${command} ${args.join(" ")}`;
  console.log(`[${name}] ${commandLine}`);
  const start = performance.now();
  return new Promise((resolve, reject) => {
    const child = spawn(command, args, {
      cwd,
      env: { ...process.env, ...env },
      detached: group,
      stdio: ["ignore", "pipe", "pipe"],
    });
    active.add(child);
    let output = "";
    child.stdout.on("data", (chunk) => (output += chunk));
    child.stderr.on("data", (chunk) => (output += chunk));
    let failure;
    const timer = setTimeout(() => {
      failure = Error(`${name} timed out`);
      stop(child);
    }, stepTimeout);
    const done = (status, signal, error) => {
      if (!active.delete(child)) return;
      clearTimeout(timer);
      const failed = finish(name, commandLine, cwd, start, {
        status,
        signal,
        error: error ?? failure,
        stopped: stopping,
        output,
      });
      if (!failed) return resolve();
      if (!keepGoing) stopActive();
      reject(failed);
    };
    child.on("error", (error) => done(null, null, error));
    child.on("close", (status, signal) => done(status, signal));
    // A stray grandchild can keep the pipes open after the check has exited.
    child.on("exit", (status, signal) =>
      setTimeout(() => done(status, signal), 2000).unref(),
    );
  });
}
// Every gate checks the shared boundary, including processor-only CI jobs that
// do not install frontend dependencies.
node("glib-security-backport", "check_glib_backport.mjs");
node("native-contract-generation", "generate_native_contracts.mjs", "--check");
if (selected.has("--processor")) {
  run("rust-format", "cargo", [
    "fmt",
    "-p",
    "dioptas-backend",
    "-p",
    "dioptas-contract",
    "--",
    "--check",
  ]);
  // The contract is compiled into both the processor and the host; its own
  // lints and tests run once here.
  run("contract-clippy", "cargo", [
    "clippy",
    "--locked",
    "--manifest-path",
    "contract/Cargo.toml",
    "--all-targets",
    "--",
    "-D",
    "warnings",
  ]);
  run("contract-tests", "cargo", [
    "test",
    "--locked",
    "--manifest-path",
    "contract/Cargo.toml",
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
  if (coreTests)
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
  if (coverage) {
    // cargo-llvm-cov builds into target/llvm-cov-target, so the normal
    // processor staged by rust-build below stays uninstrumented.
    const backend = path.join(desktop, "backend");
    mkdirSync(path.join(desktop, "artifacts/coverage"), { recursive: true });
    run(
      "rust-tests",
      "cargo",
      [
        "llvm-cov",
        "--locked",
        "--all-features",
        "--lcov",
        "--output-path",
        "../artifacts/coverage/lcov.info",
      ],
      backend,
    );
    run(
      "rust-coverage-html",
      "cargo",
      [
        "llvm-cov",
        "report",
        "--html",
        "--output-dir",
        "../artifacts/coverage/html",
      ],
      backend,
    );
  } else
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
  if (prebuilt) {
    const exe = process.platform === "win32" ? ".exe" : "";
    for (const file of [
      `target/debug/dioptas-processor${exe}`,
      `target/debug/examples/test_fixtures${exe}`,
      `target/debug/examples/hdf5_master_fixture${exe}`,
      `target/debug/examples/hdf5_source_fixture${exe}`,
    ])
      if (!existsSync(path.join(root, file)))
        throw Error(`DIOPTAS_GATE_PREBUILT=1 but ${file} is missing`);
  } else
    run("native-test-fixtures", "cargo", [
      "build",
      "--locked",
      "--manifest-path",
      "backend/Cargo.toml",
      "--example",
      "test_fixtures",
    ]);
  // Steps that are not UI checks run once, in the first shard.
  const shared = !shard || shard.index === 1;
  if (shared) {
    node("functional-coverage-map", "functional_coverage.mjs");
    run("frontend-unit", "npm", ["test"]);
  }
  run("frontend-build", "npm", ["run", "build"]);
  // The UI checks run side by side (DIOPTAS_GATE_UI_JOBS at a time; by
  // default half the cores, and one at a time below eight cores). Each entry is a script name,
  // followed by the artifacts folder it writes to when another check writes
  // there too: those two never run at the same moment. Every check gets its
  // own Vite dependency cache (see vite.config.ts), because dev servers that
  // prepare dependencies in one shared folder overwrite each other's files.
  const checks = [
    ["hook_refresh_smoke"],
    ["ui_components"],
    ["app_update_smoke"],
    ["native_backend_smoke"],
    ["native_custom_actions_smoke"],
    ["native_calibration_smoke"],
    ["calibration_validation_click_smoke"],
    ["native_mask_smoke"],
    ["native_integration_workflow_smoke"],
    ["overlay_command_order_smoke"],
    ["phase_editor_workflow_smoke"],
    ["pattern_figure_export_smoke", "pattern-figure-export"],
    ["pattern_figure_save_smoke", "pattern-figure-export"],
    ["pattern_figure_editor_smoke"],
    ["spottiness_smoke"],
    ["batch_waterfall_smoke"],
    ["batch_surface_smoke"],
    ["batch_surface_gpu_smoke"],
    ["batch_surface_guides_smoke"],
    ["batch_surface_axes_smoke"],
    ["batch_export_smoke", "batch-export"],
    ["batch_background_smoke"],
    ["processing_workers_smoke"],
    ["native_corrections_smoke"],
    ["correction_previews_smoke"],
    ["processing_drafts_smoke"],
    ["metadata_products_smoke"],
    ["native_project_smoke"],
    ["session_recovery_smoke"],
    ["dac_thermal_pressure_smoke"],
    ["native_geometry_mask_smoke"],
    ["native_detector_smoke"],
    ["native_lacosmic_smoke"],
    ["native_file_errors_smoke"],
    ["native_map_progress_smoke"],
    ["image_change_smoke", "image-change"],
    ["hdf5_sources_smoke"],
    ["hdf5_master_vds_smoke"],
    ["detector_window_smoke", "detector-window"],
    ["map_detector_independence_smoke"],
    ["detector_source_smoke", "detector-window"],
    ["companion_windows_smoke"],
  ].map(([script, ...locks]) => ({
    name: script,
    args: [`scripts/${script}.mjs`],
    locks,
  }));
  checks.push(
    {
      name: "batch_background_export",
      args: ["scripts/batch_export_smoke.mjs", "--background"],
      locks: ["batch-export"],
    },
    {
      name: "image_change_webkit",
      args: ["scripts/image_change_smoke.mjs", "--webkit"],
      locks: ["image-change"],
    },
  );
  // Seconds each check took on a hosted Linux runner (13.11.2026), used only
  // to give CI's shards equal shares. A check missing here counts as 30.
  const ciSeconds = {
    native_project_smoke: 100,
    phase_editor_workflow_smoke: 74,
    batch_surface_smoke: 68,
    native_integration_workflow_smoke: 60,
    detector_window_smoke: 60,
    hdf5_master_vds_smoke: 60,
    native_map_progress_smoke: 56,
    hdf5_sources_smoke: 50,
    companion_windows_smoke: 49,
    detector_source_smoke: 42,
    ui_components: 41,
    native_calibration_smoke: 37,
    batch_surface_axes_smoke: 31,
    native_file_errors_smoke: 31,
    spottiness_smoke: 30,
    correction_previews_smoke: 30,
    native_geometry_mask_smoke: 27,
    pattern_figure_export_smoke: 24,
    native_backend_smoke: 23,
    processing_drafts_smoke: 22,
    pattern_figure_editor_smoke: 21,
    pattern_figure_save_smoke: 21,
    hook_refresh_smoke: 19,
    batch_export_smoke: 19,
    image_change_webkit: 18,
    batch_waterfall_smoke: 16,
    session_recovery_smoke: 14,
    batch_surface_gpu_smoke: 14,
    dac_thermal_pressure_smoke: 14,
    image_change_smoke: 14,
    map_detector_independence_smoke: 14,
    native_mask_smoke: 13,
    native_lacosmic_smoke: 13,
    batch_background_smoke: 13,
    batch_background_export: 13,
    overlay_command_order_smoke: 12,
    native_custom_actions_smoke: 11,
    native_detector_smoke: 11,
    batch_surface_guides_smoke: 11,
    native_corrections_smoke: 10,
    processing_workers_smoke: 4,
    app_update_smoke: 3,
    metadata_products_smoke: 1,
  };
  // The first shard also runs the frontend unit and transport tests.
  const mine = shardTasks(checks, shard, ciSeconds, 30);
  console.log(
    `\nUI checks: ${mine.length}${shard ? ` of ${checks.length} (shard ${shard.index}/${shard.count})` : ""}, ${jobs} at a time`,
  );
  const failures = [];
  try {
    await runPool(mine, jobs, (check) =>
      runAsync(check.name, process.execPath, check.args, {
        DIOPTAS_VITE_CACHE_DIR: `node_modules/.vite-gate/${check.name}`,
      }).catch((error) => {
        if (!keepGoing) throw error;
        failures.push(error.message);
      }),
    );
    if (failures.length)
      throw Error(
        `${failures.length} UI checks failed:\n${failures.join("\n")}`,
      );
  } catch (error) {
    report("failed");
    throw error;
  }
  if (shared)
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
  run("host-format", "cargo", [
    "fmt",
    "-p",
    "dioptas-desktop",
    "--",
    "--check",
  ]);
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
