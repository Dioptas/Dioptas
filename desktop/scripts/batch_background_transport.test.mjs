import test from "node:test";
import assert from "node:assert/strict";
import { copyFile, mkdtemp, rm } from "node:fs/promises";
import path from "node:path";
import os from "node:os";
import { nativeClient, root } from "./native_backend_client.mjs";

test(
  "native stdio background progress bypasses a long row; cancellation restores settings, selection, and all products",
  { timeout: 45000 },
  async () => {
    const temp = await mkdtemp(
      path.join(os.tmpdir(), "dioptas-background-transport-"),
    );
    const source = path.join(temp, "stored.h5");
    await copyFile(
      path.join(
        root,
        "desktop/backend/tests/fixtures/batch_background_long.h5",
      ),
      source,
    );
    const native = nativeClient();
    const call = async (a, p = {}) => {
      const r = await native.invoke(a, p);
      assert.equal(r.ok, true, `${a}: ${r.error}`);
      return r;
    };
    try {
      await call("batch_open", { path: source });
      await call("batch_background_extract", {
        parameters: { smoothing: 0.1, iterations: 7, order: 3 },
      });
      await call("batch_background_display", {
        subtract: true,
        range: [2, 8],
        cut: true,
      });
      await call("batch_select", { index: 2 });
      const before = await call("state");
      const batch = await call("batch_snapshot");
      const running = native.invoke("batch_background_extract", {
        parameters: { smoothing: 0.2, iterations: 99999, order: 7 },
      });
      let progress;
      for (let i = 0; i < 100; i++) {
        progress = (await call("progress")).progress;
        if (
          progress.running &&
          progress.label === "Extracting batch background"
        )
          break;
        await new Promise((r) => setTimeout(r, 2));
      }
      assert.equal(progress.label, "Extracting batch background");
      assert.ok(progress.current < progress.total);
      const start = performance.now();
      await call("cancel_refinement");
      assert.equal((await running).cancelled, true);
      assert.ok(
        performance.now() - start < 2000,
        "Cancellation interrupts smoothing within a row",
      );
      assert.deepEqual(await call("batch_snapshot"), batch);
      assert.deepEqual(await call("state"), before);
      assert.equal((await call("progress")).progress.running, false);
    } finally {
      await native.close();
      await rm(temp, { recursive: true, force: true });
    }
  },
);
