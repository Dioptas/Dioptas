import assert from "node:assert/strict";
import { verifyPeritheosResources } from "./peritheos_distribution.mjs";
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
export async function inspectLinuxInstall(
  prefix,
  appimage = false,
  ceiling = [2, 35],
) {
  assert.equal(process.platform, "linux");
  // Tauri uses the configured product name for its Linux resource directory.
  // Discover the one manifest instead of deriving a directory from the deb name.
  const locations = [];
  for (const entry of await readdir(path.join(prefix, "usr/lib"), {
    withFileTypes: true,
  })) {
    if (!entry.isDirectory()) continue;
    const candidate = path.join(prefix, "usr/lib", entry.name, "dioptas");
    try {
      if (
        (await lstat(path.join(candidate, "RESOURCE_MANIFEST.json"))).isFile()
      )
        locations.push(candidate);
    } catch (error) {
      if (error.code !== "ENOENT" && error.code !== "ENOTDIR") throw error;
    }
  }
  assert.equal(locations.length, 1, "Expected one installed resource manifest");
  const resources = locations[0];
  const manifest = JSON.parse(
    await readFile(path.join(resources, "RESOURCE_MANIFEST.json"), "utf8"),
  );
  assert.deepEqual(
    manifest.peritheos,
    await verifyPeritheosResources(
      path.join(resources, "scientific-data/peritheos"),
    ),
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
      requiredGlibc: requiredGlibc(versions, ceiling),
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
  const runtimeLibraries = [];
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
    const extraLibraries = JSON.parse(
      await readFile(path.join(directory, "EXTRA_LIBRARIES.json"), "utf8"),
    );
    assert(extraLibraries.some((library) => library.name === "libGLESv2.so.2"));
    for (const library of extraLibraries) {
      assert.equal(path.basename(library.name), library.name);
      const file = path.join(prefix, "usr/lib", library.name);
      const bytes = await readFile(file);
      assert.equal(elfMachine(bytes), 62);
      assert.match(library.sha256, /^[a-f0-9]{64}$/);
      const dynamic = execFileSync("readelf", ["--dynamic", file], {
        encoding: "utf8",
      });
      assert(dynamic.includes(`Library soname: [${library.name}]`));
      const searchPaths = dynamic
        .split("\n")
        .filter((line) => /\((?:RPATH|RUNPATH)\)/.test(line));
      assert(
        !searchPaths.some((line) =>
          /\/home\/runner\/work\/|\/target\//.test(line),
        ),
        "Library retained a build-time search path",
      );
      // linuxdeploy can rewrite RPATH/ELF layout. Retain the source-package
      // hash separately from the relocated payload protected by the AppImage
      // checksum; do not falsely label the two byte sequences as identical.
      const bundledSha256 = digest(bytes);
      runtimeLibraries.push({
        name: library.name,
        package: library.package,
        version: library.version,
        sourceSha256: library.sha256,
        bundledSha256,
        relocatedByBundler: bundledSha256 !== library.sha256,
        requiredGlibc: requiredGlibc(
          execFileSync("readelf", ["--version-info", file], {
            encoding: "utf8",
          }),
          ceiling,
        ),
        searchPaths,
      });
      assert(
        inventory.packages.some(
          (pkg) =>
            pkg.name === library.package &&
            pkg.version === library.version &&
            pkg.file === library.copyright,
        ),
      );
    }
  }
  return {
    resources: manifest.files.length,
    cargoNotices: notices.cargo.length,
    javascriptNotices: notices.javascript.length,
    binaries: inspected,
    desktopFile,
    bundledElfFiles: nativeFiles.length,
    bundledElfPaths: appimage
      ? nativeFiles.map((file) => path.relative(prefix, file))
      : [],
    systemNoticeCount,
    runtimeLibraries,
    resourcesDirectory: resources,
    pythonPayload: false,
  };
}
