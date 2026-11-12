// Verify the complete published crates plus the reviewed Windows offset fix.
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFile, readdir } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const root = fileURLToPath(new URL("../../", import.meta.url));
const sha256 = (bytes) => createHash("sha256").update(bytes).digest("hex");
async function inventory(directory, prefix = "") {
  const files = [];
  for (const entry of await readdir(directory, { withFileTypes: true })) {
    const name = prefix + entry.name;
    if (entry.isDirectory())
      files.push(...(await inventory(path.join(directory, entry.name), name + "/")));
    else {
      assert(entry.isFile(), `Non-regular HDF5 source: ${name}`);
      files.push(name);
    }
  }
  return files.sort();
}
export async function verifyHdf5WindowsAbi(repository = root) {
  const vendor = path.join(repository, "desktop/vendor");
  const bytes = await readFile(path.join(vendor, "HDF5_WINDOWS_ABI.json"));
  assert.equal(
    sha256(bytes),
    "bdee818b864ec992ca787da869a35aee9b214d23b8821fa7b71237c70a418f83",
    "HDF5 source and patch provenance changed; review the original archives",
  );
  const provenance = JSON.parse(bytes);
  for (const pkg of provenance.packages) {
    const directory = path.join(vendor, pkg.crate);
    const expected = {
      ...pkg.originalFiles,
      ...Object.fromEntries(Object.entries(pkg.additionalFiles).map(([file, record]) => [file, record.sha256])),
    };
    assert.deepEqual(await inventory(directory), Object.keys(expected).sort());
    for (const [file, original] of Object.entries(expected)) {
      assert(!path.isAbsolute(file) && !file.split("/").includes(".."));
      assert.equal(
        sha256(await readFile(path.join(directory, file))),
        pkg.patchedFiles[file] ?? original,
        `Unexpected HDF5 source change: ${pkg.crate}/${file}`,
      );
    }
  }
  const manifest = await readFile(path.join(repository, "desktop/backend/Cargo.toml"), "utf8");
  const lock = await readFile(path.join(repository, "desktop/backend/Cargo.lock"), "utf8");
  for (const pkg of provenance.packages) {
    assert(manifest.includes(`${pkg.crate} = { path = "../vendor/${pkg.crate}" }`));
    const entries = lock.split("[[package]]").filter((entry) => entry.includes(`name = "${pkg.crate}"`));
    assert.equal(entries.length, 1);
    assert(entries[0].includes(`version = "${pkg.version}"`));
    assert.doesNotMatch(entries[0], /^(source|checksum)\s*=/m);
  }
  return provenance;
}
if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  await verifyHdf5WindowsAbi();
  console.log("Verified published HDF5 crates and Windows HDoff_t ABI patch");
}
