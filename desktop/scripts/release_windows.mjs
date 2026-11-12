// Produces installer candidates only; no releases, tags or publishing.
import assert from "node:assert/strict";
import { execFileSync, spawn } from "node:child_process";
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
import { parseArgs } from "node:util";
import { desktop, version, releaseConfig } from "./release_config.mjs";
import { windowsSigning } from "./windows_release_config.mjs";

assert.equal(process.platform, "win32", "Build Windows installers on Windows");
const { values } = parseArgs({
  options: {
    unsigned: { type: "boolean" },
    "test-upgrade": { type: "boolean" },
  },
});
const signing = windowsSigning(!!values.unsigned, process.env);
const capture = (command, args) =>
  execFileSync(command, args, { cwd: desktop, encoding: "utf8" }).trim();
const target = capture("rustc", ["-vV"]).match(/^host: (.+)$/m)?.[1];
assert.equal(target, "x86_64-pc-windows-msvc", "Use a native x64 MSVC runner");
const root = path.join(desktop, "artifacts/native-windows");
await mkdir(root, { recursive: true });
const output = await mkdtemp(path.join(root, `${version}-x64-`));
const sourceRevision = capture("git", ["rev-parse", "HEAD"]);
const sourceDirty = !!capture("git", ["status", "--porcelain"]);
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
async function run(args) {
  await new Promise((resolve, reject) => {
    const child = spawn(
      process.execPath,
      ["node_modules/@tauri-apps/cli/tauri.js", ...args],
      { cwd: desktop, stdio: "inherit" },
    );
    child.on("error", reject);
    child.on("close", (code) =>
      code === 0 ? resolve() : reject(Error(`Tauri build failed (${code})`)),
    );
  });
}
const builds = [];
const versions = [version];
if (values["test-upgrade"]) {
  assert.match(
    version,
    /^\d+\.\d+\.\d+$/,
    "Upgrade fixture requires a numeric packaging test version",
  );
  const parts = version.split(".").map(Number);
  parts[2]++;
  versions.push(parts.join("."));
}
for (const candidateVersion of versions) {
  await run([
    "build",
    "--ci",
    "--config",
    "src-tauri/tauri.release.conf.json",
    "--config",
    "src-tauri/tauri.windows-release.conf.json",
    "--config",
    JSON.stringify({ version: candidateVersion, bundle: { windows: signing } }),
    "--bundles",
    "nsis",
    ...(values.unsigned ? ["--no-sign"] : []),
    "--",
    "--locked",
  ]);
  const directory = path.join(metadata.target_directory, "release/bundle/nsis");
  const candidates = (await readdir(directory)).filter(
    (f) => f.endsWith("-setup.exe") && f.includes(`_${candidateVersion}_`),
  );
  assert.equal(
    candidates.length,
    1,
    `Expected one ${candidateVersion} NSIS installer`,
  );
  const file = path.join(output, candidates[0]);
  await copyFile(path.join(directory, candidates[0]), file);
  builds.push({
    version: candidateVersion,
    installer: file,
    sha256: createHash("sha256")
      .update(await readFile(file))
      .digest("hex"),
  });
}
const report = {
  version,
  identifier: releaseConfig.identifier,
  productName: releaseConfig.productName,
  target,
  sourceRevision,
  sourceDirty,
  signing: values.unsigned ? "unsigned-test" : "authenticode",
  signerThumbprint: values.unsigned
    ? null
    : process.env.DIOPTAS_WINDOWS_SIGNER_THUMBPRINT,
  offlineWebView2: true,
  bundledVCRuntime: true,
  published: false,
  builds,
  output,
};
await writeFile(
  path.join(output, "build.json"),
  JSON.stringify(report, null, 2) + "\n",
);
await writeFile(
  path.join(output, "SHA256SUMS"),
  builds.map((b) => `${b.sha256}  ${path.basename(b.installer)}`).join("\n") +
    "\n",
);
await writeFile(
  path.join(root, "latest.json"),
  JSON.stringify(report, null, 2) + "\n",
);
console.log(`Built ${report.signing} installer candidates: ${output}`);
