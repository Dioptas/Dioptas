import assert from "node:assert/strict";
import { test } from "node:test";
import { createPhaseCommandQueue } from "../src/phaseCommandQueue.ts";

test("wheel bursts keep the latest value before Save and after discrete actions", async () => {
  let release;
  const gate = new Promise((resolve) => {
    release = resolve;
  });
  const calls = [];
  const queue = createPhaseCommandQueue(
    () => async (command, args, _message, onSuccess) => {
      calls.push([command, args]);
      if (calls.length === 1) await gate;
      onSuccess?.({ ok: true });
    },
  );
  const change = (pressure) =>
    queue("integration_phase", {
      operation: "update",
      editor_uid: "gold",
      pressure,
    });
  const work = [change(1)];
  for (let value = 2; value <= 30; value++) work.push(change(value));
  work.push(queue("integration_phase_export", { save_current: true }));
  for (let value = 31; value <= 60; value++) work.push(change(value));
  assert.equal(calls.length, 1);
  release();
  await Promise.all(work);
  assert.deepEqual(
    calls.map(([command, args]) => [command, args.pressure]),
    [
      ["integration_phase", 1],
      ["integration_phase", 30],
      ["integration_phase_export", undefined],
      ["integration_phase", 60],
    ],
  );
});

test("different phases, fields and linked-condition changes keep their order", async () => {
  let release;
  const gate = new Promise((resolve) => {
    release = resolve;
  });
  const calls = [];
  const queue = createPhaseCommandQueue(() => async (_command, args) => {
    calls.push(args);
    if (calls.length === 1) await gate;
  });
  const update = (uid, fields) =>
    queue("integration_phase", {
      operation: "update",
      editor_uid: uid,
      ...fields,
    });
  const work = [
    update("a", { pressure: 1 }),
    update("a", { pressure: 2 }),
    update("b", { pressure: 3 }),
    update("b", { temperature: 500 }),
    queue("integration_phase", {
      operation: "same_conditions",
      enabled: false,
    }),
    update("b", { pressure: 4 }),
  ];
  release();
  await Promise.all(work);
  assert.deepEqual(
    calls.map((args) => args.pressure ?? args.temperature ?? args.enabled),
    [1, 2, 3, 500, false, 4],
  );
});

test("a failed request rejects its callers and does not discard later actions", async () => {
  const queue = createPhaseCommandQueue(() => async (_command, args) => {
    if (args.pressure === 1) throw Error("Rejected pressure");
  });
  const results = await Promise.allSettled([
    queue("integration_phase", {
      operation: "update",
      editor_uid: "a",
      pressure: 1,
    }),
    queue("integration_phase_export", { save_current: true }),
  ]);
  assert.equal(results[0].status, "rejected");
  assert.equal(results[1].status, "fulfilled");
});

test("coalesced phase callers receive the same latest result once, and one callback failure cannot poison the queue", async () => {
  let release;
  const gate = new Promise((resolve) => (release = resolve));
  const executed = [],
    delivered = [];
  const queue = createPhaseCommandQueue(
    () => async (command, args, _message, onSuccess) => {
      executed.push([command, args]);
      if (executed.length === 1) await gate;
      onSuccess?.({
        ok: true,
        phaseRevision: args.pressure,
        phaseEditor: { uid: args.editor_uid },
      });
    },
  );
  const work = [
    queue("integration_phase", {
      operation: "update",
      editor_uid: "a",
      pressure: 1,
    }),
  ];
  work.push(
    queue(
      "integration_phase",
      { operation: "update", editor_uid: "a", pressure: 2 },
      "",
      (result) => {
        delivered.push(["second", result.phaseRevision]);
        throw Error("Callback failed");
      },
    ),
  );
  work.push(
    queue(
      "integration_phase",
      { operation: "update", editor_uid: "a", pressure: 3 },
      "",
      (result) => delivered.push(["third", result.phaseRevision]),
    ),
  );
  work.push(
    queue(
      "integration_phase_export",
      { editor_uid: "a", save_current: true },
      "",
      (result) => delivered.push(["save", result.phaseEditor.uid]),
    ),
  );
  // Attach rejection handling before releasing the processor reservation.
  const settled = Promise.allSettled(work);
  release();
  const results = await settled;
  assert.deepEqual(
    executed.map(([, args]) => args.pressure),
    [1, 3, undefined],
  );
  assert.deepEqual(delivered, [
    ["second", 3],
    ["third", 3],
    ["save", "a"],
  ]);
  assert.deepEqual(
    results.map((result) => result.status),
    ["fulfilled", "rejected", "fulfilled", "fulfilled"],
  );
  assert.match(results[1].reason.message, /Callback failed/);
});

test("native phase targeting preserves operation fields and extension JSON without mutating caller payloads", async () => {
  const { phaseEditorInvocation } =
    await import("../src/phaseEditorCommands.ts");
  const changes = {
    reference: { authors: ["A"], future_extension: { value: 3 } },
    parameters: [{ scope: "eos", key: "K0", error: 2 }],
  };
  const payload = {
    operation: "editor_transaction",
    edit_operation: "editor_metadata",
    editor_uid: "old",
    index: 2,
    changes,
  };
  const invocation = phaseEditorInvocation(
    ["integration_phase", payload, "Edit", () => {}],
    "current",
  );
  assert.equal(invocation[0], "integration_phase");
  assert.equal(invocation.length, 2);
  assert.equal(invocation[1].editor_uid, "current");
  assert.equal(invocation[1].editor_only, true);
  assert.equal(invocation[1].changes, changes);
  assert.equal(invocation[1].edit_operation, "editor_metadata");
  assert.equal(payload.editor_uid, "old");
  assert.equal("editor_only" in payload, false);
});
