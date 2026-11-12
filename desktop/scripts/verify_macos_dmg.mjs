// Mount without Finder and test a copied installation. Native UI is opt-in.
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { mkdtemp, mkdir, readdir, readlink, rm } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { inspectStandalone, inspectSignature } from "./inspect_standalone.mjs";
import { desktop, releaseConfig, version } from "./release_config.mjs";

const execute = (command, args) =>
  execFileSync(command, args, {
    encoding: "utf8",
    stdio: ["ignore", "pipe", "pipe"],
    maxBuffer: 8 * 1024 * 1024,
  });

export async function verifyMacosDmg(
  dmg,
  { teamIdentifier, notarized = false, nativeSmoke = false } = {},
) {
  const directory = await mkdtemp(
    path.join(os.tmpdir(), "Dioptas DMG install "),
  );
  const mount = path.join(directory, "mounted");
  let attached = false;
  try {
    await mkdir(mount);
    execute("hdiutil", ["verify", dmg]);
    execute("codesign", ["--verify", "--strict", dmg]);
    const signing = inspectSignature(dmg);
    if (teamIdentifier) {
      assert.equal(
        signing.kind,
        "developer-id",
        "DMG requires Developer ID signing",
      );
      assert.equal(
        signing.teamIdentifier,
        teamIdentifier,
        "Unexpected DMG signing team",
      );
      assert.equal(
        signing.timestamped,
        true,
        "DMG requires a secure timestamp",
      );
    }
    if (notarized) {
      execute("xcrun", ["stapler", "validate", dmg]);
      execute("spctl", [
        "--assess",
        "--type",
        "open",
        "--context",
        "context:primary-signature",
        dmg,
      ]);
    }
    execute("hdiutil", [
      "attach",
      "-readonly",
      "-nobrowse",
      "-mountpoint",
      mount,
      dmg,
    ]);
    attached = true;
    assert.equal(
      await readlink(path.join(mount, "Applications")),
      "/Applications",
    );
    const applications = (await readdir(mount)).filter((name) =>
      name.endsWith(".app"),
    );
    assert.deepEqual(applications, [`${releaseConfig.productName}.app`]);
    const installed = path.join(directory, applications[0]);
    execute("ditto", [path.join(mount, applications[0]), installed]);
    const plist = path.join(installed, "Contents/Info.plist");
    for (const [key, value] of Object.entries({
      CFBundleIdentifier: releaseConfig.identifier,
      CFBundleShortVersionString: version,
    }))
      assert.equal(
        execute("plutil", ["-extract", key, "raw", plist]).trim(),
        value,
      );
    const inspection = await inspectStandalone(installed, { teamIdentifier });
    if (notarized) {
      execute("xcrun", ["stapler", "validate", installed]);
      execute("spctl", ["--assess", "--type", "execute", installed]);
    }
    execute(process.execPath, [
      path.join(desktop, "scripts/standalone_processor_smoke.mjs"),
      installed,
    ]);
    if (nativeSmoke)
      execute(process.execPath, [
        path.join(desktop, "scripts/standalone_smoke.mjs"),
        installed,
        "--preserve-signature",
      ]);
    return {
      headless: !nativeSmoke,
      nativeWebKit: nativeSmoke,
      readOnlyMount: true,
      copiedInstallation: true,
      applicationsLink: true,
      packagedProcessor: true,
      signing,
      notarized,
      inspection,
    };
  } finally {
    // Never recursively remove a mountpoint that failed to detach.
    if (attached) execute("hdiutil", ["detach", mount]);
    await rm(directory, { recursive: true, force: true });
  }
}

if (
  process.argv[1] &&
  path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)
) {
  assert(process.argv[2], "Provide a DMG path");
  console.log(
    JSON.stringify(
      await verifyMacosDmg(path.resolve(process.argv[2]), {
        teamIdentifier: process.env.DIOPTAS_APPLE_TEAM_ID,
        notarized: process.argv.includes("--notarized"),
        nativeSmoke: process.argv.includes("--native-smoke"),
      }),
      null,
      2,
    ),
  );
}
