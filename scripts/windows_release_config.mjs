import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

export const windowsConfig = JSON.parse(
  readFileSync(
    new URL("../src-tauri/tauri.windows-release.conf.json", import.meta.url),
  ),
);

export function windowsSigning(unsigned, environment) {
  if (unsigned) return { certificateThumbprint: null, signCommand: null };
  const thumbprint = environment.DIOPTAS_WINDOWS_SIGNER_THUMBPRINT;
  assert.match(
    thumbprint || "",
    /^[a-fA-F0-9]{40}$/,
    "Set DIOPTAS_WINDOWS_SIGNER_THUMBPRINT for signed builds, or explicitly use --unsigned",
  );
  return {
    certificateThumbprint: environment.DIOPTAS_WINDOWS_SIGN_COMMAND
      ? null
      : thumbprint,
    signCommand: environment.DIOPTAS_WINDOWS_SIGN_COMMAND || null,
    digestAlgorithm: "sha256",
    timestampUrl:
      environment.DIOPTAS_WINDOWS_TIMESTAMP_URL ||
      "http://timestamp.digicert.com",
    tsp: true,
  };
}

export function peMachine(bytes) {
  assert(
    bytes.length >= 64 && bytes.readUInt16LE(0) === 0x5a4d,
    "Missing DOS executable header",
  );
  const offset = bytes.readUInt32LE(0x3c);
  assert(
    offset + 6 <= bytes.length && bytes.readUInt32LE(offset) === 0x4550,
    "Missing PE executable header",
  );
  return bytes.readUInt16LE(offset + 4);
}

export function importLocation(name, localNames, systemExists) {
  const lower = name.toLowerCase();
  if (localNames.has(lower)) return "application";
  assert(
    !/^(vcruntime|msvcp|concrt|vcomp)\d.*\.dll$/.test(lower),
    `Visual C++ runtime must be bundled: ${name}`,
  );
  if (/^(api-ms-|ext-ms-)/.test(lower)) return "windows-api-set";
  assert(systemExists, `Unbundled native dependency: ${name}`);
  return "windows-system";
}
