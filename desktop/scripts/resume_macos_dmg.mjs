// Resume an existing signed DMG submission; never build, re-sign or submit.
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { createHash } from "node:crypto";
import {
  copyFile,
  mkdir,
  mkdtemp,
  readFile,
  readdir,
  writeFile,
} from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { desktop, releaseConfig, version } from "./release_config.mjs";
import { verifyMacosDmg } from "./verify_macos_dmg.mjs";

const sha256 = async (file) =>
  createHash("sha256")
    .update(await readFile(file))
    .digest("hex");
async function files(directory) {
  const result = [];
  for (const entry of await readdir(directory, { withFileTypes: true })) {
    const file = path.join(directory, entry.name);
    if (entry.isDirectory()) result.push(...(await files(file)));
    else if (entry.isFile()) result.push(file);
  }
  return result;
}
export async function readDmgRecovery(directory, metadata, target) {
  assert.equal(metadata.name, "Native macOS artifacts (no publishing)");
  assert.match(metadata.head_sha, /^[a-f0-9]{40}$/);
  assert(["aarch64-apple-darwin", "x86_64-apple-darwin"].includes(target));
  const inventory = await files(directory);
  const arch = target.startsWith("aarch64") ? "arm64" : "x64";
  const basename = `Dioptas-Desktop_${version}_macos_${arch}.dmg`;
  const images = inventory.filter((file) => path.basename(file) === basename);
  assert.equal(images.length, 1, "Expected exactly one original signed DMG");
  const dmg = images[0];
  const idPath = path.join(
    path.dirname(dmg),
    "dist/notarization",
    `${basename}-submission-id.txt`,
  );
  const submissionId = (await readFile(idPath, "utf8")).trim();
  assert.match(
    submissionId,
    /^[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}$/i,
    "Invalid original submission ID",
  );
  let sourceRevision = metadata.head_sha;
  try {
    const source = JSON.parse(
      await readFile(path.join(path.dirname(dmg), "source.json"), "utf8"),
    );
    assert.equal(source.target, target);
    assert.equal(source.version, version);
    assert.match(source.sourceRevision, /^[a-f0-9]{40}$/);
    sourceRevision = source.sourceRevision;
  } catch (error) {
    if (error.code !== "ENOENT") throw error;
  }
  return {
    dmg,
    submissionId,
    sourceRevision,
    originalRunId: metadata.id,
    originalDmgSha256: await sha256(dmg),
  };
}
const execute = (command, args, options = {}) =>
  execFileSync(command, args, {
    cwd: desktop,
    stdio: "inherit",
    ...options,
  });
export async function finishDmgRecovery({
  recovery,
  output,
  target,
  teamIdentifier,
  packagingRevision,
  sourceDirty,
  run = execute,
  verify = verifyMacosDmg,
}) {
  assert.match(packagingRevision, /^[a-f0-9]{40}$/);
  assert.match(teamIdentifier, /^[A-Z0-9]{10}$/);
  await mkdir(output, { recursive: true });
  const dmg = path.join(output, path.basename(recovery.dmg));
  assert.notEqual(path.resolve(dmg), path.resolve(recovery.dmg));
  await copyFile(recovery.dmg, dmg);
  assert.equal(await sha256(dmg), recovery.originalDmgSha256);
  const source = {
    version,
    target,
    sourceRevision: recovery.sourceRevision,
    packagingRevision,
  };
  await writeFile(
    path.join(output, "source.json"),
    JSON.stringify(source, null, 2) + "\n",
  );
  // The existing helper's --submission-id path skips upload and codesign.
  await run(
    "python3",
    [
      path.resolve(desktop, "../installer/macos/signing.py"),
      "notarize",
      dmg,
      "--submission-id",
      recovery.submissionId,
    ],
    { cwd: output },
  );
  const archive = dmg.replace(/\.dmg$/, ".app.tar.gz");
  const verification = await verify(dmg, {
    teamIdentifier,
    notarized: true,
    nativeSmoke: true,
    archivePath: archive,
  });
  const checksums = [];
  for (const file of [dmg, archive])
    checksums.push(`${await sha256(file)}  ${path.basename(file)}`);
  await writeFile(path.join(output, "SHA256SUMS"), checksums.join("\n") + "\n");
  const report = {
    ...source,
    identifier: releaseConfig.identifier,
    sourceDirty,
    signing: "developer-id",
    teamIdentifier,
    notarized: true,
    published: false,
    recoveredApplication: false,
    recoveredDmg: true,
    originalRunId: recovery.originalRunId,
    originalDmgSha256: recovery.originalDmgSha256,
    notarizationSubmissionId: recovery.submissionId,
    dmg: path.basename(dmg),
    verification,
  };
  await writeFile(
    path.join(output, "build.json"),
    JSON.stringify(report, null, 2) + "\n",
  );
  return report;
}
async function main() {
  assert.equal(process.platform, "darwin");
  const runId = process.env.DIOPTAS_DMG_RESUME_RUN_ID;
  const target = process.env.DIOPTAS_RELEASE_TARGET;
  assert.match(runId || "", /^\d+$/);
  assert.equal(
    target,
    process.arch === "arm64" ? "aarch64-apple-darwin" : "x86_64-apple-darwin",
  );
  assert(process.env.DIOPTAS_SIGNING_KEYCHAIN && process.env.GITHUB_REPOSITORY);
  const capture = (command, args) =>
    execFileSync(command, args, { cwd: desktop, encoding: "utf8" });
  const metadata = JSON.parse(
    capture("gh", [
      "api",
      `repos/${process.env.GITHUB_REPOSITORY}/actions/runs/${runId}`,
    ]),
  );
  const recoveryRoot = path.join(desktop, "artifacts/native-recovery");
  await mkdir(recoveryRoot, { recursive: true });
  const restored = await mkdtemp(
    path.join(recoveryRoot, `${runId}-${target}-dmg-`),
  );
  capture("gh", [
    "run",
    "download",
    runId,
    "--repo",
    process.env.GITHUB_REPOSITORY,
    "--name",
    `Dioptas-native-diagnostics-${target}`,
    "--dir",
    restored,
  ]);
  const recovery = await readDmgRecovery(restored, metadata, target);
  const root = path.join(desktop, "artifacts/native-release");
  await mkdir(root, { recursive: true });
  const output = await mkdtemp(path.join(root, `${version}-${target}-resume-`));
  const report = await finishDmgRecovery({
    recovery,
    output,
    target,
    teamIdentifier: process.env.DIOPTAS_APPLE_TEAM_ID,
    packagingRevision: capture("git", ["rev-parse", "HEAD"]).trim(),
    sourceDirty: !!capture("git", ["status", "--porcelain"]).trim(),
  });
  await writeFile(
    path.join(root, "latest.json"),
    JSON.stringify({ output, ...report }, null, 2) + "\n",
  );
  console.log(
    `Verified original DMG submission ${recovery.submissionId}; app source ${recovery.sourceRevision}; no rebuild, re-signing or upload.`,
  );
}
if (
  process.argv[1] &&
  path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)
)
  await main();
