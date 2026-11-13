import assert from "node:assert/strict";
import test from "node:test";
import path from "node:path";
import { nativeClient, root } from "./native_backend_client.mjs";

test(
  "geometric masks and transforms cancel without publishing partial pixels or history",
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
      const baseline = await call("state");
      // A dense polygon gives the real stdio progress/cancel path time to respond.
      const points = Array.from({ length: 1000 }, (_, i) => {
        const a = (2 * Math.PI * i) / 1000;
        return [490 + 470 * Math.cos(a), 520 + 490 * Math.sin(a)];
      });
      const job = native.invoke("mask_edit", { operation: "polygon", points });
      let observed = false;
      for (let i = 0; i < 300; i++) {
        const r = await call("progress");
        if (r.progress.label === "Applying mask") {
          observed = true;
          break;
        }
        await new Promise((r) => setTimeout(r, 2));
      }
      assert.ok(observed);
      const start = performance.now();
      await call("cancel_refinement");
      assert.ok(performance.now() - start < 1000);
      assert.equal((await job).cancelled, true);
      assert.deepEqual(await call("state"), baseline);
      const transform = native.invoke("image_transform", {
        operation: "rotate_right",
      });
      await call("cancel_refinement");
      assert.equal((await transform).cancelled, true);
      assert.deepEqual(await call("state"), baseline);
    } finally {
      await native.close();
    }
  },
);
