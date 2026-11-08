import { randomBytes } from "node:crypto";
import { execFileSync } from "node:child_process";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

// A different bundle identifier alone does not isolate WKWebView's default
// website store on macOS. Every native test gets a named store of its own;
// restart campaigns reuse this configuration, including companion windows.
export async function nativeTestProfile(kind) {
  if (
    process.platform === "darwin" &&
    Number(
      execFileSync("sw_vers", ["-productVersion"], { encoding: "utf8" }).split(
        ".",
      )[0],
    ) < 14
  )
    throw Error(
      "Named private WebKit stores for native restart tests require macOS 14 or newer.",
    );
  const desktop = fileURLToPath(new URL("../", import.meta.url));
  const base = JSON.parse(
    await readFile(path.join(desktop, "src-tauri/tauri.conf.json"), "utf8"),
  );
  const id = `${kind}-${process.pid}-${Date.now()}`;
  const directory = path.join(desktop, "artifacts/native-profiles", id);
  await mkdir(directory, { recursive: true });
  const commands = path.join(directory, "commands.json");
  await writeFile(commands, JSON.stringify({ version: 1, commands: [] }));
  return {
    config: {
      identifier: `org.dioptas.desktop.${id}`,
      app: {
        security: {
          capabilities: [
            ...base.app.security.capabilities,
            {
              identifier: "native-test-window-state",
              windows: ["main", "batch-window", "map-window", "phase-editor"],
              permissions: [
                "core:window:allow-get-all-windows",
                "core:window:allow-is-focused",
                "core:window:allow-set-focus",
                "core:window:allow-is-visible",
              ],
            },
          ],
        },
        windows: base.app.windows.map((window) => ({
          ...window,
          dataDirectory: path.join(directory, "webview"),
        })),
      },
    },
    env: {
      ...process.env,
      DIOPTAS_CUSTOM_COMMANDS_FILE: commands,
      DIOPTAS_TEST_WEBVIEW_STORE: JSON.stringify([...randomBytes(16)]),
      DIOPTAS_MAP_WINDOW_STATE:
        process.env.DIOPTAS_MAP_WINDOW_STATE ??
        path.join(directory, "map-window.json"),
      DIOPTAS_BATCH_WINDOW_STATE:
        process.env.DIOPTAS_BATCH_WINDOW_STATE ??
        path.join(directory, "batch-window.json"),
    },
    directory,
  };
}
