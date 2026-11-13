import assert from "node:assert/strict";
import { test } from "node:test";
import {
  commandInvocation,
  scheduledInvocation,
  withScheduling,
  withCommandMessage,
  withCommandSuccess,
  submitWorkspaceCommand,
  retryStoredMap,
} from "../src/workspaceCommands.ts";
test("scheduling composition preserves correlated payloads/callbacks while overriding only scheduler options", async () => {
  const payload = { operation: "rename", name: "Detector" },
    callback = () => {},
    predicate = () => true;
  const call = [
    "configuration",
    payload,
    "Renaming",
    callback,
    predicate,
    false,
    false,
  ];
  assert.equal(commandInvocation(call)[1], payload);
  const scheduled = scheduledInvocation(call, {
    queueIfBusy: true,
    replaceDrafts: true,
  });
  assert.deepEqual(scheduled.slice(0, 5), call.slice(0, 5));
  assert.deepEqual(scheduled.slice(5), [true, true]);
  let forwarded;
  await withScheduling(
    async (...args) => {
      forwarded = args;
    },
    { queueIfBusy: true },
  )(...call.slice(0, 4));
  assert.equal(forwarded[1], payload);
  assert.equal(forwarded[3], callback);
  assert.equal(forwarded[5], true);
  await withCommandMessage(
    async (...args) => {
      forwarded = args;
    },
    "Benchmark",
    { replaceDrafts: true },
  )("next_image", { direction: 1 });
  assert.deepEqual(forwarded.slice(0, 3), [
    "next_image",
    { direction: 1 },
    "Benchmark",
  ]);
  assert.equal(forwarded[6], true);
});
test("workspace submission adds only transport metadata and Map view context without mutating inputs", async () => {
  const calls = [],
    invoke = async (...call) => {
      calls.push(call);
      return { ok: true };
    };
  const payload = {
    operation: "rectangle",
    bounds: [1, 2, 3, 4],
    requested_products: { cake: false },
  };
  const command = ["mask_edit", payload];
  await submitWorkspaceCommand(invoke, command, "mask", true);
  assert.deepEqual(calls.at(-1), [
    "mask_edit",
    { ...payload, defer_integration: true },
  ]);
  assert.equal("defer_integration" in payload, false);
  await submitWorkspaceCommand(
    invoke,
    ["configuration", { operation: "select", index: 1 }],
    "mask",
    true,
  );
  assert.equal("defer_integration" in calls.at(-1)[1], false);
  const map = ["map_select", { index: 4, reintegrate: true }];
  await submitWorkspaceCommand(invoke, map, "integration", false);
  assert.deepEqual(calls.at(-1), [
    "map_select",
    { index: 4, reintegrate: true, integration_view: true },
  ]);
  await retryStoredMap(invoke, map, "map");
  assert.deepEqual(calls.at(-1), [
    "map_select",
    { index: 4, reintegrate: false, integration_view: false },
  ]);
  assert.equal(map[1].reintegrate, true);
  assert.throws(
    () =>
      retryStoredMap(invoke, ["next_image", { direction: 1 }], "integration"),
    /map_select/,
  );
});
test("success composition calls the original callback before the local completion action", async () => {
  const events = [],
    result = { ok: true, state: { revision: 7 } };
  const wrapped = withCommandSuccess(
    async (...call) => call[3](result),
    (command) => events.push(["local", command]),
  );
  await wrapped("manual_geometry", { dist: 0.1 }, "Apply", (reply) =>
    events.push(["caller", reply]),
  );
  assert.deepEqual(events, [
    ["caller", result],
    ["local", "manual_geometry"],
  ]);
});
