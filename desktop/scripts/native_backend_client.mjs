// Test-only client for the real Rust stdio processor. Production retains the
// binary Tauri path; base64 is used solely for the legacy browser-test adapter.
import { spawn } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";

export const root = fileURLToPath(new URL("../../", import.meta.url));
export function nativeClient(options = {}) {
  const executable =
    options.executable ??
    process.env.DIOPTAS_NATIVE_PROCESSOR ??
    path.join(
      root,
      "desktop/backend/target/debug",
      process.platform === "win32"
        ? "dioptas-processor.exe"
        : "dioptas-processor",
    );
  const child = spawn(
    options.command ?? executable,
    options.args ?? ["--source-root", root],
    {
      cwd: options.cwd ?? root,
      stdio: ["pipe", "pipe", "pipe"],
      env: {
        ...process.env,
        ...options.env,
        DIOPTAS_PYTHON: "/nonexistent/python",
        PATH: "/nonexistent",
      },
    },
  );
  const pending = new Map();
  const buffers = new Map();
  const diagnostics = [];
  let input = Buffer.alloc(4),
    filled = 0,
    packetHeader = null,
    readingHeader = false,
    nextId = 0;
  let headerBytes,
    lastPacketBytes = 0,
    lastHeaderBytes = 0;
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
  function finishPacket(bytes) {
    lastPacketBytes = 4 + headerBytes.length + bytes.length;
    lastHeaderBytes = headerBytes.length;
    let offset = 0;
    for (const buffer of packetHeader.buffers) {
      buffers.set(
        buffer.id,
        Buffer.from(bytes.subarray(offset, offset + buffer.length)),
      );
      offset += buffer.length;
    }
    const id = packetHeader.id;
    const task = pending.get(id);
    const result = packetHeader.result;
    let packet;
    if (task?.packet) {
      packet = Buffer.allocUnsafe(lastPacketBytes);
      packet.writeUInt32LE(headerBytes.length, 0);
      headerBytes.copy(packet, 4);
      bytes.copy(packet, 4 + headerBytes.length);
    }
    packetHeader = null;
    input = Buffer.alloc(4);
    filled = 0;
    readingHeader = false;
    if (task) {
      clearTimeout(task.timer);
      pending.delete(id);
      task.resolve(task.packet ? packet : result);
    }
  }
  // Fill each header/payload once. Repeated Buffer.concat copies a 40-MB
  // detector packet hundreds of times and distorts 9M browser benchmarks.
  child.stdout.on("data", (bytes) => {
    try {
      let offset = 0;
      while (offset < bytes.length) {
        const take = Math.min(input.length - filled, bytes.length - offset);
        bytes.copy(input, filled, offset, offset + take);
        filled += take;
        offset += take;
        if (filled !== input.length) continue;
        if (packetHeader) {
          finishPacket(input);
          continue;
        }
        if (readingHeader) {
          headerBytes = input;
          packetHeader = JSON.parse(input);
          const size = packetHeader.buffers.reduce(
            (sum, b) => sum + b.length,
            0,
          );
          if (
            !Number.isSafeInteger(size) ||
            size < 0 ||
            size > 1024 * 1024 * 1024
          )
            throw Error("Oversized native buffers");
          if (size === 0) finishPacket(Buffer.alloc(0));
          else {
            input = Buffer.allocUnsafe(size);
            filled = 0;
          }
        } else {
          const length = input.readUInt32LE(0);
          if (length === 0 || length > 256 * 1024 * 1024)
            throw Error("Oversized native header");
          input = Buffer.allocUnsafe(length);
          filled = 0;
          readingHeader = true;
        }
      }
    } catch (error) {
      fail(error);
    }
  });
  const request = (
    action,
    payload = {},
    cachedBuffers,
    packet = false,
    cachedProducts,
  ) =>
    new Promise((resolve, reject) => {
      const id = ++nextId;
      const timer = setTimeout(() => {
        pending.delete(id);
        reject(new Error(`Native command timed out: ${action}`));
      }, 45000);
      pending.set(id, { resolve, reject, timer, packet });
      child.stdin.write(
        JSON.stringify({
          id,
          action,
          payload,
          cachedBuffers: cachedBuffers ?? [...buffers.keys()].slice(-64),
          cachedProducts,
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
    invoke: (action, payload = {}) => request(action, payload),
    invokePacket: (action, payload = {}, cachedBuffers = [], cachedProducts) =>
      request(action, payload, cachedBuffers, true, cachedProducts),
    get lastPacketBytes() {
      return lastPacketBytes;
    },
    get lastHeaderBytes() {
      return lastHeaderBytes;
    },
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
