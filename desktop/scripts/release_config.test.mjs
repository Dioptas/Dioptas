import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import {
  buildEnvironment,
  signatureDetails,
  requireDeveloperId,
  releaseConfig,
  version,
} from "./release_config.mjs";

test("release identity is separate from previews and retains the complete main-window configuration", () => {
  const preview = JSON.parse(
    readFileSync(new URL("../src-tauri/tauri.conf.json", import.meta.url)),
  );
  assert.notEqual(releaseConfig.identifier, preview.identifier);
  assert.notEqual(releaseConfig.identifier, "com.dioptas.Dioptas");
  assert.equal(preview.version, "../package.json");
  assert.match(version, /^\d+\.\d+\.\d+/);
  assert.deepEqual(
    { ...releaseConfig.app.windows[0], title: preview.app.windows[0].title },
    preview.app.windows[0],
  );
  assert.equal(releaseConfig.bundle.createUpdaterArtifacts, false);
});

test("build environment prevents implicit Apple submission without mutating the caller", () => {
  const source = {
    APPLE_ID: "test",
    APPLE_PASSWORD: "test",
    APPLE_API_KEY: "test",
    APPLE_CERTIFICATE: "test",
    PATH: "/test",
  };
  const env = buildEnvironment(source, "certificate-hash");
  assert.equal(env.APPLE_ID, undefined);
  assert.equal(env.APPLE_PASSWORD, undefined);
  assert.equal(env.APPLE_API_KEY, undefined);
  assert.equal(env.APPLE_CERTIFICATE, undefined);
  assert.equal(env.APPLE_SIGNING_IDENTITY, "certificate-hash");
  assert.equal(env.PATH, source.PATH);
  assert.equal(source.APPLE_PASSWORD, "test");
});

test("release inspection rejects ad-hoc, wrong-team, untimestamped and unhardened binaries", () => {
  const details =
    "Authority=Developer ID Application: Test (ABCDEFGHIJ)\nTeamIdentifier=ABCDEFGHIJ\nCodeDirectory v=20500 flags=0x10000(runtime) hashes=2\nTimestamp=Nov 11, 2026\n";
  const valid = signatureDetails(details);
  requireDeveloperId(valid, "ABCDEFGHIJ");
  for (const invalid of [
    signatureDetails("Signature=adhoc\nTeamIdentifier=not set\n"),
    { ...valid, teamIdentifier: "KLMNOPQRST" },
    { ...valid, hardenedRuntime: false },
    { ...valid, timestamped: false },
  ])
    assert.throws(() => requireDeveloperId(invalid, "ABCDEFGHIJ"));
});
