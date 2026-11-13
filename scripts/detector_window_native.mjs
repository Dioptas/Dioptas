import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { mkdir, writeFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { nativeTestProfile } from "./native_test_profile.mjs";
const desktop = fileURLToPath(new URL("../", import.meta.url));
const profile = await nativeTestProfile("detector-window");
const permissions = [
  "core:window:allow-outer-position",
  "core:window:allow-set-position",
  "core:window:allow-set-size",
  "core:window:allow-inner-size",
  "core:window:allow-scale-factor",
  "core:window:allow-is-visible",
  "core:window:allow-minimize",
  "core:window:allow-close",
];
profile.config.app.security.capabilities.push({
  identifier: "detector-window-native-test",
  windows: ["detector-window"],
  permissions,
});
profile.env.DIOPTAS_DETECTOR_WINDOW_STATE =
  profile.directory + "/detector-window.json";
const config = profile.directory + "/config.json";
await writeFile(config, JSON.stringify(profile.config));
await new Promise((resolve, reject) => {
  const p = spawn(
    "npm",
    ["run", "tauri:build", "--", "--debug", "--config", config],
    { cwd: desktop, stdio: "inherit" },
  );
  p.on("error", reject);
  p.on("exit", (c) =>
    c === 0 ? resolve() : reject(Error("Build failed: " + c)),
  );
});
const child = spawn(
  "target/debug/dioptas-desktop",
  ["--backend=rust", "--smoke", "--example", "--detector-smoke"],
  { cwd: desktop, env: profile.env, stdio: ["ignore", "pipe", "pipe"] },
);
let output = "";
for (const s of [child.stdout, child.stderr])
  s.on("data", (b) => {
    output += b;
    process.stdout.write(b);
  });
const code = await new Promise((resolve, reject) => {
  child.on("error", reject);
  child.on("close", resolve);
});
const report = output
  .split("\n")
  .filter((l) => l.startsWith('{"tauriSmoke":'))
  .map((l) => JSON.parse(l).tauriSmoke)
  .findLast((r) => r.stage === "detector");
assert.equal(code, 0, report?.error || output);
assert.equal(report?.ok, true, report?.error || "No detector test report");
assert.throws(() => process.kill(report.processingPid, 0), { code: "ESRCH" });
report.processingReaped = true;
report.profile = profile.directory;
await mkdir(desktop + "artifacts/detector-window", { recursive: true });
await writeFile(
  desktop + "artifacts/detector-window/native-results.json",
  JSON.stringify(report, null, 2) + "\n",
);
