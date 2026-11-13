import assert from "node:assert/strict";
import test from "node:test";
import { execFileSync } from "node:child_process";
import { upgradeFixtureVersion, debianVersion } from "./release_version.mjs";

test("upgrade fixtures advance release candidates without changing the release line", () => {
  assert.equal(upgradeFixtureVersion("0.14.0-rc.1"), "0.14.0-rc.2");
  assert.equal(upgradeFixtureVersion("0.14.0-rc.9"), "0.14.0-rc.10");
  assert.equal(upgradeFixtureVersion("0.1.0"), "0.1.1");
  assert.throws(() => upgradeFixtureVersion("0.14.0-beta"));
});

test("Debian release candidates sort before their eventual stable version", () => {
  assert.equal(debianVersion("0.14.0-rc.1"), "0.14.0~rc.1");
  assert.equal(debianVersion("0.14.0"), "0.14.0");
  if (process.platform === "linux") {
    for (const [before, after] of [
      ["0.13.0", "0.14.0-rc.1"],
      ["0.14.0-rc.1", "0.14.0-rc.2"],
      ["0.14.0-rc.2", "0.14.0"],
    ])
      execFileSync("dpkg", [
        "--compare-versions",
        debianVersion(before),
        "lt",
        debianVersion(after),
      ]);
  }
});
