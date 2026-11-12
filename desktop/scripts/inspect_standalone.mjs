import assert from "node:assert/strict";
import { verifyPeritheosResources } from "./peritheos_distribution.mjs";
import { execFileSync, spawnSync } from "node:child_process";
import { createHash } from "node:crypto";
import {
  lstat,
  readFile,
  readdir,
  realpath,
  mkdir,
  writeFile,
} from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { signatureDetails, requireDeveloperId } from "./release_config.mjs";

const desktop = fileURLToPath(new URL("../", import.meta.url));
export function inspectSignature(file) {
  const displayed = spawnSync(
    "/usr/bin/codesign",
    ["--display", "--verbose=4", file],
    { encoding: "utf8" },
  );
  assert.equal(displayed.status, 0, displayed.stderr);
  return signatureDetails(displayed.stdout + displayed.stderr);
}

export async function inspectStandalone(application, options = {}) {
  const app = await realpath(application);
  const resources = path.join(app, "Contents/Resources/dioptas");
  const manifest = JSON.parse(
    await readFile(path.join(resources, "RESOURCE_MANIFEST.json"), "utf8"),
  );
  assert.deepEqual(
    manifest.peritheos,
    await verifyPeritheosResources(
      path.join(resources, "scientific-data/peritheos"),
    ),
  );
  const minimum = execFileSync(
    "/usr/bin/plutil",
    [
      "-extract",
      "LSMinimumSystemVersion",
      "raw",
      path.join(app, "Contents/Info.plist"),
    ],
    { encoding: "utf8" },
  ).trim();
  assert.equal(minimum, "14.0");
  for (const file of manifest.files) {
    assert(!path.isAbsolute(file.path) && !file.path.split("/").includes(".."));
    const data = await readFile(path.join(resources, file.path));
    assert.equal(data.length, file.bytes, file.path);
    assert.equal(
      createHash("sha256").update(data).digest("hex"),
      file.sha256,
      file.path,
    );
  }
  const binaries = [];
  async function inspect(directory) {
    for (const name of await readdir(directory)) {
      const file = path.join(directory, name),
        info = await lstat(file);
      if (info.isSymbolicLink()) {
        assert(
          (await realpath(file)).startsWith(`${app}${path.sep}`),
          `External bundle symlink: ${file}`,
        );
      } else if (info.isDirectory()) await inspect(file);
      else {
        assert(
          !/\.(py|pyc|pyd)$/i.test(name),
          `Python runtime/source included: ${file}`,
        );
        const bytes = await readFile(file);
        if (
          bytes.length < 4 ||
          ![
            0xfeedface, 0xfeedfacf, 0xcefaedfe, 0xcffaedfe, 0xcafebabe,
            0xbebafeca,
          ].includes(bytes.readUInt32BE(0))
        )
          continue;
        const linked = execFileSync("/usr/bin/otool", ["-L", file], {
          encoding: "utf8",
        });
        const libraries = linked
          .split("\n")
          .slice(1)
          .filter((s) => s.trim())
          .map((s) => s.trim().split(" (compatibility")[0]);
        for (const library of libraries)
          assert(
            library.startsWith("/System/Library/") ||
              library.startsWith("/usr/lib/"),
            `Non-system native dependency: ${library}`,
          );
        const commands = execFileSync("/usr/bin/otool", ["-l", file], {
          encoding: "utf8",
        });
        const versions = [
          ...commands.matchAll(/\bminos (\d+\.\d+(?:\.\d+)?)/g),
        ].map((m) => m[1]);
        assert(versions.length, `Missing deployment metadata: ${file}`);
        for (const version of versions) {
          const [major, minor = 0, patch = 0] = version.split(".").map(Number);
          assert(
            major < 14 || (major === 14 && minor === 0 && patch === 0),
            `Newer deployment target ${version}: ${file}`,
          );
        }
        const architectures = execFileSync("/usr/bin/lipo", ["-archs", file], {
          encoding: "utf8",
        })
          .trim()
          .split(/\s+/);
        const expected = manifest.target.startsWith("aarch64-")
          ? "arm64"
          : "x86_64";
        assert.deepEqual(
          architectures,
          [expected],
          `Unexpected architecture: ${file}`,
        );
        const signing = inspectSignature(file);
        if (options.teamIdentifier)
          requireDeveloperId(signing, options.teamIdentifier);
        binaries.push({
          path: path.relative(app, file),
          sha256: createHash("sha256").update(bytes).digest("hex"),
          minimumOS: versions,
          architectures,
          libraries,
          signing,
        });
      }
    }
  }
  await inspect(app);
  assert.equal(
    binaries.length,
    2,
    "Expected the host and statically linked processor",
  );
  execFileSync("/usr/bin/codesign", ["--verify", "--deep", "--strict", app], {
    stdio: ["ignore", "ignore", "pipe"],
  });
  const notices = JSON.parse(
    await readFile(path.join(resources, "THIRD_PARTY_NOTICES.json"), "utf8"),
  );
  return {
    application: app,
    minimumOS: minimum,
    signature: binaries[0].signing.kind,
    resources: manifest.files.length,
    cargoNotices: notices.cargo.length,
    javascriptNotices: notices.javascript.length,
    binaries,
  };
}
if (
  process.argv[1] &&
  path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)
) {
  const application =
    process.argv[2] ||
    path.join(
      desktop,
      "src-tauri/target/release/bundle/macos/Dioptas Desktop.app",
    );
  const result = await inspectStandalone(application);
  const artifacts = path.join(desktop, "artifacts/standalone");
  await mkdir(artifacts, { recursive: true });
  await writeFile(
    path.join(artifacts, "inspection.json"),
    JSON.stringify(result, null, 2) + "\n",
  );
  console.log(JSON.stringify(result, null, 2));
}
