import assert from "node:assert/strict";
import test from "node:test";
import { setTimeout as delay } from "node:timers/promises";
import { nativeClient } from "./native_backend_client.mjs";

test(
  "Rust stdio progress/cancel bypass fitting and restore the complete calibration",
  { timeout: 45000 },
  async () => {
    const native = nativeClient();
    const call = async (action, payload = {}) => {
      const r = await native.invoke(action, payload);
      assert.equal(r.ok, true, JSON.stringify(r));
      return r;
    };
    try {
      assert.equal((await call("__host__")).runtime, "rust");
      await call("example");
      for (const [x, y, ring] of [
        [637, 564, 1],
        [671, 511, 2],
        [668, 703, 3],
        [350.5, 592.8, 1],
        [554.3, 367.9, 1],
      ])
        await call("pick_peak", { x, y, ring });
      await call("calibrate", { automatic: false });
      await call("workflow_settings", { numberOfRings: 4 });
      const before = await call("state");
      const pending = native.invoke("calibrate", {
        automatic: true,
        restart: true,
      });
      let preview;
      for (let i = 0; i < 1000; i++) {
        const p = (await call("progress")).progress;
        if (
          p.label === "Preparing peak search" ||
          p.label === "Finding peaks on ring"
        ) {
          preview = structuredClone(p);
          break;
        }
        await delay(5);
      }
      assert.ok(preview, "Published a live detached preview while fitting");
      assert.ok(preview.calibration.rings.length > 0);
      const frozen = JSON.stringify(preview);
      const started = performance.now();
      await call("cancel_refinement");
      assert.ok(
        performance.now() - started < 1000,
        "Cancellation acknowledgement bypasses the scientific worker",
      );
      const cancelled = await pending;
      assert.equal(cancelled.ok, false);
      assert.match(cancelled.error, /cancelled/);
      const after = await call("state");
      for (const key of ["geometry", "calibration", "calibrated"])
        assert.deepEqual(after.state[key], before.state[key]);
      assert.deepEqual(after.pattern, before.pattern);
      assert.deepEqual(after.cake, before.cake);
      assert.equal(JSON.stringify(preview), frozen);
      const stopped = (await call("progress")).progress;
      assert.equal(stopped.running, false);
      assert.equal(stopped.calibration, undefined);
      // Cancellation arriving immediately after enqueue must not be cleared by
      // the worker's eventual start of this request.
      const queued = native.invoke("calibrate", { automatic: true });
      await call("cancel_refinement");
      assert.match((await queued).error, /cancelled/);
      assert.deepEqual(
        (await call("state")).state.calibration,
        before.state.calibration,
      );
    } finally {
      await native.close();
    }
  },
);
