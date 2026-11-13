import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { mkdtemp, writeFile, rm, mkdir } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const desktop = fileURLToPath(new URL("../", import.meta.url));
const temporary = await mkdtemp(
  path.join(os.tmpdir(), "dioptas-tooltip-smoke-"),
);
const config = path.join(temporary, "tauri.json");
// Only this disposable test build can inspect/reposition native windows.
await writeFile(
  config,
  JSON.stringify({
    app: {
      security: {
        capabilities: [
          "desktop",
          "calibration-tooltip",
          {
            identifier: "tooltip-smoke",
            windows: ["main"],
            permissions: [
              "core:window:allow-current-monitor",
              "core:window:allow-set-position",
              "core:window:allow-set-size",
              "core:window:allow-inner-position",
              "core:window:allow-inner-size",
              "core:window:allow-outer-position",
              "core:window:allow-outer-size",
              "core:window:allow-is-visible",
              "core:window:allow-is-focused",
              "core:window:allow-set-focus",
            ],
          },
        ],
      },
    },
  }),
);
const run = (command, args, capture = false) =>
  new Promise((resolve, reject) => {
    const child = spawn(command, args, {
      cwd: desktop,
      stdio: capture ? ["ignore", "pipe", "pipe"] : "inherit",
    });
    let output = "";
    if (capture)
      for (const stream of [child.stdout, child.stderr])
        stream.on("data", (data) => {
          output += data;
          process.stdout.write(data);
        });
    child.on("error", reject);
    child.on("close", (code) =>
      code === 0
        ? resolve(output)
        : reject(Error(`${command} exited with ${code}\n${output}`)),
    );
  });
try {
  await run("npm", ["run", "tauri:build", "--", "--debug", "--config", config]);
  const output = await run(
    "target/debug/dioptas-desktop",
    ["--example", "--tooltip-smoke"],
    true,
  );
  const report = output
    .split("\n")
    .filter((line) => line.startsWith('{"tauriSmoke":'))
    .map((line) => JSON.parse(line).tauriSmoke)
    .find((value) => typeof value.ok === "boolean");
  assert.equal(report?.ok, true, "No successful native tooltip report");
  assert.equal(report.helpButtons, 4);
  await mkdir(path.join(desktop, "artifacts"), { recursive: true });
  await writeFile(
    path.join(desktop, "artifacts/calibration-tooltip-native-smoke.json"),
    JSON.stringify(report, null, 2) + "\n",
  );
} finally {
  await rm(temporary, { recursive: true, force: true });
  // Leave the normal executable without the test-only window permissions.
  await run("npm", ["run", "tauri:build", "--", "--debug"]);
}
