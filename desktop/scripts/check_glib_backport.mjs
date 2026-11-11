// Keep a vendored security fix accountable without hiding the registry base from
// advisory databases. Normal checks are offline; --advisories explicitly queries
// https://google.github.io/osv.dev/post-v1-query/ for the original published crate.
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFile, readdir } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const root = fileURLToPath(new URL("../../", import.meta.url));
const sha256 = (value) => createHash("sha256").update(value).digest("hex");
const expected = Object.freeze({
  crate: "glib",
  version: "0.18.5",
  registryUrl: "https://static.crates.io/crates/glib/glib-0.18.5.crate",
  registrySha256:
    "233daaf6e83ae6a12a52055f568f9d7cf4671dabb78ff9560ab6da230ce00ee5",
  registryBaseCommit: "42b9caf98e03ded086362d9653ca58fe94dc8658",
  upstreamPr: "https://github.com/gtk-rs/gtk-rs-core/pull/1343",
  upstreamFixCommit: "b5a4071e439bef2b5eea76c3aa25e5ae84839e34",
  backportCommit: "ea720152f28e293ef4362ee844ee5cc499f32d2a",
});
// Digest of the sorted path/hash inventory from the verified published archive.
// Updating this anchor requires reviewing the original crate and exact patch.
const originalFilesSha256 =
  "110262bc9fd6e0096f3d5f99e70d4e368176dc9abdc61a89368c2798c5917222";
const coveredIds = new Set(["RUSTSEC-2024-0429", "GHSA-wrw7-89jp-8q8g"]);
const changes = [
  {
    path: "src/variant_iter.rs",
    from: "            let p: *mut libc::c_char = std::ptr::null_mut();",
    to: "            let mut p: *mut libc::c_char = std::ptr::null_mut();",
  },
  {
    path: "src/variant_iter.rs",
    from: "                &p,",
    to: "                &mut p,",
  },
];
async function inventory(directory, prefix = "") {
  const files = [];
  for (const entry of await readdir(directory, { withFileTypes: true })) {
    const name = prefix + entry.name;
    if (entry.isDirectory())
      files.push(
        ...(await inventory(path.join(directory, entry.name), name + "/")),
      );
    else {
      assert.ok(
        entry.isFile(),
        `Unexpected non-regular vendored entry: ${name}`,
      );
      files.push(name);
    }
  }
  return files.sort();
}
function occurrences(text, fragment) {
  return text.split(fragment).length - 1;
}
export async function verifyBackport(repository = root) {
  const vendor = path.join(repository, "desktop/vendor/glib");
  const metadata = JSON.parse(
    await readFile(path.join(vendor, "SECURITY_BACKPORT.json"), "utf8"),
  );
  for (const [key, value] of Object.entries(expected))
    assert.equal(metadata[key], value, `Unexpected GLib provenance ${key}`);
  assert.deepEqual(
    metadata.sourceChanges,
    changes,
    "Only the reviewed upstream two-line fix is covered",
  );
  const files = Object.entries(metadata.originalFiles ?? {}).sort(([a], [b]) =>
    a < b ? -1 : a > b ? 1 : 0,
  );
  assert.equal(
    sha256(JSON.stringify(files)),
    originalFilesSha256,
    "Published GLib source inventory changed",
  );
  assert.deepEqual(
    await inventory(vendor),
    [...files.map(([file]) => file), "SECURITY_BACKPORT.json"].sort(),
    "Vendored GLib files must match the complete published archive plus provenance",
  );
  for (const [file, checksum] of files) {
    assert.ok(
      !file.startsWith("/") && !file.split("/").includes(".."),
      "Unsafe provenance path",
    );
    let bytes = await readFile(path.join(vendor, file));
    const edits = changes.filter((change) => change.path === file);
    if (edits.length) {
      let text = bytes.toString("utf8");
      for (const edit of edits) {
        assert.equal(
          occurrences(text, edit.from),
          0,
          `Unpatched GLib line in ${file}`,
        );
        assert.equal(
          occurrences(text, edit.to),
          1,
          `Expected one reviewed GLib replacement in ${file}`,
        );
        text = text.replace(edit.to, edit.from);
      }
      bytes = Buffer.from(text);
    }
    assert.equal(
      sha256(bytes),
      checksum,
      `Unexpected vendored GLib change: ${file}`,
    );
  }
  const vcs = JSON.parse(
    await readFile(path.join(vendor, ".cargo_vcs_info.json"), "utf8"),
  );
  assert.equal(vcs.git.sha1, expected.registryBaseCommit);
  const manifest = await readFile(
    path.join(repository, "desktop/src-tauri/Cargo.toml"),
    "utf8",
  );
  const patches = manifest.match(
    /\[patch\.crates-io\]([\s\S]*?)(?=\n\[|$)/,
  )?.[1];
  assert.match(
    patches ?? "",
    /^glib\s*=\s*\{\s*path\s*=\s*"\.\.\/vendor\/glib"\s*\}/m,
    "Tauri must use the reviewed local GLib source",
  );
  const lock = await readFile(
    path.join(repository, "desktop/src-tauri/Cargo.lock"),
    "utf8",
  );
  const glib = lock
    .split("[[package]]")
    .filter((entry) => /^\s*name = "glib"$/m.test(entry));
  assert.equal(
    glib.length,
    1,
    "Review any additional GLib version before changing the guard",
  );
  assert.match(glib[0], /^version = "0\.18\.5"$/m);
  assert.doesNotMatch(
    glib[0],
    /^(source|checksum)\s*=/m,
    "Tauri still resolves registry GLib instead of the patched source",
  );
  return metadata;
}

/** Both OSV records for the one corrected issue remain visible in output. A new
 * ID or alias fails even if it claims an alias to the backported advisory. */
export function verifyAdvisories(vulnerabilities) {
  assert.ok(Array.isArray(vulnerabilities), "Malformed OSV vulnerability list");
  const reviewed = [];
  for (const vulnerability of vulnerabilities) {
    assert.equal(typeof vulnerability.id, "string", "OSV advisory has no id");
    const aliases = vulnerability.aliases ?? [];
    assert.ok(
      Array.isArray(aliases) &&
        aliases.every((alias) => typeof alias === "string"),
      "Malformed OSV aliases",
    );
    assert.ok(
      coveredIds.has(vulnerability.id) &&
        aliases.every((alias) => coveredIds.has(alias)),
      `Unreviewed GLib ${expected.version} advisory: ${vulnerability.id} (${aliases.join(", ")})`,
    );
    assert.ok(
      vulnerability.affected?.some(
        (affected) =>
          affected.package?.name === expected.crate &&
          affected.package.ecosystem === "crates.io",
      ),
      `Advisory ${vulnerability.id} did not identify the queried GLib package`,
    );
    reviewed.push(vulnerability.id);
  }
  return [...new Set(reviewed)].sort();
}
async function queryPage(payload, fetcher) {
  let failure;
  for (let attempt = 0; attempt < 3; attempt++) {
    try {
      const response = await fetcher("https://api.osv.dev/v1/query", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
        signal: AbortSignal.timeout(15000),
      });
      assert.ok(response.ok, `OSV query failed with HTTP ${response.status}`);
      const body = await response.text();
      assert.ok(
        Buffer.byteLength(body) <= 4 * 1024 * 1024,
        "OSV response exceeds 4 MiB",
      );
      return JSON.parse(body);
    } catch (error) {
      failure = error;
      if (attempt < 2)
        await new Promise((resolve) =>
          setTimeout(resolve, 500 * (attempt + 1)),
        );
    }
  }
  throw new Error(
    "Could not check live GLib advisories after three bounded attempts",
    { cause: failure },
  );
}
export async function queryAdvisories(fetcher = fetch) {
  const vulnerabilities = [];
  let pageToken;
  for (let page = 0; page < 10; page++) {
    const body = await queryPage(
      {
        package: { name: expected.crate, ecosystem: "crates.io" },
        version: expected.version,
        ...(pageToken ? { page_token: pageToken } : {}),
      },
      fetcher,
    );
    assert.ok(
      body && typeof body === "object" && !Array.isArray(body),
      "Malformed OSV response",
    );
    assert.ok(
      Object.keys(body).every((key) =>
        ["vulns", "next_page_token"].includes(key),
      ),
      "Unexpected OSV response fields; refusing to assume a clean result",
    );
    assert.ok(
      body.vulns === undefined || Array.isArray(body.vulns),
      "Malformed OSV vulnerability list",
    );
    vulnerabilities.push(...(body.vulns ?? []));
    if (!body.next_page_token) return vulnerabilities;
    assert.equal(
      typeof body.next_page_token,
      "string",
      "Malformed OSV pagination token",
    );
    assert.notEqual(
      body.next_page_token,
      pageToken,
      "OSV repeated its pagination token",
    );
    pageToken = body.next_page_token;
  }
  throw Error(
    "OSV advisory query exceeded ten pages; review the complete response",
  );
}
export async function checkBackport({
  repository = root,
  advisories = false,
  fetcher = fetch,
} = {}) {
  const metadata = await verifyBackport(repository);
  console.log(
    `Verified exact upstream GLib ${metadata.version} backport and published-source provenance.`,
  );
  if (advisories) {
    const reviewed = verifyAdvisories(await queryAdvisories(fetcher));
    console.log(
      `Live OSV query for registry glib ${metadata.version}: ${reviewed.join(", ") || "no advisories"}.`,
    );
    console.log(
      "Only the source-verified VariantStrIter backport is covered; any new advisory fails this check.",
    );
  }
}
if (
  process.argv[1] &&
  import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href
) {
  assert.ok(
    process.argv.slice(2).every((arg) => arg === "--advisories"),
    "Use check_glib_backport.mjs [--advisories]",
  );
  await checkBackport({ advisories: process.argv.includes("--advisories") });
}
