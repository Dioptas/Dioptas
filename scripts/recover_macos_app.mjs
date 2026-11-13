// Restore a previously signed candidate; release_macos verifies the signature,
// architecture and Apple's existing ticket before creating a new DMG.
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { appendFile, mkdtemp, mkdir, readdir } from "node:fs/promises";
import path from "node:path";
import { desktop, releaseConfig } from "./release_config.mjs";

const runId = process.env.DIOPTAS_RECOVERY_RUN_ID;
const target = process.env.DIOPTAS_RELEASE_TARGET;
assert.match(runId || "", /^\d+$/, "Provide a numeric Actions run ID");
assert(["aarch64-apple-darwin", "x86_64-apple-darwin"].includes(target));
assert(
  process.env.GITHUB_ENV && process.env.GITHUB_REPOSITORY,
  "Run recovery inside GitHub Actions",
);
const run = (command, args) =>
  execFileSync(command, args, {
    cwd: desktop,
    encoding: "utf8",
    stdio: ["ignore", "pipe", "pipe"],
  });
const metadata = JSON.parse(
  run("gh", [
    "api",
    `repos/${process.env.GITHUB_REPOSITORY}/actions/runs/${runId}`,
  ]),
);
assert.equal(
  metadata.name,
  "Native macOS artifacts (no publishing)",
  "Choose an original native candidate run",
);
assert.match(metadata.head_sha, /^[a-f0-9]{40}$/);
const root = path.join(desktop, "artifacts/native-recovery");
await mkdir(root, { recursive: true });
const output = await mkdtemp(path.join(root, `${runId}-${target}-`));
run("gh", [
  "run",
  "download",
  runId,
  "--repo",
  process.env.GITHUB_REPOSITORY,
  "--name",
  `Dioptas-native-diagnostics-${target}`,
  "--dir",
  output,
]);
const archives = [];
async function find(directory) {
  for (const entry of await readdir(directory, { withFileTypes: true })) {
    const file = path.join(directory, entry.name);
    if (entry.isDirectory()) await find(file);
    else if (entry.name === "Dioptas-signed-unnotarized.zip")
      archives.push(file);
  }
}
await find(output);
assert.equal(
  archives.length,
  1,
  "Expected exactly one original signed app ZIP",
);
const restored = path.join(output, "restored");
run("ditto", ["-x", "-k", archives[0], restored]);
await appendFile(
  process.env.GITHUB_ENV,
  `DIOPTAS_RECOVERED_APP=${path.join(restored, `${releaseConfig.productName}.app`)}\nDIOPTAS_APP_SOURCE_REVISION=${metadata.head_sha}\n`,
);
console.log(
  `Restored ${target} app from candidate ${runId} (${metadata.head_sha}).`,
);
