// Compile positive/negative contract fixtures together with the real frontend.
// @ts-expect-error is checked by tsc, so a widened API fails this gate too.
import assert from "node:assert/strict";
import { readdir, readFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { spawnSync } from "node:child_process";

const desktop = fileURLToPath(new URL("../", import.meta.url));
const root = desktop.replace(/[\\/]$/, "");
const fixtures = path.join(desktop, "scripts/type-fixtures");
const files = (await readdir(fixtures)).filter((file) => file.endsWith(".ts"));
assert.ok(files.length >= 3, "Compile-time contract fixtures must be present.");
const source = await readFile(
  path.join(desktop, "src/commandContracts.ts"),
  "utf8",
);
const contracts = [...source.matchAll(/^  ([a-z_]+): Spec</gm)].map(
  (match) => match[1],
);
assert.ok(
  contracts.length >= 100,
  "The complete frontend command registry must be checked.",
);
assert.equal(
  new Set(contracts).size,
  contracts.length,
  "Command names must be unique.",
);
// Every frontend command must have an actual native or host-mediated handler.
// This is a conservative source inventory of Rust match arms and action
// comparisons, not a Rust parser. Compile fixtures and native/UI gates remain
// authoritative: an unrelated operation with the same name can also match.
const supported = new Set();
async function nativeSources(directory) {
  for (const entry of await readdir(directory, { withFileTypes: true })) {
    const file = path.join(directory, entry.name);
    if (entry.isDirectory()) await nativeSources(file);
    else if (entry.name.endsWith(".rs")) {
      const text = await readFile(file, "utf8");
      for (const match of text.matchAll(/"([a-z_]+)"/g)) {
        // Match arms route command names; the compiler separately checks every
        // active TS callsite, including dynamically forwarded request tuples.
        const suffix = text.slice(
          match.index + match[0].length,
          match.index + match[0].length + 160,
        );
        if (/^\s*(?:\|\s*"[a-z_]+"\s*)*(?:if\s+[^\n{]+)?=>/.test(suffix))
          supported.add(match[1]);
      }
      for (const match of text.matchAll(/action\s*==\s*"([a-z_]+)"/g))
        supported.add(match[1]);
    }
  }
}
await nativeSources(path.join(root, "backend/src"));
await nativeSources(path.join(root, "src-tauri/src"));
for (const command of contracts)
  assert.ok(
    supported.has(command),
    `No native/host route for typed command ${command}`,
  );
// A checked-in project keeps this gate read-only. Creating/removing a tsconfig
// inside a watched Vite project forces a full reload and discards live UI state.
const project = path.join(fixtures, "tsconfig.json");
const result = spawnSync(
  process.execPath,
  [
    path.join(desktop, "node_modules/typescript/bin/tsc"),
    "--noEmit",
    "--project",
    project,
  ],
  {
    cwd: desktop,
    encoding: "utf8",
    maxBuffer: 16 * 1024 * 1024,
    timeout: 120000,
  },
);
if (result.status !== 0 || result.error) {
  process.stdout.write(result.stdout ?? "");
  process.stderr.write(result.stderr ?? "");
  throw (
    result.error ?? new Error("Command payload/result type fixtures failed.")
  );
}
console.log(
  `Checked ${contracts.length} typed command contracts and ${files.length} compile fixtures.`,
);
