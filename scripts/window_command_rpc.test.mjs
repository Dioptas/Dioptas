import assert from "node:assert/strict";
import test from "node:test";
import {
  WindowCommandRpc,
  readWindowCommand,
  runWindowCommand,
} from "../src/windowCommandRpc.ts";

test("detached read replies remain associated with their command and retain buffer identity", async () => {
  const sent = [];
  const rpc = new WindowCommandRpc((request) => sent.push(request));
  const map = rpc.read("map_snapshot");
  const levels = rpc.read("map_levels", { clipping: 0.1 });
  assert.equal(sent[0].command, "map_snapshot");
  assert.equal(sent[0].read, true);
  assert.deepEqual(sent[1].args, { clipping: 0.1 });
  const pixels = new ArrayBuffer(16);
  const snapshot = { ok: true, map: { raster: { data: pixels } } };
  rpc.receive(sent[1].id, { ok: true, mapLevels: [0, 10] });
  rpc.receive(sent[0].id, snapshot);
  assert.deepEqual(await levels, { ok: true, mapLevels: [0, 10] });
  assert.equal(await map, snapshot);
  assert.equal((await map).map.raster.data, pixels);
  rpc.close();
});

test("detached edits acknowledge work while local hide stays outside the native registry", async () => {
  const sent = [];
  const rpc = new WindowCommandRpc((request) => sent.push(request));
  const edit = rpc.edit("integration_save_batch", { format: "xy" });
  const hide = rpc.edit("batch_hide");
  assert.equal(sent[0].read, false);
  assert.equal(sent[1].command, "batch_hide");
  rpc.receive(sent[0].id, { ok: true });
  rpc.receive(sent[1].id, { ok: true });
  assert.deepEqual(await edit, { ok: true });
  assert.deepEqual(await hide, { ok: true });
  rpc.close();
});

test("closing a detached window settles every pending request and ignores late replies", async () => {
  const sent = [];
  const rpc = new WindowCommandRpc((request) => sent.push(request));
  const reads = [rpc.read("map_snapshot"), rpc.read("progress")];
  rpc.close();
  rpc.receive(sent[0].id, { ok: true, map: null });
  assert.deepEqual(await Promise.all(reads), [
    { ok: false, cancelled: true },
    { ok: false, cancelled: true },
  ]);
});

test("timeouts and send failures release request ownership", async () => {
  const rpc = new WindowCommandRpc(() => {}, 5);
  assert.deepEqual(await rpc.read("map_snapshot"), {
    ok: false,
    error: "The main window did not respond.",
  });
  rpc.close();
  const broken = new WindowCommandRpc(() => {
    throw new Error("closed channel");
  });
  await assert.rejects(broken.read("progress"), /closed channel/);
  broken.close();
});

test("window adapters preserve correlated arguments, queue message and success callback", async () => {
  const payload = { index: 3, reintegrate: true };
  const message = {
    type: "request",
    id: "r",
    command: "batch_select",
    args: payload,
    read: false,
  };
  let observed;
  const callback = () => {};
  await runWindowCommand(
    message,
    async (...call) => {
      observed = call;
    },
    "Loading batch frame…",
    callback,
  );
  assert.deepEqual(observed, [
    "batch_select",
    payload,
    "Loading batch frame…",
    callback,
  ]);
  assert.equal(observed[1], payload);
  const result = { ok: true, batch: null };
  assert.equal(
    await readWindowCommand(
      {
        type: "request",
        id: "s",
        command: "batch_snapshot",
        args: {},
        read: true,
      },
      async (...call) => {
        assert.deepEqual(call, ["batch_snapshot", {}]);
        return result;
      },
    ),
    result,
  );
});
