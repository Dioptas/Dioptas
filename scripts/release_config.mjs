import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

export const desktop = fileURLToPath(new URL("../", import.meta.url));
export const releaseConfig = JSON.parse(
  readFileSync(
    new URL("../src-tauri/tauri.release.conf.json", import.meta.url),
  ),
);
export const version = JSON.parse(
  readFileSync(new URL("../package.json", import.meta.url)),
).version;
assert.match(
  version,
  /^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?$/,
  "Use a filename-safe semantic version",
);

export function signatureDetails(details) {
  return {
    kind: details.includes("Authority=Developer ID Application:")
      ? "developer-id"
      : details.includes("Signature=adhoc")
        ? "ad-hoc"
        : "other",
    teamIdentifier: details.match(/^TeamIdentifier=(.+)$/m)?.[1] ?? null,
    hardenedRuntime: /flags=.*\bruntime\b/.test(details),
    timestamped: /^Timestamp=.+/m.test(details),
  };
}

export function requireDeveloperId(signature, teamIdentifier) {
  assert.equal(
    signature.kind,
    "developer-id",
    "Expected a Developer ID Application signature",
  );
  assert.equal(
    signature.teamIdentifier,
    teamIdentifier,
    "Unexpected Apple team",
  );
  assert.equal(signature.hardenedRuntime, true, "Missing hardened runtime");
  assert.equal(signature.timestamped, true, "Missing secure signing timestamp");
}

// Notarize explicitly after testing the signed app. Do not let Tauri submit
// implicitly or accidentally use a developer's unrelated Apple credentials.
export function buildEnvironment(environment, identity) {
  const env = {
    ...environment,
    MACOSX_DEPLOYMENT_TARGET: "14.0",
    APPLE_SIGNING_IDENTITY: identity,
  };
  for (const key of [
    "APPLE_ID",
    "APPLE_PASSWORD",
    "APPLE_TEAM_ID",
    "APPLE_API_KEY",
    "APPLE_API_ISSUER",
    "APPLE_API_KEY_PATH",
    "APPLE_CERTIFICATE",
    "APPLE_CERTIFICATE_PASSWORD",
  ])
    delete env[key];
  return env;
}
