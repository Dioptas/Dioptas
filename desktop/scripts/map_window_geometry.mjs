// Native lifecycle check with its own preference file, including a full app restart.
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { mkdtemp, readFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
const desktop = fileURLToPath(new URL("../", import.meta.url));
const directory = await mkdtemp(path.join(tmpdir(), "dioptas-map-placement-"));
const preference = path.join(directory, "placement.json");
const run = (expected) =>
  new Promise((resolve, reject) => {
    const child = spawn("npm", ["run", "tauri:smoke", "--", "--map"], {
      cwd: desktop,
      stdio: "inherit",
      env: {
        ...process.env,
        DIOPTAS_MAP_WINDOW_STATE: preference,
        ...(expected
          ? { DIOPTAS_MAP_WINDOW_EXPECTED: JSON.stringify(expected) }
          : {}),
      },
    });
    child.on("error", reject);
    child.on("exit", (code) =>
      code === 0
        ? resolve()
        : reject(Error(`Native placement test exited ${code}`)),
    );
  });
try {
  await run();
  let report = JSON.parse(
    await readFile(
      new URL("../artifacts/tauri-map-smoke.json", import.meta.url),
      "utf8",
    ),
  );
  assert.equal(report.detachedMap.geometryRestored, true);
  const saved = JSON.parse(await readFile(preference, "utf8"));
  assert.equal(saved.version, 1);
  assert.ok(saved.screen.name && saved.screen.scale > 0);
  assert.deepEqual(saved.size, [620, 520]);
  await run(report.detachedMap.lastPlacement);
  report = JSON.parse(
    await readFile(
      new URL("../artifacts/tauri-map-smoke.json", import.meta.url),
      "utf8",
    ),
  );
  assert.equal(report.detachedMap.startupRestore, true);
  assert.equal(report.detachedMap.geometryRestored, true);
  console.log(
    "Native map placement survived docking and an application restart",
  );
} finally {
  await rm(directory, { recursive: true, force: true });
}
