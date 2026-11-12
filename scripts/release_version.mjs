import assert from "node:assert/strict";

// The second installer is a disposable lifecycle fixture, never a release asset.
export function upgradeFixtureVersion(version) {
  const match = /^(\d+)\.(\d+)\.(\d+)(?:-rc\.(\d+))?$/.exec(version);
  assert(match, "Upgrade fixtures require a stable or rc.N semantic version");
  const [, major, minor, patch, candidate] = match;
  return candidate === undefined
    ? `${major}.${minor}.${Number(patch) + 1}`
    : `${major}.${minor}.${patch}-rc.${Number(candidate) + 1}`;
}

export function debianVersion(version) {
  return version.replace("-", "~");
}
