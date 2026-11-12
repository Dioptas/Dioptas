// Prevent legacy functional cases and native evidence from silently falling out
// of the inventory. This checks traceability, not scientific equivalence itself.
import assert from "node:assert/strict";
import { readFile, mkdir, writeFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import path from "node:path";

const root = fileURLToPath(new URL("../../", import.meta.url));
// Frozen inventory from the archived source; the executable Qt suite lives on legacy/qt.
const archived = JSON.parse(
  await readFile(
    path.join(root, "desktop/legacy_functional_inventory.json"),
    "utf8",
  ),
);
assert.match(archived.sourceRevision, /^[a-f0-9]{40}$/);
const inventory = new Set(archived.cases);
const mapping = JSON.parse(
  await readFile(path.join(root, "desktop/functional_coverage.json"), "utf8"),
);
const seen = new Set();
const counts = {};
for (const entry of mapping.cases) {
  assert(
    inventory.has(entry.legacy),
    `Unknown/renamed legacy case: ${entry.legacy}`,
  );
  assert(!seen.has(entry.legacy), `Duplicate legacy case: ${entry.legacy}`);
  seen.add(entry.legacy);
  assert(
    [
      "native",
      "headless-ui",
      "adapted",
      "unsupported",
      "platform-specific",
    ].includes(entry.status),
    entry.legacy,
  );
  assert(entry.note?.trim(), `Explain the actual boundary for ${entry.legacy}`);
  if (["native", "headless-ui", "adapted"].includes(entry.status))
    assert(entry.evidence.length, entry.legacy);
  for (const reference of entry.evidence) {
    const [file, symbol] = reference.split("#");
    assert(file.startsWith("desktop/"), reference);
    const content = await readFile(path.join(root, file), "utf8");
    if (symbol)
      assert(
        new RegExp(`\\bfn\\s+${symbol}\\s*\\(`).test(content),
        `Missing native test: ${reference}`,
      );
    if (entry.status === "native")
      assert(symbol && file.startsWith("desktop/backend/tests/"), reference);
  }
  counts[entry.status] = (counts[entry.status] ?? 0) + 1;
}
assert.deepEqual(
  [...seen].sort(),
  [...inventory].sort(),
  "Every legacy functional definition needs an explicit coverage decision.",
);
const report = { definitions: seen.size, counts, scope: mapping.scope };
await mkdir(path.join(root, "desktop/artifacts/functional-coverage"), {
  recursive: true,
});
await writeFile(
  path.join(root, "desktop/artifacts/functional-coverage/inventory.json"),
  JSON.stringify(report, null, 2) + "\n",
);
console.log(JSON.stringify(report, null, 2));
