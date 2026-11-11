import assert from "node:assert/strict";
import { cp, mkdtemp, mkdir, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { test } from "node:test";
import {
  checkBackport,
  queryAdvisories,
  verifyAdvisories,
  verifyBackport,
} from "./check_glib_backport.mjs";

const source = fileURLToPath(new URL("../vendor/glib", import.meta.url));
async function fixture(run) {
  const directory = await mkdtemp(path.join(tmpdir(), "dioptas-glib-guard-"));
  try {
    await cp(source, path.join(directory, "desktop/vendor/glib"), {
      recursive: true,
    });
    await mkdir(path.join(directory, "desktop/src-tauri"), { recursive: true });
    await writeFile(
      path.join(directory, "desktop/src-tauri/Cargo.toml"),
      '[patch.crates-io]\nglib = { path = "../vendor/glib" }\n',
    );
    await writeFile(
      path.join(directory, "desktop/src-tauri/Cargo.lock"),
      '[[package]]\nname = "glib"\nversion = "0.18.5"\n',
    );
    await run(directory, path.join(directory, "desktop/vendor/glib"));
  } finally {
    await rm(directory, { recursive: true, force: true });
  }
}
const known = (
  id = "RUSTSEC-2024-0429",
  aliases = ["GHSA-wrw7-89jp-8q8g"],
) => ({
  id,
  aliases,
  affected: [{ package: { name: "glib", ecosystem: "crates.io" } }],
});
const response = (value, status = 200) =>
  new Response(JSON.stringify(value), { status });

test("the complete published crate plus the exact fix passes offline with unchanged version", async () =>
  fixture(async (directory) => {
    let network = 0;
    await checkBackport({
      repository: directory,
      fetcher: () => {
        network++;
        throw Error("Unexpected network");
      },
    });
    assert.equal(network, 0);
  }));

test("restoring either unsound source line fails before advisory permission", async () => {
  for (let index = 0; index < 2; index++)
    await fixture(async (directory, vendor) => {
      const metadata = JSON.parse(
        await readFile(path.join(vendor, "SECURITY_BACKPORT.json"), "utf8"),
      );
      const edit = metadata.sourceChanges[index];
      const sourceFile = path.join(vendor, edit.path);
      await writeFile(
        sourceFile,
        (await readFile(sourceFile, "utf8")).replace(edit.to, edit.from),
      );
      let queried = false;
      await assert.rejects(
        checkBackport({
          repository: directory,
          advisories: true,
          fetcher: () => {
            queried = true;
            throw Error("must not query");
          },
        }),
        /Unpatched GLib line|reviewed GLib replacement/,
      );
      assert.equal(queried, false);
    });
});

test("unrelated edits, extra source, and a rewritten checksum manifest fail", async () => {
  await fixture(async (directory, vendor) => {
    await writeFile(path.join(vendor, "src/lib.rs"), "// unexpected edit\n", {
      flag: "a",
    });
    await assert.rejects(
      verifyBackport(directory),
      /Unexpected vendored GLib change/,
    );
  });
  await fixture(async (directory, vendor) => {
    await writeFile(path.join(vendor, "unreviewed.rs"), "// extra file");
    await assert.rejects(
      verifyBackport(directory),
      /complete published archive/,
    );
  });
  await fixture(async (directory, vendor) => {
    const file = path.join(vendor, "SECURITY_BACKPORT.json");
    const metadata = JSON.parse(await readFile(file, "utf8"));
    metadata.originalFiles["src/lib.rs"] = "0".repeat(64);
    await writeFile(file, JSON.stringify(metadata));
    await assert.rejects(verifyBackport(directory), /source inventory changed/);
  });
});

test("a registry-resolved GLib cannot pass the backport guard", async () =>
  fixture(async (directory) => {
    await writeFile(
      path.join(directory, "desktop/src-tauri/Cargo.lock"),
      '[[package]]\nname = "glib"\nversion = "0.18.5"\nsource = "registry+https://github.com/rust-lang/crates.io-index"\n',
    );
    await assert.rejects(
      verifyBackport(directory),
      /still resolves registry GLib/,
    );
  }));

test("only the two identities of the actual corrected advisory are covered", () => {
  assert.deepEqual(
    verifyAdvisories([
      known(),
      known("GHSA-wrw7-89jp-8q8g", ["RUSTSEC-2024-0429"]),
    ]),
    ["GHSA-wrw7-89jp-8q8g", "RUSTSEC-2024-0429"],
  );
  assert.throws(
    () => verifyAdvisories([known("RUSTSEC-2099-0001", ["RUSTSEC-2024-0429"])]),
    /Unreviewed GLib/,
  );
  assert.throws(
    () => verifyAdvisories([known("RUSTSEC-2024-0429", ["CVE-2099-12345"])]),
    /Unreviewed GLib/,
  );
  assert.throws(
    () => verifyAdvisories([{ ...known(), affected: [] }]),
    /did not identify/,
  );
  assert.throws(() => verifyAdvisories([{}]), /no id/);
});

test("OSV always sees the registry base version and all paginated results", async () => {
  const requests = [];
  const advisories = await queryAdvisories(async (url, options) => {
    assert.equal(url, "https://api.osv.dev/v1/query");
    assert.ok(options.signal instanceof AbortSignal);
    const query = JSON.parse(options.body);
    requests.push(query);
    return response(
      requests.length === 1
        ? { vulns: [known()], next_page_token: "next" }
        : { vulns: [known("GHSA-wrw7-89jp-8q8g", [])] },
    );
  });
  assert.equal(advisories.length, 2);
  assert.equal(requests.length, 2);
  for (const request of requests)
    assert.deepEqual(
      { package: request.package, version: request.version },
      { package: { name: "glib", ecosystem: "crates.io" }, version: "0.18.5" },
    );
  assert.equal(requests[1].page_token, "next");
});

test("live checks retry transient failures but never treat service failure as clean", async () => {
  let attempts = 0;
  await assert.rejects(
    queryAdvisories(async () => {
      attempts++;
      return response({ message: "unavailable" }, 503);
    }),
    /three bounded attempts/,
  );
  assert.equal(attempts, 3);
  await assert.rejects(
    queryAdvisories(async () => response({ vulns: "not an array" })),
    /Malformed OSV vulnerability list/,
  );
  await assert.rejects(
    queryAdvisories(async () => response({ error: "service failure" })),
    /Unexpected OSV response fields/,
  );
  assert.deepEqual(await queryAdvisories(async () => response({})), []);
});
