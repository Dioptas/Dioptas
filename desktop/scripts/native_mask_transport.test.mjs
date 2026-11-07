import assert from "node:assert/strict";
import test from "node:test";
import path from "node:path";
import { setTimeout as delay } from "node:timers/promises";
import { nativeClient, root } from "./native_backend_client.mjs";

test(
  "native mask cancellation rolls back plugin settings, caches, products and history",
  { timeout: 45000 },
  async () => {
    const native = nativeClient();
    const call = async (action, payload = {}) => {
      const r = await native.invoke(action, payload);
      assert.equal(r.ok, true, JSON.stringify(r));
      return r;
    };
    try {
      await call("example");
      await call("open_calibration", {
        path: path.join(root, "dioptas/tests/data/CeO2_Pilatus1M.poni"),
      });
      const before = await call("state");
      const pending = native.invoke("mask_plugin", {
        name: "Cosmic Ray Mask",
        enabled: true,
        settings: { iterations: 10, window_size: 51 },
      });
      let preview;
      for (let i = 0; i < 1000; i++) {
        const p = (await call("progress")).progress;
        if (p.label === "Computing Cosmic Ray Mask") {
          preview = p;
          break;
        }
        await delay(2);
      }
      assert.ok(preview);
      const start = performance.now();
      await call("cancel_refinement");
      assert.ok(performance.now() - start < 1000);
      const result = await pending;
      assert.equal(result.ok, false);
      assert.match(result.error, /cancelled/);
      const after = await call("state");
      assert.deepEqual(after.state, before.state);
      for (const field of ["mask", "pattern", "cake"])
        assert.deepEqual(after[field], before[field]);
      assert.equal((await call("progress")).progress.running, false);
      const queued = native.invoke("mask_plugin", {
        name: "Threshold Mask",
        enabled: true,
      });
      await call("cancel_refinement");
      assert.match((await queued).error, /cancelled/);
      assert.deepEqual((await call("state")).state, before.state);
    } finally {
      await native.close();
    }
  },
);
