import assert from "node:assert/strict";
import { test } from "node:test";
import {
  CommandCoordinator,
  commandPolicy,
} from "../src/commandCoordinator.ts";

const policy = (action, args = {}, options = {}) =>
  commandPolicy({
    action,
    args,
    message: "Processing…",
    mode: "integration",
    ...options,
  });
const applied = (value) => ({ status: "applied", value });
const gate = () => {
  let release;
  const promise = new Promise((resolve) => {
    release = resolve;
  });
  return { promise, release };
};

test("foreground work rejects a busy action but explicitly queued work retains order", async () => {
  const queue = new CommandCoordinator();
  const first = gate();
  const calls = [];
  const loading = queue.execute(policy("open_image"), async () => {
    calls.push("load-start");
    await first.promise;
    calls.push("load-end");
    return applied("image");
  });
  assert.equal(queue.busy, true);
  const ignored = await queue.execute(policy("open_project"), async () => {
    assert.fail("A blocked command must not touch the processor");
  });
  assert.deepEqual(ignored, { status: "skipped", reason: "busy" });
  const saved = queue.execute(
    policy("save_project", {}, { queueIfBusy: true }),
    async () => {
      calls.push("save");
      return applied("project");
    },
  );
  assert.deepEqual(calls, ["load-start"]);
  first.release();
  assert.deepEqual(await loading, applied("image"));
  assert.deepEqual(await saved, applied("project"));
  assert.deepEqual(calls, ["load-start", "load-end", "save"]);
  assert.equal(queue.busy, false);
  assert.equal(queue.pending, false);
});

test("interactive edits queue through image loading; watcher polls never compete with queued work", async () => {
  const queue = new CommandCoordinator();
  const first = gate();
  const calls = [];
  const loading = queue.execute(policy("open_image"), async () => {
    await first.promise;
    calls.push("image");
    return applied(null);
  });
  const correction = queue.execute(
    policy("integration_correction", { kind: "plate" }, { message: "" }),
    async () => {
      calls.push("correction");
      return applied(null);
    },
  );
  const saved = queue.execute(policy("save_project"), async () => {
    calls.push("save");
    return applied(null);
  });
  assert.deepEqual(
    await queue.execute(policy("integration_autoprocess_poll"), async () => {
      assert.fail("The watcher must wait until accepted work has drained");
    }),
    { status: "skipped", reason: "busy" },
  );
  first.release();
  await Promise.all([loading, correction, saved]);
  assert.deepEqual(calls, ["image", "correction", "save"]);
});

test("superseded mask work releases its reservation without leaving interactive admission enabled", async () => {
  const queue = new CommandCoordinator();
  const first = gate();
  const loading = queue.execute(policy("open_image"), async () => {
    await first.promise;
    return applied(null);
  });
  const obsolete = queue.execute(
    policy("mask_stroke", {}, { mode: "mask", queueIfBusy: true }),
    async () => {
      assert.fail(
        "An obsolete mask stroke must not alter the replacement image",
      );
    },
    () => false,
  );
  first.release();
  await loading;
  assert.deepEqual(await obsolete, { status: "skipped", reason: "superseded" });
  const next = gate();
  const fitting = queue.execute(policy("calibrate"), async () => {
    await next.promise;
    return applied(null);
  });
  assert.deepEqual(
    await queue.execute(policy("save_project"), async () => {
      assert.fail("Cancelled mask work must not leave admission counters set");
    }),
    { status: "skipped", reason: "busy" },
  );
  next.release();
  await fitting;
  assert.equal(queue.pending, false);
});

test("execution and stale-predicate failures cannot poison the next accepted command", async () => {
  const queue = new CommandCoordinator();
  const first = gate();
  const error = new Error("broken image");
  const broken = queue.execute(policy("open_image"), async () => {
    await first.promise;
    throw error;
  });
  const predicateError = new Error("expired context");
  const obsolete = queue.execute(
    policy("next_image"),
    async () => {
      assert.fail("Predicate rejection must prevent execution");
    },
    () => {
      throw predicateError;
    },
  );
  const valid = queue.execute(policy("next_image"), async () =>
    applied("next"),
  );
  first.release();
  assert.deepEqual(await broken, { status: "failed", error });
  assert.deepEqual(await obsolete, { status: "failed", error: predicateError });
  assert.deepEqual(await valid, applied("next"));
  assert.equal(queue.busy, false);
  assert.equal(queue.pending, false);
});

test("an identity predicate is checked after earlier commands, not when a command is captured", async () => {
  const queue = new CommandCoordinator();
  const first = gate();
  let configuration = "A";
  const switching = queue.execute(policy("configuration_select"), async () => {
    await first.promise;
    configuration = "B";
    return applied(null);
  });
  const editing = queue.execute(
    policy("integration_image_background", {}, { message: "" }),
    async () => {
      assert.fail("An edit captured for A must not change B");
    },
    () => configuration === "A",
  );
  first.release();
  await switching;
  assert.deepEqual(await editing, { status: "skipped", reason: "superseded" });
});

test("dialog deferrals and user cancellations are distinct from applied and failed work", async () => {
  const queue = new CommandCoordinator();
  for (const result of [
    { status: "cancelled", value: { cancelled: true } },
    { status: "deferred", value: { imageChange: {} } },
    { status: "failed", error: "worker rejected the edit" },
    applied({ ok: true }),
  ]) {
    assert.deepEqual(
      await queue.execute(policy("open_image"), async () => result),
      result,
    );
    assert.equal(queue.busy, false);
    assert.equal(queue.pending, false);
  }
});
