// The same native gates are used locally and by CI. Python is only an optional
// independent oracle; it is never installed by the processor or UI gates.
import { spawnSync } from "node:child_process";
import { mkdirSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";

const root = fileURLToPath(new URL("../../", import.meta.url));
const desktop = path.join(root, "desktop");
const flags = process.argv.slice(2);
const allowed = ["--processor", "--ui", "--references", "--host"];
if (flags.some((f) => !allowed.includes(f)))
  throw Error(`Use ${allowed.join(", ")}`);
const selected = new Set(flags.length ? flags : ["--processor", "--ui"]);
const artifacts = path.join(desktop, "artifacts/ci-native");
mkdirSync(artifacts, { recursive: true });
function run(name, command, args, cwd = desktop) {
  console.log(`\n[${name}] ${command} ${args.join(" ")}`);
  const r = spawnSync(command, args, {
    cwd,
    env: process.env,
    encoding: "utf8",
    timeout: 20 * 60 * 1000,
    maxBuffer: 128 * 1024 * 1024,
  });
  const output = `${r.stdout ?? ""}${r.stderr ?? ""}${r.error ? `\n${r.error.stack}` : ""}`;
  writeFileSync(path.join(artifacts, `${name}.log`), output);
  if (r.status !== 0 || r.error) {
    process.stderr.write(output.slice(-16000));
    throw Error(
      `${name} failed (${r.status ?? r.signal}); see desktop/artifacts/ci-native/${name}.log`,
    );
  }
  console.log(`${name}: passed`);
}
const node = (name, script, ...args) =>
  run(name, process.execPath, ["scripts/" + script, ...args]);
if (selected.has("--processor")) {
  run("rust-format", "cargo", [
    "fmt",
    "--manifest-path",
    "backend/Cargo.toml",
    "--",
    "--check",
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
  node("functional-coverage-map", "functional_coverage.mjs");
  run("frontend-unit", "npm", ["test"]);
  run("frontend-build", "npm", ["run", "build"]);
  for (const script of [
    "ui_components",
    "native_backend_smoke",
    "native_calibration_smoke",
    "native_mask_smoke",
    "native_integration_workflow_smoke",
    "native_project_smoke",
    "native_geometry_mask_smoke",
    "native_detector_smoke",
    "native_lacosmic_smoke",
    "native_file_errors_smoke",
    "image_change_smoke",
  ])
    node(script, `${script}.mjs`);
  node("image_change_webkit", "image_change_smoke.mjs", "--webkit");
  run("native-transport", process.execPath, [
    "--test",
    "scripts/native_calibration_transport.test.mjs",
    "scripts/native_mask_transport.test.mjs",
    "scripts/native_geometry_mask_transport.test.mjs",
    "scripts/native_lacosmic_transport.test.mjs",
  ]);
}
if (selected.has("--references")) {
  const python = process.env.DIOPTAS_REFERENCE_PYTHON;
  if (!python)
    throw Error(
      "Set DIOPTAS_REFERENCE_PYTHON to the independent reference interpreter.",
    );
  for (const name of [
    "backend",
    "autolevel",
    "calibration",
    "mask",
    "integration_core",
    "processing",
    "series",
    "phase",
    "io_history",
    "project",
    "geometry_mask",
    "detector",
    "lacosmic",
  ])
    run(
      `reference-${name}`,
      python,
      [`desktop/scripts/native_${name}_parity.py`],
      root,
    );
  run("native-fixture-transport", process.execPath, [
    "--test",
    "scripts/native_integration_transport.test.mjs",
    "scripts/native_project_transport.test.mjs",
  ]);
  node("native_map_progress", "native_map_progress_smoke.mjs");
}
if (selected.has("--host")) {
  run("host-prepare", "npm", ["run", "backend:prepare", "--", "--debug"]);
  run("host-frontend", "npm", ["run", "build"]);
  run("host-tests", "cargo", [
    "test",
    "--locked",
    "--manifest-path",
    "src-tauri/Cargo.toml",
  ]);
}
