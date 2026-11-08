// Prevent legacy functional cases and native evidence from silently falling out
// of the inventory. This checks traceability, not scientific equivalence itself.
import assert from "node:assert/strict";
import { readFile, readdir, mkdir, writeFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import path from "node:path";

const root = fileURLToPath(new URL("../../", import.meta.url));
const directory = "dioptas/tests/functional_tests";
const inventory = new Set();
for (const file of (await readdir(path.join(root, directory))).filter((f) =>
  /^test_.*\.py$/.test(f),
)) {
  const classes = [];
  for (const line of (
    await readFile(path.join(root, directory, file), "utf8")
  ).split("\n")) {
    if (!line.trim() || line.trimStart().startsWith("#")) continue;
    const indent = line.length - line.trimStart().length;
    while (classes.length && indent <= classes.at(-1).indent) classes.pop();
    const cls = line.match(/^\s*class (\w+)/);
    if (cls) classes.push({ name: cls[1], indent });
    const test = line.match(/^\s*def (test_\w+)\(/);
    if (test)
      inventory.add([file, ...classes.map((c) => c.name), test[1]].join("::"));
  }
}
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
