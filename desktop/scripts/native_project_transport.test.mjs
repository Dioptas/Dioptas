import test from "node:test";
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { mkdtemp, readFile, rm, utimes } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { nativeClient, root } from "./native_backend_client.mjs";
test(
  "project progress/cancel and source mutation preserve the session and existing file",
  { timeout: 120000 },
  async () => {
    const directory = await mkdtemp(
      path.join(tmpdir(), "dioptas-rust-project-"),
    );
    const image = path.join(directory, "counts.npy"),
      project = path.join(directory, "session.dio");
    execFileSync(path.join(root, ".venv/bin/python"), [
      "-c",
      "import sys,numpy as np; y,x=np.indices((1024,1024)); np.save(sys.argv[1],(100+x*2+y*3).astype('uint16'))",
      image,
    ]);
    const native = nativeClient();
    const invoke = async (a, p = {}) => {
      const r = await native.invoke(a, p);
      assert.equal(r.ok, true, `${a}: ${r.error}`);
      return r;
    };
    try {
      await invoke("open_image", { path: image });
      for (let i = 1; i < 16; i++)
        await invoke("configuration", { operation: "duplicate" });
      await invoke("save_project", { path: project });
      const before = await invoke("state"),
        bytes = await readFile(project);
      const underway = async (label) => {
        for (let i = 0; i < 300; i++) {
          const r = await invoke("progress");
          if (
            r.progress.label === label &&
            r.progress.current >= 1 &&
            r.progress.current < r.progress.total
          )
            return;
          await new Promise((r) => setTimeout(r, 3));
        }
        throw Error(`Missing intermediate progress: ${label}`);
      };
      let job = native.invoke("save_project", { path: project });
      await underway("Saving project configurations");
      await invoke("cancel_refinement");
      let result = await job;
      assert.equal(result.cancelled, true);
      assert.deepEqual(await invoke("state"), before);
      assert.deepEqual(await readFile(project), bytes);
      job = native.invoke("open_project", { path: project });
      await underway("Restoring project configurations");
      await invoke("cancel_refinement");
      result = await job;
      assert.equal(result.cancelled, true);
      assert.deepEqual(await invoke("state"), before);
      job = native.invoke("open_project", { path: project });
      await underway("Restoring project configurations");
      const time = new Date(Date.now() + 2000);
      await utimes(project, time, time);
      result = await job;
      assert.equal(result.ok, false);
      assert.match(result.error, /chang|snapshot/i);
      assert.deepEqual(await invoke("state"), before);
      assert.deepEqual(await readFile(project), bytes);
    } finally {
      await native.close();
      await rm(directory, { recursive: true, force: true });
    }
  },
);
