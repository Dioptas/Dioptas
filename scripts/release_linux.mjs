// Artifact-only native Linux packaging. Never creates a release or tag.
import assert from "node:assert/strict";
import { execFileSync, spawn } from "node:child_process";
import { createHash } from "node:crypto";
import {
  chmod,
  copyFile,
  mkdir,
  mkdtemp,
  readFile,
  readdir,
  rm,
  writeFile,
} from "node:fs/promises";
import path from "node:path";
import { parseArgs } from "node:util";
import { desktop, version, releaseConfig } from "./release_config.mjs";
import { upgradeFixtureVersion, debianVersion } from "./release_version.mjs";
import { systemNotices } from "./linux_system_notices.mjs";

assert.equal(process.platform, "linux", "Build Linux candidates on Linux");
const { values } = parseArgs({
  options: {
    "test-upgrade": { type: "boolean" },
    format: { type: "string", default: "deb" },
  },
});
const format = values.format;
assert(
  ["deb", "appimage"].includes(format),
  "Use --format deb or --format appimage",
);
assert(
  format === "deb" || !values["test-upgrade"],
  "Upgrade fixtures apply to deb packages",
);
const capture = (command, args) =>
  execFileSync(command, args, { cwd: desktop, encoding: "utf8" }).trim();
const rustc = capture("rustc", ["-vV"]);
const target = rustc.match(/^host: (.+)$/m)?.[1];
assert.equal(
  target,
  "x86_64-unknown-linux-gnu",
  "Use a native x64 glibc runner",
);
const osRelease = await readFile("/etc/os-release", "utf8");
assert.match(osRelease, /^ID=ubuntu$/m);
const baseline = format === "deb" ? "22.04" : "24.04";
const glibcBaseline = format === "deb" ? "2.35" : "2.39";
assert(
  osRelease.includes(`VERSION_ID="${baseline}"`),
  `Build ${format} on its declared Ubuntu ${baseline} baseline`,
);
const root = path.join(desktop, "artifacts/native-linux");
await mkdir(root, { recursive: true });
const output = await mkdtemp(path.join(root, `${version}-${format}-x64-`));
const sourceRevision = capture("git", ["rev-parse", "HEAD"]);
const sourceDirty = !!capture("git", ["status", "--porcelain"]);
const notices = await systemNotices();
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
const versions = [version];
if (values["test-upgrade"]) {
  versions.push(upgradeFixtureVersion(version));
}
const builds = [];
for (const candidateVersion of versions) {
  const kinds = [format];
  await new Promise((resolve, reject) => {
    const child = spawn(
      process.execPath,
      [
        "node_modules/@tauri-apps/cli/tauri.js",
        "build",
        "--ci",
        "--config",
        "src-tauri/tauri.release.conf.json",
        "--config",
        "src-tauri/tauri.linux-release.conf.json",
        "--config",
        JSON.stringify({ version: candidateVersion }),
        "--bundles",
        kinds.join(","),
        "--no-sign",
        "--",
        "--locked",
      ],
      {
        cwd: desktop,
        stdio: "inherit",
        env: { ...process.env, APPIMAGE_EXTRACT_AND_RUN: "1" },
      },
    );
    child.on("error", reject);
    child.on("close", (code) =>
      code === 0
        ? resolve()
        : reject(Error(`Linux packaging failed (${code})`)),
    );
  });
  for (const kind of kinds) {
    const directory = path.join(
      metadata.target_directory,
      "release/bundle",
      kind,
    );
    const extension = kind === "deb" ? ".deb" : ".AppImage";
    const files = (await readdir(directory)).filter(
      (f) => f.endsWith(extension) && f.includes(`_${candidateVersion}_`),
    );
    assert.equal(
      files.length,
      1,
      `Expected one ${candidateVersion} ${kind} candidate`,
    );
    const file = path.join(output, files[0]);
    await copyFile(path.join(directory, files[0]), file);
    // Debian sorts a hyphenated prerelease after the stable version. Use
    // Debian's tilde ordering inside the package while keeping SemVer filenames.
    // Retain the existing package identity when the visible product name changes.
    if (kind === "deb") {
      const unpacked = await mkdtemp(path.join(output, ".deb-version-"));
      execFileSync("dpkg-deb", ["--raw-extract", file, unpacked]);
      const control = path.join(unpacked, "DEBIAN/control");
      const text = await readFile(control, "utf8");
      assert(text.includes(`Version: ${candidateVersion}\n`));
      assert.match(text, /^Package: (?:dioptas|dioptas-desktop)$/m);
      await writeFile(
        control,
        text
          .replace(/^Package: .+$/m, "Package: dioptas-desktop")
          .replace(
            `Version: ${candidateVersion}\n`,
            `Version: ${debianVersion(candidateVersion)}\n`,
          ),
      );
      execFileSync("dpkg-deb", [
        "--build",
        "--root-owner-group",
        unpacked,
        file,
      ]);
      await rm(unpacked, { recursive: true });
    }
    if (kind === "appimage") await chmod(file, 0o755);
    builds.push({
      version: candidateVersion,
      kind,
      file: path.basename(file),
      sha256: createHash("sha256")
        .update(await readFile(file))
        .digest("hex"),
    });
  }
}
const report = {
  version,
  identifier: releaseConfig.identifier,
  productName: releaseConfig.productName,
  target,
  format,
  sourceRevision,
  sourceDirty,
  signing: "unsigned-test",
  published: false,
  rustc,
  buildSystem: osRelease,
  glibcBaseline,
  systemNotices: notices,
  builds,
};
await writeFile(
  path.join(output, "build.json"),
  JSON.stringify(report, null, 2) + "\n",
);
await writeFile(
  path.join(output, "SHA256SUMS"),
  builds.map((b) => `${b.sha256}  ${b.file}`).join("\n") + "\n",
);
await writeFile(
  path.join(root, "latest.json"),
  JSON.stringify({ output, ...report }, null, 2) + "\n",
);
console.log(`Built Linux test candidates: ${output}`);
