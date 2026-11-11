// Full App + Rust processor: commands captured before a response must keep
// their overlay identity after preceding queued edits reorder/remove the list.
import assert from "node:assert/strict";
import { mkdtemp, writeFile, rm } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { createServer } from "vite";
import { chromium, webkit } from "playwright";
import { nativeClient, root } from "./native_backend_client.mjs";

const temp = await mkdtemp(path.join(os.tmpdir(), "dioptas-overlay-order-"));
const paths = [];
for (const name of ["A", "B", "C"]) {
  const file = path.join(temp, `${name}.xy`);
  await writeFile(file, "1 10\n2 20\n3 15\n");
  paths.push(file);
}
const server = await createServer({
  root: path.join(root, "desktop"),
  server: { host: "127.0.0.1", port: 0 },
});
await server.listen();
try {
  for (const [name, engine] of [
    ["chromium", chromium],
    ["webkit", webkit],
  ]) {
    const native = nativeClient();
    const browser = await engine.launch({ headless: true });
    let release;
    try {
      const page = await browser.newPage({
        viewport: { width: 1500, height: 900 },
      });
      const errors = [];
      page.on("pageerror", (error) => errors.push(error.message));
      const edits = [];
      let blockNext = false;
      let entered;
      const blocked = () => {
        blockNext = true;
        return new Promise((resolve) => {
          entered = resolve;
        });
      };
      await page.exposeFunction(
        "__overlayOrderInvoke",
        async (action, payload) => {
          if (action === "integration_overlay") {
            edits.push(payload);
            if (blockNext) {
              blockNext = false;
              const gate = new Promise((resolve) => {
                release = resolve;
              });
              entered();
              await gate;
            }
          }
          return native.browserResult(await native.invoke(action, payload));
        },
      );
      await page.addInitScript(() => {
        window.__overlayOrderPending = 0;
        window.pywebview = {
          api: {
            invoke: async (action, payload) => {
              window.__overlayOrderPending++;
              try {
                return await window.__overlayOrderInvoke(action, payload);
              } finally {
                window.__overlayOrderPending--;
              }
            },
          },
        };
      });
      const ready = async () => {
        await page.waitForFunction(
          () =>
            !window.__overlayOrderPending && !document.querySelector(".spin"),
        );
        await page.evaluate(
          () =>
            new Promise((resolve) =>
              requestAnimationFrame(() => requestAnimationFrame(resolve)),
            ),
        );
      };
      const reset = async () => {
        await native.invoke("integration_overlay", { operation: "clear" });
        const loaded = await native.invoke("integration_overlay", {
          operation: "load",
          paths,
        });
        assert.equal(loaded.ok, true, loaded.error);
        assert.equal(loaded.state.integration.supportsOverlayUids, true);
        await page.goto(server.resolvedUrls.local[0]);
        await page
          .getByRole("button", { name: "Integration", exact: true })
          .click();
        await page.getByRole("tab", { name: "Overlay", exact: true }).click();
        await page
          .getByRole("textbox", { name: "Overlay 1 name", exact: true })
          .click();
        await ready();
        edits.length = 0;
        return loaded.state.integration.overlays;
      };
      const state = async () =>
        (await native.invoke("state")).state.integration.overlays;
      const button = (name) => page.getByRole("button", { name, exact: true });

      const initial = await reset();
      const moving = blocked();
      await button("Move overlay down").click();
      await moving;
      await button("Move overlay down").click();
      release();
      await page.waitForFunction(() => !window.__overlayOrderPending);
      await ready();
      assert.deepEqual(
        (await state()).map((o) => o.name),
        ["B", "C", "A"],
      );
      assert.equal(edits.length, 2);
      assert.ok(
        edits.every(
          (edit) => edit.uid === initial[0].uid && !("index" in edit),
        ),
      );

      const beforeEdit = await reset();
      const editing = blocked();
      await button("Move overlay down").click();
      await editing;
      const scale = page.getByRole("spinbutton", {
        name: "Overlay 2 scale",
        exact: true,
      });
      await scale.fill("7");
      await scale.press("Enter");
      release();
      await ready();
      const afterEdit = await state();
      assert.deepEqual(
        afterEdit.map((o) => o.name),
        ["B", "A", "C"],
      );
      assert.equal(afterEdit.find((o) => o.uid === beforeEdit[1].uid).scale, 7);
      assert.equal(afterEdit.find((o) => o.uid === beforeEdit[0].uid).scale, 1);
      assert.equal(edits.at(-1).uid, beforeEdit[1].uid);

      const beforeRemove = await reset();
      const deleting = blocked();
      await button("Delete selected overlay").click();
      await deleting;
      await button("Delete selected overlay").click();
      release();
      await ready();
      assert.deepEqual(
        (await state()).map((o) => o.name),
        ["B", "C"],
      );
      assert.ok(edits.every((edit) => edit.uid === beforeRemove[0].uid));
      await page
        .getByText("The selected overlay no longer exists.", { exact: true })
        .first()
        .waitFor();
      assert.deepEqual(errors, []);
      console.log(
        JSON.stringify({
          browser: name,
          runtime: "rust",
          repeatedMoves: true,
          editAfterReorder: true,
          repeatedRemoval: true,
          errors,
        }),
      );
    } finally {
      release?.();
      await browser.close();
      await native.close();
    }
  }
} finally {
  await server.close();
  await rm(temp, { recursive: true, force: true });
}
