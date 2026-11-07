// Test-only client for the real Rust stdio processor. Production retains the
// binary Tauri path; base64 is used solely for the legacy browser-test adapter.
import { spawn } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";

export const root = fileURLToPath(new URL("../../", import.meta.url));
export function nativeClient() {
  const executable =
    process.env.DIOPTAS_NATIVE_PROCESSOR ??
    path.join(
      root,
      "desktop/backend/target/debug",
      process.platform === "win32"
        ? "dioptas-processor.exe"
        : "dioptas-processor",
    );
  const child = spawn(executable, ["--source-root", root], {
    cwd: root,
    stdio: ["pipe", "pipe", "pipe"],
    env: {
      ...process.env,
      DIOPTAS_PYTHON: "/nonexistent/python",
      PATH: "/nonexistent",
    },
  });
  const pending = new Map();
  const buffers = new Map();
  const diagnostics = [];
  let input = Buffer.alloc(0),
    nextId = 0;
  child.stderr.on("data", (bytes) => diagnostics.push(bytes.toString()));
  function fail(error) {
    for (const task of pending.values()) {
      clearTimeout(task.timer);
      task.reject(error);
    }
    pending.clear();
  }
  child.on("error", fail);
  child.on("exit", (code) =>
    fail(new Error(`Native processor exited ${code}: ${diagnostics.join("")}`)),
  );
  child.stdout.on("data", (bytes) => {
    input = Buffer.concat([input, bytes]);
    try {
      while (input.length >= 4) {
        const length = input.readUInt32LE(0);
        if (length > 16 * 1024 * 1024)
          throw new Error("Oversized native header");
        if (input.length < 4 + length) return;
        const header = JSON.parse(input.subarray(4, 4 + length));
        const size = header.buffers.reduce((sum, b) => sum + b.length, 0);
        if (size > 1024 * 1024 * 1024)
          throw new Error("Oversized native buffers");
        if (input.length < 4 + length + size) return;
        let offset = 4 + length;
        for (const buffer of header.buffers) {
          buffers.set(
            buffer.id,
            Buffer.from(input.subarray(offset, offset + buffer.length)),
          );
          offset += buffer.length;
        }
        input = input.subarray(offset);
        const task = pending.get(header.id);
        if (task) {
          clearTimeout(task.timer);
          pending.delete(header.id);
          task.resolve(header.result);
        }
      }
    } catch (error) {
      fail(error);
    }
  });
  const invoke = (action, payload = {}) =>
    new Promise((resolve, reject) => {
      const id = ++nextId;
      const timer = setTimeout(() => {
        pending.delete(id);
        reject(new Error(`Native command timed out: ${action}`));
      }, 45000);
      pending.set(id, { resolve, reject, timer });
      child.stdin.write(
        JSON.stringify({
          id,
          action,
          payload,
          cachedBuffers: [...buffers.keys()].slice(-64),
        }) + "\n",
      );
    });
  function browserResult(value) {
    if (Array.isArray(value)) return value.map(browserResult);
    if (value && typeof value === "object") {
      const result = Object.fromEntries(
        Object.entries(value).map(([k, v]) => [k, browserResult(v)]),
      );
      if (value.bufferId) {
        const bytes = buffers.get(value.bufferId);
        if (!bytes) throw new Error(`Missing native buffer ${value.bufferId}`);
        result.data = bytes.toString("base64");
      }
      return result;
    }
    return value;
  }
  return {
    child,
    invoke,
    browserResult,
    buffers,
    diagnostics,
    async close() {
      child.stdin.end();
      if (child.exitCode !== null) return;
      await new Promise((resolve) => {
        const timer = setTimeout(() => {
          child.kill();
        }, 3000);
        child.once("exit", () => {
          clearTimeout(timer);
          resolve();
        });
      });
    },
  };
}
