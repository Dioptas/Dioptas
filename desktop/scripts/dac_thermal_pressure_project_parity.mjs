import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { mkdtemp, readFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { nativeClient, root } from "./native_backend_client.mjs";
const temp = await mkdtemp(path.join(tmpdir(), "dioptas-qt-dac-"));
const reference = (mode) => {
  const r = spawnSync(
    path.join(root, ".venv/bin/python"),
    [
      path.join(
        root,
        "desktop/scripts/dac_thermal_pressure_project_reference.py",
      ),
      mode,
      temp,
    ],
    {
      cwd: root,
      env: { ...process.env, QT_QPA_PLATFORM: "offscreen" },
      encoding: "utf8",
    },
  );
  assert.equal(r.status, 0, r.stdout + r.stderr);
  return r.stdout;
};
const native = nativeClient();
try {
  reference("write");
  const expected = JSON.parse(
    await readFile(path.join(temp, "expected.json"), "utf8"),
  );
  const invoke = async (a, p) => {
    const r = await native.invoke(a, p);
    assert.equal(r.ok, true, r.error);
    return r;
  };
  await invoke("open_project", { path: path.join(temp, "qt-factor.dio") });
  const state = await invoke("state", {});
  assert.equal(state.state.integration.phaseDacThermalPressureFactor, 0.4);
  assert.equal(state.state.integration.phaseColdPressure, true);
  const editor = (await invoke("integration_phase_editor", { index: 0 }))
    .phaseEditor;
  assert.ok(
    Math.abs(editor.lattice.v - expected.volume) < 2e-7 * expected.volume,
  );
  await invoke("configuration", { operation: "select", index: 0 });
  assert.equal(
    (await invoke("state", {})).state.integration.phaseDacThermalPressureFactor,
    0.4,
  );
  await invoke("save_project", { path: path.join(temp, "native-factor.dio") });
  console.log(reference("read").trim());
} finally {
  native.close();
  await rm(temp, { recursive: true, force: true });
}
