import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { mkdtemp, mkdir, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import test from "node:test";
import {
  collectCandidates,
  isPrerelease,
  parsePublicKey,
  releaseNotes,
  updaterManifest,
  validateAppArchive,
  verifySignature,
} from "./updater_release.mjs";
import { releaseConfig } from "./release_config.mjs";

// A throwaway key pair made only for this vector; its private half was
// discarded. `tauri signer sign --app-version 0.15.0` over the payload below.
const publicKey =
  "dW50cnVzdGVkIGNvbW1lbnQ6IG1pbmlzaWduIHB1YmxpYyBrZXk6IDdCQUFEOEY2QTYzNjkwMTIKUldRU2tEYW05dGlxZXhBbWZHQm5COUtic0NscGFMMnQ3d0NMOWU3VGJVdjhxbDNDcTdYMWVMQjEK";
const signature =
  "dW50cnVzdGVkIGNvbW1lbnQ6IHNpZ25hdHVyZSBmcm9tIHRhdXJpIHNlY3JldCBrZXkKUlVRU2tEYW05dGlxZTFJZnhPbUV0WWY4a1p0ME5qdGFFMys3MTRzeWpWM3dwalh4blN0cjhpK2VkdmtOVXA4elpkNzFvTS9ReGlzQUZjTEpjSVZxVUtSWDAyNjQwQXZWU2dRPQp0cnVzdGVkIGNvbW1lbnQ6IHRpbWVzdGFtcDoxNzk0NTAzMzU5CWZpbGU6dmVjdG9yLmJpbgl2ZXJzaW9uOjAuMTUuMAp1WlQ5YlQ4bDI0VkNiK2ZESXlsdWRxT21KVEdNODB0dGhUdzlzeVpBTjROeElBN1FYa3FFajAxMHdCS1lHMkc3ZjNBRTBNTEdsNHljd3B4L1pJbFBCUT09Cg==";
const payload = Buffer.from("dioptas-update-test");

test("update signatures are checked as an installed application checks them", () => {
  const key = parsePublicKey(publicKey);
  assert.match(
    verifySignature(payload, signature, key, "0.15.0").comment,
    /version:0\.15\.0$/,
  );
  // A different file, a different announced version and a different key fail.
  assert.throws(
    () => verifySignature(Buffer.from("tampered"), signature, key, "0.15.0"),
    /does not match the file/,
  );
  assert.throws(
    () => verifySignature(payload, signature, key, "0.16.0"),
    /bound to the released version/,
  );
  assert.throws(
    () =>
      verifySignature(
        payload,
        signature,
        { ...key, keyId: Buffer.alloc(8) },
        "0.15.0",
      ),
    /different key/,
  );
  const other = { ...key, key: Buffer.alloc(32, 7) };
  assert.throws(() => verifySignature(payload, signature, other, "0.15.0"));
  assert.throws(() => parsePublicKey(""), /No update verification key/);
  assert.throws(() => parsePublicKey("bm90IGEga2V5"), /not a minisign/);
});

test("the release configuration updates only from signed GitHub releases", () => {
  const updater = releaseConfig.plugins.updater;
  assert.deepEqual(updater.endpoints, [
    "https://github.com/Dioptas/Dioptas/releases/latest/download/latest.json",
  ]);
  // The manifest itself is unsigned; binding the version to the signature
  // prevents it from announcing an older package as a newer release.
  assert.equal(updater.requireSignedVersion, true);
  assert.notEqual(updater.allowDowngrades, true);
  for (const key of Object.keys(updater))
    assert(!key.startsWith("dangerous"), `${key} must stay off`);
  // Empty until the project key exists: such builds do not offer updates.
  if (updater.pubkey) parsePublicKey(updater.pubkey);
  // Signing happens after notarization, in updater_release.mjs.
  assert.equal(releaseConfig.bundle.createUpdaterArtifacts, false);
  const preview = JSON.parse(
    readFileSync(new URL("../src-tauri/tauri.conf.json", import.meta.url)),
  );
  assert.equal(preview.plugins?.updater, undefined);
});

test("update notes are the introduction of the release document", () => {
  assert.equal(
    releaseNotes(
      "# Dioptas 0.15.0\n\nFaster maps and\nnew masks.\n\nSecond paragraph.\n\n## Downloads\n\n| a | b |\n",
    ),
    "Faster maps and new masks.\n\nSecond paragraph.",
  );
  assert.equal(releaseNotes("# Title only\n"), "");
  assert.equal(isPrerelease("0.14.0-rc.1"), true);
  assert.equal(isPrerelease("0.14.0"), false);
});

test("the manifest names every platform with tag-specific downloads", () => {
  const manifest = updaterManifest({
    version: "0.15.0",
    notes: "Notes",
    date: "2026-11-12T12:00:00.000Z",
    platforms: {
      "windows-x86_64": {
        name: "Dioptas-Desktop_0.15.0_windows_x64-setup.exe",
        signature: "w",
      },
      "darwin-aarch64": {
        name: "Dioptas-Desktop_0.15.0_macos_arm64.app.tar.gz",
        signature: "m",
      },
    },
  });
  assert.deepEqual(Object.keys(manifest.platforms), [
    "darwin-aarch64",
    "windows-x86_64",
  ]);
  assert.equal(
    manifest.platforms["darwin-aarch64"].url,
    "https://github.com/Dioptas/Dioptas/releases/download/0.15.0/Dioptas-Desktop_0.15.0_macos_arm64.app.tar.gz",
  );
  assert.equal(manifest.platforms["windows-x86_64"].signature, "w");
  assert.equal(manifest.version, "0.15.0");
  assert.equal(manifest.pub_date, "2026-11-12T12:00:00.000Z");
});

const digest = (text) => createHash("sha256").update(text).digest("hex");
async function candidates(version, change = () => {}) {
  const root = await mkdtemp(path.join(tmpdir(), "dioptas-release-"));
  const common = {
    version,
    identifier: "org.dioptas.desktop",
    sourceRevision: "a".repeat(40),
    sourceDirty: false,
  };
  const reports = {};
  for (const [arch, target] of [
    ["arm64", "aarch64-apple-darwin"],
    ["x64", "x86_64-apple-darwin"],
  ]) {
    const folder = path.join(root, `mac-${arch}`, `${version}-${target}-x`);
    await mkdir(folder, { recursive: true });
    const base = `Dioptas-Desktop_${version}_macos_${arch}`;
    await writeFile(path.join(folder, `${base}.dmg`), `dmg-${arch}`);
    await writeFile(path.join(folder, `${base}.app.tar.gz`), `app-${arch}`);
    await writeFile(
      path.join(folder, "SHA256SUMS"),
      `${digest(`dmg-${arch}`)}  ${base}.dmg\n${digest(`app-${arch}`)}  ${base}.app.tar.gz\n`,
    );
    reports[`mac-${arch}`] = [
      folder,
      {
        ...common,
        target,
        signing: "developer-id",
        notarized: true,
        dmg: `${base}.dmg`,
      },
    ];
  }
  const windows = path.join(root, "windows", "run");
  await mkdir(windows, { recursive: true });
  const setup = `Dioptas_${version}_x64-setup.exe`;
  await writeFile(path.join(windows, setup), "setup");
  await writeFile(path.join(windows, "Dioptas_9.9.9_x64-setup.exe"), "fixture");
  reports.windows = [
    windows,
    {
      ...common,
      target: "x86_64-pc-windows-msvc",
      builds: [
        {
          version,
          installer: `D:\\a\\Dioptas\\desktop\\artifacts\\native-windows\\run\\${setup}`,
          sha256: digest("setup"),
        },
        // The upgrade-test fixture of a later version is not a release file.
        {
          version: "9.9.9",
          installer: "D:\\x\\Dioptas_9.9.9_x64-setup.exe",
          sha256: digest("fixture"),
        },
      ],
    },
  ];
  for (const [kind, file] of [
    ["deb", `Dioptas_${version}_amd64.deb`],
    ["appimage", `Dioptas_${version}_amd64.AppImage`],
  ]) {
    const folder = path.join(root, `linux-${kind}`, "run");
    await mkdir(folder, { recursive: true });
    await writeFile(path.join(folder, file), kind);
    reports[`linux-${kind}`] = [
      folder,
      {
        ...common,
        format: kind,
        builds: [{ version, kind, file, sha256: digest(kind) }],
      },
    ];
  }
  change(reports);
  for (const [folder, report] of Object.values(reports))
    await writeFile(path.join(folder, "build.json"), JSON.stringify(report));
  return root;
}

test("verified candidates become public downloads and update targets", async () => {
  const root = await candidates("0.15.0");
  try {
    const { assets, revision } = await collectCandidates(
      root,
      "0.15.0",
      "a".repeat(40),
    );
    assert.equal(revision, "a".repeat(40));
    assert.deepEqual(assets.map((asset) => asset.name).sort(), [
      "Dioptas-Desktop_0.15.0_linux_amd64.AppImage",
      "Dioptas-Desktop_0.15.0_linux_amd64.deb",
      "Dioptas-Desktop_0.15.0_macos_arm64.app.tar.gz",
      "Dioptas-Desktop_0.15.0_macos_arm64.dmg",
      "Dioptas-Desktop_0.15.0_macos_x64.app.tar.gz",
      "Dioptas-Desktop_0.15.0_macos_x64.dmg",
      "Dioptas-Desktop_0.15.0_windows_x64-setup.exe",
    ]);
    assert.deepEqual(
      assets
        .map((asset) => asset.updater)
        .filter(Boolean)
        .sort(),
      [
        "darwin-aarch64",
        "darwin-x86_64",
        "linux-x86_64-appimage",
        "linux-x86_64-deb",
        "windows-x86_64",
      ],
    );
    // Disk images are downloads only; the application archive is the update.
    assert.equal(
      assets.find((asset) => asset.name.endsWith("arm64.dmg")).updater,
      null,
    );
    const installer = assets.find(
      (asset) => asset.updater === "windows-x86_64",
    );
    assert.equal(
      path.basename(installer.source),
      "Dioptas_0.15.0_x64-setup.exe",
    );
    assert.equal(installer.sha256, digest("setup"));
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});

test("incomplete, mixed, unnotarized or edited candidates are not released", async () => {
  for (const [change, message] of [
    [
      (r) => delete r["linux-appimage"],
      /No verified candidate for linux-x86_64-appimage/,
    ],
    [(r) => (r["mac-x64"][1].notarized = false), /not notarized/],
    [(r) => (r.windows[1].sourceDirty = true), /built from edits/],
    [
      (r) => (r["linux-deb"][1].sourceRevision = "b".repeat(40)),
      /different commits/,
    ],
    [(r) => (r["mac-arm64"][1].version = "0.15.1"), /Candidate version/],
  ]) {
    const root = await candidates("0.15.0", change);
    try {
      await assert.rejects(collectCandidates(root, "0.15.0"), message);
    } finally {
      await rm(root, { recursive: true, force: true });
    }
  }
  const root = await candidates("0.15.0");
  try {
    await assert.rejects(
      collectCandidates(root, "0.15.0", "c".repeat(40)),
      /not built from the commit being released/,
    );
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});

test("macOS update archives hold exactly one application bundle", () => {
  const app = [
    "Dioptas.app/",
    "Dioptas.app/Contents/",
    "Dioptas.app/Contents/Info.plist",
    "Dioptas.app/Contents/MacOS/dioptas-desktop",
  ];
  assert.equal(validateAppArchive(app.join("\n") + "\n"), "Dioptas.app");
  assert.throws(
    () => validateAppArchive(["._Dioptas.app", ...app].join("\n")),
    /One application expected/,
  );
  assert.throws(
    () => validateAppArchive(app.slice(0, 3).join("\n")),
    /lacks Contents\/MacOS/,
  );
  assert.throws(
    () => validateAppArchive("Contents/Info.plist\nContents/MacOS/x"),
    /One application expected|Unexpected archive root/,
  );
});
