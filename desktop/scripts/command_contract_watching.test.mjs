import assert from "node:assert/strict";
import { execFile } from "node:child_process";
import {
  cp,
  mkdir,
  mkdtemp,
  realpath,
  rm,
  symlink,
  writeFile,
} from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";
import { promisify } from "node:util";
import { createServer } from "vite";

const execute = promisify(execFile);
const repository = fileURLToPath(new URL("../../", import.meta.url));

test(
  "the real command checker preserves a warm Vite preview; the old tsconfig writes reload it",
  { timeout: 30000 },
  async () => {
    // Both the positive run and deliberate former-bug reproduction operate on
    // private OS-temp copies. No files are written into a user's watched checkout.
    const temporary = await mkdtemp(
      path.join(tmpdir(), "dioptas-contract-watch-"),
    );
    const desktop = path.join(temporary, "desktop");
    let server;
    try {
      for (const relative of [
        "desktop/src",
        "desktop/backend/src",
        "desktop/src-tauri/src",
        "desktop/scripts/type-fixtures",
        "desktop/scripts/check_command_contracts.mjs",
        "desktop/tsconfig.json",
      ])
        await cp(
          path.join(repository, relative),
          path.join(temporary, relative),
          { recursive: true },
        );
      await symlink(
        await realpath(path.join(repository, "desktop/node_modules")),
        path.join(desktop, "node_modules"),
      );
      server = await createServer({
        configFile: false,
        root: desktop,
        cacheDir: path.join(temporary, "vite-cache"),
        logLevel: "silent",
        server: { host: "127.0.0.1", port: 0 },
      });
      const reloads = [];
      const send = server.ws.send.bind(server.ws);
      let observeNegativeControl;
      server.ws.send = (payload, ...args) => {
        if (payload?.type === "full-reload") {
          reloads.push(payload);
          observeNegativeControl?.();
        }
        return send(payload, ...args);
      };
      await server.listen();
      const module = await fetch(
        server.resolvedUrls.local[0] + "src/navigationTiming.ts",
      );
      assert.equal(module.status, 200);
      await module.text(); // Populate Vite's TypeScript/tsconfig cache before the gate.
      const result = await execute(
        process.execPath,
        [path.join(desktop, "scripts/check_command_contracts.mjs")],
        { cwd: desktop, timeout: 20000 },
      );
      assert.match(
        result.stdout,
        /Checked \d+ typed command contracts and \d+ compile fixtures\./,
      );
      // Allow native watcher notifications to drain after the child exits.
      await new Promise((resolve) => setTimeout(resolve, 200));
      assert.deepEqual(
        reloads,
        [],
        "A read-only contract check must not reload live UI state",
      );

      const reloaded = new Promise((resolve) => {
        observeNegativeControl = resolve;
      });
      const oldDirectory = path.join(
        desktop,
        ".command-contract-types-negative-control",
      );
      await mkdir(oldDirectory);
      await writeFile(
        path.join(oldDirectory, "tsconfig.json"),
        JSON.stringify({
          extends: path.join(desktop, "tsconfig.json"),
          include: [path.join(desktop, "src")],
        }),
      );
      let timer;
      try {
        await Promise.race([
          reloaded,
          new Promise((_, reject) => {
            timer = setTimeout(
              () =>
                reject(
                  Error(
                    "The isolated former-bug control did not trigger Vite's tsconfig reload",
                  ),
                ),
              5000,
            );
          }),
        ]);
      } finally {
        clearTimeout(timer);
      }
      assert.ok(
        reloads.length > 0,
        "The negative control must exercise the real Vite watcher",
      );
    } finally {
      await server?.close();
      await rm(temporary, { recursive: true, force: true });
    }
  },
);
