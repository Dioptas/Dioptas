// Turn verified native installer candidates into the files of one GitHub
// Release, including the signed update manifest read by installed applications.
//
//   node scripts/updater_release.mjs --candidates DIR --output DIR [--revision SHA]
//
// The candidates are the downloaded artifacts of the native macOS, Windows and
// Linux workflows. Nothing is rebuilt: the published installers are the bytes
// those workflows verified. This script does not create the release itself.
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { createHash, createPublicKey, verify } from "node:crypto";
import {
  copyFile,
  mkdir,
  readdir,
  readFile,
  rm,
  writeFile,
} from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { parseArgs } from "node:util";

const desktop = fileURLToPath(new URL("../", import.meta.url));
export const repository = "Dioptas/Dioptas";
export const manifestName = "latest.json";

const sha256 = (bytes) => createHash("sha256").update(bytes).digest("hex");
const text = (base64) => Buffer.from(base64, "base64").toString("utf8");

/** Decode the minisign public key stored in `plugins.updater.pubkey`. */
export function parsePublicKey(configured) {
  assert(
    typeof configured === "string" && configured.trim(),
    "No update verification key is configured (plugins.updater.pubkey)",
  );
  const line = text(configured.trim()).trim().split("\n").at(-1);
  const raw = Buffer.from(line, "base64");
  assert(
    raw.length === 42 && raw.subarray(0, 2).toString("latin1") === "Ed",
    "plugins.updater.pubkey is not a minisign public key",
  );
  return { keyId: raw.subarray(2, 10), key: raw.subarray(10) };
}

function ed25519(key) {
  // SubjectPublicKeyInfo prefix for a raw Ed25519 key.
  return createPublicKey({
    key: Buffer.concat([Buffer.from("302a300506032b6570032100", "hex"), key]),
    format: "der",
    type: "spki",
  });
}

/**
 * Check a Tauri updater signature exactly as an installed application will:
 * the prehashed file signature, the signed trusted comment and its version.
 * A package signed with another key would be rejected by every installation.
 */
export function verifySignature(bytes, signature, publicKey, version) {
  const lines = text(signature).trim().split("\n");
  assert.equal(lines.length, 4, "Unexpected updater signature layout");
  const raw = Buffer.from(lines[1], "base64");
  assert(
    raw.length === 74 && raw.subarray(0, 2).toString("latin1") === "ED",
    "Updater signatures must use the prehashed minisign format",
  );
  assert(
    raw.subarray(2, 10).equals(publicKey.keyId),
    "The signature was made with a different key than plugins.updater.pubkey",
  );
  const key = ed25519(publicKey.key);
  const digest = createHash("blake2b512").update(bytes).digest();
  assert(
    verify(null, digest, key, raw.subarray(10)),
    "The updater signature does not match the file",
  );
  assert(lines[2].startsWith("trusted comment: "));
  const comment = lines[2].slice("trusted comment: ".length);
  assert(
    verify(
      null,
      Buffer.concat([raw.subarray(10), Buffer.from(comment, "utf8")]),
      key,
      Buffer.from(lines[3], "base64"),
    ),
    "The signed comment of the updater signature is invalid",
  );
  const signed = comment
    .split("\t")
    .find((field) => field.startsWith("version:"))
    ?.slice("version:".length);
  assert.equal(
    signed,
    version,
    "The signature must be bound to the released version (--app-version)",
  );
  return { comment };
}

/**
 * The macOS updater drops the first path component of every archive entry, so
 * everything must sit inside one top-level `<Name>.app`. AppleDouble `._`
 * entries written by macOS tar would be unpacked over the bundle itself.
 */
export function validateAppArchive(listing) {
  const entries = listing.split("\n").filter(Boolean);
  const roots = new Set(entries.map((entry) => entry.split("/")[0]));
  assert.equal(roots.size, 1, `One application expected: ${[...roots]}`);
  const [root] = roots;
  assert(
    root.endsWith(".app") && !root.startsWith("._"),
    `Unexpected archive root ${root}`,
  );
  for (const required of ["Contents/Info.plist", "Contents/MacOS/"])
    assert(
      entries.some((entry) => entry.startsWith(`${root}/${required}`)),
      `The application archive lacks ${required}`,
    );
  return root;
}

/** The introduction of `docs/release/RELEASE_<version>.md`, shown in the update notice. */
export function releaseNotes(markdown) {
  const body = markdown.replace(/\r\n?/g, "\n").split(/^## /m)[0];
  return body
    .replace(/^# .*$/m, "")
    .split(/\n{2,}/)
    .map((paragraph) => paragraph.replace(/\s*\n\s*/g, " ").trim())
    .filter(Boolean)
    .join("\n\n");
}

export const isPrerelease = (version) => version.includes("-");

async function reports(directory) {
  const found = [];
  for (const entry of await readdir(directory, {
    withFileTypes: true,
    recursive: true,
  }))
    if (entry.isFile() && entry.name === "build.json") {
      const folder = entry.parentPath ?? entry.path;
      found.push({
        folder,
        report: JSON.parse(
          await readFile(path.join(folder, "build.json"), "utf8"),
        ),
      });
    }
  return found;
}

/**
 * Select the release files from the workflow reports. Upgrade-test fixtures of
 * another version in the same artifact are ignored.
 */
export async function collectCandidates(directory, version, revision) {
  const assets = [];
  const add = (asset) => {
    assert(
      !assets.some((existing) => existing.name === asset.name),
      `More than one candidate provides ${asset.name}`,
    );
    assets.push(asset);
  };
  const revisions = new Set();
  for (const { folder, report } of await reports(directory)) {
    assert.equal(report.version, version, `Candidate version in ${folder}`);
    assert.equal(report.sourceDirty, false, `${folder} was built from edits`);
    assert.equal(report.identifier, "org.dioptas.desktop");
    revisions.add(report.sourceRevision);
    if (report.dmg) {
      assert.equal(report.notarized, true, `${report.dmg} is not notarized`);
      assert.equal(report.signing, "developer-id");
      const arch = {
        "aarch64-apple-darwin": "aarch64",
        "x86_64-apple-darwin": "x86_64",
      }[report.target];
      assert(arch, `Unexpected macOS target ${report.target}`);
      const archive = report.dmg.replace(/\.dmg$/, ".app.tar.gz");
      const sums = await readFile(path.join(folder, "SHA256SUMS"), "utf8");
      for (const name of [report.dmg, archive]) {
        const expected = sums.match(
          new RegExp(`^([0-9a-f]{64})  ${name.replaceAll(".", "\\.")}$`, "m"),
        )?.[1];
        assert(expected, `${name} is missing from its SHA256SUMS`);
        add({
          name,
          source: path.join(folder, name),
          sha256: expected,
          updater: name === archive ? `darwin-${arch}` : null,
        });
      }
      continue;
    }
    const builds = (report.builds ?? []).filter(
      (build) => build.version === version,
    );
    assert(builds.length, `No ${version} installer in ${folder}`);
    for (const build of builds) {
      const original = path.basename(
        (build.installer ?? build.file).replaceAll("\\", "/"),
      );
      const windows = original.endsWith("-setup.exe");
      const kind = windows ? "nsis" : build.kind;
      assert(["nsis", "deb", "appimage"].includes(kind), `Unknown ${original}`);
      add({
        name: {
          nsis: `Dioptas-Desktop_${version}_windows_x64-setup.exe`,
          deb: `Dioptas-Desktop_${version}_linux_amd64.deb`,
          appimage: `Dioptas-Desktop_${version}_linux_amd64.AppImage`,
        }[kind],
        source: path.join(folder, original),
        sha256: build.sha256,
        updater: windows ? "windows-x86_64" : `linux-x86_64-${kind}`,
      });
    }
  }
  const required = [
    "darwin-aarch64",
    "darwin-x86_64",
    "windows-x86_64",
    "linux-x86_64-appimage",
    "linux-x86_64-deb",
  ];
  for (const target of required)
    assert(
      assets.some((asset) => asset.updater === target),
      `No verified candidate for ${target}`,
    );
  assert.equal(
    revisions.size,
    1,
    `Candidates come from different commits: ${[...revisions].join(", ")}`,
  );
  if (revision)
    assert.equal(
      [...revisions][0],
      revision,
      "Candidates were not built from the commit being released",
    );
  return { assets, revision: [...revisions][0] };
}

export function updaterManifest({ version, notes, date, platforms }) {
  return {
    version,
    notes,
    pub_date: date,
    platforms: Object.fromEntries(
      Object.entries(platforms)
        .sort(([a], [b]) => a.localeCompare(b))
        .map(([target, { name, signature }]) => [
          target,
          {
            signature,
            // A tag-specific URL: this manifest keeps describing this release.
            url: `https://github.com/${repository}/releases/download/${encodeURIComponent(version)}/${encodeURIComponent(name)}`,
          },
        ]),
    ),
  };
}

function sign(file, version) {
  const result = spawnSync(
    process.execPath,
    [
      path.join(desktop, "node_modules/@tauri-apps/cli/tauri.js"),
      "signer",
      "sign",
      "--app-version",
      version,
      file,
    ],
    // The private key and its password are read from the environment by the
    // CLI and never appear in arguments or output.
    { cwd: desktop, encoding: "utf8", stdio: ["ignore", "pipe", "pipe"] },
  );
  assert.equal(
    result.status,
    0,
    `Signing ${path.basename(file)} failed: ${result.stderr.trim().split("\n").at(-1)}`,
  );
  return `${file}.sig`;
}

async function main() {
  const { values } = parseArgs({
    options: {
      candidates: { type: "string" },
      output: { type: "string" },
      revision: { type: "string" },
    },
  });
  assert(values.candidates && values.output, "Use --candidates and --output");
  const { version, releaseConfig } = await import("./release_config.mjs");
  const publicKey = parsePublicKey(releaseConfig.plugins?.updater?.pubkey);
  assert(
    process.env.TAURI_SIGNING_PRIVATE_KEY ||
      process.env.TAURI_SIGNING_PRIVATE_KEY_PATH,
    "Set TAURI_SIGNING_PRIVATE_KEY to sign the update packages",
  );
  const { assets, revision } = await collectCandidates(
    path.resolve(values.candidates),
    version,
    values.revision,
  );
  const output = path.resolve(values.output);
  await mkdir(output, { recursive: true });
  const platforms = {};
  const sums = [];
  for (const asset of assets.sort((a, b) => a.name.localeCompare(b.name))) {
    const target = path.join(output, asset.name);
    await copyFile(asset.source, target);
    const bytes = await readFile(target);
    assert.equal(sha256(bytes), asset.sha256, `${asset.name} changed`);
    sums.push(`${asset.sha256}  ${asset.name}`);
    if (!asset.updater) continue;
    if (asset.updater.startsWith("darwin-")) {
      const listing = spawnSync("tar", ["-tzf", target], {
        encoding: "utf8",
        maxBuffer: 64 * 1024 * 1024,
      });
      assert.equal(listing.status, 0, `Cannot read ${asset.name}`);
      validateAppArchive(listing.stdout);
    }
    // The signature travels inside the manifest, not as a separate download.
    const signed = sign(target, version);
    const signature = (await readFile(signed, "utf8")).trim();
    await rm(signed);
    verifySignature(bytes, signature, publicKey, version);
    platforms[asset.updater] = { name: asset.name, signature };
  }
  let notes = `Dioptas ${version}`;
  try {
    notes =
      releaseNotes(
        await readFile(
          path.join(desktop, "docs", "release", `RELEASE_${version}.md`),
          "utf8",
        ),
      ) || notes;
  } catch (error) {
    if (error.code !== "ENOENT") throw error;
  }
  const manifest = updaterManifest({
    version,
    notes,
    date: new Date().toISOString(),
    platforms,
  });
  await writeFile(
    path.join(output, manifestName),
    JSON.stringify(manifest, null, 2) + "\n",
  );
  await writeFile(path.join(output, "SHA256SUMS"), sums.join("\n") + "\n");
  await writeFile(
    path.join(output, "release.json"),
    JSON.stringify(
      { version, revision, prerelease: isPrerelease(version) },
      null,
      2,
    ) + "\n",
  );
  console.log(
    `Prepared Dioptas ${version} (${revision}): ${assets.length} downloads, ${Object.keys(platforms).length} signed update packages in ${output}`,
  );
}

if (
  process.argv[1] &&
  path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)
)
  await main();
