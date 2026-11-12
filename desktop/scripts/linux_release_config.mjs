import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

export const linuxConfig = JSON.parse(
  readFileSync(
    new URL("../src-tauri/tauri.linux-release.conf.json", import.meta.url),
  ),
);

export function elfMachine(bytes) {
  assert(bytes.length >= 64, "Truncated ELF file");
  assert.equal(
    bytes.subarray(0, 4).toString("hex"),
    "7f454c46",
    "Expected ELF",
  );
  assert.equal(bytes[4], 2, "Expected ELF64");
  assert.equal(bytes[5], 1, "Expected little-endian ELF");
  return bytes.readUInt16LE(18);
}

export function requiredGlibc(listing, ceiling = [2, 35]) {
  const versions = [...listing.matchAll(/\bGLIBC_(\d+)\.(\d+)(?:\.(\d+))?\b/g)]
    .map((m) => m.slice(1).map((v) => Number(v ?? 0)))
    .sort((a, b) => a[0] - b[0] || a[1] - b[1] || a[2] - b[2]);
  const highest = versions.at(-1);
  if (highest)
    assert(
      highest[0] < ceiling[0] ||
        (highest[0] === ceiling[0] && highest[1] <= ceiling[1]),
      `Requires glibc ${highest.join(".")}, above the ${ceiling.join(".")} build baseline`,
    );
  return highest?.join(".") ?? null;
}

export function resolvedDependencies(listing) {
  assert(
    !/=>\s+not found\b/.test(listing),
    `Missing shared library:\n${listing}`,
  );
  const libraries = [
    ...listing.matchAll(/(?:=>\s+|^\s*)(\/[^\s]+)\s+\(/gm),
  ].map((m) => m[1]);
  assert(libraries.length, `No ELF loader/dependency paths found: ${listing}`);
  for (const file of libraries)
    assert(
      !/\/(?:target|worktrees)\/|\/home\/runner\/work\//.test(file),
      `Build-time library dependency: ${file}`,
    );
  return [...new Set(libraries)].sort();
}
