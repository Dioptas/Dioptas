// Headless Tauri event contract, backed by the actual Rust processor. No OS windows.
import assert from "node:assert/strict";
import { pathToFileURL } from "node:url";
import path from "node:path";
import { root } from "./native_backend_client.mjs";
export async function nativeEditorEvents(browser, native, uid) {
  const page = await browser.newPage({
    viewport: { width: 1000, height: 800 },
  });
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.exposeFunction(
    "__nativePacket",
    async (action, payload, cachedBuffers) => [
      ...(await native.invokePacket(action, payload, cachedBuffers)),
    ],
  );
  await page.addInitScript(() => {
    let id = 0;
    const callbacks = new Map(),
      listeners = new Map();
    window.isTauri = true;
    window.__nativeCloses = 0;
    window.__nativeReads = 0;
    window.__TAURI_INTERNALS__ = {
      metadata: {
        currentWindow: { label: "phase-editor" },
        currentWebview: { label: "phase-editor" },
      },
      transformCallback(callback, once = false) {
        const key = ++id;
        callbacks.set(
          key,
          once
            ? (...args) => {
                callbacks.delete(key);
                return callback(...args);
              }
            : callback,
        );
        return key;
      },
      unregisterCallback(key) {
        callbacks.delete(key);
      },
      async invoke(command, args = {}) {
        if (command === "desktop_invoke") {
          if (args.action === "integration_phase_editor")
            window.__nativeReads++;
          return Uint8Array.from(
            await window.__nativePacket(
              args.action,
              args.payload,
              args.cachedBuffers,
            ),
          ).buffer;
        }
        if (command === "plugin:event|listen") {
          const key = ++id;
          listeners.set(key, { event: args.event, handler: args.handler });
          return key;
        }
        if (command === "plugin:event|unlisten") {
          listeners.delete(args.eventId);
          return;
        }
        if (
          ["plugin:window|close", "plugin:window|destroy"].includes(command)
        ) {
          window.__nativeCloses++;
          return;
        }
        return null;
      },
    };
    window.__TAURI_EVENT_PLUGIN_INTERNALS__ = { unregisterListener() {} };
    window.__sendNativeEvent = async (event, payload) => {
      for (const [key, listener] of listeners)
        if (listener.event === event)
          await callbacks.get(listener.handler)?.({ event, id: key, payload });
    };
  });
  await page.goto(
    pathToFileURL(path.join(root, "desktop/dist/index.html")).href +
      `?phase_uid=${encodeURIComponent(uid)}`,
  );
  await page
    .getByRole("tab", { name: "Equation of state", exact: true })
    .click();
  await page.locator(".pe-metadata > summary").click();
  const notes = page.getByLabel("Record notes", { exact: true });
  await notes.fill("Detached draft retained");
  await page.waitForFunction(() =>
    document
      .querySelector(".pe-metadata-actions [role=status]")
      ?.textContent.includes("Draft"),
  );
  await page.evaluate(() =>
    window.__sendNativeEvent("tauri://close-requested", {}),
  );
  assert.equal(await page.evaluate(() => window.__nativeCloses), 0);
  assert.match(
    await page.locator(".pe-native-error").innerText(),
    /Apply or cancel/,
  );
  await page.evaluate(() =>
    window.__sendNativeEvent("phase-editor-target", { uid: "another-phase" }),
  );
  assert.equal(await notes.inputValue(), "Detached draft retained");
  assert.match(
    await page.locator(".pe-native-error").innerText(),
    /different phase/,
  );
  const reads = await page.evaluate(() => window.__nativeReads);
  await page.evaluate(() =>
    window.__sendNativeEvent("phase-editor-refresh", {}),
  );
  assert.equal(await page.evaluate(() => window.__nativeReads), reads);
  await page
    .getByRole("button", { name: "Cancel publication edits", exact: true })
    .click();
  await page.waitForFunction((reads) => window.__nativeReads > reads, reads);
  await page.getByRole("button", { name: "Close", exact: true }).click();
  await page.waitForFunction(() => window.__nativeCloses === 1);
  assert.deepEqual(errors, []);
  await page.close();
  return {
    closeProtected: true,
    targetProtected: true,
    refreshDeferred: true,
    errors,
  };
}
