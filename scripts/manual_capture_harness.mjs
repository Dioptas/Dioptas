// Shared harness for the user-manual screenshots: the real React UI in headless
// Chromium, served by Vite on an ephemeral port and connected to the native Rust
// processor through the injected test bridge. No window is opened, port 1420 is
// never used, and user settings are isolated in a temporary HOME.
import assert from "node:assert/strict";
import { mkdtemp, readdir, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { createServer } from "vite";
import { chromium } from "playwright";
import { nativeClient, root } from "./native_backend_client.mjs";

export { root };
export const data = path.join(root, "tests/data");
export const fixture = (...parts) => path.join(data, ...parts);

export async function startManualSession({
  viewport = { width: 1440, height: 900 },
  deviceScaleFactor = 1.5,
} = {}) {
  const temporary = await mkdtemp(path.join(tmpdir(), "dioptas-manual-"));
  const native = nativeClient({
    timeoutMs: 180000,
    env: {
      HOME: temporary,
      DIOPTAS_CUSTOM_COMMANDS_FILE: path.join(
        temporary,
        "custom-commands.json",
      ),
    },
  });
  const server = await createServer({
    root,
    logLevel: "warn",
    server: { host: "127.0.0.1", port: 0 },
  });
  await server.listen();
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport, deviceScaleFactor });
  const page = await context.newPage();
  page.setDefaultTimeout(30000);
  const errors = [];
  page.on("pageerror", (error) => errors.push(error.message));

  // The native host answers file choosers. Here each chooser command receives
  // the path queued for it by the capture step that is about to click.
  const chosen = new Map();
  const choose = (action, value) => chosen.set(action, value);
  const log = [];
  const bridge = async (action, payload = {}) => {
    payload = { ...payload };
    // One-shot answers, keyed by "action" or "action:operation".
    const key = [`${action}:${payload.operation}`, action].find((name) =>
      chosen.has(name),
    );
    if (key && !payload.path && !payload.paths) {
      const value = chosen.get(key);
      chosen.delete(key);
      payload[Array.isArray(value) ? "paths" : "path"] = value;
    }
    const result = await native.invoke(action, payload);
    log.push({ action, ok: result.ok !== false, error: result.error });
    return native.browserResult(result);
  };
  await context.exposeFunction("__manualInvoke", bridge);
  await context.addInitScript(() => {
    window.__manualPending = 0;
    window.pywebview = {
      api: {
        invoke: async (action, payload) => {
          window.__manualPending++;
          try {
            return await window.__manualInvoke(action, payload);
          } finally {
            window.__manualPending--;
          }
        },
      },
    };
  });

  async function call(action, payload = {}) {
    const result = await native.invoke(action, payload);
    assert.ok(result.ok !== false, `${action}: ${result.error}`);
    return result;
  }
  async function settle(target = page, extra = 250) {
    await target.waitForFunction(
      () => !window.__manualPending && !document.querySelector(".spin"),
      null,
      { timeout: 180000 },
    );
    await target.evaluate(
      () =>
        new Promise((resolve) =>
          requestAnimationFrame(() => requestAnimationFrame(resolve)),
        ),
    );
    await target.waitForTimeout(extra);
  }
  async function open() {
    await page.goto(server.resolvedUrls.local[0]);
    await page
      .getByRole("button", { name: "Calibration", exact: true })
      .waitFor();
    await settle();
  }
  async function close() {
    await browser.close();
    await server.close();
    await native.close();
    await rm(temporary, { recursive: true, force: true });
  }
  return {
    page,
    context,
    native,
    call,
    choose,
    settle,
    open,
    close,
    errors,
    log,
    temporary,
    url: () => server.resolvedUrls.local[0],
    button: (name, scope = page) =>
      scope.getByRole("button", { name, exact: true }),
    tab: (name, scope = page) =>
      scope.getByRole("tab").filter({ hasText: new RegExp(`^${name}$`) }),
    mode: async (name) => {
      await page.getByRole("button", { name, exact: true }).first().click();
      await settle();
    },
  };
}

export async function mapImages() {
  // Natural order: the scan numbers are not zero-padded.
  const number = (name) => Number(name.match(/_map_(\d+)_/)?.[1] ?? 0);
  return (await readdir(fixture("map")))
    .filter((name) => name.endsWith(".tif"))
    .sort((a, b) => number(a) - number(b))
    .map((name) => fixture("map", name));
}
