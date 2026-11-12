// Artifact-only native packaging: no tags, releases, uploads or publishing.
import assert from "node:assert/strict";
import { execFileSync, spawn } from "node:child_process";
import { createHash } from "node:crypto";
import {
  mkdir,
  mkdtemp,
  readFile,
  rm,
  symlink,
  writeFile,
} from "node:fs/promises";
import path from "node:path";
import { parseArgs } from "node:util";
import { hdiutil } from "./hdiutil.mjs";
import {
  desktop,
  releaseConfig,
  version,
  buildEnvironment,
} from "./release_config.mjs";
import { inspectStandalone } from "./inspect_standalone.mjs";
import { verifyMacosDmg } from "./verify_macos_dmg.mjs";

assert.equal(process.platform, "darwin", "Build macOS artifacts on macOS");
const { values } = parseArgs({
  options: {
    "ad-hoc": { type: "boolean" },
    notarize: { type: "boolean" },
    "native-smoke": { type: "boolean" },
    "from-app": { type: "string" },
  },
});
const adHoc = !!values["ad-hoc"];
const notarized = !!values.notarize;
const recoveredApplication =
  values["from-app"] && path.resolve(values["from-app"]);
assert(
  !recoveredApplication || notarized,
  "Recovered apps require notarized candidate verification",
);
assert(!(adHoc && notarized), "Ad-hoc artifacts cannot be notarized");
assert(
  !(adHoc && values["native-smoke"]),
  "The release WebKit check requires Developer ID signing",
);
const identity = adHoc
  ? "-"
  : process.env.DIOPTAS_CODESIGN_IDENTITY || process.env.APPLE_SIGNING_IDENTITY;
assert(
  identity && (adHoc || identity !== "-"),
  "Set DIOPTAS_CODESIGN_IDENTITY to a Developer ID Application identity, or explicitly use --ad-hoc",
);
const teamIdentifier = adHoc ? undefined : process.env.DIOPTAS_APPLE_TEAM_ID;
assert(
  adHoc || /^[A-Z0-9]{10}$/.test(teamIdentifier || ""),
  "Set DIOPTAS_APPLE_TEAM_ID to the signing certificate's team",
);
assert(
  !notarized || process.env.DIOPTAS_SIGNING_KEYCHAIN,
  "Notarization requires the credential keychain from installer/macos/signing.py setup",
);

const capture = (command, args) =>
  execFileSync(command, args, { cwd: desktop, encoding: "utf8" }).trim();
async function run(command, args, options = {}) {
  await new Promise((resolve, reject) => {
    const child = spawn(command, args, {
      cwd: desktop,
      stdio: "inherit",
      ...options,
    });
    child.on("error", reject);
    child.on("close", (code) =>
      code === 0
        ? resolve()
        : reject(Error(`${path.basename(command)} failed (exit ${code})`)),
    );
  });
}
const target = capture("rustc", ["-vV"]).match(/^host: (.+)$/m)?.[1];
assert(
  ["aarch64-apple-darwin", "x86_64-apple-darwin"].includes(target),
  "Unsupported macOS target",
);
if (process.env.DIOPTAS_RELEASE_TARGET)
  assert.equal(
    target,
    process.env.DIOPTAS_RELEASE_TARGET,
    "Use a native runner for the requested architecture",
  );
const artifacts = path.join(desktop, "artifacts/native-release");
await mkdir(artifacts, { recursive: true });
const output = await mkdtemp(path.join(artifacts, `${version}-${target}-`));
const packagingRevision = capture("git", ["rev-parse", "HEAD"]);
const sourceRevision = recoveredApplication
  ? process.env.DIOPTAS_APP_SOURCE_REVISION
  : packagingRevision;
assert.match(
  sourceRevision || "",
  /^[a-f0-9]{40}$/,
  "Record the recovered application's source revision",
);
const sourceDirty = capture("git", ["status", "--porcelain"]).length > 0;
await writeFile(
  path.join(output, "source.json"),
  JSON.stringify(
    { version, target, sourceRevision, packagingRevision },
    null,
    2,
  ) + "\n",
);
console.log(`Preparing ${version} (${target}); artifacts: ${output}`);
if (!recoveredApplication)
  await run(
    process.execPath,
    [
      "node_modules/@tauri-apps/cli/tauri.js",
      "build",
      "--config",
      "src-tauri/tauri.release.conf.json",
      "--bundles",
      "app",
      "--",
      "--locked",
    ],
    {
      env: buildEnvironment(process.env, identity),
    },
  );
const metadata = JSON.parse(
  capture("cargo", [
    "metadata",
    "--locked",
    "--no-deps",
    "--format-version",
    "1",
    "--manifest-path",
    "src-tauri/Cargo.toml",
  ]),
);
const application =
  recoveredApplication ||
  path.join(
    metadata.target_directory,
    "release/bundle/macos",
    `${releaseConfig.productName}.app`,
  );
await inspectStandalone(application, { teamIdentifier });
await run(process.execPath, [
  "scripts/standalone_processor_smoke.mjs",
  application,
]);
const notary = async (file) =>
  run(
    "python3",
    [path.resolve(desktop, "../installer/macos/signing.py"), "notarize", file],
    { cwd: output },
  );
if (recoveredApplication) {
  // Fetch the existing Apple ticket; never re-sign or re-submit an accepted app.
  await run("xcrun", ["stapler", "staple", application]);
  await run("xcrun", ["stapler", "validate", application]);
  await run("spctl", ["--assess", "--type", "execute", application]);
} else if (notarized) await notary(application);
const arch = target.startsWith("aarch64") ? "arm64" : "x64";
const basename = `Dioptas-Desktop_${version}_macos_${arch}`;
const dmg = path.join(output, `${basename}.dmg`);
const staging = path.join(output, "image-contents");
await mkdir(staging);
try {
  await run("ditto", [
    application,
    path.join(staging, path.basename(application)),
  ]);
  await symlink("/Applications", path.join(staging, "Applications"));
  await hdiutil(
    [
      "create",
      "-volname",
      releaseConfig.productName,
      "-srcfolder",
      staging,
      "-format",
      "UDZO",
      "-fs",
      "HFS+",
      dmg,
    ],
    { beforeRetry: () => rm(dmg, { force: true }) },
  );
} finally {
  await rm(staging, { recursive: true, force: true });
}
await run("codesign", [
  "--force",
  ...(adHoc ? [] : ["--timestamp"]),
  "--sign",
  identity,
  dmg,
]);
if (notarized) await notary(dmg);
const verification = await verifyMacosDmg(dmg, {
  teamIdentifier,
  notarized,
  nativeSmoke: !!values["native-smoke"],
});
const archive = path.join(output, `${basename}.app.tar.gz`);
await run("tar", [
  "-czf",
  archive,
  "-C",
  path.dirname(application),
  path.basename(application),
]);
const checksums = [];
for (const file of [dmg, archive])
  checksums.push(
    `${createHash("sha256")
      .update(await readFile(file))
      .digest("hex")}  ${path.basename(file)}`,
  );
await writeFile(path.join(output, "SHA256SUMS"), checksums.join("\n") + "\n");
const report = {
  version,
  identifier: releaseConfig.identifier,
  target,
  sourceRevision,
  packagingRevision,
  recoveredApplication: !!recoveredApplication,
  sourceDirty,
  signing: adHoc ? "ad-hoc" : "developer-id",
  teamIdentifier,
  notarized,
  published: false,
  dmg: path.basename(dmg),
  verification,
};
await writeFile(
  path.join(output, "build.json"),
  JSON.stringify(report, null, 2) + "\n",
);
await writeFile(
  path.join(artifacts, "latest.json"),
  JSON.stringify({ output, ...report }, null, 2) + "\n",
);
console.log(
  `Verified ${notarized ? "notarized" : adHoc ? "ad-hoc" : "Developer ID signed"} DMG: ${dmg}`,
);
