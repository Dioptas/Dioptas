import { spawn } from "node:child_process";
import { nativeTestProfile } from "./native_test_profile.mjs";
import { mkdir, writeFile } from "node:fs/promises";
import { createInterface } from "node:readline";
import { fileURLToPath } from "node:url";
import assert from "node:assert/strict";
const desktop = fileURLToPath(new URL("../", import.meta.url));
const artifacts = new URL("../artifacts/", import.meta.url);
await mkdir(artifacts, { recursive: true });
const config = new URL("batch-layout-config.json", artifacts);
const profile = await nativeTestProfile("batch-layout");
await writeFile(
  config,
  JSON.stringify({
    ...profile.config,
    productName: "Dioptas Batch Layout Check",
    app: {
      ...profile.config.app,
      security: {
        capabilities: [
          "desktop",
          "calibration-tooltip",
          "phase-editor",
          "map-window",
          "batch-window",
          {
            identifier: "batch-layout-check",
            windows: ["main", "batch-window"],
            permissions: [
              "core:window:allow-minimize",
              "core:window:allow-is-minimized",
              "core:window:allow-set-focus",
              "core:window:allow-is-focused",
              "core:window:allow-get-all-windows",
              "core:window:allow-set-size",
              "core:window:allow-set-position",
              "core:window:allow-inner-size",
              "core:window:allow-outer-position",
              "core:window:allow-scale-factor",
            ],
          },
        ],
      },
    },
  }),
);
await new Promise((resolve, reject) => {
  const p = spawn(
    "npx",
    [
      "tauri",
      "build",
      "--debug",
      "--bundles",
      "app",
      "--config",
      fileURLToPath(config),
    ],
    { cwd: desktop, stdio: "inherit" },
  );
  p.on("error", reject);
  p.on("exit", (code) =>
    code === 0 ? resolve() : reject(Error(`Build exited ${code}`)),
  );
});
const reports = [];
for (const stage of ["seed", "floating", "closed", "docked"]) {
  let report;
  const p = spawn(
    "src-tauri/target/debug/bundle/macos/Dioptas Batch Layout Check.app/Contents/MacOS/dioptas-desktop",
    ["--smoke", "--batch-smoke"],
    {
      cwd: desktop,
      env: { ...profile.env, DIOPTAS_BATCH_LAYOUT_STAGE: stage },
      stdio: ["ignore", "pipe", "pipe"],
    },
  );
  for (const stream of [p.stdout, p.stderr])
    createInterface({ input: stream }).on("line", (line) => {
      if (line.startsWith('{"tauriSmoke":')) {
        const value = JSON.parse(line).tauriSmoke;
        if (value.stage !== "diagnostic") report = value;
      }
      console.log(line);
    });
  const code = await new Promise((resolve, reject) => {
    p.on("error", reject);
    p.on("close", resolve);
  });
  assert.equal(
    code,
    0,
    report?.error ?? `Native ${stage} check exited without a report`,
  );
  assert.equal(
    report?.ok,
    true,
    report?.error ?? `Native ${stage} report missing`,
  );
  assert.throws(() => process.kill(report.processingPid, 0), { code: "ESRCH" });
  reports.push({ ...report, processingReaped: true });
}
assert.deepEqual(
  reports[1].placement,
  reports[0].placement,
  "Batch native bounds did not survive an application restart",
);
await writeFile(
  new URL("tauri-batch-layout.json", artifacts),
  JSON.stringify({ ok: true, reports }, null, 2),
);
console.log("Native Batch layout restart checks passed");
