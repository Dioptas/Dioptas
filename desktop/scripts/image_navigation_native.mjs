import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { createInterface } from "node:readline";
import { cp, mkdir, stat, writeFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import path from "node:path";
import { nativeTestProfile } from "./native_test_profile.mjs";
import { prepareNativeCapture } from "./native_capture.mjs";

const desktop = fileURLToPath(new URL("../", import.meta.url));
const args = process.argv.slice(2);
const value = (name, fallback) => {
  const i = args.indexOf(name);
  return i < 0 ? fallback : args[i + 1];
};
const eiger = value("--eiger", null);
const output = value(
  "--output",
  path.join(desktop, "artifacts/native-navigation"),
);
const outputDirectory = path.resolve(output);
await mkdir(outputDirectory, { recursive: true });
const profile = await nativeTestProfile("navigation-timing");
if (!args.includes("--foreground"))
  profile.config.app.windows = profile.config.app.windows.map((window) => ({
    ...window,
    focus: false,
    alwaysOnTop: args.includes("--keep-visible"),
  }));
profile.config.build = { beforeBuildCommand: null };
const configFile = path.join(outputDirectory, "config.json");
await writeFile(configFile, JSON.stringify(profile.config));
const run = (command, args, env = process.env) =>
  new Promise((resolve, reject) => {
    const child = spawn(command, args, { cwd: desktop, stdio: "inherit", env });
    child.on("error", reject);
    child.on("exit", (code) =>
      code === 0 ? resolve() : reject(Error(`${command} exited ${code}`)),
    );
  });
if (!args.includes("--no-build")) {
  await run("npm", ["run", "build"], {
    ...process.env,
    VITE_DIOPTAS_NAVIGATION_BENCHMARK: "1",
  });
  await run("npx", ["tauri", "build", "--debug", "--config", configFile]);
}
const capture = await prepareNativeCapture(
  path.join(outputDirectory, "captures"),
);
const foreground = args.includes("--foreground");
const config = {
  root: path.resolve(desktop, ".."),
  foreground,
  series: args.includes("--series"),
  seriesExtra: args.includes("--series-extra"),
  seriesMethod: value("--series-method", null),
  ...(eiger && (await stat(eiger).catch(() => null)) ? { eiger } : {}),
};
let executable = value("--app", "src-tauri/target/debug/dioptas-desktop");
if (process.platform === "darwin" && !args.includes("--app")) {
  // A distinct bundle path prevents Launch Services from reusing a previous
  // benchmark build's registration when this window needs to be raised.
  const bundle = path.join(
    profile.directory,
    "Dioptas Navigation Benchmark.app",
  );
  await cp(
    path.join(
      desktop,
      "src-tauri/target/debug/bundle/macos/Dioptas Desktop.app",
    ),
    bundle,
    { recursive: true },
  );
  executable = path.join(bundle, "Contents/MacOS/dioptas-desktop");
  console.log(`Private benchmark bundle: ${bundle}`);
}
const child = spawn(executable, ["--backend=rust", "--navigation-benchmark"], {
  cwd: desktop,
  stdio: ["ignore", "pipe", "pipe"],
  env: {
    ...profile.env,
    DIOPTAS_NATIVE_PROCESSOR: path.join(
      desktop,
      "backend/target/debug/dioptas-processor",
    ),
    DIOPTAS_NAVIGATION_BENCHMARK: JSON.stringify(config),
    DIOPTAS_TRACE_FRAME: "1",
    DIOPTAS_TRACE_NATIVE_NAV: "1",
    DIOPTAS_DEV_RELOAD: "0",
  },
});
const logs = [],
  native = [],
  backend = [],
  captures = [],
  traceErrors = [];
const parseTrace = (line, prefix, target) => {
  try {
    target.push(JSON.parse(line.slice(prefix.length)));
  } catch (error) {
    traceErrors.push({ error: String(error), line });
  }
};
let final,
  processingPid,
  capturing = Promise.resolve();
const stopTest = () => {
  if (child.exitCode === null) child.kill("SIGTERM");
  if (processingPid) {
    try {
      process.kill(processingPid, "SIGTERM");
    } catch {}
  }
};
const watchdog = setTimeout(stopTest, 600000);
console.log(
  `Isolated native benchmark PID ${child.pid}; foreground samples wait for its window to be visible and focused.`,
);
for (const stream of [child.stdout, child.stderr])
  createInterface({ input: stream }).on("line", (line) => {
    logs.push(line);
    if (line.startsWith("DIOPTAS_NATIVE_TRACE "))
      parseTrace(line, "DIOPTAS_NATIVE_TRACE ", native);
    else if (line.startsWith("DIOPTAS_TRACE "))
      parseTrace(line, "DIOPTAS_TRACE ", backend);
    else if (line.startsWith('{"tauriSmoke":')) {
      const report = JSON.parse(line).tauriSmoke;
      if (report.processingPid && !processingPid) {
        processingPid = report.processingPid;
      }
      if (report.navigationProgress)
        console.log(JSON.stringify(report.navigationProgress));
      else if (report.stage === "diagnostic" && report.capture && capture)
        capturing = capturing.then(async () => {
          try {
            captures.push(await capture(child.pid, "main", report.capture));
          } catch (error) {
            captures.push({ error: String(error) });
          }
        });
      else if (!["diagnostic", "hmr"].includes(report.stage)) final = report;
    } else console.log(line);
  });
try {
  const code = await new Promise((resolve, reject) => {
    child.on("error", reject);
    child.on("close", resolve);
  });
  await capturing;
  if (final?.reports)
    for (const row of final.reports) {
      row.native = native.filter((trace) => trace.id === row.requestId);
      row.backendPacket = backend.filter(
        (trace) => trace.stage === "packet" && trace.id === row.requestId,
      );
    }
  final = {
    ...(final ?? { ok: false, error: `No native report (exit ${code})` }),
    sourcePid: child.pid,
    testProfile: profile.directory,
    captures,
    traceErrors,
    foregroundRequested: foreground,
    transport: "Tauri-owned stdio",
    nativeTraces: native,
    backendTraces: backend,
  };
  await writeFile(
    path.join(outputDirectory, "receipt.json"),
    JSON.stringify(final, null, 2) + "\n",
  );
  assert.equal(code, 0);
  assert.equal(final.ok, true, final.error);
  assert.deepEqual(traceErrors, []);
  assert.throws(
    () => process.kill(processingPid, 0),
    { code: "ESRCH" },
    "Test processing child survived its window",
  );
  console.log(JSON.stringify(final.summaries, null, 2));
} finally {
  clearTimeout(watchdog);
  stopTest();
  await writeFile(
    path.join(outputDirectory, "run.log"),
    logs.join("\n") + "\n",
  );
}
