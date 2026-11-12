import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { createHash } from "node:crypto";
import { lstat, open, readFile, readdir, realpath } from "node:fs/promises";
import path from "node:path";
import {
  elfMachine,
  requiredGlibc,
  resolvedDependencies,
} from "./linux_release_config.mjs";

const digest = (bytes) => createHash("sha256").update(bytes).digest("hex");
export async function inspectLinuxInstall(prefix, appimage = false) {
  assert.equal(process.platform, "linux");
  const resources = path.join(prefix, "usr/lib/dioptas-desktop/dioptas");
  const manifest = JSON.parse(
    await readFile(path.join(resources, "RESOURCE_MANIFEST.json"), "utf8"),
  );
  assert.equal(manifest.target, "x86_64-unknown-linux-gnu");
  for (const record of manifest.files) {
    assert(
      !path.isAbsolute(record.path) &&
        !record.path.split(/[\\/]/).includes(".."),
    );
    const file = path.join(resources, record.path);
    assert(
      (await lstat(file)).isFile(),
      `Non-regular application resource: ${file}`,
    );
    const bytes = await readFile(file);
    assert.equal(bytes.length, record.bytes, file);
    assert.equal(digest(bytes), record.sha256, file);
  }
  const binaries = [
    path.join(prefix, "usr/bin/dioptas-desktop"),
    path.join(prefix, "usr/bin/dioptas-processor"),
  ];
  const nativeFiles = [];
  async function walk(directory) {
    for (const entry of await readdir(directory, { withFileTypes: true })) {
      const file = path.join(directory, entry.name);
      if (entry.isDirectory()) await walk(file);
      else if (entry.isSymbolicLink()) {
        const resolved = await realpath(file);
        assert(
          resolved.startsWith(path.resolve(prefix) + path.sep),
          `Escaping AppDir symlink: ${file}`,
        );
      } else {
        assert(!/\.(py|pyc|pyd)$/i.test(entry.name), `Python payload: ${file}`);
        const handle = await open(file, "r");
        const header = Buffer.alloc(64);
        try {
          await handle.read(header, 0, 64, 0);
        } finally {
          await handle.close();
        }
        if (header.subarray(0, 4).toString("hex") === "7f454c46") {
          assert.equal(elfMachine(header), 62, `Expected x64 ELF: ${file}`);
          nativeFiles.push(file);
        }
      }
    }
  }
  if (appimage) await walk(prefix);
  else await walk(resources);
  const libraryPath = appimage
    ? [
        ...new Set(
          nativeFiles
            .filter((f) => /\.so(?:\.|$)/.test(f))
            .map((f) => path.dirname(f)),
        ),
      ].join(":")
    : "";
  const inspected = [];
  for (const file of binaries) {
    const bytes = await readFile(file);
    assert.equal(elfMachine(bytes), 62, `Expected x64 executable: ${file}`);
    assert(
      (await lstat(file)).mode & 0o111,
      `Missing execute permission: ${file}`,
    );
    const versions = execFileSync("readelf", ["--version-info", file], {
      encoding: "utf8",
    });
    const dependencies = execFileSync("ldd", [file], {
      encoding: "utf8",
      env: { ...process.env, LD_LIBRARY_PATH: libraryPath, LD_PRELOAD: "" },
    });
    inspected.push({
      file: path.relative(prefix, file),
      sha256: digest(bytes),
      requiredGlibc: requiredGlibc(versions),
      dependencies: resolvedDependencies(dependencies),
    });
  }
  const desktopDirectory = path.join(prefix, "usr/share/applications");
  const entries = (await readdir(desktopDirectory)).filter(
    (f) => f.endsWith(".desktop") && /dioptas/i.test(f),
  );
  assert.equal(entries.length, 1, "Expected one Dioptas desktop entry");
  const desktopFile = path.join(desktopDirectory, entries[0]);
  execFileSync("desktop-file-validate", [desktopFile]);
  const desktopEntry = await readFile(desktopFile, "utf8");
  assert.match(desktopEntry, /^Exec=.*dioptas-desktop/m);
  assert.match(desktopEntry, /^Type=Application$/m);
  const notices = JSON.parse(
    await readFile(path.join(resources, "THIRD_PARTY_NOTICES.json"), "utf8"),
  );
  let systemNoticeCount = 0;
  if (appimage) {
    const directory = path.join(prefix, "usr/share/doc/dioptas-native-runtime");
    const inventory = JSON.parse(
      await readFile(path.join(directory, "SYSTEM_NOTICES.json"), "utf8"),
    );
    for (const record of inventory.packages) {
      assert(
        !path.isAbsolute(record.file) && !record.file.split("/").includes(".."),
      );
      assert.equal(
        digest(await readFile(path.join(directory, record.file))),
        record.sha256,
      );
    }
    systemNoticeCount = inventory.packages.length;
    assert(systemNoticeCount > 0);
  }
  return {
    resources: manifest.files.length,
    cargoNotices: notices.cargo.length,
    javascriptNotices: notices.javascript.length,
    binaries: inspected,
    desktopFile,
    bundledElfFiles: nativeFiles.length,
    systemNoticeCount,
    resourcesDirectory: resources,
    pythonPayload: false,
  };
}
