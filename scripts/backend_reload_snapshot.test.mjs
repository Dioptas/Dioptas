import assert from "node:assert/strict";
import { test } from "node:test";
import {
  refreshBackendSnapshots,
  backendUpdateMessage,
} from "../src/backendReloadSnapshot.ts";
import {
  initialResponseSnapshot,
  reduceResponseSnapshot,
} from "../src/responseSnapshot.ts";

test("update guidance drops the redundant host prefix and keeps the recovery action first", () => {
  assert.equal(
    backendUpdateMessage(
      "Backend update failed; current session retained. Save your work, then restart.",
    ),
    "Save your work, then restart.",
  );
  assert.equal(backendUpdateMessage("Compilation error"), "Compilation error");
});

test("successful worker updates refresh SC as well as powder snapshots", async () => {
  const actions = [],
    applied = [];
  const lost = await refreshBackendSnapshots(
    async (action) => {
      actions.push(action);
      return action === "state"
        ? { ok: true }
        : { ok: true, scxrd: { frames: 144 } };
    },
    (result) => applied.push(result),
    true,
    true,
  );
  assert.deepEqual(actions, ["state", "scxrd_snapshot"]);
  assert.equal(applied.at(-1).scxrd.frames, 144);
  assert.equal(lost, false);
});
test("a refused update reconciles an already lost scan and clears the stale image", async () => {
  let state = {
    ...initialResponseSnapshot(),
    scxrd: { frames: 144, image: { bufferId: "stale" } },
  };
  const lost = await refreshBackendSnapshots(
    async (action) => {
      assert.equal(action, "scxrd_snapshot");
      return { ok: true, scxrd: { frames: 0, image: null } };
    },
    (result) => {
      state = reduceResponseSnapshot(state, result);
    },
    true,
    false,
  );
  assert.equal(lost, true);
  assert.equal(state.scxrd.frames, 0);
  assert.equal(state.scxrd.image, null);
});
test("a safely retained scan stays loaded; failed snapshots cannot replace it", async () => {
  let applied = 0;
  assert.equal(
    await refreshBackendSnapshots(
      async () => ({ ok: true, scxrd: { frames: 144 } }),
      () => applied++,
      true,
      false,
    ),
    false,
  );
  assert.equal(applied, 1);
  await assert.rejects(
    refreshBackendSnapshots(
      async () => ({ ok: false, error: "Disconnected" }),
      () => applied++,
      true,
      false,
    ),
    /Disconnected/,
  );
  assert.equal(applied, 1);
});
