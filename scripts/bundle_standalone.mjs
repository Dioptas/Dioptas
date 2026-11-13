// Local standalone artifact only: ad-hoc signing, no publishing/notarization.
import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";
import path from "node:path";
const desktop = fileURLToPath(new URL("../", import.meta.url));
const env = {
  ...process.env,
  MACOSX_DEPLOYMENT_TARGET: "14.0",
  APPLE_SIGNING_IDENTITY: "-",
};
for (const key of [
  "APPLE_ID",
  "APPLE_PASSWORD",
  "APPLE_API_KEY",
  "APPLE_API_ISSUER",
  "APPLE_API_KEY_PATH",
  "APPLE_CERTIFICATE",
  "APPLE_CERTIFICATE_PASSWORD",
])
  delete env[key];
const cli = path.join(desktop, "node_modules/@tauri-apps/cli/tauri.js");
const child = spawn(
  process.execPath,
  [cli, "build", "--bundles", "app", ...process.argv.slice(2)],
  {
    cwd: desktop,
    env,
    stdio: "inherit",
  },
);
child.on("error", (error) => {
  console.error(error);
  process.exitCode = 1;
});
child.on("exit", (code) => {
  process.exitCode = code ?? 1;
});
