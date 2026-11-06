import assert from "node:assert/strict";
import { nativeTestProfile } from "./native_test_profile.mjs";
import { prepareNativeCapture } from "./native_capture.mjs";
import { spawn } from "node:child_process";
import { mkdir, writeFile, unlink } from "node:fs/promises";
import { createInterface } from "node:readline";
import { fileURLToPath } from "node:url";

const desktop = fileURLToPath(new URL("../", import.meta.url));
const live = process.argv.includes("--live");
const batchSmoke = process.argv.includes("--batch");
const mapSmoke = process.argv.includes("--map");
if (live && (mapSmoke || batchSmoke))
  throw Error(
    "Map/Batch native smoke uses bundled assets; run with --map only.",
  );
const artifacts = new URL("../artifacts/", import.meta.url);
const probe = new URL("../src/__dioptas_live_check_tauri.css", import.meta.url);
await mkdir(artifacts, { recursive: true });
const run = (command, args) =>
  new Promise((resolve, reject) => {
    const child = spawn(command, args, { cwd: desktop, stdio: "inherit" });
    child.on("error", reject);
    child.on("exit", (code) =>
      code === 0 ? resolve() : reject(Error(`${command} exited with ${code}`)),
    );
  });
const profile = !live
  ? await nativeTestProfile(
      batchSmoke ? "batch-smoke" : mapSmoke ? "map-smoke" : "workflow-smoke",
    )
  : null;
if (!live) {
  const buildArgs = ["run", "tauri:build", "--", "--debug"];
  const config = new URL("native-smoke-config.json", artifacts);
  await writeFile(config, JSON.stringify(profile.config));
  buildArgs.push("--config", fileURLToPath(config));
  await run("npm", buildArgs);
} else await writeFile(probe, ":root { --dioptas-tauri-hmr: before; }\n");

const capture = !live
  ? await prepareNativeCapture(
      fileURLToPath(
        new URL(
          `native-${batchSmoke ? "batch" : mapSmoke ? "map" : "workflow"}/`,
          artifacts,
        ),
      ),
    )
  : null;
const captures = [];
let capturing = Promise.resolve();
const child = spawn(
  live ? "npm" : "src-tauri/target/debug/dioptas-desktop",
  live
    ? ["run", "tauri:dev", "--", "--", "--", "--example", "--smoke"]
    : [
        "--example",
        "--smoke",
        ...(mapSmoke ? ["--map-smoke"] : batchSmoke ? ["--batch-smoke"] : []),
      ],
  {
    cwd: desktop,
    env: profile?.env ?? process.env,
    stdio: ["ignore", "pipe", "pipe"],
  },
);
const logs = [];
let report;
let probeUpdate = Promise.resolve();
const read = (stream) =>
  createInterface({ input: stream }).on("line", (line) => {
    logs.push(line);
    console.log(line);
    if (!line.startsWith('{"tauriSmoke":')) return;
    const result = JSON.parse(line).tauriSmoke;
    if (result.stage === "diagnostic") {
      const request = result.diagnostics;
      if (request?.capture && capture)
        capturing = capturing.then(async () => {
          try {
            captures.push({
              window: request.window,
              path: await capture(child.pid, request.window, request.capture),
            });
          } catch (error) {
            captures.push({ window: request.window, error: String(error) });
          }
        });
      return;
    }
    if (result.stage === "hmr") {
      probeUpdate = writeFile(probe, ":root { --dioptas-tauri-hmr: after; }\n");
    } else report = result;
  });
read(child.stdout);
read(child.stderr);
try {
  const code = await new Promise((resolve, reject) => {
    child.on("error", reject);
    child.on("close", resolve);
  });
  await probeUpdate;
  await capturing;
  assert.equal(code, 0);
  assert.equal(
    report?.ok,
    true,
    report?.error ?? "No native smoke report received",
  );
  if (!mapSmoke && !batchSmoke) assert.equal(report.hotReloadVerified, live);
  assert.throws(
    () => process.kill(report.processingPid, 0),
    { code: "ESRCH" },
    "Processing child survived the native window",
  );
  report.processingReaped = true;
  report.nativeCaptures = captures;
  report.testProfile = profile?.directory;
  await writeFile(
    new URL(
      batchSmoke
        ? "tauri-batch-smoke.json"
        : mapSmoke
          ? "tauri-map-smoke.json"
          : live
            ? "tauri-live-smoke.json"
            : "tauri-native-smoke.json",
      artifacts,
    ),
    JSON.stringify(report, null, 2) + "\n",
  );
} finally {
  await writeFile(
    new URL(
      batchSmoke
        ? "tauri-batch-smoke.log"
        : mapSmoke
          ? "tauri-map-smoke.log"
          : live
            ? "tauri-live-smoke.log"
            : "tauri-native-smoke.log",
      artifacts,
    ),
    logs.join("\n") + "\n",
  );
  if (live) await unlink(probe).catch(() => {});
}
