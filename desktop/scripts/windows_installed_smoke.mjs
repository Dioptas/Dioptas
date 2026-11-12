// Runs on an isolated Windows runner, using only the installed binaries/data.
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import {
  mkdir,
  mkdtemp,
  readFile,
  rename,
  rm,
  writeFile,
} from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { setTimeout as delay } from "node:timers/promises";
import { nativeClient, root } from "./native_backend_client.mjs";
import { inspectWindowsInstall } from "./inspect_windows_install.mjs";

assert.equal(process.platform, "win32");
const installation = path.resolve(process.argv[2]);
const reportPath = path.resolve(process.argv[3]);
const inspection = await inspectWindowsInstall(installation);
const temporary = await mkdtemp(
  path.join(os.tmpdir(), "Dioptas isolated runtime "),
);
const originalRoot = path.resolve(root);
const hiddenRoot = `${originalRoot}.unavailable-${process.pid}`;
const previousDirectory = process.cwd();
let hidden = false,
  native,
  child;
const logs = [];
try {
  // The caller also leaves the checkout before launching this process, so no
  // current-directory handle prevents temporarily hiding the build-time path.
  process.chdir(temporary);
  await rename(originalRoot, hiddenRoot);
  hidden = true;
  native = nativeClient({
    executable: path.join(installation, "dioptas-processor.exe"),
    args: [],
    cwd: temporary,
  });
  const call = async (action, payload = {}) => {
    const result = await native.invoke(action, payload);
    assert.equal(result.ok, true, `${action}: ${result.error}`);
    return result;
  };
  assert.equal((await call("__host__")).runtime, "rust");
  await call("example");
  await call("open_calibration", {
    path: path.join(installation, "dioptas/examples/CeO2_Pilatus1M.poni"),
  });
  await call("integration_settings", {
    bins: 128,
    cake_bins: 24,
    poisson_errors: true,
  });
  for (const kind of ["cylinder", "sphere"]) {
    const corrected = await call("integration_correction", {
      kind,
      enabled: true,
      parameters: { radius: 0.2, beam_width: 0.12 },
      material: { mode: "formula", formula: "SiO2", density: 2.2 },
    });
    assert(corrected.pattern.y.every(Number.isFinite));
    assert(corrected.pattern.sigma.some((v) => v > 0));
  }
  await call("configuration", { operation: "duplicate" });
  const combined = await call("combination_settings", {
    patterns: true,
    cakes: true,
  });
  assert.equal(combined.pattern.y.length, 128);
  assert.equal(combined.cake.height, 24);
  const project = path.join(temporary, "portable.dio");
  await call("save_project", { path: project });
  const restored = await call("open_project", { path: project });
  assert.equal(restored.state.configurationCount, 2);
  assert.deepEqual(restored.pattern, combined.pattern);
  await call("save_combined_pattern", {
    path: path.join(temporary, "portable.xy"),
  });
  await native.close();
  native = undefined;

  const uiOutput = path.join(temporary, "ui");
  await mkdir(uiOutput);
  const env = { ...process.env };
  for (const key of Object.keys(env))
    if (
      /^(path|pythonpath|pythonhome|hdf5_plugin_path|dioptas_native_processor|dioptas_backend)$/i.test(
        key,
      )
    )
      delete env[key];
  Object.assign(env, {
    PATH: path.join(process.env.SystemRoot, "System32"),
    DIOPTAS_PYTHON: "C:\\nonexistent\\python.exe",
    DIOPTAS_SOURCE_ROOT: "C:\\nonexistent\\checkout",
    HDF5_PLUGIN_PRELOAD: "::",
    DIOPTAS_STANDALONE_TEST_DIRECTORY: uiOutput,
  });
  child = spawn(
    path.join(installation, "dioptas-desktop.exe"),
    ["--example", "--standalone-smoke"],
    {
      cwd: temporary,
      env,
      windowsHide: true,
      stdio: ["ignore", "pipe", "pipe"],
    },
  );
  child.stdout.on("data", (b) => logs.push(b.toString()));
  child.stderr.on("data", (b) => logs.push(b.toString()));
  const timer = setTimeout(() => child.kill(), 180_000);
  let code;
  try {
    code = await new Promise((resolve, reject) => {
      child.on("error", reject);
      child.on("close", resolve);
    });
  } finally {
    clearTimeout(timer);
  }
  const reports = logs
    .join("")
    .split(/\r?\n/)
    .filter((l) => l.startsWith('{"tauriSmoke":'))
    .map((l) => JSON.parse(l).tauriSmoke);
  const ui = reports.findLast((r) => r.standalone);
  assert.equal(code, 0, logs.join(""));
  assert.equal(ui?.ok, true, ui?.error || logs.join(""));
  let processingReaped = false;
  for (let i = 0; i < 50; i++) {
    try {
      process.kill(ui.processingPid, 0);
      await delay(100);
    } catch (error) {
      if (error.code === "ESRCH") {
        processingReaped = true;
        break;
      }
      throw error;
    }
  }
  assert(processingReaped, "Processor survived application exit");
  assert((await readFile(path.join(uiOutput, "standalone.dio"))).length > 1000);
  assert((await readFile(path.join(uiOutput, "standalone.xy"))).length > 100);
  await writeFile(
    reportPath,
    JSON.stringify(
      {
        ok: true,
        sourceCheckoutAtBuildPathUnavailable: true,
        developerPathUnavailable: true,
        headlessProcessor: true,
        projectRoundtrip: true,
        combinedPatternAndCake: true,
        countingStd: true,
        nativeWebView2: ui,
        processingReaped,
        inspection,
      },
      null,
      2,
    ),
  );
} finally {
  await native?.close();
  if (child && child.exitCode === null) child.kill();
  if (hidden) await rename(hiddenRoot, originalRoot);
  process.chdir(previousDirectory);
  await writeFile(`${reportPath}.log`, logs.join(""));
  await rm(temporary, { recursive: true, force: true });
}
