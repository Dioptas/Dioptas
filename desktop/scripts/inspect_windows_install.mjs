import assert from "node:assert/strict";
import { verifyPeritheosResources } from "./peritheos_distribution.mjs";
import { execFileSync } from "node:child_process";
import { createHash } from "node:crypto";
import { lstat, readFile, readdir, realpath, access } from "node:fs/promises";
import path from "node:path";
import { peMachine, importLocation } from "./windows_release_config.mjs";

export async function inspectWindowsInstall(directory) {
  assert.equal(process.platform, "win32");
  const root = await realpath(directory);
  const resources = path.join(root, "dioptas");
  const manifest = JSON.parse(
    await readFile(path.join(resources, "RESOURCE_MANIFEST.json"), "utf8"),
  );
  assert.deepEqual(
    manifest.peritheos,
    await verifyPeritheosResources(
      path.join(resources, "scientific-data/peritheos"),
    ),
  );
  assert.equal(manifest.target, "x86_64-pc-windows-msvc");
  for (const file of manifest.files) {
    assert(
      !path.win32.isAbsolute(file.path) &&
        !file.path.split(/[\\/]/).includes(".."),
    );
    const bytes = await readFile(path.join(resources, file.path));
    assert.equal(bytes.length, file.bytes, file.path);
    assert.equal(
      createHash("sha256").update(bytes).digest("hex"),
      file.sha256,
      file.path,
    );
  }
  async function walk(folder) {
    const result = [];
    for (const entry of await readdir(folder, { withFileTypes: true })) {
      const file = path.join(folder, entry.name);
      const stat = await lstat(file);
      assert(!stat.isSymbolicLink(), `Unexpected installed symlink: ${file}`);
      if (entry.isDirectory()) result.push(...(await walk(file)));
      else {
        assert(!/\.(py|pyc|pyd)$/i.test(entry.name), `Python payload: ${file}`);
        result.push(file);
      }
    }
    return result;
  }
  const files = await walk(root);
  const localDlls = new Set(
    files
      .filter(
        (f) => path.dirname(f) === root && f.toLowerCase().endsWith(".dll"),
      )
      .map((f) => path.basename(f).toLowerCase()),
  );
  const binaries = [];
  const targets = [
    path.join(root, "dioptas-desktop.exe"),
    path.join(root, "dioptas-processor.exe"),
    ...files.filter((f) => f.toLowerCase().endsWith(".dll")),
  ];
  for (const file of targets) {
    const bytes = await readFile(file);
    assert.equal(peMachine(bytes), 0x8664, `Expected x64: ${file}`);
    const listing = execFileSync("dumpbin", ["/nologo", "/dependents", file], {
      encoding: "utf8",
    });
    const names = [...listing.matchAll(/^\s+([a-z0-9_.-]+\.dll)\s*$/gim)].map(
      (m) => m[1],
    );
    const dependencies = [];
    for (const name of names) {
      let systemExists = false;
      try {
        await access(path.join(process.env.SystemRoot, "System32", name));
        systemExists = true;
      } catch {}
      dependencies.push({
        name,
        location: importLocation(name, localDlls, systemExists),
      });
    }
    binaries.push({
      path: path.relative(root, file),
      sha256: createHash("sha256").update(bytes).digest("hex"),
      architecture: "x64",
      dependencies,
    });
  }
  const notices = JSON.parse(
    await readFile(path.join(resources, "THIRD_PARTY_NOTICES.json"), "utf8"),
  );
  return {
    resources: manifest.files.length,
    cargoNotices: notices.cargo.length,
    javascriptNotices: notices.javascript.length,
    binaries,
    pythonPayload: false,
  };
}
