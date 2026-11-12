import assert from "node:assert/strict";
import { mkdtemp, mkdir, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { test } from "node:test";
import { cargoLicenseFiles } from "./prepare_standalone_resources.mjs";

const overridesDirectory = fileURLToPath(
  new URL("../licenses/cargo-overrides", import.meta.url),
);
const overrides = JSON.parse(
  await readFile(path.join(overridesDirectory, "SOURCES.json"), "utf8"),
);
async function fixture(run) {
  const root = await mkdtemp(path.join(tmpdir(), "dioptas-license-resolver-"));
  // Keep the five-level workspace search entirely inside this fixture.
  const directory = path.join(root, "cache/a/b/c/d/e/package");
  await mkdir(directory, { recursive: true });
  const item = {
    name: "fixture",
    version: "1.0.0",
    manifest_path: path.join(directory, "Cargo.toml"),
    source: "registry+https://github.com/rust-lang/crates.io-index",
    license: "MIT",
  };
  try {
    await run({ root, directory, item });
  } finally {
    await rm(root, { recursive: true, force: true });
  }
}

test("SPDX metadata alone never replaces a missing license text", async () =>
  fixture(async ({ item }) => {
    await assert.rejects(
      cargoLicenseFiles(item, overridesDirectory, overrides),
      /Missing license text for fixture 1.0.0/,
    );
  }));

test("all three omitted Linux license archives use exact-version upstream texts and copyright", async () =>
  fixture(async ({ item }) => {
    for (const [name, version, expectedAuthors, count] of [
      [
        "dlopen2",
        "0.8.2",
        ["2017 Szymon Wieloch", "2019 Ahmed Masud", "2022 OpenByte"],
        1,
      ],
      [
        "dlopen2_derive",
        "0.4.3",
        ["2017 Szymon Wieloch", "2019 Ahmed Masud", "2022 OpenByte"],
        1,
      ],
      [
        "libappindicator-sys",
        "0.9.0",
        ["2017-2021 qDot", "2021 Tauri Apps Contributors"],
        2,
      ],
    ]) {
      const resolved = await cargoLicenseFiles(
        { ...item, name, version },
        overridesDirectory,
        overrides,
      );
      assert.equal(resolved.files.length, count);
      assert.equal(resolved.override.length, count);
      const contents = (
        await Promise.all(resolved.files.map((file) => readFile(file, "utf8")))
      ).join("\n");
      for (const author of expectedAuthors)
        assert.ok(contents.includes(author), `${name}: ${author}`);
      for (const record of resolved.override)
        assert.match(
          record.url,
          /^https:\/\/raw\.githubusercontent\.com\/[^/]+\/[^/]+\/[a-f0-9]{40}\//,
        );
      if (name === "libappindicator-sys")
        assert.ok(contents.includes("Version 2.0, January 2004"));
    }
    await assert.rejects(
      cargoLicenseFiles(
        { ...item, name: "dlopen2", version: "0.8.3" },
        overridesDirectory,
        overrides,
      ),
      /Missing license text for dlopen2 0.8.3/,
    );
  }));

test("Windows WebView2 wrappers retain exact-version upstream MIT notices", async () =>
  fixture(async ({ item }) => {
    for (const [name, version] of [
      ["webview2-com", "0.39.1"],
      ["webview2-com-sys", "0.39.1"],
      ["webview2-com-macros", "0.8.1"],
    ]) {
      const result = await cargoLicenseFiles(
        { ...item, name, version },
        overridesDirectory,
        overrides,
      );
      assert.equal(result.files.length, 1);
      assert.match(
        await readFile(result.files[0], "utf8"),
        /Copyright \(c\) 2021 Bill Avery/,
      );
      assert.match(
        result.override[0].url,
        /webview2-rs\/[a-f0-9]{40}\/LICENSE$/,
      );
    }
  }));

test("a modified pinned upstream text fails even when a crate-local license exists", async () =>
  fixture(async ({ root, directory, item }) => {
    const copiedOverrides = path.join(root, "overrides");
    await mkdir(copiedOverrides);
    const record = overrides["dlopen2@0.8.2"][0];
    await writeFile(path.join(copiedOverrides, record.file), "altered license");
    await writeFile(path.join(directory, "LICENSE"), "local license fixture");
    await assert.rejects(
      cargoLicenseFiles(
        { ...item, name: "dlopen2", version: "0.8.2" },
        copiedOverrides,
        overrides,
      ),
      /Changed pinned license text/,
    );
  }));

test("native nested notices and explicit license-file paths remain included", async () =>
  fixture(async ({ directory, item }) => {
    const nested = path.join(directory, "native");
    await mkdir(nested);
    await writeFile(path.join(nested, "NOTICE.txt"), "native fixture notice");
    const explicit = path.join(directory, "Legal.txt");
    await writeFile(explicit, "explicit fixture license");
    const resolved = await cargoLicenseFiles(
      { ...item, license_file: "Legal.txt" },
      overridesDirectory,
      overrides,
    );
    assert.deepEqual(
      resolved.files.sort(),
      [explicit, path.join(nested, "NOTICE.txt")].sort(),
    );
  }));

test("workspace packages still inherit their repository license", async () =>
  fixture(async ({ directory, item }) => {
    const parentLicense = path.join(path.dirname(directory), "LICENSE-MIT");
    await writeFile(parentLicense, "workspace fixture license");
    const resolved = await cargoLicenseFiles(
      { ...item, source: null },
      overridesDirectory,
      overrides,
    );
    assert.deepEqual(resolved.files, [parentLicense]);
  }));
