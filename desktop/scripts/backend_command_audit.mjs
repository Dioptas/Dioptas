// Check dispatch coverage of the legacy React backend contract without importing Python.
// Empty payloads deliberately exercise routes/validation, not scientific parity.
import assert from "node:assert/strict";
import { readFile, mkdir, writeFile } from "node:fs/promises";
import path from "node:path";
import { nativeClient, root } from "./native_backend_client.mjs";

const commands = new Set(["progress", "cancel_refinement"]);
for (const [file, marker] of [
  ["session.py", "        handlers = {"],
  ["integration.py", "    def _integration_handlers(self):"],
  ["batch.py", "    def _batch_commands(self):"],
  ["map.py", "    def _map_commands(self):"],
]) {
  const source = await readFile(
    path.join(root, "dioptas/desktop", file),
    "utf8",
  );
  const start = source.indexOf(marker);
  assert(start >= 0, `Missing command registry in ${file}`);
  const end = source.indexOf("\n        }", start);
  assert(end > start, `Missing registry end in ${file}`);
  const keys = [...source.slice(start, end).matchAll(/^\s+"([a-z_]+)":/gm)];
  assert(keys.length > 10, `Unexpected command registry in ${file}`);
  for (const [, key] of keys) commands.add(key);
}
const native = nativeClient();
const routed = [];
try {
  const host = await native.invoke("__host__");
  assert.equal(host.runtime, "rust");
  for (const command of [...commands]
    .sort()
    .filter((c) => c !== "cancel_refinement")) {
    const result = await native.invoke(command);
    assert(
      !String(result.error).includes("not migrated"),
      `${command}: ${result.error}`,
    );
    routed.push({ command, result: result.ok ? "accepted" : "validated" });
  }
  assert.equal((await native.invoke("cancel_refinement")).ok, true);
  routed.push({ command: "cancel_refinement", result: "accepted" });
  const unknown = await native.invoke("__unported_audit_command__");
  assert.equal(unknown.ok, false);
  assert.match(unknown.error, /not migrated/);
  const directory = path.join(root, "desktop/artifacts/default-backend");
  await mkdir(directory, { recursive: true });
  const receipt = {
    runtime: host.runtime,
    commands: routed.length,
    scope:
      "Dispatch/validation only; independent scientific parity checks remain separate.",
    routed,
  };
  await writeFile(
    path.join(directory, "commands.json"),
    JSON.stringify(receipt, null, 2) + "\n",
  );
  console.log(
    `All ${routed.length} legacy desktop commands have native dispatch routes.`,
  );
} finally {
  await native.close();
}
