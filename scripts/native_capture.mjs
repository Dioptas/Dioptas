import { execFile } from "node:child_process";
import { promisify } from "node:util";
import { mkdir } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const exec = promisify(execFile);
export async function prepareNativeCapture(directory) {
  if (process.platform !== "darwin") return null;
  await mkdir(directory, { recursive: true });
  const binary = path.join(directory, "window-id");
  await exec("swiftc", [
    fileURLToPath(new URL("native_window_id.swift", import.meta.url)),
    "-o",
    binary,
  ]);
  return async (pid, label, name) => {
    const title =
      {
        "batch-window": "Batch",
        "map-window": "Map",
        "phase-editor": "Phase Editor",
      }[label] ?? "";
    const { stdout } = await exec(binary, [String(pid), title]);
    const id = stdout.trim();
    if (!/^\d+$/.test(id)) throw Error("Invalid test window ID");
    const output = path.join(
      directory,
      `${name.replace(/[^a-z0-9-]/gi, "-")}.png`,
    );
    await exec("/usr/sbin/screencapture", ["-x", "-l", id, output]);
    return output;
  };
}
