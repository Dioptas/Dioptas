import { execFileSync } from "node:child_process";
import { createHash } from "node:crypto";
import { cp, mkdir, readFile, readdir, rm, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { verifyHdf5WindowsAbi } from "./check_hdf5_windows_abi.mjs";

import { verifyPeritheosResources } from "./peritheos_distribution.mjs";

const desktop = fileURLToPath(new URL("../", import.meta.url));
const repository = path.dirname(desktop.slice(0, -1));
const digest = (data) => createHash("sha256").update(data).digest("hex");
const notice = /^(licen[cs]e|copying|copyright|notice|authors)([._-]|$)/i;
const excluded = new Set([
  "target",
  ".git",
  "node_modules",
  "tests",
  "examples",
  "benches",
  "artifacts",
]);

async function notices(directory, recursive = true) {
  const result = [];
  for (const entry of await readdir(directory, { withFileTypes: true })) {
    const file = path.join(directory, entry.name);
    if (entry.isFile() && notice.test(entry.name)) result.push(file);
    else if (recursive && entry.isDirectory() && !excluded.has(entry.name))
      result.push(...(await notices(file)));
  }
  return result;
}

// Resolve every package through the same fail-closed path used by staging.
// Version-specific, hash-pinned upstream texts cover incomplete crate archives.
export async function cargoLicenseFiles(item, overridesDirectory, overrides) {
  const directory = path.dirname(item.manifest_path);
  let files = await notices(directory, item.source !== null);
  if (item.license_file) files.push(path.resolve(directory, item.license_file));
  // Workspace crates can inherit a repository-level license.
  if (files.length === 0) {
    let parent = path.dirname(directory);
    for (
      let depth = 0;
      depth < 5 && parent !== path.dirname(parent);
      depth++, parent = path.dirname(parent)
    ) {
      files = await notices(parent, false);
      if (files.length) break;
    }
  }
  const override = overrides[`${item.name}@${item.version}`] || [];
  for (const record of override) {
    const file = path.join(overridesDirectory, record.file);
    if (digest(await readFile(file)) !== record.sha256)
      throw Error(`Changed pinned license text: ${record.file}`);
    files.push(file);
  }
  if (!files.length)
    throw Error(`Missing license text for ${item.name} ${item.version}`);
  return { files, override };
}

export async function prepareStandaloneResources(target) {
  const hdf5Abi = await verifyHdf5WindowsAbi(repository);
  const output = path.join(desktop, "src-tauri/resources/dioptas");
  // Only this generated staging directory is replaced.
  await rm(output, { recursive: true, force: true });
  await mkdir(path.join(output, "examples"), { recursive: true });
  const copies = [
    ["LICENSE.txt", "licenses/Dioptas-MIT.txt"],
    ["desktop/licenses", "licenses/interface"],
    [
      "desktop/vendor/HDF5_WINDOWS_ABI.json",
      "licenses/hdf5/HDF5_WINDOWS_ABI.json",
    ],
    ["desktop/vendor/HDF5_WINDOWS_ABI.md", "licenses/hdf5/HDF5_WINDOWS_ABI.md"],
    ["desktop/standalone/README.html", "README.html"],
    ["desktop/backend/resources", "scientific-data"],
    ["dioptas/resources/calibrants", "calibrants"],
    ["dioptas/resources/data", "reference-data"],
    ["dioptas/tests/data/CeO2_Pilatus1M.tif", "examples/CeO2_Pilatus1M.tif"],
    ["dioptas/tests/data/CeO2_Pilatus1M.poni", "examples/CeO2_Pilatus1M.poni"],
    ["dioptas/tests/data/jcpds/mo.jcpds", "examples/mo.jcpds"],
  ];
  for (const [source, destination] of copies) {
    await cp(path.join(repository, source), path.join(output, destination), {
      recursive: true,
    });
  }
  const peritheos = await verifyPeritheosResources(
    path.join(output, "scientific-data/peritheos"),
  );
  const packages = new Map();
  for (const manifest of ["backend/Cargo.toml", "src-tauri/Cargo.toml"]) {
    const metadata = JSON.parse(
      execFileSync(
        process.env.CARGO || "cargo",
        [
          "metadata",
          "--locked",
          "--format-version",
          "1",
          "--filter-platform",
          target,
          "--manifest-path",
          manifest,
        ],
        { cwd: desktop, encoding: "utf8", maxBuffer: 64 * 1024 * 1024 },
      ),
    );
    const active = new Set(metadata.resolve.nodes.map((n) => n.id));
    for (const item of metadata.packages.filter((p) => active.has(p.id)))
      packages.set(item.id, item);
  }
  const cargo = [];
  const overridesDirectory = path.join(desktop, "licenses/cargo-overrides");
  const overrides = JSON.parse(
    await readFile(path.join(overridesDirectory, "SOURCES.json"), "utf8"),
  );
  for (const item of [...packages.values()].sort((a, b) =>
    a.id.localeCompare(b.id),
  )) {
    const { files, override } = await cargoLicenseFiles(
      item,
      overridesDirectory,
      overrides,
    );
    const texts = [];
    const key = `${item.name}-${item.version}-${digest(item.source || "application").slice(0, 8)}`;
    for (const file of [...new Set(files)].sort()) {
      const data = await readFile(file);
      const sha256 = digest(data);
      const relative = `licenses/cargo/${key}/${sha256.slice(0, 12)}-${path.basename(file)}`;
      await mkdir(path.dirname(path.join(output, relative)), {
        recursive: true,
      });
      await writeFile(path.join(output, relative), data);
      texts.push({ path: relative, sha256 });
    }
    const patch =
      item.source === null &&
      hdf5Abi.packages.find(
        (pkg) => pkg.crate === item.name && pkg.version === item.version,
      );
    cargo.push({
      name: item.name,
      version: item.version,
      source:
        item.source ||
        (patch ? `vendored:${patch.registryUrl}` : "application"),
      repository: item.repository,
      sourceArchive: patch
        ? patch.registryUrl
        : item.source?.startsWith("registry+")
          ? `https://crates.io/api/v1/crates/${item.name}/${item.version}/download`
          : item.source,
      license: item.license,
      upstreamNotices: override,
      ...(patch ? { localPatch: "licenses/hdf5/HDF5_WINDOWS_ABI.json" } : {}),
      texts,
    });
  }
  const javascript = [];
  const manifest = JSON.parse(
    await readFile(path.join(desktop, "package.json"), "utf8"),
  );
  const pending = Object.keys(manifest.dependencies);
  const visited = new Set();
  while (pending.length) {
    const name = pending.pop();
    if (visited.has(name)) continue;
    visited.add(name);
    const directory = path.join(desktop, "node_modules", name);
    const item = JSON.parse(
      await readFile(path.join(directory, "package.json"), "utf8"),
    );
    const files = await notices(directory, false);
    if (!files.length)
      throw Error(`Missing JavaScript license text for ${name}`);
    const texts = [];
    for (const file of files.sort()) {
      const relative = `licenses/javascript/${name}/${path.basename(file)}`;
      await mkdir(path.dirname(path.join(output, relative)), {
        recursive: true,
      });
      const data = await readFile(file);
      await writeFile(path.join(output, relative), data);
      texts.push({ path: relative, sha256: digest(data) });
    }
    javascript.push({
      name,
      version: item.version,
      license: item.license,
      texts,
    });
    pending.push(...Object.keys(item.dependencies || {}));
  }
  await writeFile(
    path.join(output, "THIRD_PARTY_NOTICES.json"),
    JSON.stringify(
      {
        scope:
          "Target-resolved Cargo application/build dependencies and production JavaScript dependencies. Native-source notices are retained recursively. Not a claim of scientific or source-data rights equivalence.",
        target,
        cargo,
        javascript,
      },
      null,
      2,
    ) + "\n",
  );
  const files = [];
  async function inventory(directory) {
    for (const entry of (
      await readdir(directory, { withFileTypes: true })
    ).sort((a, b) => a.name.localeCompare(b.name))) {
      const file = path.join(directory, entry.name);
      if (entry.isDirectory()) await inventory(file);
      else {
        const bytes = await readFile(file);
        files.push({
          path: path.relative(output, file).split(path.sep).join("/"),
          bytes: bytes.length,
          sha256: digest(bytes),
        });
      }
    }
  }
  await inventory(output);
  await writeFile(
    path.join(output, "RESOURCE_MANIFEST.json"),
    JSON.stringify(
      {
        format: 1,
        target,
        fontPolicy:
          "System UI fonts only; no external font service or font download.",
        scientificData:
          "Calibrants, phase/material core metadata, symmetry/scattering tables and detector definitions are also embedded in native binaries. Peritheos source qualifications and notices are retained; only EOS definitions/parameters, structure, references and qualifications are included, with no experimental datasets or embedded observation/audit row tables.",
        peritheos,
        example:
          "Raw CeO2 TIFF starts uncalibrated. The adjacent PONI is a separate reference, not an automatic fit or accuracy certificate.",
        files,
      },
      null,
      2,
    ) + "\n",
  );
  console.log(
    `Staged ${files.length} resources and notices (${cargo.length} Cargo packages, ${javascript.length} JavaScript packages).`,
  );
}
