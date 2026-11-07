import assert from "node:assert/strict";
import test from "node:test";
import { nativeClient } from "./native_backend_client.mjs";
test(
  "LA Cosmic second-pass progress and cancellation retain exact data and history",
  { timeout: 45000 },
  async () => {
    const native = nativeClient();
    const call = async (a, p = {}) => {
      const r = await native.invoke(a, p);
      assert.equal(r.ok, true, `${a}: ${r.error}`);
      return r;
    };
    try {
      await call("example");
      await call("mask_stroke", { points: [[25, 35]], radius: 3 });
      await call("undo_mask");
      const baseline = await call("state");
      assert.equal(baseline.state.canRedoMask, true);
      const pending = native.invoke("mask_edit", { operation: "cosmic" });
      let second;
      for (let i = 0; i < 1000; i++) {
        const r = await call("progress");
        if (
          r.progress.label === "Cosmic removal" &&
          r.progress.current === 1 &&
          r.progress.running
        ) {
          second = r.progress;
          break;
        }
        await new Promise((r) => setTimeout(r, 3));
      }
      assert.ok(second, "Observe the second pass before cancellation");
      const start = performance.now();
      await call("cancel_refinement");
      assert.ok(performance.now() - start < 1000);
      assert.equal((await pending).cancelled, true);
      assert.deepEqual(await call("state"), baseline);
      assert.equal((await call("progress")).progress.running, false);
      const queued = native.invoke("mask_edit", { operation: "cosmic" });
      await call("cancel_refinement");
      assert.equal((await queued).cancelled, true);
      assert.deepEqual(await call("state"), baseline);
      await call("redo_mask");
    } finally {
      await native.close();
    }
  },
);
